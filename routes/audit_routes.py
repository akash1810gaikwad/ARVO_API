from fastapi import APIRouter, Query
from typing import List, Optional
from schemas.audit_schema import AuditLogResponse

from services.audit_service import audit_service

router = APIRouter(prefix="/api/audit", tags=["Audit Logs"])


@router.get("/", response_model=List[AuditLogResponse])
async def get_audit_logs(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    resource: Optional[str] = Query(None, description="Filter by resource type"),
    action: Optional[str] = Query(None, description="Filter by action"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """Get audit logs with optional filters"""
    return await audit_service.get_audit_logs(
        user_id=user_id,
        resource=resource,
        action=action,
        skip=skip,
        limit=limit
    )


@router.get("/{log_id}", response_model=AuditLogResponse)
async def get_audit_log(log_id: str):
    """Get specific audit log by ID"""
    log = await audit_service.get_audit_log_by_id(log_id)
    if not log:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=200,
            content={"message": "Audit log not found", "data": None}
        )
    return log
