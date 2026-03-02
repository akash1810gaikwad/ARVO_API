from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from config.mysql_database import get_mysql_db
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/test-cleanup", tags=["Test Cleanup"])


class MarkSimsTestedRequest(BaseModel):
    customer_id: int


@router.post("/mark-sims-tested")
def mark_customer_sims_as_tested(
    request: MarkSimsTestedRequest,
    db: Session = Depends(get_mysql_db)
):
    """
    Mark all SIMs allocated to a customer as tested (is_tested = 1).
    This is used to flag SIMs used in test payments.
    
    Request body: {"customer_id": 123}
    """
    from models.mysql_models import Customer
    from models.mysql_models import Subscriber, ChildSimCard, SimInventory
    
    try:
        customer_id = request.customer_id
        
        # Verify customer exists
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "message": "Customer not found",
                    "customer_id": customer_id
                }
            )
        
        # Get subscriber
        subscriber = db.query(Subscriber).filter(Subscriber.customer_id == customer_id).first()
        if not subscriber:
            return {
                "success": True,
                "message": "No subscriber found for this customer",
                "customer_id": customer_id,
                "sims_marked_tested": 0
            }
        
        # Get all child SIM cards for this subscriber
        child_sims = db.query(ChildSimCard).filter(
            ChildSimCard.subscriber_id == subscriber.id
        ).all()
        
        if not child_sims:
            return {
                "success": True,
                "message": "No SIM cards found for this customer",
                "customer_id": customer_id,
                "sims_marked_tested": 0
            }
        
        # Mark all associated SIM inventory as tested
        marked_count = 0
        sim_details = []
        
        for child_sim in child_sims:
            if child_sim.sim_inventory_id:
                sim_inv = db.query(SimInventory).filter(
                    SimInventory.id == child_sim.sim_inventory_id
                ).first()
                
                if sim_inv and not sim_inv.is_tested:
                    sim_inv.is_tested = True
                    marked_count += 1
                    sim_details.append({
                        "sim_inventory_id": sim_inv.id,
                        "iccid": sim_inv.iccid,
                        "sim_number": sim_inv.sim_number
                    })
        
        db.commit()
        
        logger.info(f"Marked {marked_count} SIMs as tested for customer_id: {customer_id}")
        
        return {
            "success": True,
            "message": f"Marked {marked_count} SIMs as tested",
            "customer_id": customer_id,
            "customer_email": customer.email,
            "sims_marked_tested": marked_count,
            "sim_details": sim_details
        }
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to mark SIMs as tested: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to mark SIMs as tested",
                "error": str(e)
            }
        )


@router.delete("/customer/{customer_id}")
def delete_customer_test_data(
    customer_id: int,
    db: Session = Depends(get_mysql_db)
):
    """
    CRITICAL: Delete ALL records associated with a customer ID.
    This is for TEST purposes only - removes customer and all related data.
    
    Deletion order (to respect foreign key constraints):
    1. Parental Controls
    2. Customer Module Access
    3. Audit Trail
    4. Payments
    5. Child SIM Cards (and release SIM inventory)
    6. User Journeys (must be before Orders)
    7. Orders
    8. Subscriptions
    9. Complaints
    10. Subscriber
    11. Password Reset OTPs (by email)
    12. Customer
    
    WARNING: This operation is IRREVERSIBLE!
    """
    from models.mysql_models import Customer
    from models.mysql_models import (
        Subscriber, Subscription, ChildSimCard, SimInventory, Payment, AuditTrail
    )
    from models.mysql_models import Order
    from models.mysql_models import ParentalControl
    from models.mysql_models import OperatorModuleAccess
    from models.mysql_models import TblComplaintMaster, TblComplaintComment, TblComplaintAttachment
    from models.mysql_models import PasswordResetOTP
    
    try:
        # First, verify customer exists
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "message": "Customer not found",
                    "customer_id": customer_id
                }
            )
        
        customer_email = customer.email
        deletion_summary = {
            "customer_id": customer_id,
            "customer_email": customer_email,
            "deleted_records": {}
        }
        
        logger.info(f"Starting deletion of all data for customer_id: {customer_id} ({customer_email})")
        
        # Get subscriber_id for cascading deletes
        subscriber = db.query(Subscriber).filter(Subscriber.customer_id == customer_id).first()
        subscriber_id = subscriber.id if subscriber else None
        
        # Get subscription_ids for cascading deletes
        subscription_ids = []
        if subscriber_id:
            subscriptions = db.query(Subscription).filter(
                Subscription.subscriber_id == subscriber_id
            ).all()
            subscription_ids = [sub.id for sub in subscriptions]
        
        # Get order_ids for cascading deletes
        orders = db.query(Order).filter(Order.customer_id == customer_id).all()
        order_ids = [o.id for o in orders]
        
        # Get complaint_ids for cascading deletes
        complaints = db.query(TblComplaintMaster).filter(
            TblComplaintMaster.customer_id == customer_id
        ).all()
        complaint_ids = [c.id for c in complaints]
        
        # DELETION ORDER (respecting foreign key constraints):
        
        # 1. Delete Parental Controls
        parental_controls_count = db.query(ParentalControl).filter(
            ParentalControl.customer_id == customer_id
        ).delete(synchronize_session=False)
        deletion_summary["deleted_records"]["parental_controls"] = parental_controls_count
        logger.info(f"Deleted {parental_controls_count} parental control records")
        
        # 2. Delete Operator Module Access
        module_access_count = db.query(OperatorModuleAccess).filter(
            OperatorModuleAccess.customer_id == customer_id
        ).delete(synchronize_session=False)
        deletion_summary["deleted_records"]["operator_module_access"] = module_access_count
        logger.info(f"Deleted {module_access_count} operator module access records")
        
        # 3. Delete Complaint Attachments
        attachments_count = 0
        if complaint_ids:
            attachments_count = db.query(TblComplaintAttachment).filter(
                TblComplaintAttachment.complaint_id.in_(complaint_ids)
            ).delete(synchronize_session=False)
        deletion_summary["deleted_records"]["complaint_attachments"] = attachments_count
        logger.info(f"Deleted {attachments_count} complaint attachments")
        
        # 4. Delete Complaint Comments
        comments_count = 0
        if complaint_ids:
            comments_count = db.query(TblComplaintComment).filter(
                TblComplaintComment.complaint_id.in_(complaint_ids)
            ).delete(synchronize_session=False)
        deletion_summary["deleted_records"]["complaint_comments"] = comments_count
        logger.info(f"Deleted {comments_count} complaint comments")
        
        # 5. Delete Complaints
        complaints_count = db.query(TblComplaintMaster).filter(
            TblComplaintMaster.customer_id == customer_id
        ).delete(synchronize_session=False)
        deletion_summary["deleted_records"]["complaints"] = complaints_count
        logger.info(f"Deleted {complaints_count} complaints")
        
        # 6. Delete Audit Trail (must be before Orders/Subscriptions due to FK)
        # Delete by order_id, subscription_id, and customer_id to catch all related records
        audit_trail_count = 0
        
        # Delete audit trail by order_id
        if order_ids:
            audit_trail_count += db.query(AuditTrail).filter(
                AuditTrail.order_id.in_(order_ids)
            ).delete(synchronize_session=False)
        
        # Delete audit trail by subscription_id
        if subscription_ids:
            audit_trail_count += db.query(AuditTrail).filter(
                AuditTrail.subscription_id.in_(subscription_ids)
            ).delete(synchronize_session=False)
        
        # Delete audit trail by customer_id (for any remaining records)
        audit_trail_count += db.query(AuditTrail).filter(
            AuditTrail.customer_id == customer_id
        ).delete(synchronize_session=False)
        
        deletion_summary["deleted_records"]["audit_trail"] = audit_trail_count
        logger.info(f"Deleted {audit_trail_count} audit trail records")
        
        # 7. Delete Payments
        payments_count = 0
        if subscriber_id:
            payments_count = db.query(Payment).filter(
                Payment.subscriber_id == subscriber_id
            ).delete(synchronize_session=False)
        deletion_summary["deleted_records"]["payments"] = payments_count
        logger.info(f"Deleted {payments_count} payment records")
        
        # 8. Delete Child SIM Cards and release SIM inventory
        child_sim_cards_count = 0
        released_sims_count = 0
        if subscriber_id:
            # Get all child SIM cards
            child_sims = db.query(ChildSimCard).filter(
                ChildSimCard.subscriber_id == subscriber_id
            ).all()
            
            # Release SIM inventory back to AVAILABLE status
            for child_sim in child_sims:
                if child_sim.sim_inventory_id:
                    sim_inv = db.query(SimInventory).filter(
                        SimInventory.id == child_sim.sim_inventory_id
                    ).first()
                    if sim_inv:
                        sim_inv.status = "AVAILABLE"
                        sim_inv.assigned_to_child_sim_id = None
                        sim_inv.assigned_at = None
                        released_sims_count += 1
            
            # Delete child SIM cards
            child_sim_cards_count = db.query(ChildSimCard).filter(
                ChildSimCard.subscriber_id == subscriber_id
            ).delete(synchronize_session=False)
        
        deletion_summary["deleted_records"]["child_sim_cards"] = child_sim_cards_count
        deletion_summary["deleted_records"]["released_sims"] = released_sims_count
        logger.info(f"Deleted {child_sim_cards_count} child SIM cards and released {released_sims_count} SIMs")
        
        # 9. Delete User Journeys (must be before Orders due to FK constraint)
        from models.mysql_models import UserJourney
        user_journeys_count = 0
        
        # Delete by order_id
        if order_ids:
            user_journeys_count += db.query(UserJourney).filter(
                UserJourney.order_id.in_(order_ids)
            ).delete(synchronize_session=False)
        
        # Delete by subscription_id
        if subscription_ids:
            user_journeys_count += db.query(UserJourney).filter(
                UserJourney.subscription_id.in_(subscription_ids)
            ).delete(synchronize_session=False)
        
        # Delete by customer_id (for any remaining records)
        user_journeys_count += db.query(UserJourney).filter(
            UserJourney.customer_id == customer_id
        ).delete(synchronize_session=False)
        
        deletion_summary["deleted_records"]["user_journeys"] = user_journeys_count
        logger.info(f"Deleted {user_journeys_count} user journey records")
        
        # 10. Delete Orders
        orders_count = db.query(Order).filter(
            Order.customer_id == customer_id
        ).delete(synchronize_session=False)
        deletion_summary["deleted_records"]["orders"] = orders_count
        logger.info(f"Deleted {orders_count} order records")
        
        # 11. Delete Subscriptions
        subscriptions_count = 0
        if subscriber_id:
            subscriptions_count = db.query(Subscription).filter(
                Subscription.subscriber_id == subscriber_id
            ).delete(synchronize_session=False)
        deletion_summary["deleted_records"]["subscriptions"] = subscriptions_count
        logger.info(f"Deleted {subscriptions_count} subscription records")
        
        # 12. Delete Subscriber
        subscriber_count = 0
        if subscriber_id:
            subscriber_count = db.query(Subscriber).filter(
                Subscriber.id == subscriber_id
            ).delete(synchronize_session=False)
        deletion_summary["deleted_records"]["subscriber"] = subscriber_count
        logger.info(f"Deleted {subscriber_count} subscriber record")
        
        # 13. Delete Password Reset OTPs by email
        otp_count = db.query(PasswordResetOTP).filter(
            PasswordResetOTP.email == customer_email
        ).delete(synchronize_session=False)
        deletion_summary["deleted_records"]["password_reset_otps"] = otp_count
        logger.info(f"Deleted {otp_count} password reset OTP records")
        
        # 14. Delete Customer (final step)
        customer_count = db.query(Customer).filter(
            Customer.id == customer_id
        ).delete(synchronize_session=False)
        deletion_summary["deleted_records"]["customer"] = customer_count
        logger.info(f"Deleted {customer_count} customer record")
        
        # Commit all deletions
        db.commit()
        
        # Calculate total deleted records
        total_deleted = sum(deletion_summary["deleted_records"].values())
        
        logger.info(f"Successfully deleted all data for customer_id: {customer_id}. Total records deleted: {total_deleted}")
        
        return {
            "success": True,
            "message": f"Successfully deleted all data for customer {customer_email}",
            "total_records_deleted": total_deleted,
            "deletion_summary": deletion_summary
        }
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete customer data: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to delete customer data",
                "error": str(e)
            }
        )
