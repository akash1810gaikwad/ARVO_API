from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, Tuple
from models.promo_code_models import PromoCode
from utils.logger import logger


class PromoCodeService:
    """Service for promo code validation and management"""
    
    def validate_promo_code(self, db: Session, code: str) -> Tuple[bool, str, Optional[PromoCode]]:
        """
        Validate a promo code
        
        Returns:
            Tuple of (is_valid, message, promo_code_object)
        """
        if not code or code.strip() == "":
            return False, "Promo code is empty", None
        
        # Find promo code
        promo = db.query(PromoCode).filter(PromoCode.code == code.strip()).first()
        
        if not promo:
            return False, "Invalid promo code", None
        
        # Check if active
        if not promo.is_active:
            return False, "This promo code is no longer active", None
        
        # Check validity dates
        now = datetime.utcnow()
        
        if promo.valid_from and now < promo.valid_from:
            return False, "This promo code is not yet valid", None
        
        if promo.valid_until and now > promo.valid_until:
            return False, "This promo code has expired", None
        
        # Check usage limit
        if promo.max_uses is not None and promo.current_uses >= promo.max_uses:
            return False, "This promo code has reached its usage limit", None
        
        # Valid promo code
        message = promo.message or "Promo code applied successfully"
        return True, message, promo
    
    def increment_usage(self, db: Session, promo_code_id: int) -> bool:
        """Increment the usage count for a promo code"""
        try:
            promo = db.query(PromoCode).filter(PromoCode.id == promo_code_id).first()
            if promo:
                promo.current_uses += 1
                db.commit()
                logger.info(f"Incremented usage for promo code {promo.code}: {promo.current_uses}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error incrementing promo code usage: {e}")
            db.rollback()
            return False
    
    def create_promo_code(self, db: Session, promo_data: dict) -> Optional[PromoCode]:
        """Create a new promo code"""
        try:
            promo = PromoCode(**promo_data)
            db.add(promo)
            db.commit()
            db.refresh(promo)
            logger.info(f"Created promo code: {promo.code}")
            return promo
        except Exception as e:
            logger.error(f"Error creating promo code: {e}")
            db.rollback()
            return None
    
    def update_promo_code(self, db: Session, code: str, update_data: dict) -> Optional[PromoCode]:
        """Update an existing promo code"""
        try:
            promo = db.query(PromoCode).filter(PromoCode.code == code).first()
            if not promo:
                return None
            
            for key, value in update_data.items():
                if value is not None and hasattr(promo, key):
                    setattr(promo, key, value)
            
            db.commit()
            db.refresh(promo)
            logger.info(f"Updated promo code: {promo.code}")
            return promo
        except Exception as e:
            logger.error(f"Error updating promo code: {e}")
            db.rollback()
            return None
    
    def get_all_promo_codes(self, db: Session, active_only: bool = False) -> list:
        """Get all promo codes"""
        query = db.query(PromoCode)
        if active_only:
            query = query.filter(PromoCode.is_active == True)
        return query.order_by(PromoCode.created_at.desc()).all()
    
    def get_promo_code_by_code(self, db: Session, code: str) -> Optional[PromoCode]:
        """Get a promo code by its code"""
        return db.query(PromoCode).filter(PromoCode.code == code).first()
    
    def delete_promo_code(self, db: Session, code: str) -> bool:
        """Delete a promo code"""
        try:
            promo = db.query(PromoCode).filter(PromoCode.code == code).first()
            if not promo:
                return False
            
            db.delete(promo)
            db.commit()
            logger.info(f"Deleted promo code: {code}")
            return True
        except Exception as e:
            logger.error(f"Error deleting promo code: {e}")
            db.rollback()
            return False


# Singleton instance
promo_code_service = PromoCodeService()
