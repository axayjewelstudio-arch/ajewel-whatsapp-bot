# ═══════════════════════════════════════════════════════════
# AJewelBot v3 - Professional WhatsApp Commerce Bot
# Complete Flow Architecture with Session Management
# ═══════════════════════════════════════════════════════════

import os
import json
import time
import threading
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

load_dotenv()
app = Flask(__name__)
CORS(app)

# ── Environment Variables ──
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN')
WHATSAPP_PHONE_ID = os.getenv('WHATSAPP_PHONE_ID')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN')
GOOGLE_CREDENTIALS = os.getenv('GOOGLE_CREDENTIALS')
SHOPIFY_STORE = os.getenv('SHOPIFY_STORE', 'a-jewel-studio-3.myshopify.com')
SHOPIFY_ACCESS_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN')
RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET')

# ── URLs ──
SHEET_ID = "1w-4Zi65AqsQZFJIr1GLrDrW9BJNez8Wtr-dTL8oBLbs"
JOIN_US_URL = "https://a-jewel-studio-3.myshopify.com/pages/join-us"
BACKEND_API_URL = os.getenv('BACKEND_API_URL', 'https://ajewelbot-v2-backend.onrender.com/api')
WHATSAPP_CATALOG_ID = os.getenv('WHATSAPP_CATALOG_ID', '')
LOGO_IMAGE_URL = 'https://a-jewel-studio-3.myshopify.com/cdn/shop/files/A_Jewel_Studio.png?v=1771946995&width=130'

# ── Session Storage (In-memory) ──
user_sessions = {}
SESSION_TIMEOUT = 1800  # 30 minutes

# ── Keep-Alive Thread ──
def keep_alive():
    """Ping server every 12 minutes to prevent sleep"""
    while True:
        try:
            time.sleep(720)  # 12 minutes
            print(f"[{datetime.now()}] Keep-alive ping")
        except Exception as e:
            print(f"Keep-alive error: {e}")

# Start keep-alive thread
threading.Thread(target=keep_alive, daemon=True).start()

print("✅ AJewelBot v3 Initialized")
print("✅ Keep-alive thread started")
print(f"✅ Logo URL: {LOGO_IMAGE_URL}")
# ═══════════════════════════════════════════════════════════
# GOOGLE SHEETS SERVICE
# ═══════════════════════════════════════════════════════════

def get_google_sheet():
    """Connect to Google Sheets"""
    try:
        creds_dict = json.loads(GOOGLE_CREDENTIALS)
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID).worksheet('Registrations')
    except Exception as e:
        print(f"Google Sheets Error: {e}")
        return None

def log_to_column_a(phone_number):
    """Log phone number to Column A (no duplicates)"""
    try:
        sheet = get_google_sheet()
        if not sheet:
            return False
        
        # Check if exists
        all_values = sheet.col_values(1)
        if phone_number in all_values:
            print(f"Phone {phone_number} already logged")
            return True
        
        # Append to Column A
        sheet.append_row([phone_number])
        print(f"✅ Logged to Column A: {phone_number}")
        return True
    except Exception as e:
        print(f"Column A logging error: {e}")
        return False

# ═══════════════════════════════════════════════════════════
# SHOPIFY SERVICE
# ═══════════════════════════════════════════════════════════

def get_shopify_customer(phone_number):
    """Get customer from Shopify by phone"""
    try:
        url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/customers/search.json"
        headers = {
            'X-Shopify-Access-Token': SHOPIFY_ACCESS_TOKEN,
            'Content-Type': 'application/json'
        }
        params = {'query': f'phone:{phone_number}'}
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('customers'):
                return data['customers'][0]
        return None
    except Exception as e:
        print(f"Shopify customer fetch error: {e}")
        return None

def get_shopify_order(order_number):
    """Get order from Shopify by order number"""
    try:
        url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/orders.json"
        headers = {
            'X-Shopify-Access-Token': SHOPIFY_ACCESS_TOKEN,
            'Content-Type': 'application/json'
        }
        params = {'name': order_number}
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('orders'):
                return data['orders'][0]
        return None
    except Exception as e:
        print(f"Shopify order fetch error: {e}")
        return None

def is_b2b_customer(customer):
    """Check if customer is B2B based on tags"""
    if not customer:
        return False
    tags = customer.get('tags', '').lower()
    return 'b2b' in tags or 'wholesaler' in tags
# ═══════════════════════════════════════════════════════════
# SESSION MANAGEMENT
# ═══════════════════════════════════════════════════════════

def get_session(phone_number):
    """Get or create user session"""
    current_time = datetime.now()
    
    if phone_number in user_sessions:
        session = user_sessions[phone_number]
        last_activity = session.get('last_activity')
        
        # Check timeout (30 minutes)
        if last_activity and (current_time - last_activity).seconds > SESSION_TIMEOUT:
            print(f"Session expired for {phone_number}")
            clear_session(phone_number)
            return create_session(phone_number)
        
        # Update last activity
        session['last_activity'] = current_time
        return session
    
    return create_session(phone_number)

def create_session(phone_number):
    """Create new session"""
    user_sessions[phone_number] = {
        'phone': phone_number,
        'state': 'idle',
        'data': {},
        'last_activity': datetime.now(),
        'created_at': datetime.now()
    }
    return user_sessions[phone_number]

def update_session(phone_number, state=None, data=None):
    """Update session state and data"""
    session = get_session(phone_number)
    if state:
        session['state'] = state
    if data:
        session['data'].update(data)
    session['last_activity'] = datetime.now()
    return session

def clear_session(phone_number):
    """Clear user session"""
    if phone_number in user_sessions:
        del user_sessions[phone_number]
        print(f"Session cleared for {phone_number}")
# ═══════════════════════════════════════════════════════════
# WHATSAPP SEND FUNCTIONS
# ═══════════════════════════════════════════════════════════

def send_whatsapp_text(to_number, message_text):
    """Send text message"""
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "text": {"body": message_text}
    }
    try:
        r = requests.post(url, json=payload, headers=headers)
        print(f"Text sent to {to_number}: {r.status_code}")
        return r.json()
    except Exception as e:
        print(f"WhatsApp text error: {e}")
        return None

def send_whatsapp_image(to_number, image_url, caption=''):
    """Send image message"""
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "image",
        "image": {
            "link": image_url,
            "caption": caption
        }
    }
    try:
        r = requests.post(url, json=payload, headers=headers)
        print(f"Image sent to {to_number}: {r.status_code}")
        return r.json()
    except Exception as e:
        print(f"WhatsApp image error: {e}")
        return None

def send_whatsapp_buttons(to_number, body_text, buttons):
    """Send interactive buttons (max 3)"""
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body_text},
            "action": {
                "buttons": buttons[:3]
            }
        }
    }
    try:
        r = requests.post(url, json=payload, headers=headers)
        print(f"Buttons sent to {to_number}: {r.status_code}")
        return r.json()
    except Exception as e:
        print(f"WhatsApp buttons error: {e}")
        return None

def send_whatsapp_cta_button(to_number, body_text, button_text, button_url):
    """Send CTA URL button"""
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "interactive",
        "interactive": {
            "type": "cta_url",
            "body": {"text": body_text},
            "action": {
                "name": "cta_url",
                "parameters": {
                    "display_text": button_text,
                    "url": button_url
                }
            }
        }
    }
    try:
        r = requests.post(url, json=payload, headers=headers)
        if r.status_code == 200:
            return r.json()
        else:
            # Fallback to text
            fallback = f"{body_text}\n\n{button_text}: {button_url}"
            return send_whatsapp_text(to_number, fallback)
    except Exception as e:
        print(f"WhatsApp CTA error: {e}")
        return None

def send_whatsapp_catalog(to_number, body_text="Browse our collection"):
    """Send WhatsApp native catalog"""
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "interactive",
        "interactive": {
            "type": "catalog_message",
            "body": {"text": body_text},
            "action": {
                "name": "catalog_message"
            }
        }
    }
    try:
        r = requests.post(url, json=payload, headers=headers)
        print(f"Catalog sent to {to_number}: {r.status_code}")
        return r.json()
    except Exception as e:
        print(f"WhatsApp catalog error: {e}")
        return None
# ═══════════════════════════════════════════════════════════
# ANALYTICS LOGGING
# ═══════════════════════════════════════════════════════════

def log_analytics(event_type, data):
    """Log analytics event to backend"""
    try:
        url = f"{BACKEND_API_URL}/analytics/log"
        payload = {
            'event_type': event_type,
            'timestamp': datetime.now().isoformat(),
            'data': data
        }
        requests.post(url, json=payload, timeout=5)
        print(f"✅ Analytics logged: {event_type}")
    except Exception as e:
        print(f"Analytics logging error: {e}")

# ═══════════════════════════════════════════════════════════
# FLOW MESSAGES - NEW CUSTOMER
# ═══════════════════════════════════════════════════════════

def send_new_customer_signup(to_number):
    """Flow: New customer - Send signup prompt"""
    # Send logo image
    send_whatsapp_image(
        to_number,
        LOGO_IMAGE_URL,
        caption="Welcome to A Jewel Studio"
    )
    
    # Send Join Us button
    join_url = f"{JOIN_US_URL}?wa={to_number}"
    send_whatsapp_cta_button(
        to_number,
        "Tap Join Us below to become a part of our family.",
        "Join Us",
        join_url
    )
    
    # Update session
    update_session(to_number, state='awaiting_signup')
    
    # Log analytics
    log_analytics('new_customer_signup_prompt', {'phone': to_number})

# ═══════════════════════════════════════════════════════════
# FLOW MESSAGES - B2B CUSTOMER
# ═══════════════════════════════════════════════════════════

def send_b2b_welcome(to_number, customer_name):
    """Flow: B2B customer welcome"""
    message = f"Welcome back, {customer_name}.\n\nWe are delighted to have you here."
    send_whatsapp_text(to_number, message)
    
    # Send catalog
    send_whatsapp_catalog(to_number, "Browse our digital jewellery files collection.")
    
    # Log analytics
    log_analytics('b2b_catalog_shown', {'phone': to_number, 'name': customer_name})

# ═══════════════════════════════════════════════════════════
# FLOW MESSAGES - RETAIL CUSTOMER
# ═══════════════════════════════════════════════════════════

def send_retail_welcome(to_number, customer_name):
    """Flow: Retail customer welcome"""
    message = f"Welcome back, {customer_name}.\n\nWe are delighted to have you here.\n\nWould you like to explore custom jewellery designs?"
    
    buttons = [
        {"id": "custom_yes", "title": "Yes"},
        {"id": "custom_no", "title": "No"}
    ]
    
    send_whatsapp_buttons(to_number, message, buttons)
    
    # Update session
    update_session(to_number, state='awaiting_custom_choice')
    
    # Log analytics
    log_analytics('retail_menu_shown', {'phone': to_number, 'name': customer_name})
# ═══════════════════════════════════════════════════════════
# MESSAGE HANDLERS - TEXT MESSAGES
# ═══════════════════════════════════════════════════════════

def handle_text_message(phone_number, message_text):
    """Handle incoming text messages"""
    print(f"📩 Text from {phone_number}: {message_text}")
    
    # Log to Column A
    log_to_column_a(phone_number)
    
    # Get session
    session = get_session(phone_number)
    current_state = session.get('state', 'idle')
    
    # Check if tracking order
    if message_text.lower().startswith('track'):
        handle_order_tracking(phone_number, message_text)
        return
    
    # Check if referral request
    if message_text.lower() == 'referral':
        handle_referral_request(phone_number)
        return
    
    # Get customer from Shopify
    customer = get_shopify_customer(phone_number)
    
    # NEW CUSTOMER - Not in Shopify
    if not customer:
        print(f"🆕 New customer: {phone_number}")
        send_new_customer_signup(phone_number)
        return
    
    # EXISTING CUSTOMER
    customer_name = customer.get('first_name', 'Customer')
    
    # Check if B2B or Retail
    if is_b2b_customer(customer):
        print(f"🏢 B2B customer: {customer_name}")
        send_b2b_welcome(phone_number, customer_name)
    else:
        print(f"🛍️ Retail customer: {customer_name}")
        send_retail_welcome(phone_number, customer_name)

# ═══════════════════════════════════════════════════════════
# MESSAGE HANDLERS - BUTTON RESPONSES
# ═══════════════════════════════════════════════════════════

def handle_button_response(phone_number, button_id):
    """Handle button click responses"""
    print(f"🔘 Button clicked: {button_id} by {phone_number}")
    
    session = get_session(phone_number)
    customer = get_shopify_customer(phone_number)
    customer_name = customer.get('first_name', 'Customer') if customer else 'Customer'
    
    # CUSTOM JEWELLERY - YES
    if button_id == 'custom_yes':
        message = f"Wonderful, {customer_name}!\n\nOur design team would love to discuss your requirements.\n\nPlease book an appointment at your convenience."
        
        appointment_url = "https://calendly.com/ajewelstudio/consultation"  # Replace with actual URL
        send_whatsapp_cta_button(
            phone_number,
            message,
            "Book Appointment",
            appointment_url
        )
        
        log_analytics('custom_appointment_link_sent', {'phone': phone_number})
        clear_session(phone_number)
    
    # CUSTOM JEWELLERY - NO
    elif button_id == 'custom_no':
        message = f"No problem, {customer_name}!\n\nBrowse our ready-to-order collection below."
        send_whatsapp_text(phone_number, message)
        
        # Send catalog
        send_whatsapp_catalog(phone_number, "Explore our exclusive jewellery designs.")
        
        log_analytics('retail_catalog_shown', {'phone': phone_number})
        clear_session(phone_number)
    
    # VIEW CART (Abandoned cart reminder)
    elif button_id == 'view_cart':
        cart_url = f"https://{SHOPIFY_STORE}/cart"
        send_whatsapp_cta_button(
            phone_number,
            "Your cart is waiting for you.",
            "View Cart",
            cart_url
        )
    
    # CONTINUE SHOPPING
    elif button_id == 'continue_shopping':
        send_whatsapp_catalog(phone_number, "Continue browsing our collection.")
    
    else:
        send_whatsapp_text(phone_number, "Thank you for your response.")

# ═══════════════════════════════════════════════════════════
# MESSAGE HANDLERS - WHATSAPP CART ORDER
# ═══════════════════════════════════════════════════════════

def handle_whatsapp_cart_order(phone_number, order_data):
    """Handle WhatsApp native catalog order"""
    print(f"🛒 Order received from {phone_number}")
    
    try:
        # Extract order items
        items = order_data.get('order', {}).get('product_items', [])
        
        if not items:
            send_whatsapp_text(phone_number, "We could not process your order. Please try again.")
            return
        
        # Calculate total
        total_amount = 0
        order_summary = "*Order Summary:*\n\n"
        
        for idx, item in enumerate(items, 1):
            product_name = item.get('product_retailer_id', 'Product')
            quantity = item.get('quantity', 1)
            price = item.get('item_price', 0)
            item_total = quantity * price
            total_amount += item_total
            
            order_summary += f"{idx}. {product_name}\n"
            order_summary += f"   Qty: {quantity} × ₹{price} = ₹{item_total}\n\n"
        
        order_summary += f"━━━━━━━━━━━━━━━━━━━━\n"
        order_summary += f"*Total: ₹{total_amount}*"
        
        # Get customer
        customer = get_shopify_customer(phone_number)
        
        # Check if B2B
        if customer and is_b2b_customer(customer):
            # B2B - Generate payment link
            handle_b2b_order_payment(phone_number, total_amount, order_summary, items)
        else:
            # RETAIL - Manual follow-up
            handle_retail_order_manual(phone_number, order_summary)
        
    except Exception as e:
        print(f"Order handling error: {e}")
        send_whatsapp_text(phone_number, "We encountered an error processing your order. Our team will contact you shortly.")

def handle_b2b_order_payment(phone_number, amount, order_summary, items):
    """Handle B2B order with Razorpay payment"""
    try:
        # Create order ID
        order_id = f"AJS{int(time.time())}"
        
        # Generate Razorpay payment link
        payment_url = generate_razorpay_link(order_id, amount, phone_number)
        
        if payment_url:
            message = f"{order_summary}\n\nPlease complete your payment to confirm the order."
            send_whatsapp_cta_button(
                phone_number,
                message,
                "Pay Now",
                payment_url
            )
            
            # Store order data in session
            update_session(phone_number, data={
                'order_id': order_id,
                'amount': amount,
                'items': items
            })
            
            log_analytics('b2b_order_created', {
                'phone': phone_number,
                'order_id': order_id,
                'amount': amount
            })
        else:
            send_whatsapp_text(phone_number, f"{order_summary}\n\nOur team will contact you shortly to complete the payment.")
    
    except Exception as e:
        print(f"B2B payment error: {e}")
        send_whatsapp_text(phone_number, "Our team will contact you shortly to process your order.")

def handle_retail_order_manual(phone_number, order_summary):
    """Handle retail order - manual follow-up"""
    message = f"{order_summary}\n\nThank you for your order!\n\nOur team will contact you shortly to confirm the details and arrange delivery."
    send_whatsapp_text(phone_number, message)
    
    log_analytics('retail_order_created', {'phone': phone_number})

# ═══════════════════════════════════════════════════════════
# RAZORPAY PAYMENT LINK GENERATION
# ═══════════════════════════════════════════════════════════

def generate_razorpay_link(order_id, amount, phone_number):
    """Generate Razorpay payment link"""
    try:
        url = "https://api.razorpay.com/v1/payment_links"
        auth = (RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)
        
        payload = {
            "amount": int(amount * 100),  # Amount in paise
            "currency": "INR",
            "description": f"Order Payment - {order_id}",
            "customer": {
                "contact": phone_number
            },
            "notify": {
                "sms": False,
                "email": False,
                "whatsapp": False
            },
            "reminder_enable": False,
            "callback_url": f"{BACKEND_API_URL}/payment/callback",
            "callback_method": "get"
        }
        
        response = requests.post(url, json=payload, auth=auth)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('short_url')
        else:
            print(f"Razorpay error: {response.text}")
            return None
    
    except Exception as e:
        print(f"Payment link generation error: {e}")
        return None
# ═══════════════════════════════════════════════════════════
# ORDER TRACKING
# ═══════════════════════════════════════════════════════════

def handle_order_tracking(phone_number, message_text):
    """Handle order tracking request"""
    try:
        # Extract order number (e.g., "Track #1234" or "Track 1234")
        order_number = message_text.replace('track', '').replace('#', '').strip()
        
        if not order_number:
            send_whatsapp_text(phone_number, "Please provide your order number.\n\nExample: Track #1234")
            return
        
        # Get order from Shopify
        order = get_shopify_order(f"#{order_number}")
        
        if not order:
            send_whatsapp_text(phone_number, f"We could not find order #{order_number}.\n\nPlease check the order number and try again.")
            return
        
        # Get order details
        order_status = order.get('financial_status', 'Unknown')
        fulfillment_status = order.get('fulfillment_status', 'unfulfilled')
        
        # Build status message
        status_message = f"*Order #{order_number}*\n\n"
        status_message += f"Payment Status: {order_status.title()}\n"
        status_message += f"Fulfillment Status: {fulfillment_status.title()}\n\n"
        
        # Check for tracking
        fulfillments = order.get('fulfillments', [])
        if fulfillments:
            tracking_url = fulfillments[0].get('tracking_url')
            tracking_number = fulfillments[0].get('tracking_number')
            
            if tracking_url:
                status_message += f"Tracking Number: {tracking_number}\n\n"
                send_whatsapp_cta_button(
                    phone_number,
                    status_message,
                    "Track Shipment",
                    tracking_url
                )
                return
        
        send_whatsapp_text(phone_number, status_message + "Our team will update you once your order is dispatched.")
    
    except Exception as e:
        print(f"Order tracking error: {e}")
        send_whatsapp_text(phone_number, "We encountered an error. Please contact our support team.")

# ═══════════════════════════════════════════════════════════
# REFERRAL SYSTEM
# ═══════════════════════════════════════════════════════════

def handle_referral_request(phone_number):
    """Handle referral link request"""
    try:
        # Get customer
        customer = get_shopify_customer(phone_number)
        
        if not customer:
            send_whatsapp_text(phone_number, "Please register first to get your referral link.")
            send_new_customer_signup(phone_number)
            return
        
        # Generate referral code
        customer_id = str(customer.get('id', ''))
        first_name = customer.get('first_name', 'USER')
        
        # Code: First 3 letters + Last 4 digits of ID
        referral_code = f"{first_name[:3].upper()}{customer_id[-4:]}"
        
        # Generate referral URL
        referral_url = f"{JOIN_US_URL}?ref={referral_code}"
        
        # Send referral message
        message = f"*Your Referral Code:* {referral_code}\n\n"
        message += f"Share this link with your friends:\n{referral_url}\n\n"
        message += "*Benefits:*\n"
        message += "• Your friend gets 10% OFF on first order\n"
        message += "• You earn ₹500 credit for each successful referral\n\n"
        message += "Start sharing and earn rewards!"
        
        send_whatsapp_text(phone_number, message)
        
        log_analytics('referral_link_sent', {
            'phone': phone_number,
            'code': referral_code
        })
    
    except Exception as e:
        print(f"Referral error: {e}")
        send_whatsapp_text(phone_number, "We encountered an error. Please try again later.")
# ═══════════════════════════════════════════════════════════
# PAYMENT CALLBACK
# ═══════════════════════════════════════════════════════════

def handle_payment_callback(payment_data):
    """Handle Razorpay payment callback"""
    try:
        event_type = payment_data.get('event')
        payload = payment_data.get('payload', {})
        payment = payload.get('payment', {})
        
        phone_number = payment.get('contact')
        amount = payment.get('amount', 0) / 100  # Convert from paise
        status = payment.get('status')
        
        if not phone_number:
            return
        
        if event_type == 'payment.captured' or status == 'captured':
            # Payment successful
            message = f"✅ Payment Received!\n\nAmount: ₹{amount}\n\nYour order is confirmed. You will receive your digital files shortly."
            send_whatsapp_text(phone_number, message)
            
            # Send download link (if B2B)
            download_url = "https://a-jewel-studio-3.myshopify.com/pages/downloads"  # Replace with actual
            send_whatsapp_cta_button(
                phone_number,
                "Your files are ready for download.",
                "Download Files",
                download_url
            )
            
            log_analytics('payment_successful', {
                'phone': phone_number,
                'amount': amount
            })
        
        else:
            # Payment failed/cancelled
            message = f"❌ Payment {status.title()}\n\nAmount: ₹{amount}\n\nPlease try again or contact our support team."
            send_whatsapp_text(phone_number, message)
            
            log_analytics('payment_failed', {
                'phone': phone_number,
                'amount': amount,
                'status': status
            })
    
    except Exception as e:
        print(f"Payment callback error: {e}")

# ═══════════════════════════════════════════════════════════
# ABANDONED CART REMINDER
# ═══════════════════════════════════════════════════════════

def send_abandoned_cart_reminder(phone_number, cart_data):
    """Send abandoned cart reminder"""
    try:
        message = "You left items in your cart 🛒\n\nWould you like to complete your purchase?"
        
        buttons = [
            {"id": "view_cart", "title": "View Cart"},
            {"id": "continue_shopping", "title": "Continue Shopping"}
        ]
        
        send_whatsapp_buttons(phone_number, message, buttons)
        
        log_analytics('abandoned_cart_reminder', {'phone': phone_number})
    
    except Exception as e:
        print(f"Abandoned cart error: {e}")

# ═══════════════════════════════════════════════════════════
# BIRTHDAY/ANNIVERSARY WISHES
# ═══════════════════════════════════════════════════════════

def send_birthday_wish(phone_number, customer_name):
    """Send birthday wish with discount"""
    message = f"🎉 Happy Birthday, {customer_name}!\n\n"
    message += "Celebrate your special day with an exclusive 15% OFF on all products.\n\n"
    message += "Use code: *BDAY15*\n\n"
    message += "Valid for 7 days."
    
    send_whatsapp_text(phone_number, message)
    send_whatsapp_catalog(phone_number, "Browse our collection and treat yourself!")
    
    log_analytics('birthday_wish_sent', {'phone': phone_number})

def send_anniversary_wish(phone_number, customer_name):
    """Send anniversary wish with discount"""
    message = f"💍 Happy Anniversary, {customer_name}!\n\n"
    message += "Celebrate your special day with an exclusive 20% OFF on all products.\n\n"
    message += "Use code: *ANNIV20*\n\n"
    message += "Valid for 7 days."
    
    send_whatsapp_text(phone_number, message)
    send_whatsapp_catalog(phone_number, "Browse our collection and make this day memorable!")
    
    log_analytics('anniversary_wish_sent', {'phone': phone_number})
# ═══════════════════════════════════════════════════════════
# BROADCAST CAMPAIGN
# ═══════════════════════════════════════════════════════════

def send_broadcast_message(phone_list, message, button_text=None, button_url=None):
    """Send broadcast message to multiple customers"""
    success_count = 0
    
    for phone in phone_list:
        try:
            if button_text and button_url:
                send_whatsapp_cta_button(phone, message, button_text, button_url)
            else:
                send_whatsapp_text(phone, message)
            
            success_count += 1
            time.sleep(1)  # Rate limiting
        
        except Exception as e:
            print(f"Broadcast error for {phone}: {e}")
    
    return success_count

# ═══════════════════════════════════════════════════════════
# ERROR HANDLING
# ═══════════════════════════════════════════════════════════

def handle_error(phone_number, error_message):
    """Handle errors gracefully"""
    try:
        send_whatsapp_text(
            phone_number,
            "We encountered an error processing your request. Our team has been notified and will assist you shortly."
        )
        clear_session(phone_number)
        print(f"❌ Error for {phone_number}: {error_message}")
    except Exception as e:
        print(f"Error handler failed: {e}")
# ═══════════════════════════════════════════════════════════
# WEBHOOK ROUTES
# ═══════════════════════════════════════════════════════════

@app.route('/', methods=['GET'])
def home():
    """Health check endpoint"""
    return jsonify({
        "status": "running",
        "app": "AJewelBot v3",
        "version": "3.0.0",
        "timestamp": datetime.now().isoformat(),
        "features": [
            "WhatsApp Commerce Bot",
            "Session Management",
            "Order Tracking",
            "Razorpay Integration",
            "Referral System",
            "Analytics Logging",
            "Abandoned Cart Recovery",
            "Birthday/Anniversary Wishes"
        ]
    }), 200

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    """WhatsApp webhook endpoint"""
    
    # ── GET: Webhook Verification ──
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            print("✅ Webhook verified")
            return challenge, 200
        
        print("❌ Webhook verification failed")
        return 'Forbidden', 403
    
    # ── POST: Incoming Message ──
    data = request.get_json()
    print("=" * 60)
    print(f"[{datetime.now()}] Webhook received")
    
    try:
        entry = data.get('entry', [])
        if not entry:
            return jsonify({"status": "ok"}), 200
        
        changes = entry[0].get('changes', [])
        if not changes:
            return jsonify({"status": "ok"}), 200
        
        value = changes[0].get('value', {})
        
        # Check for messages
        if 'messages' in value:
            messages = value['messages']
            for message in messages:
                phone_number = message.get('from')
                message_type = message.get('type')
                
                print(f"📱 From: {phone_number} | Type: {message_type}")
                
                # Handle TEXT messages
                if message_type == 'text':
                    message_text = message.get('text', {}).get('body', '')
                    handle_text_message(phone_number, message_text)
                
                # Handle BUTTON responses
                elif message_type == 'interactive':
                    interactive = message.get('interactive', {})
                    
                    # Button reply
                    if 'button_reply' in interactive:
                        button_id = interactive['button_reply'].get('id', '')
                        handle_button_response(phone_number, button_id)
                    
                    # List reply
                    elif 'list_reply' in interactive:
                        list_id = interactive['list_reply'].get('id', '')
                        handle_button_response(phone_number, list_id)
                
                # Handle ORDER (WhatsApp Catalog)
                elif message_type == 'order':
                    order_data = message.get('order', {})
                    handle_whatsapp_cart_order(phone_number, {'order': order_data})
        
        # Check for statuses (message delivery, read receipts)
        elif 'statuses' in value:
            statuses = value['statuses']
            for status in statuses:
                status_type = status.get('status')
                print(f"📊 Status: {status_type}")
    
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        import traceback
        traceback.print_exc()
    
    print("=" * 60)
    return jsonify({"status": "ok"}), 200

# ═══════════════════════════════════════════════════════════
# PAYMENT CALLBACK ROUTE
# ═══════════════════════════════════════════════════════════

@app.route('/payment/callback', methods=['GET', 'POST'])
def payment_callback():
    """Razorpay payment callback"""
    try:
        if request.method == 'GET':
            # URL callback with query params
            payment_id = request.args.get('razorpay_payment_id')
            payment_link_id = request.args.get('razorpay_payment_link_id')
            status = request.args.get('razorpay_payment_link_status')
            
            print(f"💳 Payment callback: {payment_id} | Status: {status}")
            
            # You can redirect to a thank you page or return success message
            return jsonify({
                "status": "success",
                "message": "Payment processed"
            }), 200
        
        elif request.method == 'POST':
            # Webhook callback
            data = request.get_json()
            handle_payment_callback(data)
            return jsonify({"status": "ok"}), 200
    
    except Exception as e:
        print(f"Payment callback error: {e}")
        return jsonify({"status": "error"}), 500

# ═══════════════════════════════════════════════════════════
# ADMIN ROUTES
# ═══════════════════════════════════════════════════════════

@app.route('/admin/broadcast', methods=['POST'])
def admin_broadcast():
    """Admin endpoint for broadcast messages"""
    try:
        data = request.get_json()
        phone_list = data.get('phone_list', [])
        message = data.get('message', '')
        button_text = data.get('button_text')
        button_url = data.get('button_url')
        
        if not phone_list or not message:
            return jsonify({
                "success": False,
                "message": "phone_list and message are required"
            }), 400
        
        success_count = send_broadcast_message(phone_list, message, button_text, button_url)
        
        return jsonify({
            "success": True,
            "message": f"Broadcast sent to {success_count}/{len(phone_list)} customers"
        }), 200
    
    except Exception as e:
        print(f"Broadcast error: {e}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/admin/send-birthday-wishes', methods=['POST'])
def admin_send_birthday_wishes():
    """Admin endpoint to trigger birthday wishes"""
    try:
        data = request.get_json()
        customers = data.get('customers', [])
        
        for customer in customers:
            phone = customer.get('phone')
            name = customer.get('name')
            if phone and name:
                send_birthday_wish(phone, name)
        
        return jsonify({
            "success": True,
            "message": f"Birthday wishes sent to {len(customers)} customers"
        }), 200
    
    except Exception as e:
        print(f"Birthday wishes error: {e}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/admin/send-anniversary-wishes', methods=['POST'])
def admin_send_anniversary_wishes():
    """Admin endpoint to trigger anniversary wishes"""
    try:
        data = request.get_json()
        customers = data.get('customers', [])
        
        for customer in customers:
            phone = customer.get('phone')
            name = customer.get('name')
            if phone and name:
                send_anniversary_wish(phone, name)
        
        return jsonify({
            "success": True,
            "message": f"Anniversary wishes sent to {len(customers)} customers"
        }), 200
    
    except Exception as e:
        print(f"Anniversary wishes error: {e}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/admin/send-abandoned-cart', methods=['POST'])
def admin_send_abandoned_cart():
    """Admin endpoint to trigger abandoned cart reminders"""
    try:
        data = request.get_json()
        customers = data.get('customers', [])
        
        for customer in customers:
            phone = customer.get('phone')
            cart_data = customer.get('cart_data', {})
            if phone:
                send_abandoned_cart_reminder(phone, cart_data)
        
        return jsonify({
            "success": True,
            "message": f"Abandoned cart reminders sent to {len(customers)} customers"
        }), 200
    
    except Exception as e:
        print(f"Abandoned cart error: {e}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/admin/sessions', methods=['GET'])
def admin_get_sessions():
    """Admin endpoint to view active sessions"""
    try:
        sessions_data = []
        for phone, session in user_sessions.items():
            sessions_data.append({
                'phone': phone,
                'state': session.get('state'),
                'last_activity': session.get('last_activity').isoformat() if session.get('last_activity') else None,
                'created_at': session.get('created_at').isoformat() if session.get('created_at') else None
            })
        
        return jsonify({
            "success": True,
            "count": len(sessions_data),
            "sessions": sessions_data
        }), 200
    
    except Exception as e:
        print(f"Sessions error: {e}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/admin/clear-session/<phone>', methods=['DELETE'])
def admin_clear_session(phone):
    """Admin endpoint to clear a specific session"""
    try:
        clear_session(phone)
        return jsonify({
            "success": True,
            "message": f"Session cleared for {phone}"
        }), 200
    
    except Exception as e:
        print(f"Clear session error: {e}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

# ═══════════════════════════════════════════════════════════
# ERROR HANDLERS
# ═══════════════════════════════════════════════════════════

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "success": False,
        "message": "Endpoint not found"
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "success": False,
        "message": "Internal server error"
    }), 500

# ═══════════════════════════════════════════════════════════
# RUN APPLICATION
# ═══════════════════════════════════════════════════════════

if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    
    print("=" * 60)
    print("🚀 AJewelBot v3 - Professional WhatsApp Commerce Bot")
    print("=" * 60)
    print(f"✅ Server starting on port {port}")
    print(f"✅ WhatsApp Phone ID: {WHATSAPP_PHONE_ID}")
    print(f"✅ Shopify Store: {SHOPIFY_STORE}")
    print(f"✅ Backend API: {BACKEND_API_URL}")
    print(f"✅ Logo URL: {LOGO_IMAGE_URL}")
    print(f"✅ Session timeout: {SESSION_TIMEOUT} seconds")
    print(f"✅ Keep-alive: Active (12-min ping)")
    print("=" * 60)
    print("📊 Available Endpoints:")
    print("   GET  /")
    print("   GET  /webhook (verification)")
    print("   POST /webhook (messages)")
    print("   GET  /payment/callback")
    print("   POST /payment/callback")
    print("   POST /admin/broadcast")
    print("   POST /admin/send-birthday-wishes")
    print("   POST /admin/send-anniversary-wishes")
    print("   POST /admin/send-abandoned-cart")
    print("   GET  /admin/sessions")
    print("   DELETE /admin/clear-session/<phone>")
    print("=" * 60)
    print("🎯 Flow Architecture:")
    print("   ✅ New Customer → Signup")
    print("   ✅ B2B Customer → Catalog → Payment")
    print("   ✅ Retail Customer → Custom/Browse")
    print("   ✅ Order Tracking")
    print("   ✅ Referral System")
    print("   ✅ Abandoned Cart Recovery")
    print("   ✅ Birthday/Anniversary Wishes")
    print("=" * 60)
    print("🔥 Bot is LIVE and ready to receive messages!")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=port, debug=False)
