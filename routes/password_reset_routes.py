from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging
import random
import string
from datetime import datetime, timedelta, timezone

from config.mysql_database import get_mysql_db
from models.mysql_models import Customer
from models.mysql_models import PasswordResetOTP
from schemas.password_reset_schema import (
    ForgotPasswordRequest, ForgotPasswordResponse,
    ResetPasswordRequest, ResetPasswordResponse
)
from services.email_service import send_password_reset_otp_email
from services.customer_service import customer_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/password-reset", tags=["Password Reset"])


def generate_otp() -> str:
    """Generate a 6-digit OTP"""
    return ''.join(random.choices(string.digits, k=6))


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_mysql_db)
):
    """Send OTP to email for password reset"""
    try:
        # Check if customer exists
        customer = db.query(Customer).filter(Customer.email == request.email).first()
        
        if not customer:
            # Don't reveal if email exists or not for security
            return ForgotPasswordResponse(
                success=True,
                message="If the email exists, an OTP has been sent to your email address."
            )
        
        # Generate OTP
        otp_code = generate_otp()
        
        # Set expiry time (10 minutes from now)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        
        # Invalidate any existing OTPs for this email
        db.query(PasswordResetOTP).filter(
            PasswordResetOTP.email == request.email,
            PasswordResetOTP.is_used == False
        ).update({"is_used": True})
        
        # Create new OTP record
        otp_record = PasswordResetOTP(
            email=request.email,
            otp_code=otp_code,
            expires_at=expires_at
        )
        db.add(otp_record)
        db.commit()
        
        # Send OTP email
        try:
            send_password_reset_otp_email(
                customer_email=customer.email,
                customer_name=customer.full_name or "Customer",
                otp_code=otp_code
            )
            logger.info(f"Password reset OTP sent to {customer.email}")
        except Exception as email_error:
            logger.error(f"Failed to send OTP email: {email_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send OTP email. Please try again."
            )
        
        return ForgotPasswordResponse(
            success=True,
            message="OTP has been sent to your email address. Please check your inbox."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in forgot password: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process password reset request: {str(e)}"
        )


@router.post("/reset-password", response_model=ResetPasswordResponse)
def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_mysql_db)
):
    """Reset password using OTP"""
    try:
        from sqlalchemy import text
        
        # Use raw SQL to check OTP validity with proper datetime handling (MySQL syntax)
        query = text("""
            SELECT id, email, otp_code, is_used, 
                   CASE WHEN expires_at > NOW() THEN 0 ELSE 1 END as is_expired
            FROM password_reset_otps
            WHERE email = :email 
              AND otp_code = :otp_code 
              AND is_used = 0
            ORDER BY created_at DESC
            LIMIT 1
        """)
        
        result = db.execute(query, {
            "email": request.email,
            "otp_code": request.otp_code
        }).fetchone()
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OTP code"
            )
        
        # Check if OTP is expired
        if result.is_expired:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP has expired. Please request a new one."
            )
        
        # Find customer
        customer = db.query(Customer).filter(Customer.email == request.email).first()
        
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found"
            )
        
        # Hash new password using the same method as registration
        hashed_password = customer_service.hash_password(request.new_password)
        
        # Update customer password
        customer.password_hash = hashed_password
        
        # Mark OTP as used using raw SQL
        update_query = text("""
            UPDATE password_reset_otps 
            SET is_used = 1 
            WHERE id = :otp_id
        """)
        db.execute(update_query, {"otp_id": result.id})
        
        db.commit()
        
        logger.info(f"Password reset successful for {customer.email}")
        
        return ResetPasswordResponse(
            success=True,
            message="Password has been reset successfully. You can now login with your new password."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in reset password: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset password: {str(e)}"
        )
