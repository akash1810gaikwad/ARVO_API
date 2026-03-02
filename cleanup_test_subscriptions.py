"""
Script to list and cancel all test subscriptions
"""
import stripe
from config.settings import settings

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

def list_all_subscriptions():
    """List all subscriptions"""
    try:
        subscriptions = stripe.Subscription.list(limit=100)
        print(f"\n📋 Found {len(subscriptions.data)} subscriptions:\n")
        
        for sub in subscriptions.data:
            customer = stripe.Customer.retrieve(sub.customer)
            print(f"ID: {sub.id}")
            print(f"Customer: {customer.email}")
            print(f"Status: {sub.status}")
            print(f"Amount: {sub.plan.amount / 100} {sub.plan.currency.upper()}")
            print(f"Trial End: {sub.trial_end}")
            print("-" * 50)
        
        return subscriptions.data
    except stripe.error.StripeError as e:
        print(f"❌ Error listing subscriptions: {str(e)}")
        return []

def cancel_all_trialing_subscriptions():
    """Cancel all subscriptions in trialing status"""
    try:
        subscriptions = stripe.Subscription.list(status='trialing', limit=100)
        print(f"\n🔍 Found {len(subscriptions.data)} trialing subscriptions\n")
        
        for sub in subscriptions.data:
            customer = stripe.Customer.retrieve(sub.customer)
            print(f"Cancelling: {sub.id} for {customer.email}")
            stripe.Subscription.delete(sub.id)
            print(f"✅ Cancelled\n")
        
        print(f"✅ All trialing subscriptions cancelled")
        return True
    except stripe.error.StripeError as e:
        print(f"❌ Error: {str(e)}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("Stripe Subscription Cleanup Tool")
    print("=" * 50)
    
    # List all subscriptions
    list_all_subscriptions()
    
    # Ask for confirmation
    response = input("\n⚠️  Do you want to cancel ALL trialing subscriptions? (yes/no): ")
    
    if response.lower() == 'yes':
        cancel_all_trialing_subscriptions()
    else:
        print("❌ Cancelled. No subscriptions were deleted.")
