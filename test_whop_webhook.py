"""
Test script to simulate a Whop webhook call
This helps verify the webhook endpoint is working correctly
"""
import requests
import json
import hmac
import hashlib
from config.settings import settings

def test_whop_webhook():
    """Send a test webhook to the local server"""
    
    # Test webhook payload
    payload = {
        "id": "evt_test_123456",
        "type": "membership.created",
        "data": {
            "id": "mem_test_123456",
            "email": "test@example.com",
            "plan_id": "plan_test_123",
            "status": "active",
            "amount": 2999,  # £29.99 in pence
            "currency": "gbp"
        }
    }
    
    payload_str = json.dumps(payload)
    payload_bytes = payload_str.encode('utf-8')
    
    # Generate signature
    webhook_secret = getattr(settings, 'WHOP_WEBHOOK_SECRET', '')
    if webhook_secret:
        signature = hmac.new(
            webhook_secret.encode(),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
    else:
        signature = "test_signature"
    
    # Send webhook
    url = "http://localhost:8000/api/v1/webhooks/whop"
    headers = {
        "Content-Type": "application/json",
        "x-whop-signature": signature
    }
    
    print(f"Sending test webhook to {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print(f"Signature: {signature}")
    print()
    
    try:
        response = requests.post(url, data=payload_bytes, headers=headers)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("\n✅ Webhook test successful!")
            print("\nCheck the logs at: GET http://localhost:8000/api/v1/webhooks/whop/logs")
        else:
            print("\n❌ Webhook test failed!")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Make sure the API is running on http://localhost:8000")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    print("=" * 60)
    print("Whop Webhook Test")
    print("=" * 60)
    print()
    test_whop_webhook()
