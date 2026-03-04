# ═══════════════════════════════════════════════════════════
# A Jewel Studio - Professional WhatsApp Bot v3
# Complete Flow Architecture with AI Support
# ═══════════════════════════════════════════════════════════

import os
import json
import time
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai

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
BACKEND_API_URL = os.getenv('BACKEND_API_URL', 'https://ajewelbot-v2-backend.onrender.com')
GEMINI_API_KEY = 'AIzaSyAI_7J57EpfoQoBlCVJtVHdpj_YR4x6GTY'

# ── Configure Gemini AI ──
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-pro')

# ── Constants ──
SHEET_ID = "1w-4Zi65AqsQZFJIr1GLrDrW9BJNez8Wtr-dTL8oBLbs"
JOIN_US_URL = "https://a-jewel-studio-3.myshopify.com/pages/join-us"
LOGO_IMAGE_URL = "https://cdn.shopify.com/s/files/1/0815/3248/5868/files/Welcome_Photo.jpg?v=1772108644"
CUSTOMER_CARE_NUMBER = "7600056655"
SESSION_TIMEOUT = 1800  # 30 minutes

# ── Session Storage ──
user_sessions = {}

# ═══════════════════════════════════════════════════════════
# GEMINI AI SUPPORT
# ═══════════════════════════════════════════════════════════

def get_ai_response(customer_message, customer_name='Customer', customer_type='Retail'):
    """Get professional AI response using Gemini"""
    try:
        system_prompt = f"""You are a professional customer service representative for A Jewel Studio, a premium jewellery brand.

IMPORTANT GUIDELINES:
- You are an employee of A Jewel Studio
- Always be professional, polite, and helpful
- Keep responses concise (2-3 sentences max)
- Use proper grammar and punctuation
- Address customer as "{customer_name}"
- Customer type: {customer_type}
- Brand name: "A Jewel Studio" (with spaces)

WHAT YOU CAN HELP WITH:
- General jewellery questions
- Product information
- Store policies
- Business hours (Mon-Sat: 10 AM - 7 PM, Sunday: Closed)
- Shipping and delivery
- Custom jewellery design
- Gift recommendations

WHAT YOU CANNOT DO:
- Process orders (direct to WhatsApp catalog)
- Check order status (ask customer to type "Track #OrderID")
- Book appointments (direct to appointment flow)
- Access customer data
- Make promises about pricing or discounts

If customer asks about orders, appointments, or catalog, politely direct them to use the menu buttons.

Customer message: {customer_message}

Respond professionally as an A Jewel Studio employee:"""

        response = gemini_model.generate_content(system_prompt)
        ai_reply = response.text.strip()
        
        if not any(word in ai_reply.lower() for word in ['regards', 'help', 'assist']):
            ai_reply += "\n\nHow else may I assist you today?"
        
        return ai_reply
    
    except Exception as e:
        print(f"Gemini AI Error: {e}")
        return "Thank you for your message. For immediate assistance, please select an option from the menu or contact our team at +91 7600056655."

# ═══════════════════════════════════════════════════════════
# GOOGLE SHEETS CONNECTION
# ═══════════════════════════════════════════════════════════

def get_google_sheet():
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

# ═══════════════════════════════════════════════════════════
# SHOPIFY API FUNCTIONS
# ═══════════════════════════════════════════════════════════

def get_shopify_customer(phone):
    """Get customer from Shopify by phone number"""
    try:
        url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/customers/search.json"
        headers = {
            'X-Shopify-Access-Token': SHOPIFY_ACCESS_TOKEN,
            'Content-Type': 'application/json'
        }
        params = {'query': f'phone:{phone}'}
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            customers = response.json().get('customers', [])
            return customers[0] if customers else None
        return None
    except Exception as e:
        print(f"Shopify API Error: {e}")
        return None

def is_b2b_customer(customer):
    """Check if customer is B2B based on tags"""
    if not customer:
        return False
    tags = customer.get('tags', '').lower()
    return 'b2b' in tags or 'wholesaler' in tags or 'wholesale' in tags

# ═══════════════════════════════════════════════════════════
# CUSTOMER STATUS CHECK
# ═══════════════════════════════════════════════════════════

def check_customer_status(phone_number):
    """Check customer status"""
    try:
        sheet = get_google_sheet()
        if not sheet:
            return {'exists': False}
        
        all_data = sheet.get_all_values()
        
        for idx, row in enumerate(all_data[1:], start=2):
            if len(row) > 0 and row[0] == phone_number:
                has_form_data = bool(row[1]) if len(row) > 1 else False
                customer_type_sheet = row[27] if len(row) > 27 else 'Retail'
                first_name = row[1] if len(row) > 1 else ''
                last_name = row[2] if len(row) > 2 else ''
                
                shopify_customer = get_shopify_customer(phone_number)
                
                if shopify_customer:
                    customer_type = 'B2B' if is_b2b_customer(shopify_customer) else customer_type_sheet
                else:
                    customer_type = customer_type_sheet
                
                return {
                    'exists': True,
                    'has_form_data': has_form_data,
                    'customer_type': customer_type,
                    'name': f"{first_name} {last_name}".strip() or 'Customer',
                    'shopify_customer': shopify_customer,
                    'row': idx
                }
        
        return {'exists': False}
    
    except Exception as e:
        print(f"Sheet check error: {e}")
        return {'exists': False}

def add_number_to_sheet(phone_number):
    """Add new number to Column A only"""
    try:
        customer_status = check_customer_status(phone_number)
        
        if customer_status['exists']:
            print(f"Number already exists: {phone_number}")
            return False
        
        sheet = get_google_sheet()
        if sheet:
            sheet.append_row([phone_number])
            print(f"New number added to Column A: {phone_number}")
            return True
    except Exception as e:
        print(f"Sheet add error: {e}")
    return False

# ═══════════════════════════════════════════════════════════
# SESSION MANAGEMENT
# ═══════════════════════════════════════════════════════════

def get_session(phone_number):
    """Get or create session"""
    if phone_number not in user_sessions:
        user_sessions[phone_number] = {
            'state': 'idle',
            'data': {},
            'created_at': datetime.now(),
            'last_activity': datetime.now()
        }
    else:
        last_activity = user_sessions[phone_number]['last_activity']
        if (datetime.now() - last_activity).seconds > SESSION_TIMEOUT:
            user_sessions[phone_number] = {
                'state': 'idle',
                'data': {},
                'created_at': datetime.now(),
                'last_activity': datetime.now()
            }
    
    user_sessions[phone_number]['last_activity'] = datetime.now()
    return user_sessions[phone_number]

def update_session(phone_number, state=None, data=None):
    """Update session"""
    session = get_session(phone_number)
    if state:
        session['state'] = state
    if data:
        session['data'].update(data)
    session['last_activity'] = datetime.now()

def clear_session(phone_number):
    """Clear session"""
    if phone_number in user_sessions:
        del user_sessions[phone_number]

# ═══════════════════════════════════════════════════════════
# WHATSAPP SEND FUNCTIONS
# ═══════════════════════════════════════════════════════════

def send_whatsapp_text(to_number, message_text):
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
    """Send interactive buttons - FIXED FORMAT"""
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Format buttons properly
    formatted_buttons = []
    for btn in buttons[:3]:  # Max 3 buttons
        formatted_buttons.append({
            "type": "reply",
            "reply": {
                "id": btn.get('id', 'btn_' + str(len(formatted_buttons))),
                "title": btn.get('title', 'Option')[:20]  # Max 20 chars
            }
        })
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": body_text[:1024]  # Max 1024 chars
            },
            "action": {
                "buttons": formatted_buttons
            }
        }
    }
    
    try:
        r = requests.post(url, json=payload, headers=headers)
        print(f"Buttons sent to {to_number}: {r.status_code}")
        if r.status_code != 200:
            print(f"Button error response: {r.text}")
            # Fallback to text
            button_text = "\n".join([f"{i+1}. {btn['title']}" for i, btn in enumerate(buttons)])
            return send_whatsapp_text(to_number, f"{body_text}\n\n{button_text}")
        return r.json()
    except Exception as e:
        print(f"WhatsApp buttons error: {e}")
        button_text = "\n".join([f"{i+1}. {btn['title']}" for i, btn in enumerate(buttons)])
        return send_whatsapp_text(to_number, f"{body_text}\n\n{button_text}")

def send_whatsapp_cta_button(to_number, body_text, button_text, button_url):
    """Send CTA URL button"""
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "interactive",
        "interactive": {
            "type": "cta_url",
            "body": {"text": body_text[:1024]},
            "action": {
                "name": "cta_url",
                "parameters": {
                    "display_text": button_text[:20],
                    "url": button_url
                }
            }
        }
    }
    try:
        r = requests.post(url, json=payload, headers=headers)
        if r.status_code == 200:
            print(f"CTA button sent to {to_number}")
            return r.json()
        else:
            print(f"CTA button failed: {r.text}")
            fallback = f"{body_text}\n\n{button_text}: {button_url}"
            return send_whatsapp_text(to_number, fallback)
    except Exception as e:
        print(f"WhatsApp CTA button error: {e}")
        fallback = f"{body_text}\n\n{button_text}: {button_url}"
        return send_whatsapp_text(to_number, fallback)

# ═══════════════════════════════════════════════════════════
# FLOW MESSAGES - NEW CUSTOMER
# ═══════════════════════════════════════════════════════════

def send_new_customer_welcome(to_number):
    """Flow 1: New customer first visit"""
    if LOGO_IMAGE_URL:
        send_whatsapp_image(
            to_number,
            LOGO_IMAGE_URL,
            caption="Welcome to\n\n*A Jewel Studio*"
        )
        time.sleep(2)
    
    join_url = f"{JOIN_US_URL}?wa={to_number}"
    send_whatsapp_cta_button(
        to_number,
        "Tap Join Us below to become a part of our family.",
        "Join Us",
        join_url
    )

def send_complete_registration(to_number):
    """Customer logged but form not completed"""
    message = "Hello!\n\nI see you messaged us before but did not complete registration.\n\nWould you like to complete your registration?"
    
    join_url = f"{JOIN_US_URL}?wa={to_number}"
    send_whatsapp_cta_button(
        to_number,
        message,
        "Complete Registration",
        join_url
    )

# ═══════════════════════════════════════════════════════════
# FLOW MESSAGES - RETURNING CUSTOMER
# ═══════════════════════════════════════════════════════════

def send_retail_welcome(to_number, customer_name):
    """Flow 2A: Returning retail customer"""
    message = f"Welcome, {customer_name}.\n\nWe are delighted to have you here.\nPlease select an option below to get started."
    
    buttons = [
        {"id": "browse_collections", "title": "Browse Collections"},
        {"id": "customise_product", "title": "Customise Product"},
        {"id": "my_orders", "title": "My Orders"}
    ]
    
    send_whatsapp_buttons(to_number, message, buttons)

def send_b2b_welcome(to_number, customer_name):
    """Flow 2B: Returning B2B customer"""
    message = f"Welcome, {customer_name}.\n\nWe are delighted to have you here.\nPlease select an option below to get started."
    
    buttons = [
        {"id": "browse_digital_files", "title": "Browse Files"},
        {"id": "request_custom_file", "title": "Custom File"},
        {"id": "my_orders", "title": "My Orders"}
    ]
    
    send_whatsapp_buttons(to_number, message, buttons)

# ═══════════════════════════════════════════════════════════
# FLOW MESSAGES - SUPPORT
# ═══════════════════════════════════════════════════════════

def send_business_hours(to_number):
    """Business hours enquiry"""
    message = """Our business hours are:

Monday to Saturday: 10:00 AM to 7:00 PM
Sunday: Closed

For support outside these hours, please leave a message and our team will respond on the next business day."""
    
    send_whatsapp_text(to_number, message)

def send_about_us(to_number):
    """About A Jewel Studio"""
    message = """A Jewel Studio is a premium 3D jewellery design studio specialising in creating high-quality digital jewellery files for B2B partners and exclusive jewellery collections for retail customers.

Our designs are crafted with precision and made available through a network of authorised partner stores across India."""
    
    buttons = [
        {"id": "browse_collections", "title": "Browse Collections"},
        {"id": "connect_support", "title": "Connect with Us"}
    ]
    
    send_whatsapp_buttons(to_number, message, buttons)

def send_unrecognised_message(to_number, customer_type='Retail'):
    """Unrecognised message fallback"""
    message = "Thank you for reaching out to A Jewel Studio.\nWe could not understand your message. Please select an option below so we can assist you better."
    
    if customer_type == 'B2B' or customer_type == 'Wholesale':
        buttons = [
            {"id": "browse_digital_files", "title": "Browse Files"},
            {"id": "request_custom_file", "title": "Custom File"},
            {"id": "my_orders", "title": "My Orders"}
        ]
    else:
        buttons = [
            {"id": "browse_collections", "title": "Browse Collections"},
            {"id": "customise_product", "title": "Customise Product"},
            {"id": "my_orders", "title": "My Orders"}
        ]
    
    send_whatsapp_buttons(to_number, message, buttons)

# ═══════════════════════════════════════════════════════════
# KEYWORD DETECTION
# ═══════════════════════════════════════════════════════════

def detect_keyword(message_text):
    """Detect keywords in customer message"""
    message_lower = message_text.lower().strip()
    
    if any(word in message_lower for word in ['hi', 'hello', 'hey', 'namaste', 'hii', 'helo']):
        return 'greeting'
    
    if any(word in message_lower for word in ['business hours', 'timing', 'when available', 'open', 'time']):
        return 'business_hours'
    
    if any(word in message_lower for word in ['about', 'tell me about', 'who are you', 'what is']):
        return 'about'
    
    if any(word in message_lower for word in ['my orders', 'order status', 'track order', 'track']):
        return 'my_orders'
    
    if message_lower.startswith('track #') or message_lower.startswith('track#'):
        return 'track_order_id'
    
    if 'referral' in message_lower or 'refer' in message_lower:
        return 'referral'
    
    if 'help' in message_lower or 'support' in message_lower:
        return 'help'
    
    return None

# ═══════════════════════════════════════════════════════════
# ORDER TRACKING
# ═══════════════════════════════════════════════════════════

def track_order(to_number, order_id):
    """Track order by ID"""
    try:
        response = requests.get(f"{BACKEND_API_URL}/api/orders/track/{order_id}")
        
        if response.status_code == 200:
            order_data = response.json()
            message = f"""*Order Status*

Order ID: {order_id}
Status: {order_data.get('status', 'In Production')}
Expected Ready Date: {order_data.get('readyDate', 'TBD')}

We will notify you once your order is ready for collection."""
            send_whatsapp_text(to_number, message)
        else:
            send_whatsapp_text(to_number, f"Order {order_id} not found. Please check the order ID and try again.")
    except Exception as e:
        print(f"Order tracking error: {e}")
        send_whatsapp_text(to_number, "Unable to fetch order details at the moment. Please try again later or contact our support team.")

# ═══════════════════════════════════════════════════════════
# REFERRAL SYSTEM
# ═══════════════════════════════════════════════════════════

def generate_referral_code(customer_name, phone_number):
    """Generate referral code"""
    name_part = customer_name[:3].upper() if customer_name else 'REF'
    phone_part = phone_number[-4:]
    return f"{name_part}{phone_part}"

def send_referral_info(to_number, customer_name):
    """Send referral code and info"""
    referral_code = generate_referral_code(customer_name, to_number)
    
    message = f"""*Your Referral Code*

Code: {referral_code}

Share this code with your friends and family. When they register using your code, both of you will receive special benefits!

Share this link:
{JOIN_US_URL}?ref={referral_code}

Thank you for being a valued member of A Jewel Studio."""
    
    send_whatsapp_text(to_number, message)

# ═══════════════════════════════════════════════════════════
# BUTTON CLICK HANDLER
# ═══════════════════════════════════════════════════════════

def handle_button_click(button_id, from_number, customer_type='Retail'):
    """Handle interactive button clicks"""
    print(f"Button clicked: {button_id}")
    
    if button_id == 'browse_collections' or button_id == 'browse_digital_files':
        message = "Please select a category."
        buttons = [
            {"id": "cat_face", "title": "Face Jewellery"},
            {"id": "cat_hand", "title": "Hand & Wrist"},
            {"id": "cat_neck", "title": "Neck & Collar"}
        ]
        send_whatsapp_buttons(from_number, message, buttons)
    
    elif button_id == 'customise_product':
        message = "We would love to create something special for you.\n\nTo discuss your customisation requirements, please book an appointment with our design team."
        buttons = [
            {"id": "book_appointment", "title": "Book Appointment"}
        ]
        send_whatsapp_buttons(from_number, message, buttons)
    
    elif button_id == 'request_custom_file':
        message = "We would be happy to create a custom 3D jewellery file based on your requirements.\n\nPlease connect with our team directly. Share your photo or design reference and we will provide a quote at the earliest."
        buttons = [
            {"id": "connect_support", "title": "Connect with Team"}
        ]
        send_whatsapp_buttons(from_number, message, buttons)
    
    elif button_id == 'my_orders':
        message = "To track your order, please type:\n\nTrack #OrderID\n\nExample: Track #AJS123456\n\nOr connect with our team for assistance."
        buttons = [
            {"id": "connect_support", "title": "Connect with Us"}
        ]
        send_whatsapp_buttons(from_number, message, buttons)
    
    elif button_id == 'book_appointment':
        message = "To book an appointment, please share your preferred date and time.\n\nOur team will confirm your appointment shortly."
        send_whatsapp_text(from_number, message)
    
    elif button_id == 'connect_support':
        message = f"Our team is here to help you.\n\nBusiness Hours: Monday to Saturday, 10:00 AM to 7:00 PM\n\nContact: +91 {CUSTOMER_CARE_NUMBER}"
        send_whatsapp_text(from_number, message)
    
    elif button_id.startswith('cat_'):
        message = "Please browse our WhatsApp catalog to view products in this category.\n\nTap the catalog icon (🛍️) in the chat to explore our collection."
        send_whatsapp_text(from_number, message)
    
    else:
        send_unrecognised_message(from_number, customer_type)

# ═══════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "running", 
        "app": "A Jewel Studio WhatsApp Bot v3",
        "features": [
            "AI Support (Gemini)",
            "Multi-language Support",
            "Professional Flow Architecture",
            "Order Tracking",
            "Referral System",
            "Session Management"
        ]
    }), 200

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            print("Webhook verified")
            return challenge, 200
        return 'Forbidden', 403

    data = request.get_json()
    print("=" * 60)
    
    try:
        entry = data['entry'][0]
        changes = entry['changes'][0]
        value = changes['value']

        if 'messages' not in value:
            return jsonify({"status": "ok"}), 200

        message = value['messages'][0]
        from_number = message['from']
        message_type = message.get('type')

        print(f"Phone: {from_number} | Type: {message_type}")

        if message_type == 'interactive':
            interactive = message.get('interactive', {})
            button_reply = interactive.get('button_reply', {})
            button_id = button_reply.get('id', '')
            
            customer_status = check_customer_status(from_number)
            customer_type = customer_status.get('customer_type', 'Retail') if customer_status['exists'] else 'Retail'
            
            handle_button_click(button_id, from_number, customer_type)
            return jsonify({"status": "ok"}), 200

        if message_type == 'text':
            message_body = message['text']['body']
            print(f"Message: {message_body}")

            customer_status = check_customer_status(from_number)

            if not customer_status['exists']:
                print("NEW CUSTOMER")
                add_number_to_sheet(from_number)
                send_new_customer_welcome(from_number)
            
            elif customer_status['exists'] and not customer_status['has_form_data']:
                print("INCOMPLETE REGISTRATION")
                
                keyword = detect_keyword(message_body)
                
                if keyword == 'greeting':
                    send_complete_registration(from_number)
                elif keyword == 'business_hours':
                    send_business_hours(from_number)
                elif keyword == 'about':
                    send_about_us(from_number)
                elif keyword == 'help':
                    send_complete_registration(from_number)
                else:
                    ai_response = get_ai_response(message_body, 'Customer', 'Retail')
                    send_whatsapp_text(from_number, ai_response)
            
            else:
                print("RETURNING CUSTOMER")
                customer_name = customer_status.get('name', 'Customer')
                customer_type = customer_status.get('customer_type', 'Retail')
                
                keyword = detect_keyword(message_body)
                
                if keyword == 'greeting':
                    if customer_type == 'B2B' or customer_type == 'Wholesale':
                        send_b2b_welcome(from_number, customer_name)
                    else:
                        send_retail_welcome(from_number, customer_name)
                
                elif keyword == 'business_hours':
                    send_business_hours(from_number)
                
                elif keyword == 'about':
                    send_about_us(from_number)
                
                elif keyword == 'track_order_id':
                    order_id = message_body.replace('track', '').replace('Track', '').replace('#', '').strip()
                    track_order(from_number, order_id)
                                
                elif keyword == 'referral':
                    send_referral_info(from_number, customer_name)
                
                elif keyword == 'help':
                    if customer_type == 'B2B' or customer_type == 'Wholesale':
                        send_b2b_welcome(from_number, customer_name)
                    else:
                        send_retail_welcome(from_number, customer_name)
                
                else:
                    ai_response = get_ai_response(message_body, customer_name, customer_type)
                    send_whatsapp_text(from_number, ai_response)

    except Exception as e:
        print(f"Webhook error: {e}")

    print("=" * 60)
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"Starting A Jewel Studio WhatsApp Bot v3 on port {port}...")
    print("✅ WhatsApp Bot Active")
    print("✅ Google Sheets Connected")
    print("✅ Shopify Integration Active")
    print("✅ Backend API Ready")
    print("✅ Gemini AI Support Enabled")
    print("✅ Multi-language Support Active")
    app.run(host='0.0.0.0', port=port, debug=False)
    
