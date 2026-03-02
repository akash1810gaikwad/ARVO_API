from .audit_routes import router as audit_router
from .api_logs_routes import router as api_logs_router
from .plan_routes import router as plan_router
from .service_option_routes import router as service_option_router
from .plan_service_option_routes import router as plan_service_option_router
from .customer_routes import router as customer_router
from .new_subscription_routes import router as new_subscription_router
from .order_routes import router as order_router
from .transatel_routes import router as transatel_router
from .transatel_api_log_routes import router as transatel_api_log_router
from .email_template_routes import router as email_template_router
from .email_routes import router as email_router
from .parental_control_routes import router as parental_control_router
from .complaint_routes import router as complaint_router
from .operator_routes import router as operator_router
from .subscriber_routes import router as subscriber_router
from .transaction_routes import router as transaction_router
from .password_reset_routes import router as password_reset_router
from .test_cleanup_routes import router as test_cleanup_router
from .user_journey_routes import router as user_journey_router
from .promo_code_routes import router as promo_code_router
from .stripe_webhook_routes import router as stripe_webhook_router
from .whop_webhook_routes import router as whop_webhook_router
from .cdr_routes import router as cdr_router
from .sim_inventory_routes import router as sim_inventory_router

__all__ = ["audit_router", "api_logs_router", "plan_router", "service_option_router", "plan_service_option_router", "customer_router", "new_subscription_router", "order_router", "transatel_router", "transatel_api_log_router", "email_template_router", "email_router", "parental_control_router", "complaint_router", "operator_router", "subscriber_router", "transaction_router", "password_reset_router", "test_cleanup_router", "user_journey_router", "promo_code_router", "stripe_webhook_router", "whop_webhook_router", "cdr_router", "sim_inventory_router"]
