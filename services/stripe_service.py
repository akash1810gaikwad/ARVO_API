import stripe
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime
from decimal import Decimal
from config.settings import settings
from models.mysql_models import Subscriber, Subscription, Payment
from models.mysql_models import Customer
from models.mysql_models import PlanMaster
from utils.logger import logger

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeService:
    """Service for Stripe payment operations"""
    
    def create_customer(self, db: Session, customer: Customer) -> Optional[Subscriber]:
        """Create a Stripe customer and subscriber record"""
        try:
            # Create Stripe customer
            stripe_customer = stripe.Customer.create(
                email=customer.email,
                name=customer.full_name,
                phone=customer.phone_number,
                metadata={
                    "customer_id": customer.id,
                    "app": "ARVO"
                }
            )
            
            # Create subscriber record
            subscriber = Subscriber(
                customer_id=customer.id,
                stripe_customer_id=stripe_customer.id,
                auto_renew_enabled=True
            )
            db.add(subscriber)
            db.commit()
            db.refresh(subscriber)
            
            logger.info(f"Created Stripe customer: {stripe_customer.id} for customer: {customer.id}")
            return subscriber
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating customer: {str(e)}")
            db.rollback()
            return None
        except Exception as e:
            logger.error(f"Error creating Stripe customer: {str(e)}")
            db.rollback()
            return None
    
    def create_payment_intent(
        self,
        db: Session,
        subscriber: Subscriber,
        plan: PlanMaster,
        billing_cycle: str,
        number_of_children: int
    ) -> Optional[Dict[str, Any]]:
        """Create a Stripe payment intent"""
        try:
            # Calculate amount
            if billing_cycle == "monthly":
                amount = float(plan.monthly_price) * number_of_children
            else:  # annual
                amount = float(plan.annual_price) * number_of_children
            
            # Convert to cents
            amount_cents = int(amount * 100)
            
            # Create payment intent
            payment_intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency="gbp",
                customer=subscriber.stripe_customer_id,
                metadata={
                    "subscriber_id": subscriber.id,
                    "plan_id": plan.id,
                    "billing_cycle": billing_cycle,
                    "number_of_children": number_of_children
                },
                automatic_payment_methods={"enabled": True}
            )
            
            logger.info(f"Created payment intent: {payment_intent.id}")
            
            return {
                "client_secret": payment_intent.client_secret,
                "amount": amount_cents,
                "currency": "gbp",
                "payment_intent_id": payment_intent.id
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating payment intent: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error creating payment intent: {str(e)}")
            return None
    
    def create_subscription(
        self,
        db: Session,
        subscriber: Subscriber,
        plan: PlanMaster,
        billing_cycle: str,
        number_of_children: int,
        payment_method_id: str
    ) -> Optional[tuple[Subscription, 'Order']]:
        """Create a Stripe subscription and order"""
        try:
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
            
            # Calculate price
            if billing_cycle == "monthly":
                unit_amount = int(float(plan.monthly_price) * 100)
                interval = "month"
            else:
                unit_amount = int(float(plan.annual_price) * 100)
                interval = "year"
            
            # Create or retrieve Stripe price
            price = stripe.Price.create(
                unit_amount=unit_amount,
                currency="gbp",
                recurring={"interval": interval},
                product_data={
                    "name": f"{plan.plan_name} - {billing_cycle.capitalize()}",
                    "metadata": {"plan_id": plan.id}
                }
            )
            
            # Create Stripe subscription
            stripe_subscription = stripe.Subscription.create(
                customer=subscriber.stripe_customer_id,
                items=[{"price": price.id, "quantity": number_of_children}],
                payment_behavior="default_incomplete",
                payment_settings={"save_default_payment_method": "on_subscription"},
                expand=["latest_invoice.payment_intent"],
                billing_cycle_anchor=None,  # Optional: Set to specific timestamp if needed
                backdate_start_date=None,  # Optional: Set to backdate subscription start
                trial_end=None,  # Optional: Set trial end timestamp if applicable
                metadata={
                    "subscriber_id": subscriber.id,
                    "plan_id": plan.id,
                    "number_of_children": number_of_children
                }
            )
            
            # Create subscription record
            total_amount = (unit_amount / 100) * number_of_children
            subscription = Subscription(
                subscriber_id=subscriber.id,
                plan_id=plan.id,
                stripe_subscription_id=stripe_subscription.id,
                stripe_price_id=price.id,
                status=SubscriptionStatus.ACTIVE if stripe_subscription.status == "active" else SubscriptionStatus.INCOMPLETE,
                billing_cycle=billing_cycle,
                number_of_children=number_of_children,
                sim_cards_issued=0,
                start_date=datetime.fromtimestamp(stripe_subscription.start_date),
                current_period_start=datetime.fromtimestamp(stripe_subscription.current_period_start),
                current_period_end=datetime.fromtimestamp(stripe_subscription.current_period_end),
                amount=Decimal(str(total_amount)),
                currency="gbp"
            )
            
            db.add(subscription)
            db.flush()  # Get subscription ID without committing
            
            # Create order record
            from services.order_service import order_service
            from schemas.order_schema import OrderCreate, OrderItemSchema
            
            order_data = OrderCreate(
                customer_id=subscriber.customer_id,
                order_type="SUBSCRIPTION",
                plan_id=plan.id,
                billing_cycle=billing_cycle,
                number_of_children=number_of_children,
                subtotal=Decimal(str(total_amount)),
                tax_amount=Decimal("0.00"),
                discount_amount=Decimal("0.00"),
                total_amount=Decimal(str(total_amount)),
                order_items=[
                    OrderItemSchema(
                        item_type="plan",
                        item_id=plan.id,
                        item_name=f"{plan.plan_name} - {billing_cycle.capitalize()}",
                        quantity=number_of_children,
                        unit_price=Decimal(str(unit_amount / 100)),
                        total_price=Decimal(str(total_amount))
                    )
                ]
            )
            
            order = order_service.create_order(db, order_data)
            
            if order:
                # Link order to subscription
                order.subscription_id = subscription.id
                order.subscriber_id = subscriber.id
                order.payment_status = "PAID"
                order.order_status = "COMPLETED"
                order.payment_method = payment_method.type
                order.stripe_payment_intent_id = stripe_subscription.latest_invoice.payment_intent if hasattr(stripe_subscription.latest_invoice, 'payment_intent') else None
                order.payment_date = datetime.utcnow()
                order.completed_at = datetime.utcnow()
            
            db.commit()
            db.refresh(subscription)
            if order:
                db.refresh(order)
            
            logger.info(f"Created subscription: {subscription.id} with order: {order.order_number if order else 'N/A'}")
            return subscription, order
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating subscription: {str(e)}")
            db.rollback()
            return None
        except Exception as e:
            logger.error(f"Error creating subscription: {str(e)}")
            db.rollback()
            return None
    
    def cancel_subscription(
        self,
        db: Session,
        subscription: Subscription,
        cancel_immediately: bool = False
    ) -> bool:
        """Cancel a Stripe subscription"""
        try:
            if cancel_immediately:
                # Cancel immediately
                stripe.Subscription.delete(subscription.stripe_subscription_id)
                subscription.status = SubscriptionStatus.CANCELLED
                subscription.cancelled_at = datetime.utcnow()
                subscription.ended_at = datetime.utcnow()
            else:
                # Cancel at period end
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=True
                )
                subscription.cancel_at = subscription.current_period_end
                subscription.cancelled_at = datetime.utcnow()
            
            db.commit()
            logger.info(f"Cancelled subscription: {subscription.id}")
            return True
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error cancelling subscription: {str(e)}")
            db.rollback()
            return False
        except Exception as e:
            logger.error(f"Error cancelling subscription: {str(e)}")
            db.rollback()
            return False
    
    def update_payment_method(
        self,
        db: Session,
        subscriber: Subscriber,
        payment_method_id: str
    ) -> bool:
        """Update customer's default payment method"""
        try:
            # Attach new payment method
            stripe.PaymentMethod.attach(
                payment_method_id,
                customer=subscriber.stripe_customer_id
            )
            
            # Set as default
            stripe.Customer.modify(
                subscriber.stripe_customer_id,
                invoice_settings={"default_payment_method": payment_method_id}
            )
            
            # Get payment method details
            payment_method = stripe.PaymentMethod.retrieve(payment_method_id)
            
            # Update subscriber
            subscriber.default_payment_method_id = payment_method_id
            if payment_method.card:
                subscriber.card_brand = payment_method.card.brand
                subscriber.card_last4 = payment_method.card.last4
                subscriber.card_exp_month = payment_method.card.exp_month
                subscriber.card_exp_year = payment_method.card.exp_year
            
            db.commit()
            logger.info(f"Updated payment method for subscriber: {subscriber.id}")
            return True
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error updating payment method: {str(e)}")
            db.rollback()
            return False
        except Exception as e:
            logger.error(f"Error updating payment method: {str(e)}")
            db.rollback()
            return False
    
    def handle_webhook_event(self, db: Session, event: Dict[str, Any]) -> bool:
        """Handle Stripe webhook events"""
        try:
            event_type = event["type"]
            data = event["data"]["object"]
            
            logger.info(f"Processing webhook event: {event_type}")
            
            if event_type == "payment_intent.succeeded":
                self._handle_payment_succeeded(db, data)
            elif event_type == "payment_intent.payment_failed":
                self._handle_payment_failed(db, data)
            elif event_type == "customer.subscription.updated":
                self._handle_subscription_updated(db, data)
            elif event_type == "customer.subscription.deleted":
                self._handle_subscription_deleted(db, data)
            elif event_type == "invoice.payment_succeeded":
                self._handle_invoice_payment_succeeded(db, data)
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling webhook event: {str(e)}")
            return False
    
    def _handle_payment_succeeded(self, db: Session, payment_intent: Dict):
        """Handle successful payment"""
        try:
            subscription_id = payment_intent.get("metadata", {}).get("subscription_id")
            if subscription_id:
                subscription = db.query(Subscription).filter(
                    Subscription.id == subscription_id
                ).first()
                
                if subscription:
                    payment = Payment(
                        subscription_id=subscription.id,
                        stripe_payment_intent_id=payment_intent["id"],
                        amount=Decimal(str(payment_intent["amount"] / 100)),
                        currency=payment_intent["currency"],
                        status=PaymentStatus.SUCCEEDED,
                        payment_date=datetime.utcnow()
                    )
                    db.add(payment)
                    db.commit()
                    logger.info(f"Recorded successful payment for subscription: {subscription_id}")
        except Exception as e:
            logger.error(f"Error handling payment succeeded: {str(e)}")
            db.rollback()
    
    def _handle_payment_failed(self, db: Session, payment_intent: Dict):
        """Handle failed payment"""
        try:
            subscription_id = payment_intent.get("metadata", {}).get("subscription_id")
            if subscription_id:
                subscription = db.query(Subscription).filter(
                    Subscription.id == subscription_id
                ).first()
                
                if subscription:
                    payment = Payment(
                        subscription_id=subscription.id,
                        stripe_payment_intent_id=payment_intent["id"],
                        amount=Decimal(str(payment_intent["amount"] / 100)),
                        currency=payment_intent["currency"],
                        status=PaymentStatus.FAILED,
                        failure_reason=payment_intent.get("last_payment_error", {}).get("message")
                    )
                    db.add(payment)
                    subscription.status = SubscriptionStatus.PAST_DUE
                    db.commit()
                    logger.warning(f"Payment failed for subscription: {subscription_id}")
        except Exception as e:
            logger.error(f"Error handling payment failed: {str(e)}")
            db.rollback()
    
    def _handle_subscription_updated(self, db: Session, stripe_subscription: Dict):
        """Handle subscription update"""
        try:
            subscription = db.query(Subscription).filter(
                Subscription.stripe_subscription_id == stripe_subscription["id"]
            ).first()
            
            if subscription:
                subscription.status = SubscriptionStatus(stripe_subscription["status"])
                subscription.current_period_start = datetime.fromtimestamp(stripe_subscription["current_period_start"])
                subscription.current_period_end = datetime.fromtimestamp(stripe_subscription["current_period_end"])
                db.commit()
                logger.info(f"Updated subscription: {subscription.id}")
        except Exception as e:
            logger.error(f"Error handling subscription updated: {str(e)}")
            db.rollback()
    
    def _handle_subscription_deleted(self, db: Session, stripe_subscription: Dict):
        """Handle subscription deletion"""
        try:
            subscription = db.query(Subscription).filter(
                Subscription.stripe_subscription_id == stripe_subscription["id"]
            ).first()
            
            if subscription:
                subscription.status = SubscriptionStatus.CANCELLED
                subscription.ended_at = datetime.utcnow()
                db.commit()
                logger.info(f"Subscription deleted: {subscription.id}")
        except Exception as e:
            logger.error(f"Error handling subscription deleted: {str(e)}")
            db.rollback()
    
    def _handle_invoice_payment_succeeded(self, db: Session, invoice: Dict):
        """Handle successful invoice payment"""
        try:
            subscription_id_stripe = invoice.get("subscription")
            if subscription_id_stripe:
                subscription = db.query(Subscription).filter(
                    Subscription.stripe_subscription_id == subscription_id_stripe
                ).first()
                
                if subscription:
                    payment = Payment(
                        subscription_id=subscription.id,
                        stripe_payment_intent_id=invoice.get("payment_intent", ""),
                        stripe_charge_id=invoice.get("charge", ""),
                        stripe_invoice_id=invoice["id"],
                        amount=Decimal(str(invoice["amount_paid"] / 100)),
                        currency=invoice["currency"],
                        status=PaymentStatus.SUCCEEDED,
                        payment_date=datetime.utcnow(),
                        receipt_url=invoice.get("hosted_invoice_url")
                    )
                    db.add(payment)
                    db.commit()
                    logger.info(f"Recorded invoice payment for subscription: {subscription.id}")
        except Exception as e:
            logger.error(f"Error handling invoice payment: {str(e)}")
            db.rollback()

    def get_invoice_by_payment_intent(self, payment_intent_id: str) -> Optional[Dict[str, Any]]:
        """Get invoice details and PDF URL by payment intent ID"""
        try:
            # Retrieve the payment intent with expanded charges
            payment_intent = stripe.PaymentIntent.retrieve(
                payment_intent_id,
                expand=['charges']
            )
            
            if not payment_intent:
                logger.error(f"Payment intent not found: {payment_intent_id}")
                return None
            
            logger.info(f"Payment intent retrieved: {payment_intent_id}, status: {payment_intent.status}")
            
            # Get the invoice ID from the payment intent
            invoice_id = payment_intent.get('invoice')
            
            if invoice_id:
                logger.info(f"Invoice found: {invoice_id}")
                # Retrieve the invoice if it exists
                invoice = stripe.Invoice.retrieve(invoice_id)
                
                if invoice:
                    # Return invoice details
                    return {
                        "invoice_id": invoice.id,
                        "invoice_number": invoice.number,
                        "invoice_pdf": invoice.invoice_pdf,  # Direct PDF download URL
                        "hosted_invoice_url": invoice.hosted_invoice_url,  # Web view URL
                        "amount_paid": invoice.amount_paid / 100,  # Convert from cents
                        "currency": invoice.currency,
                        "status": invoice.status,
                        "created": datetime.fromtimestamp(invoice.created),
                        "customer_email": invoice.customer_email,
                        "customer_name": invoice.customer_name
                    }
            
            # If no invoice, try to get the charge receipt
            logger.info(f"No invoice found, checking for charge receipt")
            
            # Get latest charge
            latest_charge = payment_intent.latest_charge
            if latest_charge:
                # If latest_charge is just an ID, retrieve the full charge object
                if isinstance(latest_charge, str):
                    charge = stripe.Charge.retrieve(latest_charge)
                else:
                    charge = latest_charge
                
                receipt_url = charge.receipt_url
                logger.info(f"Charge found: {charge.id}, receipt_url: {receipt_url}")
                
                if receipt_url:
                    return {
                        "invoice_id": payment_intent.id,
                        "invoice_number": f"RECEIPT-{payment_intent.id[-8:]}",
                        "invoice_pdf": receipt_url,  # Receipt URL from Stripe
                        "hosted_invoice_url": receipt_url,  # Same as PDF for receipts
                        "amount_paid": payment_intent.amount / 100,  # Convert from cents
                        "currency": payment_intent.currency,
                        "status": payment_intent.status,
                        "created": datetime.fromtimestamp(payment_intent.created),
                        "customer_email": charge.billing_details.email if charge.billing_details else None,
                        "customer_name": charge.billing_details.name if charge.billing_details else None
                    }
            
            logger.error(f"No invoice or receipt found for payment intent: {payment_intent_id}")
            return None
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error retrieving invoice: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving invoice: {str(e)}", exc_info=True)
            return None


# Create singleton instance
stripe_service = StripeService()
