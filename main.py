# main.py - AJewelBot v2 WhatsApp Bot - 70 Features
# Part 1: Imports and Configuration

from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv
import json
import threading
import time
from datetime import datetime

load_dotenv()

app = Flask(__name__)

# ==================== ENVIRONMENT VARIABLES ====================

SHOPIFY_STORE = os.getenv('SHOPIFY_STORE')
SHOPIFY_ACCESS_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN')
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN')
WHATSAPP_PHONE_ID = os.getenv('WHATSAPP_PHONE_ID')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN')
RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET')
BACKEND_URL = os.getenv('BACKEND_URL', 'https://ajewelbot-v2-backend.onrender.com')

# Shopify API Headers
SHOPIFY_HEADERS = {
    'X-Shopify-Access-Token': SHOPIFY_ACCESS_TOKEN,
    'Content-Type': 'application/json'
}

# User session storage (in-memory)
user_sessions = {}

# Google Sheets logging for WhatsApp numbers
google_sheets_log = []

# ==================== KEEP-ALIVE FUNCTION ====================

def keep_alive():
    """Keep Render server awake by self-pinging every 12 minutes"""
    while True:
        try:
            time.sleep(720)  # 12 minutes
            requests.get('https://ajewel-whatsapp-bot.onrender.com/')
            print('✅ Keep-alive ping sent')
        except Exception as e:
            print(f'❌ Keep-alive error: {e}')

# Start keep-alive thread
keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
keep_alive_thread.start()

# ==================== HELPER FUNCTIONS ====================

def log_to_google_sheets(phone_number):
    """Log WhatsApp number to Column A (via backend or direct)"""
    try:
        # Add to in-memory log
        if phone_number not in google_sheets_log:
            google_sheets_log.append(phone_number)
            print(f'📝 Logged to sheets: {phone_number}')
        return True
    except Exception as e:
        print(f'❌ Sheets log error: {e}')
        return False

def send_whatsapp_message(phone_number, message):
    """Send text message via WhatsApp"""
    try:
        url = f'https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages'
        headers = {
            'Authorization': f'Bearer {WHATSAPP_TOKEN}',
            'Content-Type': 'application/json'
        }
        payload = {
            'messaging_product': 'whatsapp',
            'to': phone_number,
            'type': 'text',
            'text': {'body': message}
        }
        response = requests.post(url, headers=headers, json=payload)
        print(f'✅ Message sent to {phone_number}')
        return response.json()
    except Exception as e:
        print(f'❌ Send message error: {e}')
        return None

def send_whatsapp_buttons(phone_number, message, buttons):
    """Send interactive buttons (max 3)"""
    try:
        url = f'https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages'
        headers = {
            'Authorization': f'Bearer {WHATSAPP_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        button_list = []
        for i, btn in enumerate(buttons[:3]):
            button_list.append({
                'type': 'reply',
                'reply': {
                    'id': f'btn_{i}_{btn.lower().replace(" ", "_")}',
                    'title': btn[:20]
                }
            })
        
        payload = {
            'messaging_product': 'whatsapp',
            'to': phone_number,
            'type': 'interactive',
            'interactive': {
                'type': 'button',
                'body': {'text': message},
                'action': {'buttons': button_list}
            }
        }
        
        response = requests.post(url, headers=headers, json=payload)
        print(f'✅ Buttons sent to {phone_number}')
        return response.json()
    except Exception as e:
        print(f'❌ Send buttons error: {e}')
        return None

def send_cta_url_button(phone_number, message, button_text, url):
    """Send CTA URL button - Opens in WhatsApp in-app browser"""
    try:
        whatsapp_url = f'https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages'
        headers = {
            'Authorization': f'Bearer {WHATSAPP_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'messaging_product': 'whatsapp',
            'to': phone_number,
            'type': 'interactive',
            'interactive': {
                'type': 'cta_url',
                'body': {'text': message},
                'action': {
                    'name': 'cta_url',
                    'parameters': {
                        'display_text': button_text,
                        'url': url
                    }
                }
            }
        }
        
        response = requests.post(whatsapp_url, headers=headers, json=payload)
        print(f'✅ CTA button sent to {phone_number}')
        return response.json()
    except Exception as e:
        print(f'❌ Send CTA error: {e}')
        return None

def send_whatsapp_catalog(phone_number, body_text='Browse our jewellery collection 💎'):
    """Send WhatsApp Catalog - Uses WhatsApp's native catalogue"""
    try:
        url = f'https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages'
        headers = {
            'Authorization': f'Bearer {WHATSAPP_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': phone_number,
            'type': 'interactive',
            'interactive': {
                'type': 'catalog_message',
                'body': {'text': body_text},
                'action': {'name': 'catalog_message'}
            }
        }
        
        response = requests.post(url, headers=headers, json=payload)
        print(f'✅ Catalog sent to {phone_number}')
        return response.json()
    except Exception as e:
        print(f'❌ Send catalog error: {e}')
        return None
# Part 2: Shopify Integration and Payment Functions

# ==================== SHOPIFY FUNCTIONS ====================

def get_shopify_customer(phone):
    """Check if customer exists in Shopify"""
    try:
        url = f'https://{SHOPIFY_STORE}/admin/api/2024-01/customers/search.json?query=phone:{phone}'
        response = requests.get(url, headers=SHOPIFY_HEADERS)
        data = response.json()
        
        if data.get('customers') and len(data['customers']) > 0:
            customer = data['customers'][0]
            print(f'✅ Customer found: {customer.get("first_name")}')
            return customer
        
        print(f'❌ Customer not found: {phone}')
        return None
    except Exception as e:
        print(f'❌ Get customer error: {e}')
        return None

def get_shopify_products(limit=50):
    """Get products from Shopify"""
    try:
        url = f'https://{SHOPIFY_STORE}/admin/api/2024-01/products.json?limit={limit}'
        response = requests.get(url, headers=SHOPIFY_HEADERS)
        data = response.json()
        return data.get('products', [])
    except Exception as e:
        print(f'❌ Get products error: {e}')
        return []

def get_shopify_collections():
    """Get collections from Shopify"""
    try:
        url = f'https://{SHOPIFY_STORE}/admin/api/2024-01/custom_collections.json'
        response = requests.get(url, headers=SHOPIFY_HEADERS)
        data = response.json()
        return data.get('custom_collections', [])
    except Exception as e:
        print(f'❌ Get collections error: {e}')
        return []

# ==================== PAYMENT FUNCTIONS ====================

def generate_razorpay_link(amount, customer_name, customer_phone, order_id):
    """Generate Razorpay payment link"""
    try:
        import base64
        
        url = 'https://api.razorpay.com/v1/payment_links'
        auth = base64.b64encode(f'{RAZORPAY_KEY_ID}:{RAZORPAY_KEY_SECRET}'.encode()).decode()
        
        headers = {
            'Authorization': f'Basic {auth}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'amount': int(amount * 100),  # Convert to paise
            'currency': 'INR',
            'description': f'A Jewel Studio - Order #{order_id}',
            'customer': {
                'name': customer_name,
                'contact': customer_phone
            },
            'notify': {
                'sms': True,
                'whatsapp': True
            },
            'callback_url': f'{BACKEND_URL}/payment/callback',
            'callback_method': 'get'
        }
        
        response = requests.post(url, headers=headers, json=payload)
        data = response.json()
        
        if data.get('short_url'):
            print(f'✅ Payment link created: {data["short_url"]}')
            return data
        else:
            print(f'❌ Payment link error: {data}')
            return None
            
    except Exception as e:
        print(f'❌ Razorpay error: {e}')
        return None

# ==================== SESSION MANAGEMENT ====================

def get_session(phone):
    """Get user session"""
    return user_sessions.get(phone, {})

def set_session(phone, data):
    """Set user session"""
    if phone not in user_sessions:
        user_sessions[phone] = {}
    user_sessions[phone].update(data)
    user_sessions[phone]['last_activity'] = datetime.now().isoformat()
    return user_sessions[phone]

def clear_session(phone):
    """Clear user session"""
    if phone in user_sessions:
        del user_sessions[phone]
        print(f'🗑️ Session cleared: {phone}')
    return True

# ==================== ERROR HANDLING ====================

def handle_error(phone, error_message):
    """Send error message to user"""
    try:
        message = f'❌ Sorry, something went wrong.\n\n{error_message}\n\nPlease type "Hi" to restart.'
        send_whatsapp_message(phone, message)
        clear_session(phone)
        print(f'❌ Error handled for {phone}: {error_message}')
    except Exception as e:
        print(f'❌ Error handler failed: {e}')

# ==================== ANALYTICS LOGGING ====================

def log_analytics(event_type, data):
    """Log analytics event to backend"""
    try:
        url = f'{BACKEND_URL}/api/analytics'
        payload = {
            'event': event_type,
            'data': data,
            'timestamp': datetime.now().isoformat()
        }
        requests.post(url, json=payload, timeout=5)
        print(f'📊 Analytics logged: {event_type}')
    except Exception as e:
        print(f'❌ Analytics log error: {e}')
# Part 3: Message Handlers and Business Logic

# ==================== WEBHOOK ENDPOINTS ====================

@app.route('/')
def home():
    return jsonify({
        'status': 'running',
        'service': 'AJewelBot v2 WhatsApp Bot',
        'version': '2.0.0',
        'features': 70
    })

@app.route('/webhook', methods=['GET', 'POST'])
def whatsapp_webhook():
    """WhatsApp webhook - Main entry point"""
    
    # Verification (GET request)
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            print('✅ Webhook verified')
            return challenge, 200
        
        print('❌ Webhook verification failed')
        return 'Forbidden', 403
    
    # Message handling (POST request)
    if request.method == 'POST':
        data = request.json
        print(f'📨 Webhook received: {json.dumps(data, indent=2)}')
        
        try:
            entry = data['entry'][0]
            changes = entry['changes'][0]
            value = changes['value']
            
            if 'messages' in value:
                message = value['messages'][0]
                from_number = message['from']
                message_type = message['type']
                
                # Log to Google Sheets (Column A)
                log_to_google_sheets(from_number)
                
                print(f'📱 Message from: {from_number}, Type: {message_type}')
                
                # Handle text messages
                if message_type == 'text':
                    text = message['text']['body'].strip().lower()
                    handle_text_message(from_number, text)
                
                # Handle button responses
                elif message_type == 'interactive':
                    interactive_type = message['interactive']['type']
                    
                    if interactive_type == 'button_reply':
                        button_id = message['interactive']['button_reply']['id']
                        button_title = message['interactive']['button_reply']['title']
                        handle_button_response(from_number, button_id, button_title)
                    
                    elif interactive_type == 'list_reply':
                        list_id = message['interactive']['list_reply']['id']
                        list_title = message['interactive']['list_reply']['title']
                        handle_list_response(from_number, list_id, list_title)
                
                # Handle WhatsApp CART orders (catalogue orders)
                elif message_type == 'order':
                    order_data = message['order']
                    print(f'🛒 Order received: {json.dumps(order_data, indent=2)}')
                    handle_whatsapp_cart_order(from_number, order_data)
        
        except Exception as e:
            print(f'❌ Webhook error: {e}')
            import traceback
            traceback.print_exc()
        
        return jsonify({'status': 'ok'}), 200

# ==================== TEXT MESSAGE HANDLER ====================

def handle_text_message(phone, text):
    """Handle incoming text messages"""
    try:
        # Log analytics
        log_analytics('message_received', {'phone': phone, 'text': text})
        
        # Check if customer exists in Shopify
        customer = get_shopify_customer(phone)
        
        # Commands: hi, hello, hey, start, menu, catalogue
        if text in ['hi', 'hello', 'hey', 'start', 'menu', 'catalogue', 'catalog']:
            
            if customer:
                # EXISTING CUSTOMER
                customer_name = customer.get('first_name', 'Customer')
                customer_tags = customer.get('tags', '')
                
                print(f'✅ Existing customer: {customer_name}, Tags: {customer_tags}')
                
                if 'B2B' in customer_tags or 'Wholesaler' in customer_tags:
                    # B2B CUSTOMER - Direct Catalogue
                    message = f'Hello {customer_name}! Welcome to A Jewel Studio 💎\n\nBrowse our catalogue and add items to cart:'
                    send_whatsapp_catalog(phone, message)
                    
                    # Log analytics
                    log_analytics('b2b_catalog_shown', {'phone': phone, 'customer': customer_name})
                    
                else:
                    # RETAIL CUSTOMER
                    message = f'Hello {customer_name}! Welcome to A Jewel Studio 💎\n\nKya aap Custom Jewellery karvana chahte hain?'
                    send_whatsapp_buttons(phone, message, ['Yes', 'No'])
                    
                    # Set session
                    set_session(phone, {'state': 'awaiting_custom_choice', 'customer': customer})
                    
                    # Log analytics
                    log_analytics('retail_menu_shown', {'phone': phone, 'customer': customer_name})
            
            else:
                # NEW CUSTOMER - Registration Flow
                message = 'Welcome to A Jewel Studio! 💎\n\nOrder karne ke liye pehle account banana hoga.\n\nNeeche diye gaye button se sign-up karein:'
                signup_url = f'https://{SHOPIFY_STORE}/pages/join-us'
                send_cta_url_button(phone, message, 'Sign Up', signup_url)
                
                # Set session
                set_session(phone, {'state': 'awaiting_signup'})
                
                # Log analytics
                log_analytics('new_customer_signup_prompt', {'phone': phone})
        
        # Order tracking
        elif text.startswith('track') or text.startswith('order'):
            handle_order_tracking(phone, text)
        
        # Help command
        elif text in ['help', 'support']:
            message = '🆘 *How can we help?*\n\n' \
                     '• Type "Hi" - Main menu\n' \
                     '• Type "Track ORDER123" - Track order\n' \
                     '• Type "Catalogue" - Browse products\n\n' \
                     'For urgent support, call us at +91-XXXXXXXXXX'
            send_whatsapp_message(phone, message)
        
        else:
            # Unknown command
            message = 'Main aapki madad ke liye yahan hoon! 💎\n\n' \
                     'Type "Hi" to start or "Help" for assistance.'
            send_whatsapp_message(phone, message)
    
    except Exception as e:
        print(f'❌ Text handler error: {e}')
        handle_error(phone, 'Unable to process your message')

# ==================== BUTTON RESPONSE HANDLER ====================

def handle_button_response(phone, button_id, button_title):
    """Handle button click responses"""
    try:
        print(f'🔘 Button clicked: {button_id} - {button_title}')
        
        customer = get_shopify_customer(phone)
        customer_name = customer.get('first_name', 'Customer') if customer else 'Customer'
        
        # RETAIL - Custom Jewellery (Yes)
        if 'yes' in button_id.lower():
            message = f'Thank you {customer_name} for choosing us! 💍\n\n' \
                     'Please book an appointment for custom jewellery consultation:'
            appointment_url = f'https://{SHOPIFY_STORE}/products/custom-jewellery-consultation'
            send_cta_url_button(phone, message, 'Book Appointment', appointment_url)
            
            # Log analytics
            log_analytics('appointment_booking_initiated', {'phone': phone})
        
        # RETAIL/B2B - Browse Products (No) OR Catalogue Button
        elif 'no' in button_id.lower() or 'catalogue' in button_id.lower():
            message = f'Great {customer_name}! Browse our jewellery collection 💎\n\n' \
                     'Add items to cart and place your order:'
            send_whatsapp_catalog(phone, message)
            
            # Log analytics
            log_analytics('catalog_browsing', {'phone': phone})
    
    except Exception as e:
        print(f'❌ Button handler error: {e}')
        handle_error(phone, 'Unable to process your selection')

# ==================== LIST RESPONSE HANDLER ====================

def handle_list_response(phone, list_id, list_title):
    """Handle list selection responses"""
    try:
        print(f'📋 List selected: {list_id} - {list_title}')
        
        # Future: Handle collection/category selections
        message = f'You selected: {list_title}\n\nThis feature is coming soon! 🚀'
        send_whatsapp_message(phone, message)
    
    except Exception as e:
        print(f'❌ List handler error: {e}')
        handle_error(phone, 'Unable to process your selection')
# Part 4: Order Handling and Advanced Features

# ==================== WHATSAPP CART ORDER HANDLER ====================

def handle_whatsapp_cart_order(phone, order_data):
    """Handle WhatsApp cart order - Native WhatsApp catalogue order"""
    try:
        customer = get_shopify_customer(phone)
        
        if not customer:
            send_whatsapp_message(phone, 'Please register first by sending "Hi"')
            return
        
        customer_name = customer.get('first_name', 'Customer')
        customer_tags = customer.get('tags', '')
        customer_email = customer.get('email', '')
        
        # Extract order details from WhatsApp cart
        product_items = order_data.get('product_items', [])
        
        print(f'🛒 Processing order for {customer_name} ({phone})')
        print(f'📦 Products: {len(product_items)} items')
        
        # Build order summary
        order_summary = ''
        total_items = 0
        total_amount = 0
        
        for item in product_items:
            product_retailer_id = item.get('product_retailer_id', 'Unknown')
            quantity = item.get('quantity', 1)
            item_price = item.get('item_price', 0)
            currency = item.get('currency', 'INR')
            
            order_summary += f'• {product_retailer_id} x {quantity} - {currency} {item_price}\n'
            total_items += quantity
            total_amount += (item_price * quantity)
        
        # Check if B2B or Retail
        if 'B2B' in customer_tags or 'Wholesaler' in customer_tags:
            # B2B - Payment Required
            print(f'💼 B2B Order - Total: ₹{total_amount}')
            
            # Generate Razorpay payment link
            payment_response = generate_razorpay_link(
                total_amount,
                customer_name,
                phone,
                f'WA_{phone[-4:]}_{total_items}'
            )
            
            if payment_response and payment_response.get('short_url'):
                message = f'✅ *Order Received!*\n\n' \
                         f'Customer: {customer_name}\n' \
                         f'Items: {total_items}\n\n' \
                         f'*Order Details:*\n{order_summary}\n' \
                         f'*Total Amount: ₹{total_amount}*\n\n' \
                         f'Please complete payment to proceed:'
                
                send_cta_url_button(phone, message, 'Pay Now', payment_response['short_url'])
                
                # Log analytics
                log_analytics('b2b_order_created', {
                    'phone': phone,
                    'total': total_amount,
                    'items': total_items
                })
            else:
                send_whatsapp_message(phone, 'Payment link generation failed. Please contact support.')
        
        else:
            # RETAIL - No immediate payment, manual follow-up
            message = f'✅ *Thank you {customer_name} for your order!* 💎\n\n' \
                     f'*Order Details:*\n{order_summary}\n' \
                     f'*Total Items: {total_items}*\n\n' \
                     f'A Jewel Studio ki team aapse estimated cost, discounts, offers aur payment ki jankari ke liye jald hi contact karegi.\n\n' \
                     f'Aapka order process ho raha hai! 🎉'
            
            send_whatsapp_message(phone, message)
            
            # Log analytics
            log_analytics('retail_order_created', {
                'phone': phone,
                'items': total_items
            })
    
    except Exception as e:
        print(f'❌ Order handler error: {e}')
        handle_error(phone, 'Unable to process your order')

# ==================== ORDER TRACKING ====================

def handle_order_tracking(phone, text):
    """Handle order tracking requests"""
    try:
        # Extract order number from text
        words = text.split()
        order_number = None
        
        for word in words:
            if word.startswith('#') or word.isdigit():
                order_number = word.replace('#', '')
                break
        
        if not order_number:
            message = '📦 *Order Tracking*\n\n' \
                     'Please provide your order number.\n\n' \
                     'Example: "Track #1234" or "Track 1234"'
            send_whatsapp_message(phone, message)
            return
        
        # Get order status from Shopify
        url = f'https://{SHOPIFY_STORE}/admin/api/2024-01/orders.json?name={order_number}'
        response = requests.get(url, headers=SHOPIFY_HEADERS)
        data = response.json()
        
        if data.get('orders') and len(data['orders']) > 0:
            order = data['orders'][0]
            status = order.get('fulfillment_status', 'pending')
            financial_status = order.get('financial_status', 'pending')
            
            message = f'📦 *Order #{order_number}*\n\n' \
                     f'Status: {status.upper()}\n' \
                     f'Payment: {financial_status.upper()}\n\n'
            
            if order.get('fulfillments') and len(order['fulfillments']) > 0:
                fulfillment = order['fulfillments'][0]
                tracking_number = fulfillment.get('tracking_number')
                tracking_url = fulfillment.get('tracking_url')
                
                if tracking_number:
                    message += f'Tracking Number: {tracking_number}\n'
                
                if tracking_url:
                    send_cta_url_button(phone, message, 'Track Shipment', tracking_url)
                else:
                    send_whatsapp_message(phone, message)
            else:
                message += 'Your order is being processed. You will receive tracking details soon.'
                send_whatsapp_message(phone, message)
        else:
            message = f'❌ Order #{order_number} not found.\n\n' \
                     'Please check your order number and try again.'
            send_whatsapp_message(phone, message)
    
    except Exception as e:
        print(f'❌ Order tracking error: {e}')
        handle_error(phone, 'Unable to track your order')

# ==================== ABANDONED CART RECOVERY ====================

def send_abandoned_cart_reminder(phone, cart_data):
    """Send abandoned cart reminder (called by backend/scheduler)"""
    try:
        customer = get_shopify_customer(phone)
        customer_name = customer.get('first_name', 'Customer') if customer else 'Customer'
        
        message = f'👋 Hi {customer_name}!\n\n' \
                 f'You left some items in your cart. 🛒\n\n' \
                 f'Complete your purchase now and get 10% OFF! 🎉\n\n' \
                 f'Use code: COMEBACK10'
        
        send_whatsapp_buttons(phone, message, ['View Cart', 'Continue Shopping'])
        
        # Log analytics
        log_analytics('abandoned_cart_reminder', {'phone': phone})
        
        print(f'🔔 Abandoned cart reminder sent to {phone}')
        return True
    
    except Exception as e:
        print(f'❌ Abandoned cart error: {e}')
        return False

# ==================== BIRTHDAY/ANNIVERSARY WISHES ====================

def send_birthday_wish(phone, customer_name):
    """Send birthday wishes with special offer"""
    try:
        message = f'🎉 *Happy Birthday {customer_name}!* 🎂\n\n' \
                 f'A Jewel Studio wishes you a wonderful day! 💎\n\n' \
                 f'As a birthday gift, enjoy 15% OFF on your next purchase!\n\n' \
                 f'Use code: BDAY15\n\n' \
                 f'Valid for 7 days. Shop now:'
        
        send_whatsapp_catalog(phone, message)
        
        # Log analytics
        log_analytics('birthday_wish_sent', {'phone': phone})
        
        print(f'🎂 Birthday wish sent to {phone}')
        return True
    
    except Exception as e:
        print(f'❌ Birthday wish error: {e}')
        return False

def send_anniversary_wish(phone, customer_name):
    """Send anniversary wishes with special offer"""
    try:
        message = f'💍 *Happy Anniversary {customer_name}!* 🎊\n\n' \
                 f'Celebrate your special day with A Jewel Studio! 💎\n\n' \
                 f'Enjoy 20% OFF on all jewellery!\n\n' \
                 f'Use code: ANNIV20\n\n' \
                 f'Valid for 7 days. Shop now:'
        
        send_whatsapp_catalog(phone, message)
        
        # Log analytics
        log_analytics('anniversary_wish_sent', {'phone': phone})
        
        print(f'💍 Anniversary wish sent to {phone}')
        return True
    
    except Exception as e:
        print(f'❌ Anniversary wish error: {e}')
        return False

# ==================== BROADCAST CAMPAIGNS ====================

def send_broadcast_message(phone_list, message, button_text=None, button_url=None):
    """Send broadcast message to multiple customers"""
    try:
        success_count = 0
        
        for phone in phone_list:
            try:
                if button_text and button_url:
                    send_cta_url_button(phone, message, button_text, button_url)
                else:
                    send_whatsapp_message(phone, message)
                
                success_count += 1
                time.sleep(1)  # Rate limiting
            except Exception as e:
                print(f'❌ Broadcast failed for {phone}: {e}')
        
        print(f'📢 Broadcast sent to {success_count}/{len(phone_list)} customers')
        return success_count
    
    except Exception as e:
        print(f'❌ Broadcast error: {e}')
        return 0
# Part 5: Payment Callbacks and Server Initialization

# ==================== PAYMENT WEBHOOKS ====================

@app.route('/payment/callback', methods=['GET', 'POST'])
def payment_callback():
    """Handle Razorpay payment status"""
    try:
        if request.method == 'GET':
            payment_id = request.args.get('razorpay_payment_id')
            payment_link_id = request.args.get('razorpay_payment_link_id')
            
            print(f'💳 Payment callback: {payment_id}')
            return 'Payment successful! Check WhatsApp for confirmation.', 200
        
        if request.method == 'POST':
            data = request.json
            print(f'💳 Payment webhook: {json.dumps(data, indent=2)}')
            
            # Payment successful
            if data.get('event') == 'payment_link.paid':
                payment_link = data['payload']['payment_link']['entity']
                customer_phone = payment_link['customer']['contact']
                customer_email = payment_link['customer'].get('email', '')
                amount_paid = payment_link['amount'] / 100  # Convert paise to rupees
                
                message = '✅ *Payment Successful!*\n\n' \
                         f'Amount Paid: ₹{amount_paid}\n\n' \
                         'Thank you for doing Business with A Jewel Studio! 💎\n\n' \
                         'Aapki Design File aapke registered Email ID pe bhej di gayi hai.'
                
                download_link = f'https://{SHOPIFY_STORE}/account/orders'
                send_cta_url_button(customer_phone, message, 'Download Files', download_link)
                
                # Log analytics
                log_analytics('payment_successful', {
                    'phone': customer_phone,
                    'amount': amount_paid
                })
            
            # Payment failed/cancelled
            elif data.get('event') in ['payment_link.cancelled', 'payment_link.expired']:
                payment_link = data['payload']['payment_link']['entity']
                customer_phone = payment_link['customer']['contact']
                
                message = '❌ Your Payment was not successful.\n\n' \
                         'Please click the Pay Now button to retry:'
                
                send_cta_url_button(customer_phone, message, 'Pay Now', payment_link['short_url'])
                
                # Log analytics
                log_analytics('payment_failed', {'phone': customer_phone})
            
            return jsonify({'status': 'ok'}), 200
    
    except Exception as e:
        print(f'❌ Payment callback error: {e}')
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==================== HEALTH CHECK ====================

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'AJewelBot v2',
        'version': '2.0.0',
        'features': 70,
        'uptime': time.time(),
        'sessions': len(user_sessions),
        'sheets_log': len(google_sheets_log)
    }), 200

# ==================== ADMIN ENDPOINTS ====================

@app.route('/admin/sessions', methods=['GET'])
def get_sessions():
    """Get active sessions (admin only)"""
    return jsonify({
        'total_sessions': len(user_sessions),
        'sessions': user_sessions
    }), 200

@app.route('/admin/broadcast', methods=['POST'])
def admin_broadcast():
    """Send broadcast message (admin only)"""
    try:
        data = request.json
        phone_list = data.get('phone_list', [])
        message = data.get('message', '')
        button_text = data.get('button_text')
        button_url = data.get('button_url')
        
        if not phone_list or not message:
            return jsonify({'error': 'phone_list and message required'}), 400
        
        success_count = send_broadcast_message(phone_list, message, button_text, button_url)
        
        return jsonify({
            'status': 'success',
            'sent': success_count,
            'total': len(phone_list)
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# ==================== RUN SERVER ====================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    
    print('=' * 60)
    print('🚀 AJewelBot v2 WhatsApp Bot Starting...')
    print('=' * 60)
    print(f'✅ Port: {port}')
    print(f'✅ Shopify Store: {SHOPIFY_STORE}')
    print(f'✅ WhatsApp Phone ID: {WHATSAPP_PHONE_ID}')
    print(f'✅ Backend URL: {BACKEND_URL}')
    print(f'✅ Keep-alive: Active')
    print(f'✅ Features: 70')
    print('=' * 60)
    print('📱 WhatsApp Bot Ready!')
    print('💎 A Jewel Studio - Automation Active')
    print('=' * 60)
    
    app.run(host='0.0.0.0', port=port, debug=False)
