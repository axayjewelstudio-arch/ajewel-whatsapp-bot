# main.py - Basic Customer Check & Registration Flow

from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv

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
    url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/customers/search.json?query=phone:{phone}"
    response = requests.get(url, headers=SHOPIFY_HEADERS)
    data = response.json()
    
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
    requests.post(url, headers=headers, json=payload)

def send_signup_flow(phone):
    """Send WhatsApp Flow for signup"""
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        'Authorization': f'Bearer {WHATSAPP_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "flow",
            "header": {"type": "text", "text": "Welcome to A Jewel Studio 💎"},
            "body": {"text": "Please complete your registration"},
            "footer": {"text": "Your data is secure"},
            "action": {
                "name": "flow",
                "parameters": {
                    "flow_message_version": "3",
                    "flow_token": f"signup_{phone}",
                    "flow_id": "YOUR_FLOW_ID",  # Meta Business Manager se milega
                    "flow_cta": "Sign Up",
                    "flow_action": "navigate",
                    "flow_action_payload": {"screen": "SIGNUP"}
                }
            }
        }
    }
    
    requests.post(url, headers=headers, json=payload)

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
        
        try:
            message = data['entry'][0]['changes'][0]['value']['messages'][0]
            phone = message['from']
            msg_type = message['type']
            
            # Text message: "hi"
            if msg_type == 'text':
                text = message['text']['body'].lower().strip()
                
                if text == 'hi':
                    # Check customer in Shopify
                    result = check_customer(phone)
                    
                    if result['status'] == 'new':
                        # New customer - send signup flow
                        send_signup_flow(phone)
                    
                    elif result['status'] == 'old':
                        # Old customer - welcome message
                        name = result['name']
                        welcome_msg = f"{name} We welcome You in A Jewel Studio 💎\n\nType Hi to Continue with us."
                        send_message(phone, welcome_msg)
            
            # Flow response: signup data
            elif msg_type == 'interactive':
                interactive = message['interactive']
                
                if interactive.get('type') == 'nfm_reply':
                    # Flow submitted
                    flow_data = interactive['nfm_reply']['response_json']
                    import json
                    form_data = json.loads(flow_data)
                    
                    # Extract data
                    name = form_data.get('full_name')
                    email = form_data.get('email')
                    
                    # Save to Shopify
                    save_result = create_customer(phone, name, email)
                    
                    if save_result['status'] == 'success':
                        success_msg = f"Your Account Created Successfully.\n\n{name} We welcome You in A Jewel Studio 💎\n\nType Hi to Continue with us."
                        send_message(phone, success_msg)
        
        except Exception as e:
            print(f"Error: {e}")
        
        return jsonify({"status": "ok"}), 200

# ========== RUN ==========

if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
