from typing import List, Optional
from sqlalchemy.orm import Session
from models.mysql_models import ServiceOption
from schemas.service_option_schema import ServiceOptionCreate, ServiceOptionUpdate
from utils.logger import logger


class ServiceOptionService:
    """Service for managing service options"""
    
    def create_service_option(self, db: Session, option_data: ServiceOptionCreate) -> ServiceOption:
        """Create a new service option"""
        try:
            db_option = ServiceOption(**option_data.model_dump())
            db.add(db_option)
            db.commit()
            db.refresh(db_option)
            logger.info(f"Service option created: {db_option.id}")
            return db_option
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create service option: {str(e)}")
            raise
    
    def get_service_option_by_id(self, db: Session, option_id: int) -> Optional[ServiceOption]:
        """Get service option by ID"""
        return db.query(ServiceOption).filter(ServiceOption.id == option_id).first()
    
    def get_service_options(self, db: Session, skip: int = 0, limit: int = 100, category: Optional[str] = None, active_only: bool = False) -> List[ServiceOption]:
        """Get all service options"""
        query = db.query(ServiceOption)
        if category:
            query = query.filter(ServiceOption.category == category)
        if active_only:
            query = query.filter(ServiceOption.is_active == True)
        return query.order_by(ServiceOption.sort_order).offset(skip).limit(limit).all()
    
    def update_service_option(self, db: Session, option_id: int, option_data: ServiceOptionUpdate) -> Optional[ServiceOption]:
        """Update service option"""
        try:
            db_option = self.get_service_option_by_id(db, option_id)
            if not db_option:
                return None
            
            update_data = option_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_option, field, value)
            
            db.commit()
            db.refresh(db_option)
            logger.info(f"Service option updated: {option_id}")
            return db_option
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update service option: {str(e)}")
            raise
    
    def delete_service_option(self, db: Session, option_id: int) -> bool:
        """Delete service option"""
        try:
            db_option = self.get_service_option_by_id(db, option_id)
            if not db_option:
                return False
            
            db.delete(db_option)
            db.commit()
            logger.info(f"Service option deleted: {option_id}")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to delete service option: {str(e)}")
            raise


service_option_service = ServiceOptionService()
