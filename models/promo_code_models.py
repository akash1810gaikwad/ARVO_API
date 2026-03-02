from sqlalchemy import Column, Integer, String, Boolean, Text, DECIMAL, DateTime
from sqlalchemy.sql import func
from config.mysql_database import MySQLBase


class PromoCode(MySQLBase):
    """Promo code table for subscription discounts and special handling"""
    __tablename__ = "promo_codes"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    message = Column(Text, nullable=True, comment="Message to display when promo is applied")
    
    # Validation settings
    is_active = Column(Boolean, default=True, nullable=False, comment="Whether promo code is currently active")
    valid_from = Column(DateTime, nullable=True, comment="Start date for promo validity")
    valid_until = Column(DateTime, nullable=True, comment="End date for promo validity")
    max_uses = Column(Integer, nullable=True, comment="Maximum number of times this promo can be used")
    current_uses = Column(Integer, default=0, nullable=False, comment="Current number of times used")
    
    # Payment bypass settings
    bypass_payment = Column(Boolean, default=False, nullable=False, comment="If True, skip Stripe payment and create dummy payment")
    activate_sim = Column(Boolean, default=True, nullable=False, comment="If True, activate SIM; If False, allocate but don't activate")
    
    # Discount settings (for future use)
    discount_type = Column(String(20), nullable=True, comment="PERCENTAGE, FIXED_AMOUNT, or NULL")
    discount_value = Column(DECIMAL(10, 2), nullable=True, comment="Discount amount or percentage")
    
    # Metadata
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(String(100), nullable=True, comment="Admin who created this promo")
    
    def __repr__(self):
        return f"<PromoCode(code='{self.code}', bypass_payment={self.bypass_payment}, activate_sim={self.activate_sim})>"
