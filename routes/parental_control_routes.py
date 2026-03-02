from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from config.mysql_database import get_mysql_db
from schemas.parental_control_schema import (
    ParentalControlResponse, ParentalControlUpdateRequest, 
    ParentalControlSyncResponse, ParentalControlSettings
)
from schemas.audit_schema import AuditLogCreate
from services.parental_control_service import parental_control_service
from services.audit_service import audit_service
from middleware.auth import get_current_user
from utils.logger import logger
from models.mysql_models import ParentalControl, Customer

router = APIRouter(prefix="/api/parental-controls", tags=["Parental Controls"])


@router.get("/child/{child_sim_card_id}", response_model=ParentalControlResponse)
async def get_parental_controls(
    child_sim_card_id: int,
    customer_id: int,
    plan_id: Optional[int] = None,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """
    Get parental control settings for a child SIM card in Transatel format.
    Returns custom settings if they exist, otherwise returns plan defaults from service_options.
    
    Parameters:
    - child_sim_card_id: Child SIM card ID
    - customer_id: Customer ID
    - plan_id: Optional plan ID to get service options from (if not provided, uses child's subscription plan)
    """
    try:
        settings = parental_control_service.get_settings(
            db, child_sim_card_id, customer_id, plan_id
        )
        
        if not settings:
            return JSONResponse(
                status_code=200,
                content={"message": "Child SIM card not found", "data": None}
            )
        
        return settings
    except Exception as e:
        logger.error(f"Error getting parental controls: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get parental controls: {str(e)}"
        )


@router.get("/customer/{customer_id}", response_model=List[ParentalControlResponse])
async def get_customer_parental_controls(
    customer_id: int,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """Get all parental control settings for a customer's children"""
    try:
        settings = parental_control_service.get_all_for_customer(db, customer_id)
        return settings
    except Exception as e:
        logger.error(f"Error getting customer parental controls: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get parental controls: {str(e)}"
        )


@router.put("/child/{child_sim_card_id}", response_model=ParentalControlSyncResponse)
async def update_parental_controls(
    request: Request,
    child_sim_card_id: int,
    customer_id: int,
    settings: ParentalControlSettings,
    sync_with_transatel: bool = True,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """
    Update parental control settings using Transatel parameter format.
    Optionally syncs with Transatel API.
    
    Note: Parents must wait 30 minutes between modifications for the same child.
    """
    try:
        # Check if 30 minutes have passed since last modification
        existing_control = db.query(ParentalControl).filter(
            ParentalControl.child_sim_card_id == child_sim_card_id,
            ParentalControl.customer_id == customer_id
        ).first()
        
        if existing_control and existing_control.last_modified_at:
            time_since_last_mod = datetime.utcnow() - existing_control.last_modified_at
            cooldown_period = timedelta(minutes=30)
            
            if time_since_last_mod < cooldown_period:
                time_remaining = cooldown_period - time_since_last_mod
                minutes_remaining = int(time_remaining.total_seconds() / 60)
                seconds_remaining = int(time_remaining.total_seconds() % 60)
                
                raise HTTPException(
                    status_code=429,
                    detail={
                        "success": False,
                        "message": f"Please wait {minutes_remaining} minutes and {seconds_remaining} seconds before making another change",
                        "error": "COOLDOWN_ACTIVE",
                        "time_remaining_seconds": int(time_remaining.total_seconds()),
                        "last_modified_at": existing_control.last_modified_at.isoformat()
                    }
                )
        
        # Convert params to list of dicts
        params = [p.model_dump() for p in settings.params]
        
        # Save settings to database
        control = parental_control_service.update_settings(
            db, child_sim_card_id, customer_id, params
        )
        
        # Update last_modified_at timestamp
        control.last_modified_at = datetime.utcnow()
        db.commit()
        
        # Sync with Transatel if requested
        if sync_with_transatel:
            sync_result = parental_control_service.sync_with_transatel(
                db, child_sim_card_id, params
            )
        else:
            sync_result = {
                "success": True,
                "message": "Settings saved locally without Transatel sync",
                "params_sent": params
            }
        
        # Create audit log
        await audit_service.create_audit_log(AuditLogCreate(
            user_id=customer_id,
            action="UPDATE",
            resource="ParentalControl",
            resource_id=str(control.id),
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            changes={"params": params},
            metadata={
                "child_sim_card_id": child_sim_card_id,
                "synced_with_transatel": sync_result.get("success", False)
            }
        ))
        
        return sync_result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating parental controls: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update parental controls: {str(e)}"
        )


@router.post("/sync", response_model=ParentalControlSyncResponse)
async def sync_parental_controls(
    request: Request,
    update_request: ParentalControlUpdateRequest,
    customer_id: int,
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """
    Manually sync parental control settings with Transatel.
    Useful for re-syncing after network issues.
    """
    try:
        print('heree')
        # Convert params to list of dicts
        params = [p.model_dump() for p in update_request.params]
        
        sync_result = parental_control_service.sync_with_transatel(
            db, update_request.child_sim_card_id, params
        )
        
        # Create audit log
        await audit_service.create_audit_log(AuditLogCreate(
            user_id=customer_id,
            action="SYNC",
            resource="ParentalControl",
            resource_id=str(update_request.child_sim_card_id),
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            metadata={
                "sync_success": sync_result.get("success", False),
                "params": params
            }
        ))
        
        return sync_result
    except Exception as e:
        logger.error(f"Error syncing parental controls: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync parental controls: {str(e)}"
        )
