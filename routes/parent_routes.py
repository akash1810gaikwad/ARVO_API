from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from config.mysql_database import get_mysql_db
from models.mysql_models import ChildAlert, ChildSimCard, Customer
from middleware.auth import get_current_user
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from utils.logger import logger

router = APIRouter(prefix="/api/parent", tags=["Parent"])


# ============= RESPONSE MODELS =============

class AlertResponse(BaseModel):
    id: int
    type: str
    message: str
    msisdn: str
    child_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    battery_level: Optional[int] = None
    is_read: bool
    created_at: str
    
    class Config:
        from_attributes = True


# ============= ENDPOINTS =============

@router.get("/alerts", response_model=List[AlertResponse])
async def get_parent_alerts(
    msisdn: Optional[str] = None,
    unread_only: bool = False,
    limit: int = 50,
    current_user: Customer = Depends(get_current_user),
    db: Session = Depends(get_mysql_db)
):
    """
    Get all alerts for the authenticated parent
    Optionally filter by child's MSISDN and unread status
    """
    try:
        logger.info(f"Fetching alerts for customer: {current_user.id}")
        
        # Build query
        query = db.query(ChildAlert).filter(
            ChildAlert.customer_id == current_user.id
        )
        
        # Filter by MSISDN if provided
        if msisdn:
            query = query.filter(ChildAlert.msisdn == msisdn)
        
        # Filter unread only
        if unread_only:
            query = query.filter(ChildAlert.is_read == False)
        
        # Order by most recent first and limit
        alerts = query.order_by(ChildAlert.created_at.desc()).limit(limit).all()
        
        # Format response
        result = []
        for alert in alerts:
            # Get child name if available
            child_name = None
            if alert.child_sim_card_id:
                child_sim = db.query(ChildSimCard).filter(
                    ChildSimCard.id == alert.child_sim_card_id
                ).first()
                if child_sim:
                    child_name = child_sim.child_name
            
            result.append(AlertResponse(
                id=alert.id,
                type=alert.alert_type,
                message=alert.message,
                msisdn=alert.msisdn,
                child_name=child_name,
                latitude=float(alert.latitude) if alert.latitude else None,
                longitude=float(alert.longitude) if alert.longitude else None,
                battery_level=alert.battery_level,
                is_read=alert.is_read,
                created_at=alert.created_at.strftime("%Y-%m-%d %H:%M:%S")
            ))
        
        logger.info(f"Found {len(result)} alerts for customer {current_user.id}")
        return result
        
    except Exception as e:
        logger.error(f"Error fetching alerts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch alerts: {str(e)}"
        )


@router.put("/alerts/{alert_id}/read")
async def mark_alert_as_read(
    alert_id: int,
    current_user: Customer = Depends(get_current_user),
    db: Session = Depends(get_mysql_db)
):
    """
    Mark an alert as read
    """
    try:
        alert = db.query(ChildAlert).filter(
            ChildAlert.id == alert_id,
            ChildAlert.customer_id == current_user.id
        ).first()
        
        if not alert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found"
            )
        
        alert.is_read = True
        alert.read_at = datetime.utcnow()
        db.commit()
        
        return {"success": True, "message": "Alert marked as read"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking alert as read: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark alert as read: {str(e)}"
        )


@router.put("/alerts/read-all")
async def mark_all_alerts_as_read(
    msisdn: Optional[str] = None,
    current_user: Customer = Depends(get_current_user),
    db: Session = Depends(get_mysql_db)
):
    """
    Mark all alerts as read for the authenticated parent
    Optionally filter by child's MSISDN
    """
    try:
        query = db.query(ChildAlert).filter(
            ChildAlert.customer_id == current_user.id,
            ChildAlert.is_read == False
        )
        
        if msisdn:
            query = query.filter(ChildAlert.msisdn == msisdn)
        
        count = query.update({
            "is_read": True,
            "read_at": datetime.utcnow()
        })
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Marked {count} alerts as read"
        }
        
    except Exception as e:
        logger.error(f"Error marking all alerts as read: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark alerts as read: {str(e)}"
        )



# ============= LOCATION TRACKING =============

class ChildLocationResponse(BaseModel):
    msisdn: str
    latitude: float
    longitude: float
    speed: Optional[float] = None
    battery: Optional[int] = None
    accuracy: Optional[float] = None
    created_at: str
    
    class Config:
        from_attributes = True


class ChildInfo(BaseModel):
    id: int
    name: str
    age: int
    msisdn: str
    status: str
    last_location: Optional[dict] = None
    battery: Optional[int] = None
    last_seen: Optional[str] = None


@router.get("/location/{msisdn}", response_model=ChildLocationResponse)
async def get_child_location(
    msisdn: str,
    current_user: Customer = Depends(get_current_user),
    db: Session = Depends(get_mysql_db)
):
    """
    Get latest location for a child by MSISDN
    Used by parent dashboard to track child's location
    """
    try:
        from models.mysql_models import ChildLocation, ChildSimCard, Subscriber
        
        logger.info(f"Parent {current_user.id} fetching location for MSISDN: {msisdn}")
        
        # Verify child belongs to this parent
        subscriber = db.query(Subscriber).filter(
            Subscriber.customer_id == current_user.id,
            Subscriber.is_active == True
        ).first()
        
        if not subscriber:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active subscription found"
            )
        
        # Verify child SIM exists and belongs to this parent
        child_sim = db.query(ChildSimCard).filter(
            ChildSimCard.msisdn == msisdn,
            ChildSimCard.subscriber_id == subscriber.id,
            ChildSimCard.is_active == True
        ).first()
        
        if not child_sim:
            logger.warning(f"Child SIM not found or doesn't belong to parent {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Child not found or doesn't belong to you"
            )
        
        # Get latest location
        latest_location = db.query(ChildLocation).filter(
            ChildLocation.msisdn == msisdn
        ).order_by(ChildLocation.created_at.desc()).first()
        
        if not latest_location:
            logger.warning(f"No location data found for MSISDN: {msisdn}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No location data available"
            )
        
        logger.info(f"Found location for MSISDN: {msisdn}")
        
        return ChildLocationResponse(
            msisdn=latest_location.msisdn,
            latitude=float(latest_location.latitude),
            longitude=float(latest_location.longitude),
            speed=float(latest_location.speed) if latest_location.speed else None,
            battery=latest_location.battery,
            accuracy=float(latest_location.accuracy) if latest_location.accuracy else None,
            created_at=latest_location.created_at.strftime("%Y-%m-%d %H:%M:%S")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching location: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch location: {str(e)}"
        )


@router.get("/children", response_model=List[ChildInfo])
async def get_parent_children(
    current_user: Customer = Depends(get_current_user),
    db: Session = Depends(get_mysql_db)
):
    """
    Get all children for the authenticated parent
    Returns list of children with their latest location and status
    """
    try:
        from models.mysql_models import ChildLocation, ChildSimCard, Subscriber
        from datetime import datetime, timedelta
        
        logger.info(f"Fetching children for customer: {current_user.id}")
        
        # Get subscriber for this customer
        subscriber = db.query(Subscriber).filter(
            Subscriber.customer_id == current_user.id,
            Subscriber.is_active == True
        ).first()
        
        if not subscriber:
            logger.warning(f"No subscriber found for customer: {current_user.id}")
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
            children_list.append(ChildInfo(
                id=child_sim.id,
                name=child_sim.child_name,
                age=child_sim.child_age,
                msisdn=child_sim.msisdn,
                status=status,
                last_location=last_location_data,
                battery=battery,
                last_seen=last_seen
            ))
        
        logger.info(f"Found {len(children_list)} children for customer: {current_user.id}")
        
        return children_list
        
    except Exception as e:
        logger.error(f"Error fetching children: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch children: {str(e)}"
        )
