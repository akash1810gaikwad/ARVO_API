from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List
from config.mysql_database import get_mysql_db
from schemas.email_template_schema import (
    EmailTemplateCreate, EmailTemplateUpdate, EmailTemplateResponse,
    EmailTemplatePreviewRequest, EmailTemplatePreviewResponse
)
from schemas.audit_schema import AuditLogCreate
from services.email_template_service import email_template_service
from services.audit_service import audit_service
from utils.logger import logger

router = APIRouter(prefix="/api/email-templates", tags=["Email Templates"])


@router.post("/", response_model=EmailTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    request: Request,
    template_data: EmailTemplateCreate,
    db: Session = Depends(get_mysql_db)
):
    """Create a new email template"""
    try:
        # Check if template key already exists
        existing = email_template_service.get_template_by_key(db, template_data.template_key)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Template with key '{template_data.template_key}' already exists"
            )
        
        template = email_template_service.create_template(db, template_data)
        
        # Create audit log
        await audit_service.create_audit_log(AuditLogCreate(
            action="CREATE",
            resource="EmailTemplate",
            resource_id=str(template.id),
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent")
        ))
        
        return template
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating email template: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create template: {str(e)}")


@router.get("/", response_model=List[EmailTemplateResponse])
def get_all_templates(
    include_inactive: bool = False,
    db: Session = Depends(get_mysql_db)
):
    """Get all email templates"""
    templates = email_template_service.get_all_templates(db, include_inactive)
    return templates


@router.get("/{template_id}", response_model=EmailTemplateResponse)
def get_template(template_id: int, db: Session = Depends(get_mysql_db)):
    """Get email template by ID"""
    template = email_template_service.get_template_by_id(db, template_id)
    if not template:
        return JSONResponse(
            status_code=200,
            content={"message": "Template not found", "data": None}
        )
    return template


@router.get("/key/{template_key}", response_model=EmailTemplateResponse)
def get_template_by_key(template_key: str, db: Session = Depends(get_mysql_db)):
    """Get email template by key"""
    template = email_template_service.get_template_by_key(db, template_key)
    if not template:
        return JSONResponse(
            status_code=200,
            content={"message": "Template not found", "data": None}
        )
    return template


@router.put("/{template_id}", response_model=EmailTemplateResponse)
async def update_template(
    request: Request,
    template_id: int,
    template_data: EmailTemplateUpdate,
    db: Session = Depends(get_mysql_db)
):
    """Update email template"""
    template = email_template_service.update_template(db, template_id, template_data)
    if not template:
        return JSONResponse(
            status_code=200,
            content={"message": "Template not found", "data": None}
        )
    
    # Create audit log
    await audit_service.create_audit_log(AuditLogCreate(
        action="UPDATE",
        resource="EmailTemplate",
        resource_id=str(template_id),
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        changes=template_data.model_dump(exclude_unset=True)
    ))
    
    return template


@router.delete("/{template_id}")
async def delete_template(
    request: Request,
    template_id: int,
    db: Session = Depends(get_mysql_db)
):
    """Delete email template"""
    success = email_template_service.delete_template(db, template_id)
    if not success:
        return JSONResponse(
            status_code=200,
            content={"message": "Template not found", "success": False}
        )
    
    # Create audit log
    await audit_service.create_audit_log(AuditLogCreate(
        action="DELETE",
        resource="EmailTemplate",
        resource_id=str(template_id),
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    ))
    
    return JSONResponse(
        status_code=200,
        content={"message": "Template deleted successfully", "success": True}
    )


@router.post("/preview", response_model=EmailTemplatePreviewResponse)
def preview_template(
    preview_data: EmailTemplatePreviewRequest,
    db: Session = Depends(get_mysql_db)
):
    """Preview email template with variables"""
    try:
        template = email_template_service.get_template_by_key(db, preview_data.template_key)
        if not template:
            raise HTTPException(
                status_code=404,
                detail=f"Template '{preview_data.template_key}' not found"
            )
        
        subject, body_html, body_text = email_template_service.render_template(
            template, preview_data.variables
        )
        
        return {
            "subject": subject,
            "body_html": body_html,
            "body_text": body_text
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error previewing template: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to preview template: {str(e)}")
