"""
Script to create the whop_webhook_logs table in MySQL database
Run this once to set up the table for logging Whop webhooks
"""
from config.mysql_database import connect_mysql, MySQLBase
from models.whop_webhook_log_model import WhopWebhookLog
from utils.logger import logger

def create_whop_webhook_table():
    """Create the whop_webhook_logs table"""
    try:
        logger.info("Connecting to MySQL...")
        engine = connect_mysql()
        
        if not engine:
            logger.error("Failed to connect to MySQL")
            return False
        
        logger.info("Creating whop_webhook_logs table...")
        
        # Create the table
        WhopWebhookLog.__table__.create(engine, checkfirst=True)
        
        logger.info("✅ whop_webhook_logs table created successfully!")
        logger.info("Table structure:")
        logger.info("  - id (BigInteger, Primary Key)")
        logger.info("  - event_type (String)")
        logger.info("  - event_id (String)")
        logger.info("  - raw_payload (Text)")
        logger.info("  - signature (String)")
        logger.info("  - signature_valid (Boolean)")
        logger.info("  - status (String)")
        logger.info("  - error_message (Text)")
        logger.info("  - membership_id (String)")
        logger.info("  - customer_email (String)")
        logger.info("  - plan_id (String)")
        logger.info("  - amount (String)")
        logger.info("  - currency (String)")
        logger.info("  - received_at (DateTime)")
        logger.info("  - processed_at (DateTime)")
        logger.info("  - created_at (DateTime)")
        logger.info("  - updated_at (DateTime)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creating whop_webhook_logs table: {str(e)}")
        return False

if __name__ == "__main__":
    success = create_whop_webhook_table()
    if success:
        print("\n✅ Setup complete! You can now receive Whop webhooks.")
        print("\nWebhook endpoint: POST /api/v1/webhooks/whop")
        print("View logs: GET /api/v1/webhooks/whop/logs")
        print("View log detail: GET /api/v1/webhooks/whop/logs/{log_id}")
    else:
        print("\n❌ Setup failed. Check the logs for details.")
