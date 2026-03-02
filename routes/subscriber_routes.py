from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from config.mysql_database import get_mysql_db
from models.mysql_models import Subscriber, Subscription, ChildSimCard, Payment
from models.mysql_models import Customer
from models.mysql_models import PlanMaster
from middleware.auth import get_current_user
from fastapi import Depends

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/subscribers", tags=["Subscribers"])


@router.get("/")
def get_all_subscribers(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of records to return"),
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """Get all subscribers grouped by customer (one row per customer with aggregated subscriptions)"""
    try:
        from sqlalchemy import func
        from datetime import datetime
        
        # Get unique subscribers with pagination
        subscribers = db.query(Subscriber).order_by(Subscriber.id.desc()).offset(skip).limit(limit).all()
        
        result = []
        for subscriber in subscribers:
            # Get customer
            customer = db.query(Customer).filter(Customer.id == subscriber.customer_id).first()
            if not customer:
                continue
            
            # Get all subscriptions for this subscriber
            subscriptions = db.query(Subscription).filter(
                Subscription.subscriber_id == subscriber.id
            ).order_by(Subscription.created_at.desc()).all()
            
            if not subscriptions:
                continue
            
            # Get all plans for this subscriber
            plan_names = []
            total_children = 0
            active_subscriptions = 0
            latest_subscription = None
            latest_created_at = None
            
            for subscription in subscriptions:
                plan = db.query(PlanMaster).filter(PlanMaster.id == subscription.plan_id).first()
                if plan and plan.plan_name not in plan_names:
                    plan_names.append(plan.plan_name)
                
                total_children += subscription.number_of_children or 0
                
                if subscription.status == "ACTIVE":
                    active_subscriptions += 1
                
                # Track latest subscription
                if subscription.created_at:
                    if latest_created_at is None or subscription.created_at > latest_created_at:
                        latest_created_at = subscription.created_at
                        latest_subscription = subscription
            
            # Use the latest subscription for main data
            if not latest_subscription:
                latest_subscription = subscriptions[0]
            
            # Get plan for latest subscription
            plan = db.query(PlanMaster).filter(PlanMaster.id == latest_subscription.plan_id).first()
            
            # Split full_name into first_name and last_name
            first_name = ""
            last_name = ""
            if customer.full_name:
                name_parts = customer.full_name.split(" ", 1)
                first_name = name_parts[0] if len(name_parts) > 0 else ""
                last_name = name_parts[1] if len(name_parts) > 1 else ""
            
            # Build single aggregated row
            result.append({
                "customer_id": subscriber.customer_id,
                "plan_id": latest_subscription.plan_id,
                "sim_id": None,
                "external_reference": latest_subscription.stripe_subscription_id or f"SUB_{latest_subscription.subscription_number}",
                "transatel_subscriber_id": None,
                "auto_renewal": latest_subscription.auto_renew,
                "notes": f"{len(subscriptions)} subscription(s): {', '.join(plan_names)} - {total_children} children total",
                "id": subscriber.id,  # Use subscriber ID instead of subscription ID
                "subscription_status": "ACTIVE" if active_subscriptions > 0 else latest_subscription.status,
                "activation_date": latest_subscription.start_date.isoformat() if latest_subscription.start_date else None,
                "expiry_date": latest_subscription.end_date.isoformat() if latest_subscription.end_date else None,
                "last_renewal_date": None,
                "next_billing_date": latest_subscription.next_billing_date.isoformat() if latest_subscription.next_billing_date else None,
                "data_used_gb": "0.00",
                "voice_used_minutes": 0,
                "sms_used_count": 0,
                "created_at": subscriber.created_at.isoformat() if subscriber.created_at else None,
                "updated_at": subscriber.updated_at.isoformat() if subscriber.updated_at else None,
                "terminated_at": latest_subscription.cancelled_at.isoformat() if latest_subscription.cancelled_at else None,
                "suspended_at": None,
                "customer": {
                    "id": customer.id,
                    "email": customer.email,
                    "first_name": first_name,
                    "last_name": last_name,
                    "phone": customer.phone_number,
                    "country_code": None,
                    "is_active": customer.is_active,
                    "is_verified": customer.is_email_verified if hasattr(customer, 'is_email_verified') else False,
                    "created_at": customer.created_at.isoformat() if customer.created_at else None
                },
                # Additional aggregated fields
                "total_subscriptions": len(subscriptions),
                "active_subscriptions": active_subscriptions,
                "total_children": total_children,
                "all_plans": ", ".join(plan_names)
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Error fetching subscribers: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch subscribers: {str(e)}"
        )


@router.get("/{subscriber_id}")
def get_subscriber_by_id(
    subscriber_id: int,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """Get a specific subscription by ID in the old API format"""
    try:
        # Get subscription by ID
        subscription = db.query(Subscription).filter(Subscription.id == subscriber_id).first()
        
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Subscription with ID {subscriber_id} not found"
            )
        
        # Get subscriber
        subscriber = db.query(Subscriber).filter(Subscriber.id == subscription.subscriber_id).first()
        
        # Get customer
        customer = db.query(Customer).filter(Customer.id == subscriber.customer_id).first() if subscriber else None
        
        # Get plan
        plan = db.query(PlanMaster).filter(PlanMaster.id == subscription.plan_id).first()
        
        # Split full_name into first_name and last_name
        first_name = ""
        last_name = ""
        if customer and customer.full_name:
            name_parts = customer.full_name.split(" ", 1)
            first_name = name_parts[0] if len(name_parts) > 0 else ""
            last_name = name_parts[1] if len(name_parts) > 1 else ""
        
        return {
            "customer_id": subscriber.customer_id if subscriber else None,
            "plan_id": subscription.plan_id,
            "sim_id": None,
            "external_reference": subscription.stripe_subscription_id or f"SUB_{subscription.subscription_number}",
            "transatel_subscriber_id": None,
            "auto_renewal": subscription.auto_renew,
            "notes": f"Subscription {subscription.subscription_number} - {plan.plan_name if plan else 'Unknown Plan'}",
            "id": subscription.id,
            "subscription_status": subscription.status,
            "activation_date": subscription.start_date.isoformat() if subscription.start_date else None,
            "expiry_date": subscription.end_date.isoformat() if subscription.end_date else None,
            "last_renewal_date": None,
            "next_billing_date": subscription.next_billing_date.isoformat() if subscription.next_billing_date else None,
            "data_used_gb": "0.00",
            "voice_used_minutes": 0,
            "sms_used_count": 0,
            "created_at": subscription.created_at.isoformat() if subscription.created_at else None,
            "updated_at": subscription.updated_at.isoformat() if subscription.updated_at else None,
            "terminated_at": subscription.cancelled_at.isoformat() if subscription.cancelled_at else None,
            "suspended_at": None,
            "customer": {
                "id": customer.id if customer else None,
                "email": customer.email if customer else None,
                "first_name": first_name,
                "last_name": last_name,
                "phone": customer.phone_number if customer else None,
                "country_code": None,
                "is_active": customer.is_active if customer else False,
                "is_verified": customer.is_email_verified if customer else False,
                "created_at": customer.created_at.isoformat() if customer and customer.created_at else None
            } if customer else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching subscription {subscriber_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch subscription: {str(e)}"
        )



@router.get("/details/{customer_id}")
def get_subscriber_details_by_customer(
    customer_id: int,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """Get detailed subscriber information by customer ID with plan and SIM details"""
    try:
        from models.mysql_models import Subscriber, Subscription, ChildSimCard, SimInventory
        from models.mysql_models import PlanMaster
        
        # Get subscriber by customer_id
        subscriber = db.query(Subscriber).filter(Subscriber.customer_id == customer_id).first()
        
        if not subscriber:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Subscriber not found for customer ID {customer_id}"
            )
        
        # Get all subscriptions for this subscriber
        subscriptions = db.query(Subscription).filter(
            Subscription.subscriber_id == subscriber.id
        ).order_by(Subscription.id.desc()).all()
        
        result = []
        
        for subscription in subscriptions:
            # Get plan details
            plan = db.query(PlanMaster).filter(PlanMaster.id == subscription.plan_id).first()
            
            # Get child SIM cards for this subscription
            child_sims = db.query(ChildSimCard).filter(
                ChildSimCard.subscription_id == subscription.id
            ).order_by(ChildSimCard.child_order).all()
            
            # For each child SIM, get the SIM inventory details
            for child_sim in child_sims:
                sim_details = None
                
                if child_sim.sim_inventory_id:
                    sim_inventory = db.query(SimInventory).filter(
                        SimInventory.id == child_sim.sim_inventory_id
                    ).first()
                    
                    if sim_inventory:
                        sim_details = {
                            "sim_id": sim_inventory.id,
                            "iccid": sim_inventory.iccid,
                            "msisdn": sim_inventory.msisdn,
                            "sim_type": sim_inventory.sim_type,
                            "activation_code": sim_inventory.activation_code,
                            "sim_status": sim_inventory.status,
                            "is_allocated": sim_inventory.assigned_to_child_sim_id is not None,
                            "is_in_use": sim_inventory.status == "ASSIGNED" or sim_inventory.status == "ACTIVE",
                            "activation_date": child_sim.activation_date.isoformat() if child_sim.activation_date else None
                        }
                else:
                    # Use child_sim data if no inventory record
                    sim_details = {
                        "sim_id": None,
                        "iccid": child_sim.iccid,
                        "msisdn": child_sim.msisdn,
                        "sim_type": child_sim.sim_type,
                        "activation_code": child_sim.activation_code,
                        "sim_status": "ACTIVE" if child_sim.is_active else "INACTIVE",
                        "is_allocated": True,
                        "is_in_use": child_sim.is_active,
                        "activation_date": child_sim.activation_date.isoformat() if child_sim.activation_date else None
                    }
                
                # Build plan details
                plan_details = None
                if plan:
                    plan_details = {
                        "plan_id": plan.id,
                        "plan_name": plan.plan_name,
                        "plan_type": plan.plan_type.value if hasattr(plan.plan_type, 'value') else str(plan.plan_type) if plan.plan_type else "Monthly",
                        "data_limit": plan.data_allowance or "0 GB",
                        "validity_days": plan.duration_days or 30,
                        "price": float(plan.monthly_price) if plan.monthly_price else 0.0,
                        "currency": plan.currency or "EUR",
                        "description": plan.description
                    }
                
                result.append({
                    "subscriber_id": subscription.id,
                    "customer_id": customer_id,
                    "subscription_status": subscription.status,
                    "plan": plan_details,
                    "sim": sim_details,
                    "activation_date": subscription.start_date.isoformat() if subscription.start_date else None,
                    "expiry_date": subscription.end_date.isoformat() if subscription.end_date else None,
                    "next_billing_date": subscription.next_billing_date.isoformat() if subscription.next_billing_date else None,
                    "suspended_at": None,
                    "terminated_at": subscription.cancelled_at.isoformat() if subscription.cancelled_at else None,
                    "created_at": subscription.created_at.isoformat() if subscription.created_at else None,
                    "updated_at": subscription.updated_at.isoformat() if subscription.updated_at else None,
                    "auto_renewal": subscription.auto_renew,
                    "external_reference": subscription.stripe_subscription_id or f"SUB_{subscription.subscription_number}",
                    "transatel_subscriber_id": None,
                    "notes": f"Subscription {subscription.subscription_number} - {plan.plan_name if plan else 'Unknown Plan'}"
                })
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching subscriber details for customer {customer_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch subscriber details: {str(e)}"
        )



@router.get("/summary/counts")
def get_subscriber_summary_counts(db: Session = Depends(get_mysql_db), current_user: Customer = Depends(get_current_user)):
    """Get summary counts for subscribers and allocated SIMs"""
    try:
        from models.mysql_models import SimInventory
        from datetime import datetime, timedelta
        from sqlalchemy import func, cast, Date
        
        # Count total subscribers
        total_subscribers = db.query(Subscriber).count()
        
        # Count allocated SIMs (where assigned_to_child_sim_id is not null or status is ASSIGNED/ACTIVE)
        total_allocated_sims = db.query(SimInventory).filter(
            (SimInventory.assigned_to_child_sim_id.isnot(None)) | 
            (SimInventory.status.in_(["ASSIGNED", "ACTIVE"]))
        ).count()
        
        # Get today's date (start of day)
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Count subscribers added today
        today_added_count = db.query(Subscriber).filter(
            cast(Subscriber.created_at, Date) == today_start.date()
        ).count()
        
        return {
            "success": True,
            "total_subscribers": total_subscribers,
            "total_allocated_sims": total_allocated_sims,
            "today_added_count": today_added_count
        }
        
    except Exception as e:
        logger.error(f"Error fetching subscriber summary counts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch summary counts: {str(e)}"
        )
