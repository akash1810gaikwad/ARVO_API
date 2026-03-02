from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class AuditLogCreate(BaseModel):
    user_id: Optional[int] = None
    action: str = Field(..., description="Action performed (CREATE, UPDATE, DELETE, READ)")
    resource: str = Field(..., description="Resource type (User, Post, etc.)")
    resource_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    changes: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class AuditLogResponse(AuditLogCreate):
    id: str
    timestamp: datetime
    
    class Config:
        from_attributes = True
