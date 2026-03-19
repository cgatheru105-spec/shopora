"""
Quick test to verify checkout flow works correctly
"""
import os
import django
import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shopora.settings')
django.setup()

# Add testserver to ALLOWED_HOSTS for testing
from django.conf import settings
if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append('testserver')

from django.test import Client
from django.contrib.auth import get_user_model
from buyhive.models import Item, Order, Payment
from decimal import Decimal

User = get_user_model()

def test_checkout_flow():
    """Test the complete checkout flow"""
    print("\n🧪 Testing Checkout Flow...\n")
    
    # Generate unique usernames
    timestamp = str(int(time.time() * 1000))
    buyer_username = f'buyer_{timestamp}'
    seller_username = f'seller_{timestamp}'
    
    # Create test user
    user = User.objects.create_user(
        username=buyer_username,
        email=f'{buyer_username}@test.com',
        password='testpass123'
    )
    print(f"✓ Created test user: {user.username}")
    
    # Create test seller
    seller = User.objects.create_user(
        username=seller_username,
        email=f'{seller_username}@test.com',
        password='testpass123'
    )
    print(f"✓ Created test seller: {seller.username}")
    
    # Create test item
    item = Item.objects.create(
        name='Test Product',
        description='A test product for checkout flow',
        price=Decimal('100.00'),
        owner=seller,
        is_available=True
    )
    print(f"✓ Created test item: {item.name} (ID: {item.id}, Price: ${item.price})")
    
    # Create client and login
    client = Client()
    login_success = client.login(username=buyer_username, password='testpass123')
    print(f"✓ Logged in user: {login_success}")
    
    # Test 1: Checkout page without cart (should redirect)
    print("\n📝 Test 1: Accessing checkout without cart...")
    response = client.get('/checkout/')
    print(f"   Response status: {response.status_code}")
    if response.status_code == 302:
        print("   ✓ Correctly redirected (no cart)")
    else:
        print(f"   ✗ Expected redirect, got {response.status_code}")
    
    # Test 2: Review checkout with cart data
    print("\n📝 Test 2: Sending cart to checkout review...")
    review_data = {
        'checkout_action': 'review',
        f'cart_{item.id}': '2',  # 2 units of the item
    }

    response = client.post('/checkout/', data=review_data, follow=False)
    print(f"   Response status: {response.status_code}")
    if response.status_code == 302:
        print("   ✓ Checkout review stored cart and redirected")
    else:
        print(f"   ✗ Expected redirect to review page, got {response.status_code}")

    # Test 3: Submit checkout details
    print("\n📝 Test 3: Submitting checkout form...")
    checkout_data = {
        'checkout_action': 'submit',
        'buyer_name': 'John Doe',
        'buyer_email': 'john@example.com',
        'phone_number': '254712345678',
        'delivery_address': '123 Main Street, Nairobi',
    }

    response = client.post('/checkout/', data=checkout_data, follow=False)
    print(f"   Response status: {response.status_code}")

    # Check if order was created
    orders = Order.objects.filter(buyer=user)
    if orders.exists():
        order = orders.first()
        print(f"   ✓ Order created: {order.order_id}")
        print(f"   ✓ Total amount: ${order.total_amount}")
        print(f"   ✓ Status: {order.status}")
        print(f"   ✓ Redirect target: {response.headers.get('Location')}")
        
        # Check if payment record was created
        payment = Payment.objects.filter(order=order).first()
        if payment:
            print(f"   ✓ Payment record created: ${payment.amount}")
            print(f"   ✓ Phone: {payment.phone_number}")
        else:
            print(f"   ✗ No payment record found")
    else:
        print(f"   ✗ No order created")
    
    print("\n✅ Checkout flow test completed!\n")

if __name__ == '__main__':
    try:
        test_checkout_flow()
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
