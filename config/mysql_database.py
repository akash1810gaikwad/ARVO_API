from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from motor.motor_asyncio import AsyncIOMotorClient
from config.settings import settings
from utils.logger import logger

# MySQL Connection
mysql_engine = None
MySQLSessionLocal = None
MySQLBase = declarative_base()

# MongoDB Connection
mongodb_client = None
mongodb_db = None


def connect_mysql():
    """Connect to MySQL"""
    global mysql_engine, MySQLSessionLocal
    
    if not settings.MYSQL_ENABLED:
        logger.warning("MySQL is disabled in configuration")
        return None
    
    if not settings.MYSQL_HOST or not settings.MYSQL_DATABASE:
        logger.warning("MySQL configuration incomplete, skipping connection")
        return None
    
    try:
        connection_url = settings.mysql_connection_url
        logger.info(f"Connecting to MySQL: {settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}")
        
        mysql_engine = create_engine(
            connection_url,
            pool_pre_ping=True,
            pool_recycle=3600,
            pool_size=10,
            max_overflow=20,
            echo=settings.APP_DEBUG
        )
        
        # Test connection
        with mysql_engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("SELECT 1"))
            logger.info("MySQL connection test successful")
        
        MySQLSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=mysql_engine)
        logger.info("MySQL connected successfully")
        return mysql_engine
        
    except Exception as e:
        logger.error(f"MySQL connection failed: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        logger.warning("API will start without MySQL")
        return None


def get_mysql_db():
    """Get MySQL database session"""
    global MySQLSessionLocal
    
    if not MySQLSessionLocal:
        logger.warning("MySQLSessionLocal not initialized, attempting to connect...")
        connect_mysql()
    
    if not MySQLSessionLocal:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail="MySQL database is not available. Please check database configuration."
        )
    
    db = MySQLSessionLocal()
    try:
        yield db
    finally:
        db.close()


def is_mysql_connected():
    """Check if MySQL is connected"""
    return MySQLSessionLocal is not None and mysql_engine is not None


def init_mysql_db():
    """Initialize MySQL database - create all tables"""
    if mysql_engine:
        MySQLBase.metadata.create_all(bind=mysql_engine)
        logger.info("MySQL database tables created")
    else:
        logger.warning("MySQL engine not available, skipping table creation")


# ============= MONGODB FUNCTIONS =============

async def connect_mongodb():
    """Connect to MongoDB"""
    global mongodb_client, mongodb_db
    try:
        mongodb_client = AsyncIOMotorClient(settings.MONGODB_URL)
        mongodb_db = mongodb_client[settings.MONGODB_DB_NAME]
        await mongodb_client.admin.command('ping')
        logger.info("MongoDB connected successfully")
    except Exception as e:
        logger.error(f"MongoDB connection failed: {str(e)}")
        raise


async def close_mongodb():
    """Close MongoDB connection"""
    global mongodb_client
    if mongodb_client:
        mongodb_client.close()
        logger.info("MongoDB connection closed")


def get_mongodb():
    """Get MongoDB database instance"""
    return mongodb_db
