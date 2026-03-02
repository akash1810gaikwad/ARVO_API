from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any, Dict, Union
from datetime import datetime
from enum import Enum
import json


class APIStatus(str, Enum):
    """API call status"""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class TransatelAPILogBase(BaseModel):
    """Base schema for Transatel API log"""
    api_name: str = Field(..., max_length=100, description="Name of the API")
    endpoint: str = Field(..., max_length=255, description="API endpoint URL")
    request_payload: Optional[Union[Dict[str, Any], str]] = Field(None, description="Request payload sent")
    response_payload: Optional[Union[Dict[str, Any], str]] = Field(None, description="Response received")
    status: APIStatus = Field(..., description="API call status")
    http_status_code: Optional[int] = Field(None, description="HTTP status code")
    error_message: Optional[str] = Field(None, description="Error message if failed")


class TransatelAPILogCreate(TransatelAPILogBase):
    """Schema for creating a new API log"""
    pass


class TransatelAPILogResponse(TransatelAPILogBase):
    """Schema for API log response"""
    id: int
    created_at: datetime
    
    @field_validator('request_payload', 'response_payload', mode='before')
    @classmethod
    def parse_json_string(cls, v):
        """Parse JSON string to dict if needed"""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, ValueError):
                return v
        return v
    
    class Config:
        from_attributes = True


class TransatelAPILogListResponse(BaseModel):
    """Schema for paginated API log list"""
    success: bool = True
    message: str = "API logs retrieved successfully"
    data: list[TransatelAPILogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class TransatelAPILogStatsResponse(BaseModel):
    """Schema for API log statistics"""
    success: bool = True
    message: str = "API log statistics retrieved successfully"
    data: Dict[str, Any]


class TransatelAPILogSearchFilters(BaseModel):
    """Schema for search filters"""
    api_name: Optional[str] = None
    endpoint: Optional[str] = None
    status: Optional[APIStatus] = None
    http_status_code: Optional[int] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
