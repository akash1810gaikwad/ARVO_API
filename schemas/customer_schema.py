from pydantic import BaseModel, EmailStr, Field
from typing import Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    pass


class CustomerBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    phone_number: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = None
    postcode: Optional[str] = Field(None, max_length=20)
    city: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    number_of_children: Optional[int] = Field(None, ge=0, description="Number of children")


class CustomerCreate(CustomerBase):
    password: Optional[str] = Field(None, min_length=6, max_length=72, description="Password for manual registration (max 72 characters)")


class CustomerUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    phone_number: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = None
    postcode: Optional[str] = Field(None, max_length=20)
    city: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    number_of_children: Optional[int] = Field(None, ge=0, description="Number of children")


class CustomerResponse(BaseModel):
    id: int
    email: str
    full_name: str
    phone_number: Optional[str] = None
    address: Optional[str] = None
    postcode: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    number_of_children: Optional[int] = None
    google_id: Optional[str] = None
    oauth_provider: Optional[str] = None
    profile_picture: Optional[str] = None
    is_email_verified: bool
    email_verified_at: Optional[datetime] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class GoogleAuthRequest(BaseModel):
    token: str = Field(..., description="Google OAuth token")


class GoogleAuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    customer: CustomerResponse


class EmailVerificationRequest(BaseModel):
    token: str = Field(..., description="Email verification token")


class EmailVerificationResponse(BaseModel):
    message: str
    is_verified: bool


class PasswordLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=72)


class PasswordLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    customer: CustomerResponse
