from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal


class OrderItemSchema(BaseModel):
    """Individual item in an order"""
    item_type: str  # 'plan', 'sim_card', 'addon'
    item_id: Optional[int] = None
    item_name: str
    quantity: int = 1
    unit_price: Decimal
    total_price: Decimal
    metadata: Optional[Dict[str, Any]] = None


class OrderCreate(BaseModel):
    """Create a new order"""
    customer_id: int
    order_type: str = Field(..., pattern="^(SUBSCRIPTION|SIM_CARD|PLAN_UPGRADE|ADDON)$")
    plan_id: Optional[int] = None
    billing_cycle: Optional[str] = Field(None, pattern="^(monthly|annual)$")
    number_of_children: Optional[int] = Field(None, ge=1)
    
    # Pricing
    subtotal: Decimal
    tax_amount: Decimal = Decimal("0.00")
    discount_amount: Decimal = Decimal("0.00")
    total_amount: Decimal
    
    # Items
    order_items: List[OrderItemSchema]
    
    # Shipping (optional)
    shipping_address: Optional[str] = None
    shipping_city: Optional[str] = None
    shipping_postcode: Optional[str] = None
    shipping_country: Optional[str] = None
    
    # Notes
    customer_notes: Optional[str] = None


class OrderUpdate(BaseModel):
    """Update order status"""
    order_status: Optional[str] = Field(None, pattern="^(PENDING|PROCESSING|COMPLETED|FAILED|CANCELLED|REFUNDED)$")
    payment_status: Optional[str] = Field(None, pattern="^(PENDING|PAID|FAILED|REFUNDED)$")
    delivery_status: Optional[str] = Field(None, pattern="^(NOT_SHIPPED|SHIPPED|IN_TRANSIT|DELIVERED)$")
    tracking_number: Optional[str] = None
    internal_notes: Optional[str] = None


class OrderResponse(BaseModel):
    """Order response"""
    id: int
    customer_id: int
    order_number: str
    order_type: str
    order_status: str
    
    # Plan details
    plan_id: Optional[int] = None
    plan_name: Optional[str] = None
    billing_cycle: Optional[str] = None
    
    # Pricing
    subtotal: Decimal
    tax_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    currency: str
    
    # Quantity
    quantity: int
    number_of_children: Optional[int] = None
    
    # Payment
    payment_method: Optional[str] = None
    payment_status: str
    stripe_payment_intent_id: Optional[str] = None
    
    # Shipping
    shipping_address: Optional[str] = None
    shipping_city: Optional[str] = None
    shipping_postcode: Optional[str] = None
    shipping_country: Optional[str] = None
    tracking_number: Optional[str] = None
    delivery_status: str
    
    # Timestamps
    order_date: datetime
    payment_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class OrderWithDetails(OrderResponse):
    """Order with full details including items"""
    order_items: Optional[List[Dict[str, Any]]] = None
    customer_notes: Optional[str] = None
    internal_notes: Optional[str] = None
    
    # Related info
    customer_email: Optional[str] = None
    customer_name: Optional[str] = None


class OrderSummary(BaseModel):
    """Order summary for lists"""
    id: int
    order_number: str
    order_type: str
    order_status: str
    payment_status: str
    total_amount: Decimal
    currency: str
    order_date: datetime
    customer_name: Optional[str] = None
    
    class Config:
        from_attributes = True
