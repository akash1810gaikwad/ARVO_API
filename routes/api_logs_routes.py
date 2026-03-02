from fastapi import APIRouter, Query
from typing import List, Optional
from datetime import datetime, timedelta
from config.mysql_database import get_mongodb
from utils.logger import logger

router = APIRouter(prefix="/api/logs", tags=["API Logs"])


@router.get("/")
async def get_api_logs(
    method: Optional[str] = Query(None, description="Filter by HTTP method"),
    path: Optional[str] = Query(None, description="Filter by path"),
    status_code: Optional[int] = Query(None, description="Filter by status code"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """Get API logs with optional filters"""
    try:
        db = get_mongodb()
        collection = db["api_logs"]
        
        query = {}
        if method:
            query["method"] = method.upper()
        if path:
            query["path"] = {"$regex": path, "$options": "i"}
        if status_code:
            query["status_code"] = status_code
        
        cursor = collection.find(query).sort("timestamp", -1).skip(skip).limit(limit)
        logs = await cursor.to_list(length=limit)
        
        # Convert ObjectId to string
        for log in logs:
            log["id"] = str(log.pop("_id"))
        
        return {
            "total": await collection.count_documents(query),
            "logs": logs
        }
    except Exception as e:
        logger.error(f"Failed to retrieve API logs: {str(e)}")
        raise


@router.get("/stats")
async def get_api_stats():
    """Get API usage statistics"""
    try:
        db = get_mongodb()
        collection = db["api_logs"]
        
        # Last 24 hours
        yesterday = datetime.utcnow() - timedelta(days=1)
        
        total_requests = await collection.count_documents({"timestamp": {"$gte": yesterday}})
        
        # Group by status code
        pipeline = [
            {"$match": {"timestamp": {"$gte": yesterday}}},
            {"$group": {
                "_id": "$status_code",
                "count": {"$sum": 1}
            }}
        ]
        status_counts = await collection.aggregate(pipeline).to_list(length=None)
        
        # Group by method
        pipeline = [
            {"$match": {"timestamp": {"$gte": yesterday}}},
            {"$group": {
                "_id": "$method",
                "count": {"$sum": 1}
            }}
        ]
        method_counts = await collection.aggregate(pipeline).to_list(length=None)
        
        # Average response time
        pipeline = [
            {"$match": {"timestamp": {"$gte": yesterday}}},
            {"$group": {
                "_id": None,
                "avg_duration": {"$avg": "$duration_ms"}
            }}
        ]
        avg_result = await collection.aggregate(pipeline).to_list(length=1)
        avg_duration = avg_result[0]["avg_duration"] if avg_result else 0
        
        return {
            "period": "last_24_hours",
            "total_requests": total_requests,
            "average_response_time_ms": round(avg_duration, 2),
            "by_status_code": {str(item["_id"]): item["count"] for item in status_counts},
            "by_method": {item["_id"]: item["count"] for item in method_counts}
        }
    except Exception as e:
        logger.error(f"Failed to retrieve API stats: {str(e)}")
        raise


@router.get("/{log_id}")
async def get_api_log(log_id: str):
    """Get specific API log by ID"""
    try:
        from bson import ObjectId
        db = get_mongodb()
        collection = db["api_logs"]
        
        log = await collection.find_one({"_id": ObjectId(log_id)})
        if log:
            log["id"] = str(log.pop("_id"))
            return log
        
        return JSONResponse(
            status_code=200,
            content={"message": "API log not found", "data": None}
        )
    except Exception as e:
        logger.error(f"Failed to retrieve API log: {str(e)}")
        raise


@router.delete("/cleanup")
async def manual_cleanup():
    """Manually trigger cleanup of old API logs"""
    try:
        db = get_mongodb()
        collection = db["api_logs"]
        
        cutoff_date = datetime.utcnow() - timedelta(days=2)
        result = await collection.delete_many({"timestamp": {"$lt": cutoff_date}})
        
        return {
            "message": "Cleanup completed",
            "deleted_count": result.deleted_count
        }
    except Exception as e:
        logger.error(f"Failed to cleanup API logs: {str(e)}")
        raise
