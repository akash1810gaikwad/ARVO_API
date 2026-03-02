"""
Check Stripe Configuration
This script verifies your Stripe API keys are from the same account
"""
import os
from dotenv import load_dotenv

load_dotenv()

def extract_account_id(key):
    """Extract account ID from Stripe key"""
    if not key:
        return None
    
    parts = key.split('_')
    if len(parts) >= 3:
        # Format: pk_test_51ACCOUNTID... or sk_test_51ACCOUNTID...
        account_part = parts[2]
        if account_part.startswith('51'):
            # Extract first 15 chars after '51'
            return account_part[:17]  # 51 + 15 chars
    return None

def main():
    print("=" * 60)
    print("STRIPE CONFIGURATION CHECK")
    print("=" * 60)
    
    pub_key = os.getenv('STRIPE_PUBLISHABLE_KEY', '')
    secret_key = os.getenv('STRIPE_SECRET_KEY', '')
    
    print(f"\n📋 Current Configuration:")
    print(f"   Publishable Key: {pub_key[:30]}...")
    print(f"   Secret Key:      {secret_key[:30]}...")
    
    pub_account = extract_account_id(pub_key)
    secret_account = extract_account_id(secret_key)
    
    print(f"\n🔍 Account IDs:")
    print(f"   Publishable Key Account: {pub_account}")
    print(f"   Secret Key Account:      {secret_account}")
    
    if pub_account and secret_account:
        if pub_account == secret_account:
            print(f"\n✅ SUCCESS: Keys are from the SAME account!")
            print(f"   Account ID: {pub_account}")
            print(f"\n   Your payment methods should start with:")
            print(f"   pm_1...{pub_account[2:]}...")
        else:
            print(f"\n❌ ERROR: Keys are from DIFFERENT accounts!")
            print(f"\n   Publishable Key Account: {pub_account}")
            print(f"   Secret Key Account:      {secret_account}")
            print(f"\n   This is why payment methods can't be found!")
            print(f"\n   FIX: Get the secret key from account {pub_account}")
            print(f"   Go to: https://dashboard.stripe.com/test/apikeys")
    else:
        print(f"\n⚠️  WARNING: Could not extract account IDs")
        print(f"   Make sure your keys are in the correct format")
    
    print("\n" + "=" * 60)
    print("RECOMMENDATIONS:")
    print("=" * 60)
    
    if pub_account != secret_account:
        print("\n1. IMMEDIATE FIX (for testing):")
        print("   Use promo code to bypass Stripe:")
        print("   - Create promo code: python create_test_promo.py")
        print("   - Use 'promo_code': 'TEST2024' in your request")
        
        print("\n2. PROPER FIX (for production):")
        print("   - Log into Stripe Dashboard")
        print(f"   - Find account with ID: {pub_account}")
        print("   - Copy the SECRET KEY from that account")
        print("   - Update STRIPE_SECRET_KEY in .env")
        print("   - Restart your server")
    else:
        print("\n✅ Your Stripe configuration looks good!")
        print("   If you're still having issues:")
        print("   1. Make sure payment methods exist in this account")
        print("   2. Check you're in TEST mode (not live mode)")
        print("   3. Verify the payment method ID is correct")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
