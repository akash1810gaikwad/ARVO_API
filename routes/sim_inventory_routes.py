from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from datetime import datetime
import logging

from config.mysql_database import get_mysql_db
from models.mysql_models import SimInventory, Customer
from middleware.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/sim-inventory", tags=["SIM Inventory"])


class UpdateSimStatusRequest(BaseModel):
    status: str = "AVAILABLE"  # Default to AVAILABLE
    assigned_to_child_sim_id: Optional[int] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "AVAILABLE",
                "assigned_to_child_sim_id": None
            }
        }


@router.get("/search-sims")
def search_sims(
    q: Optional[str] = Query(None, description="Search query - searches in both ICCID and MSISDN (partial match)"),
    status: Optional[str] = Query(None, description="Filter by status"),
    sim_type: Optional[str] = Query(None, description="Filter by SIM type (eSIM or pSIM)"),
    limit: int = Query(50, description="Maximum number of results to return"),
    db: Session = Depends(get_mysql_db),
    # current_user: Customer = Depends(get_current_user)
):
    """
    Search for SIMs by ICCID or MSISDN using a single search query.
    The query parameter 'q' searches in both ICCID and MSISDN fields.
    Supports partial matching.
    """
    try:
        query = db.query(SimInventory)
        
        # Search in both ICCID and MSISDN (partial match)
        if q:
            from sqlalchemy import or_
            query = query.filter(
                or_(
                    SimInventory.iccid.like(f"%{q}%"),
                    SimInventory.msisdn.like(f"%{q}%")
                )
            )
        
        # Filter by status
        if status:
            query = query.filter(SimInventory.status == status)
        
        # Filter by SIM type
        if sim_type:
            query = query.filter(SimInventory.sim_type == sim_type)
        
        # Order by creation date (newest first) and limit results
        query = query.order_by(SimInventory.created_at.desc()).limit(limit)
        
        sims = query.all()
        
        # Convert to list with all relevant fields
        sim_list = []
        for sim in sims:
            sim_dict = {
                "id": sim.id,
                "sim_number": sim.sim_number,
                "iccid": sim.iccid,
                "msisdn": sim.msisdn,
                "activation_code": sim.activation_code,
                "status": sim.status,
                "sim_type": sim.sim_type,
                "supplier": sim.supplier,
                "batch_number": sim.batch_number,
                "assigned_to_child_sim_id": sim.assigned_to_child_sim_id,
                "assigned_at": sim.assigned_at.isoformat() if sim.assigned_at else None,
                "created_at": sim.created_at.isoformat() if sim.created_at else None
            }
            sim_list.append(sim_dict)
        
        return {
            "success": True,
            "count": len(sim_list),
            "data": sim_list
        }
        
    except Exception as e:
        logger.error(f"Error searching SIMs: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to search SIMs",
                "error": str(e)
            }
        )


@router.get("/available/full")
def get_available_sims(
    sim_type: Optional[str] = Query(None, description="Filter by SIM type (eSIM or pSIM)"),
    supplier: Optional[str] = Query(None, description="Filter by supplier"),
    db: Session = Depends(get_mysql_db),
    # current_user: Customer = Depends(get_current_user)
):
    """
    Get all available (unallocated) SIM cards from inventory.
    Returns SIMs where status = 'AVAILABLE' and not assigned to any child.
    """
    try:
        # Build query for available SIMs
        query = db.query(SimInventory).filter(
            SimInventory.status == "AVAILABLE",
            SimInventory.assigned_to_child_sim_id.is_(None)
        )
        
        # Add filters
        if sim_type:
            query = query.filter(SimInventory.sim_type == sim_type)
        
        if supplier:
            query = query.filter(SimInventory.supplier == supplier)
        
        # Order by creation date (newest first)
        query = query.order_by(SimInventory.created_at.desc())
        
        # Get all results
        sims = query.all()
        
        # Convert to simple list with only essential fields
        sim_list = []
        for sim in sims:
            sim_dict = {
                "iccid": sim.iccid,
                "msisdn": sim.msisdn,
                "activation_code": sim.activation_code
            }
            sim_list.append(sim_dict)
        
        return sim_list
        
    except Exception as e:
        logger.error(f"Error fetching available SIMs: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to fetch available SIMs",
                "error": str(e)
            }
        )
        # Available SIMs
        available_sims = db.query(func.count(SimInventory.id)).filter(
            SimInventory.status == "AVAILABLE",
            SimInventory.assigned_to_child_sim_id.is_(None)
        ).scalar()
        
        # Assigned SIMs
        assigned_sims = db.query(func.count(SimInventory.id)).filter(
            SimInventory.status == "ASSIGNED"
        ).scalar()
        
        # By SIM type
        esim_count = db.query(func.count(SimInventory.id)).filter(
            SimInventory.sim_type == "eSIM"
        ).scalar()
        
        psim_count = db.query(func.count(SimInventory.id)).filter(
            SimInventory.sim_type == "pSIM"
        ).scalar()
        
        # Available by type
        available_esim = db.query(func.count(SimInventory.id)).filter(
            SimInventory.status == "AVAILABLE",
            SimInventory.sim_type == "eSIM",
            SimInventory.assigned_to_child_sim_id.is_(None)
        ).scalar()
        
        available_psim = db.query(func.count(SimInventory.id)).filter(
            SimInventory.status == "AVAILABLE",
            SimInventory.sim_type == "pSIM",
            SimInventory.assigned_to_child_sim_id.is_(None)
        ).scalar()
        
        # By supplier
        suppliers = db.query(
            SimInventory.supplier,
            func.count(SimInventory.id).label('count')
        ).group_by(SimInventory.supplier).all()
        
        supplier_stats = {supplier: count for supplier, count in suppliers if supplier}
        
        return {
            "success": True,
            "stats": {
                "total_sims": total_sims or 0,
                "available_sims": available_sims or 0,
                "assigned_sims": assigned_sims or 0,
                "by_type": {
                    "eSIM": {
                        "total": esim_count or 0,
                        "available": available_esim or 0
                    },
                    "pSIM": {
                        "total": psim_count or 0,
                        "available": available_psim or 0
                    }
                },
                "by_supplier": supplier_stats
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching inventory stats: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to fetch inventory stats",
                "error": str(e)
            }
        )



@router.put("/{iccid}/status")
def update_sim_status(
    iccid: str,
    request: UpdateSimStatusRequest,
    db: Session = Depends(get_mysql_db),
    # current_user: Customer = Depends(get_current_user)
):
    """
    Update SIM allocation status by ICCID.
    Default status is AVAILABLE.
    Only admin users should access this endpoint.
    
    Valid statuses: AVAILABLE, ASSIGNED, SUSPENDED, TERMINATED
    """
    try:
        # Find the SIM by ICCID
        sim = db.query(SimInventory).filter(SimInventory.iccid == iccid).first()
        
        if not sim:
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "message": "SIM not found",
                    "iccid": iccid
                }
            )
        
        # Validate status
        valid_statuses = ["AVAILABLE", "ASSIGNED", "SUSPENDED", "TERMINATED"]
        if request.status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
                    "provided_status": request.status
                }
            )
        
        # Store old values for logging
        old_status = sim.status
        old_assigned_to = sim.assigned_to_child_sim_id
        
        # Update status
        sim.status = request.status
        
        # Update assignment
        if request.status == "AVAILABLE":
            # If setting to AVAILABLE, clear assignment
            sim.assigned_to_child_sim_id = None
            sim.assigned_at = None
        else:
            # For other statuses, update assignment if provided
            if request.assigned_to_child_sim_id is not None:
                sim.assigned_to_child_sim_id = request.assigned_to_child_sim_id
                if request.status == "ASSIGNED" and not sim.assigned_at:
                    sim.assigned_at = datetime.utcnow()
        
        # Update timestamp
        sim.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(sim)
        
        logger.info(f"SIM {iccid} status updated: {old_status} -> {request.status}, assignment: {old_assigned_to} -> {sim.assigned_to_child_sim_id}")
        
        return {
            "success": True,
            "message": "SIM status updated successfully",
            "data": {
                "id": sim.id,
                "sim_number": sim.sim_number,
                "iccid": sim.iccid,
                "old_status": old_status,
                "new_status": sim.status,
                "old_assigned_to": old_assigned_to,
                "new_assigned_to": sim.assigned_to_child_sim_id,
                "assigned_at": sim.assigned_at.isoformat() if sim.assigned_at else None,
                "updated_at": sim.updated_at.isoformat() if sim.updated_at else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating SIM status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to update SIM status",
                "error": str(e)
            }
        )


@router.put("/bulk/status")
def bulk_update_sim_status(
    iccids: list[str],
    request: UpdateSimStatusRequest,
    db: Session = Depends(get_mysql_db),
    # current_user: Customer = Depends(get_current_user)
):
    """
    Bulk update SIM allocation status for multiple SIMs by ICCID.
    Default status is AVAILABLE.
    Only admin users should access this endpoint.
    
    Valid statuses: AVAILABLE, ASSIGNED, SUSPENDED, TERMINATED
    """
    try:
        # Validate status
        valid_statuses = ["AVAILABLE", "ASSIGNED", "SUSPENDED", "TERMINATED"]
        if request.status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
                    "provided_status": request.status
                }
            )
        
        if not iccids:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": "No ICCIDs provided"
                }
            )
        
        # Find all SIMs by ICCID
        sims = db.query(SimInventory).filter(SimInventory.iccid.in_(iccids)).all()
        
        if not sims:
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "message": "No SIMs found with provided ICCIDs"
                }
            )
        
        updated_sims = []
        
        for sim in sims:
            old_status = sim.status
            
            # Update status
            sim.status = request.status
            
            # Update assignment
            if request.status == "AVAILABLE":
                # If setting to AVAILABLE, clear assignment
                sim.assigned_to_child_sim_id = None
                sim.assigned_at = None
            else:
                # For other statuses, update assignment if provided
                if request.assigned_to_child_sim_id is not None:
                    sim.assigned_to_child_sim_id = request.assigned_to_child_sim_id
                    if request.status == "ASSIGNED" and not sim.assigned_at:
                        sim.assigned_at = datetime.utcnow()
            
            # Update timestamp
            sim.updated_at = datetime.utcnow()
            
            updated_sims.append({
                "id": sim.id,
                "iccid": sim.iccid,
                "sim_number": sim.sim_number,
                "old_status": old_status,
                "new_status": sim.status
            })
        
        db.commit()
        
        logger.info(f"Bulk updated {len(updated_sims)} SIMs to status: {request.status}")
        
        return {
            "success": True,
            "message": f"Successfully updated {len(updated_sims)} SIMs",
            "total_updated": len(updated_sims),
            "total_requested": len(iccids),
            "data": updated_sims
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error bulk updating SIM status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to bulk update SIM status",
                "error": str(e)
            }
        )



@router.post("/allocate-by-admin/{iccid}")
def allocate_sim_by_admin(
    iccid: str,
    db: Session = Depends(get_mysql_db),
    # current_user: Customer = Depends(get_current_user)
):
    """
    Simple admin allocation endpoint - just send ICCID.
    Changes status to ASSIGNED and batch_number to 'adminGiven'.
    """
    try:
        # Find the SIM by ICCID
        sim = db.query(SimInventory).filter(SimInventory.iccid == iccid).first()
        
        if not sim:
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "message": "SIM not found",
                    "iccid": iccid
                }
            )
        
        # Store old values
        old_status = sim.status
        old_batch = sim.batch_number
        
        # Update to admin allocated
        sim.status = "ASSIGNED"
        sim.batch_number = "adminGiven"
        sim.assigned_at = datetime.utcnow()
        sim.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(sim)
        
        logger.info(f"SIM {iccid} allocated by admin: status {old_status} -> ASSIGNED, batch {old_batch} -> adminGiven")
        
        return {
            "success": True,
            "message": "SIM allocated by admin successfully",
            "data": {
                "id": sim.id,
                "sim_number": sim.sim_number,
                "iccid": sim.iccid,
                "msisdn": sim.msisdn,
                "old_status": old_status,
                "new_status": sim.status,
                "old_batch": old_batch,
                "new_batch": sim.batch_number,
                "assigned_at": sim.assigned_at.isoformat() if sim.assigned_at else None,
                "updated_at": sim.updated_at.isoformat() if sim.updated_at else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error allocating SIM by admin: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to allocate SIM by admin",
                "error": str(e)
            }
        )



class UpdateSimDetailsRequest(BaseModel):
    activation_code: Optional[str] = None
    sim_number: Optional[str] = None
    iccid: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "activation_code": "LPA:1$...",
                "sim_number": "89443042334118156270",
                "iccid": "89443042334118156270"
            }
        }


@router.put("/update-details/{iccid}")
def update_sim_details(
    iccid: str,
    request: UpdateSimDetailsRequest,
    db: Session = Depends(get_mysql_db),
    # current_user: Customer = Depends(get_current_user)
):
    """
    Update SIM details (activation_code, sim_number, iccid) by providing the current ICCID.
    Automatically sets batch_number to 'simswapadmin'.
    Only updates fields that are provided in the request body.
    """
    try:
        # Find the SIM by ICCID
        sim = db.query(SimInventory).filter(SimInventory.iccid == iccid).first()
        
        if not sim:
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "message": "SIM not found",
                    "iccid": iccid
                }
            )
        
        # Store old values for logging
        old_values = {
            "activation_code": sim.activation_code,
            "sim_number": sim.sim_number,
            "iccid": sim.iccid,
            "batch_number": sim.batch_number
        }
        
        updated_fields = []
        
        # Update activation_code if provided
        if request.activation_code is not None:
            sim.activation_code = request.activation_code
            updated_fields.append("activation_code")
        
        # Update sim_number if provided
        if request.sim_number is not None:
            sim.sim_number = request.sim_number
            updated_fields.append("sim_number")
        
        # Update iccid if provided
        if request.iccid is not None:
            sim.iccid = request.iccid
            updated_fields.append("iccid")
        
        # Always update batch_number to simswapadmin
        sim.batch_number = "simswapadmin"
        updated_fields.append("batch_number")
        
        if not updated_fields:
            return {
                "success": False,
                "message": "No fields provided to update"
            }
        
        # Update timestamp
        sim.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(sim)
        
        logger.info(f"SIM {iccid} details updated: {', '.join(updated_fields)}")
        
        return {
            "success": True,
            "message": f"SIM details updated successfully: {', '.join(updated_fields)}",
            "data": {
                "id": sim.id,
                "old_values": old_values,
                "new_values": {
                    "activation_code": sim.activation_code,
                    "sim_number": sim.sim_number,
                    "iccid": sim.iccid,
                    "batch_number": sim.batch_number
                },
                "updated_fields": updated_fields,
                "updated_at": sim.updated_at.isoformat() if sim.updated_at else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating SIM details: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to update SIM details",
                "error": str(e)
            }
        )
