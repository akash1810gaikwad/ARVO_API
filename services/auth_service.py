from typing import Optional
from sqlalchemy.orm import Session
from google.oauth2 import id_token
from google.auth.transport import requests
from datetime import datetime, timedelta
import jwt
from config.settings import settings
from models.mysql_models import Customer
from services.customer_service import customer_service
from schemas.customer_schema import CustomerCreate
from utils.logger import logger


class AuthService:
    """Service for authentication"""
    
    def verify_google_token(self, token: str) -> Optional[dict]:
        """Verify Google OAuth token (ID token, not access token)"""
        try:
            logger.info(f"Attempting to verify Google token (length: {len(token)})")
            logger.info(f"Using GOOGLE_CLIENT_ID: {settings.GOOGLE_CLIENT_ID[:20]}...")
            
            # Check if this looks like an access token (starts with ya29)
            if token.startswith('ya29.'):
                logger.error("Received access token instead of ID token. Frontend must send credential (ID token), not accessToken.")
                return None
            
            # Verify the token with Google with clock skew tolerance
            # Adding clock_skew_in_seconds to handle minor time differences between client and server
            idinfo = id_token.verify_oauth2_token(
                token,
                requests.Request(),
                settings.GOOGLE_CLIENT_ID,
                clock_skew_in_seconds=10  # Allow 10 seconds clock skew tolerance
            )
            
            logger.info(f"Token verified successfully. Email: {idinfo.get('email')}")
            
            # Verify the issuer
            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                logger.error(f"Invalid token issuer: {idinfo['iss']}")
                return None
            
            return {
                'google_id': idinfo['sub'],
                'email': idinfo['email'],
                'name': idinfo.get('name', ''),
                'picture': idinfo.get('picture', ''),
                'email_verified': idinfo.get('email_verified', False)
            }
        except ValueError as e:
            error_msg = str(e)
            logger.error(f"ValueError verifying Google token: {error_msg}")
            
            # Provide helpful error messages
            if "Token used too early" in error_msg or "Token used too late" in error_msg:
                logger.error("Clock skew detected. This usually means:")
                logger.error("1. Your server's system clock is not synchronized")
                logger.error("2. Run 'w32tm /resync' (Windows) or 'ntpdate' (Linux) to sync time")
                logger.error("3. Or the token was generated with incorrect time")
            else:
                logger.error("Make sure frontend sends the ID token (credential), not the access token")
            
            return None
        except Exception as e:
            logger.error(f"Failed to verify Google token: {type(e).__name__}: {str(e)}")
            return None
    
    def create_access_token(self, customer_id: int, email: str, is_admin: bool = False) -> str:
        """Create JWT access token"""
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode = {
            "sub": str(customer_id),
            "email": email,
            "is_admin": is_admin,
            "exp": expire
        }
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt
    
    def authenticate_with_password(self, db: Session, email: str, password: str) -> Optional[tuple[Customer, str]]:
        """Authenticate customer with email and password"""
        try:
            # Get customer by email
            customer = customer_service.get_customer_by_email(db, email)
            
            if not customer:
                logger.warning(f"Login attempt for non-existent email: {email}")
                return None
            
            # Check if customer has a password set
            if not customer.password_hash:
                logger.warning(f"Login attempt for customer without password: {email}")
                return None
            
            # Verify password
            if not customer_service.verify_password(password, customer.password_hash):
                logger.warning(f"Invalid password for customer: {email}")
                return None
            
            # Check if account is active
            if not customer.is_active:
                logger.warning(f"Login attempt for inactive account: {email}")
                return None
            
            # Update last login
            customer_service.update_last_login(db, customer.id)
            
            # Create access token
            access_token = self.create_access_token(customer.id, customer.email, customer.is_admin)
            
            logger.info(f"Password authentication successful for: {email}")
            return customer, access_token
            
        except Exception as e:
            logger.error(f"Failed to authenticate with password: {str(e)}")
            return None
    
    def authenticate_with_google(self, db: Session, token: str) -> Optional[tuple[Customer, str]]:
        """Authenticate or register customer with Google OAuth"""
        try:
            # Verify Google token
            google_data = self.verify_google_token(token)
            if not google_data:
                return None
            
            # Check if customer exists by Google ID
            customer = customer_service.get_customer_by_google_id(db, google_data['google_id'])
            
            if not customer:
                # Check if customer exists by email
                customer = customer_service.get_customer_by_email(db, google_data['email'])
                
                if customer:
                    # Link Google account to existing customer
                    customer.google_id = google_data['google_id']
                    customer.oauth_provider = 'google'
                    customer.profile_picture = google_data['picture']
                    customer.is_email_verified = True
                    customer.email_verified_at = datetime.utcnow()
                    db.commit()
                    db.refresh(customer)
                else:
                    # Create new customer
                    customer_data = CustomerCreate(
                        email=google_data['email'],
                        full_name=google_data['name'],
                        phone_number=None,
                        address=None,
                        postcode=None,
                        city=None,
                        country=None
                    )
                    customer = customer_service.create_customer(
                        db,
                        customer_data,
                        google_id=google_data['google_id'],
                        profile_picture=google_data['picture']
                    )
            
            # Update last login
            customer_service.update_last_login(db, customer.id)
            
            # Create access token
            access_token = self.create_access_token(customer.id, customer.email, customer.is_admin)
            
            return customer, access_token
            
        except Exception as e:
            logger.error(f"Failed to authenticate with Google: {str(e)}")
            return None


auth_service = AuthService()
