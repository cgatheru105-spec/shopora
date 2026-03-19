"""
MPESA/Daraja Integration Utilities
Handles all MPESA API calls and payment processing
"""
import json
import requests
import base64
import logging
from datetime import datetime
from urllib.parse import urlparse
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class MPESAConfigurationError(ValueError):
    """Raised when MPESA settings are present but not usable for sandbox calls."""


class MPESAClient:
    """MPESA Client for handling payment requests and callbacks"""
    
    def __init__(self):
        self.consumer_key = settings.MPESA_CONSUMER_KEY
        self.consumer_secret = settings.MPESA_CONSUMER_SECRET
        self.passkey = settings.MPESA_PASSKEY
        self.business_shortcode = settings.MPESA_BUSINESS_SHORTCODE
        self.environment = settings.MPESA_ENVIRONMENT
        
        # API Endpoints
        if self.environment == 'sandbox':
            self.base_url = 'https://sandbox.safaricom.co.ke'
        else:
            self.base_url = 'https://api.safaricom.co.ke'
        
        self.auth_url = f'{self.base_url}/oauth/v1/generate?grant_type=client_credentials'
        self.stkpush_url = f'{self.base_url}/mpesa/stkpush/v1/processrequest'
        self.stk_query_url = f'{self.base_url}/mpesa/stkpushquery/v1/query'

    def get_callback_url(self):
        """Return a validated callback URL for MPESA requests."""
        callback_url = (getattr(settings, 'MPESA_CALLBACK_URL', '') or '').strip()
        if not callback_url:
            raise MPESAConfigurationError(
                "MPESA_CALLBACK_URL is missing. Set it to a public HTTPS callback URL before initiating sandbox payments."
            )

        parsed = urlparse(callback_url)
        hostname = (parsed.hostname or '').lower()

        if parsed.scheme != 'https':
            raise MPESAConfigurationError(
                "MPESA sandbox requires MPESA_CALLBACK_URL to use HTTPS."
            )

        if not hostname:
            raise MPESAConfigurationError(
                "MPESA_CALLBACK_URL must include a valid public hostname."
            )

        placeholder_hosts = {'your-domain.com', 'www.your-domain.com'}
        local_hosts = {'localhost', '127.0.0.1', '0.0.0.0', 'testserver'}
        if hostname in placeholder_hosts or hostname in local_hosts or hostname.endswith('.local'):
            raise MPESAConfigurationError(
                "MPESA sandbox requires MPESA_CALLBACK_URL to point to a public HTTPS domain, not a placeholder or local address."
            )

        return callback_url
    
    def get_access_token(self):
        """Get MPESA access token"""
        try:
            auth_string = f'{self.consumer_key}:{self.consumer_secret}'
            auth_bytes = auth_string.encode('ascii')
            auth_base64 = str(base64.b64encode(auth_bytes), 'utf-8')
            
            headers = {
                'Authorization': f'Basic {auth_base64}'
            }
            
            response = requests.get(self.auth_url, headers=headers, timeout=5)
            response.raise_for_status()
            
            token_data = response.json()
            return token_data.get('access_token')
        except Exception as e:
            logger.error(f"Failed to get MPESA access token: {str(e)}")
            raise
    
    def initiate_stk_push(self, phone_number, amount, order_id, callback_url):
        """
        Initiate STK Push for payment
        
        Args:
            phone_number: Customer phone number (format: 254XXXXXXXXX)
            amount: Amount in KES (integer)
            order_id: Unique order identifier
            callback_url: URL for payment callback
        
        Returns:
            dict: Response with CheckoutRequestID
        """
        try:
            # Normalize phone number
            phone_number = self._normalize_phone(phone_number)
            amount = int(amount)
            
            # Get timestamp
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            
            # Generate password
            password_string = f'{self.business_shortcode}{self.passkey}{timestamp}'
            password = base64.b64encode(password_string.encode()).decode()
            
            headers = {
                'Authorization': f'Bearer {self.get_access_token()}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'BusinessShortCode': self.business_shortcode,
                'Password': password,
                'Timestamp': timestamp,
                'TransactionType': 'CustomerPayBillOnline',
                'Amount': amount,
                'PartyA': phone_number,
                'PartyB': self.business_shortcode,
                'PhoneNumber': phone_number,
                'CallBackURL': callback_url,
                'AccountReference': order_id,
                'TransactionDesc': f'Payment for order {order_id}'
            }
            
            response = requests.post(
                self.stkpush_url,
                json=payload,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"STK Push initiated - Order: {order_id}, Response: {result}")
            
            return result
        except Exception as e:
            logger.error(f"Failed to initiate STK push for order {order_id}: {str(e)}")
            raise
    
    def query_stk_status(self, checkout_request_id):
        """
        Query the status of an STK push request
        
        Args:
            checkout_request_id: The CheckoutRequestID from initiate_stk_push
        
        Returns:
            dict: Response with payment status
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password_string = f'{self.business_shortcode}{self.passkey}{timestamp}'
            password = base64.b64encode(password_string.encode()).decode()
            
            headers = {
                'Authorization': f'Bearer {self.get_access_token()}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'BusinessShortCode': self.business_shortcode,
                'Password': password,
                'Timestamp': timestamp,
                'CheckoutRequestID': checkout_request_id
            }
            
            response = requests.post(
                self.stk_query_url,
                json=payload,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            
            return response.json()
        except Exception as e:
            logger.error(f"Failed to query STK status for {checkout_request_id}: {str(e)}")
            raise
    
    def _normalize_phone(self, phone_number):
        """
        Normalize phone number to format 254XXXXXXXXX
        
        Args:
            phone_number: Phone number in various formats
        
        Returns:
            str: Normalized phone number
        """
        # Remove any non-digit characters
        digits = ''.join(filter(str.isdigit, str(phone_number)))
        
        # If it starts with 0, replace with 254
        if digits.startswith('0'):
            digits = '254' + digits[1:]
        # If it doesn't start with 254, add it
        elif not digits.startswith('254'):
            digits = '254' + digits
        
        return digits


def create_mpesa_client():
    """Factory function to create MPESA client"""
    return MPESAClient()
