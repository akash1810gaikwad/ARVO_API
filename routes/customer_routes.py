from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from config.mysql_database import get_mysql_db
from schemas.customer_schema import (
    CustomerCreate, CustomerUpdate, CustomerResponse,
    GoogleAuthRequest, GoogleAuthResponse,
    EmailVerificationRequest, EmailVerificationResponse,
    PasswordLoginRequest, PasswordLoginResponse
)
from schemas.email_template_schema import CustomerChildrenSimsResponse
from schemas.audit_schema import AuditLogCreate
from services.customer_service import customer_service
from services.auth_service import auth_service
from services.audit_service import audit_service
from middleware.auth import get_current_user
from models.mysql_models import Customer
from utils.logger import logger

router = APIRouter(prefix="/api/customers", tags=["Customers"])


@router.post("/auth/google", response_model=GoogleAuthResponse)
async def google_auth(
    request: Request,
    auth_data: GoogleAuthRequest,
    db: Session = Depends(get_mysql_db)
):
    """Authenticate or register with Google OAuth"""
    try:
        logger.info(f"Received Google auth request from {request.client.host}")
        logger.info(f"Token received: {auth_data.token[:50]}..." if len(auth_data.token) > 50 else f"Token: {auth_data.token}")
        
        result = auth_service.authenticate_with_google(db, auth_data.token)
        
        if not result:
            logger.warning("Google authentication failed - invalid token or verification error")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google token or authentication failed"
            )
        
        customer, access_token = result
        logger.info(f"Google auth successful for customer: {customer.email}")
        
        # Create audit log
        await audit_service.create_audit_log(AuditLogCreate(
            user_id=customer.id,
            action="LOGIN",
            resource="Customer",
            resource_id=str(customer.id),
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            metadata={"oauth_provider": "google"}
        ))
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "customer": customer
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in Google auth endpoint: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")


@router.post("/auth/login", response_model=PasswordLoginResponse)
async def password_login(
    request: Request,
    login_data: PasswordLoginRequest,
    db: Session = Depends(get_mysql_db)
):
    """Authenticate with email and password"""
    try:
        logger.info(f"Password login attempt for: {login_data.email}")
        
        result = auth_service.authenticate_with_password(db, login_data.email, login_data.password)
        
        if not result:
            logger.warning(f"Password login failed for: {login_data.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        customer, access_token = result
        logger.info(f"Password login successful for: {customer.email}")
        
        # Create audit log
        await audit_service.create_audit_log(AuditLogCreate(
            user_id=customer.id,
            action="LOGIN",
            resource="Customer",
            resource_id=str(customer.id),
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            metadata={"auth_method": "password"}
        ))
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "customer": customer
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in password login endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Login failed")


@router.post("/", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    request: Request,
    customer_data: CustomerCreate,
    db: Session = Depends(get_mysql_db)
):
    """Create a new customer (manual registration)"""
    try:
        # Check if customer already exists
        existing_customer = customer_service.get_customer_by_email(db, customer_data.email)
        if existing_customer:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Validate password is provided for manual registration
        if not customer_data.password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password is required for registration"
            )
        
        # Create customer
        customer = customer_service.create_customer(db, customer_data)
        
        # Create audit log
        await audit_service.create_audit_log(AuditLogCreate(
            user_id=customer.id,
            action="CREATE",
            resource="Customer",
            resource_id=str(customer.id),
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent")
        ))
        
        # STEP 1: Create user journey (Registration completed)
        try:
            from repositories.user_journey_repo import UserJourneyRepository
            from schemas.user_journey_schema import UserJourneyCreate
            import json
            
            journey_data = UserJourneyCreate(
                customer_id=customer.id,
                customer_email=customer.email,
                registration_payload=json.dumps({
                    "source": "manual_registration",
                    "ip_address": request.client.host,
                    "user_agent": request.headers.get("user-agent")
                })
            )
            UserJourneyRepository.create_journey(db, journey_data)
            logger.info(f"User journey created for customer {customer.id}")
        except Exception as journey_error:
            logger.error(f"Failed to create user journey: {journey_error}")
            # Don't fail registration if journey tracking fails
        
        return customer
    except ValueError as ve:
        # Handle password hashing errors
        logger.error(f"Validation error creating customer: {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating customer: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create customer: {str(e)}")


@router.get("/me", response_model=CustomerResponse)
def get_current_customer(
    current_user: Customer = Depends(get_current_user)
):
    """Get the currently authenticated user's profile"""
    return current_user


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """Get customer by ID (requires authentication)"""
    customer = customer_service.get_customer_by_id(db, customer_id)
    if not customer:
        return JSONResponse(
            status_code=200,
            content={"message": "Customer not found", "data": None}
        )
    return customer


@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    request: Request,
    customer_id: int,
    customer_data: CustomerUpdate,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """Update customer"""
    customer = customer_service.update_customer(db, customer_id, customer_data)
    if not customer:
        return JSONResponse(
            status_code=200,
            content={"message": "Customer not found", "data": None}
        )
    
    # Create audit log
    await audit_service.create_audit_log(AuditLogCreate(
        user_id=customer_id,
        action="UPDATE",
        resource="Customer",
        resource_id=str(customer_id),
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        changes=customer_data.model_dump(exclude_unset=True)
    ))
    
    return customer


@router.post("/verify-email", response_model=EmailVerificationResponse)
async def verify_email(
    request: Request,
    verification_data: EmailVerificationRequest,
    db: Session = Depends(get_mysql_db)
):
    """Verify customer email"""
    customer = customer_service.verify_email(db, verification_data.token)
    
    if not customer:
        return JSONResponse(
            status_code=200,
            content={
                "message": "Invalid or expired verification token",
                "is_verified": False
            }
        )
    
    # Create audit log
    await audit_service.create_audit_log(AuditLogCreate(
        user_id=customer.id,
        action="EMAIL_VERIFIED",
        resource="Customer",
        resource_id=str(customer.id),
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    ))
    
    return {
        "message": "Email verified successfully",
        "is_verified": True
    }


@router.delete("/{customer_id}")
async def delete_customer(
    request: Request,
    customer_id: int,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """Delete customer (soft delete)"""
    success = customer_service.delete_customer(db, customer_id)
    if not success:
        return JSONResponse(
            status_code=200,
            content={"message": "Customer not found", "success": False}
        )
    
    # Create audit log
    await audit_service.create_audit_log(AuditLogCreate(
        user_id=customer_id,
        action="DELETE",
        resource="Customer",
        resource_id=str(customer_id),
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    ))
    
    return JSONResponse(
        status_code=200,
        content={"message": "Customer deleted successfully", "success": True}
    )


@router.post("/test-welcome-email")
async def test_welcome_email(email: str, name: str):
    """Test endpoint to manually send welcome email"""
    from services.email_service import send_welcome_email
    try:
        result = send_welcome_email(email, name)
        return {
            "success": result,
            "message": "Email sent successfully" if result else "Email failed to send"
        }
    except Exception as e:
        logger.error(f"Test email error: {str(e)}")
        return {
            "success": False,
            "message": f"Error: {str(e)}"
        }


@router.get("/{customer_id}/children-sims", response_model=CustomerChildrenSimsResponse)
async def get_customer_children_sims(
    customer_id: int,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """Get all children SIM card details for a customer"""
    try:
        result = customer_service.get_customer_children_sims(db, customer_id)
        
        if not result:
            return JSONResponse(
                status_code=200,
                content={"message": "Customer not found", "data": None}
            )
        
        return result
    except Exception as e:
        logger.error(f"Error getting customer children SIMs: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get children SIM details: {str(e)}"
        )
