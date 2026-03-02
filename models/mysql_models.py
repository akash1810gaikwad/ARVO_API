"""
MySQL Models - Complete database structure for MySQL
Converted from MSSQL models with MySQL-compatible types
"""
from sqlalchemy import Column, String, Integer, BigInteger, DateTime, Boolean, Text, Enum, ForeignKey, Numeric, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from sqlalchemy.sql import func
from config.mysql_database import MySQLBase


# ============= ENUMS =============

class PlanType(enum.Enum):
    MONTHLY = "monthly"
    YEARLY = "yearly"


class ServiceOptionCategory(enum.Enum):
    DATA_ACCESS = "DATA_ACCESS"
    DATA_CONTENT_FILTERING = "DATA_CONTENT_FILTERING"
    INTERNATIONAL_SERVICE = "INTERNATIONAL_SERVICE"
    MULTI_SPN_SERVICES = "MULTI_SPN_SERVICES"
    NETWORK_BARRINGS = "NETWORK_BARRINGS"
    ROAMING_SERVICE = "ROAMING_SERVICE"
    SMS_MMS_SERVICE = "SMS_MMS_SERVICE"
    VOICE_SERVICE = "VOICE_SERVICE"
    VOICEMAIL = "VOICEMAIL"
    WHOLESALE_PURCHASING = "WHOLESALE_PURCHASING"


class ServiceOptionType(enum.Enum):
    CIRCLE = "circle"
    ENABLE = "enable"
    TRAILED_CIRCLE = "trailed_circle"


class OrderType(str, enum.Enum):
    SUBSCRIPTION = "SUBSCRIPTION"
    SIM_CARD = "SIM_CARD"
    PLAN_UPGRADE = "PLAN_UPGRADE"
    ADDON = "ADDON"


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class DeliveryStatus(str, enum.Enum):
    NOT_SHIPPED = "NOT_SHIPPED"
    SHIPPED = "SHIPPED"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"


# ============= CUSTOMER =============

class Customer(MySQLBase):
    __tablename__ = "customer_master"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    phone_number = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    postcode = Column(String(20), nullable=True)
    city = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    number_of_children = Column(Integer, nullable=True, default=0)
    
    password_hash = Column(String(255), nullable=True)
    
    google_id = Column(String(255), unique=True, nullable=True, index=True)
    oauth_provider = Column(String(50), nullable=True)
    profile_picture = Column(String(500), nullable=True)
    
    is_email_verified = Column(Boolean, default=False)
    email_verified_at = Column(DateTime, nullable=True)
    verification_token = Column(String(255), nullable=True)
    
    is_active = Column(Boolean, default=True, index=True)
    is_deleted = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)
    
    subscriber = relationship("Subscriber", back_populates="customer", uselist=False)


# ============= PLAN MASTER =============

class PlanMaster(MySQLBase):
    __tablename__ = "plan_master"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    plan_code = Column(String(100), nullable=False, unique=True, index=True)
    plan_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    tagline = Column(String(255), nullable=True)
    plan_type = Column(Enum(PlanType), nullable=False, index=True)
    duration_days = Column(Integer, nullable=False, default=30)
    monthly_price = Column(Numeric(10, 2), nullable=False)
    annual_price = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="GBP")
    data_allowance = Column(String(50), nullable=True)
    is_popular = Column(Boolean, default=False)
    gradient = Column(String(255), nullable=True)
    icon_bg = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(BigInteger, nullable=True)
    
    plan_service_options = relationship("PlanServiceOption", back_populates="plan")


# ============= SERVICE OPTIONS =============

class ServiceOption(MySQLBase):
    __tablename__ = "service_options"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    option_code = Column(String(100), nullable=False, unique=True, index=True)
    option_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(Enum(ServiceOptionCategory), nullable=False, index=True)
    option_type = Column(Enum(ServiceOptionType), nullable=False, index=True)
    is_default = Column(Boolean, default=False, index=True)
    is_active = Column(Boolean, default=True, index=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    plan_service_options = relationship("PlanServiceOption", back_populates="service_option")


class PlanServiceOption(MySQLBase):
    __tablename__ = "plan_service_options"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    plan_id = Column(BigInteger, ForeignKey("plan_master.id"), nullable=False, index=True)
    service_option_id = Column(BigInteger, ForeignKey("service_options.id"), nullable=False, index=True)
    is_default = Column(Boolean, default=True)
    is_required = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(BigInteger, nullable=True)
    
    plan = relationship("PlanMaster", back_populates="plan_service_options")
    service_option = relationship("ServiceOption", back_populates="plan_service_options")


# ============= SUBSCRIBER & SUBSCRIPTION =============

class Subscriber(MySQLBase):
    __tablename__ = "subscribers"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    customer_id = Column(BigInteger, ForeignKey("customer_master.id"), nullable=False, unique=True)
    stripe_customer_id = Column(String(255), unique=True)
    
    default_payment_method_id = Column(String(255))
    card_brand = Column(String(50))
    card_last4 = Column(String(4))
    card_exp_month = Column(Integer)
    card_exp_year = Column(Integer)
    
    auto_renew_enabled = Column(Boolean, default=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    
    customer = relationship("Customer", back_populates="subscriber")
    subscriptions = relationship("Subscription", back_populates="subscriber")
    child_sim_cards = relationship("ChildSimCard", back_populates="subscriber")
    payments = relationship("Payment", back_populates="subscriber")


class Subscription(MySQLBase):
    __tablename__ = "subscriptions"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    subscriber_id = Column(BigInteger, ForeignKey("subscribers.id"), nullable=False)
    plan_id = Column(BigInteger, ForeignKey("plan_master.id"), nullable=False)
    
    subscription_number = Column(String(50), unique=True, nullable=False, index=True)
    status = Column(String(50), default="ACTIVE", nullable=False)
    
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    next_billing_date = Column(DateTime)
    
    number_of_children = Column(Integer, nullable=False)
    
    plan_price_per_child = Column(Numeric(10, 2), nullable=False)
    total_monthly_amount = Column(Numeric(10, 2), nullable=False)
    initial_payment_amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="GBP", nullable=False)
    
    billing_cycle = Column(String(20), nullable=False)
    initial_months = Column(Integer, default=3, nullable=False)
    auto_renew = Column(Boolean, default=True, nullable=False)
    
    stripe_subscription_id = Column(String(255))
    stripe_price_id = Column(String(255))
    
    cancelled_at = Column(DateTime)
    cancellation_reason = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    
    subscriber = relationship("Subscriber", back_populates="subscriptions")
    plan = relationship("PlanMaster")
    child_sim_cards = relationship("ChildSimCard", back_populates="subscription")
    payments = relationship("Payment", back_populates="subscription")
    orders = relationship("Order", back_populates="subscription")


# ============= SIM INVENTORY & CHILD SIM CARDS =============

class SimInventory(MySQLBase):
    __tablename__ = "sim_inventory"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    
    sim_number = Column(String(50), unique=True, nullable=False, index=True)
    iccid = Column(String(50), unique=True)
    msisdn = Column(String(20))
    activation_code = Column(String(255))
    sim_type = Column(String(10), nullable=False, default="pSIM")
    
    status = Column(String(50), default="AVAILABLE", nullable=False)
    is_tested = Column(Boolean, default=False, nullable=False)
    
    assigned_to_child_sim_id = Column(BigInteger)
    assigned_at = Column(DateTime)
    
    batch_number = Column(String(50))
    supplier = Column(String(100))
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)


class ChildSimCard(MySQLBase):
    __tablename__ = "child_sim_cards"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    subscription_id = Column(BigInteger, ForeignKey("subscriptions.id"), nullable=False)
    subscriber_id = Column(BigInteger, ForeignKey("subscribers.id"), nullable=False)
    
    child_name = Column(String(255), nullable=False)
    child_age = Column(Integer, nullable=False)
    child_order = Column(Integer, nullable=False)
    
    sim_inventory_id = Column(BigInteger, ForeignKey("sim_inventory.id"))
    sim_number = Column(String(50))
    iccid = Column(String(50))
    msisdn = Column(String(20))
    activation_code = Column(String(50))
    sim_type = Column(String(10))
    
    is_active = Column(Boolean, default=True, nullable=False)
    activation_date = Column(DateTime)
    deactivation_date = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    
    subscription = relationship("Subscription", back_populates="child_sim_cards")
    subscriber = relationship("Subscriber", back_populates="child_sim_cards")
    sim_inventory = relationship("SimInventory")


# ============= ORDERS =============

class Order(MySQLBase):
    __tablename__ = "orders"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    
    customer_id = Column(BigInteger, ForeignKey("customer_master.id"), nullable=False)
    subscriber_id = Column(BigInteger, ForeignKey("subscribers.id"), nullable=True)
    subscription_id = Column(BigInteger, ForeignKey("subscriptions.id"), nullable=True)
    
    order_number = Column(String(50), unique=True, nullable=False, index=True)
    order_type = Column(Enum(OrderType), nullable=False)
    order_status = Column(Enum(OrderStatus), default=OrderStatus.PENDING, nullable=False)
    
    plan_id = Column(BigInteger, ForeignKey("plan_master.id"), nullable=True)
    plan_name = Column(String(255), nullable=True)
    
    subtotal = Column(Numeric(10, 2), nullable=True)
    tax_amount = Column(Numeric(10, 2), default=0)
    discount_amount = Column(Numeric(10, 2), default=0)
    total_amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="GBP", nullable=False)
    
    quantity = Column(Integer, default=1, nullable=False)
    number_of_children = Column(Integer, nullable=True)
    
    children_details = Column(Text, nullable=True)
    plan_price_per_child = Column(Numeric(10, 2), nullable=True)
    initial_payment_amount = Column(Numeric(10, 2), nullable=True)
    monthly_amount = Column(Numeric(10, 2), nullable=True)
    sim_type = Column(String(10), nullable=True)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    
    process_state = Column(String(50), default="INITIATED")
    last_successful_step = Column(String(100))
    failure_reason = Column(Text)
    
    auto_renew = Column(Boolean, default=True, nullable=False)
    
    payment_method = Column(String(50), nullable=True)
    payment_status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    stripe_payment_intent_id = Column(String(255), nullable=True)
    stripe_invoice_id = Column(String(255), nullable=True)
    
    shipping_address = Column(Text, nullable=True)
    shipping_city = Column(String(100), nullable=True)
    shipping_postcode = Column(String(20), nullable=True)
    shipping_country = Column(String(100), nullable=True)
    tracking_number = Column(String(100), nullable=True)
    delivery_status = Column(Enum(DeliveryStatus), default=DeliveryStatus.NOT_SHIPPED)
    shipped_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    
    order_items = Column(Text, nullable=True)
    
    customer_notes = Column(Text, nullable=True)
    internal_notes = Column(Text, nullable=True)
    extra_metadata = Column(Text, nullable=True)
    
    order_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    payment_date = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    refunded_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    
    customer = relationship("Customer")
    subscriber = relationship("Subscriber")
    subscription = relationship("Subscription", back_populates="orders")
    plan = relationship("PlanMaster")


# ============= PAYMENTS =============

class Payment(MySQLBase):
    __tablename__ = "payments"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    
    order_id = Column(BigInteger, ForeignKey("orders.id"))
    subscription_id = Column(BigInteger, ForeignKey("subscriptions.id"), nullable=False)
    subscriber_id = Column(BigInteger, ForeignKey("subscribers.id"), nullable=False)
    
    payment_type = Column(String(50), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="GBP", nullable=False)
    status = Column(String(50), default="PENDING", nullable=False)
    
    stripe_payment_intent_id = Column(String(255))
    stripe_charge_id = Column(String(255))
    stripe_invoice_id = Column(String(255))
    
    payment_method_type = Column(String(50))
    card_brand = Column(String(50))
    card_last4 = Column(String(4))
    
    billing_period_start = Column(DateTime)
    billing_period_end = Column(DateTime)
    
    failure_reason = Column(Text)
    receipt_url = Column(String(500))
    
    payment_date = Column(DateTime)
    refunded_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    
    order = relationship("Order")
    subscription = relationship("Subscription", back_populates="payments")
    subscriber = relationship("Subscriber", back_populates="payments")


# ============= USER JOURNEY =============

class UserJourney(MySQLBase):
    __tablename__ = "user_journeys"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    customer_id = Column(BigInteger, ForeignKey("customer_master.id"), nullable=False, index=True)
    customer_email = Column(String(255), nullable=True)
    
    journey_started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    journey_completed_at = Column(DateTime, nullable=True)
    journey_status = Column(String(50), default="IN_PROGRESS", nullable=False)
    
    registration_completed = Column(Boolean, default=False, nullable=False)
    registration_completed_at = Column(DateTime, nullable=True)
    registration_payload = Column(Text, nullable=True)
    
    plan_selection_completed = Column(Boolean, default=False, nullable=False)
    plan_selection_completed_at = Column(DateTime, nullable=True)
    plan_selection_payload = Column(Text, nullable=True)
    
    payment_completed = Column(Boolean, default=False, nullable=False)
    payment_completed_at = Column(DateTime, nullable=True)
    payment_payload = Column(Text, nullable=True)
    
    iccid_allocation_completed = Column(Boolean, default=False, nullable=False)
    iccid_allocation_completed_at = Column(DateTime, nullable=True)
    iccid_allocation_payload = Column(Text, nullable=True)
    
    esim_activation_completed = Column(Boolean, default=False, nullable=False)
    esim_activation_completed_at = Column(DateTime, nullable=True)
    esim_activation_payload = Column(Text, nullable=True)
    
    qr_code_generation_completed = Column(Boolean, default=False, nullable=False)
    qr_code_generation_completed_at = Column(DateTime, nullable=True)
    qr_code_generation_payload = Column(Text, nullable=True)
    
    subscriber_id = Column(BigInteger, ForeignKey("subscribers.id"), nullable=True)
    subscription_id = Column(BigInteger, ForeignKey("subscriptions.id"), nullable=True)
    order_id = Column(BigInteger, ForeignKey("orders.id"), nullable=True)
    sim_id = Column(BigInteger, ForeignKey("sim_inventory.id"), nullable=True)
    plan_id = Column(BigInteger, ForeignKey("plan_master.id"), nullable=True)
    stripe_session_id = Column(String(255), nullable=True, index=True)
    stripe_payment_intent_id = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    notes = Column(Text, nullable=True)


# ============= AUDIT TRAIL =============

class AuditTrail(MySQLBase):
    __tablename__ = "audit_trail"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    
    order_id = Column(BigInteger, ForeignKey("orders.id"))
    subscription_id = Column(BigInteger, ForeignKey("subscriptions.id"))
    customer_id = Column(BigInteger, ForeignKey("customer_master.id"))
    
    action = Column(String(100), nullable=False)
    step = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False)
    
    details = Column(Text)
    error_message = Column(Text)
    
    ip_address = Column(String(50))
    user_agent = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    order = relationship("Order")
    subscription = relationship("Subscription")
    customer = relationship("Customer")


# ============= OTP =============

class PasswordResetOTP(MySQLBase):
    __tablename__ = "password_reset_otps"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), nullable=False, index=True)
    otp_code = Column(String(6), nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    def is_expired(self):
        from datetime import datetime, timezone
        if self.expires_at is None:
            return True
        now = datetime.now(timezone.utc)
        expires = self.expires_at.replace(tzinfo=timezone.utc) if self.expires_at.tzinfo is None else self.expires_at
        return now > expires
    
    def is_valid(self):
        return not self.is_used and not self.is_expired()


# ============= TRANSATEL =============

class TransatelToken(MySQLBase):
    __tablename__ = "transatel_tokens"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    access_token = Column(Text, nullable=False)
    token_type = Column(String(50), default="Bearer")
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class TransatelAPILog(MySQLBase):
    __tablename__ = "transatel_api_logs"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    api_name = Column(String(255), nullable=False)
    endpoint = Column(String(500), nullable=False)
    request_payload = Column(Text)
    response_payload = Column(Text)
    status = Column(String(50), nullable=False)
    http_status_code = Column(Integer)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ============= COMPLAINTS =============

class TblComplaintType(MySQLBase):
    __tablename__ = "tbl_complaint_type"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    type_name = Column(String(100), nullable=False, unique=True)
    type_code = Column(String(20), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(BigInteger, nullable=True)
    updated_by = Column(BigInteger, nullable=True)

    sub_types = relationship("TblComplaintSubType", back_populates="complaint_type")
    complaints = relationship("TblComplaintMaster", back_populates="complaint_type")


class TblComplaintSubType(MySQLBase):
    __tablename__ = "tbl_complaint_sub_type"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    complaint_type_id = Column(BigInteger, ForeignKey("tbl_complaint_type.id"), nullable=False, index=True)
    sub_type_name = Column(String(100), nullable=False)
    sub_type_code = Column(String(20), nullable=False)
    description = Column(Text, nullable=True)
    resolution_sla_hours = Column(Integer, default=24)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(BigInteger, nullable=True)
    updated_by = Column(BigInteger, nullable=True)

    complaint_type = relationship("TblComplaintType", back_populates="sub_types")
    complaints = relationship("TblComplaintMaster", back_populates="complaint_sub_type")


class TblComplaintMaster(MySQLBase):
    __tablename__ = "tbl_complaint_master"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    complaint_number = Column(String(50), nullable=False, unique=True, index=True)
    customer_id = Column(BigInteger, ForeignKey("customer_master.id"), nullable=False, index=True)
    subscriber_id = Column(BigInteger, ForeignKey("subscribers.id"), nullable=True, index=True)
    complaint_type_id = Column(BigInteger, ForeignKey("tbl_complaint_type.id"), nullable=False, index=True)
    complaint_sub_type_id = Column(BigInteger, ForeignKey("tbl_complaint_sub_type.id"), nullable=False, index=True)
    
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    priority = Column(String(20), default="MEDIUM")
    status = Column(String(20), default="OPEN", index=True)
    
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    
    resolution_notes = Column(Text, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(BigInteger, nullable=True)
    
    sla_due_date = Column(DateTime, nullable=True)
    is_sla_breached = Column(Boolean, default=False, nullable=False)
    needs_attention = Column(Boolean, default=False, nullable=False, index=True)
    
    assigned_to = Column(BigInteger, nullable=True)
    assigned_at = Column(DateTime, nullable=True)
    
    escalated_at = Column(DateTime, nullable=True)
    escalated_to = Column(BigInteger, nullable=True)
    escalation_reason = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    
    source = Column(String(50), default="API")
    reference_number = Column(String(100), nullable=True)
    tags = Column(Text, nullable=True)
    
    complaint_type = relationship("TblComplaintType", back_populates="complaints")
    complaint_sub_type = relationship("TblComplaintSubType", back_populates="complaints")
    comments = relationship("TblComplaintComment", back_populates="complaint")
    attachments = relationship("TblComplaintAttachment", back_populates="complaint")


class TblComplaintComment(MySQLBase):
    __tablename__ = "tbl_complaint_comment"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    complaint_id = Column(BigInteger, ForeignKey("tbl_complaint_master.id"), nullable=False, index=True)
    comment_text = Column(Text, nullable=False)
    comment_type = Column(String(50), default="INTERNAL")
    is_internal = Column(Boolean, default=True)
    created_by = Column(BigInteger, nullable=False)
    created_by_type = Column(String(20), default="STAFF")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    complaint = relationship("TblComplaintMaster", back_populates="comments")


class TblComplaintAttachment(MySQLBase):
    __tablename__ = "tbl_complaint_attachment"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    complaint_id = Column(BigInteger, ForeignKey("tbl_complaint_master.id"), nullable=False, index=True)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(BigInteger, nullable=True)
    file_type = Column(String(100), nullable=True)
    uploaded_by = Column(BigInteger, nullable=False)
    uploaded_by_type = Column(String(20), default="STAFF")
    created_at = Column(DateTime, default=datetime.utcnow)

    complaint = relationship("TblComplaintMaster", back_populates="attachments")


# ============= EMAIL TEMPLATES =============

class EmailTemplate(MySQLBase):
    __tablename__ = "email_templates"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    template_key = Column(String(100), unique=True, nullable=False, index=True)
    template_name = Column(String(255), nullable=False)
    subject = Column(String(500), nullable=False)
    body_html = Column(Text, nullable=False)
    body_text = Column(Text, nullable=True)
    variables = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============= PARENTAL CONTROLS =============

class ParentalControl(MySQLBase):
    __tablename__ = "parental_controls"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    child_sim_card_id = Column(BigInteger, ForeignKey("child_sim_cards.id"), nullable=False, index=True)
    customer_id = Column(BigInteger, ForeignKey("customer_master.id"), nullable=False, index=True)
    
    voice_calls_enabled = Column(Boolean, default=True, nullable=False)
    mobile_data_enabled = Column(Boolean, default=True, nullable=False)
    sms_enabled = Column(Boolean, default=True, nullable=False)
    
    adult_content_filter = Column(String(50), default="MODERATE", nullable=False)
    
    custom_settings = Column(Text, nullable=True)
    previous_params = Column(Text, nullable=True)
    
    voice_calls_changed_at = Column(DateTime, nullable=True)
    mobile_data_changed_at = Column(DateTime, nullable=True)
    sms_changed_at = Column(DateTime, nullable=True)
    adult_content_changed_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    last_synced_at = Column(DateTime, nullable=True)
    last_modified_at = Column(DateTime, nullable=True)  # Track last modification for 30-min cooldown
    
    child_sim_card = relationship("ChildSimCard")
    customer = relationship("Customer")


# ============= MODULES =============

class Module(MySQLBase):
    __tablename__ = "modules"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    module_code = Column(String(50), unique=True, nullable=False, index=True)
    module_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String(50), nullable=True)
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    operator_accesses = relationship("OperatorModuleAccess", back_populates="module")


class OperatorModuleAccess(MySQLBase):
    __tablename__ = "operator_module_access"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    customer_id = Column(BigInteger, ForeignKey("customer_master.id"), nullable=False)
    module_id = Column(BigInteger, ForeignKey("modules.id"), nullable=False)
    has_access = Column(Boolean, default=True, nullable=False)
    granted_by = Column(BigInteger, ForeignKey("customer_master.id"), nullable=True)
    granted_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    customer = relationship("Customer", foreign_keys=[customer_id])
    module = relationship("Module", back_populates="operator_accesses")
    granted_by_user = relationship("Customer", foreign_keys=[granted_by])
