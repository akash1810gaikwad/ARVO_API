"""
Quick script to create a test promo code that bypasses payment
Run this to create a promo code for testing subscriptions without Stripe
"""
from sqlalchemy.orm import Session
from config.mysql_database import connect_mysql, MySQLSessionLocal
from models.promo_code_models import PromoCode
from datetime import datetime, timedelta

def create_test_promo():
    """Create a test promo code that bypasses payment"""
    
    # Connect to database
    engine = connect_mysql()
    if not engine:
        print("❌ Failed to connect to MySQL")
        return
    
    db = MySQLSessionLocal()
    
    try:
        # Check if promo already exists
        existing = db.query(PromoCode).filter(PromoCode.code == "TEST2024").first()
        if existing:
            print(f"✅ Promo code 'TEST2024' already exists")
            print(f"   - Bypass Payment: {existing.bypass_payment}")
            print(f"   - Activate SIM: {existing.activate_sim}")
            print(f"   - Uses: {existing.current_uses}/{existing.max_uses or 'unlimited'}")
            return
        
        # Create new promo code
        promo = PromoCode(
            code="TEST2024",
            description="Test promo code for development - bypasses Stripe payment",
            message="Test mode: Payment bypassed",
            is_active=True,
            valid_from=datetime.utcnow(),
            valid_until=datetime.utcnow() + timedelta(days=365),
            max_uses=None,  # Unlimited uses
            current_uses=0,
            bypass_payment=True,  # Skip Stripe payment
            activate_sim=False,  # Don't activate SIM (for testing)
            created_by="system"
        )
        
        db.add(promo)
        db.commit()
        
        print("✅ Test promo code created successfully!")
        print(f"   Code: TEST2024")
        print(f"   - Bypass Payment: True (no Stripe charge)")
        print(f"   - Activate SIM: False (allocate but don't activate)")
        print(f"   - Valid until: {promo.valid_until.strftime('%Y-%m-%d')}")
        print(f"\n📝 Use this in your API request:")
        print(f'   "promo_code": "TEST2024"')
        
    except Exception as e:
        print(f"❌ Error creating promo code: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    create_test_promo()
