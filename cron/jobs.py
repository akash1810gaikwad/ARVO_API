from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
from config.mysql_database import get_mongodb
from utils.logger import logger
from config.settings import settings


class CronJobs:
    """Manage scheduled cron jobs"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
    
    async def cleanup_old_api_logs(self):
        """Clean up API logs older than 2 days"""
        try:
            db = get_mongodb()
            collection = db["api_logs"]
            
            cutoff_date = datetime.utcnow() - timedelta(days=2)
            result = await collection.delete_many({"timestamp": {"$lt": cutoff_date}})
            
            logger.info(f"Cleaned up {result.deleted_count} old API logs (older than 2 days)")
        except Exception as e:
            logger.error(f"Failed to cleanup API logs: {str(e)}")
    
    async def cleanup_old_audit_logs(self):
        """Clean up audit logs older than 90 days"""
        try:
            db = get_mongodb()
            collection = db["audit_logs"]
            
            cutoff_date = datetime.utcnow() - timedelta(days=90)
            result = await collection.delete_many({"timestamp": {"$lt": cutoff_date}})
            
            logger.info(f"Cleaned up {result.deleted_count} old audit logs")
        except Exception as e:
            logger.error(f"Failed to cleanup audit logs: {str(e)}")
    
    async def generate_daily_report(self):
        """Generate daily activity report"""
        try:
            db = get_mongodb()
            collection = db["audit_logs"]
            
            # Get logs from last 24 hours
            yesterday = datetime.utcnow() - timedelta(days=1)
            logs = await collection.count_documents({"timestamp": {"$gte": yesterday}})
            
            logger.info(f"Daily report: {logs} activities in the last 24 hours")
        except Exception as e:
            logger.error(f"Failed to generate daily report: {str(e)}")
    
    async def health_check(self):
        """Periodic health check"""
        try:
            # Check MongoDB
            db = get_mongodb()
            await db.command('ping')
            
            logger.info("Health check: All systems operational")
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
    
    def start(self):
        """Start all cron jobs"""
        if not settings.ENABLE_CRON_JOBS:
            logger.info("Cron jobs are disabled")
            return
        
        # Cleanup old API logs - runs every 6 hours
        self.scheduler.add_job(
            self.cleanup_old_api_logs,
            CronTrigger(hour="*/6"),
            id="cleanup_api_logs",
            name="Cleanup old API logs (older than 2 days)",
            replace_existing=True
        )
        
        # Cleanup old audit logs - runs daily at 2 AM
        self.scheduler.add_job(
            self.cleanup_old_audit_logs,
            CronTrigger(hour=2, minute=0),
            id="cleanup_audit_logs",
            name="Cleanup old audit logs",
            replace_existing=True
        )
        
        # Generate daily report - runs daily at 8 AM
        self.scheduler.add_job(
            self.generate_daily_report,
            CronTrigger(hour=8, minute=0),
            id="daily_report",
            name="Generate daily report",
            replace_existing=True
        )
        
        # Health check - runs every 15 minutes
        self.scheduler.add_job(
            self.health_check,
            CronTrigger(minute="*/15"),
            id="health_check",
            name="System health check",
            replace_existing=True
        )
        
        self.scheduler.start()
        logger.info("Cron jobs started successfully")
    
    def shutdown(self):
        """Shutdown scheduler"""
        self.scheduler.shutdown()
        logger.info("Cron jobs stopped")


cron_jobs = CronJobs()
