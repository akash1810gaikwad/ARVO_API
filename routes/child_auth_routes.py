from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from config.mysql_database import get_mysql_db
from models.mysql_models import ChildSimCard, Customer, Subscriber, ChildLoginOTP
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime, timedelta, timezone
import random
import string
from utils.logger import logger
from services.email_service import send_child_login_otp_email

router = APIRouter(prefix="/api/child", tags=["Child Authentication"])


def generate_otp() -> str:
    """Generate a 6-digit OTP"""
    return ''.join(random.choices(string.digits, k=6))


# ============= REQUEST MODELS =============

class ChildLoginRequest(BaseModel):
    mobile: str = Field(..., description="Child mobile number (MSISDN)")
    
    @validator('mobile')
    def validate_mobile(cls, v):
        # Remove any spaces or special characters
        cleaned = v.strip()
        
        if not cleaned:
            raise ValueError('Mobile number is required')
        
        return cleaned


class ChildLoginResponse(BaseModel):
    success: bool
    message: str
    masked_email: Optional[str] = None


class ChildVerifyOTPRequest(BaseModel):
    mobile: str = Field(..., description="Child mobile number (MSISDN)")
    otp: str = Field(..., description="6-digit OTP code")
    
    @validator('mobile')
    def validate_mobile(cls, v):
        cleaned = v.strip()
        if not cleaned:
            raise ValueError('Mobile number is required')
        return cleaned
    
    @validator('otp')
    def validate_otp(cls, v):
        if len(v) != 6 or not v.isdigit():
            raise ValueError('OTP must be exactly 6 digits')
        return v


class ChildVerifyOTPResponse(BaseModel):
    success: bool
    message: str
    access_token: Optional[str] = None
    child_data: Optional[dict] = None


# ============= ENDPOINTS =============

@router.post("/auth/login", response_model=ChildLoginResponse)
async def child_login(
    request: Request,
    login_data: ChildLoginRequest,
    db: Session = Depends(get_mysql_db)
):
    """
    Step 1: Child Login - Validate MSISDN and send OTP to parent's email
    """
    try:
        msisdn = login_data.mobile
        logger.info(f"Child login request for MSISDN: {msisdn}")
        
        # Find child SIM card by MSISDN
        child_sim = db.query(ChildSimCard).filter(
            ChildSimCard.msisdn == msisdn,
            ChildSimCard.is_active == True
        ).first()
        
        if not child_sim:
            logger.warning(f"Child SIM not found for MSISDN: {msisdn}")
            raise HTTPException(
                status_code=400,
                detail="Mobile number not found or inactive"
            )
        
        logger.info(f"Found child SIM: {child_sim.id}, Child: {child_sim.child_name}")
        
        # Get subscriber (parent) information
        subscriber = db.query(Subscriber).filter(
            Subscriber.id == child_sim.subscriber_id,
            Subscriber.is_active == True
        ).first()
        
        if not subscriber:
            logger.warning(f"Subscriber not found for child SIM: {msisdn}")
            raise HTTPException(
                status_code=400,
                detail="Parent information not found"
            )
        
        logger.info(f"Found subscriber: {subscriber.id}")
        
        # Get parent customer information
        customer = db.query(Customer).filter(
            Customer.id == subscriber.customer_id,
            Customer.is_active == True,
            Customer.is_deleted == False
        ).first()
        
        if not customer or not customer.email:
            logger.warning(f"Parent customer not found for MSISDN: {msisdn}")
            raise HTTPException(
                status_code=400,
                detail="Parent email not found"
            )
        
        logger.info(f"Found parent customer: {customer.id}, Email: {customer.email}")
        
        # Generate OTP
        otp_code = generate_otp()
        
        # Set expiry time (10 minutes from now)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        
        # Invalidate any existing OTPs for this MSISDN
        db.query(ChildLoginOTP).filter(
            ChildLoginOTP.msisdn == msisdn,
            ChildLoginOTP.is_used == False
        ).update({"is_used": True})
        db.commit()
        
        logger.info(f"Invalidated old OTPs for MSISDN: {msisdn}")
        
        # Create new OTP record
        otp_record = ChildLoginOTP(
            msisdn=msisdn,
            child_sim_card_id=child_sim.id,
            customer_id=customer.id,
            otp_code=otp_code,
            expires_at=expires_at
        )
        db.add(otp_record)
        db.commit()
        
        logger.info(f"Created new OTP record: {otp_record.id}")
        
        # Send OTP email to parent
        try:
            email_sent = send_child_login_otp_email(
                parent_email=customer.email,
                parent_name=customer.full_name or "Parent",
                child_name=child_sim.child_name,
                mobile_number=msisdn,
                otp_code=otp_code
            )
            
            if not email_sent:
                raise Exception("Email service returned False")
            
            logger.info(f"OTP email sent successfully to: {customer.email}")
            
        except Exception as email_error:
            logger.error(f"Failed to send OTP email: {email_error}")
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Failed to send OTP email. Please try again."
            )
        
        # Mask email for privacy (show first 3 chars and domain)
        email_parts = customer.email.split('@')
        masked_email = f"{email_parts[0][:3]}***@{email_parts[1]}" if len(email_parts) == 2 else "***"
        
        return {
            "success": True,
            "message": f"OTP has been sent to parent's email",
            "masked_email": masked_email
        }
        
    except HTTPException:
        raise
    except ValueError as ve:
        logger.error(f"Validation error: {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error in child login: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process login request: {str(e)}"
        )


@router.post("/auth/verify-otp", response_model=ChildVerifyOTPResponse)
async def child_verify_otp(
    request: Request,
    verify_data: ChildVerifyOTPRequest,
    db: Session = Depends(get_mysql_db)
):
    """
    Step 2: Verify OTP and complete child login
    """
    try:
        msisdn = verify_data.mobile
        otp_code = verify_data.otp
        
        logger.info(f"OTP verification request for MSISDN: {msisdn}")
        
        # Use raw SQL to check OTP validity with proper datetime handling
        query = text("""
            SELECT id, msisdn, child_sim_card_id, customer_id, otp_code, is_used, 
                   CASE WHEN expires_at > NOW() THEN 0 ELSE 1 END as is_expired
            FROM child_login_otps
            WHERE msisdn = :msisdn 
              AND otp_code = :otp_code 
              AND is_used = 0
            ORDER BY created_at DESC
            LIMIT 1
        """)
        
        result = db.execute(query, {
            "msisdn": msisdn,
            "otp_code": otp_code
        }).fetchone()
        
        if not result:
            logger.warning(f"Invalid OTP for MSISDN: {msisdn}")
            raise HTTPException(
                status_code=400,
                detail="Invalid OTP code"
            )
        
        # Check if OTP is expired
        if result.is_expired:
            logger.warning(f"Expired OTP for MSISDN: {msisdn}")
            raise HTTPException(
                status_code=400,
                detail="OTP has expired. Please request a new one."
            )
        
        # Get child SIM card details
        child_sim = db.query(ChildSimCard).filter(
            ChildSimCard.id == result.child_sim_card_id
        ).first()
        
        if not child_sim:
            raise HTTPException(
                status_code=400,
                detail="Child SIM card not found"
            )
        
        # Mark OTP as used
        update_query = text("""
            UPDATE child_login_otps 
            SET is_used = 1 
            WHERE id = :otp_id
        """)
        db.execute(update_query, {"otp_id": result.id})
        db.commit()
        
        logger.info(f"OTP marked as used for MSISDN: {msisdn}")
        
        # Generate access token (simple token for now)
        access_token = f"child_{child_sim.id}_{int(datetime.now().timestamp())}"
        
        logger.info(f"Child login successful for MSISDN: {msisdn}")
        
        return {
            "success": True,
            "message": "Login successful",
            "access_token": access_token,
            "child_data": {
                "id": child_sim.id,
                "child_name": child_sim.child_name,
                "child_age": child_sim.child_age,
                "msisdn": child_sim.msisdn,
                "iccid": child_sim.iccid,
                "sim_type": child_sim.sim_type
            }
        }
        
    except HTTPException:
        raise
    except ValueError as ve:
        logger.error(f"Validation error: {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error in OTP verification: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to verify OTP: {str(e)}"
        )



# ============= LOCATION TRACKING =============

class ChildLocationRequest(BaseModel):
    msisdn: str = Field(..., description="Child mobile number (MSISDN)")
    latitude: float = Field(..., description="Latitude coordinate")
    longitude: float = Field(..., description="Longitude coordinate")
    speed: Optional[float] = Field(default=0, description="Speed in m/s or km/h")
    battery: Optional[int] = Field(default=None, description="Battery percentage (0-100)")
    accuracy: Optional[float] = Field(default=None, description="Location accuracy in meters")
    
    @validator('msisdn')
    def validate_msisdn(cls, v):
        cleaned = v.strip()
        if not cleaned:
            raise ValueError('MSISDN is required')
        return cleaned
    
    @validator('latitude')
    def validate_latitude(cls, v):
        if v < -90 or v > 90:
            raise ValueError('Latitude must be between -90 and 90')
        return v
    
    @validator('longitude')
    def validate_longitude(cls, v):
        if v < -180 or v > 180:
            raise ValueError('Longitude must be between -180 and 180')
        return v
    
    @validator('battery')
    def validate_battery(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError('Battery must be between 0 and 100')
        return v


class ChildLocationResponse(BaseModel):
    success: bool
    message: str


class ChildLocationDataResponse(BaseModel):
    msisdn: str
    latitude: float
    longitude: float
    speed: Optional[float] = None
    battery: Optional[int] = None
    accuracy: Optional[float] = None
    created_at: str


@router.post("/location", response_model=ChildLocationResponse)
async def save_child_location(
    request: Request,
    location_data: ChildLocationRequest,
    db: Session = Depends(get_mysql_db)
):
    """
    Save child's current location
    Called every 10-20 seconds from child's device
    """
    try:
        from models.mysql_models import ChildLocation
        
        msisdn = location_data.msisdn
        logger.info(f"Received location for MSISDN: {msisdn}, Lat: {location_data.latitude}, Lng: {location_data.longitude}")
        
        # Verify child SIM exists (optional - for security)
        child_sim = db.query(ChildSimCard).filter(
            ChildSimCard.msisdn == msisdn,
            ChildSimCard.is_active == True
        ).first()
        
        if not child_sim:
            logger.warning(f"Location update from unknown MSISDN: {msisdn}")
            # You can choose to reject or accept unknown MSISDNs
            # For now, we'll accept but log the warning
        
        # Create location record
        location_record = ChildLocation(
            msisdn=msisdn,
            latitude=location_data.latitude,
            longitude=location_data.longitude,
            speed=location_data.speed or 0,
            battery=location_data.battery,
            accuracy=location_data.accuracy,
            provider='gps',
            created_at=datetime.utcnow()
        )
        
        db.add(location_record)
        db.commit()
        db.refresh(location_record)
        
        logger.info(f"Location saved successfully for MSISDN: {msisdn}, ID: {location_record.id}")
        
        return {
            "success": True,
            "message": "Location saved successfully"
        }
        
    except ValueError as ve:
        logger.error(f"Validation error: {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error saving location: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save location: {str(e)}"
        )



@router.get("/location/{msisdn}", response_model=ChildLocationDataResponse)
async def get_child_location(
    msisdn: str,
    request: Request,
    db: Session = Depends(get_mysql_db)
):
    """
    Get latest location for a child by MSISDN
    Used by parent dashboard to track child's location
    """
    try:
        from models.mysql_models import ChildLocation
        
        logger.info(f"Fetching latest location for MSISDN: {msisdn}")
        
        # Verify child SIM exists
        child_sim = db.query(ChildSimCard).filter(
            ChildSimCard.msisdn == msisdn,
            ChildSimCard.is_active == True
        ).first()
        
        if not child_sim:
            logger.warning(f"Child SIM not found for MSISDN: {msisdn}")
            raise HTTPException(
                status_code=404,
                detail="Child not found or inactive"
            )
        
        # Get latest location
        latest_location = db.query(ChildLocation).filter(
            ChildLocation.msisdn == msisdn
        ).order_by(ChildLocation.created_at.desc()).first()
        
        if not latest_location:
            logger.warning(f"No location data found for MSISDN: {msisdn}")
            raise HTTPException(
                status_code=404,
                detail="No location data available"
            )
        
        logger.info(f"Found location for MSISDN: {msisdn}, Lat: {latest_location.latitude}, Lng: {latest_location.longitude}")
        
        # Format created_at as string
        created_at_str = latest_location.created_at.strftime("%Y-%m-%d %H:%M:%S") if latest_location.created_at else ""
        
        return {
            "msisdn": latest_location.msisdn,
            "latitude": float(latest_location.latitude),
            "longitude": float(latest_location.longitude),
            "speed": float(latest_location.speed) if latest_location.speed else None,
            "battery": latest_location.battery,
            "accuracy": float(latest_location.accuracy) if latest_location.accuracy else None,
            "created_at": created_at_str
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching location: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch location: {str(e)}"
        )



# ============= PARENT - GET CHILDREN =============

class ChildInfo(BaseModel):
    id: int
    name: str
    age: int
    msisdn: str
    status: str
    last_location: Optional[dict] = None
    battery: Optional[int] = None
    last_seen: Optional[str] = None


@router.get("/children", response_model=list[ChildInfo])
async def get_parent_children(
    customer_id: str,
    request: Request,
    db: Session = Depends(get_mysql_db),
   
):
    """
    Get all children for the authenticated parent
    Returns list of children with their latest location and status
    """
    try:
        from models.mysql_models import ChildLocation
        from datetime import datetime, timedelta
        
        logger.info(f"Fetching children for customer: {customer_id}")
        
        # Get subscriber for this customer
        subscriber = db.query(Subscriber).filter(
            Subscriber.customer_id == customer_id,
            Subscriber.is_active == True
        ).first()
        
        if not subscriber:
            logger.warning(f"No subscriber found for customer: {customer_id}")
            return []
        
        # Get all child SIM cards for this subscriber
        child_sims = db.query(ChildSimCard).filter(
            ChildSimCard.subscriber_id == subscriber.id,
            ChildSimCard.is_active == True
        ).all()
        
        if not child_sims:
            logger.info(f"No children found for subscriber: {subscriber.id}")
            return []
        
        children_list = []
        
        for child_sim in child_sims:
            # Get latest location for this child
            latest_location = db.query(ChildLocation).filter(
                ChildLocation.msisdn == child_sim.msisdn
            ).order_by(ChildLocation.created_at.desc()).first()
            
            # Determine online status (online if location updated in last 2 minutes)
            status = "offline"
            last_seen = None
            last_location_data = None
            battery = None
            
            if latest_location:
                # Check if location is recent (within 2 minutes)
                time_diff = datetime.utcnow() - latest_location.created_at
                if time_diff.total_seconds() < 120:  # 2 minutes
                    status = "online"
                
                last_seen = latest_location.created_at.strftime("%Y-%m-%d %H:%M:%S")
                
                # Include location data
                last_location_data = {
                    "latitude": float(latest_location.latitude),
                    "longitude": float(latest_location.longitude)
                }
                
                battery = latest_location.battery
            
            # Build child info
            child_info = {
                "id": child_sim.id,
                "name": child_sim.child_name,
                "age": child_sim.child_age,
                "msisdn": child_sim.msisdn,
                "status": status,
                "last_location": last_location_data,
                "battery": battery,
                "last_seen": last_seen
            }
            
            children_list.append(child_info)
        
        logger.info(f"Found {len(children_list)} children for customer: {customer_id}")
        
        return children_list
        
    except Exception as e:
        logger.error(f"Error fetching children: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch children: {str(e)}"
        )



# ============= SOS ALERT =============

class SOSRequest(BaseModel):
    msisdn: str = Field(..., description="Child mobile number (MSISDN)")
    message: str = Field(default="Emergency SOS triggered", description="SOS message")
    latitude: Optional[float] = Field(None, description="Current latitude")
    longitude: Optional[float] = Field(None, description="Current longitude")
    
    @validator('msisdn')
    def validate_msisdn(cls, v):
        cleaned = v.strip()
        if not cleaned:
            raise ValueError('MSISDN is required')
        return cleaned


@router.post("/sos")
async def send_sos_alert(
    request: SOSRequest,
    db: Session = Depends(get_mysql_db)
):
    """
    Child sends SOS alert
    Creates an alert and optionally sends push notification
    """
    try:
        from models.mysql_models import ChildAlert, ChildHeartbeat
        
        logger.info(f"SOS alert received from: {request.msisdn}")
        
        # Find child SIM card
        child_sim = db.query(ChildSimCard).filter(
            ChildSimCard.msisdn == request.msisdn,
            ChildSimCard.is_active == True
        ).first()
        
        if not child_sim:
            logger.warning(f"Child SIM not found for MSISDN: {request.msisdn}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Child SIM card not found"
            )
        
        # Get customer ID from subscriber
        customer_id = child_sim.subscriber.customer_id if child_sim.subscriber else None
        
        # Get battery level from heartbeat if available
        battery_level = None
        heartbeat = db.query(ChildHeartbeat).filter(
            ChildHeartbeat.msisdn == request.msisdn
        ).first()
        if heartbeat:
            battery_level = heartbeat.battery_level
        
        # Create SOS alert
        alert = ChildAlert(
            msisdn=request.msisdn,
            child_sim_card_id=child_sim.id,
            customer_id=customer_id,
            alert_type="SOS",
            message=request.message,
            latitude=request.latitude,
            longitude=request.longitude,
            battery_level=battery_level,
            is_read=False
        )
        
        db.add(alert)
        db.commit()
        db.refresh(alert)
        
        logger.info(f"SOS alert created with ID: {alert.id}")
        
        # TODO: Send push notification to parent
        # await send_push_notification(customer_id, alert)
        
        return {
            "success": True,
            "message": "SOS alert sent successfully",
            "alert_id": alert.id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending SOS alert: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send SOS alert: {str(e)}"
        )


# ============= HEARTBEAT =============

class HeartbeatRequest(BaseModel):
    msisdn: str = Field(..., description="Child mobile number (MSISDN)")
    battery: Optional[int] = Field(None, description="Battery level (0-100)", ge=0, le=100)
    
    @validator('msisdn')
    def validate_msisdn(cls, v):
        cleaned = v.strip()
        if not cleaned:
            raise ValueError('MSISDN is required')
        return cleaned


@router.post("/heartbeat")
async def update_heartbeat(
    request: HeartbeatRequest,
    db: Session = Depends(get_mysql_db)
):
    """
    Child sends heartbeat every 30 seconds
    Used to detect online/offline status
    """
    try:
        from models.mysql_models import ChildHeartbeat, ChildAlert
        
        logger.debug(f"Heartbeat received from: {request.msisdn}")
        
        # Find child SIM card
        child_sim = db.query(ChildSimCard).filter(
            ChildSimCard.msisdn == request.msisdn,
            ChildSimCard.is_active == True
        ).first()
        
        if not child_sim:
            logger.warning(f"Child SIM not found for MSISDN: {request.msisdn}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Child SIM card not found"
            )
        
        # Update or create heartbeat
        heartbeat = db.query(ChildHeartbeat).filter(
            ChildHeartbeat.msisdn == request.msisdn
        ).first()
        
        now = datetime.utcnow()
        
        if heartbeat:
            # Check if was offline and now coming online
            was_offline = not heartbeat.is_online
            
            heartbeat.last_heartbeat_at = now
            heartbeat.is_online = True
            heartbeat.updated_at = now
            
            if request.battery is not None:
                old_battery = heartbeat.battery_level
                heartbeat.battery_level = request.battery
                
                # Create low battery alert if battery drops below 10%
                if request.battery <= 10 and (old_battery is None or old_battery > 10):
                    customer_id = child_sim.subscriber.customer_id if child_sim.subscriber else None
                    alert = ChildAlert(
                        msisdn=request.msisdn,
                        child_sim_card_id=child_sim.id,
                        customer_id=customer_id,
                        alert_type="BATTERY_LOW",
                        message=f"Battery below 10% ({request.battery}%)",
                        battery_level=request.battery,
                        is_read=False
                    )
                    db.add(alert)
                    logger.info(f"Low battery alert created for {request.msisdn}")
            
            # Create alert if device came back online
            if was_offline:
                customer_id = child_sim.subscriber.customer_id if child_sim.subscriber else None
                alert = ChildAlert(
                    msisdn=request.msisdn,
                    child_sim_card_id=child_sim.id,
                    customer_id=customer_id,
                    alert_type="ONLINE",
                    message=f"{child_sim.child_name}'s device is back online",
                    battery_level=request.battery,
                    is_read=False
                )
                db.add(alert)
                logger.info(f"Device online alert created for {request.msisdn}")
        else:
            # Create new heartbeat record
            heartbeat = ChildHeartbeat(
                msisdn=request.msisdn,
                child_sim_card_id=child_sim.id,
                last_heartbeat_at=now,
                battery_level=request.battery,
                is_online=True
            )
            db.add(heartbeat)
        
        db.commit()
        
        return {
            "success": True,
            "message": "Heartbeat updated",
            "is_online": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating heartbeat: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update heartbeat: {str(e)}"
        )


# ============= BATTERY UPDATE =============

class BatteryUpdateRequest(BaseModel):
    msisdn: str = Field(..., description="Child mobile number (MSISDN)")
    battery: int = Field(..., description="Battery level (0-100)", ge=0, le=100)
    
    @validator('msisdn')
    def validate_msisdn(cls, v):
        cleaned = v.strip()
        if not cleaned:
            raise ValueError('MSISDN is required')
        return cleaned


@router.post("/battery")
async def update_battery(
    request: BatteryUpdateRequest,
    db: Session = Depends(get_mysql_db)
):
    """
    Child sends battery level update
    Creates alert if battery is critically low
    """
    try:
        from models.mysql_models import ChildHeartbeat, ChildAlert
        
        logger.debug(f"Battery update received from: {request.msisdn} - {request.battery}%")
        
        # Find child SIM card
        child_sim = db.query(ChildSimCard).filter(
            ChildSimCard.msisdn == request.msisdn,
            ChildSimCard.is_active == True
        ).first()
        
        if not child_sim:
            logger.warning(f"Child SIM not found for MSISDN: {request.msisdn}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Child SIM card not found"
            )
        
        # Update heartbeat with battery level
        heartbeat = db.query(ChildHeartbeat).filter(
            ChildHeartbeat.msisdn == request.msisdn
        ).first()
        
        old_battery = None
        if heartbeat:
            old_battery = heartbeat.battery_level
            heartbeat.battery_level = request.battery
            heartbeat.last_heartbeat_at = datetime.utcnow()
            heartbeat.updated_at = datetime.utcnow()
        else:
            # Create heartbeat if doesn't exist
            heartbeat = ChildHeartbeat(
                msisdn=request.msisdn,
                child_sim_card_id=child_sim.id,
                last_heartbeat_at=datetime.utcnow(),
                battery_level=request.battery,
                is_online=True
            )
            db.add(heartbeat)
        
        # Create low battery alert if battery drops below 10%
        if request.battery <= 10 and (old_battery is None or old_battery > 10):
            customer_id = child_sim.subscriber.customer_id if child_sim.subscriber else None
            alert = ChildAlert(
                msisdn=request.msisdn,
                child_sim_card_id=child_sim.id,
                customer_id=customer_id,
                alert_type="BATTERY_LOW",
                message=f"Battery critically low: {request.battery}%",
                battery_level=request.battery,
                is_read=False
            )
            db.add(alert)
            logger.info(f"Low battery alert created for {request.msisdn}")
        
        db.commit()
        
        return {
            "success": True,
            "message": "Battery level updated",
            "battery": request.battery
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating battery: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update battery: {str(e)}"
        )
