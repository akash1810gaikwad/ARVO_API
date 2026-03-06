from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.requests import Request
from starlette.responses import Response
import time
import json
from datetime import datetime
from config.mysql_database import get_mongodb
from utils.logger import logger


class LoggingMiddleware:
    """Pure ASGI middleware to log all HTTP requests to MongoDB.
    WebSocket connections pass through untouched."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        # Only process HTTP requests — let WebSocket and lifespan pass through
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        start_time = time.time()

        # Capture request body without consuming it
        request_body = None
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

        # Capture response status code
        response_status = [None]

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                response_status[0] = message["status"]
            await send(message)

        # Process request
        await self.app(scope, receive, send_wrapper)

        # Calculate duration
        duration = time.time() - start_time
        status_code = response_status[0] or 0

        # Store API log in MongoDB
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
                    "status_code": status_code,
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
                "status_code": status_code,
                "duration": f"{duration:.3f}s"
            }
        )
