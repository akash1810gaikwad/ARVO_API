from sqlalchemy import Column, BigInteger, String, Text, DateTime, Boolean
from sqlalchemy.sql import func
from config.mysql_database import MySQLBase
from datetime import datetime


class WhopWebhookLog(MySQLBase):
    """Model for logging all incoming Whop webhook events"""
    __tablename__ = "whop_webhook_logs"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    
    # Webhook details
    event_type = Column(String(100), nullable=False, index=True)
    event_id = Column(String(255), nullable=True, index=True)
    
    # Request details
    raw_payload = Column(Text, nullable=False)  # Full JSON payload
    signature = Column(String(500), nullable=True)
    signature_valid = Column(Boolean, default=False)
    
    # Processing details
    status = Column(String(50), default="RECEIVED")  # RECEIVED, PROCESSED, FAILED
    error_message = Column(Text, nullable=True)
    
    # Extracted data (for quick reference)
    membership_id = Column(String(255), nullable=True, index=True)
    customer_email = Column(String(255), nullable=True, index=True)
    plan_id = Column(String(255), nullable=True)
    amount = Column(String(50), nullable=True)
    currency = Column(String(10), nullable=True)
    
    # Timestamps
    received_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<WhopWebhookLog(id={self.id}, event_type={self.event_type}, status={self.status})>"
