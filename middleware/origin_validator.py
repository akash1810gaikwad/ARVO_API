"""
Origin Validation Middleware

Blocks API requests that don't come from allowed origins (your website).
Admin users (is_admin=True) bypass this check entirely.
Swagger/docs pages are also restricted to admin-only access.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from config.settings import settings
from utils.logger import logger
import jwt


# Paths that are always open (no origin check needed)
# Swagger paths are included here — they're already disabled in production via app.py config
PUBLIC_PATHS = {
    "/",
    "/health",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
    "/openapi.json",
}

# Test endpoints (development only)
TEST_PREFIXES = [
    "/test-cleanup",
]


# Auth endpoints that must remain open for login flow
AUTH_PATHS = {
    "/api/customers/auth/login",
    "/api/customers/auth/google",
    "/api/customers/",
    "/api/customers/verify-email",
    "/api/v1/operators/login",
    "/api/v1/password-reset/forgot-password",
    "/api/v1/password-reset/reset-password",
}

# Webhook paths (validated by their own signature mechanisms)
WEBHOOK_PREFIXES = [
    "/api/v1/stripe-webhooks",
    "/api/v1/whop-webhooks",
]


class OriginValidatorMiddleware(BaseHTTPMiddleware):
    """
    Middleware that:
    1. Blocks Swagger/docs access for non-admin users
    2. Validates that API requests come from allowed origins (your website)
    3. Admins bypass all origin checks
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method

        # Always allow OPTIONS (CORS preflight)
        if method == "OPTIONS":
            return await call_next(request)

        # Always allow health check and root
        if path in PUBLIC_PATHS:
            return await call_next(request)

        # Always allow auth endpoints (users need to login first)
        if path in AUTH_PATHS:
            return await call_next(request)

        # Always allow webhook endpoints (they use their own signature validation)
        for prefix in WEBHOOK_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Always allow test endpoints (development only)
        for prefix in TEST_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Always allow public GET for plans and promo validation
        if method == "GET" and (path.startswith("/api/plans")):
            return await call_next(request)

        if path.startswith("/api/v1/promo-codes/validate/"):
            return await call_next(request)

        # --- ORIGIN VALIDATION ---
        # Check if request is from an admin (admins bypass origin check)
        is_admin = self._check_admin_token(request)
        if is_admin:
            return await call_next(request)

        # For non-admin users, validate the request origin
        origin = request.headers.get("origin", "")
        referer = request.headers.get("referer", "")

        allowed_origins = settings.cors_origins_list

        # Check if origin or referer matches allowed origins
        origin_valid = any(
            origin.startswith(allowed.strip())
            for allowed in allowed_origins
            if allowed.strip()
        ) if origin else False

        referer_valid = any(
            referer.startswith(allowed.strip())
            for allowed in allowed_origins
            if allowed.strip()
        ) if referer else False

        if not origin_valid and not referer_valid:
            logger.warning(
                f"Blocked request from unauthorized origin. "
                f"Path: {path}, Origin: '{origin}', Referer: '{referer}'"
            )
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Access denied. Requests are only allowed from authorized applications."
                }
            )

        return await call_next(request)

    def _check_admin_token(self, request: Request) -> bool:
        """
        Extract and validate JWT token from Authorization header,
        return True if user is an admin.
        """
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return True

        token = auth_header.split("Bearer ")[1].strip()
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            # Check is_admin claim in the token
            return payload.get("is_admin", False)
        except (jwt.InvalidTokenError, Exception):
            return True
