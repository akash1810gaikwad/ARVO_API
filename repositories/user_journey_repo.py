import json
import logging
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
from models.mysql_models import UserJourney
from schemas.user_journey_schema import UserJourneyCreate, UserJourneyUpdate

logger = logging.getLogger(__name__)


class UserJourneyRepository:
    """Repository for user journey operations"""
    
    @staticmethod
    def create_journey(db: Session, journey_data: UserJourneyCreate) -> UserJourney:
        """Create a new user journey (Step 1: Registration)"""
        try:
            journey = UserJourney(
                customer_id=journey_data.customer_id,
                customer_email=journey_data.customer_email,
                journey_status="IN_PROGRESS",
                registration_completed=True,
                registration_completed_at=datetime.utcnow(),
                registration_payload=journey_data.registration_payload,
                updated_at=datetime.utcnow(),
                notes=journey_data.notes
            )
            db.add(journey)
            db.commit()
            db.refresh(journey)
            logger.info(f"Created user journey {journey.id} for customer {journey_data.customer_id}")
            return journey
        except Exception as e:
            logger.error(f"Error creating user journey: {e}")
            db.rollback()
            raise
    
    @staticmethod
    def get_journey_by_id(db: Session, journey_id: int) -> Optional[UserJourney]:
        """Get user journey by ID"""
        return db.query(UserJourney).filter(UserJourney.id == journey_id).first()
    
    @staticmethod
    def get_journey_by_customer_id(db: Session, customer_id: int) -> Optional[UserJourney]:
        """Get the most recent user journey for a customer"""
        return db.query(UserJourney).filter(
            UserJourney.customer_id == customer_id
        ).order_by(desc(UserJourney.created_at)).first()
    
    @staticmethod
    def get_journey_by_stripe_session(db: Session, stripe_session_id: str) -> Optional[UserJourney]:
        """Get user journey by Stripe session ID"""
        return db.query(UserJourney).filter(
            UserJourney.stripe_session_id == stripe_session_id
        ).first()
    
    @staticmethod
    def get_journey_by_order_id(db: Session, order_id: int) -> Optional[UserJourney]:
        """Get user journey by order ID"""
        return db.query(UserJourney).filter(
            UserJourney.order_id == order_id
        ).first()
    
    @staticmethod
    def get_all_journeys(
        db: Session, 
        skip: int = 0, 
        limit: int = 100,
        status: Optional[str] = None
    ) -> List[UserJourney]:
        """Get all user journeys with optional filtering"""
        query = db.query(UserJourney)
        
        if status:
            query = query.filter(UserJourney.journey_status == status)
        
        return query.order_by(desc(UserJourney.created_at)).offset(skip).limit(limit).all()
    
    @staticmethod
    def update_journey(
        db: Session, 
        journey_id: int, 
        update_data: UserJourneyUpdate
    ) -> Optional[UserJourney]:
        """Update user journey with step completion"""
        try:
            journey = UserJourneyRepository.get_journey_by_id(db, journey_id)
            if not journey:
                return None
            
            # Update plan selection (Step 2)
            if update_data.plan_selection_completed is not None:
                journey.plan_selection_completed = update_data.plan_selection_completed
                if update_data.plan_selection_completed:
                    journey.plan_selection_completed_at = datetime.utcnow()
            
            if update_data.plan_selection_payload:
                journey.plan_selection_payload = update_data.plan_selection_payload
            if update_data.plan_id:
                journey.plan_id = update_data.plan_id
            if update_data.stripe_session_id:
                journey.stripe_session_id = update_data.stripe_session_id
            
            # Update payment (Step 3)
            if update_data.payment_completed is not None:
                journey.payment_completed = update_data.payment_completed
                if update_data.payment_completed:
                    journey.payment_completed_at = datetime.utcnow()
            
            if update_data.payment_payload:
                journey.payment_payload = update_data.payment_payload
            if update_data.stripe_payment_intent_id:
                journey.stripe_payment_intent_id = update_data.stripe_payment_intent_id
            if update_data.order_id:
                journey.order_id = update_data.order_id
            
            # Update ICCID allocation (Step 4)
            if update_data.iccid_allocation_completed is not None:
                journey.iccid_allocation_completed = update_data.iccid_allocation_completed
                if update_data.iccid_allocation_completed:
                    journey.iccid_allocation_completed_at = datetime.utcnow()
            
            if update_data.iccid_allocation_payload:
                journey.iccid_allocation_payload = update_data.iccid_allocation_payload
            if update_data.sim_id:
                journey.sim_id = update_data.sim_id
            
            # Update eSIM activation (Step 5)
            if update_data.esim_activation_completed is not None:
                journey.esim_activation_completed = update_data.esim_activation_completed
                if update_data.esim_activation_completed:
                    journey.esim_activation_completed_at = datetime.utcnow()
            
            if update_data.esim_activation_payload:
                journey.esim_activation_payload = update_data.esim_activation_payload
            if update_data.subscriber_id:
                journey.subscriber_id = update_data.subscriber_id
            if update_data.subscription_id:
                journey.subscription_id = update_data.subscription_id
            
            # Update QR code generation (Step 6)
            if update_data.qr_code_generation_completed is not None:
                journey.qr_code_generation_completed = update_data.qr_code_generation_completed
                if update_data.qr_code_generation_completed:
                    journey.qr_code_generation_completed_at = datetime.utcnow()
            
            if update_data.qr_code_generation_payload:
                journey.qr_code_generation_payload = update_data.qr_code_generation_payload
            
            # Update journey status
            if update_data.journey_status:
                journey.journey_status = update_data.journey_status
            if update_data.journey_completed_at:
                journey.journey_completed_at = update_data.journey_completed_at
            
            # Check if journey is complete
            if (journey.registration_completed and 
                journey.plan_selection_completed and 
                journey.payment_completed and 
                journey.iccid_allocation_completed and 
                journey.esim_activation_completed and 
                journey.qr_code_generation_completed):
                journey.journey_status = "COMPLETED"
                if not journey.journey_completed_at:
                    journey.journey_completed_at = datetime.utcnow()
            
            if update_data.notes:
                journey.notes = update_data.notes
            
            journey.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(journey)
            logger.info(f"Updated user journey {journey_id}")
            return journey
            
        except Exception as e:
            logger.error(f"Error updating user journey: {e}")
            db.rollback()
            raise
    
    @staticmethod
    def update_plan_selection(
        db: Session,
        customer_id: int,
        plan_id: int,
        stripe_session_id: str,
        payload_data: dict
    ) -> Optional[UserJourney]:
        """Update journey with plan selection (Step 2)"""
        journey = UserJourneyRepository.get_journey_by_customer_id(db, customer_id)
        if not journey:
            logger.warning(f"No journey found for customer {customer_id}")
            return None
        
        update_data = UserJourneyUpdate(
            plan_selection_completed=True,
            plan_selection_payload=json.dumps(payload_data),
            plan_id=plan_id,
            stripe_session_id=stripe_session_id
        )
        return UserJourneyRepository.update_journey(db, journey.id, update_data)
    
    @staticmethod
    def update_payment_success(
        db: Session,
        stripe_session_id: str,
        order_id: int,
        payload_data: dict
    ) -> Optional[UserJourney]:
        """Update journey with payment success (Step 3)"""
        journey = UserJourneyRepository.get_journey_by_stripe_session(db, stripe_session_id)
        if not journey:
            logger.warning(f"No journey found for session {stripe_session_id}")
            return None
        
        update_data = UserJourneyUpdate(
            payment_completed=True,
            payment_payload=json.dumps(payload_data),
            order_id=order_id,
            stripe_payment_intent_id=payload_data.get("payment_intent_id")
        )
        return UserJourneyRepository.update_journey(db, journey.id, update_data)
    
    @staticmethod
    def update_iccid_allocation(
        db: Session,
        order_id: int,
        sim_id: int,
        payload_data: dict
    ) -> Optional[UserJourney]:
        """Update journey with ICCID allocation (Step 4)"""
        journey = UserJourneyRepository.get_journey_by_order_id(db, order_id)
        if not journey:
            logger.warning(f"No journey found for order {order_id}")
            return None
        
        update_data = UserJourneyUpdate(
            iccid_allocation_completed=True,
            iccid_allocation_payload=json.dumps(payload_data),
            sim_id=sim_id
        )
        return UserJourneyRepository.update_journey(db, journey.id, update_data)
    
    @staticmethod
    def update_esim_activation(
        db: Session,
        order_id: int,
        subscriber_id: int,
        subscription_id: int,
        payload_data: dict
    ) -> Optional[UserJourney]:
        """Update journey with eSIM activation (Step 5)"""
        journey = UserJourneyRepository.get_journey_by_order_id(db, order_id)
        if not journey:
            logger.warning(f"No journey found for order {order_id}")
            return None
        
        update_data = UserJourneyUpdate(
            esim_activation_completed=True,
            esim_activation_payload=json.dumps(payload_data),
            subscriber_id=subscriber_id,
            subscription_id=subscription_id
        )
        return UserJourneyRepository.update_journey(db, journey.id, update_data)
    
    @staticmethod
    def update_qr_code_generation(
        db: Session,
        order_id: int,
        payload_data: dict
    ) -> Optional[UserJourney]:
        """Update journey with QR code generation (Step 6)"""
        journey = UserJourneyRepository.get_journey_by_order_id(db, order_id)
        if not journey:
            logger.warning(f"No journey found for order {order_id}")
            return None
        
        update_data = UserJourneyUpdate(
            qr_code_generation_completed=True,
            qr_code_generation_payload=json.dumps(payload_data)
        )
        return UserJourneyRepository.update_journey(db, journey.id, update_data)
