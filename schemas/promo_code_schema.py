from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal


class PromoCodeCreate(BaseModel):
    """Create promo code request"""
    code: str = Field(..., min_length=1, max_length=50, description="Unique promo code")
    description: Optional[str] = Field(None, description="Description of the promo code")
    message: Optional[str] = Field(None, description="Message to display when promo is applied")
    
    # Validation settings
    is_active: bool = Field(True, description="Whether promo code is currently active")
    valid_from: Optional[datetime] = Field(None, description="Start date for promo validity")
    valid_until: Optional[datetime] = Field(None, description="End date for promo validity")
    max_uses: Optional[int] = Field(None, description="Maximum number of times this promo can be used")
    
    # Payment bypass settings
    bypass_payment: bool = Field(False, description="If True, skip Stripe payment and create dummy payment")
    activate_sim: bool = Field(True, description="If True, activate SIM; If False, allocate but don't activate")
    
    # Discount settings (for future use)
    discount_type: Optional[str] = Field(None, description="PERCENTAGE, FIXED_AMOUNT, or NULL")
    discount_value: Optional[Decimal] = Field(None, description="Discount amount or percentage")
    
    created_by: Optional[str] = Field(None, description="Admin who created this promo")


class PromoCodeUpdate(BaseModel):
    """Update promo code request"""
    description: Optional[str] = None
    message: Optional[str] = None
    is_active: Optional[bool] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    max_uses: Optional[int] = None
    bypass_payment: Optional[bool] = None
    activate_sim: Optional[bool] = None
    discount_type: Optional[str] = None
    discount_value: Optional[Decimal] = None


class PromoCodeResponse(BaseModel):
    """Promo code response"""
    id: int
    code: str
    description: Optional[str] = None
    message: Optional[str] = None
    
    # Validation settings
    is_active: bool
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    max_uses: Optional[int] = None
    current_uses: int
    
    # Payment bypass settings
    bypass_payment: bool
    activate_sim: bool
    
    # Discount settings
    discount_type: Optional[str] = None
    discount_value: Optional[Decimal] = None
    
    # Metadata
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    
    class Config:
        from_attributes = True


class PromoCodeValidationResponse(BaseModel):
    """Promo code validation response"""
    valid: bool
    message: str
    promo_code: Optional[PromoCodeResponse] = None
