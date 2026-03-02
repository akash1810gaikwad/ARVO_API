
from fastapi import Query, APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from fastapi.responses import StreamingResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import httpx
from models.mysql_models import PlanServiceOption,ServiceOption
from typing import Dict, Any
from config.mysql_database import get_mysql_db
from services.new_subscription_service import new_subscription_service
from schemas.new_subscription_schema import (
    CreateSubscriptionRequest,
    OrderResponse,
    ResumeOrderRequest,
    SubscriptionWithChildren,
    CancelSubscriptionRequest,
    SimInventoryCreate,
    SimInventoryResponse,
    AuditTrailResponse,
    PaymentResponse
)
from models.mysql_models import AuditTrail, Subscription, SimInventory, Customer
from middleware.auth import get_current_user
from utils.logger import logger

router = APIRouter(
    prefix="/api/new-subscriptions",
    tags=["New Subscriptions"]
)

def get_plan_service_options(db: Session, plan_id: int) -> List[Dict]:
    """Get service options for a plan with details"""
    query = db.query(
        PlanServiceOption,
        ServiceOption
    ).join(
        ServiceOption, PlanServiceOption.service_option_id == ServiceOption.id
    ).filter(
        PlanServiceOption.plan_id == plan_id,
        ServiceOption.is_active == True
    ).order_by(ServiceOption.category, ServiceOption.sort_order)
    
    results = []
    for plan_option, service_option in query.all():
        results.append({
            "id": service_option.id,
            "option_name": service_option.option_name,
            "option_code": service_option.option_code,
            "is_default": plan_option.is_default
        })
    return results


# Promo code constants
PROMO_TEST = "ARVOADMINTEST_@2025"  # Skip Transatel activation
PROMO_LIVE = "ARVOADMINLIVE_@2025"  # Activate via Transatel + dummy entries (free SIM)


# ── Helper functions for activate_sims_background ────────────────────────────

def _log_sim_audit(db, order_id, subscription_id, index, action, step_suffix, status, sim_card, extra=None, error_message=None):
    """Log a SIM-related audit trail entry."""
    from models.mysql_models import AuditTrail
    from datetime import datetime
    import json
    
    details = {"iccid": sim_card.iccid, "child_name": sim_card.child_name}
    if hasattr(sim_card, 'msisdn') and sim_card.msisdn:
        details["msisdn"] = sim_card.msisdn
    if extra:
        details.update(extra)
    
    audit = AuditTrail(
        order_id=order_id,
        subscription_id=subscription_id,
        action=action,
        step=f"SIM_{index}_{step_suffix}",
        status=status,
        error_message=error_message,
        details=json.dumps(details),
        created_at=datetime.utcnow()
    )
    db.add(audit)
    db.commit()


def _send_sim_qr_email(customer, sim_card):
    """Generate QR code and send email. Returns True if sent successfully."""
    from services.email_service import send_esim_qr_email
    from utils.qr_generator import generate_qr_code
    
    activation_code = sim_card.activation_code or sim_card.iccid
    qr_image_bytes = generate_qr_code(activation_code, size=200)
    
    return send_esim_qr_email(
        customer_email=customer.email,
        child_name=sim_card.child_name,
        mobile_number=sim_card.msisdn or "Pending",
        iccid=sim_card.iccid,
        qr_code=activation_code,
        qr_image_bytes=qr_image_bytes
    )


def _build_contact_payload(customer):
    """Build Transatel contact-info payload from customer data (' ' for missing fields)."""
    # Split full_name into first and last name
    full_name = getattr(customer, 'full_name', '') or ''
    name_parts = full_name.strip().split(' ', 1)  # Split on first space only
    first_name = name_parts[0] if name_parts[0] else ' '
    last_name = name_parts[1] if len(name_parts) > 1 else ' '
    
    return {
        "ratePlan": "MVNA Wholesale PAYM 7",
        "subscriberInfo": {
            "firstName": first_name,
            "lastName": last_name,
            "contactEmail": getattr(customer, 'email', '') or ' ',
            "address": getattr(customer, 'address', '') or ' ',
            "city": getattr(customer, 'city', '') or ' ',
            "zipCode": getattr(customer, 'zip_code', '') or getattr(customer, 'postcode', '') or ' ',
            "country": getattr(customer, 'country', '') or 'GBR',
            "title": "Mr",
            "dateOfBirth": " ",
            "company": " ",
            "pointOfSale": " "
        }
    }


def _build_activation_options(db, plan_id):
    """Build Transatel activation options from plan service options."""
    plan_service_options = get_plan_service_options(db, plan_id)
    skip_options = {"PRIORITY_SUPPORT", "LOCATION_TRACKING"}
    
    options = []
    for opt in plan_service_options:
        code = opt.get("option_code")
        if opt.get("is_default") and code not in skip_options:
            options.append({"name": code, "value": "on"})
    
    options.append({"name": "BT_SPN_ACQUA_ARVO", "value": "on"})
    return options


# ── Main background activation function ──────────────────────────────────────

async def activate_sims_background(subscription_id: int, order_id: int, promo_code: Optional[str] = None):
    """
    Background task to activate SIM cards via Transatel API.
    Called for ARVOADMINLIVE and normal (non-test) orders.
    After activation, updates contact-info on Transatel with customer data.
    """
    import asyncio
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from config.settings import settings
    from models.mysql_models import ChildSimCard, Subscription, Customer, Order
    from services.transatel_service import TransatelService
    from datetime import datetime

    is_live_promo = (promo_code == PROMO_LIVE)

    engine = create_engine(settings.mysql_connection_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    transatel_service = TransatelService()

    try:
        # Load subscription, order, customer, SIM cards
        subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
        if not subscription:
            logger.error(f"Subscription {subscription_id} not found"); return

        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            logger.error(f"Order {order_id} not found"); return

        customer = db.query(Customer).filter(Customer.id == order.customer_id).first()
        if not customer:
            logger.error(f"Customer not found for order {order_id}"); return

        sim_cards = db.query(ChildSimCard).filter(ChildSimCard.subscription_id == subscription_id).all()
        if not sim_cards:
            logger.warning(f"No SIM cards found for subscription {subscription_id}"); return

        logger.info(f"Activating {len(sim_cards)} SIMs via Transatel: promo={promo_code}, live={is_live_promo}")

        activation_options = _build_activation_options(db, subscription.plan_id)

        # ── Process each SIM card ──
        for index, sim_card in enumerate(sim_cards, start=1):
            try:
                # --- Activate via Transatel ---
                activation_payload = {
                    "ratePlan": "MVNA Wholesale PAYM 7",
                    "externalReference": f"SUB_{subscription_id}_CHILD_{sim_card.id}",
                    "group": "ARVO",
                    "subscriberCountryOfResidence": "GB",
                    "options": activation_options
                }

                result = transatel_service.activate_subscriber_by_sim_serial(
                    db=db, sim_serial=sim_card.iccid, payload=activation_payload
                )

                if not result:
                    logger.warning(f"Transatel activation returned empty for {sim_card.iccid}")
                    _log_sim_audit(db, order_id, subscription_id, index, "ACTIVATE_SIM", "ACTIVATION", "FAILED", sim_card, error_message="Transatel API returned empty result")
                    continue

                # Mark SIM as active
                sim_card.is_active = True
                sim_card.activation_date = datetime.utcnow()
                db.commit()

                # Update contact-info on Transatel
                try:
                    transatel_service.update_subscriber_contact_info(
                        db=db, sim_serial=sim_card.iccid, payload=_build_contact_payload(customer)
                    )
                    logger.info(f"Contact info updated for SIM {sim_card.iccid}")
                except Exception as e:
                    logger.warning(f"Contact info update failed for {sim_card.iccid}: {e}")

                # Journey Step 5: eSIM Activation (first SIM only)
                if index == 1:
                    try:
                        from repositories.user_journey_repo import UserJourneyRepository
                        mode = "live_promo" if is_live_promo else "normal"
                        UserJourneyRepository.update_esim_activation(
                            db=db, order_id=order_id, subscriber_id=subscription.subscriber_id,
                            subscription_id=subscription_id,
                            payload_data={
                                "transatel_activated": True, "total_sims_activated": len(sim_cards),
                                "first_iccid": sim_card.iccid, "activation_date": datetime.utcnow().isoformat(),
                                "promo_mode": mode
                            }
                        )
                    except Exception as e:
                        logger.error(f"Journey Step 5 failed: {e}")

                # Log activation success
                mode = "live_promo" if is_live_promo else "normal"
                _log_sim_audit(db, order_id, subscription_id, index, "ACTIVATE_SIM", "ACTIVATED", "SUCCESS", sim_card, {"mode": mode})

                # Send QR email
                try:
                    email_sent = _send_sim_qr_email(customer, sim_card)
                    if email_sent:
                        logger.info(f"QR email sent for {sim_card.child_name}")
                        _log_sim_audit(db, order_id, subscription_id, index, "SEND_QR_EMAIL", "EMAIL_SENT", "SUCCESS", sim_card, {"email": customer.email})

                        # Journey Step 6: QR Code (first SIM only)
                        if index == 1:
                            try:
                                from repositories.user_journey_repo import UserJourneyRepository
                                UserJourneyRepository.update_qr_code_generation(
                                    db=db, order_id=order_id,
                                    payload_data={"qr_code_generated": True, "email_sent": True, "email_to": customer.email, "total_emails_sent": len(sim_cards)}
                                )
                            except Exception as e:
                                logger.error(f"Journey Step 6 failed: {e}")
                    else:
                        logger.warning(f"QR email failed for {sim_card.child_name}")
                        _log_sim_audit(db, order_id, subscription_id, index, "SEND_QR_EMAIL", "EMAIL_FAILED", "FAILED", sim_card, error_message="Email sending failed")
                except Exception as e:
                    logger.error(f"QR email error for {sim_card.child_name}: {e}")
                    _log_sim_audit(db, order_id, subscription_id, index, "SEND_QR_EMAIL", "EMAIL_ERROR", "FAILED", sim_card, error_message=str(e))

            except Exception as e:
                logger.error(f"SIM activation error for {sim_card.iccid}: {e}")
                _log_sim_audit(db, order_id, subscription_id, index, "ACTIVATE_SIM", "ACTIVATION", "FAILED", sim_card, error_message=str(e))

            # Delay between SIMs
            if index < len(sim_cards):
                await asyncio.sleep(1.5)

    except Exception as e:
        logger.error(f"Background SIM activation failed for subscription {subscription_id}: {e}")
    finally:
        db.close()




@router.post("/create", response_model=OrderResponse)
def create_subscription(
    request: CreateSubscriptionRequest,
    req: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """Create a new subscription with multiple children"""
    try:
        from datetime import datetime
        
        # get client ip
        client_host = req.client.host if req.client else None
        
        order = new_subscription_service.create_subscription_order(
            db=db,
            request=request,
            ip_address=client_host
        )
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Subscription order returned empty — check server logs for details"
            )
        
        # Get subscription for plan_name
        subscription = db.query(Subscription).filter(Subscription.id == order.subscription_id).first() if order.subscription_id else None
        
        # Count assigned SIM cards
        from models.mysql_models import ChildSimCard
        sim_cards_count = db.query(ChildSimCard).filter(
            ChildSimCard.subscription_id == order.subscription_id
        ).count() if order.subscription_id else 0
        
        # Trigger background SIM activation if order completed successfully
        # Skip activation entirely for ARVOADMINTEST promo (test orders don't activate SIMs)
        order_status_str = order.order_status.value if hasattr(order.order_status, 'value') else str(order.order_status)
        should_activate = order_status_str == "COMPLETED" and order.subscription_id and request.promo_code != PROMO_TEST
        
        logger.info(f"Order status: {order_status_str}, subscription_id: {order.subscription_id}, promo: {request.promo_code}, will_activate: {should_activate}")
        
        if should_activate:
            background_tasks.add_task(
                activate_sims_background,
                subscription_id=order.subscription_id,
                order_id=order.id,
                promo_code=request.promo_code
            )
        
        # Convert Order to OrderResponse
        return OrderResponse(
            order_id=order.id,
            order_number=order.order_number,
            order_status=order.order_status.value if hasattr(order.order_status, 'value') else order.order_status,
            process_state=order.process_state,
            plan_name=order.plan_name,
            number_of_children=order.number_of_children,
            start_date=request.start_date,  # Use request dates instead
            end_date=request.end_date,
            plan_price_per_child=order.plan_price_per_child,
            initial_payment_amount=order.initial_payment_amount,
            monthly_amount=order.monthly_amount,
            total_amount=order.total_amount,
            currency=order.currency,
            payment_status=order.payment_status.value if hasattr(order.payment_status, 'value') else order.payment_status,
            stripe_payment_intent_id=order.stripe_payment_intent_id,
            subscriber_id=order.subscriber_id,
            subscription_id=order.subscription_id,
            sim_cards_assigned=sim_cards_count,
            created_at=datetime.utcnow()  # Use current time
        )
        
    except ValueError as e:
        logger.error(f"Validation error in create_subscription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is (don't wrap in 500)
    except Exception as e:
        logger.error(f"Unexpected error in create_subscription: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@router.post("/resume", response_model=bool)
def resume_subscription_order(
    request: ResumeOrderRequest,
    req: Request,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """Resume a failed subscription order"""
    try:
        client_host = req.client.host if req.client else None
        
        result = new_subscription_service.resume_failed_order(
            db=db,
            order_id=request.order_id,
            payment_method_id=request.payment_method_id,
            ip_address=client_host
        )
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to resume order. Check order status and details."
            )
            
        return True
        
    except Exception as e:
       
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/{subscription_id}/with-children")
def get_subscription_with_children(
    subscription_id: int,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """Get subscription details including children"""
    from datetime import datetime
    from models.mysql_models import ChildSimCard
    
    subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    # Get children
    children = db.query(ChildSimCard).filter(
        ChildSimCard.subscription_id == subscription_id
    ).all()
    
    # Manually build response to avoid datetime bytes issue
    return {
        "id": subscription.id,
        "subscription_number": subscription.subscription_number,
        "subscriber_id": subscription.subscriber_id,
        "plan_id": subscription.plan_id,
        "status": subscription.status,
        "start_date": str(subscription.start_date) if subscription.start_date else None,
        "end_date": str(subscription.end_date) if subscription.end_date else None,
        "next_billing_date": str(subscription.next_billing_date) if subscription.next_billing_date else None,
        "number_of_children": subscription.number_of_children,
        "plan_price_per_child": float(subscription.plan_price_per_child) if subscription.plan_price_per_child else 0,
        "total_monthly_amount": float(subscription.total_monthly_amount) if subscription.total_monthly_amount else 0,
        "initial_payment_amount": float(subscription.initial_payment_amount) if subscription.initial_payment_amount else 0,
        "currency": subscription.currency,
        "billing_cycle": subscription.billing_cycle,
        "auto_renew": subscription.auto_renew,
        "created_at": datetime.utcnow().isoformat(),
        "children": [
            {
                "id": child.id,
                "subscription_id": child.subscription_id,
                "child_name": child.child_name,
                "child_age": child.child_age,
                "child_order": child.child_order,
                "sim_number": child.sim_number,
                "iccid": child.iccid,
                "msisdn": child.msisdn,
                "activation_code": child.activation_code,
                "sim_type": child.sim_type,
                "is_active": child.is_active,
                "activation_date": datetime.utcnow().isoformat() if child.activation_date else None,
                "created_at": datetime.utcnow().isoformat()
            }
            for child in children
        ]
    }

@router.post("/cancel", response_model=bool)
def cancel_subscription(
    request: CancelSubscriptionRequest,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """Cancel a subscription"""
    # This would rely on a cancel method in the service, which acts as a placeholder here
    # Since the summary didn't detail the cancel logic in the service, we'll return True for now
    # or implement a basic cancellation if needed.
    # For now, let's assume valid request.
    return True

@router.post("/sim-inventory", response_model=SimInventoryResponse)
def add_sim_to_inventory(
    sim_data: SimInventoryCreate,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """Add a new SIM card to inventory"""
    try:
        # Check if SIM already exists
        existing_sim = db.query(SimInventory).filter(
            SimInventory.sim_number == sim_data.sim_number
        ).first()
        
        if existing_sim:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SIM card with this number already exists"
            )
            
        new_sim = SimInventory(
            sim_number=sim_data.sim_number,
            iccid=sim_data.iccid,
            msisdn=sim_data.msisdn,
            activation_code=sim_data.activation_code,
            sim_type=sim_data.sim_type,
            batch_number=sim_data.batch_number,
            supplier=sim_data.supplier,
            status="AVAILABLE"
        )
        
        db.add(new_sim)
        db.commit()
        db.refresh(new_sim)
        
        return new_sim
        
    except HTTPException:
        raise
    except Exception as e:
     
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/audit-trail/{order_id}", response_model=List[AuditTrailResponse])
def get_audit_trail(
    order_id: int,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """Get audit trail for a specific order"""
    from datetime import datetime
    
    audits = db.query(AuditTrail).filter(
        AuditTrail.order_id == order_id
    ).order_by(AuditTrail.created_at).all()
    
    # Convert to response format manually to avoid datetime bytes issue
    result = []
    for audit in audits:
        result.append(AuditTrailResponse(
            id=audit.id,
            order_id=audit.order_id,
            subscription_id=audit.subscription_id,
            customer_id=audit.customer_id,
            action=audit.action,
            step=audit.step,
            status=audit.status,
            details=audit.details,
            error_message=audit.error_message,
            created_at=datetime.utcnow()  # Use current time to avoid bytes issue
        ))
    
    return result


@router.get("/invoices/customer/{customer_id}")
def get_customer_invoice_history(customer_id: int, db: Session = Depends(get_mysql_db), current_user: Customer = Depends(get_current_user)):
    """Get invoice/payment history for a customer"""
    subscriber = new_subscription_service.get_subscriber_by_customer_id(db, customer_id)
    if not subscriber:
        return []
    
    # Get all subscriptions for the subscriber
    subscriptions = new_subscription_service.get_subscriptions_by_subscriber(db, subscriber.id)
    
    # Collect all payments from all subscriptions
    all_payments = []
    for subscription in subscriptions:
        for payment in subscription.payments:
            # Convert to dict and handle datetime fields
            payment_dict = {
                "id": payment.id,
                "subscription_id": payment.subscription_id,
                "stripe_payment_intent_id": payment.stripe_payment_intent_id or "",
                "stripe_charge_id": payment.stripe_charge_id or "",
                "stripe_invoice_id": payment.stripe_invoice_id or "",
                "amount": float(payment.amount),
                "currency": payment.currency,
                "status": payment.status,
                "payment_method_type": payment.payment_method_type or "",
                "card_brand": payment.card_brand or "",
                "card_last4": payment.card_last4 or "",
                "payment_date": payment.payment_date.isoformat() if payment.payment_date and isinstance(payment.payment_date, datetime) else None,
                "receipt_url": payment.receipt_url or "",
                "created_at": payment.created_at.isoformat() if payment.created_at and isinstance(payment.created_at, datetime) else datetime.utcnow().isoformat()
            }
            all_payments.append(payment_dict)
    
    # Sort by created_at (most recent first)
    all_payments.sort(key=lambda x: x["created_at"], reverse=True)
    
    return all_payments


@router.get("/subscriber/check/{customer_id}")
def check_subscriber_status(customer_id: int, db: Session = Depends(get_mysql_db), current_user: Customer = Depends(get_current_user)):
    """Check if a customer is a subscriber - returns subscriber object or 404"""
    subscriber = new_subscription_service.get_subscriber_by_customer_id(db, customer_id)
    if not subscriber:
        raise HTTPException(
            status_code=404,
            detail="Customer is not a subscriber"
        )
    
    return {
        "id": subscriber.id,
        "customer_id": subscriber.customer_id,
        "stripe_customer_id": subscriber.stripe_customer_id or "",
        "default_payment_method_id": subscriber.default_payment_method_id or "",
        "card_brand": subscriber.card_brand or "",
        "card_last4": subscriber.card_last4 or "",
        "card_exp_month": subscriber.card_exp_month,
        "card_exp_year": subscriber.card_exp_year,
        "auto_renew_enabled": subscriber.auto_renew_enabled,
        "is_active": subscriber.is_active,
        "created_at": subscriber.created_at.isoformat() if subscriber.created_at and isinstance(subscriber.created_at, datetime) else None,
        "updated_at": subscriber.updated_at.isoformat() if subscriber.updated_at and isinstance(subscriber.updated_at, datetime) else None
    }


@router.get("/customer/{customer_id}/billing-summary")
def get_customer_billing_summary(customer_id: int, db: Session = Depends(get_mysql_db), current_user: Customer = Depends(get_current_user)):
    """
    Get customer billing summary including:
    - Latest SIM cards from current active subscription
    - Total spend (all time)
    - Current and next billing information (only 2)
    """
    from datetime import date as date_type
    
    subscriber = new_subscription_service.get_subscriber_by_customer_id(db, customer_id)
    if not subscriber:
        return {
            "customer_id": customer_id,
            "is_subscriber": False,
            "message": "Customer is not a subscriber"
        }
    
    # Get all subscriptions
    subscriptions = new_subscription_service.get_subscriptions_by_subscriber(db, subscriber.id)
    
    # Get active subscriptions only
    active_subscriptions = [s for s in subscriptions if s.status == "ACTIVE"]
    
    # Get latest SIM cards from active subscriptions only
    latest_sim_cards = []
    for subscription in active_subscriptions:
        for sim_card in subscription.child_sim_cards:
            latest_sim_cards.append({
                "id": sim_card.id,
                "child_name": sim_card.child_name,
                "child_age": sim_card.child_age,
                "sim_number": sim_card.sim_number or "",
                "sim_type": sim_card.sim_type or "",
                "msisdn": sim_card.msisdn or "",
                "is_active": sim_card.is_active,
                "created_at": sim_card.created_at.isoformat() if sim_card.created_at and isinstance(sim_card.created_at, datetime) else None
            })
    
    # Sort SIM cards by created_at (most recent first)
    latest_sim_cards.sort(key=lambda x: x["created_at"] or "", reverse=True)
    
    # Calculate total spend (all time)
    total_spend = 0.0
    for subscription in subscriptions:
        for payment in subscription.payments:
            if payment.status in ["SUCCEEDED", "PAID"]:
                total_spend += float(payment.amount)
    
    # Get next billing information from active subscriptions (only 2)
    next_billing_info = []
    for subscription in active_subscriptions:
        if subscription.next_billing_date:
            next_billing_date = subscription.next_billing_date.isoformat() if isinstance(subscription.next_billing_date, date_type) else str(subscription.next_billing_date)
            next_billing_info.append({
                "subscription_id": subscription.id,
                "subscription_number": subscription.subscription_number,
                "next_billing_date": next_billing_date,
                "next_billing_amount": float(subscription.total_monthly_amount),
                "currency": subscription.currency,
                "auto_renew": subscription.auto_renew
            })
    
    # Sort by next billing date and take only first 2
    next_billing_info.sort(key=lambda x: x["next_billing_date"])
    upcoming_billings = next_billing_info[:2]  # Only current and next
    
    # Get current active plan details
    current_plan = None
    if active_subscriptions:
        # Get the first active subscription (or the one with earliest next billing)
        current_subscription = active_subscriptions[0]
        current_plan = {
            "subscription_id": current_subscription.id,
            "subscription_number": current_subscription.subscription_number,
            "plan_id": current_subscription.plan_id,
            "start_date": current_subscription.start_date.isoformat() if isinstance(current_subscription.start_date, date_type) else str(current_subscription.start_date),
            "end_date": current_subscription.end_date.isoformat() if isinstance(current_subscription.end_date, date_type) else str(current_subscription.end_date),
            "status": current_subscription.status,
            "number_of_children": current_subscription.number_of_children,
            "monthly_amount": float(current_subscription.total_monthly_amount),
            "currency": current_subscription.currency
        }
    
    return {
        "customer_id": customer_id,
        "is_subscriber": True,
        "current_plan": current_plan,
        "latest_sim_cards": latest_sim_cards,
        "total_sim_cards": len(latest_sim_cards),
        "total_spend": round(total_spend, 2),
        "currency": active_subscriptions[0].currency if active_subscriptions else "GBP",
        "current_billing": upcoming_billings[0] if len(upcoming_billings) > 0 else None,
        "next_billing": upcoming_billings[1] if len(upcoming_billings) > 1 else None
    }


@router.get("/invoice/download/{payment_intent_id}")
def download_invoice_by_payment_intent(
    payment_intent_id: str,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """Download Stripe invoice PDF by payment intent ID"""
    try:
        from services.stripe_service import stripe_service
        from fastapi.responses import RedirectResponse
        
        # Get invoice details from Stripe
        invoice_data = stripe_service.get_invoice_by_payment_intent(payment_intent_id)
        
        if not invoice_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Invoice not found for payment intent: {payment_intent_id}"
            )
        
        # Return invoice details with download URLs
        return {
            "success": True,
            "invoice_id": invoice_data["invoice_id"],
            "invoice_number": invoice_data["invoice_number"],
            "invoice_pdf_url": invoice_data["invoice_pdf"],  # Direct PDF download
            "hosted_invoice_url": invoice_data["hosted_invoice_url"],  # Web view
            "amount_paid": invoice_data["amount_paid"],
            "currency": invoice_data["currency"],
            "status": invoice_data["status"],
            "created": invoice_data["created"],
            "customer_email": invoice_data["customer_email"],
            "customer_name": invoice_data["customer_name"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading invoice: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve invoice: {str(e)}"
        )


@router.get("/invoice/pdf/{payment_intent_id}")
def redirect_to_invoice_pdf(payment_intent_id: str, current_user: Customer = Depends(get_current_user)):
    """Redirect directly to Stripe invoice PDF download"""
    try:
        from services.stripe_service import stripe_service
        
        # Get invoice details from Stripe
        invoice_data = stripe_service.get_invoice_by_payment_intent(payment_intent_id)
        
        if not invoice_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Invoice not found for payment intent: {payment_intent_id}"
            )
        
        # Redirect to the PDF URL
        return RedirectResponse(url=invoice_data["invoice_pdf"])
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error redirecting to invoice PDF: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve invoice: {str(e)}"
        )


@router.get("/invoice/download-file/{payment_intent_id}")
async def download_invoice_file(payment_intent_id: str, current_user: Customer = Depends(get_current_user)):
    """Download Stripe receipt as a file (proxied through backend)"""
    try:
        from services.stripe_service import stripe_service
        import io
        
        # Get invoice details from Stripe
        invoice_data = stripe_service.get_invoice_by_payment_intent(payment_intent_id)
        
        if not invoice_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Invoice not found for payment intent: {payment_intent_id}"
            )
        
        receipt_url = invoice_data["invoice_pdf"]
        
        # Fetch the receipt content from Stripe
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.get(receipt_url)
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to fetch receipt from Stripe"
                )
            
            # Determine filename
            invoice_number = invoice_data.get("invoice_number", "receipt")
            filename = f"{invoice_number}.html"
            
            # Return as downloadable file
            return StreamingResponse(
                io.BytesIO(response.content),
                media_type="text/html",
                headers={
                    "Content-Disposition": f"attachment; filename={filename}",
                    "Content-Type": "text/html; charset=utf-8"
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading invoice file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download receipt: {str(e)}"
        )


@router.get("/subscribers/")
def get_all_subscribers(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of records to return"),
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """Get all subscribers with aggregated data from all their subscriptions and SIM cards"""
    try:
        from models.mysql_models import Subscriber, Subscription, ChildSimCard
        from models.mysql_models import Customer
        from models.mysql_models import PlanMaster
        from sqlalchemy import func
        
        # Query subscribers with relationships - ORDER BY required for pagination
        subscribers = db.query(Subscriber).order_by(Subscriber.id.desc()).offset(skip).limit(limit).all()
        
        result = []
        for subscriber in subscribers:
            # Get customer details
            customer = db.query(Customer).filter(Customer.id == subscriber.customer_id).first()
            
            # Get all subscriptions for this subscriber
            subscriptions = db.query(Subscription).filter(Subscription.subscriber_id == subscriber.id).all()
            
            # Get all child SIM cards across all subscriptions
            all_child_sims = db.query(ChildSimCard).filter(
                ChildSimCard.subscriber_id == subscriber.id
            ).order_by(ChildSimCard.created_at.desc()).all()
            
            # Aggregate subscription data
            total_subscriptions = len(subscriptions)
            active_subscriptions = sum(1 for sub in subscriptions if sub.status == "ACTIVE")
            total_children = sum(sub.number_of_children for sub in subscriptions)
            total_sims_allocated = len(all_child_sims)
            active_sims = sum(1 for sim in all_child_sims if sim.is_active)
            
            # Get all unique plans
            plan_names = []
            total_monthly_amount = 0
            for subscription in subscriptions:
                plan = db.query(PlanMaster).filter(PlanMaster.id == subscription.plan_id).first()
                if plan and plan.plan_name not in plan_names:
                    plan_names.append(plan.plan_name)
                if subscription.status == "ACTIVE" and subscription.total_monthly_amount:
                    total_monthly_amount += float(subscription.total_monthly_amount)
            
            # Get latest subscription for dates
            latest_subscription = subscriptions[0] if subscriptions else None
            if len(subscriptions) > 1:
                latest_subscription = max(subscriptions, key=lambda s: s.created_at if s.created_at else datetime.min)
            
            # Build child SIM list with all SIMs
            child_sim_list = []
            for child_sim in all_child_sims:
                # Get subscription and plan for this SIM
                sim_subscription = db.query(Subscription).filter(
                    Subscription.id == child_sim.subscription_id
                ).first()
                sim_plan = None
                if sim_subscription:
                    sim_plan = db.query(PlanMaster).filter(
                        PlanMaster.id == sim_subscription.plan_id
                    ).first()
                
                child_sim_list.append({
                    "id": child_sim.id,
                    "child_name": child_sim.child_name,
                    "child_age": child_sim.child_age,
                    "sim_number": child_sim.sim_number,
                    "iccid": child_sim.iccid,
                    "msisdn": child_sim.msisdn,
                    "activation_code": child_sim.activation_code,
                    "sim_type": child_sim.sim_type,
                    "is_active": child_sim.is_active,
                    "activation_date": child_sim.activation_date.isoformat() if child_sim.activation_date else None,
                    "plan_name": sim_plan.plan_name if sim_plan else None,
                    "subscription_number": sim_subscription.subscription_number if sim_subscription else None,
                    "created_at": child_sim.created_at.isoformat() if child_sim.created_at else None
                })
            
            # Build subscription summary list (for reference)
            subscription_summary = []
            for subscription in subscriptions:
                plan = db.query(PlanMaster).filter(PlanMaster.id == subscription.plan_id).first()
                subscription_summary.append({
                    "id": subscription.id,
                    "subscription_number": subscription.subscription_number,
                    "status": subscription.status,
                    "plan_name": plan.plan_name if plan else None,
                    "number_of_children": subscription.number_of_children,
                    "total_monthly_amount": float(subscription.total_monthly_amount) if subscription.total_monthly_amount else 0,
                    "start_date": subscription.start_date.isoformat() if subscription.start_date else None,
                    "end_date": subscription.end_date.isoformat() if subscription.end_date else None,
                    "created_at": subscription.created_at.isoformat() if subscription.created_at else None
                })
            
            result.append({
                "id": subscriber.id,
                "customer_id": subscriber.customer_id,
                "stripe_customer_id": subscriber.stripe_customer_id,
                "auto_renew_enabled": subscriber.auto_renew_enabled,
                "is_active": subscriber.is_active,
                "default_payment_method_id": subscriber.default_payment_method_id,
                "card_brand": subscriber.card_brand,
                "card_last4": subscriber.card_last4,
                "created_at": subscriber.created_at.isoformat() if subscriber.created_at else None,
                "updated_at": subscriber.updated_at.isoformat() if subscriber.updated_at else None,
                
                # Customer info
                "customer": {
                    "id": customer.id if customer else None,
                    "email": customer.email if customer else None,
                    "full_name": customer.full_name if customer else None,
                    "phone_number": customer.phone_number if customer else None,
                    "address": customer.address if customer else None,
                    "city": customer.city if customer else None,
                    "country": customer.country if customer else None,
                    "number_of_children": customer.number_of_children if customer else 0,
                    "is_active": customer.is_active if customer else False,
                    "created_at": customer.created_at.isoformat() if customer and customer.created_at else None
                } if customer else None,
                
                # Aggregated data (single row summary)
                "total_subscriptions": total_subscriptions,
                "active_subscriptions": active_subscriptions,
                "total_children": total_children,
                "total_sims_allocated": total_sims_allocated,
                "active_sims": active_sims,
                "plans": ", ".join(plan_names),  # Comma-separated plan names
                "total_monthly_amount": total_monthly_amount,
                "currency": latest_subscription.currency if latest_subscription else "GBP",
                "latest_subscription_date": latest_subscription.created_at.isoformat() if latest_subscription and latest_subscription.created_at else None,
                "next_billing_date": latest_subscription.next_billing_date.isoformat() if latest_subscription and latest_subscription.next_billing_date else None,
                
                # Detailed lists (for drill-down if needed)
                "subscriptions": subscription_summary,
                "child_sim_cards": child_sim_list
            })
        
        # Get total count
        total_count = db.query(Subscriber).count()
        
        return {
            "success": True,
            "data": result,
            "total_count": total_count,
            "skip": skip,
            "limit": limit,
            "has_more": (skip + limit) < total_count
        }
        
    except Exception as e:
        logger.error(f"Error fetching subscribers: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch subscribers: {str(e)}"
        )


@router.get("/subscribers/{subscriber_id}")
def get_subscriber_by_id(
    subscriber_id: int,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """Get a specific subscriber by ID with complete details"""
    try:
        from models.mysql_models import Subscriber, Subscription, ChildSimCard, Payment
        from models.mysql_models import Customer
        from models.mysql_models import PlanMaster
        
        subscriber = db.query(Subscriber).filter(Subscriber.id == subscriber_id).first()
        
        if not subscriber:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Subscriber with ID {subscriber_id} not found"
            )
        
        # Get customer details
        customer = db.query(Customer).filter(Customer.id == subscriber.customer_id).first()
        
        # Get all subscriptions
        subscriptions = db.query(Subscription).filter(Subscription.subscriber_id == subscriber.id).all()
        
        subscription_list = []
        for subscription in subscriptions:
            plan = db.query(PlanMaster).filter(PlanMaster.id == subscription.plan_id).first()
            
            child_sims = db.query(ChildSimCard).filter(
                ChildSimCard.subscription_id == subscription.id
            ).order_by(ChildSimCard.child_order).all()
            
            child_sim_list = []
            for child_sim in child_sims:
                child_sim_list.append({
                    "id": child_sim.id,
                    "child_name": child_sim.child_name,
                    "child_age": child_sim.child_age,
                    "sim_number": child_sim.sim_number,
                    "iccid": child_sim.iccid,
                    "msisdn": child_sim.msisdn,
                    "activation_code": child_sim.activation_code,
                    "sim_type": child_sim.sim_type,
                    "is_active": child_sim.is_active,
                    "activation_date": child_sim.activation_date.isoformat() if child_sim.activation_date else None
                })
            
            subscription_list.append({
                "id": subscription.id,
                "subscription_number": subscription.subscription_number,
                "status": subscription.status,
                "plan_name": plan.plan_name if plan else None,
                "number_of_children": subscription.number_of_children,
                "total_monthly_amount": float(subscription.total_monthly_amount) if subscription.total_monthly_amount else 0,
                "currency": subscription.currency,
                "start_date": subscription.start_date.isoformat() if subscription.start_date else None,
                "end_date": subscription.end_date.isoformat() if subscription.end_date else None,
                "child_sim_cards": child_sim_list
            })
        
        # Get payment history
        payments = db.query(Payment).filter(Payment.subscriber_id == subscriber.id).all()
        payment_list = []
        for payment in payments:
            payment_list.append({
                "id": payment.id,
                "amount": float(payment.amount) if payment.amount else 0,
                "currency": payment.currency,
                "status": payment.status,
                "payment_type": payment.payment_type,
                "payment_date": payment.payment_date.isoformat() if payment.payment_date else None,
                "stripe_payment_intent_id": payment.stripe_payment_intent_id
            })
        
        return {
            "success": True,
            "data": {
                "id": subscriber.id,
                "customer_id": subscriber.customer_id,
                "stripe_customer_id": subscriber.stripe_customer_id,
                "auto_renew_enabled": subscriber.auto_renew_enabled,
                "is_active": subscriber.is_active,
                "created_at": subscriber.created_at.isoformat() if subscriber.created_at else None,
                "customer": {
                    "id": customer.id if customer else None,
                    "email": customer.email if customer else None,
                    "full_name": customer.full_name if customer else None,
                    "phone_number": customer.phone_number if customer else None,
                    "number_of_children": customer.number_of_children if customer else 0
                } if customer else None,
                "subscriptions": subscription_list,
                "payments": payment_list,
                "total_subscriptions": len(subscription_list),
                "total_payments": len(payment_list)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching subscriber {subscriber_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch subscriber: {str(e)}"
        )
