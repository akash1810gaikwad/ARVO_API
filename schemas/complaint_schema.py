from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from datetime import datetime


# Complaint Type Schemas
class ComplaintTypeCreate(BaseModel):
    type_name: str = Field(..., min_length=1, max_length=100)
    type_code: str = Field(..., min_length=1, max_length=20)
    description: Optional[str] = None
    is_active: bool = True


class ComplaintTypeUpdate(BaseModel):
    type_name: Optional[str] = Field(None, min_length=1, max_length=100)
    type_code: Optional[str] = Field(None, min_length=1, max_length=20)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class ComplaintTypeResponse(BaseModel):
    id: int
    type_name: str
    type_code: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Complaint Sub Type Schemas
class ComplaintSubTypeCreate(BaseModel):
    complaint_type_id: int
    sub_type_name: str = Field(..., min_length=1, max_length=100)
    sub_type_code: str = Field(..., min_length=1, max_length=20)
    description: Optional[str] = None
    resolution_sla_hours: int = Field(default=24, ge=1, le=720)  # 1 hour to 30 days
    is_active: bool = True


class ComplaintSubTypeUpdate(BaseModel):
    sub_type_name: Optional[str] = Field(None, min_length=1, max_length=100)
    sub_type_code: Optional[str] = Field(None, min_length=1, max_length=20)
    description: Optional[str] = None
    resolution_sla_hours: Optional[int] = Field(None, ge=1, le=720)
    is_active: Optional[bool] = None


class ComplaintSubTypeResponse(BaseModel):
    id: int
    complaint_type_id: int
    sub_type_name: str
    sub_type_code: str
    description: Optional[str]
    resolution_sla_hours: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Complaint Master Schemas
class ComplaintCreate(BaseModel):
    complaint_type_id: int
    complaint_sub_type_id: int
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=10)
    priority: str = Field(default="MEDIUM", pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    source: str = Field(default="API", max_length=50)
    reference_number: Optional[str] = Field(None, max_length=100)
    tags: Optional[str] = None  # JSON string
    needs_attention: bool = Field(default=False, description="Flag complaint as needing immediate attention")

    @validator('contact_email')
    def validate_email(cls, v):
        if v and '@' not in v:
            raise ValueError('Invalid email format')
        return v


class ComplaintUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, min_length=10)
    priority: Optional[str] = Field(None, pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    status: Optional[str] = Field(None, pattern="^(OPEN|IN_PROGRESS|RESOLVED|CLOSED|ESCALATED|CANCELLED)$")
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    resolution_notes: Optional[str] = None
    tags: Optional[str] = None
    needs_attention: Optional[bool] = Field(None, description="Flag complaint as needing immediate attention")

    @validator('contact_email')
    def validate_email(cls, v):
        if v and '@' not in v:
            raise ValueError('Invalid email format')
        return v


class ComplaintAssign(BaseModel):
    assigned_to: int
    assignment_notes: Optional[str] = None


class ComplaintResolve(BaseModel):
    resolution_notes: str = Field(..., min_length=10)
    status: str = Field(default="RESOLVED", pattern="^(RESOLVED|CLOSED)$")


class ComplaintEscalate(BaseModel):
    escalated_to: int
    escalation_reason: str = Field(..., min_length=10)


class ComplaintResponse(BaseModel):
    id: int
    complaint_number: str
    customer_id: int
    subscriber_id: Optional[int]
    complaint_type_id: int
    complaint_sub_type_id: int
    title: str
    description: str
    priority: str
    status: str
    contact_email: Optional[str]
    contact_phone: Optional[str]
    resolution_notes: Optional[str]
    resolved_at: Optional[datetime]
    resolved_by: Optional[int]
    sla_due_date: Optional[datetime]
    is_sla_breached: bool
    needs_attention: Optional[bool] = False  # Optional with default to handle NULL values
    assigned_to: Optional[int]
    assigned_at: Optional[datetime]
    escalated_at: Optional[datetime]
    escalated_to: Optional[int]
    escalation_reason: Optional[str]
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime]
    source: str
    reference_number: Optional[str]
    tags: Optional[str]

    class Config:
        from_attributes = True


class ComplaintDetailResponse(ComplaintResponse):
    complaint_type: ComplaintTypeResponse
    complaint_sub_type: ComplaintSubTypeResponse
    comments_count: int = 0
    attachments_count: int = 0


# Comment Schemas
class ComplaintCommentCreate(BaseModel):
    comment_text: str = Field(..., min_length=1)
    comment_type: str
    is_internal: bool = True


class ComplaintCommentResponse(BaseModel):
    id: int
    complaint_id: int
    comment_text: str
    comment_type: str
    is_internal: bool
    created_by: int
    created_by_type: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Search and Filter Schemas
class ComplaintSearch(BaseModel):
    complaint_number: Optional[str] = None
    customer_id: Optional[int] = None
    subscriber_id: Optional[int] = None
    complaint_type_id: Optional[int] = None
    complaint_sub_type_id: Optional[int] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[int] = None
    is_sla_breached: Optional[bool] = None
    needs_attention: Optional[bool] = None
    created_from: Optional[datetime] = None
    created_to: Optional[datetime] = None
    source: Optional[str] = None


class ComplaintStatistics(BaseModel):
    total_complaints: int
    open_complaints: int
    in_progress_complaints: int
    resolved_complaints: int
    closed_complaints: int
    escalated_complaints: int
    sla_breached_complaints: int
    avg_resolution_time_hours: float
    complaints_by_type: Dict[str, int]
    complaints_by_priority: Dict[str, int]


class ComplaintListResponse(BaseModel):
    success: bool
    data: List[ComplaintResponse]
    total_count: int
    page: int
    limit: int
    has_more: bool