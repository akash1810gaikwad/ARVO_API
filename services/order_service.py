from typing import Optional, List
from sqlalchemy.orm import Session
from datetime import datetime
from decimal import Decimal
import json
import secrets

from models.mysql_models import Order, OrderStatus, PaymentStatus, DeliveryStatus
from models.mysql_models import Customer
from schemas.order_schema import OrderCreate, OrderUpdate
from utils.logger import logger


class OrderService:
    """Service for managing orders"""
    
    def generate_order_number(self) -> str:
        """Generate unique order number"""
        timestamp = datetime.utcnow().strftime("%Y%m%d")
        random_part = secrets.token_hex(4).upper()
        return f"ORD-{timestamp}-{random_part}"
    
    def create_order(self, db: Session, order_data: OrderCreate) -> Optional[Order]:
        """Create a new order"""
        try:
            # Generate order number
            order_number = self.generate_order_number()
            
            # Convert order items to JSON
            order_items_json = json.dumps([item.model_dump() for item in order_data.order_items])
            
            # Get plan name if plan_id provided
            plan_name = None
            if order_data.plan_id:
                from models.mysql_models import PlanMaster
                plan = db.query(PlanMaster).filter(PlanMaster.id == order_data.plan_id).first()
                if plan:
                    plan_name = plan.plan_name
            
            # Create order
            order = Order(
                customer_id=order_data.customer_id,
                order_number=order_number,
                order_type=order_data.order_type,
                order_status=OrderStatus.PENDING,
                plan_id=order_data.plan_id,
                plan_name=plan_name,
                billing_cycle=order_data.billing_cycle,
                subtotal=order_data.subtotal,
                tax_amount=order_data.tax_amount,
                discount_amount=order_data.discount_amount,
                total_amount=order_data.total_amount,
                quantity=len(order_data.order_items),
                number_of_children=order_data.number_of_children,
                payment_status=PaymentStatus.PENDING,
                shipping_address=order_data.shipping_address,
                shipping_city=order_data.shipping_city,
                shipping_postcode=order_data.shipping_postcode,
                shipping_country=order_data.shipping_country,
                delivery_status=DeliveryStatus.NOT_SHIPPED,
                order_items=order_items_json,
                customer_notes=order_data.customer_notes
            )
            
            db.add(order)
            db.commit()
            db.refresh(order)
            
            logger.info(f"Order created: {order.order_number}")
            return order
            
        except Exception as e:
            logger.error(f"Error creating order: {str(e)}")
            db.rollback()
            return None
    
    def get_order_by_id(self, db: Session, order_id: int) -> Optional[Order]:
        """Get order by ID"""
        return db.query(Order).filter(Order.id == order_id).first()
    
    def get_order_by_number(self, db: Session, order_number: str) -> Optional[Order]:
        """Get order by order number"""
        return db.query(Order).filter(Order.order_number == order_number).first()
    
    def get_customer_orders(
        self, 
        db: Session, 
        customer_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Order]:
        """Get all orders for a customer"""
        return db.query(Order).filter(
            Order.customer_id == customer_id
        ).order_by(Order.order_date.desc()).offset(skip).limit(limit).all()
    
    def get_orders_by_status(
        self,
        db: Session,
        status: OrderStatus,
        skip: int = 0,
        limit: int = 100
    ) -> List[Order]:
        """Get orders by status"""
        return db.query(Order).filter(
            Order.order_status == status
        ).order_by(Order.order_date.desc()).offset(skip).limit(limit).all()
    
    def update_order(
        self,
        db: Session,
        order_id: int,
        order_data: OrderUpdate
    ) -> Optional[Order]:
        """Update order"""
        try:
            order = self.get_order_by_id(db, order_id)
            if not order:
                return None
            
            update_data = order_data.model_dump(exclude_unset=True)
            
            for field, value in update_data.items():
                setattr(order, field, value)
            
            # Update timestamps based on status changes
            if order_data.order_status == "COMPLETED" and not order.completed_at:
                order.completed_at = datetime.utcnow()
            
            if order_data.order_status == "CANCELLED" and not order.cancelled_at:
                order.cancelled_at = datetime.utcnow()
            
            if order_data.payment_status == "PAID" and not order.payment_date:
                order.payment_date = datetime.utcnow()
            
            if order_data.payment_status == "REFUNDED" and not order.refunded_at:
                order.refunded_at = datetime.utcnow()
            
            if order_data.delivery_status == "SHIPPED" and not order.shipped_at:
                order.shipped_at = datetime.utcnow()
            
            if order_data.delivery_status == "DELIVERED" and not order.delivered_at:
                order.delivered_at = datetime.utcnow()
            
            db.commit()
            db.refresh(order)
            
            logger.info(f"Order updated: {order.order_number}")
            return order
            
        except Exception as e:
            logger.error(f"Error updating order: {str(e)}")
            db.rollback()
            return None
    
    def link_order_to_subscription(
        self,
        db: Session,
        order_id: int,
        subscription_id: int,
        subscriber_id: int
    ) -> bool:
        """Link order to subscription after payment"""
        try:
            order = self.get_order_by_id(db, order_id)
            if not order:
                return False
            
            order.subscription_id = subscription_id
            order.subscriber_id = subscriber_id
            order.order_status = OrderStatus.COMPLETED
            order.payment_status = PaymentStatus.PAID
            order.payment_date = datetime.utcnow()
            order.completed_at = datetime.utcnow()
            
            db.commit()
            logger.info(f"Order {order.order_number} linked to subscription {subscription_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error linking order to subscription: {str(e)}")
            db.rollback()
            return False
    
    def update_payment_info(
        self,
        db: Session,
        order_id: int,
        payment_intent_id: str,
        payment_method: str,
        payment_status: str
    ) -> bool:
        """Update order payment information"""
        try:
            order = self.get_order_by_id(db, order_id)
            if not order:
                return False
            
            order.stripe_payment_intent_id = payment_intent_id
            order.payment_method = payment_method
            order.payment_status = payment_status
            
            if payment_status == "PAID":
                order.payment_date = datetime.utcnow()
            
            db.commit()
            logger.info(f"Payment info updated for order: {order.order_number}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating payment info: {str(e)}")
            db.rollback()
            return False
    
    def cancel_order(self, db: Session, order_id: int, reason: str = None) -> bool:
        """Cancel an order"""
        try:
            order = self.get_order_by_id(db, order_id)
            if not order:
                return False
            
            if order.order_status in [OrderStatus.COMPLETED, OrderStatus.CANCELLED]:
                logger.warning(f"Cannot cancel order {order.order_number} - status: {order.order_status}")
                return False
            
            order.order_status = OrderStatus.CANCELLED
            order.cancelled_at = datetime.utcnow()
            
            if reason:
                order.internal_notes = f"Cancelled: {reason}\n{order.internal_notes or ''}"
            
            db.commit()
            logger.info(f"Order cancelled: {order.order_number}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling order: {str(e)}")
            db.rollback()
            return False
    
    def get_order_statistics(self, db: Session, customer_id: Optional[int] = None) -> dict:
        """Get order statistics"""
        try:
            query = db.query(Order)
            
            if customer_id:
                query = query.filter(Order.customer_id == customer_id)
            
            total_orders = query.count()
            pending_orders = query.filter(Order.order_status == OrderStatus.PENDING).count()
            completed_orders = query.filter(Order.order_status == OrderStatus.COMPLETED).count()
            cancelled_orders = query.filter(Order.order_status == OrderStatus.CANCELLED).count()
            
            # Calculate total revenue
            from sqlalchemy import func
            total_revenue = query.filter(
                Order.payment_status == PaymentStatus.PAID
            ).with_entities(func.sum(Order.total_amount)).scalar() or Decimal("0.00")
            
            return {
                "total_orders": total_orders,
                "pending_orders": pending_orders,
                "completed_orders": completed_orders,
                "cancelled_orders": cancelled_orders,
                "total_revenue": float(total_revenue)
            }
            
        except Exception as e:
            logger.error(f"Error getting order statistics: {str(e)}")
            return {}


order_service = OrderService()
