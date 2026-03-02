from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt
from config.settings import settings
from config.mysql_database import get_mysql_db
from models.mysql_models import Customer
from utils.logger import logger

# OAuth2 scheme — tokenUrl points to the login endpoint
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/operators/login")

# Optional version (won't raise if token is missing)
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/operators/login", auto_error=False)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_mysql_db)
) -> Customer:
    """
    Validate JWT Bearer token and return the authenticated customer.
    Raises 401 if token is missing, invalid, or expired.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        customer_id: str = payload.get("sub")
        email: str = payload.get("email")

        if customer_id is None or email is None:
            logger.warning("JWT token missing 'sub' or 'email' claim")
            raise credentials_exception

    except jwt.ExpiredSignatureError:
        logger.warning("JWT token has expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {str(e)}")
        raise credentials_exception

    # Look up customer in the database
    customer = db.query(Customer).filter(Customer.id == int(customer_id)).first()

    if customer is None:
        logger.warning(f"Customer ID {customer_id} from token not found in database")
        raise credentials_exception

    if not customer.is_active:
        logger.warning(f"Inactive customer {customer_id} attempted to authenticate")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    return customer


def get_current_user_optional(
    token: str = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_mysql_db)
) -> Customer | None:
    """
    Optional auth — returns the customer if a valid token is provided,
    or None if no token is present. Useful for endpoints that work
    both with and without authentication.
    """
    if token is None:
        return None

    try:
        return _validate_token(token, db)
    except Exception:
        return None


def require_admin(
    current_user: Customer = Depends(get_current_user)
) -> Customer:
    """
    Dependency that ensures the authenticated user is an admin (is_admin=True).
    Use this on admin-only endpoints like Swagger, plan management, etc.
    """
    if not current_user.is_admin:
        logger.warning(f"Non-admin user {current_user.id} ({current_user.email}) attempted admin action")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required. You do not have permission to perform this action.",
        )
    return current_user


def _validate_token(token: str, db: Session) -> Customer | None:
    """Internal helper to validate token without raising exceptions."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        customer_id = payload.get("sub")
        if customer_id is None:
            return None

        customer = db.query(Customer).filter(Customer.id == int(customer_id)).first()
        if customer and customer.is_active:
            return customer
        return None
    except (jwt.InvalidTokenError, Exception):
        return None
