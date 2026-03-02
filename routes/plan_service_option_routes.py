from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List
from config.mysql_database import get_mysql_db
from schemas.service_option_schema import (
    PlanServiceOptionCreate,
    PlanServiceOptionResponse,
    PlanWithServiceOptions,
    PlanServiceOptionsAssign
)
from models.mysql_models import PlanServiceOption, ServiceOption, PlanMaster
from utils.logger import logger

router = APIRouter(prefix="/api/v1/plan-service-options", tags=["Plan Service Options"])


@router.get("/plan/{plan_id}/options", response_model=PlanWithServiceOptions)
def get_plan_service_options(
    plan_id: int,
    db: Session = Depends(get_mysql_db)
):
    """Get all service options for a specific plan"""
    try:
        # Get plan
        plan = db.query(PlanMaster).filter(PlanMaster.id == plan_id).first()
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Plan with ID {plan_id} not found"
            )
        
        # Get service options for this plan
        plan_options = db.query(
            PlanServiceOption,
            ServiceOption
        ).join(
            ServiceOption, PlanServiceOption.service_option_id == ServiceOption.id
        ).filter(
            PlanServiceOption.plan_id == plan_id,
            ServiceOption.is_active == True
        ).order_by(ServiceOption.category, ServiceOption.sort_order).all()
        
        service_options = []
        for plan_option, service_option in plan_options:
            service_options.append({
                "id": service_option.id,
                "option_code": service_option.option_code,
                "option_name": service_option.option_name,
                "description": service_option.description,
                "category": service_option.category,
                "is_default": plan_option.is_default,
                "is_required": plan_option.is_required,
                "sort_order": service_option.sort_order
            })
        
        return PlanWithServiceOptions(
            plan_id=plan.id,
            plan_name=plan.plan_name,
            plan_code=plan.plan_code,
            service_options=service_options
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting plan service options: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get plan service options: {str(e)}"
        )


@router.post("/", response_model=PlanServiceOptionResponse, status_code=status.HTTP_201_CREATED)
def create_plan_service_option(
    option_data: PlanServiceOptionCreate,
    db: Session = Depends(get_mysql_db)
):
    """Add a service option to a plan"""
    try:
        # Check if plan exists
        plan = db.query(PlanMaster).filter(PlanMaster.id == option_data.plan_id).first()
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Plan with ID {option_data.plan_id} not found"
            )
        
        # Check if service option exists
        service_option = db.query(ServiceOption).filter(
            ServiceOption.id == option_data.service_option_id
        ).first()
        if not service_option:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service option with ID {option_data.service_option_id} not found"
            )
        
        # Check if already exists
        existing = db.query(PlanServiceOption).filter(
            PlanServiceOption.plan_id == option_data.plan_id,
            PlanServiceOption.service_option_id == option_data.service_option_id
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This service option is already assigned to the plan"
            )
        
        # Create plan service option
        plan_option = PlanServiceOption(
            plan_id=option_data.plan_id,
            service_option_id=option_data.service_option_id,
            is_default=option_data.is_default,
            is_required=option_data.is_required
        )
        
        db.add(plan_option)
        db.commit()
        db.refresh(plan_option)
        
        logger.info(f"Service option {option_data.service_option_id} added to plan {option_data.plan_id}")
        
        return PlanServiceOptionResponse(
            id=plan_option.id,
            plan_id=plan_option.plan_id,
            service_option_id=plan_option.service_option_id,
            is_default=plan_option.is_default,
            is_required=plan_option.is_required,
            created_at=plan_option.created_at,
            created_by=plan_option.created_by
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating plan service option: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create plan service option: {str(e)}"
        )


@router.post("/assign-multiple", response_model=List[PlanServiceOptionResponse])
def assign_multiple_service_options(
    assign_data: PlanServiceOptionsAssign,
    db: Session = Depends(get_mysql_db)
):
    """Assign multiple service options to a plan at once"""
    try:
        # Check if plan exists
        plan = db.query(PlanMaster).filter(PlanMaster.id == assign_data.plan_id).first()
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Plan with ID {assign_data.plan_id} not found"
            )
        
        created_options = []
        
        for service_option_id in assign_data.service_option_ids:
            # Check if service option exists
            service_option = db.query(ServiceOption).filter(
                ServiceOption.id == service_option_id
            ).first()
            if not service_option:
                logger.warning(f"Service option {service_option_id} not found, skipping")
                continue
            
            # Check if already exists
            existing = db.query(PlanServiceOption).filter(
                PlanServiceOption.plan_id == assign_data.plan_id,
                PlanServiceOption.service_option_id == service_option_id
            ).first()
            
            if existing:
                logger.info(f"Service option {service_option_id} already assigned to plan {assign_data.plan_id}, skipping")
                continue
            
            # Create plan service option
            plan_option = PlanServiceOption(
                plan_id=assign_data.plan_id,
                service_option_id=service_option_id,
                is_default=assign_data.is_default,
                is_required=assign_data.is_required
            )
            
            db.add(plan_option)
            db.flush()
            
            created_options.append(PlanServiceOptionResponse(
                id=plan_option.id,
                plan_id=plan_option.plan_id,
                service_option_id=plan_option.service_option_id,
                is_default=plan_option.is_default,
                is_required=plan_option.is_required,
                created_at=plan_option.created_at,
                created_by=plan_option.created_by
            ))
        
        db.commit()
        
        logger.info(f"Assigned {len(created_options)} service options to plan {assign_data.plan_id}")
        
        return created_options
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning service options: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to assign service options: {str(e)}"
        )


@router.delete("/plan/{plan_id}/option/{service_option_id}")
def remove_service_option_from_plan(
    plan_id: int,
    service_option_id: int,
    db: Session = Depends(get_mysql_db)
):
    """Remove a service option from a plan"""
    try:
        plan_option = db.query(PlanServiceOption).filter(
            PlanServiceOption.plan_id == plan_id,
            PlanServiceOption.service_option_id == service_option_id
        ).first()
        
        if not plan_option:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service option not found for this plan"
            )
        
        db.delete(plan_option)
        db.commit()
        
        logger.info(f"Service option {service_option_id} removed from plan {plan_id}")
        
        return {
            "success": True,
            "message": "Service option removed from plan successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing service option from plan: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove service option: {str(e)}"
        )


@router.get("/", response_model=List[PlanServiceOptionResponse])
def get_all_plan_service_options(
    plan_id: int = None,
    service_option_id: int = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_mysql_db)
):
    """Get all plan-service option mappings with optional filters"""
    try:
        query = db.query(PlanServiceOption)
        
        if plan_id:
            query = query.filter(PlanServiceOption.plan_id == plan_id)
        
        if service_option_id:
            query = query.filter(PlanServiceOption.service_option_id == service_option_id)
        
        plan_options = query.offset(skip).limit(limit).all()
        
        return [
            PlanServiceOptionResponse(
                id=po.id,
                plan_id=po.plan_id,
                service_option_id=po.service_option_id,
                is_default=po.is_default,
                is_required=po.is_required,
                created_at=po.created_at,
                created_by=po.created_by
            )
            for po in plan_options
        ]
        
    except Exception as e:
        logger.error(f"Error getting plan service options: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get plan service options: {str(e)}"
        )
