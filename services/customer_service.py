from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime
from models.mysql_models import Customer
from schemas.customer_schema import CustomerCreate, CustomerUpdate
from utils.logger import logger
from services.email_service import send_welcome_email
import secrets
import bcrypt


class CustomerService:
    """Service for managing customers"""
    
    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt"""
        try:
            # Convert password to bytes
            password_bytes = password.encode('utf-8')
            # Bcrypt has a 72-byte limit
            if len(password_bytes) > 72:
                password_bytes = password_bytes[:72]
            # Generate salt and hash
            salt = bcrypt.gensalt()
            hashed = bcrypt.hashpw(password_bytes, salt)
            # Return as string
            return hashed.decode('utf-8')
        except Exception as e:
            logger.error(f"Bcrypt hashing error: {str(e)}")
            raise
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        try:
            password_bytes = plain_password.encode('utf-8')
            if len(password_bytes) > 72:
                password_bytes = password_bytes[:72]
            hashed_bytes = hashed_password.encode('utf-8')
            return bcrypt.checkpw(password_bytes, hashed_bytes)
        except Exception as e:
            logger.error(f"Password verification error: {str(e)}")
            return False
    
    def create_customer(self, db: Session, customer_data: CustomerCreate, google_id: Optional[str] = None, profile_picture: Optional[str] = None) -> Customer:
        """Create a new customer"""
        try:
            # Hash password if provided
            password_hash = None
            if customer_data.password:
                try:
                    password_hash = self.hash_password(customer_data.password)
                except Exception as hash_error:
                    logger.error(f"Password hashing failed: {str(hash_error)}")
                    raise ValueError("Failed to hash password. Please try a different password.")
            
            db_customer = Customer(
                email=customer_data.email,
                full_name=customer_data.full_name,
                phone_number=customer_data.phone_number,
                address=customer_data.address,
                postcode=customer_data.postcode,
                city=customer_data.city,
                country=customer_data.country,
                number_of_children=customer_data.number_of_children,
                password_hash=password_hash,
                google_id=google_id,
                oauth_provider="google" if google_id else None,
                profile_picture=profile_picture,
                is_email_verified=True if google_id else False,  # Auto-verify if from Google
                email_verified_at=datetime.utcnow() if google_id else None,
                verification_token=None if google_id else secrets.token_urlsafe(32)
            )
            db.add(db_customer)
            db.commit()
            db.refresh(db_customer)
            logger.info(f"Customer created: {db_customer.id}")
            
            # Send welcome email asynchronously (don't block registration if email fails)
            try:
                email_sent = send_welcome_email(db_customer.email, db_customer.full_name)
                if email_sent:
                    logger.info(f"Welcome email sent successfully to: {db_customer.email}")
                else:
                    logger.warning(f"Welcome email failed to send to: {db_customer.email}")
            except Exception as email_error:
                logger.error(f"Failed to send welcome email to {db_customer.email}: {str(email_error)}")
                # Don't raise - email failure shouldn't block registration
            
            return db_customer
        except ValueError:
            # Re-raise ValueError for password hashing issues
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create customer: {str(e)}")
            raise
    
    def get_customer_by_id(self, db: Session, customer_id: int) -> Optional[Customer]:
        """Get customer by ID"""
        return db.query(Customer).filter(
            Customer.id == customer_id,
            Customer.is_deleted == False
        ).first()
    
    def get_customer_by_email(self, db: Session, email: str) -> Optional[Customer]:
        """Get customer by email"""
        return db.query(Customer).filter(
            Customer.email == email,
            Customer.is_deleted == False
        ).first()
    
    def get_customer_by_google_id(self, db: Session, google_id: str) -> Optional[Customer]:
        """Get customer by Google ID"""
        return db.query(Customer).filter(
            Customer.google_id == google_id,
            Customer.is_deleted == False
        ).first()
    
    def update_customer(self, db: Session, customer_id: int, customer_data: CustomerUpdate) -> Optional[Customer]:
        """Update customer"""
        try:
            db_customer = self.get_customer_by_id(db, customer_id)
            if not db_customer:
                return None
            
            update_data = customer_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_customer, field, value)
            
            db.commit()
            db.refresh(db_customer)
            logger.info(f"Customer updated: {customer_id}")
            return db_customer
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update customer: {str(e)}")
            raise
    
    def update_last_login(self, db: Session, customer_id: int) -> None:
        """Update last login timestamp"""
        try:
            db_customer = self.get_customer_by_id(db, customer_id)
            if db_customer:
                db_customer.last_login_at = datetime.utcnow()
                db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update last login: {str(e)}")
    
    def verify_email(self, db: Session, token: str) -> Optional[Customer]:
        """Verify customer email"""
        try:
            db_customer = db.query(Customer).filter(
                Customer.verification_token == token,
                Customer.is_deleted == False
            ).first()
            
            if not db_customer:
                return None
            
            db_customer.is_email_verified = True
            db_customer.email_verified_at = datetime.utcnow()
            db_customer.verification_token = None
            
            db.commit()
            db.refresh(db_customer)
            logger.info(f"Email verified for customer: {db_customer.id}")
            return db_customer
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to verify email: {str(e)}")
            raise
    
    def delete_customer(self, db: Session, customer_id: int) -> bool:
        """Soft delete customer"""
        try:
            db_customer = self.get_customer_by_id(db, customer_id)
            if not db_customer:
                return False
            
            db_customer.is_deleted = True
            db_customer.is_active = False
            db.commit()
            logger.info(f"Customer deleted: {customer_id}")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to delete customer: {str(e)}")
            raise
    
    def get_customer_children_sims(self, db: Session, customer_id: int) -> Optional[dict]:
        """Get all children SIM card details for a customer"""
        try:
            from models.mysql_models import Subscriber, ChildSimCard, Subscription
            from models.mysql_models import PlanMaster
            
            # Get customer
            customer = self.get_customer_by_id(db, customer_id)
            if not customer:
                return None
            
            # Get subscriber
            subscriber = db.query(Subscriber).filter(
                Subscriber.customer_id == customer_id
            ).first()
            
            if not subscriber:
                # Customer exists but has no subscriptions yet
                return {
                    "customer_id": customer.id,
                    "customer_name": customer.full_name,
                    "customer_email": customer.email,
                    "total_children": 0,
                    "active_sims": 0,
                    "inactive_sims": 0,
                    "children_sims": []
                }
            
            # Get all child SIM cards with subscription and plan details
            children_sims = db.query(
                ChildSimCard,
                Subscription.subscription_number,
                Subscription.status.label("subscription_status"),
                Subscription.start_date,
                Subscription.end_date,
                PlanMaster.plan_name
            ).join(
                Subscription, ChildSimCard.subscription_id == Subscription.id
            ).outerjoin(
                PlanMaster, Subscription.plan_id == PlanMaster.id
            ).filter(
                ChildSimCard.subscriber_id == subscriber.id
            ).order_by(
                ChildSimCard.created_at.desc()
            ).all()
            
            # Format response
            children_details = []
            active_count = 0
            inactive_count = 0
            
            for sim, sub_number, sub_status, start_date, end_date, plan_name in children_sims:
                if sim.is_active:
                    active_count += 1
                else:
                    inactive_count += 1
                
                children_details.append({
                    "id": sim.id,
                    "child_name": sim.child_name,
                    "child_age": sim.child_age,
                    "child_order": sim.child_order,
                    "sim_number": sim.sim_number,
                    "iccid": sim.iccid,
                    "msisdn": sim.msisdn,
                    "activation_code": sim.activation_code,
                    "sim_type": sim.sim_type,
                    "is_active": sim.is_active,
                    "activation_date": sim.activation_date,
                    "subscription_id": sim.subscription_id,
                    "subscription_number": sub_number,
                    "plan_name": plan_name,
                    "subscription_status": sub_status,
                    "subscription_start_date": start_date,
                    "subscription_end_date": end_date,
                    "created_at": sim.created_at
                })
            
            return {
                "customer_id": customer.id,
                "customer_name": customer.full_name,
                "customer_email": customer.email,
                "total_children": len(children_details),
                "active_sims": active_count,
                "inactive_sims": inactive_count,
                "children_sims": children_details
            }
            
        except Exception as e:
            logger.error(f"Failed to get customer children SIMs: {str(e)}")
            raise


customer_service = CustomerService()
