#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AJewel WhatsApp Bot – with WhatsApp Flow Signup
================================================
Features:
- WhatsApp Flow for new customer signup (slides up in chat)
- Phone-based customer lookup via Shopify Admin API
- Collection browsing with main/sub categories
- Order creation and Razorpay payment for B2B
- Message deduplication
"""

from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv
import json
import time
import re
import urllib.parse
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Environment variables
SHOPIFY_STORE        = os.getenv('SHOPIFY_STORE')
SHOPIFY_ACCESS_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN')
WHATSAPP_TOKEN       = os.getenv('ACCESS_TOKEN')
WHATSAPP_PHONE_ID    = os.getenv('PHONE_NUMBER_ID')
VERIFY_TOKEN         = os.getenv('VERIFY_TOKEN')
WHATSAPP_FLOW_ID     = os.getenv('WHATSAPP_FLOW_ID')  # Add this to .env
RAZORPAY_KEY_ID      = os.getenv('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET  = os.getenv('RAZORPAY_KEY_SECRET')
PORT                 = int(os.getenv('PORT', 10000))

# Shopify API headers
SHOPIFY_HEADERS = {
    'X-Shopify-Access-Token': SHOPIFY_ACCESS_TOKEN,
    'Content-Type': 'application/json'
}

# WhatsApp API headers
WHATSAPP_HEADERS = {
    "Authorization": f"Bearer {WHATSAPP_TOKEN}",
    "Content-Type": "application/json"
}

# Global storage
user_sessions = {}
processed_messages = {}
CACHE_DURATION = timedelta(minutes=5)

# Collections data
MAIN_COLLECTIONS = [
    {"id": "25628597613502595", "title": "Baby Jewellery"},
    {"id": "25749951748007044", "title": "Face Jewellery"},
    {"id": "25770023742652990", "title": "Neck Jewellery"},
    {"id": "26078491468433934", "title": "Hand Jewellery"},
    {"id": "26473022232283999", "title": "Lower Body Jewellery"},
    {"id": "26328388420090334", "title": "Murti & Figurines"},
]

SUB_COLLECTIONS = {
    "25628597613502595": [
        {"id": "25948367958163570", "title": "Anklets & Payal"},
        {"id": "26693163706953517", "title": "Bangles & Kada"},
        {"id": "26008758518787659", "title": "Earrings"},
        {"id": "34573479015569657", "title": "Hair Accessories"},
        {"id": "25864345456526176", "title": "Necklace & Chain"},
        {"id": "26302662429369350", "title": "Rings"},
    ],
    "25749951748007044": [
        {"id": "26090421433907722", "title": "Ear Jewellery"},
        {"id": "25629234596754210", "title": "Head Jewellery"},
        {"id": "25993617556990784", "title": "Lip & Eye Jewellery"},
        {"id": "26026555510330213", "title": "Nose Jewellery"},
    ],
    "25770023742652990": [
        {"id": "26277843851853890", "title": "Modern Necklace"},
        {"id": "25850209314636536", "title": "Pendant & Butti"},
        {"id": "26252397311060803", "title": "Special Sets"},
        {"id": "25892135267109218", "title": "Traditional Haar"},
    ],
    "26078491468433934": [
        {"id": "34397077723223821", "title": "Baju Band & Haath Panja"},
        {"id": "26079781681708309", "title": "Bangdi & Bangle"},
        {"id": "26349002784723474", "title": "Bracelet"},
        {"id": "26047371878255581", "title": "Kada"},
        {"id": "25891367957149672", "title": "Rings"},
    ],
    "26473022232283999": [
        {"id": "26118144874448091", "title": "Bichhiya & Toe Ring"},
        {"id": "25835297096142403", "title": "Kamarband & Waist"},
        {"id": "33976400778641336", "title": "Payal & Anklet"},
    ],
    "26328388420090334": [
        {"id": "33871729065808088", "title": "Animal Murti"},
        {"id": "26357708767188650", "title": "Hindu God Murti"},
        {"id": "34195647333383660", "title": "Mix Designs"},
    ],
}

# ============================================
# UTILITY FUNCTIONS
# ============================================

def normalize_phone(phone):
    """Normalize phone to E.164 format (+91xxxxxxxxxx)"""
    digits = re.sub(r'\D', '', phone)
    if not digits.startswith('91') and len(digits) == 10:
        digits = '91' + digits
    return '+' + digits

def is_duplicate_message(message_id):
    """Check if message was already processed"""
    now = datetime.now()
    if message_id in processed_messages:
        if now - processed_messages[message_id] < CACHE_DURATION:
            return True
    processed_messages[message_id] = now
    return False

# ============================================
# SHOPIFY CUSTOMER FUNCTIONS
# ============================================

def check_customer_exists(phone_number):
    """
    Check if customer exists in Shopify by phone
    Returns: {'is_new': bool, 'customer': dict or None}
    """
    normalized_phone = normalize_phone(phone_number)
    encoded_phone = urllib.parse.quote(normalized_phone)
    
    url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/customers/search.json?query=phone:{encoded_phone}"
    
    try:
        response = requests.get(url, headers=SHOPIFY_HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get('customers') and len(data['customers']) > 0:
            return {'is_new': False, 'customer': data['customers'][0]}
        else:
            return {'is_new': True, 'customer': None}
    except Exception as e:
        print(f"Error checking customer: {e}")
        return None

def create_shopify_customer(phone, full_name, email=None, customer_type="retail"):
    """Create new customer in Shopify"""
    name_parts = full_name.split(maxsplit=1)
    first_name = name_parts[0] if name_parts else ""
    last_name = name_parts[1] if len(name_parts) > 1 else ""
    
    customer_data = {
        "customer": {
            "phone": normalize_phone(phone),
            "first_name": first_name,
            "last_name": last_name,
            "verified_email": True,
            "tags": f"whatsapp-signup,{customer_type}",
            "note": f"Signed up via WhatsApp on {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        }
    }
    
    if email:
        customer_data["customer"]["email"] = email
    
    try:
        response = requests.post(
            f"https://{SHOPIFY_STORE}/admin/api/2024-01/customers.json",
            headers=SHOPIFY_HEADERS,
            json=customer_data,
            timeout=10
        )
        response.raise_for_status()
        return response.json().get('customer')
    except Exception as e:
        print(f"Error creating customer: {e}")
        return None

# ============================================
# WHATSAPP MESSAGING FUNCTIONS
# ============================================

def send_whatsapp_message(phone, message_data):
    """Send message via WhatsApp API"""
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    message_data["messaging_product"] = "whatsapp"
    message_data["to"] = phone
    
    try:
        response = requests.post(url, headers=WHATSAPP_HEADERS, json=message_data, timeout=10)
        return response.json()
    except Exception as e:
        print(f"Error sending WhatsApp message: {e}")
        return None

def send_signup_flow(phone_number):
    """Send WhatsApp Flow for signup (slides up in chat)"""
    message_data = {
        "type": "interactive",
        "interactive": {
            "type": "flow",
            "header": {
                "type": "text",
                "text": "Welcome to AJewel Studio 💎"
            },
            "body": {
                "text": "Namaste! Please complete your registration to start browsing our exclusive jewellery collections."
            },
            "footer": {
                "text": "Your information is secure with us"
            },
            "action": {
                "name": "flow",
                "parameters": {
                    "flow_message_version": "3",
                    "flow_token": f"signup_{phone_number}_{int(time.time())}",
                    "flow_id": WHATSAPP_FLOW_ID,
                    "flow_cta": "Sign Up Now",
                    "flow_action": "navigate",
                    "flow_action_payload": {
                        "screen": "SIGNUP_FORM",
                        "data": {
                            "phone": phone_number
                        }
                    }
                }
            }
        }
    }
    
    return send_whatsapp_message(phone_number, message_data)

def send_text_message(phone, text):
    """Send simple text message"""
    message_data = {
        "type": "text",
        "text": {"body": text}
    }
    return send_whatsapp_message(phone, message_data)

def send_collection_menu(phone_number):
    """Send main collections as interactive buttons"""
    buttons = []
    for i, col in enumerate(MAIN_COLLECTIONS[:3]):  # WhatsApp allows max 3 buttons
        buttons.append({
            "type": "reply",
            "reply": {
                "id": f"main_{col['id']}",
                "title": col['title'][:20]  # Max 20 chars
            }
        })
    
    message_data = {
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": "Browse our collections:\n\n" + "\n".join([f"• {c['title']}" for c in MAIN_COLLECTIONS])
            },
            "action": {
                "buttons": buttons
            }
        }
    }
    
    return send_whatsapp_message(phone_number, message_data)

def send_welcome_message(phone_number, customer_name=None):
    """Send welcome message to registered customer"""
    name = customer_name if customer_name else "there"
    text = f"Welcome {name}! 🙏\n\nYou're all set to explore AJewel Studio's exclusive collections."
    send_text_message(phone_number, text)
    time.sleep(1)
    send_collection_menu(phone_number)

# ============================================
# FLOW RESPONSE HANDLER
# ============================================

def handle_signup_flow_response(message):
    """Process signup form data from WhatsApp Flow"""
    phone_number = message['from']
    flow_reply = message['interactive']['nfm_reply']
    
    try:
        # Parse form data
        response_json = json.loads(flow_reply['response_json'])
        
        full_name = response_json.get('full_name', '').strip()
        email = response_json.get('email', '').strip() or None
        customer_type = response_json.get('customer_type', 'retail')
        
        if not full_name:
            send_text_message(phone_number, "Sorry, we need your name to continue. Please try again.")
            return
        
        # Create customer in Shopify
        customer = create_shopify_customer(phone_number, full_name, email, customer_type)
        
        if customer:
            # Store in session
            user_sessions[phone_number] = {
                'customer_id': customer['id'],
                'customer_type': customer_type,
                'name': full_name
            }
            
            # Send welcome and collections
            send_welcome_message(phone_number, full_name.split()[0])
        else:
            send_text_message(phone_number, "Sorry, there was an error. Please try again or contact support.")
    
    except Exception as e:
        print(f"Error handling signup flow: {e}")
        send_text_message(phone_number, "Something went wrong. Please try again.")

# ============================================
# WEBHOOK HANDLERS
# ============================================

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    """Verify webhook for WhatsApp"""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    if mode == 'subscribe' and token == VERIFY_TOKEN:
        return challenge, 200
    return 'Forbidden', 403

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming WhatsApp messages"""
    data = request.json
    
    try:
        if 'entry' not in data:
            return jsonify({"status": "ok"}), 200
        
        for entry in data['entry']:
            for change in entry.get('changes', []):
                value = change.get('value', {})
                
                # Handle messages
                if 'messages' in value:
                    for message in value['messages']:
                        message_id = message.get('id')
                        
                        # Skip duplicates
                        if is_duplicate_message(message_id):
                            continue
                        
                        phone_number = message['from']
                        message_type = message.get('type')
                        
                        # Handle Flow response (signup completion)
                        if message_type == 'interactive':
                            interactive = message.get('interactive', {})
                            if interactive.get('type') == 'nfm_reply':
                                handle_signup_flow_response(message)
                                continue
                        
                        # Handle regular text messages
                        if message_type == 'text':
                            text = message['text']['body'].lower().strip()
                            
                            # Check if customer exists
                            customer_check = check_customer_exists(phone_number)
                            
                            if customer_check and customer_check['is_new']:
                                # New customer - send signup flow
                                send_signup_flow(phone_number)
                            else:
                                # Existing customer - show collections
                                customer = customer_check['customer'] if customer_check else None
                                customer_name = customer['first_name'] if customer else None
                                send_collection_menu(phone_number)
        
        return jsonify({"status": "ok"}), 200
    
    except Exception as e:
        print(f"Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ============================================
# HEALTH CHECK & KEEP-ALIVE
# ============================================

@app.route('/', methods=['GET'])
def home():
    """Health check endpoint"""
    return jsonify({
        "status": "running",
        "service": "AJewel WhatsApp Bot",
        "timestamp": datetime.now().isoformat()
    }), 200

@app.route('/health', methods=['GET'])
def health():
    """Detailed health check"""
    return jsonify({
        "status": "healthy",
        "shopify_store": SHOPIFY_STORE,
        "whatsapp_configured": bool(WHATSAPP_TOKEN and WHATSAPP_PHONE_ID),
        "flow_configured": bool(WHATSAPP_FLOW_ID)
    }), 200

# ============================================
# RUN APP
# ============================================

if __name__ == '__main__':
    print(f"🚀 AJewel WhatsApp Bot starting on port {PORT}")
    print(f"📱 WhatsApp Flow ID: {WHATSAPP_FLOW_ID}")
    app.run(host='0.0.0.0', port=PORT, debug=False)
