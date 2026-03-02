from fastapi import APIRouter, Request, HTTPException, Header
from sqlalchemy.orm import Session
from fastapi import Depends
import json
from config.settings import settings
from config.mysql_database import get_mysql_db
from models.mysql_models import Subscription, Payment, Subscriber, Customer
from models.whop_webhook_log_model import WhopWebhookLog
from services.whop_service import whop_service
from utils.logger import logger
from datetime import datetime
from decimal import Decimal

router = APIRouter(prefix="/api/v1/webhooks", tags=["Whop Webhooks"])


@router.post("/whop")
async def whop_webhook(
    request: Request,
    whop_signature: str = Header(None, alias="x-whop-signature"),
    db: Session = Depends(get_mysql_db)
):
    """
    Handle Whop webhook events
    
    Events handled:
    - membership.created: New membership purchased
    - membership.updated: Membership status changed
    - membership.cancelled: Membership cancelled
    - membership.renewed: Membership renewed
    - payment.succeeded: Payment successful
    - payment.failed: Payment failed
    
    All webhooks are logged to whop_webhook_logs table for testing and debugging
    """
    
    payload = await request.body()
    payload_str = payload.decode('utf-8')
    
    # Initialize webhook log
    webhook_log = None
    signature_valid = False
    
    try:
        # Parse event first to get basic info
        event = json.loads(payload_str)
        event_type = event.get('type', 'unknown')
        event_id = event.get('id')
        data = event.get('data', {})
        
        # Get webhook secret from settings
        webhook_secret = getattr(settings, 'WHOP_WEBHOOK_SECRET', '')
        
        # Validate signature if secret is configured
        if webhook_secret and whop_signature:
            signature_valid = whop_service.validate_webhook_signature(
                payload, whop_signature, webhook_secret
            )
            if not signature_valid:
                logger.error("❌ Whop webhook signature verification failed")
            else:
                logger.info("✅ Whop webhook signature verified")
        else:
            logger.warning("⚠️ Whop webhook signature validation is DISABLED")
            signature_valid = True  # Consider valid if validation is disabled
        
        # Extract common fields for quick reference
        membership_id = data.get('id') or data.get('membership_id')
        customer_email = data.get('email')
        plan_id = data.get('plan_id')
        amount = str(data.get('amount', '')) if data.get('amount') else None
        currency = data.get('currency')
        
        # Create webhook log entry
        webhook_log = WhopWebhookLog(
            event_type=event_type,
            event_id=event_id,
            raw_payload=payload_str,
            signature=whop_signature,
            signature_valid=signature_valid,
            status="RECEIVED",
            membership_id=membership_id,
            customer_email=customer_email,
            plan_id=plan_id,
            amount=amount,
            currency=currency,
            received_at=datetime.utcnow()
        )
        
        db.add(webhook_log)
        db.commit()
        db.refresh(webhook_log)
        
        logger.info(f"📨 Whop webhook logged: ID={webhook_log.id}, Type={event_type}, Event ID={event_id}")
        
        # If signature validation failed, reject the webhook
        if not signature_valid and webhook_secret:
            webhook_log.status = "FAILED"
            webhook_log.error_message = "Invalid signature"
            webhook_log.processed_at = datetime.utcnow()
            db.commit()
            raise HTTPException(status_code=400, detail="Invalid signature")
        
        # Handle different event types
        try:
            if event_type == 'membership.created':
                handle_membership_created(db, data)
                
            elif event_type == 'membership.updated':
                handle_membership_updated(db, data)
                
            elif event_type == 'membership.cancelled':
                handle_membership_cancelled(db, data)
                
            elif event_type == 'membership.renewed':
                handle_membership_renewed(db, data)
                
            elif event_type == 'payment.succeeded':
                handle_payment_succeeded(db, data)
                
            elif event_type == 'payment.failed':
                handle_payment_failed(db, data)
            
            else:
                logger.info(f"Unhandled Whop event type: {event_type}")
            
            # Mark as processed
            webhook_log.status = "PROCESSED"
            webhook_log.processed_at = datetime.utcnow()
            db.commit()
            
        except Exception as handler_error:
            # Mark as failed but don't raise - we still want to acknowledge receipt
            webhook_log.status = "FAILED"
            webhook_log.error_message = str(handler_error)
            webhook_log.processed_at = datetime.utcnow()
            db.commit()
            logger.error(f"❌ Whop webhook handler error: {str(handler_error)}", exc_info=True)
        
        return {
            "success": True, 
            "message": "Webhook received and logged",
            "webhook_log_id": webhook_log.id,
            "event_type": event_type
        }
        
    except HTTPException:
        raise
        
    except Exception as e:
        logger.error(f"❌ Whop webhook processing error: {str(e)}", exc_info=True)
        
        # Try to log the error
        if webhook_log:
            try:
                webhook_log.status = "FAILED"
                webhook_log.error_message = str(e)
                webhook_log.processed_at = datetime.utcnow()
                db.commit()
            except:
                pass
        
        raise HTTPException(status_code=500, detail=str(e))


def handle_membership_created(db: Session, data: dict):
    """Handle new membership creation"""
    try:
        membership_id = data.get('id')
        customer_email = data.get('email')
        plan_id = data.get('plan_id')
        status = data.get('status')
        
        logger.info(f"✅ New Whop membership created: {membership_id} for {customer_email}")
        
        # Find customer in database
        customer = db.query(Customer).filter(Customer.email == customer_email).first()
        
        if not customer:
            logger.warning(f"Customer not found for email: {customer_email}")
            return
        
        # Find or create subscriber
        subscriber = db.query(Subscriber).filter(
            Subscriber.customer_id == customer.id
        ).first()
        
        if not subscriber:
            # Create subscriber
            subscriber = Subscriber(
                customer_id=customer.id,
                auto_renew_enabled=True
            )
            db.add(subscriber)
            db.flush()
        
        # Create subscription record
        from models.mysql_models import PlanMaster
        plan = db.query(PlanMaster).filter(PlanMaster.id == plan_id).first()
        
        if plan:
            subscription = Subscription(
                subscriber_id=subscriber.id,
                plan_id=plan.id,
                subscription_number=f"WHOP-{membership_id}",
                status="ACTIVE" if status == "active" else "PENDING",
                start_date=datetime.utcnow(),
                auto_renew=True,
                currency="GBP"
            )
            
            db.add(subscription)
            db.commit()
            
            logger.info(f"✅ Subscription created from Whop membership: {subscription.subscription_number}")
        
    except Exception as e:
        logger.error(f"Error handling membership created: {str(e)}")
        db.rollback()


def handle_membership_updated(db: Session, data: dict):
    """Handle membership status update"""
    try:
        membership_id = data.get('id')
        status = data.get('status')
        
        # Find subscription by Whop membership ID
        subscription = db.query(Subscription).filter(
            Subscription.subscription_number == f"WHOP-{membership_id}"
        ).first()
        
        if not subscription:
            logger.warning(f"Subscription not found for Whop membership: {membership_id}")
            return
        
        # Map Whop status to our status
        status_mapping = {
            'active': 'ACTIVE',
            'cancelled': 'CANCELLED',
            'expired': 'EXPIRED',
            'trialing': 'ACTIVE'
        }
        
        old_status = subscription.status
        new_status = status_mapping.get(status, subscription.status)
        
        subscription.status = new_status
        db.commit()
        
        logger.info(f"📝 Whop membership {membership_id} status changed: {old_status} → {new_status}")
        
    except Exception as e:
        logger.error(f"Error handling membership updated: {str(e)}")
        db.rollback()


def handle_membership_cancelled(db: Session, data: dict):
    """Handle membership cancellation"""
    try:
        membership_id = data.get('id')
        
        subscription = db.query(Subscription).filter(
            Subscription.subscription_number == f"WHOP-{membership_id}"
        ).first()
        
        if not subscription:
            return
        
        subscription.status = "CANCELLED"
        subscription.cancelled_at = datetime.utcnow()
        subscription.ended_at = datetime.utcnow()
        
        db.commit()
        
        logger.info(f"🚫 Whop membership cancelled: {membership_id}")
        
    except Exception as e:
        logger.error(f"Error handling membership cancelled: {str(e)}")
        db.rollback()


def handle_membership_renewed(db: Session, data: dict):
    """Handle membership renewal"""
    try:
        membership_id = data.get('id')
        amount = data.get('amount', 0)
        currency = data.get('currency', 'gbp')
        
        subscription = db.query(Subscription).filter(
            Subscription.subscription_number == f"WHOP-{membership_id}"
        ).first()
        
        if not subscription:
            return
        
        # Create payment record
        payment = Payment(
            subscription_id=subscription.id,
            subscriber_id=subscription.subscriber_id,
            payment_type="RECURRING",
            amount=Decimal(str(amount / 100)),  # Convert cents to dollars
            currency=currency.upper(),
            status="SUCCEEDED",
            payment_date=datetime.utcnow()
        )
        
        db.add(payment)
        
        # Update subscription
        subscription.status = "ACTIVE"
        
        db.commit()
        
        logger.info(f"✅ Whop membership renewed: {membership_id}")
        
    except Exception as e:
        logger.error(f"Error handling membership renewed: {str(e)}")
        db.rollback()


def handle_payment_succeeded(db: Session, data: dict):
    """Handle successful payment"""
    try:
        payment_id = data.get('id')
        membership_id = data.get('membership_id')
        amount = data.get('amount', 0)
        currency = data.get('currency', 'gbp')
        
        logger.info(f"✅ Whop payment succeeded: {payment_id} for membership {membership_id}")
        
        # Find subscription
        subscription = db.query(Subscription).filter(
            Subscription.subscription_number == f"WHOP-{membership_id}"
        ).first()
        
        if subscription:
            # Create payment record
            payment = Payment(
                subscription_id=subscription.id,
                subscriber_id=subscription.subscriber_id,
                payment_type="INITIAL",
                amount=Decimal(str(amount / 100)),
                currency=currency.upper(),
                status="SUCCEEDED",
                payment_date=datetime.utcnow()
            )
            
            db.add(payment)
            db.commit()
        
    except Exception as e:
        logger.error(f"Error handling payment succeeded: {str(e)}")
        db.rollback()


def handle_payment_failed(db: Session, data: dict):
    """Handle failed payment"""
    try:
        payment_id = data.get('id')
        membership_id = data.get('membership_id')
        
        logger.warning(f"⚠️ Whop payment failed: {payment_id} for membership {membership_id}")
        
        # Find subscription and mark as past due
        subscription = db.query(Subscription).filter(
            Subscription.subscription_number == f"WHOP-{membership_id}"
        ).first()
        
        if subscription:
            subscription.status = "PAST_DUE"
            db.commit()
        
    except Exception as e:
        logger.error(f"Error handling payment failed: {str(e)}")
        db.rollback()


@router.get("/whop/logs")
async def get_whop_webhook_logs(
    skip: int = 0,
    limit: int = 50,
    event_type: str = None,
    status: str = None,
    db: Session = Depends(get_mysql_db)
):
    """
    Get Whop webhook logs for testing and debugging
    
    Query parameters:
    - skip: Number of records to skip (pagination)
    - limit: Maximum number of records to return (max 100)
    - event_type: Filter by event type (e.g., 'membership.created')
    - status: Filter by status (RECEIVED, PROCESSED, FAILED)
    """
    try:
        # Build query
        query = db.query(WhopWebhookLog)
        
        # Apply filters
        if event_type:
            query = query.filter(WhopWebhookLog.event_type == event_type)
        
        if status:
            query = query.filter(WhopWebhookLog.status == status)
        
        # Get total count
        total = query.count()
        
        # Get paginated results (most recent first)
        logs = query.order_by(WhopWebhookLog.received_at.desc()).offset(skip).limit(min(limit, 100)).all()
        
        # Format response
        results = []
        for log in logs:
            results.append({
                "id": log.id,
                "event_type": log.event_type,
                "event_id": log.event_id,
                "status": log.status,
                "signature_valid": log.signature_valid,
                "membership_id": log.membership_id,
                "customer_email": log.customer_email,
                "plan_id": log.plan_id,
                "amount": log.amount,
                "currency": log.currency,
                "error_message": log.error_message,
                "received_at": log.received_at.isoformat() if log.received_at else None,
                "processed_at": log.processed_at.isoformat() if log.processed_at else None,
                "raw_payload": json.loads(log.raw_payload) if log.raw_payload else None
            })
        
        return {
            "success": True,
            "total": total,
            "skip": skip,
            "limit": limit,
            "count": len(results),
            "logs": results
        }
        
    except Exception as e:
        logger.error(f"❌ Error fetching webhook logs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/whop/logs/{log_id}")
async def get_whop_webhook_log_detail(
    log_id: int,
    db: Session = Depends(get_mysql_db)
):
    """
    Get detailed information about a specific webhook log
    """
    try:
        log = db.query(WhopWebhookLog).filter(WhopWebhookLog.id == log_id).first()
        
        if not log:
            raise HTTPException(status_code=404, detail="Webhook log not found")
        
        return {
            "success": True,
            "log": {
                "id": log.id,
                "event_type": log.event_type,
                "event_id": log.event_id,
                "status": log.status,
                "signature": log.signature,
                "signature_valid": log.signature_valid,
                "membership_id": log.membership_id,
                "customer_email": log.customer_email,
                "plan_id": log.plan_id,
                "amount": log.amount,
                "currency": log.currency,
                "error_message": log.error_message,
                "received_at": log.received_at.isoformat() if log.received_at else None,
                "processed_at": log.processed_at.isoformat() if log.processed_at else None,
                "raw_payload": json.loads(log.raw_payload) if log.raw_payload else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching webhook log detail: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
