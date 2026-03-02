from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ServiceOptionBase(BaseModel):
    option_code: str = Field(..., min_length=1, max_length=100)
    option_name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    category: str = Field(..., description="Service option category")
    option_type: str = Field(..., description="circle, enable, or trailed_circle")
    is_default: bool = False
    is_active: bool = True
    sort_order: int = 0


class ServiceOptionCreate(ServiceOptionBase):
    pass


class ServiceOptionUpdate(BaseModel):
    option_name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class ServiceOptionResponse(ServiceOptionBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# Plan Service Option Schemas
class PlanServiceOptionBase(BaseModel):
    """Base schema for plan service option"""
    plan_id: int = Field(..., description="Plan ID")
    service_option_id: int = Field(..., description="Service option ID")
    is_default: bool = Field(True, description="Whether this option is applied by default")
    is_required: bool = Field(False, description="Whether this option is mandatory")


class PlanServiceOptionCreate(PlanServiceOptionBase):
    """Schema for creating plan service option"""
    pass


class PlanServiceOptionResponse(PlanServiceOptionBase):
    """Schema for plan service option response"""
    id: int
    created_at: datetime
    created_by: Optional[int] = None
    
    class Config:
        from_attributes = True


class PlanWithServiceOptions(BaseModel):
    """Schema for plan with its service options"""
    plan_id: int
    plan_name: str
    plan_code: str
    service_options: List[dict]  # Will contain service option details


class PlanServiceOptionsAssign(BaseModel):
    """Schema for assigning service options to plan"""
    plan_id: int = Field(..., description="Plan ID")
    service_option_ids: List[int] = Field(..., description="List of service option IDs")
    is_default: bool = Field(True, description="Whether these options are applied by default")
    is_required: bool = Field(False, description="Whether these options are mandatory")


class TransatelActivationOption(BaseModel):
    """Schema for Transatel activation options"""
    name: str = Field(..., description="Option name (service option code)")
    value: str = Field(..., description="Option value (usually 'on' or 'off')")


class TransatelActivationRequest(BaseModel):
    """Schema for Transatel SIM activation request"""
    ratePlan: str = Field(..., description="Rate plan for activation")
    externalReference: str = Field(..., description="External reference")
    group: str = Field(..., description="Group name")
    subscriberCountryOfResidence: str = Field(..., description="Country of residence")
    options: List[TransatelActivationOption] = Field(default_factory=list, description="Service options")
