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
    
    async def check_offline_devices(self):
        """Check for offline child devices and create alerts"""
        try:
            from config.mysql_database import MySQLSessionLocal
            from models.mysql_models import ChildHeartbeat, ChildAlert, ChildSimCard

            if not MySQLSessionLocal:
                logger.warning("MySQL not connected, skipping offline device check")
                return

            db = MySQLSessionLocal()
            
            try:
                # Get all heartbeats that haven't been updated in 2 minutes
                cutoff_time = datetime.utcnow() - timedelta(minutes=2)
                
                offline_devices = db.query(ChildHeartbeat).filter(
                    ChildHeartbeat.last_heartbeat_at < cutoff_time,
                    ChildHeartbeat.is_online == True
                ).all()
                
                for heartbeat in offline_devices:
                    # Mark as offline
                    heartbeat.is_online = False
                    
                    # Get child SIM info
                    child_sim = db.query(ChildSimCard).filter(
                        ChildSimCard.msisdn == heartbeat.msisdn,
                        ChildSimCard.is_active == True
                    ).first()
                    
                    if child_sim and child_sim.subscriber:
                        customer_id = child_sim.subscriber.customer_id
                        
                        # Check if we already created an offline alert recently (within last hour)
                        recent_alert = db.query(ChildAlert).filter(
                            ChildAlert.msisdn == heartbeat.msisdn,
                            ChildAlert.alert_type == "OFFLINE",
                            ChildAlert.created_at > datetime.utcnow() - timedelta(hours=1)
                        ).first()
                        
                        if not recent_alert:
                            # Create offline alert
                            alert = ChildAlert(
                                msisdn=heartbeat.msisdn,
                                child_sim_card_id=child_sim.id,
                                customer_id=customer_id,
                                alert_type="OFFLINE",
                                message=f"{child_sim.child_name}'s device is offline",
                                battery_level=heartbeat.battery_level,
                                is_read=False
                            )
                            db.add(alert)
                            logger.info(f"Offline alert created for {heartbeat.msisdn}")
                
                db.commit()
                logger.debug(f"Offline device check completed: {len(offline_devices)} devices marked offline")
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to check offline devices: {str(e)}")
    
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
        
        # Check offline devices - runs every minute
        self.scheduler.add_job(
            self.check_offline_devices,
            CronTrigger(minute="*"),
            id="check_offline_devices",
            name="Check for offline child devices",
            replace_existing=True
        )
        
        self.scheduler.start()
        logger.info("Cron jobs started successfully")
    
    def shutdown(self):
        """Shutdown scheduler"""
        self.scheduler.shutdown()
        logger.info("Cron jobs stopped")


cron_jobs = CronJobs()
