from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import logging

from config.mysql_database import get_mysql_db
from services.complaint_service import (
    ComplaintTypeRepository, ComplaintSubTypeRepository, 
    ComplaintRepository, ComplaintCommentRepository
)
from models.mysql_models import TblComplaintComment
from schemas.complaint_schema import (
    ComplaintTypeCreate, ComplaintTypeResponse,
    ComplaintSubTypeCreate, ComplaintSubTypeResponse,
    ComplaintCreate, ComplaintUpdate, ComplaintResponse, ComplaintDetailResponse,
    ComplaintCommentCreate, ComplaintCommentResponse,
    ComplaintListResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/complaints", tags=["Complaint Management"])


# ============= COMPLAINT TYPE ENDPOINTS =============

@router.post("/types", response_model=ComplaintTypeResponse, status_code=status.HTTP_201_CREATED)
def create_complaint_type(
    type_data: ComplaintTypeCreate,
    db: Session = Depends(get_mysql_db)
):
    """Create a new complaint type"""
    try:
        existing_type = ComplaintTypeRepository.get_complaint_type_by_code(db, type_data.type_code)
        if existing_type:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Complaint type with code '{type_data.type_code}' already exists"
            )
        
        complaint_type = ComplaintTypeRepository.create_complaint_type(db, type_data, created_by=1)
        return complaint_type
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating complaint type: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create complaint type: {str(e)}"
        )


@router.get("/types", response_model=List[ComplaintTypeResponse])
def get_complaint_types(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_mysql_db)
):
    """Get all complaint types"""
    try:
        complaint_types = ComplaintTypeRepository.get_all_complaint_types(db, is_active)
        return complaint_types
    except Exception as e:
        logger.error(f"Error getting complaint types: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get complaint types: {str(e)}"
        )


@router.get("/types/{type_id}", response_model=ComplaintTypeResponse)
def get_complaint_type(
    type_id: int,
    db: Session = Depends(get_mysql_db)
):
    """Get complaint type by ID"""
    complaint_type = ComplaintTypeRepository.get_complaint_type_by_id(db, type_id)
    if not complaint_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint type with ID {type_id} not found"
        )
    return complaint_type


# ============= COMPLAINT SUB-TYPE ENDPOINTS =============

@router.post("/sub-types", response_model=ComplaintSubTypeResponse, status_code=status.HTTP_201_CREATED)
def create_complaint_sub_type(
    sub_type_data: ComplaintSubTypeCreate,
    db: Session = Depends(get_mysql_db)
):
    """Create a new complaint sub-type"""
    try:
        complaint_type = ComplaintTypeRepository.get_complaint_type_by_id(db, sub_type_data.complaint_type_id)
        if not complaint_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Complaint type with ID {sub_type_data.complaint_type_id} not found"
            )
        
        sub_type = ComplaintSubTypeRepository.create_complaint_sub_type(db, sub_type_data, created_by=1)
        return sub_type
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating complaint sub type: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create complaint sub type: {str(e)}"
        )


@router.get("/types/{type_id}/sub-types", response_model=List[ComplaintSubTypeResponse])
def get_complaint_sub_types(
    type_id: int,
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_mysql_db)
):
    """Get sub-types for a complaint type"""
    try:
        complaint_type = ComplaintTypeRepository.get_complaint_type_by_id(db, type_id)
        if not complaint_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Complaint type with ID {type_id} not found"
            )
        
        sub_types = ComplaintSubTypeRepository.get_sub_types_by_type(db, type_id, is_active)
        return sub_types
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting complaint sub types: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get complaint sub types: {str(e)}"
        )


# ============= COMPLAINT ENDPOINTS =============

@router.post("/customer/{customer_id}", response_model=ComplaintResponse, status_code=status.HTTP_201_CREATED)
def create_complaint(
    customer_id: int,
    complaint_data: ComplaintCreate,
    db: Session = Depends(get_mysql_db)
):
    """Create a new complaint for a customer"""
    try:
        from models.mysql_models import Customer
        from services.email_service import send_complaint_created_email
        
        # Verify complaint type exists
        complaint_type = ComplaintTypeRepository.get_complaint_type_by_id(db, complaint_data.complaint_type_id)
        if not complaint_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Complaint type with ID {complaint_data.complaint_type_id} not found"
            )
        
        # Verify sub type exists
        sub_type = ComplaintSubTypeRepository.get_complaint_sub_type_by_id(db, complaint_data.complaint_sub_type_id)
        if not sub_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Complaint sub type with ID {complaint_data.complaint_sub_type_id} not found"
            )
        
        # Verify sub type belongs to the complaint type
        if sub_type.complaint_type_id != complaint_data.complaint_type_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sub type does not belong to the specified complaint type"
            )
        
        # Create complaint
        complaint = ComplaintRepository.create_complaint(db, complaint_data, customer_id)
        
        # Get customer details for email
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if customer and customer.email:
            try:
                send_complaint_created_email(
                    customer_email=customer.email,
                    customer_name=customer.full_name or "Customer",
                    complaint_number=complaint.complaint_number,
                    complaint_title=complaint.title,
                    complaint_description=complaint.description
                )
                logger.info(f"Complaint created email sent to {customer.email}")
            except Exception as email_error:
                logger.error(f"Failed to send complaint created email: {email_error}")
        
        return complaint
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating complaint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create complaint: {str(e)}"
        )


@router.get("/", response_model=ComplaintListResponse)
def get_all_complaints(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of records to return"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    complaint_type_id: Optional[int] = Query(None, description="Filter by complaint type"),
    db: Session = Depends(get_mysql_db)
):
    """Get all complaints with optional filters"""
    try:
        from models.mysql_models import TblComplaintMaster
        
        # Build query with ORDER BY for pagination
        query = db.query(TblComplaintMaster)
        
        # Apply filters
        if status_filter:
            query = query.filter(TblComplaintMaster.status == status_filter)
        
        if priority:
            query = query.filter(TblComplaintMaster.priority == priority)
        
        if complaint_type_id:
            query = query.filter(TblComplaintMaster.complaint_type_id == complaint_type_id)
        
        # Get total count before pagination
        total_count = query.count()
        
        # Order by ID descending (newest first) and apply pagination
        complaints = query.order_by(TblComplaintMaster.id.desc()).offset(skip).limit(limit).all()
        
        # Calculate page number
        page = (skip // limit) + 1 if limit > 0 else 1
        
        # Check if there are more records
        has_more = (skip + limit) < total_count
        
        return ComplaintListResponse(
            success=True,
            data=complaints,
            total_count=total_count,
            page=page,
            limit=limit,
            has_more=has_more
        )
        
    except Exception as e:
        logger.error(f"Error getting all complaints: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get complaints: {str(e)}"
        )


@router.get("/customer/{customer_id}", response_model=List[ComplaintResponse])
def get_customer_complaints(
    customer_id: int,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of records to return"),
    db: Session = Depends(get_mysql_db)
):
    """Get all complaints for a customer"""
    try:
        complaints = ComplaintRepository.get_customer_complaints(db, customer_id, skip, limit)
        return complaints
    except Exception as e:
        logger.error(f"Error getting complaints for customer {customer_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get complaints: {str(e)}"
        )


@router.get("/{complaint_id}", response_model=ComplaintDetailResponse)
def get_complaint(
    complaint_id: int,
    db: Session = Depends(get_mysql_db)
):
    """Get complaint by ID"""
    complaint = ComplaintRepository.get_complaint_by_id(db, complaint_id)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint with ID {complaint_id} not found"
        )
    
    response_data = {
        "id": complaint.id,
        "complaint_number": complaint.complaint_number,
        "customer_id": complaint.customer_id,
        "subscriber_id": complaint.subscriber_id,
        "complaint_type_id": complaint.complaint_type_id,
        "complaint_sub_type_id": complaint.complaint_sub_type_id,
        "title": complaint.title,
        "description": complaint.description,
        "priority": complaint.priority,
        "status": complaint.status,
        "contact_email": complaint.contact_email,
        "contact_phone": complaint.contact_phone,
        "resolution_notes": complaint.resolution_notes,
        "resolved_at": complaint.resolved_at,
        "resolved_by": complaint.resolved_by,
        "sla_due_date": complaint.sla_due_date,
        "is_sla_breached": complaint.is_sla_breached,
        "assigned_to": complaint.assigned_to,
        "assigned_at": complaint.assigned_at,
        "escalated_at": complaint.escalated_at,
        "escalated_to": complaint.escalated_to,
        "escalation_reason": complaint.escalation_reason,
        "created_at": complaint.created_at,
        "updated_at": complaint.updated_at,
        "closed_at": complaint.closed_at,
        "source": complaint.source,
        "reference_number": complaint.reference_number,
        "tags": complaint.tags,
        "complaint_type": complaint.complaint_type,
        "complaint_sub_type": complaint.complaint_sub_type,
        "comments_count": len(complaint.comments) if complaint.comments else 0,
        "attachments_count": len(complaint.attachments) if complaint.attachments else 0
    }
    
    return ComplaintDetailResponse(**response_data)


@router.put("/{complaint_id}", response_model=ComplaintResponse)
def update_complaint(
    complaint_id: int,
    complaint_update: ComplaintUpdate,
    db: Session = Depends(get_mysql_db)
):
    """Update a complaint"""
    try:
        from models.mysql_models import Customer
        from services.email_service import send_complaint_resolved_email
        
        existing_complaint = ComplaintRepository.get_complaint_by_id(db, complaint_id)
        if not existing_complaint:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Complaint with ID {complaint_id} not found"
            )
        
        # Check if status is being changed to RESOLVED
        old_status = existing_complaint.status
        new_status = complaint_update.status if complaint_update.status else old_status
        
        # Update complaint
        complaint = ComplaintRepository.update_complaint(db, complaint_id, complaint_update)
        
        # Send email if complaint was just resolved
        if old_status != "RESOLVED" and new_status == "RESOLVED":
            customer = db.query(Customer).filter(Customer.id == complaint.customer_id).first()
            if customer and customer.email and complaint.resolution_notes:
                try:
                    send_complaint_resolved_email(
                        customer_email=customer.email,
                        customer_name=customer.full_name or "Customer",
                        complaint_number=complaint.complaint_number,
                        complaint_title=complaint.title,
                        resolution_notes=complaint.resolution_notes
                    )
                    logger.info(f"Complaint resolved email sent to {customer.email}")
                except Exception as email_error:
                    logger.error(f"Failed to send complaint resolved email: {email_error}")
        
        return complaint
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating complaint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update complaint: {str(e)}"
        )


@router.get("/number/{complaint_number}", response_model=ComplaintResponse)
def get_complaint_by_number(
    complaint_number: str,
    db: Session = Depends(get_mysql_db)
):
    """Get complaint by complaint number"""
    complaint = ComplaintRepository.get_complaint_by_number(db, complaint_number)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint with number '{complaint_number}' not found"
        )
    return complaint


# ============= COMMENT ENDPOINTS =============

@router.post("/{complaint_id}/comments", response_model=ComplaintCommentResponse, status_code=status.HTTP_201_CREATED)
def add_complaint_comment(
    complaint_id: int,
    comment_data: ComplaintCommentCreate,
    db: Session = Depends(get_mysql_db)
):
    """Add a comment to a complaint"""
    try:
        complaint = ComplaintRepository.get_complaint_by_id(db, complaint_id)
        if not complaint:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Complaint with ID {complaint_id} not found"
            )
        
        # Create comment with complaint_id from URL
        db_comment = TblComplaintComment(
            complaint_id=complaint_id,
            comment_text=comment_data.comment_text,
            comment_type=comment_data.comment_type,
            is_internal=comment_data.is_internal,
            created_by=1,
            created_by_type=comment_data.comment_type
        )
        db.add(db_comment)
        db.commit()
        db.refresh(db_comment)
        return db_comment
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding complaint comment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add comment: {str(e)}"
        )


@router.get("/{complaint_id}/comments", response_model=List[ComplaintCommentResponse])
def get_complaint_comments(
    complaint_id: int,
    db: Session = Depends(get_mysql_db)
):
    """Get all comments for a complaint"""
    try:
        complaint = ComplaintRepository.get_complaint_by_id(db, complaint_id)
        if not complaint:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Complaint with ID {complaint_id} not found"
            )
        
        comments = ComplaintCommentRepository.get_complaint_comments(db, complaint_id, include_internal=False)
        return comments
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting complaint comments: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get comments: {str(e)}"
        )



@router.get("/statistics/summary")
def get_complaints_statistics_summary(
    customer_id: Optional[int] = Query(None, description="Filter by customer ID"),
    db: Session = Depends(get_mysql_db)
):
    """Get complaints statistics summary"""
    try:
        from models.mysql_models import TblComplaintMaster, TblComplaintType
        from sqlalchemy import func, case
        from datetime import datetime
        
        # Build base query
        query = db.query(TblComplaintMaster)
        
        # Filter by customer if provided
        if customer_id:
            query = query.filter(TblComplaintMaster.customer_id == customer_id)
        
        # Get total complaints
        total_complaints = query.count()
        
        # Count by status
        open_complaints = query.filter(TblComplaintMaster.status == "OPEN").count()
        in_progress_complaints = query.filter(TblComplaintMaster.status == "IN_PROGRESS").count()
        resolved_complaints = query.filter(TblComplaintMaster.status == "RESOLVED").count()
        closed_complaints = query.filter(TblComplaintMaster.status == "CLOSED").count()
        
        # Count escalated complaints
        escalated_complaints = query.filter(TblComplaintMaster.escalated_at.isnot(None)).count()
        
        # Count SLA breached complaints
        sla_breached_complaints = query.filter(TblComplaintMaster.is_sla_breached == True).count()
        
        # Calculate average resolution time
        resolved_query = query.filter(
            TblComplaintMaster.resolved_at.isnot(None),
            TblComplaintMaster.created_at.isnot(None)
        ).all()
        
        total_resolution_time = 0
        resolution_count = 0
        for complaint in resolved_query:
            if complaint.resolved_at and complaint.created_at:
                time_diff = complaint.resolved_at - complaint.created_at
                total_resolution_time += time_diff.total_seconds() / 3600  # Convert to hours
                resolution_count += 1
        
        avg_resolution_time_hours = round(total_resolution_time / resolution_count, 2) if resolution_count > 0 else 0.0
        
        # Get complaints by type
        complaints_by_type_query = db.query(
            TblComplaintType.type_name,
            func.count(TblComplaintMaster.id).label('count')
        ).join(
            TblComplaintType,
            TblComplaintMaster.complaint_type_id == TblComplaintType.id
        )
        
        if customer_id:
            complaints_by_type_query = complaints_by_type_query.filter(
                TblComplaintMaster.customer_id == customer_id
            )
        
        complaints_by_type_result = complaints_by_type_query.group_by(
            TblComplaintType.type_name
        ).all()
        
        complaints_by_type = {row.type_name: row.count for row in complaints_by_type_result}
        
        # Get complaints by priority
        complaints_by_priority_query = db.query(
            TblComplaintMaster.priority,
            func.count(TblComplaintMaster.id).label('count')
        )
        
        if customer_id:
            complaints_by_priority_query = complaints_by_priority_query.filter(
                TblComplaintMaster.customer_id == customer_id
            )
        
        complaints_by_priority_result = complaints_by_priority_query.filter(
            TblComplaintMaster.priority.isnot(None)
        ).group_by(
            TblComplaintMaster.priority
        ).all()
        
        complaints_by_priority = {row.priority: row.count for row in complaints_by_priority_result}
        
        return {
            "total_complaints": total_complaints,
            "open_complaints": open_complaints,
            "in_progress_complaints": in_progress_complaints,
            "resolved_complaints": resolved_complaints,
            "closed_complaints": closed_complaints,
            "escalated_complaints": escalated_complaints,
            "sla_breached_complaints": sla_breached_complaints,
            "avg_resolution_time_hours": avg_resolution_time_hours,
            "complaints_by_type": complaints_by_type,
            "complaints_by_priority": complaints_by_priority
        }
        
    except Exception as e:
        logger.error(f"Error getting complaints statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}"
        )
