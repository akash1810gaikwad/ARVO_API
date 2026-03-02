from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal


# Child Details Schema
class ChildDetails(BaseModel):
    """Child information"""
    name: str = Field(..., min_length=1, max_length=255)
    age: int = Field(..., ge=1, le=18)


# Create Subscription Request
class CreateSubscriptionRequest(BaseModel):
    """Complete subscription creation request"""
    customer_id: int
    plan_id: int
    start_date: date
    end_date: date
    children: List[ChildDetails] = Field(..., min_items=1, max_items=10)
    sim_type: str = Field(default="pSIM", pattern="^(eSIM|pSIM)$", description="Type of SIM to allocate")
    currency: str = Field(default="GBP", pattern="^[A-Z]{3}$")
    auto_renew: bool = True
    payment_method_id: str = Field(..., description="Stripe payment method ID")
    promo_code: Optional[str] = Field(None, description="Promo code for special handling")


# Order Response
class OrderResponse(BaseModel):
    """Order creation response"""
    order_id: int
    order_number: str
    order_status: str
    process_state: str
    
    # Subscription Details
    plan_name: str
    number_of_children: int
    start_date: date
    end_date: date
    
    # Pricing
    plan_price_per_child: Decimal
    initial_payment_amount: Decimal
    monthly_amount: Decimal
    total_amount: Decimal
    currency: str
    
    # Payment
    payment_status: str
    stripe_payment_intent_id: Optional[str] = None
    
    # Created Resources
    subscriber_id: Optional[int] = None
    subscription_id: Optional[int] = None
    sim_cards_assigned: int = 0
    
    # Test Order Flag
    is_test_order: Optional[bool] = False
    
    created_at: datetime
    
    class Config:
        from_attributes = True


# Subscription Response
class SubscriptionResponse(BaseModel):
    """Subscription details"""
    id: int
    subscription_number: str
    subscriber_id: int
    plan_id: int
    status: str
    
    # Date Range
    start_date: date
    end_date: date
    next_billing_date: Optional[date] = None
    
    # Children
    number_of_children: int
    
    # Pricing
    plan_price_per_child: Decimal
    total_monthly_amount: Decimal
    initial_payment_amount: Decimal
    currency: str
    
    # Billing
    billing_cycle: str
    auto_renew: bool
    
    created_at: datetime
    
    class Config:
        from_attributes = True


# Child SIM Card Response
class ChildSimCardResponse(BaseModel):
    """Child SIM card details"""
    id: int
    subscription_id: int
    child_name: str
    child_age: int
    child_order: int
    
    # SIM Details
    sim_number: Optional[str] = None
    iccid: Optional[str] = None
    msisdn: Optional[str] = None  # Changed from phone_number
    activation_code: Optional[str] = None  # New field
    sim_type: Optional[str] = None  # New field
    
    is_active: bool
    activation_date: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


# Payment Response
class PaymentResponse(BaseModel):
    """Payment details"""
    id: int
    subscription_id: int
    payment_type: str
    amount: Decimal
    currency: str
    status: str
    
    # Payment Method
    payment_method_type: Optional[str] = None
    card_brand: Optional[str] = None
    card_last4: Optional[str] = None
    
    # Billing Period
    billing_period_start: Optional[date] = None
    billing_period_end: Optional[date] = None
    
    payment_date: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


# Resume Order Request
class ResumeOrderRequest(BaseModel):
    """Resume a failed order"""
    order_id: int
    payment_method_id: Optional[str] = None


# Cancel Subscription Request
class CancelSubscriptionRequest(BaseModel):
    """Cancel subscription"""
    subscription_id: int
    reason: Optional[str] = None
    cancel_immediately: bool = False


# SIM Inventory Schema
class SimInventoryCreate(BaseModel):
    """Add SIM to inventory"""
    sim_number: str = Field(..., min_length=1, max_length=50)
    iccid: Optional[str] = Field(None, max_length=50)
    msisdn: Optional[str] = Field(None, max_length=20)  # Changed from phone_number
    activation_code: Optional[str] = Field(None, max_length=255)  # Increased to 255 for eSIM LPA codes
    sim_type: str = Field(default="pSIM", pattern="^(eSIM|pSIM)$")  # New field
    batch_number: Optional[str] = None
    supplier: Optional[str] = None


class SimInventoryResponse(BaseModel):
    """SIM inventory details"""
    id: int
    sim_number: str
    iccid: Optional[str] = None
    msisdn: Optional[str] = None  # Changed from phone_number
    activation_code: Optional[str] = None  # New field
    sim_type: str  # New field
    status: str
    batch_number: Optional[str] = None
    supplier: Optional[str] = None
    assigned_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


# Subscription with Children
class SubscriptionWithChildren(SubscriptionResponse):
    """Subscription with child SIM cards"""
    children: List[ChildSimCardResponse] = []


# Audit Trail Response
class AuditTrailResponse(BaseModel):
    """Audit trail entry"""
    id: int
    order_id: Optional[int] = None
    subscription_id: Optional[int] = None
    customer_id: Optional[int] = None
    action: str
    step: str
    status: str
    details: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class PaymentResponse(BaseModel):
    id: int
    subscription_id: int
    stripe_payment_intent_id: str
    amount: Decimal
    currency: str
    status: str
    payment_method_type: Optional[str] = None
    card_brand: Optional[str] = None
    card_last4: Optional[str] = None
    payment_date: Optional[datetime] = None
    receipt_url: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True