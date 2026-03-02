from fastapi import APIRouter, Request, HTTPException, Header
from sqlalchemy.orm import Session
from fastapi import Depends
import stripe
from config.settings import settings
from config.mysql_database import get_mysql_db
from models.mysql_models import Subscription, Payment, Subscriber
from utils.logger import logger
from datetime import datetime
from decimal import Decimal

router = APIRouter(prefix="/api/v1/webhooks", tags=["Stripe Webhooks"])

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
    db: Session = Depends(get_mysql_db)
):
    """
    Handle Stripe webhook events
    
    Events handled:
    - invoice.payment_succeeded: Recurring payment successful
    - invoice.payment_failed: Recurring payment failed
    - customer.subscription.updated: Subscription status changed
    - customer.subscription.deleted: Subscription cancelled
    - payment_intent.succeeded: One-time payment successful
    - payment_intent.payment_failed: One-time payment failed
    """
    
    payload = await request.body()
    
    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
        
        logger.info(f"📨 Stripe webhook received: {event['type']}")
        
        # Handle different event types
        if event['type'] == 'invoice.payment_succeeded':
            handle_invoice_payment_succeeded(db, event['data']['object'])
            
        elif event['type'] == 'invoice.payment_failed':
            handle_invoice_payment_failed(db, event['data']['object'])
            
        elif event['type'] == 'customer.subscription.updated':
            handle_subscription_updated(db, event['data']['object'])
            
        elif event['type'] == 'customer.subscription.deleted':
            handle_subscription_deleted(db, event['data']['object'])
            
        elif event['type'] == 'payment_intent.succeeded':
            handle_payment_intent_succeeded(db, event['data']['object'])
            
        elif event['type'] == 'payment_intent.payment_failed':
            handle_payment_intent_failed(db, event['data']['object'])
        
        else:
            logger.info(f"Unhandled event type: {event['type']}")
        
        return {"success": True, "message": "Webhook processed"}
        
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"❌ Webhook signature verification failed: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid signature")
        
    except Exception as e:
        logger.error(f"❌ Webhook processing error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def handle_invoice_payment_succeeded(db: Session, invoice):
    """Handle successful recurring payment"""
    try:
        stripe_subscription_id = invoice.get('subscription')
        
        if not stripe_subscription_id:
            logger.warning("Invoice has no subscription ID")
            return
        
        # Find subscription in our database
        subscription = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == stripe_subscription_id
        ).first()
        
        if not subscription:
            logger.warning(f"Subscription not found for Stripe ID: {stripe_subscription_id}")
            return
        
        # Create payment record
        payment = Payment(
            subscription_id=subscription.id,
            subscriber_id=subscription.subscriber_id,
            payment_type="RECURRING",
            amount=Decimal(str(invoice['amount_paid'] / 100)),
            currency=invoice['currency'].upper(),
            status="SUCCEEDED",
            stripe_payment_intent_id=invoice.get('payment_intent'),
            stripe_invoice_id=invoice['id'],
            payment_method_type="card",
            billing_period_start=datetime.fromtimestamp(invoice['period_start']),
            billing_period_end=datetime.fromtimestamp(invoice['period_end']),
            payment_date=datetime.utcnow(),
            receipt_url=invoice.get('hosted_invoice_url')
        )
        
        db.add(payment)
        
        # Update subscription status
        subscription.status = "ACTIVE"
        subscription.next_billing_date = datetime.fromtimestamp(invoice['period_end'])
        
        db.commit()
        
        logger.info(f"✅ Recurring payment recorded for subscription {subscription.subscription_number}: {invoice['currency'].upper()} {invoice['amount_paid'] / 100}")
        
    except Exception as e:
        logger.error(f"Error handling invoice payment succeeded: {str(e)}")
        db.rollback()


def handle_invoice_payment_failed(db: Session, invoice):
    """Handle failed recurring payment"""
    try:
        stripe_subscription_id = invoice.get('subscription')
        
        if not stripe_subscription_id:
            return
        
        subscription = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == stripe_subscription_id
        ).first()
        
        if not subscription:
            return
        
        # Create failed payment record
        payment = Payment(
            subscription_id=subscription.id,
            subscriber_id=subscription.subscriber_id,
            payment_type="RECURRING",
            amount=Decimal(str(invoice['amount_due'] / 100)),
            currency=invoice['currency'].upper(),
            status="FAILED",
            stripe_payment_intent_id=invoice.get('payment_intent'),
            stripe_invoice_id=invoice['id'],
            payment_method_type="card",
            billing_period_start=datetime.fromtimestamp(invoice['period_start']),
            billing_period_end=datetime.fromtimestamp(invoice['period_end']),
            failure_reason=invoice.get('last_payment_error', {}).get('message', 'Payment failed')
        )
        
        db.add(payment)
        
        # Update subscription status to past_due
        subscription.status = "PAST_DUE"
        
        db.commit()
        
        logger.warning(f"⚠️ Payment failed for subscription {subscription.subscription_number}")
        
        # TODO: Send email notification to customer about failed payment
        
    except Exception as e:
        logger.error(f"Error handling invoice payment failed: {str(e)}")
        db.rollback()


def handle_subscription_updated(db: Session, stripe_subscription):
    """Handle subscription status changes"""
    try:
        subscription = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == stripe_subscription['id']
        ).first()
        
        if not subscription:
            return
        
        # Map Stripe status to our status
        status_mapping = {
            'active': 'ACTIVE',
            'past_due': 'PAST_DUE',
            'canceled': 'CANCELLED',
            'unpaid': 'PAST_DUE',
            'incomplete': 'PENDING',
            'incomplete_expired': 'CANCELLED',
            'trialing': 'ACTIVE'
        }
        
        old_status = subscription.status
        new_status = status_mapping.get(stripe_subscription['status'], subscription.status)
        
        subscription.status = new_status
        subscription.next_billing_date = datetime.fromtimestamp(stripe_subscription['current_period_end'])
        
        # Handle cancellation
        if stripe_subscription.get('cancel_at_period_end'):
            subscription.cancel_at = datetime.fromtimestamp(stripe_subscription['current_period_end'])
            subscription.cancelled_at = datetime.utcnow()
        
        db.commit()
        
        if old_status != new_status:
            logger.info(f"📝 Subscription {subscription.subscription_number} status changed: {old_status} → {new_status}")
        
    except Exception as e:
        logger.error(f"Error handling subscription updated: {str(e)}")
        db.rollback()


def handle_subscription_deleted(db: Session, stripe_subscription):
    """Handle subscription cancellation"""
    try:
        subscription = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == stripe_subscription['id']
        ).first()
        
        if not subscription:
            return
        
        subscription.status = "CANCELLED"
        subscription.ended_at = datetime.utcnow()
        
        if not subscription.cancelled_at:
            subscription.cancelled_at = datetime.utcnow()
        
        db.commit()
        
        logger.info(f"🚫 Subscription {subscription.subscription_number} cancelled")
        
    except Exception as e:
        logger.error(f"Error handling subscription deleted: {str(e)}")
        db.rollback()


def handle_payment_intent_succeeded(db: Session, payment_intent):
    """Handle successful one-time payment"""
    try:
        # This is mainly for logging, as we already handle this in the create flow
        order_id = payment_intent.get('metadata', {}).get('order_id')
        subscription_id = payment_intent.get('metadata', {}).get('subscription_id')
        
        if subscription_id:
            logger.info(f"✅ Payment intent succeeded for subscription ID {subscription_id}: {payment_intent['currency'].upper()} {payment_intent['amount'] / 100}")
        
    except Exception as e:
        logger.error(f"Error handling payment intent succeeded: {str(e)}")


def handle_payment_intent_failed(db: Session, payment_intent):
    """Handle failed one-time payment"""
    try:
        order_id = payment_intent.get('metadata', {}).get('order_id')
        subscription_id = payment_intent.get('metadata', {}).get('subscription_id')
        
        if subscription_id:
            logger.warning(f"⚠️ Payment intent failed for subscription ID {subscription_id}")
            
            # TODO: Handle failed payment - maybe mark order as failed
        
    except Exception as e:
        logger.error(f"Error handling payment intent failed: {str(e)}")
