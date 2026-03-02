from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional
import json

from config.mysql_database import get_mysql_db
from schemas.order_schema import (
    OrderCreate, OrderUpdate, OrderResponse, 
    OrderWithDetails, OrderSummary
)
from schemas.audit_schema import AuditLogCreate
from services.order_service import order_service
from services.audit_service import audit_service
from utils.logger import logger

router = APIRouter(prefix="/api/orders", tags=["Orders"])


@router.post("/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    request: Request,
    order_data: OrderCreate,
    db: Session = Depends(get_mysql_db)
):
    """Create a new order"""
    try:
        order = order_service.create_order(db, order_data)
        
        if not order:
            raise HTTPException(status_code=500, detail="Failed to create order")
        
        # Create audit log
        await audit_service.create_audit_log(AuditLogCreate(
            user_id=order_data.customer_id,
            action="CREATE_ORDER",
            resource="Order",
            resource_id=str(order.id),
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            metadata={
                "order_number": order.order_number,
                "order_type": order_data.order_type,
                "total_amount": float(order_data.total_amount)
            }
        ))
        
        return order
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating order: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create order")


@router.get("/{order_id}", response_model=OrderWithDetails)
def get_order(order_id: int, db: Session = Depends(get_mysql_db)):
    """Get order by ID with full details"""
    order = order_service.get_order_by_id(db, order_id)
    
    if not order:
        return JSONResponse(
            status_code=200,
            content={"message": "Order not found", "data": None}
        )
    
    # Parse order items JSON
    order_dict = OrderWithDetails.model_validate(order).model_dump()
    if order.order_items:
        try:
            order_dict["order_items"] = json.loads(order.order_items)
        except:
            order_dict["order_items"] = []
    
    # Add customer info
    if order.customer:
        order_dict["customer_email"] = order.customer.email
        order_dict["customer_name"] = order.customer.full_name
    
    return order_dict


@router.get("/number/{order_number}", response_model=OrderWithDetails)
def get_order_by_number(order_number: str, db: Session = Depends(get_mysql_db)):
    """Get order by order number"""
    order = order_service.get_order_by_number(db, order_number)
    
    if not order:
        return JSONResponse(
            status_code=200,
            content={"message": "Order not found", "data": None}
        )
    
    # Parse order items JSON
    order_dict = OrderWithDetails.model_validate(order).model_dump()
    if order.order_items:
        try:
            order_dict["order_items"] = json.loads(order.order_items)
        except:
            order_dict["order_items"] = []
    
    # Add customer info
    if order.customer:
        order_dict["customer_email"] = order.customer.email
        order_dict["customer_name"] = order.customer.full_name
    
    return order_dict


@router.get("/customer/{customer_id}", response_model=list[OrderSummary])
def get_customer_orders(
    customer_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_mysql_db)
):
    """Get all orders for a customer"""
    orders = order_service.get_customer_orders(db, customer_id, skip, limit)
    
    # Add customer name to each order
    result = []
    for order in orders:
        order_dict = OrderSummary.model_validate(order).model_dump()
        if order.customer:
            order_dict["customer_name"] = order.customer.full_name
        result.append(order_dict)
    
    return result


@router.get("/status/{status}", response_model=list[OrderSummary])
def get_orders_by_status(
    status: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_mysql_db)
):
    """Get orders by status"""
    try:
        from models.mysql_models import OrderStatus
        order_status = OrderStatus(status.upper())
        orders = order_service.get_orders_by_status(db, order_status, skip, limit)
        
        # Add customer name to each order
        result = []
        for order in orders:
            order_dict = OrderSummary.model_validate(order).model_dump()
            if order.customer:
                order_dict["customer_name"] = order.customer.full_name
            result.append(order_dict)
        
        return result
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid order status")


@router.put("/{order_id}", response_model=OrderResponse)
async def update_order(
    request: Request,
    order_id: int,
    order_data: OrderUpdate,
    db: Session = Depends(get_mysql_db)
):
    """Update order status and details"""
    try:
        order = order_service.update_order(db, order_id, order_data)
        
        if not order:
            return JSONResponse(
                status_code=200,
                content={"message": "Order not found", "data": None}
            )
        
        # Create audit log
        await audit_service.create_audit_log(AuditLogCreate(
            user_id=order.customer_id,
            action="UPDATE_ORDER",
            resource="Order",
            resource_id=str(order_id),
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            changes=order_data.model_dump(exclude_unset=True)
        ))
        
        return order
        
    except Exception as e:
        logger.error(f"Error updating order: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update order")


@router.post("/{order_id}/cancel")
async def cancel_order(
    request: Request,
    order_id: int,
    reason: Optional[str] = None,
    db: Session = Depends(get_mysql_db)
):
    """Cancel an order"""
    try:
        order = order_service.get_order_by_id(db, order_id)
        if not order:
            return JSONResponse(
                status_code=200,
                content={"message": "Order not found", "success": False}
            )
        
        success = order_service.cancel_order(db, order_id, reason)
        
        if success:
            # Create audit log
            await audit_service.create_audit_log(AuditLogCreate(
                user_id=order.customer_id,
                action="CANCEL_ORDER",
                resource="Order",
                resource_id=str(order_id),
                ip_address=request.client.host,
                user_agent=request.headers.get("user-agent"),
                metadata={"reason": reason}
            ))
        
        return {
            "message": "Order cancelled successfully" if success else "Failed to cancel order",
            "success": success
        }
        
    except Exception as e:
        logger.error(f"Error cancelling order: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to cancel order")


@router.get("/statistics/summary")
def get_order_statistics(
    customer_id: Optional[int] = None,
    db: Session = Depends(get_mysql_db)
):
    """Get order statistics"""
    stats = order_service.get_order_statistics(db, customer_id)
    return stats


@router.post("/{order_id}/link-subscription")
async def link_order_to_subscription(
    request: Request,
    order_id: int,
    subscription_id: int,
    subscriber_id: int,
    db: Session = Depends(get_mysql_db)
):
    """Link order to subscription (internal use after payment)"""
    try:
        success = order_service.link_order_to_subscription(
            db, order_id, subscription_id, subscriber_id
        )
        
        if success:
            order = order_service.get_order_by_id(db, order_id)
            # Create audit log
            await audit_service.create_audit_log(AuditLogCreate(
                user_id=order.customer_id,
                action="LINK_ORDER_SUBSCRIPTION",
                resource="Order",
                resource_id=str(order_id),
                ip_address=request.client.host,
                user_agent=request.headers.get("user-agent"),
                metadata={
                    "subscription_id": subscription_id,
                    "subscriber_id": subscriber_id
                }
            ))
        
        return {
            "message": "Order linked to subscription" if success else "Failed to link order",
            "success": success
        }
        
    except Exception as e:
        logger.error(f"Error linking order to subscription: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to link order")
