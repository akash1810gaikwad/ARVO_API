from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from config.mysql_database import get_mysql_db
from schemas.service_option_schema import ServiceOptionCreate, ServiceOptionUpdate, ServiceOptionResponse
from schemas.audit_schema import AuditLogCreate
from services.service_option_service import service_option_service
from services.audit_service import audit_service
from middleware.auth import get_current_user
from models.mysql_models import Customer
from utils.logger import logger

router = APIRouter(prefix="/api/v1/service-options", tags=["Service Options"])


@router.post("/", response_model=ServiceOptionResponse, status_code=status.HTTP_201_CREATED)
async def create_service_option(
    request: Request,
    option_data: ServiceOptionCreate,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """Create a new service option"""
    try:
        option = service_option_service.create_service_option(db, option_data)
        
        await audit_service.create_audit_log(AuditLogCreate(
            action="CREATE",
            resource="ServiceOption",
            resource_id=str(option.id),
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent")
        ))
        
        return option
    except Exception as e:
        logger.error(f"Error creating service option: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[ServiceOptionResponse])
def get_service_options(
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None,
    active_only: bool = False,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """Get all service options"""
    return service_option_service.get_service_options(db, skip=skip, limit=limit, category=category, active_only=active_only)


@router.get("/{option_id}", response_model=ServiceOptionResponse)
def get_service_option(option_id: int, db: Session = Depends(get_mysql_db), current_user: Customer = Depends(get_current_user)):
    """Get service option by ID"""
    option = service_option_service.get_service_option_by_id(db, option_id)
    if not option:
        return JSONResponse(
            status_code=200,
            content={"message": "Service option not found", "data": None}
        )
    return option


@router.put("/{option_id}", response_model=ServiceOptionResponse)
async def update_service_option(
    request: Request,
    option_id: int,
    option_data: ServiceOptionUpdate,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """Update service option"""
    option = service_option_service.update_service_option(db, option_id, option_data)
    if not option:
        return JSONResponse(
            status_code=200,
            content={"message": "Service option not found", "data": None}
        )
    
    await audit_service.create_audit_log(AuditLogCreate(
        action="UPDATE",
        resource="ServiceOption",
        resource_id=str(option_id),
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        changes=option_data.model_dump(exclude_unset=True)
    ))
    
    return option


@router.delete("/{option_id}")
async def delete_service_option(
    request: Request,
    option_id: int,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """Delete service option"""
    success = service_option_service.delete_service_option(db, option_id)
    if not success:
        return JSONResponse(
            status_code=200,
            content={"message": "Service option not found", "success": False}
        )
    
    await audit_service.create_audit_log(AuditLogCreate(
        action="DELETE",
        resource="ServiceOption",
        resource_id=str(option_id),
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    ))
    
    return JSONResponse(
        status_code=200,
        content={"message": "Service option deleted successfully", "success": True}
    )
