"""
Script to cancel a test Stripe subscription
"""
import stripe
from config.settings import settings

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

def cancel_subscription(subscription_id: str):
    """Cancel a Stripe subscription"""
    try:
        # Cancel the subscription
        subscription = stripe.Subscription.delete(subscription_id)
        print(f"✅ Subscription {subscription_id} cancelled successfully")
        print(f"Status: {subscription.status}")
        return True
    except stripe.error.StripeError as e:
        print(f"❌ Error cancelling subscription: {str(e)}")
        return False

if __name__ == "__main__":
    # Replace with your test subscription ID
    test_subscription_id = "sub_1T4IvSADmJ0oD5zqdWyBYkk8"
    
    print(f"Cancelling subscription: {test_subscription_id}")
    cancel_subscription(test_subscription_id)
