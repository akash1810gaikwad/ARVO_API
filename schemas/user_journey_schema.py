from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class UserJourneyResponse(BaseModel):
    """Response schema for user journey"""
    id: int
    customer_id: int
    customer_email: Optional[str] = None
    
    # Journey tracking
    journey_started_at: datetime
    journey_completed_at: Optional[datetime] = None
    journey_status: str
    
    # Step 1: Registration
    registration_completed: bool
    registration_completed_at: Optional[datetime] = None
    registration_payload: Optional[str] = None
    
    # Step 2: Plan Selection
    plan_selection_completed: bool
    plan_selection_completed_at: Optional[datetime] = None
    plan_selection_payload: Optional[str] = None
    
    # Step 3: Payment Success
    payment_completed: bool
    payment_completed_at: Optional[datetime] = None
    payment_payload: Optional[str] = None
    
    # Step 4: ICCID Allocation
    iccid_allocation_completed: bool
    iccid_allocation_completed_at: Optional[datetime] = None
    iccid_allocation_payload: Optional[str] = None
    
    # Step 5: eSIM Activation
    esim_activation_completed: bool
    esim_activation_completed_at: Optional[datetime] = None
    esim_activation_payload: Optional[str] = None
    
    # Step 6: QR Code Generation
    qr_code_generation_completed: bool
    qr_code_generation_completed_at: Optional[datetime] = None
    qr_code_generation_payload: Optional[str] = None
    
    # Summary fields
    subscriber_id: Optional[int] = None
    subscription_id: Optional[int] = None
    order_id: Optional[int] = None
    sim_id: Optional[int] = None
    plan_id: Optional[int] = None
    stripe_session_id: Optional[str] = None
    stripe_payment_intent_id: Optional[str] = None
    
    # Metadata
    created_at: datetime
    updated_at: Optional[datetime] = None
    notes: Optional[str] = None
    
    class Config:
        from_attributes = True


class UserJourneyCreate(BaseModel):
    """Schema for creating a new user journey"""
    customer_id: int
    customer_email: Optional[str] = None
    registration_payload: Optional[str] = None
    notes: Optional[str] = None


class UserJourneyUpdate(BaseModel):
    """Schema for updating user journey steps"""
    # Step 2: Plan Selection
    plan_selection_completed: Optional[bool] = None
    plan_selection_payload: Optional[str] = None
    plan_id: Optional[int] = None
    stripe_session_id: Optional[str] = None
    
    # Step 3: Payment Success
    payment_completed: Optional[bool] = None
    payment_payload: Optional[str] = None
    stripe_payment_intent_id: Optional[str] = None
    order_id: Optional[int] = None
    
    # Step 4: ICCID Allocation
    iccid_allocation_completed: Optional[bool] = None
    iccid_allocation_payload: Optional[str] = None
    sim_id: Optional[int] = None
    
    # Step 5: eSIM Activation
    esim_activation_completed: Optional[bool] = None
    esim_activation_payload: Optional[str] = None
    subscriber_id: Optional[int] = None
    subscription_id: Optional[int] = None
    
    # Step 6: QR Code Generation
    qr_code_generation_completed: Optional[bool] = None
    qr_code_generation_payload: Optional[str] = None
    
    # Journey status
    journey_status: Optional[str] = None
    journey_completed_at: Optional[datetime] = None
    notes: Optional[str] = None
