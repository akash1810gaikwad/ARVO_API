"""
Whop Payment Gateway Integration
https://docs.whop.com/
"""
import requests
from typing import Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from utils.logger import logger
from config.settings import settings


class WhopService:
    """Service for Whop payment gateway operations"""
    
    def __init__(self):
        self.base_url = "https://api.whop.com/v2"
        self.api_key = getattr(settings, 'WHOP_API_KEY', '')
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def create_checkout_session(
        self,
        plan_id: str,
        customer_email: str,
        customer_name: str,
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a Whop checkout session
        
        Args:
            plan_id: Whop plan/product ID
            customer_email: Customer email
            customer_name: Customer name
            success_url: Redirect URL after successful payment
            cancel_url: Redirect URL if payment cancelled
            metadata: Additional metadata to attach
            
        Returns:
            Checkout session data with checkout URL
        """
        try:
            payload = {
                "plan_id": plan_id,
                "customer_email": customer_email,
                "customer_name": customer_name,
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": metadata or {}
            }
            
            response = requests.post(
                f"{self.base_url}/checkout/sessions",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            response.raise_for_status()
            data = response.json()
            
            logger.info(f"✅ Whop checkout session created: {data.get('id')}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Whop checkout session creation failed: {str(e)}")
            return None
    
    def get_membership(self, membership_id: str) -> Optional[Dict[str, Any]]:
        """
        Get membership details from Whop
        
        Args:
            membership_id: Whop membership ID
            
        Returns:
            Membership data
        """
        try:
            response = requests.get(
                f"{self.base_url}/memberships/{membership_id}",
                headers=self.headers,
                timeout=30
            )
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to get Whop membership: {str(e)}")
            return None
    
    def cancel_membership(self, membership_id: str) -> bool:
        """
        Cancel a Whop membership
        
        Args:
            membership_id: Whop membership ID
            
        Returns:
            True if successful
        """
        try:
            response = requests.post(
                f"{self.base_url}/memberships/{membership_id}/cancel",
                headers=self.headers,
                timeout=30
            )
            
            response.raise_for_status()
            logger.info(f"✅ Whop membership cancelled: {membership_id}")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to cancel Whop membership: {str(e)}")
            return False
    
    def validate_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        webhook_secret: str
    ) -> bool:
        """
        Validate Whop webhook signature
        
        Args:
            payload: Raw webhook payload
            signature: Signature from webhook header
            webhook_secret: Your Whop webhook secret
            
        Returns:
            True if signature is valid
        """
        import hmac
        import hashlib
        
        try:
            expected_signature = hmac.new(
                webhook_secret.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(expected_signature, signature)
            
        except Exception as e:
            logger.error(f"❌ Webhook signature validation failed: {str(e)}")
            return False
    
    def get_customer_memberships(self, customer_email: str) -> Optional[list]:
        """
        Get all memberships for a customer
        
        Args:
            customer_email: Customer email
            
        Returns:
            List of memberships
        """
        try:
            response = requests.get(
                f"{self.base_url}/memberships",
                headers=self.headers,
                params={"email": customer_email},
                timeout=30
            )
            
            response.raise_for_status()
            data = response.json()
            return data.get('data', [])
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to get customer memberships: {str(e)}")
            return None


# Create singleton instance
whop_service = WhopService()
