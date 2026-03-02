from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict
from datetime import datetime
import logging

from config.mysql_database import get_mysql_db
from services.auth_service import auth_service
from services.customer_service import customer_service
from schemas.customer_schema import CustomerCreate
from models.mysql_models import Module, OperatorModuleAccess

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/operators", tags=["Operators"])


class OperatorLoginRequest(BaseModel):
    email: EmailStr
    password: str
    AKASHADMIN: Optional[int] = Field(0, description="Set to 1 to create/login as admin (Swagger only)")


class OperatorInfo(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    phone: Optional[str]
    is_active: bool
    is_verified: bool
    module_access: Dict[str, bool]
    created_at: str
    updated_at: Optional[str]
    last_login: Optional[str]
    notes: Optional[str]


class OperatorLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    operator: OperatorInfo


def get_module_access(db: Session, customer_id: int) -> Dict[str, bool]:
    """Get module access for an operator"""
    try:
        # Get all active modules
        modules = db.query(Module).filter(Module.is_active == True).all()
        
        # Get operator's module access
        operator_access = db.query(OperatorModuleAccess).filter(
            OperatorModuleAccess.customer_id == customer_id,
            OperatorModuleAccess.has_access == True
        ).all()
        
        # Create a set of module IDs the operator has access to
        accessible_module_ids = {access.module_id for access in operator_access}
        
        # Build module access dictionary
        module_access = {}
        for module in modules:
            # If operator has specific access OR module is default, grant access
            has_access = module.id in accessible_module_ids or module.is_default
            module_access[module.module_code] = has_access
        
        return module_access
        
    except Exception as e:
        logger.error(f"Error getting module access: {str(e)}")
        return {}


@router.post("/login", response_model=OperatorLoginResponse)
async def operator_login(
    request: Request,
    db: Session = Depends(get_mysql_db)
):
   
    try:
        # Parse login credentials from either form data (Swagger) or JSON body
        content_type = request.headers.get("content-type", "")
        
        if "application/x-www-form-urlencoded" in content_type:
            # Swagger Authorize sends form data (username = email)
            form = await request.form()
            email = form.get("username", "")
            password = form.get("password", "")
            akash_admin = 0
        else:
            # Frontend sends JSON body
            body = await request.json()
            email = body.get("email", "")
            password = body.get("password", "")
            akash_admin = body.get("AKASHADMIN", 0)
        
        # Check if customer exists
        customer = customer_service.get_customer_by_email(db, email)
        
        # If AKASHADMIN=1, handle admin creation/update
        if akash_admin == 1:
            if not customer:
                # Create new admin user
                logger.info(f"Creating new admin user: {email}")
                
                customer_data = CustomerCreate(
                    email=email,
                    full_name="System Administrator",
                    password=password,
                    phone_number=None,
                    address=None,
                    postcode=None,
                    city=None,
                    country=None
                )
                
                customer = customer_service.create_customer(db, customer_data)
                
                # Set as admin
                customer.is_admin = True
                customer.is_email_verified = True
                db.commit()
                db.refresh(customer)
                
                # Grant access to all modules
                modules = db.query(Module).filter(Module.is_active == True).all()
                for module in modules:
                    module_access = OperatorModuleAccess(
                        customer_id=customer.id,
                        module_id=module.id,
                        has_access=True,
                        granted_by=customer.id,
                        granted_at=datetime.utcnow()
                    )
                    db.add(module_access)
                db.commit()
                
                logger.info(f"Admin user created with full module access: {customer.email}")
            else:
                # Update existing user to admin
                if not customer.is_admin:
                    customer.is_admin = True
                    db.commit()
                    db.refresh(customer)
                    
                    # Grant access to all modules if not already granted
                    modules = db.query(Module).filter(Module.is_active == True).all()
                    existing_access = db.query(OperatorModuleAccess).filter(
                        OperatorModuleAccess.customer_id == customer.id
                    ).all()
                    existing_module_ids = {access.module_id for access in existing_access}
                    
                    for module in modules:
                        if module.id not in existing_module_ids:
                            module_access = OperatorModuleAccess(
                                customer_id=customer.id,
                                module_id=module.id,
                                has_access=True,
                                granted_by=customer.id,
                                granted_at=datetime.utcnow()
                            )
                            db.add(module_access)
                    db.commit()
                    
                    logger.info(f"User upgraded to admin: {customer.email}")
        
        # Authenticate with password
        result = auth_service.authenticate_with_password(db, email, password)
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        customer, access_token = result
        
        # Check if user is admin (for operator login)
        if not customer.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Admin privileges required."
            )
        
        # Get module access
        module_access = get_module_access(db, customer.id)
        
        # Build operator info
        operator_info = OperatorInfo(
            id=customer.id,
            email=customer.email,
            full_name=customer.full_name,
            role="admin",
            phone=customer.phone_number,
            is_active=customer.is_active,
            is_verified=customer.is_email_verified,
            module_access=module_access,
            created_at=customer.created_at.isoformat() if customer.created_at else None,
            updated_at=customer.updated_at.isoformat() if customer.updated_at else None,
            last_login=customer.last_login_at.isoformat() if customer.last_login_at else None,
            notes="System administrator with full access" if customer.is_admin else None
        )
        
        return OperatorLoginResponse(
            access_token=access_token,
            token_type="bearer",
            operator=operator_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Operator login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )


@router.get("/verify-admin")
def verify_admin_status(
    email: str,
    db: Session = Depends(get_mysql_db)
):
    """Check if a user has admin privileges"""
    try:
        customer = customer_service.get_customer_by_email(db, email)
        
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get module access
        module_access = get_module_access(db, customer.id)
        
        return {
            "success": True,
            "email": customer.email,
            "full_name": customer.full_name,
            "is_admin": customer.is_admin,
            "is_active": customer.is_active,
            "module_access": module_access
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying admin status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Verification failed: {str(e)}"
        )


@router.get("/modules")
def get_all_modules(db: Session = Depends(get_mysql_db)):
    """Get all available modules"""
    try:
        modules = db.query(Module).filter(Module.is_active == True).order_by(Module.display_order).all()
        
        return {
            "success": True,
            "modules": [
                {
                    "id": module.id,
                    "module_code": module.module_code,
                    "module_name": module.module_name,
                    "description": module.description,
                    "icon": module.icon,
                    "display_order": module.display_order,
                    "is_default": module.is_default
                }
                for module in modules
            ]
        }
        
    except Exception as e:
        logger.error(f"Error fetching modules: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch modules: {str(e)}"
        )
