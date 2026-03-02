from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import Optional
from datetime import datetime, timedelta
import math

from config.mysql_database import get_mysql_db
from models.mysql_models import TransatelAPILog
from schemas.transatel_api_log_schema import (
    TransatelAPILogCreate,
    TransatelAPILogResponse,
    TransatelAPILogListResponse,
    TransatelAPILogStatsResponse,
    APIStatus
)
from utils.logger import logger

router = APIRouter(prefix="/api/v1/transatel-api-logs", tags=["Transatel API Logs"])


@router.get("/", response_model=TransatelAPILogListResponse, summary="Get All API Logs")
def get_all_api_logs(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of records to return"),
    api_name: Optional[str] = Query(None, description="Filter by API name"),
    endpoint: Optional[str] = Query(None, description="Filter by endpoint"),
    status: Optional[APIStatus] = Query(None, description="Filter by status"),
    http_status_code: Optional[int] = Query(None, description="Filter by HTTP status code"),
    date_from: Optional[datetime] = Query(None, description="Filter from date"),
    date_to: Optional[datetime] = Query(None, description="Filter to date"),
    db: Session = Depends(get_mysql_db)
):
    """
    Get all Transatel API logs with pagination and filters.
    Returns logs ordered by created_at descending (newest first).
    """
    try:
        # Build query
        query = db.query(TransatelAPILog)
        
        # Apply filters
        if api_name:
            query = query.filter(TransatelAPILog.api_name.like(f"%{api_name}%"))
        
        if endpoint:
            query = query.filter(TransatelAPILog.endpoint.like(f"%{endpoint}%"))
        
        if status:
            query = query.filter(TransatelAPILog.status == status.value)
        
        if http_status_code:
            query = query.filter(TransatelAPILog.http_status_code == http_status_code)
        
        if date_from:
            query = query.filter(TransatelAPILog.created_at >= date_from)
        
        if date_to:
            query = query.filter(TransatelAPILog.created_at <= date_to)
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering
        logs = query.order_by(TransatelAPILog.created_at.desc()).offset(skip).limit(limit).all()
        
        # Calculate pagination info
        page = (skip // limit) + 1
        total_pages = math.ceil(total / limit) if total > 0 else 0
        
        return TransatelAPILogListResponse(
            data=logs,
            total=total,
            page=page,
            page_size=limit,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Error fetching API logs: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to fetch API logs",
                "error": str(e)
            }
        )


@router.post("/", response_model=TransatelAPILogResponse, summary="Create API Log Entry")
def create_api_log(
    log: TransatelAPILogCreate,
    db: Session = Depends(get_mysql_db)
):
    """
    Create a new Transatel API log entry.
    """
    try:
        db_log = TransatelAPILog(
            api_name=log.api_name,
            endpoint=log.endpoint,
            request_payload=log.request_payload,
            response_payload=log.response_payload,
            status=log.status.value,
            http_status_code=log.http_status_code,
            error_message=log.error_message
        )
        
        db.add(db_log)
        db.commit()
        db.refresh(db_log)
        
        logger.info(f"Created API log entry: {log.api_name} - {log.status}")
        
        return db_log
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating API log: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to create API log",
                "error": str(e)
            }
        )


@router.get("/failed", response_model=TransatelAPILogListResponse, summary="Get Failed API Logs")
def get_failed_api_logs(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of records to return"),
    api_name: Optional[str] = Query(None, description="Filter by API name"),
    hours: int = Query(24, ge=1, description="Get failed logs from last N hours"),
    db: Session = Depends(get_mysql_db)
):
    """
    Get all failed Transatel API logs.
    By default, returns failed logs from the last 24 hours.
    """
    try:
        # Calculate time threshold
        time_threshold = datetime.utcnow() - timedelta(hours=hours)
        
        # Build query for failed logs
        query = db.query(TransatelAPILog).filter(
            TransatelAPILog.status == "FAILED",
            TransatelAPILog.created_at >= time_threshold
        )
        
        # Apply API name filter if provided
        if api_name:
            query = query.filter(TransatelAPILog.api_name.like(f"%{api_name}%"))
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering
        logs = query.order_by(TransatelAPILog.created_at.desc()).offset(skip).limit(limit).all()
        
        # Calculate pagination info
        page = (skip // limit) + 1
        total_pages = math.ceil(total / limit) if total > 0 else 0
        
        return TransatelAPILogListResponse(
            data=logs,
            total=total,
            page=page,
            page_size=limit,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Error fetching failed API logs: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to fetch failed API logs",
                "error": str(e)
            }
        )


@router.get("/stats", response_model=TransatelAPILogStatsResponse, summary="Get API Log Statistics")
def get_api_log_statistics(
    hours: int = Query(24, ge=1, description="Get statistics from last N hours"),
    db: Session = Depends(get_mysql_db)
):
    """
    Get Transatel API log statistics including success/failure rates,
    most called APIs, and error distribution.
    """
    try:
        # Calculate time threshold
        time_threshold = datetime.utcnow() - timedelta(hours=hours)
        
        # Total logs
        total_logs = db.query(func.count(TransatelAPILog.id)).filter(
            TransatelAPILog.created_at >= time_threshold
        ).scalar()
        
        # Success/Failed counts
        success_count = db.query(func.count(TransatelAPILog.id)).filter(
            TransatelAPILog.created_at >= time_threshold,
            TransatelAPILog.status == "SUCCESS"
        ).scalar()
        
        failed_count = db.query(func.count(TransatelAPILog.id)).filter(
            TransatelAPILog.created_at >= time_threshold,
            TransatelAPILog.status == "FAILED"
        ).scalar()
        
        # Success rate
        success_rate = (success_count / total_logs * 100) if total_logs > 0 else 0
        
        # Most called APIs
        most_called = db.query(
            TransatelAPILog.api_name,
            func.count(TransatelAPILog.id).label('count')
        ).filter(
            TransatelAPILog.created_at >= time_threshold
        ).group_by(TransatelAPILog.api_name).order_by(func.count(TransatelAPILog.id).desc()).limit(10).all()
        
        most_called_apis = [{"api_name": name, "count": count} for name, count in most_called]
        
        # HTTP status code distribution
        status_codes = db.query(
            TransatelAPILog.http_status_code,
            func.count(TransatelAPILog.id).label('count')
        ).filter(
            TransatelAPILog.created_at >= time_threshold,
            TransatelAPILog.http_status_code.isnot(None)
        ).group_by(TransatelAPILog.http_status_code).all()
        
        status_code_distribution = {str(code): count for code, count in status_codes if code}
        
        # Most common errors
        common_errors = db.query(
            TransatelAPILog.error_message,
            func.count(TransatelAPILog.id).label('count')
        ).filter(
            TransatelAPILog.created_at >= time_threshold,
            TransatelAPILog.status == "FAILED",
            TransatelAPILog.error_message.isnot(None)
        ).group_by(TransatelAPILog.error_message).order_by(func.count(TransatelAPILog.id).desc()).limit(5).all()
        
        common_error_list = [{"error": error, "count": count} for error, count in common_errors if error]
        
        stats = {
            "time_period_hours": hours,
            "total_logs": total_logs or 0,
            "success_count": success_count or 0,
            "failed_count": failed_count or 0,
            "success_rate": round(success_rate, 2),
            "most_called_apis": most_called_apis,
            "status_code_distribution": status_code_distribution,
            "common_errors": common_error_list
        }
        
        return TransatelAPILogStatsResponse(data=stats)
        
    except Exception as e:
        logger.error(f"Error fetching API log statistics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to fetch API log statistics",
                "error": str(e)
            }
        )


@router.get("/{log_id}", response_model=TransatelAPILogResponse, summary="Get API Log by ID")
def get_api_log_by_id(
    log_id: int,
    db: Session = Depends(get_mysql_db)
):
    """
    Get a specific Transatel API log by ID.
    """
    try:
        log = db.query(TransatelAPILog).filter(TransatelAPILog.id == log_id).first()
        
        if not log:
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "message": "API log not found",
                    "log_id": log_id
                }
            )
        
        return log
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching API log: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to fetch API log",
                "error": str(e)
            }
        )


@router.delete("/cleanup", summary="Delete Old API Logs")
def delete_old_api_logs(
    days: int = Query(30, ge=1, description="Delete logs older than N days"),
    db: Session = Depends(get_mysql_db)
):
    """
    Delete Transatel API logs older than specified number of days.
    Default is 30 days.
    """
    try:
        # Calculate cutoff date
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Count logs to be deleted
        count = db.query(func.count(TransatelAPILog.id)).filter(
            TransatelAPILog.created_at < cutoff_date
        ).scalar()
        
        if count == 0:
            return {
                "success": True,
                "message": f"No logs older than {days} days found",
                "deleted_count": 0
            }
        
        # Delete old logs
        db.query(TransatelAPILog).filter(
            TransatelAPILog.created_at < cutoff_date
        ).delete(synchronize_session=False)
        
        db.commit()
        
        logger.info(f"Deleted {count} API logs older than {days} days")
        
        return {
            "success": True,
            "message": f"Successfully deleted logs older than {days} days",
            "deleted_count": count,
            "cutoff_date": cutoff_date.isoformat()
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting old API logs: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to delete old API logs",
                "error": str(e)
            }
        )
