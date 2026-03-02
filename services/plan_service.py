from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from models.mysql_models import PlanMaster, PlanServiceOption, ServiceOption
from schemas.plan_schema import PlanCreate, PlanUpdate
from utils.logger import logger


class PlanService:
    """Service for managing subscription plans"""
    
    def create_plan(self, db: Session, plan_data: PlanCreate) -> PlanMaster:
        """Create a new plan with service options"""
        try:
            db_plan = PlanMaster(
                plan_code=plan_data.plan_code,
                plan_name=plan_data.plan_name,
                description=plan_data.description,
                plan_type=plan_data.plan_type,
                duration_months=plan_data.duration_months,
                price=plan_data.price,
                currency=plan_data.currency,
                is_active=plan_data.is_active,
                sort_order=plan_data.sort_order
            )
            db.add(db_plan)
            db.flush()
            
            # Add service options to plan
            if plan_data.service_option_ids:
                for option_id in plan_data.service_option_ids:
                    plan_option = PlanServiceOption(
                        plan_id=db_plan.id,
                        service_option_id=option_id,
                        is_default=True
                    )
                    db.add(plan_option)
            
            db.commit()
            db.refresh(db_plan)
            logger.info(f"Plan created: {db_plan.id}")
            return db_plan
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create plan: {str(e)}")
            raise
    
    def get_plan_by_id(self, db: Session, plan_id: int) -> Optional[PlanMaster]:
        """Get plan by ID with service options"""
        return db.query(PlanMaster).options(
            joinedload(PlanMaster.plan_service_options).joinedload(PlanServiceOption.service_option)
        ).filter(PlanMaster.id == plan_id).first()
    
    def get_plans(self, db: Session, skip: int = 0, limit: int = 100, active_only: bool = False) -> List[PlanMaster]:
        """Get all plans"""
        query = db.query(PlanMaster).options(
            joinedload(PlanMaster.plan_service_options).joinedload(PlanServiceOption.service_option)
        )
        if active_only:
            query = query.filter(PlanMaster.is_active == True)
        return query.order_by(PlanMaster.sort_order).offset(skip).limit(limit).all()
    
    def update_plan(self, db: Session, plan_id: int, plan_data: PlanUpdate) -> Optional[PlanMaster]:
        """Update plan"""
        try:
            db_plan = self.get_plan_by_id(db, plan_id)
            if not db_plan:
                return None
            
            update_data = plan_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_plan, field, value)
            
            db.commit()
            db.refresh(db_plan)
            logger.info(f"Plan updated: {plan_id}")
            return db_plan
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update plan: {str(e)}")
            raise
    
    def delete_plan(self, db: Session, plan_id: int) -> bool:
        """Delete plan"""
        try:
            db_plan = self.get_plan_by_id(db, plan_id)
            if not db_plan:
                return False
            
            db.delete(db_plan)
            db.commit()
            logger.info(f"Plan deleted: {plan_id}")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to delete plan: {str(e)}")
            raise
    
    def add_service_option_to_plan(self, db: Session, plan_id: int, service_option_id: int, is_required: bool = False) -> PlanServiceOption:
        """Add service option to plan"""
        try:
            plan_option = PlanServiceOption(
                plan_id=plan_id,
                service_option_id=service_option_id,
                is_default=True,
                is_required=is_required
            )
            db.add(plan_option)
            db.commit()
            db.refresh(plan_option)
            logger.info(f"Service option {service_option_id} added to plan {plan_id}")
            return plan_option
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to add service option to plan: {str(e)}")
            raise
    
    def remove_service_option_from_plan(self, db: Session, plan_id: int, service_option_id: int) -> bool:
        """Remove service option from plan"""
        try:
            plan_option = db.query(PlanServiceOption).filter(
                PlanServiceOption.plan_id == plan_id,
                PlanServiceOption.service_option_id == service_option_id
            ).first()
            
            if not plan_option:
                return False
            
            db.delete(plan_option)
            db.commit()
            logger.info(f"Service option {service_option_id} removed from plan {plan_id}")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to remove service option from plan: {str(e)}")
            raise


plan_service = PlanService()
