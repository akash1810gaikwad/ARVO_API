from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from config.mysql_database import get_mysql_db
from repositories.user_journey_repo import UserJourneyRepository
from schemas.user_journey_schema import UserJourneyResponse, UserJourneyCreate, UserJourneyUpdate
from middleware.auth import get_current_user
from models.mysql_models import Customer
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/user-journeys", tags=["User Journey"])


@router.post("/", response_model=UserJourneyResponse)
def create_user_journey(
    journey_data: UserJourneyCreate,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """
    Create a new user journey (Step 1: Registration completed)
    """
    try:
        journey = UserJourneyRepository.create_journey(db, journey_data)
        return journey
    except Exception as e:
        logger.error(f"Error creating user journey: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to create user journey",
                "error": str(e)
            }
        )


@router.get("/{journey_id}", response_model=UserJourneyResponse)
def get_user_journey(
    journey_id: int,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """
    Get user journey by ID
    """
    journey = UserJourneyRepository.get_journey_by_id(db, journey_id)
    if not journey:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "message": "User journey not found",
                "journey_id": journey_id
            }
        )
    return journey


@router.get("/customer/{customer_id}", response_model=UserJourneyResponse)
def get_customer_journey(
    customer_id: int,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """
    Get the most recent user journey for a customer
    """
    journey = UserJourneyRepository.get_journey_by_customer_id(db, customer_id)
    if not journey:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "message": "No user journey found for this customer",
                "customer_id": customer_id
            }
        )
    return journey


@router.get("/stripe-session/{stripe_session_id}", response_model=UserJourneyResponse)
def get_journey_by_stripe_session(
    stripe_session_id: str,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """
    Get user journey by Stripe session ID
    """
    journey = UserJourneyRepository.get_journey_by_stripe_session(db, stripe_session_id)
    if not journey:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "message": "No user journey found for this Stripe session",
                "stripe_session_id": stripe_session_id
            }
        )
    return journey


@router.get("/order/{order_id}", response_model=UserJourneyResponse)
def get_journey_by_order(
    order_id: int,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """
    Get user journey by order ID
    """
    journey = UserJourneyRepository.get_journey_by_order_id(db, order_id)
    if not journey:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "message": "No user journey found for this order",
                "order_id": order_id
            }
        )
    return journey


@router.get("/", response_model=List[UserJourneyResponse])
def get_all_journeys(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """
    Get all user journeys with optional filtering
    
    Query params:
    - skip: Number of records to skip (pagination)
    - limit: Maximum number of records to return
    - status: Filter by journey status (IN_PROGRESS, COMPLETED, FAILED)
    """
    journeys = UserJourneyRepository.get_all_journeys(db, skip, limit, status)
    return journeys


@router.patch("/{journey_id}", response_model=UserJourneyResponse)
def update_user_journey(
    journey_id: int,
    update_data: UserJourneyUpdate,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """
    Update user journey with step completion
    """
    try:
        journey = UserJourneyRepository.update_journey(db, journey_id, update_data)
        if not journey:
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "message": "User journey not found",
                    "journey_id": journey_id
                }
            )
        return journey
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user journey: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to update user journey",
                "error": str(e)
            }
        )
