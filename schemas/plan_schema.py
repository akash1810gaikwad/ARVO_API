from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class PlanBase(BaseModel):
    plan_code: str = Field(..., min_length=1, max_length=100)
    plan_name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    tagline: Optional[str] = Field(None, max_length=255)
    plan_type: str = Field(..., description="monthly or yearly")
    duration_days: int = Field(default=30, gt=0)
    monthly_price: Decimal = Field(..., gt=0)
    annual_price: Decimal = Field(..., gt=0)
    currency: str = Field(default="GBP", max_length=3)
    data_allowance: Optional[str] = Field(None, max_length=50)
    is_popular: bool = False
    gradient: Optional[str] = Field(None, max_length=255)
    icon_bg: Optional[str] = Field(None, max_length=255)
    is_active: bool = True
    sort_order: int = 0


class PlanCreate(PlanBase):
    service_option_ids: Optional[List[int]] = []


class PlanUpdate(BaseModel):
    plan_name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    tagline: Optional[str] = Field(None, max_length=255)
    monthly_price: Optional[Decimal] = Field(None, gt=0)
    annual_price: Optional[Decimal] = Field(None, gt=0)
    data_allowance: Optional[str] = Field(None, max_length=50)
    is_popular: Optional[bool] = None
    gradient: Optional[str] = Field(None, max_length=255)
    icon_bg: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class PlanServiceOptionResponse(BaseModel):
    id: int
    service_option_id: int
    option_code: str
    option_name: str
    category: str
    is_default: bool
    is_required: bool
    
    class Config:
        from_attributes = True


class PlanResponse(BaseModel):
    id: int
    plan_code: str
    plan_name: str
    description: Optional[str] = None
    tagline: Optional[str] = None
    plan_type: str
    duration_days: int
    monthly_price: Decimal
    annual_price: Decimal
    currency: str
    data_allowance: Optional[str] = None
    is_popular: bool
    gradient: Optional[str] = None
    icon_bg: Optional[str] = None
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    features: List[str] = []
    service_options: List[PlanServiceOptionResponse] = []
    
    class Config:
        from_attributes = True
