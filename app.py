# Disable SQLAlchemy logging BEFORE any imports
import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.dialects').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.orm').setLevel(logging.WARNING)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from config.settings import settings
from config.mysql_database import connect_mysql, connect_mongodb, close_mongodb, MySQLBase, mysql_engine
from routes import audit_router, api_logs_router, complaint_router, plan_router, service_option_router, plan_service_option_router, customer_router, new_subscription_router, order_router, transatel_router, transatel_api_log_router, email_template_router, email_router, parental_control_router, operator_router, subscriber_router, transaction_router, password_reset_router, test_cleanup_router, user_journey_router, promo_code_router, stripe_webhook_router, whop_webhook_router, cdr_router, sim_inventory_router
from middleware import LoggingMiddleware, OriginValidatorMiddleware
from cron import cron_jobs
from utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info(f"Starting {settings.APP_NAME}...")
    
    # Connect to MongoDB
    await connect_mongodb()
    
    # Connect to MySQL
    engine = connect_mysql()
    
    # Create MySQL tables if connected
    if engine:
        MySQLBase.metadata.create_all(bind=engine)
        logger.info("MySQL tables created")
    else:
        logger.warning("MySQL not available - Database endpoints will not work")
    
    # Start cron jobs
    cron_jobs.start()
    
    logger.info(f"{settings.APP_NAME} started successfully")
    
    yield
    
    # Shutdown
    logger.info(f"Shutting down {settings.APP_NAME}...")
    cron_jobs.shutdown()
    await close_mongodb()
    logger.info(f"{settings.APP_NAME} stopped")


# Create FastAPI app
# In production: Swagger docs are completely disabled (no /docs, no /redoc)
# In development: Swagger is available for testing
is_development = settings.APP_ENV.lower() in ("development", "dev", "local")

app = FastAPI(
    title=settings.APP_NAME,
    description="API with MongoDB for audit logs and MSSQL for main relations",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if is_development else None,
    redoc_url="/redoc" if is_development else None,
    openapi_url="/openapi.json" if is_development else None,
)

# Add Origin Validator middleware (runs FIRST — blocks unauthorized origins & Swagger access)
app.add_middleware(OriginValidatorMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add logging middleware
app.add_middleware(LoggingMiddleware)

# Include routers
app.include_router(customer_router)
app.include_router(new_subscription_router)
app.include_router(order_router)
app.include_router(plan_router)
app.include_router(service_option_router)
app.include_router(plan_service_option_router)
app.include_router(audit_router)
app.include_router(api_logs_router)
app.include_router(transatel_router)
app.include_router(transatel_api_log_router)
app.include_router(email_template_router)
app.include_router(email_router)
app.include_router(parental_control_router)
app.include_router(complaint_router)
app.include_router(operator_router)
app.include_router(subscriber_router)
app.include_router(transaction_router)
app.include_router(password_reset_router)
app.include_router(test_cleanup_router)
app.include_router(user_journey_router)
app.include_router(promo_code_router)
app.include_router(stripe_webhook_router)
app.include_router(whop_webhook_router)
app.include_router(cdr_router)
app.include_router(sim_inventory_router)




@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": "1.0.0",
        "environment": settings.APP_ENV
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    from config.mysql_database import is_mysql_connected
    
    mysql_status = "connected" if is_mysql_connected() else "disconnected"
    
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "mysql": mysql_status
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.APP_DEBUG
    )
