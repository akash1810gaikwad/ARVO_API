from datetime import datetime
from typing import Optional, Dict, Any, List
from bson import ObjectId
from config.mysql_database import get_mongodb
from schemas.audit_schema import AuditLogCreate
from utils.logger import logger


class AuditService:
    """Service for managing audit logs in MongoDB"""
    
    def __init__(self):
        self.collection_name = "audit_logs"
    
    async def create_audit_log(self, audit_data: AuditLogCreate) -> str:
        """Create a new audit log entry"""
        try:
            db = get_mongodb()
            collection = db[self.collection_name]
            
            log_entry = {
                **audit_data.model_dump(),
                "timestamp": datetime.utcnow()
            }
            
            result = await collection.insert_one(log_entry)
            logger.info(f"Audit log created: {result.inserted_id}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Failed to create audit log: {str(e)}")
            raise
    
    async def get_audit_logs(
        self,
        user_id: Optional[int] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """Retrieve audit logs with filters"""
        try:
            db = get_mongodb()
            collection = db[self.collection_name]
            
            query = {}
            if user_id:
                query["user_id"] = user_id
            if resource:
                query["resource"] = resource
            if action:
                query["action"] = action
            
            cursor = collection.find(query).sort("timestamp", -1).skip(skip).limit(limit)
            logs = await cursor.to_list(length=limit)
            
            # Convert ObjectId to string
            for log in logs:
                log["id"] = str(log.pop("_id"))
            
            return logs
        except Exception as e:
            logger.error(f"Failed to retrieve audit logs: {str(e)}")
            raise
    
    async def get_audit_log_by_id(self, log_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific audit log by ID"""
        try:
            db = get_mongodb()
            collection = db[self.collection_name]
            
            log = await collection.find_one({"_id": ObjectId(log_id)})
            if log:
                log["id"] = str(log.pop("_id"))
            return log
        except Exception as e:
            logger.error(f"Failed to retrieve audit log: {str(e)}")
            raise


audit_service = AuditService()
