from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import time
import json
from datetime import datetime
from config.mysql_database import get_mongodb
from utils.logger import logger


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all HTTP requests to MongoDB"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Capture request body without consuming it
        request_body = None
        body_bytes = b""
        
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body_bytes = await request.body()
                if body_bytes:
                    try:
                        request_body = json.loads(body_bytes.decode())
                    except json.JSONDecodeError:
                        request_body = {"raw": body_bytes.decode()[:500]}
            except Exception as e:
                logger.error(f"Failed to capture request body: {str(e)}")
                request_body = {"error": "Failed to parse body"}
        
        # Get query parameters
        query_params = dict(request.query_params) if request.query_params else None
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Store API log in MongoDB (async, don't wait)
        try:
            db = get_mongodb()
            if db is not None:
                collection = db["api_logs"]
                
                log_entry = {
                    "timestamp": datetime.utcnow(),
                    "method": request.method,
                    "path": request.url.path,
                    "full_url": str(request.url),
                    "query_params": query_params,
                    "request_body": request_body,
                    "status_code": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                    "client_ip": request.client.host if request.client else None,
                    "user_agent": request.headers.get("user-agent"),
                }
                
                # Insert synchronously to avoid coroutine issues
                collection.insert_one(log_entry)
        except Exception as e:
            logger.error(f"Failed to store API log in MongoDB: {str(e)}")
        
        # Log to console/file
        logger.info(
            f"API Request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration": f"{duration:.3f}s"
            }
        )
        
        return response
