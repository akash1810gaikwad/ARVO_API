from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class EmailTemplateBase(BaseModel):
    template_key: str = Field(..., max_length=100, description="Unique template identifier")
    template_name: str = Field(..., max_length=255, description="Human-readable template name")
    subject: str = Field(..., max_length=500, description="Email subject line")
    body_html: str = Field(..., description="HTML email body")
    body_text: Optional[str] = Field(None, description="Plain text fallback")
    variables: Optional[str] = Field(None, description="JSON string of available variables")
    description: Optional[str] = Field(None, description="Template description")
    is_active: bool = Field(True, description="Whether template is active")


class EmailTemplateCreate(EmailTemplateBase):
    pass


class EmailTemplateUpdate(BaseModel):
    template_name: Optional[str] = Field(None, max_length=255)
    subject: Optional[str] = Field(None, max_length=500)
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    variables: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class EmailTemplateResponse(BaseModel):
    id: int
    template_key: str
    template_name: str
    subject: str
    body_html: str
    body_text: Optional[str] = None
    variables: Optional[str] = None
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class EmailTemplatePreviewRequest(BaseModel):
    template_key: str = Field(..., description="Template key to preview")
    variables: dict = Field(..., description="Variables to substitute in template")


class EmailTemplatePreviewResponse(BaseModel):
    subject: str
    body_html: str
    body_text: Optional[str] = None


class ChildSimCardDetail(BaseModel):
    """Child SIM card details"""
    id: int
    child_name: str
    child_age: int
    child_order: int
    sim_number: Optional[str] = None
    iccid: Optional[str] = None
    msisdn: Optional[str] = None
    activation_code: Optional[str] = None
    sim_type: Optional[str] = None
    is_active: bool
    activation_date: Optional[datetime] = None
    subscription_id: int
    subscription_number: Optional[str] = None
    plan_name: Optional[str] = None
    subscription_status: Optional[str] = None
    subscription_start_date: Optional[datetime] = None
    subscription_end_date: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class CustomerChildrenSimsResponse(BaseModel):
    """Response with all children SIM cards for a customer"""
    customer_id: int
    customer_name: str
    customer_email: str
    total_children: int
    active_sims: int
    inactive_sims: int
    children_sims: List[ChildSimCardDetail]
