from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, asc, func
from datetime import datetime, timedelta
import uuid

from models.mysql_models import (
    TblComplaintType, TblComplaintSubType, TblComplaintMaster, 
    TblComplaintComment, TblComplaintAttachment
)
from schemas.complaint_schema import (
    ComplaintTypeCreate, ComplaintTypeUpdate,
    ComplaintSubTypeCreate, ComplaintSubTypeUpdate,
    ComplaintCreate, ComplaintUpdate, ComplaintSearch,
    ComplaintCommentCreate
)


class ComplaintTypeRepository:
    """Repository for complaint type operations"""

    @staticmethod
    def create_complaint_type(db: Session, type_data: ComplaintTypeCreate, created_by: int) -> TblComplaintType:
        """Create a new complaint type"""
        db_type = TblComplaintType(
            **type_data.dict(),
            created_by=created_by,
            updated_by=created_by
        )
        db.add(db_type)
        db.commit()
        db.refresh(db_type)
        return db_type

    @staticmethod
    def get_complaint_type_by_id(db: Session, type_id: int) -> Optional[TblComplaintType]:
        """Get complaint type by ID"""
        return db.query(TblComplaintType).filter(TblComplaintType.id == type_id).first()

    @staticmethod
    def get_complaint_type_by_code(db: Session, type_code: str) -> Optional[TblComplaintType]:
        """Get complaint type by code"""
        return db.query(TblComplaintType).filter(TblComplaintType.type_code == type_code).first()

    @staticmethod
    def get_all_complaint_types(db: Session, is_active: Optional[bool] = None, skip: int = 0, limit: int = 100) -> List[TblComplaintType]:
        """Get all complaint types with optional filtering"""
        query = db.query(TblComplaintType)
        
        if is_active is not None:
            query = query.filter(TblComplaintType.is_active == is_active)
        
        # Add ORDER BY for pagination
        return query.order_by(TblComplaintType.id).offset(skip).limit(limit).all()

    @staticmethod
    def update_complaint_type(db: Session, type_id: int, type_update: ComplaintTypeUpdate, updated_by: int) -> Optional[TblComplaintType]:
        """Update complaint type"""
        db_type = db.query(TblComplaintType).filter(TblComplaintType.id == type_id).first()
        if db_type:
            update_data = type_update.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_type, field, value)
            db_type.updated_by = updated_by
            db_type.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(db_type)
        return db_type

    @staticmethod
    def delete_complaint_type(db: Session, type_id: int) -> bool:
        """Soft delete complaint type"""
        db_type = db.query(TblComplaintType).filter(TblComplaintType.id == type_id).first()
        if db_type:
            db_type.is_active = False
            db_type.updated_at = datetime.utcnow()
            db.commit()
            return True
        return False


class ComplaintSubTypeRepository:
    """Repository for complaint sub type operations"""

    @staticmethod
    def create_complaint_sub_type(db: Session, sub_type_data: ComplaintSubTypeCreate, created_by: int) -> TblComplaintSubType:
        """Create a new complaint sub type"""
        db_sub_type = TblComplaintSubType(
            **sub_type_data.dict(),
            created_by=created_by,
            updated_by=created_by
        )
        db.add(db_sub_type)
        db.commit()
        db.refresh(db_sub_type)
        return db_sub_type

    @staticmethod
    def get_complaint_sub_type_by_id(db: Session, sub_type_id: int) -> Optional[TblComplaintSubType]:
        """Get complaint sub type by ID"""
        return db.query(TblComplaintSubType).filter(TblComplaintSubType.id == sub_type_id).first()

    @staticmethod
    def get_sub_types_by_type(db: Session, complaint_type_id: int, is_active: Optional[bool] = None) -> List[TblComplaintSubType]:
        """Get sub types by complaint type"""
        query = db.query(TblComplaintSubType).filter(TblComplaintSubType.complaint_type_id == complaint_type_id)
        
        if is_active is not None:
            query = query.filter(TblComplaintSubType.is_active == is_active)
        
        # Add ORDER BY for pagination
        return query.order_by(TblComplaintSubType.id).all()

    @staticmethod
    def update_complaint_sub_type(db: Session, sub_type_id: int, sub_type_update: ComplaintSubTypeUpdate, updated_by: int) -> Optional[TblComplaintSubType]:
        """Update complaint sub type"""
        db_sub_type = db.query(TblComplaintSubType).filter(TblComplaintSubType.id == sub_type_id).first()
        if db_sub_type:
            update_data = sub_type_update.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_sub_type, field, value)
            db_sub_type.updated_by = updated_by
            db_sub_type.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(db_sub_type)
        return db_sub_type


class ComplaintRepository:
    """Repository for complaint operations"""

    @staticmethod
    def generate_complaint_number() -> str:
        """Generate unique complaint number"""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        unique_id = str(uuid.uuid4())[:8].upper()
        return f"CMP-{timestamp}-{unique_id}"

    @staticmethod
    def create_complaint(db: Session, complaint_data: ComplaintCreate, customer_id: int) -> TblComplaintMaster:
        """Create a new complaint"""
        # Get sub type for SLA calculation
        sub_type = db.query(TblComplaintSubType).filter(TblComplaintSubType.id == complaint_data.complaint_sub_type_id).first()
        sla_hours = sub_type.resolution_sla_hours if sub_type else 24
        
        # Convert complaint_data to dict and exclude customer_id to avoid conflicts
        complaint_dict = complaint_data.dict(exclude={'customer_id'})
        
        db_complaint = TblComplaintMaster(
            complaint_number=ComplaintRepository.generate_complaint_number(),
            customer_id=customer_id,
            sla_due_date=datetime.utcnow() + timedelta(hours=sla_hours),
            **complaint_dict
        )
        db.add(db_complaint)
        db.commit()
        db.refresh(db_complaint)
        return db_complaint

    @staticmethod
    def get_complaint_by_id(db: Session, complaint_id: int) -> Optional[TblComplaintMaster]:
        """Get complaint by ID with relationships"""
        return db.query(TblComplaintMaster).options(
            joinedload(TblComplaintMaster.complaint_type),
            joinedload(TblComplaintMaster.complaint_sub_type),
            joinedload(TblComplaintMaster.comments),
            joinedload(TblComplaintMaster.attachments)
        ).filter(TblComplaintMaster.id == complaint_id).first()

    @staticmethod
    def get_complaint_by_number(db: Session, complaint_number: str) -> Optional[TblComplaintMaster]:
        """Get complaint by complaint number"""
        return db.query(TblComplaintMaster).filter(TblComplaintMaster.complaint_number == complaint_number).first()

    @staticmethod
    def get_customer_complaints(db: Session, customer_id: int, skip: int = 0, limit: int = 100) -> List[TblComplaintMaster]:
        """Get complaints for a specific customer"""
        return db.query(TblComplaintMaster).filter(
            TblComplaintMaster.customer_id == customer_id
        ).order_by(desc(TblComplaintMaster.created_at)).offset(skip).limit(limit).all()

    @staticmethod
    def search_complaints(db: Session, search_params: ComplaintSearch, skip: int = 0, limit: int = 100) -> List[TblComplaintMaster]:
        """Search complaints with multiple criteria"""
        query = db.query(TblComplaintMaster).options(
            joinedload(TblComplaintMaster.complaint_type),
            joinedload(TblComplaintMaster.complaint_sub_type)
        )
        
        # Build filters
        filters = []
        
        if search_params.complaint_number:
            filters.append(TblComplaintMaster.complaint_number.like(f"%{search_params.complaint_number}%"))
        
        if search_params.customer_id:
            filters.append(TblComplaintMaster.customer_id == search_params.customer_id)
        
        if search_params.subscriber_id:
            filters.append(TblComplaintMaster.subscriber_id == search_params.subscriber_id)
        
        if search_params.complaint_type_id:
            filters.append(TblComplaintMaster.complaint_type_id == search_params.complaint_type_id)
        
        if search_params.complaint_sub_type_id:
            filters.append(TblComplaintMaster.complaint_sub_type_id == search_params.complaint_sub_type_id)
        
        if search_params.status:
            filters.append(TblComplaintMaster.status == search_params.status)
        
        if search_params.priority:
            filters.append(TblComplaintMaster.priority == search_params.priority)
        
        if search_params.assigned_to:
            filters.append(TblComplaintMaster.assigned_to == search_params.assigned_to)
        
        if search_params.is_sla_breached is not None:
            filters.append(TblComplaintMaster.is_sla_breached == search_params.is_sla_breached)
        
        if search_params.needs_attention is not None:
            filters.append(TblComplaintMaster.needs_attention == search_params.needs_attention)
        
        if search_params.created_from:
            filters.append(TblComplaintMaster.created_at >= search_params.created_from)
        
        if search_params.created_to:
            filters.append(TblComplaintMaster.created_at <= search_params.created_to)
        
        if search_params.source:
            filters.append(TblComplaintMaster.source == search_params.source)
        
        # Apply filters
        if filters:
            query = query.filter(and_(*filters))
        
        return query.order_by(desc(TblComplaintMaster.created_at)).offset(skip).limit(limit).all()

    @staticmethod
    def update_complaint(db: Session, complaint_id: int, complaint_update: ComplaintUpdate) -> Optional[TblComplaintMaster]:
        """Update complaint"""
        db_complaint = db.query(TblComplaintMaster).filter(TblComplaintMaster.id == complaint_id).first()
        if db_complaint:
            update_data = complaint_update.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_complaint, field, value)
            db_complaint.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(db_complaint)
        return db_complaint

    @staticmethod
    def assign_complaint(db: Session, complaint_id: int, assigned_to: int) -> Optional[TblComplaintMaster]:
        """Assign complaint to staff member"""
        db_complaint = db.query(TblComplaintMaster).filter(TblComplaintMaster.id == complaint_id).first()
        if db_complaint:
            db_complaint.assigned_to = assigned_to
            db_complaint.assigned_at = datetime.utcnow()
            db_complaint.status = "IN_PROGRESS"
            db_complaint.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(db_complaint)
        return db_complaint

    @staticmethod
    def resolve_complaint(db: Session, complaint_id: int, resolution_notes: str, resolved_by: int) -> Optional[TblComplaintMaster]:
        """Resolve complaint"""
        db_complaint = db.query(TblComplaintMaster).filter(TblComplaintMaster.id == complaint_id).first()
        if db_complaint:
            db_complaint.status = "RESOLVED"
            db_complaint.resolution_notes = resolution_notes
            db_complaint.resolved_at = datetime.utcnow()
            db_complaint.resolved_by = resolved_by
            db_complaint.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(db_complaint)
        return db_complaint

    @staticmethod
    def escalate_complaint(db: Session, complaint_id: int, escalated_to: int, escalation_reason: str) -> Optional[TblComplaintMaster]:
        """Escalate complaint"""
        db_complaint = db.query(TblComplaintMaster).filter(TblComplaintMaster.id == complaint_id).first()
        if db_complaint:
            db_complaint.status = "ESCALATED"
            db_complaint.escalated_at = datetime.utcnow()
            db_complaint.escalated_to = escalated_to
            db_complaint.escalation_reason = escalation_reason
            db_complaint.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(db_complaint)
        return db_complaint

    @staticmethod
    def close_complaint(db: Session, complaint_id: int) -> Optional[TblComplaintMaster]:
        """Close complaint"""
        db_complaint = db.query(TblComplaintMaster).filter(TblComplaintMaster.id == complaint_id).first()
        if db_complaint:
            db_complaint.status = "CLOSED"
            db_complaint.closed_at = datetime.utcnow()
            db_complaint.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(db_complaint)
        return db_complaint

    @staticmethod
    def update_sla_breach_status(db: Session):
        """Update SLA breach status for overdue complaints"""
        overdue_complaints = db.query(TblComplaintMaster).filter(
            and_(
                TblComplaintMaster.sla_due_date < datetime.utcnow(),
                TblComplaintMaster.status.in_(["OPEN", "IN_PROGRESS"]),
                TblComplaintMaster.is_sla_breached == False
            )
        ).all()
        
        for complaint in overdue_complaints:
            complaint.is_sla_breached = True
            complaint.updated_at = datetime.utcnow()
        
        db.commit()
        return len(overdue_complaints)

    @staticmethod
    def get_complaint_statistics(db: Session, customer_id: Optional[int] = None) -> Dict[str, Any]:
        """Get complaint statistics"""
        query = db.query(TblComplaintMaster)
        
        if customer_id:
            query = query.filter(TblComplaintMaster.customer_id == customer_id)
        
        total = query.count()
        open_count = query.filter(TblComplaintMaster.status == "OPEN").count()
        in_progress = query.filter(TblComplaintMaster.status == "IN_PROGRESS").count()
        resolved = query.filter(TblComplaintMaster.status == "RESOLVED").count()
        closed = query.filter(TblComplaintMaster.status == "CLOSED").count()
        escalated = query.filter(TblComplaintMaster.status == "ESCALATED").count()
        sla_breached = query.filter(TblComplaintMaster.is_sla_breached == True).count()
        
        # Calculate average resolution time
        resolved_complaints = query.filter(
            and_(
                TblComplaintMaster.status == "RESOLVED",
                TblComplaintMaster.resolved_at.isnot(None)
            )
        ).all()
        
        avg_resolution_hours = 0
        if resolved_complaints:
            total_hours = sum([
                (complaint.resolved_at - complaint.created_at).total_seconds() / 3600
                for complaint in resolved_complaints
            ])
            avg_resolution_hours = total_hours / len(resolved_complaints)
        
        return {
            "total_complaints": total,
            "open_complaints": open_count,
            "in_progress_complaints": in_progress,
            "resolved_complaints": resolved,
            "closed_complaints": closed,
            "escalated_complaints": escalated,
            "sla_breached_complaints": sla_breached,
            "avg_resolution_time_hours": round(avg_resolution_hours, 2)
        }


class ComplaintCommentRepository:
    """Repository for complaint comment operations"""

    @staticmethod
    def create_comment(db: Session, comment_data: ComplaintCommentCreate, created_by: int, created_by_type: str = "STAFF") -> TblComplaintComment:
        """Create a new comment"""
        db_comment = TblComplaintComment(
            **comment_data.dict(),
            created_by=created_by,
            created_by_type=created_by_type
        )
        db.add(db_comment)
        db.commit()
        db.refresh(db_comment)
        return db_comment

    @staticmethod
    def get_complaint_comments(db: Session, complaint_id: int, include_internal: bool = True) -> List[TblComplaintComment]:
        """Get comments for a complaint"""
        query = db.query(TblComplaintComment).filter(TblComplaintComment.complaint_id == complaint_id)
        
        # if not include_internal:
        #     query = query.filter(TblComplaintComment.is_internal == False)
        
        # Add ORDER BY for pagination
        return query.order_by(asc(TblComplaintComment.created_at)).all()