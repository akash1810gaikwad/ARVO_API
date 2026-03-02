from typing import Optional, List
from sqlalchemy.orm import Session
from models.mysql_models import EmailTemplate
from schemas.email_template_schema import EmailTemplateCreate, EmailTemplateUpdate
from utils.logger import logger
import json


class EmailTemplateService:
    """Service for managing email templates"""
    
    def create_template(self, db: Session, template_data: EmailTemplateCreate) -> EmailTemplate:
        """Create a new email template"""
        try:
            db_template = EmailTemplate(
                template_key=template_data.template_key,
                template_name=template_data.template_name,
                subject=template_data.subject,
                body_html=template_data.body_html,
                body_text=template_data.body_text,
                variables=template_data.variables,
                description=template_data.description,
                is_active=template_data.is_active
            )
            db.add(db_template)
            db.commit()
            db.refresh(db_template)
            logger.info(f"Email template created: {db_template.template_key}")
            return db_template
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create email template: {str(e)}")
            raise
    
    def get_template_by_id(self, db: Session, template_id: int) -> Optional[EmailTemplate]:
        """Get template by ID"""
        return db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
    
    def get_template_by_key(self, db: Session, template_key: str) -> Optional[EmailTemplate]:
        """Get template by key"""
        return db.query(EmailTemplate).filter(
            EmailTemplate.template_key == template_key,
            EmailTemplate.is_active == True
        ).first()
    
    def get_all_templates(self, db: Session, include_inactive: bool = False) -> List[EmailTemplate]:
        """Get all templates"""
        query = db.query(EmailTemplate)
        if not include_inactive:
            query = query.filter(EmailTemplate.is_active == True)
        return query.all()
    
    def update_template(self, db: Session, template_id: int, template_data: EmailTemplateUpdate) -> Optional[EmailTemplate]:
        """Update email template"""
        try:
            db_template = self.get_template_by_id(db, template_id)
            if not db_template:
                return None
            
            update_data = template_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_template, field, value)
            
            db.commit()
            db.refresh(db_template)
            logger.info(f"Email template updated: {template_id}")
            return db_template
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update email template: {str(e)}")
            raise
    
    def delete_template(self, db: Session, template_id: int) -> bool:
        """Delete email template"""
        try:
            db_template = self.get_template_by_id(db, template_id)
            if not db_template:
                return False
            
            db.delete(db_template)
            db.commit()
            logger.info(f"Email template deleted: {template_id}")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to delete email template: {str(e)}")
            raise
    
    def render_template(self, template: EmailTemplate, variables: dict) -> tuple[str, str, Optional[str]]:
        """Render template with variables"""
        try:
            subject = template.subject
            body_html = template.body_html
            body_text = template.body_text
            
            # Replace variables in subject
            for key, value in variables.items():
                placeholder = f"{{{{{key}}}}}"  # {{variable_name}}
                subject = subject.replace(placeholder, str(value))
                body_html = body_html.replace(placeholder, str(value))
                if body_text:
                    body_text = body_text.replace(placeholder, str(value))
            
            return subject, body_html, body_text
        except Exception as e:
            logger.error(f"Failed to render template: {str(e)}")
            raise


email_template_service = EmailTemplateService()
