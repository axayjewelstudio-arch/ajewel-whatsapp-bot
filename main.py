# main.py - Basic Customer Check & Registration Flow

from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv
import json
import traceback

load_dotenv()
app = Flask(__name__)

# Environment Variables
SHOPIFY_STORE = os.getenv('SHOPIFY_STORE')
SHOPIFY_ACCESS_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN')
WHATSAPP_TOKEN = os.getenv('ACCESS_TOKEN')
WHATSAPP_PHONE_ID = os.getenv('PHONE_NUMBER_ID')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN')

# Shopify Headers
SHOPIFY_HEADERS = {
    'X-Shopify-Access-Token': SHOPIFY_ACCESS_TOKEN,
    'Content-Type': 'application/json'
}

# ========== SHOPIFY FUNCTIONS ==========

def check_customer(phone):
    """Check if customer exists in Shopify"""
    # Format phone with +
    if not phone.startswith('+'):
        phone = '+' + phone
    
    print(f"🔍 Checking customer: {phone}")
    
    url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/customers/search.json?query=phone:{phone}"
    response = requests.get(url, headers=SHOPIFY_HEADERS)
    data = response.json()
    
    print(f"📊 Shopify response: {data}")
    
    if data.get('customers') and len(data['customers']) > 0:
        customer = data['customers'][0]
        return {
            'status': 'old',
            'name': customer.get('first_name', 'Customer'),
            'customer_id': customer.get('id')
        }
    return {'status': 'new'}

def create_customer(phone, name, email):
    """Create new customer in Shopify"""
    url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/customers.json"
    
    customer_data = {
        "customer": {
            "phone": phone,
            "first_name": name,
            "email": email,
            "verified_email": True,
            "tags": "whatsapp-signup"
        }
    }
    
    response = requests.post(url, headers=SHOPIFY_HEADERS, json=customer_data)
    
    if response.status_code == 201:
        return {'status': 'success', 'data': response.json()}
    return {'status': 'error'}

# ========== WHATSAPP FUNCTIONS ==========

def send_message(phone, message):
    """Send text message"""
    print(f"📤 Sending message to {phone}: {message}")
    
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        'Authorization': f'Bearer {WHATSAPP_TOKEN}',
        'Content-Type': 'application/json'
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": message}
    }
    response = requests.post(url, headers=headers, json=payload)
    print(f"📥 WhatsApp response: {response.json()}")

def send_signup_flow(phone):
    """Send signup link via text message"""
    print(f"📋 Sending signup link to {phone}")
    
    signup_url = "https://a-jewel-studio-3.myshopify.com/pages/join-us"
    message = f"Welcome to A Jewel Studio! 💎\n\nPlease complete your registration:\n{signup_url}\n\nAfter signup, type 'Hi' again to continue."
    
    send_message(phone, message)

# ========== WEBHOOK ==========

@app.route('/')
def home():
    return "AJewel Bot Running! 🚀"

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # Verification (GET)
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            return challenge, 200
        return 'Forbidden', 403
    
    # Message handling (POST)
    if request.method == 'POST':
        data = request.json
        
        print("=== DEBUG START ===")
        print(f"Received data: {data}")
        print("=== DEBUG END ===")
        
        try:
            message = data['entry'][0]['changes'][0]['value']['messages'][0]
            phone = message['from']
            msg_type = message['type']
            
            print(f"📱 Phone: {phone}, Type: {msg_type}")
            
            # Text message: "hi"
            if msg_type == 'text':
                text = message['text']['body'].lower().strip()
                print(f"💬 Text received: '{text}'")
                
                if text == 'hi':
                    print("✅ Processing 'hi' command")
                    
                    # Check customer in Shopify
                    result = check_customer(phone)
                    print(f"👤 Customer check result: {result}")
                    
                    if result['status'] == 'new':
                        print("🆕 New customer - sending signup link")
                        send_signup_flow(phone)
                    
                    elif result['status'] == 'old':
                        print("👋 Existing customer - sending welcome")
                        name = result['name']
                        welcome_msg = f"{name} We welcome You in A Jewel Studio 💎\n\nType Hi to Continue with us."
                        send_message(phone, welcome_msg)
        
        except Exception as e:
            print(f"❌ ERROR: {e}")
            traceback.print_exc()
        
        return jsonify({"status": "ok"}), 200

# ========== RUN ==========

if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
