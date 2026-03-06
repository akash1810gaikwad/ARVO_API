from typing import Optional, Tuple, List
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
from decimal import Decimal
import json
import secrets
import stripe

from config.settings import settings
from models.mysql_models import (
    Subscriber, Subscription, ChildSimCard, SimInventory,
    Payment, AuditTrail
)
from models.mysql_models import Order
from models.mysql_models import Customer
from models.mysql_models import PlanMaster
from schemas.new_subscription_schema import CreateSubscriptionRequest, ChildDetails
from utils.logger import logger

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class NewSubscriptionService:
    """Service for managing subscriptions with resumable process"""
    
    def generate_order_number(self) -> str:
        """Generate unique order number"""
        timestamp = datetime.utcnow().strftime("%Y%m%d")
        random_part = secrets.token_hex(4).upper()
        return f"ORD-{timestamp}-{random_part}"
    
    def generate_subscription_number(self) -> str:
        """Generate unique subscription number"""
        timestamp = datetime.utcnow().strftime("%Y%m%d")
        random_part = secrets.token_hex(4).upper()
        return f"SUB-{timestamp}-{random_part}"
    
    def log_audit(
        self,
        db: Session,
        action: str,
        step: str,
        status: str,
        order_id: Optional[int] = None,
        subscription_id: Optional[int] = None,
        customer_id: Optional[int] = None,
        details: Optional[dict] = None,
        error_message: Optional[str] = None,
        ip_address: Optional[str] = None
    ):
        """Log every step to audit trail"""
        try:
            audit = AuditTrail(
                order_id=order_id,
                subscription_id=subscription_id,
                customer_id=customer_id,
                action=action,
                step=step,
                status=status,
                details=json.dumps(details) if details else None,
                error_message=error_message,
                ip_address=ip_address
            )
            db.add(audit)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to log audit: {str(e)}")
            db.rollback()
    
    def calculate_pricing(
        self,
        plan: PlanMaster,
        number_of_children: int,
        start_date: date,
        end_date: date
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """Calculate pricing: (plan_price_per_child, initial_payment, monthly_amount)"""
        # Use monthly price per child
        plan_price_per_child = plan.monthly_price
        
        # Calculate full months between start and end date
        months_diff = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
        
        # Ensure at least 1 month
        if months_diff < 1:
            months_diff = 1
        
        # Initial payment is for the FULL subscription period (full months only)
        initial_payment = plan_price_per_child * number_of_children * months_diff
        
        # Monthly amount after initial period (for recurring billing if auto_renew)
        monthly_amount = plan_price_per_child * number_of_children
        
        return (
            Decimal(str(plan_price_per_child)),
            Decimal(str(initial_payment)),
            Decimal(str(monthly_amount))
        )
    
    def create_subscription_order(
        self,
        db: Session,
        request: CreateSubscriptionRequest,
        ip_address: Optional[str] = None
    ) -> Optional[Order]:
        """
        Complete subscription creation process with resumability
        Steps:
        1. Create Order (INITIATED)
        2. Create/Get Subscriber (SUBSCRIBER_CREATED)
        3. Create Subscription (SUBSCRIPTION_CREATED)
        4. Assign SIM Cards (SIMS_ASSIGNED)
        5. Process Payment (PAYMENT_PROCESSED)
        6. Complete Order (COMPLETED)
        
        Promo Code Handling:
        - Validates promo code from database
        - If bypass_payment=True: Creates dummy payment
        - If activate_sim=False: Allocates SIM but doesn't activate
        """
        order = None
        promo_code_obj = None
        bypass_payment = False
        activate_sim = True
        
        # Validate promo code if provided
        if request.promo_code:
            from services.promo_code_service import promo_code_service
            is_valid, message, promo_code_obj = promo_code_service.validate_promo_code(db, request.promo_code)
            
            if not is_valid:
                raise ValueError(f"Promo code validation failed: {message}")
            
            # Get promo code settings
            bypass_payment = promo_code_obj.bypass_payment
            activate_sim = promo_code_obj.activate_sim
            
            logger.info(f"Promo code '{request.promo_code}' validated: bypass_payment={bypass_payment}, activate_sim={activate_sim}")
        
        try:
            # Get customer
            customer = db.query(Customer).filter(Customer.id == request.customer_id).first()
            if not customer:
                raise ValueError("Customer not found")
            
            # Get plan
            plan = db.query(PlanMaster).filter(PlanMaster.id == request.plan_id).first()
            if not plan:
                raise ValueError("Plan not found")
            
            # Calculate pricing
            plan_price_per_child, initial_payment, monthly_amount = self.calculate_pricing(
                plan, len(request.children), request.start_date, request.end_date
            )
            
            # STEP 1: Create Order
            order_number = self.generate_order_number()
            children_json = json.dumps([{"name": c.name, "age": c.age} for c in request.children])
            
            order = Order(
                customer_id=request.customer_id,
                order_number=order_number,
                order_type="SUBSCRIPTION",
                order_status="PENDING",
                plan_id=request.plan_id,
                plan_name=plan.plan_name,
                children_details=children_json,
                number_of_children=len(request.children),
                plan_price_per_child=plan_price_per_child,
                initial_payment_amount=initial_payment,
                monthly_amount=monthly_amount,
                total_amount=initial_payment,
                currency=request.currency,
                auto_renew=request.auto_renew,
                sim_type=request.sim_type,  # Store sim_type for resumability
                start_date=request.start_date,  # Store start_date for resumability
                end_date=request.end_date,  # Store end_date for resumability
                process_state="INITIATED"
            )
            
            db.add(order)
            db.commit()
            db.refresh(order)
            
            self.log_audit(
                db, "CREATE_SUBSCRIPTION", "ORDER_CREATED", "SUCCESS",
                order_id=order.id, customer_id=request.customer_id,
                details={"order_number": order_number}, ip_address=ip_address
            )
            
            # STEP 2: Create/Get Subscriber
            subscriber = self._create_or_get_subscriber(db, customer, order, ip_address)
            if not subscriber:
                raise Exception("Failed to create subscriber")
            
            order.subscriber_id = subscriber.id
            order.process_state = "SUBSCRIBER_CREATED"
            order.last_successful_step = "SUBSCRIBER_CREATED"
            db.commit()
            
            # STEP 3: Create Subscription
            subscription = self._create_subscription(
                db, subscriber, plan, request, order,
                plan_price_per_child, initial_payment, monthly_amount, ip_address
            )
            if not subscription:
                raise Exception("Failed to create subscription")
            
            order.subscription_id = subscription.id
            order.process_state = "SUBSCRIPTION_CREATED"
            order.last_successful_step = "SUBSCRIPTION_CREATED"
            db.commit()
            
            # USER JOURNEY STEP 2: Plan Selection
            try:
                from repositories.user_journey_repo import UserJourneyRepository
                from schemas.user_journey_schema import UserJourneyCreate
                
                # Check if journey exists, if not create it
                journey = UserJourneyRepository.get_journey_by_customer_id(db, request.customer_id)
                if not journey:
                    logger.warning(f"No journey found for customer {request.customer_id}, creating one")
                    journey_data = UserJourneyCreate(
                        customer_id=request.customer_id,
                        customer_email=customer.email,
                        registration_payload=json.dumps({
                            "source": "auto_created_during_subscription",
                            "note": "Journey created automatically during subscription"
                        })
                    )
                    journey = UserJourneyRepository.create_journey(db, journey_data)
                
                # Update plan selection
                UserJourneyRepository.update_plan_selection(
                    db=db,
                    customer_id=request.customer_id,
                    plan_id=request.plan_id,
                    stripe_session_id=f"ORDER_{order.order_number}",  # Using order number as reference
                    payload_data={
                        "plan_id": request.plan_id,
                        "plan_name": plan.plan_name,
                        "children_count": len(request.children),
                        "sim_type": request.sim_type,
                        "start_date": str(request.start_date),
                        "end_date": str(request.end_date),
                        "total_amount": float(initial_payment)
                    }
                )
                logger.info(f"Journey Step 2 (Plan Selection) completed for customer {request.customer_id}")
            except Exception as journey_error:
                logger.error(f"Failed to update journey Step 2: {journey_error}")
            
            # STEP 4: Assign SIM Cards (only if pSIM is selected)
            sim_cards = []
            if request.sim_type == "pSIM":
                sim_cards = self._assign_sim_cards(db, subscription, subscriber, request.children, request.sim_type, order, ip_address, not activate_sim)
                if not sim_cards:
                    logger.warning(f"No SIM cards assigned for order {order.order_number} - continuing without SIM allocation")
                    sim_cards = []  # Initialize empty list to continue

            order.process_state = "SIMS_ASSIGNED"
            order.last_successful_step = "SIMS_ASSIGNED"
            db.commit()
            
            # STEP 5: Process Payment
            payment_success = self._process_payment(
                db, order, subscription, subscriber, request.payment_method_id, ip_address, bypass_payment, request.promo_code
            )
            if not payment_success:
                raise Exception("Payment processing failed")
            
            order.process_state = "PAYMENT_PROCESSED"
            order.last_successful_step = "PAYMENT_PROCESSED"
            order.payment_status = "PAID"
            order.payment_date = datetime.utcnow()
            db.commit()
            
            # USER JOURNEY STEP 3: Payment Success
            try:
                from repositories.user_journey_repo import UserJourneyRepository
                UserJourneyRepository.update_payment_success(
                    db=db,
                    stripe_session_id=f"ORDER_{order.order_number}",
                    order_id=order.id,
                    payload_data={
                        "payment_intent_id": order.stripe_payment_intent_id,
                        "amount": float(order.total_amount),
                        "currency": order.currency,
                        "payment_status": "PAID",
                        "payment_method_id": request.payment_method_id
                    }
                )
                logger.info(f"Journey Step 3 (Payment Success) completed for order {order.id}")
            except Exception as journey_error:
                logger.error(f"Failed to update journey Step 3: {journey_error}")
            
            # STEP 6: Complete Order
            order.order_status = "COMPLETED"
            order.process_state = "COMPLETED"
            order.completed_at = datetime.utcnow()
            db.commit()
            
            # Send QR code emails for all SIM cards immediately after order completion (only if pSIM is selected)
            if request.sim_type == "pSIM" and sim_cards:
                try:
                    from services.email_service import send_esim_qr_email
                    from utils.qr_generator import generate_qr_code

                    logger.info(f"Sending QR code emails for {len(sim_cards)} SIM cards")

                    for idx, sim_card in enumerate(sim_cards, start=1):
                        try:
                            # Use activation_code if available, otherwise use ICCID
                            activation_code_to_use = sim_card.activation_code or sim_card.iccid

                            logger.info(f"Preparing QR code email {idx}/{len(sim_cards)} for {sim_card.child_name}")

                            # Generate QR code
                            qr_image_bytes = generate_qr_code(activation_code_to_use, size=200)

                            # Send email
                            email_sent = send_esim_qr_email(
                                customer_email=customer.email,
                                child_name=sim_card.child_name,
                                mobile_number=sim_card.msisdn or "Pending",
                                iccid=sim_card.iccid,
                                qr_code=activation_code_to_use,
                                qr_image_bytes=qr_image_bytes
                            )

                            if email_sent:
                                logger.info(f"QR code email sent successfully to {customer.email} for {sim_card.child_name}")
                            else:
                                logger.warning(f"Failed to send QR code email for {sim_card.child_name}")

                        except Exception as email_error:
                            logger.error(f"Error sending QR code email for {sim_card.child_name}: {str(email_error)}", exc_info=True)

                    # USER JOURNEY STEP 6: QR Code Generation & Email
                    try:
                        from repositories.user_journey_repo import UserJourneyRepository
                        UserJourneyRepository.update_qr_code_generation(
                            db=db,
                            order_id=order.id,
                            payload_data={
                                "qr_code_generated": True,
                                "email_sent": True,
                                "email_to": customer.email,
                                "total_emails_sent": len(sim_cards),
                                "children_names": [sim.child_name for sim in sim_cards]
                            }
                        )
                        logger.info(f"Journey Step 6 (QR Code & Email) completed for order {order.id}")
                    except Exception as journey_error:
                        logger.error(f"Failed to update journey Step 6: {journey_error}")

                except Exception as qr_error:
                    logger.error(f"Error in QR code email process: {str(qr_error)}", exc_info=True)
            elif request.sim_type == "pSIM" and not sim_cards:
                logger.info(f"No SIM cards available for order {order.order_number} - skipping QR code email sending")
            else:
                logger.info(f"Skipping QR code email sending - sim_type is '{request.sim_type}', not 'pSIM'")
            
            # Send order confirmation email with Stripe invoice
            try:
                from services.email_service import send_order_confirmation_email
                
                # Get Stripe invoice if payment was processed
                invoice_url = None
                if order.stripe_payment_intent_id and not bypass_payment:
                    from services.stripe_service import stripe_service
                    invoice_data = stripe_service.get_invoice_by_payment_intent(order.stripe_payment_intent_id)
                    if invoice_data:
                        invoice_url = invoice_data.get('hosted_invoice_url') or invoice_data.get('invoice_pdf')
                
                # Send order confirmation
                confirmation_sent = send_order_confirmation_email(
                    customer_email=customer.email,
                    customer_name=customer.full_name,
                    order_number=order.order_number,
                    plan_name=plan.plan_name,
                    number_of_children=len(request.children),
                    total_amount=float(order.total_amount),
                    currency=order.currency,
                    invoice_url=invoice_url
                )
                
                if confirmation_sent:
                    logger.info(f"Order confirmation email sent to {customer.email}")
                else:
                    logger.warning(f"Failed to send order confirmation email to {customer.email}")
                    
            except Exception as conf_error:
                logger.error(f"Error sending order confirmation email: {str(conf_error)}", exc_info=True)
            
            # Increment promo code usage if promo was used
            if promo_code_obj:
                from services.promo_code_service import promo_code_service
                promo_code_service.increment_usage(db, promo_code_obj.id)
            
            self.log_audit(
                db, "CREATE_SUBSCRIPTION", "ORDER_COMPLETED", "SUCCESS",
                order_id=order.id, subscription_id=subscription.id,
                customer_id=request.customer_id, ip_address=ip_address
            )
            
            logger.info(f"Subscription order completed: {order.order_number}")
            return order
            
        except Exception as e:
            logger.error(f"Error creating subscription order: {str(e)}", exc_info=True)
            
            if order:
                order.order_status = "FAILED"
                order.failure_reason = str(e)
                order.failed_at = datetime.utcnow()
                try:
                    db.commit()
                except Exception:
                    db.rollback()
                
                self.log_audit(
                    db, "CREATE_SUBSCRIPTION", order.process_state or "UNKNOWN", "FAILED",
                    order_id=order.id, customer_id=request.customer_id,
                    error_message=str(e), ip_address=ip_address
                )
            
            raise  # Re-raise so route can show the actual error
    
    def _create_or_get_subscriber(
        self,
        db: Session,
        customer: Customer,
        order: Order,
        ip_address: Optional[str]
    ) -> Optional[Subscriber]:
        """Create or get existing subscriber and update customer's number_of_children"""
        try:
            # Check if subscriber exists
            subscriber = db.query(Subscriber).filter(
                Subscriber.customer_id == customer.id
            ).first()
            
            if subscriber:
                # Existing subscriber - update customer's number_of_children
                current_children = customer.number_of_children or 0
                new_children_count = order.number_of_children
                customer.number_of_children = current_children + new_children_count
                db.commit()
                
                self.log_audit(
                    db, "CREATE_SUBSCRIPTION", "SUBSCRIBER_EXISTS", "SUCCESS",
                    order_id=order.id, customer_id=customer.id,
                    details={
                        "subscriber_id": subscriber.id,
                        "previous_children_count": current_children,
                        "new_children_count": new_children_count,
                        "total_children_count": customer.number_of_children
                    }, 
                    ip_address=ip_address
                )
                logger.info(f"Reusing existing subscriber {subscriber.id} for customer {customer.id}. Updated children count from {current_children} to {customer.number_of_children}")
                return subscriber
            
            # Create Stripe customer for new subscriber
            stripe_customer = stripe.Customer.create(
                email=customer.email,
                name=customer.full_name,
                phone=customer.phone_number,
                metadata={"customer_id": customer.id}
            )
            
            # Create new subscriber
            subscriber = Subscriber(
                customer_id=customer.id,
                stripe_customer_id=stripe_customer.id,
                auto_renew_enabled=order.auto_renew
            )
            
            db.add(subscriber)
            
            # Set initial number_of_children for new subscriber
            customer.number_of_children = order.number_of_children
            
            db.commit()
            db.refresh(subscriber)
            
            self.log_audit(
                db, "CREATE_SUBSCRIPTION", "SUBSCRIBER_CREATED", "SUCCESS",
                order_id=order.id, customer_id=customer.id,
                details={
                    "subscriber_id": subscriber.id, 
                    "stripe_customer_id": stripe_customer.id,
                    "initial_children_count": customer.number_of_children
                },
                ip_address=ip_address
            )
            
            logger.info(f"Created new subscriber {subscriber.id} for customer {customer.id} with {customer.number_of_children} children")
            return subscriber
            
        except Exception as e:
            logger.error(f"Error creating subscriber: {str(e)}")
            self.log_audit(
                db, "CREATE_SUBSCRIPTION", "SUBSCRIBER_CREATION", "FAILED",
                order_id=order.id, customer_id=customer.id,
                error_message=str(e), ip_address=ip_address
            )
            return None
    
    def _create_subscription(
        self,
        db: Session,
        subscriber: Subscriber,
        plan: PlanMaster,
        request: CreateSubscriptionRequest,
        order: Order,
        plan_price_per_child: Decimal,
        initial_payment: Decimal,
        monthly_amount: Decimal,
        ip_address: Optional[str]
    ) -> Optional[Subscription]:
        """Create subscription record"""
        try:
            subscription_number = self.generate_subscription_number()
            
            # Calculate next billing date (should be the end_date since we charge full period upfront)
            next_billing_date = request.end_date
            
            subscription = Subscription(
                subscriber_id=subscriber.id,
                plan_id=plan.id,
                subscription_number=subscription_number,
                status="ACTIVE",
                start_date=request.start_date,
                end_date=request.end_date,
                next_billing_date=next_billing_date,
                number_of_children=len(request.children),
                plan_price_per_child=plan_price_per_child,
                total_monthly_amount=monthly_amount,
                initial_payment_amount=initial_payment,
                currency=request.currency,
                billing_cycle="MONTHLY",
                initial_months=3,
                auto_renew=request.auto_renew
            )
            
            db.add(subscription)
            db.commit()
            db.refresh(subscription)
            
            self.log_audit(
                db, "CREATE_SUBSCRIPTION", "SUBSCRIPTION_CREATED", "SUCCESS",
                order_id=order.id, subscription_id=subscription.id,
                customer_id=request.customer_id,
                details={"subscription_number": subscription_number}, ip_address=ip_address
            )
            
            return subscription
            
        except Exception as e:
            logger.error(f"Error creating subscription: {str(e)}")
            self.log_audit(
                db, "CREATE_SUBSCRIPTION", "SUBSCRIPTION_CREATION", "FAILED",
                order_id=order.id, customer_id=request.customer_id,
                error_message=str(e), ip_address=ip_address
            )
            return None
    
    def _assign_sim_cards(
        self,
        db: Session,
        subscription: Subscription,
        subscriber: Subscriber,
        children: List[ChildDetails],
        sim_type: str,
        order: Order,
        ip_address: Optional[str],
        is_test_order: bool = False
    ) -> Optional[List[ChildSimCard]]:
        """Assign SIM cards to children from inventory based on sim_type
        
        Args:
            is_test_order: If True, SIM is allocated but not activated (for ARVOADMINTEST_@2025)
        """
        try:
            sim_cards = []
            assigned_sim_ids = []  # Track assigned SIMs to avoid duplicates
            
            for idx, child in enumerate(children, start=1):
                # Get available SIM from inventory with matching sim_type
                # Exclude already assigned SIMs in this transaction
                query = db.query(SimInventory).filter(
                    SimInventory.status == "AVAILABLE",
                    SimInventory.sim_type == sim_type  # Filter by sim_type
                )
                
                # Exclude SIMs already assigned in this loop
                if assigned_sim_ids:
                    query = query.filter(~SimInventory.id.in_(assigned_sim_ids))
                
                sim_inventory = query.first()
                
                if not sim_inventory:
                    raise Exception(f"No available {sim_type} SIM cards in inventory for child {idx}")
                
                # Mark this SIM as assigned in our tracking list
                assigned_sim_ids.append(sim_inventory.id)
                
                # Update SIM inventory status immediately
                sim_inventory.status = "ASSIGNED"
                sim_inventory.assigned_at = datetime.utcnow()
                
                # Create child SIM card record
                # For test orders, don't activate the SIM
                child_sim = ChildSimCard(
                    subscription_id=subscription.id,
                    subscriber_id=subscriber.id,
                    child_name=child.name,
                    child_age=child.age,
                    child_order=idx,
                    sim_inventory_id=sim_inventory.id,
                    sim_number=sim_inventory.sim_number,
                    iccid=sim_inventory.iccid,
                    msisdn=sim_inventory.msisdn,
                    activation_code=sim_inventory.activation_code,
                    sim_type=sim_inventory.sim_type,
                    is_active=False if is_test_order else True,  # Don't activate for test orders
                    activation_date=None if is_test_order else datetime.utcnow()  # No activation date for test orders
                )
                
                db.add(child_sim)
                db.flush()  # Flush to get the child_sim.id
                
                # Update the assigned_to_child_sim_id
                sim_inventory.assigned_to_child_sim_id = child_sim.id
                
                sim_cards.append(child_sim)
            
            db.commit()
            
            self.log_audit(
                db, "CREATE_SUBSCRIPTION", "SIMS_ASSIGNED", "SUCCESS",
                order_id=order.id, subscription_id=subscription.id,
                customer_id=subscriber.customer_id,
                details={"sim_cards_count": len(sim_cards), "sim_type": sim_type, "is_test_order": is_test_order}, ip_address=ip_address
            )
            
            # USER JOURNEY STEP 4: ICCID Allocation
            try:
                from repositories.user_journey_repo import UserJourneyRepository
                # Get first SIM for tracking
                first_sim = sim_cards[0] if sim_cards else None
                if first_sim and first_sim.sim_inventory_id:
                    UserJourneyRepository.update_iccid_allocation(
                        db=db,
                        order_id=order.id,
                        sim_id=first_sim.sim_inventory_id,
                        payload_data={
                            "total_sims_allocated": len(sim_cards),
                            "sim_type": sim_type,
                            "iccids": [sim.iccid for sim in sim_cards if sim.iccid],
                            "sim_numbers": [sim.sim_number for sim in sim_cards if sim.sim_number]
                        }
                    )
                    logger.info(f"Journey Step 4 (ICCID Allocation) completed for order {order.id}")
            except Exception as journey_error:
                logger.error(f"Failed to update journey Step 4: {journey_error}")
            
            return sim_cards
            
        except Exception as e:
            logger.error(f"Error assigning SIM cards: {str(e)}")
            self.log_audit(
                db, "CREATE_SUBSCRIPTION", "SIM_ASSIGNMENT", "FAILED",
                order_id=order.id, subscription_id=subscription.id,
                customer_id=subscriber.customer_id,
                error_message=str(e), ip_address=ip_address
            )
            db.rollback()
            return None
    
    def _process_payment(
        self,
        db: Session,
        order: Order,
        subscription: Subscription,
        subscriber: Subscriber,
        payment_method_id: str,
        ip_address: Optional[str],
        bypass_payment: bool = False,
        promo_code: Optional[str] = None
    ) -> bool:
        """Process initial payment through Stripe or create dummy payment for promo codes
        
        Args:
            bypass_payment: If True, creates dummy payment instead of charging Stripe
            promo_code: Promo code used (for logging)
        """
        try:
            # Handle promo codes with payment bypass
            if bypass_payment:
                logger.info(f"Creating dummy payment for promo code '{promo_code}' - Order: {order.order_number}")
                
                # Generate dummy payment intent ID
                dummy_payment_intent_id = f"pi_PROMO_{order.order_number}_{int(datetime.utcnow().timestamp())}"
                
                # Update order with dummy payment info
                order.stripe_payment_intent_id = dummy_payment_intent_id
                order.payment_method = f"promo_{promo_code}" if promo_code else "promo"
                
                # Create dummy payment record
                payment = Payment(
                    order_id=order.id,
                    subscription_id=subscription.id,
                    subscriber_id=subscriber.id,
                    payment_type="INITIAL",
                    amount=order.initial_payment_amount,
                    currency=order.currency,
                    status="SUCCEEDED",
                    stripe_payment_intent_id=dummy_payment_intent_id,
                    payment_method_type=f"promo_{promo_code}" if promo_code else "promo",
                    card_brand=None,
                    card_last4=None,
                    billing_period_start=subscription.start_date,
                    billing_period_end=subscription.start_date + timedelta(days=90),
                    payment_date=datetime.utcnow()
                )
                
                db.add(payment)
                db.commit()
                
                self.log_audit(
                    db, "CREATE_SUBSCRIPTION", "PAYMENT_PROCESSED", "SUCCESS",
                    order_id=order.id, subscription_id=subscription.id,
                    customer_id=subscriber.customer_id,
                    details={
                        "payment_intent_id": dummy_payment_intent_id,
                        "amount": float(order.initial_payment_amount),
                        "payment_type": "promo_bypass",
                        "promo_code": promo_code
                    }, ip_address=ip_address
                )
                
                return True
            
            # Normal Stripe payment processing
            # Attach payment method to customer
            stripe.PaymentMethod.attach(
                payment_method_id,
                customer=subscriber.stripe_customer_id
            )
            
            # Set as default payment method
            stripe.Customer.modify(
                subscriber.stripe_customer_id,
                invoice_settings={"default_payment_method": payment_method_id}
            )
            
            # Get payment method details
            payment_method = stripe.PaymentMethod.retrieve(payment_method_id)
            
            # Update subscriber with payment method info
            subscriber.default_payment_method_id = payment_method_id
            if payment_method.card:
                subscriber.card_brand = payment_method.card.brand
                subscriber.card_last4 = payment_method.card.last4
                subscriber.card_exp_month = payment_method.card.exp_month
                subscriber.card_exp_year = payment_method.card.exp_year
            
            db.commit()
            
            # Determine if we should create a Stripe subscription or one-time payment
            if order.auto_renew:
                logger.info(f"Creating Stripe subscription with auto-renew for order {order.order_number}")
                
                # Create Stripe Price for recurring billing
                monthly_amount_cents = int(float(order.monthly_amount) * 100)
                stripe_price = stripe.Price.create(
                    unit_amount=monthly_amount_cents,
                    currency=order.currency.lower(),
                    recurring={"interval": "month"},
                    product_data={
                        "name": f"{order.plan_name} - Monthly Subscription",
                        "metadata": {
                            "plan_id": order.plan_id,
                            "plan_name": order.plan_name
                        }
                    }
                )
                
                # Calculate trial end (delay first recurring charge until after prepaid period)
                trial_end_timestamp = None
                if subscription.next_billing_date:
                    # Convert date to datetime if needed
                    if isinstance(subscription.next_billing_date, date) and not isinstance(subscription.next_billing_date, datetime):
                        trial_end_datetime = datetime.combine(subscription.next_billing_date, datetime.min.time())
                    else:
                        trial_end_datetime = subscription.next_billing_date
                    trial_end_timestamp = int(trial_end_datetime.timestamp())
                    logger.info(f"Stripe subscription trial will end on {subscription.next_billing_date}")
                
                # Create Stripe subscription for recurring billing
                stripe_subscription = stripe.Subscription.create(
                    customer=subscriber.stripe_customer_id,
                    items=[{"price": stripe_price.id}],
                    default_payment_method=payment_method_id,
                    trial_end=trial_end_timestamp,  # Delay first recurring charge
                    payment_settings={"save_default_payment_method": "on_subscription"},
                    metadata={
                        "subscriber_id": subscriber.id,
                        "subscription_id": subscription.id,
                        "subscription_number": subscription.subscription_number,
                        "plan_id": order.plan_id,
                        "number_of_children": order.number_of_children
                    }
                )
                
                logger.info(f"✅ Stripe subscription created: {stripe_subscription.id}")
                
                # Update our subscription with Stripe IDs
                subscription.stripe_subscription_id = stripe_subscription.id
                subscription.stripe_price_id = stripe_price.id
                db.commit()
                
                # Create one-time payment intent for the initial prepaid period
                amount_cents = int(float(order.initial_payment_amount) * 100)
                payment_intent = stripe.PaymentIntent.create(
                    amount=amount_cents,
                    currency=order.currency.lower(),
                    customer=subscriber.stripe_customer_id,
                    payment_method=payment_method_id,
                    confirm=True,
                    off_session=True,
                    metadata={
                        "order_id": order.id,
                        "subscription_id": subscription.id,
                        "order_number": order.order_number,
                        "payment_type": "initial_prepaid",
                        "stripe_subscription_id": stripe_subscription.id
                    }
                )
                
                logger.info(f"✅ Initial payment processed: {payment_intent.id} for {order.currency} {order.initial_payment_amount}")
                
            else:
                logger.info(f"Creating one-time payment (no auto-renew) for order {order.order_number}")
                
                # No auto-renew: create one-time payment intent only
                amount_cents = int(float(order.initial_payment_amount) * 100)
                payment_intent = stripe.PaymentIntent.create(
                    amount=amount_cents,
                    currency=order.currency.lower(),
                    customer=subscriber.stripe_customer_id,
                    payment_method=payment_method_id,
                    confirm=True,
                    off_session=True,
                    metadata={
                        "order_id": order.id,
                        "subscription_id": subscription.id,
                        "order_number": order.order_number,
                        "auto_renew": "false",
                        "payment_type": "one_time"
                    }
                )
                
                logger.info(f"✅ One-time payment processed: {payment_intent.id} for {order.currency} {order.initial_payment_amount}")
            
            # Check payment status
            if payment_intent.status != "succeeded":
                raise Exception(f"Payment failed with status: {payment_intent.status}")
            
            # Update order with payment info
            order.stripe_payment_intent_id = payment_intent.id
            order.payment_method = payment_method.type
            
            # Create payment record
            payment = Payment(
                order_id=order.id,
                subscription_id=subscription.id,
                subscriber_id=subscriber.id,
                payment_type="INITIAL",
                amount=order.initial_payment_amount,
                currency=order.currency,
                status="SUCCEEDED",
                stripe_payment_intent_id=payment_intent.id,
                payment_method_type=payment_method.type,
                card_brand=payment_method.card.brand if payment_method.card else None,
                card_last4=payment_method.card.last4 if payment_method.card else None,
                billing_period_start=subscription.start_date,
                billing_period_end=subscription.start_date + timedelta(days=90),
                payment_date=datetime.utcnow()
            )
            
            db.add(payment)
            db.commit()
            
            self.log_audit(
                db, "CREATE_SUBSCRIPTION", "PAYMENT_PROCESSED", "SUCCESS",
                order_id=order.id, subscription_id=subscription.id,
                customer_id=subscriber.customer_id,
                details={
                    "payment_intent_id": payment_intent.id,
                    "amount": float(order.initial_payment_amount)
                }, ip_address=ip_address
            )
            
            return True
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe payment error: {str(e)}")
            self.log_audit(
                db, "CREATE_SUBSCRIPTION", "PAYMENT_PROCESSING", "FAILED",
                order_id=order.id, subscription_id=subscription.id,
                customer_id=subscriber.customer_id,
                error_message=str(e), ip_address=ip_address
            )
            return False
        except Exception as e:
            logger.error(f"Error processing payment: {str(e)}")
            self.log_audit(
                db, "CREATE_SUBSCRIPTION", "PAYMENT_PROCESSING", "FAILED",
                order_id=order.id, subscription_id=subscription.id,
                customer_id=subscriber.customer_id,
                error_message=str(e), ip_address=ip_address
            )
            return False
    def get_subscriptions_by_subscriber(self, db: Session, subscriber_id: int) -> List[Subscription]:
        """Get all subscriptions for a subscriber"""
        return db.query(Subscription).filter(Subscription.subscriber_id == subscriber_id).all()
    
    def get_subscriber_by_customer_id(self, db: Session, customer_id: int) -> Optional[Subscriber]:
        """Get subscriber by customer ID"""
        return db.query(Subscriber).filter(Subscriber.customer_id == customer_id).first()
    
    def resume_failed_order(
        self,
        db: Session,
        order_id: int,
        payment_method_id: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> bool:
        """Resume a failed order from where it stopped"""
        try:
            order = db.query(Order).filter(Order.id == order_id).first()
            if not order:
                return False
            
            if order.order_status != "FAILED":
                return False
            
            # Resume from last successful step
            last_step = order.last_successful_step or "INITIATED"
            
            self.log_audit(
                db, "RESUME_ORDER", f"RESUMING_FROM_{last_step}", "PENDING",
                order_id=order.id, customer_id=order.customer_id,
                ip_address=ip_address
            )
            
            # Continue from where it failed
            # Resume logic based on last successful step
            
            # If failed before SUBSCRIBER_CREATED
            if last_step == "INITIATED":
                # Get customer and create subscriber
                customer = db.query(Customer).filter(Customer.id == order.customer_id).first()
                subscriber = self._create_or_get_subscriber(db, customer, order, ip_address)
                if not subscriber:
                    raise Exception("Failed to resume at subscriber creation")
                
                order.subscriber_id = subscriber.id
                order.process_state = "SUBSCRIBER_CREATED"
                order.last_successful_step = "SUBSCRIBER_CREATED"
                db.commit()
                last_step = "SUBSCRIBER_CREATED"

            # If failed before SUBSCRIPTION_CREATED
            if last_step == "SUBSCRIBER_CREATED":
                subscriber = db.query(Subscriber).filter(Subscriber.id == order.subscriber_id).first()
                plan = db.query(PlanMaster).filter(PlanMaster.id == order.plan_id).first()
                
                # Reconstruct request-like object for pricing/dates
                # In a real scenario, we might have stored these in order details or metadata
                # For now using order stored values
                
                class MockRequest:
                    start_date = order.start_date
                    end_date = order.end_date
                    children = json.loads(order.children_details) # List of dicts
                    currency = order.currency
                    auto_renew = order.auto_renew
                    customer_id = order.customer_id
                
                mock_req = MockRequest()
                
                subscription = self._create_subscription(
                    db, subscriber, plan, mock_req, order,
                    order.plan_price_per_child, order.initial_payment_amount, order.monthly_amount, ip_address
                )
                if not subscription:
                    raise Exception("Failed to resume at subscription creation")
                
                order.subscription_id = subscription.id
                order.process_state = "SUBSCRIPTION_CREATED"
                order.last_successful_step = "SUBSCRIPTION_CREATED"
                db.commit()
                last_step = "SUBSCRIPTION_CREATED"

            # If failed before SIMS_ASSIGNED
            if last_step == "SUBSCRIPTION_CREATED":
                subscription = db.query(Subscription).filter(Subscription.id == order.subscription_id).first()
                subscriber = db.query(Subscriber).filter(Subscriber.id == order.subscriber_id).first()
                children_data = json.loads(order.children_details)

                # Convert to ChildDetails objects
                children_objs = [ChildDetails(**c) for c in children_data]

                # Get sim_type from order
                sim_type = order.sim_type or "pSIM"

                # Only assign SIMs if pSIM type
                if sim_type == "pSIM":
                    sim_cards = self._assign_sim_cards(db, subscription, subscriber, children_objs, sim_type, order, ip_address)
                    if not sim_cards:
                        logger.warning(f"No SIM cards available for resume order {order.order_number} - continuing without SIM allocation")
                else:
                    logger.info(f"Skipping SIM assignment for resume - sim_type is '{sim_type}', not 'pSIM'")

                order.process_state = "SIMS_ASSIGNED"
                order.last_successful_step = "SIMS_ASSIGNED"
                db.commit()
                last_step = "SIMS_ASSIGNED"

            # If failed before PAYMENT_PROCESSED
            if last_step == "SIMS_ASSIGNED":
                if not payment_method_id:
                     raise Exception("Payment method ID required to resume payment")
                
                subscription = db.query(Subscription).filter(Subscription.id == order.subscription_id).first()
                subscriber = db.query(Subscriber).filter(Subscriber.id == order.subscriber_id).first()
                
                payment_success = self._process_payment(
                    db, order, subscription, subscriber, payment_method_id, ip_address
                )
                if not payment_success:
                    raise Exception("Failed to resume at payment processing")
                
                order.process_state = "PAYMENT_PROCESSED"
                order.last_successful_step = "PAYMENT_PROCESSED"
                order.payment_status = "PAID"
                order.payment_date = datetime.utcnow()
                db.commit()
                last_step = "PAYMENT_PROCESSED"
            
            # Complete Order
            if last_step == "PAYMENT_PROCESSED":
                order.order_status = "COMPLETED"
                order.process_state = "COMPLETED"
                order.completed_at = datetime.utcnow()
                order.failure_reason = None # Clear failure reason
                db.commit()
                
                self.log_audit(
                    db, "RESUME_ORDER", "ORDER_COMPLETED", "SUCCESS",
                    order_id=order.id, customer_id=order.customer_id, ip_address=ip_address
                )
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error resuming order: {str(e)}")
            # Log failure again
            self.log_audit(
                db, "RESUME_ORDER", f"RESUME_FAILED_AT_{last_step if 'last_step' in locals() else 'UNKNOWN'}", "FAILED",
                order_id=order.id, customer_id=order.customer_id,
                error_message=str(e), ip_address=ip_address
            )
            return False


new_subscription_service = NewSubscriptionService()
