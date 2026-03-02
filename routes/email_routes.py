from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from config.mysql_database import get_mysql_db
from services.email_service import send_welcome_email, send_esim_qr_email, send_order_confirmation_email
from models.mysql_models import Customer
from utils.logger import logger

router = APIRouter(prefix="/api/v1/email", tags=["Email Service"])


class WelcomeEmailRequest(BaseModel):
    customer_email: EmailStr
    customer_name: str = "Customer"


class QRCodeEmailRequest(BaseModel):
    customer_email: EmailStr
    child_name: str
    mobile_number: str
    iccid: str
    qr_code: str


class OrderConfirmationRequest(BaseModel):
    customer_email: EmailStr
    customer_name: str
    order_number: str
    plan_name: str
    number_of_children: int
    total_amount: float
    currency: str = "GBP"
    invoice_url: Optional[str] = None


class EmailResponse(BaseModel):
    success: bool
    message: str
    recipient: str


@router.post("/send-welcome", response_model=EmailResponse)
def send_welcome_email_endpoint(
    email_request: WelcomeEmailRequest,
    db: Session = Depends(get_mysql_db)
):
    """Send welcome email after customer registration"""
    try:
        result = send_welcome_email(
            customer_email=str(email_request.customer_email),
            customer_name=email_request.customer_name
        )
        
        if result:
            return EmailResponse(
                success=True,
                message="Welcome email sent successfully",
                recipient=str(email_request.customer_email)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send welcome email"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending welcome email: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send welcome email: {str(e)}"
        )


@router.post("/send-qr-code", response_model=EmailResponse)
def send_qr_code_email_endpoint(
    email_request: QRCodeEmailRequest,
    db: Session = Depends(get_mysql_db)
):
    """Send QR code email for eSIM activation"""
    try:
        from utils.qr_generator import generate_qr_code
        
        # Generate QR code image
        qr_image_bytes = generate_qr_code(email_request.qr_code, size=200)
        
        result = send_esim_qr_email(
            customer_email=str(email_request.customer_email),
            child_name=email_request.child_name,
            mobile_number=email_request.mobile_number,
            iccid=email_request.iccid,
            qr_code=email_request.qr_code,
            qr_image_bytes=qr_image_bytes
        )
        
        if result:
            return EmailResponse(
                success=True,
                message="QR code email sent successfully",
                recipient=str(email_request.customer_email)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send QR code email"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending QR code email: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send QR code email: {str(e)}"
        )


@router.post("/send-order-confirmation", response_model=EmailResponse)
def send_order_confirmation_endpoint(
    email_request: OrderConfirmationRequest,
    db: Session = Depends(get_mysql_db)
):
    """Send order confirmation email with optional invoice link"""
    try:
        result = send_order_confirmation_email(
            customer_email=str(email_request.customer_email),
            customer_name=email_request.customer_name,
            order_number=email_request.order_number,
            plan_name=email_request.plan_name,
            number_of_children=email_request.number_of_children,
            total_amount=email_request.total_amount,
            currency=email_request.currency,
            invoice_url=email_request.invoice_url
        )
        
        if result:
            return EmailResponse(
                success=True,
                message="Order confirmation email sent successfully",
                recipient=str(email_request.customer_email)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send order confirmation email"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending order confirmation email: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send order confirmation email: {str(e)}"
        )


@router.post("/send-activation-notification", response_model=EmailResponse)
def send_activation_notification_endpoint(
    customer_id: int = Query(..., description="Customer ID"),
    sim_id: str = Query(..., description="SIM ICCID"),
    activation_code: str = Query(..., description="eSIM activation code (LPA string)"),
    msisdn: Optional[str] = Query(None, description="Mobile number (optional)"),
    db: Session = Depends(get_mysql_db)
):
    """Send activation notification email with QR code for a specific SIM"""
    try:
        from utils.qr_generator import generate_qr_code
        from models.mysql_models import ChildSimCard
        
        # Get customer
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer with ID {customer_id} not found"
            )
        
        # Find the SIM card by ICCID
        sim_card = db.query(ChildSimCard).filter(ChildSimCard.iccid == sim_id).first()
        
        if not sim_card:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"SIM card with ICCID {sim_id} not found"
            )
        
        # Use provided MSISDN or get from SIM card
        mobile_number = msisdn or sim_card.msisdn or "Pending"
        
        # Generate QR code
        qr_image_bytes = generate_qr_code(activation_code, size=200)
        
        # Send email
        result = send_esim_qr_email(
            customer_email=customer.email,
            child_name=sim_card.child_name,
            mobile_number=mobile_number,
            iccid=sim_id,
            qr_code=activation_code,
            qr_image_bytes=qr_image_bytes
        )
        
        if result:
            return EmailResponse(
                success=True,
                message=f"Activation notification sent successfully to {customer.email}",
                recipient=customer.email
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send activation notification"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending activation notification: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send activation notification: {str(e)}"
        )


@router.post("/test")
def test_email_service(
    test_email: EmailStr = Query(..., description="Email address to send test email to"),
    db: Session = Depends(get_mysql_db)
):
    """Test email service by sending a test email"""
    try:
        from services.email_service import send_email
        
        test_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Test Email</title>
        </head>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>Email Service Test</h2>
            <p>This is a test email from ARVO Mobile API.</p>
            <p>If you received this email, the email service is working correctly!</p>
            <p style="color: #666; font-size: 12px; margin-top: 30px;">
                Sent at: {datetime}
            </p>
        </body>
        </html>
        """.format(datetime=str(__import__('datetime').datetime.now()))
        
        result = send_email(
            to_email=str(test_email),
            subject="ARVO Email Service Test",
            body_html=test_html
        )
        
        if result:
            return {
                "success": True,
                "message": f"Test email sent successfully to {test_email}",
                "recipient": str(test_email)
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send test email"
            )
        
    except Exception as e:
        logger.error(f"Error testing email service: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test email service: {str(e)}"
        )


@router.get("/config")
def get_email_config():
    """Get current email service configuration (without sensitive data)"""
    try:
        from services.email_service import SMTP_HOST, SMTP_PORT, SMTP_USER
        
        return {
            "success": True,
            "config": {
                "smtp_host": SMTP_HOST,
                "smtp_port": SMTP_PORT,
                "smtp_user": SMTP_USER,
                "default_bcc": ["akg6595@gmail.com"]
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting email config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get email configuration: {str(e)}"
        )