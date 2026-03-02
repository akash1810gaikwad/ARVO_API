from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List
from config.mysql_database import get_mysql_db
from schemas.plan_schema import PlanCreate, PlanUpdate, PlanResponse, PlanServiceOptionResponse
from schemas.audit_schema import AuditLogCreate
from services.plan_service import plan_service
from services.audit_service import audit_service
from middleware.auth import get_current_user
from models.mysql_models import Customer
from utils.logger import logger

router = APIRouter(prefix="/api/plans", tags=["Plans"])


@router.post("/", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
async def create_plan(
    request: Request,
    plan_data: PlanCreate,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """Create a new subscription plan"""
    try:
        plan = plan_service.create_plan(db, plan_data)
        
        await audit_service.create_audit_log(AuditLogCreate(
            action="CREATE",
            resource="Plan",
            resource_id=str(plan.id),
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent")
        ))
        
        return plan
    except Exception as e:
        logger.error(f"Error creating plan: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[PlanResponse])
def get_plans(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
    db: Session = Depends(get_mysql_db)
):
    """Get all plans"""
    plans = plan_service.get_plans(db, skip=skip, limit=limit, active_only=active_only)
    
    result = []
    for plan in plans:
        # Extract feature names
        features = [pso.service_option.option_name for pso in plan.plan_service_options]
        
        plan_dict = {
            "id": plan.id,
            "plan_code": plan.plan_code,
            "plan_name": plan.plan_name,
            "description": plan.description,
            "tagline": plan.tagline,
            "plan_type": plan.plan_type.value,
            "duration_days": plan.duration_days,
            "monthly_price": plan.monthly_price,
            "annual_price": plan.annual_price,
            "currency": plan.currency,
            "data_allowance": plan.data_allowance,
            "is_popular": plan.is_popular,
            "gradient": plan.gradient,
            "icon_bg": plan.icon_bg,
            "is_active": plan.is_active,
            "sort_order": plan.sort_order,
            "created_at": plan.created_at,
            "updated_at": plan.updated_at,
            "features": features,
            "service_options": []
        }
        
        for pso in plan.plan_service_options:
            plan_dict["service_options"].append({
                "id": pso.id,
                "service_option_id": pso.service_option_id,
                "option_code": pso.service_option.option_code,
                "option_name": pso.service_option.option_name,
                "category": pso.service_option.category.value,
                "is_default": pso.is_default,
                "is_required": pso.is_required
            })
        
        result.append(plan_dict)
    
    return result



@router.get("/{plan_id}", response_model=PlanResponse)
def get_plan(plan_id: int, db: Session = Depends(get_mysql_db)):
    """Get plan by ID"""
    plan = plan_service.get_plan_by_id(db, plan_id)
    if not plan:
        return JSONResponse(
            status_code=200,
            content={"message": "Plan not found", "data": None}
        )
    
    # Extract feature names
    features = [pso.service_option.option_name for pso in plan.plan_service_options]
    
    plan_dict = {
        "id": plan.id,
        "plan_code": plan.plan_code,
        "plan_name": plan.plan_name,
        "description": plan.description,
        "tagline": plan.tagline,
        "plan_type": plan.plan_type.value,
        "duration_days": plan.duration_days,
        "monthly_price": plan.monthly_price,
        "annual_price": plan.annual_price,
        "currency": plan.currency,
        "data_allowance": plan.data_allowance,
        "is_popular": plan.is_popular,
        "gradient": plan.gradient,
        "icon_bg": plan.icon_bg,
        "is_active": plan.is_active,
        "sort_order": plan.sort_order,
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
        "features": features,
        "service_options": []
    }
    
    for pso in plan.plan_service_options:
        plan_dict["service_options"].append({
            "id": pso.id,
            "service_option_id": pso.service_option_id,
            "option_code": pso.service_option.option_code,
            "option_name": pso.service_option.option_name,
            "category": pso.service_option.category.value,
            "is_default": pso.is_default,
            "is_required": pso.is_required
        })
    
    return plan_dict


@router.put("/{plan_id}", response_model=PlanResponse)
async def update_plan(
    request: Request,
    plan_id: int,
    plan_data: PlanUpdate,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """Update plan"""
    plan = plan_service.update_plan(db, plan_id, plan_data)
    if not plan:
        return JSONResponse(
            status_code=200,
            content={"message": "Plan not found", "data": None}
        )
    
    await audit_service.create_audit_log(AuditLogCreate(
        action="UPDATE",
        resource="Plan",
        resource_id=str(plan_id),
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        changes=plan_data.model_dump(exclude_unset=True)
    ))
    
    return plan


@router.delete("/{plan_id}")
async def delete_plan(
    request: Request,
    plan_id: int,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """Delete plan"""
    success = plan_service.delete_plan(db, plan_id)
    if not success:
        return JSONResponse(
            status_code=200,
            content={"message": "Plan not found", "success": False}
        )
    
    await audit_service.create_audit_log(AuditLogCreate(
        action="DELETE",
        resource="Plan",
        resource_id=str(plan_id),
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    ))
    
    return JSONResponse(
        status_code=200,
        content={"message": "Plan deleted successfully", "success": True}
    )
