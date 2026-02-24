import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Environment Variables
SHOPIFY_STORE = os.getenv('SHOPIFY_STORE')  # your-store.myshopify.com
SHOPIFY_ACCESS_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN')
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN')
WHATSAPP_PHONE_ID = os.getenv('WHATSAPP_PHONE_ID')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN', 'ajewelbot_verify_2026')

# API URLs
SHOPIFY_GRAPHQL_URL = f"https://{SHOPIFY_STORE}/admin/api/2024-01/graphql.json"
WHATSAPP_API_URL = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"

# Headers
SHOPIFY_HEADERS = {
    'Content-Type': 'application/json',
    'X-Shopify-Access-Token': SHOPIFY_ACCESS_TOKEN
}

WHATSAPP_HEADERS = {
    'Authorization': f'Bearer {WHATSAPP_TOKEN}',
    'Content-Type': 'application/json'
}


def check_customer_exists(phone):
    """Check if customer exists in Shopify - flexible phone matching"""
    try:
        # Multiple phone format variants
        phone_variants = [
            phone,
            phone.replace('+', ''),
            phone.replace('+91', ''),
            f"+91{phone.replace('+91', '').replace('+', '')}"
        ]
        
        print(f"🔍 Checking customer with phone variants: {phone_variants}")
        
        query = """
        query($query: String!) {
            customers(first: 10, query: $query) {
                edges {
                    node {
                        id
                        firstName
                        lastName
                        email
                        phone
                    }
                }
            }
        }
        """
        
        # Try each phone variant
        for variant in phone_variants:
            variables = {"query": f"phone:{variant}"}
            response = requests.post(
                SHOPIFY_GRAPHQL_URL,
                json={'query': query, 'variables': variables},
                headers=SHOPIFY_HEADERS
            )
            
            data = response.json().get('data', {})
            customers = data.get('customers', {}).get('edges', [])
            
            if customers:
                customer = customers[0]['node']
                name = f"{customer.get('firstName', '')} {customer.get('lastName', '')}".strip()
                print(f"✅ Existing customer found: {name} ({customer.get('phone')})")
                return {
                    'status': 'existing',
                    'name': name or 'Valued Customer',
                    'email': customer.get('email'),
                    'phone': customer.get('phone')
                }
        
        print("👤 New customer - not found in Shopify")
        return {'status': 'new'}
        
    except Exception as e:
        print(f"❌ Error checking customer: {e}")
        return {'status': 'new'}


def send_greeting(phone, name):
    """Send personalized greeting to existing customer"""
    message = f"Hello {name}! 👋\n\nWelcome back to A.Jewel.Studio! 💎\n\nHow can we help you today?\n\n✨ Browse our latest collection\n📦 Track your order\n💬 Chat with us"
    
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": message}
    }
    
    print(f"📤 Sending personalized greeting to {name}")
    
    response = requests.post(
        WHATSAPP_API_URL,
        headers=WHATSAPP_HEADERS,
        json=payload
    )
    
    print(f"✅ Greeting sent: {response.status_code}")
    return response.json()


def send_signup_button(phone):
    """Send Join Us button to new customer"""
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": "Welcome to A.Jewel.Studio! 💎\n\nDiscover our exquisite collection of handcrafted jewelry.\n\nJoin us to get exclusive updates and personalized service!"
            },
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {
                            "id": "join_now",
                            "title": "Join Us ✨"
                        }
                    }
                ]
            }
        }
    }
    
    print(f"📤 Sending Join Us button to new customer")
    
    response = requests.post(
        WHATSAPP_API_URL,
        headers=WHATSAPP_HEADERS,
        json=payload
    )
    
    print(f"✅ Join button sent: {response.status_code}")
    return response.json()


def create_customer(phone, name="New Customer"):
    """Create new customer in Shopify"""
    try:
        # Normalize phone format
        normalized_phone = f"+{phone}" if not phone.startswith('+') else phone
        
        mutation = """
        mutation customerCreate($input: CustomerInput!) {
            customerCreate(input: $input) {
                customer {
                    id
                    firstName
                    phone
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        variables = {
            "input": {
                "phone": normalized_phone,
                "firstName": name,
                "tags": ["WhatsApp", "AJewelBot"]
            }
        }
        
        response = requests.post(
            SHOPIFY_GRAPHQL_URL,
            json={'query': mutation, 'variables': variables},
            headers=SHOPIFY_HEADERS
        )
        
        result = response.json()
        print(f"📊 Customer creation response: {result}")
        
        if result.get('data', {}).get('customerCreate', {}).get('customer'):
            print(f"✅ Customer created successfully: {normalized_phone}")
            return {'status': 'success', 'phone': normalized_phone}
        else:
            errors = result.get('data', {}).get('customerCreate', {}).get('userErrors', [])
            print(f"❌ Customer creation failed: {errors}")
            return {'status': 'error', 'errors': errors}
            
    except Exception as e:
        print(f"❌ Exception creating customer: {e}")
        return {'status': 'error', 'message': str(e)}


def send_welcome_message(phone, name):
    """Send welcome message after successful registration"""
    message = f"Welcome to A.Jewel.Studio, {name}! 🎉\n\n✅ Your account has been created successfully!\n\n💎 Explore our collection\n📱 Stay updated with exclusive offers\n🛍️ Enjoy personalized shopping experience\n\nHow can we assist you today?"
    
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": message}
    }
    
    response = requests.post(
        WHATSAPP_API_URL,
        headers=WHATSAPP_HEADERS,
        json=payload
    )
    
    print(f"✅ Welcome message sent")
    return response.json()


@app.route('/webhook', methods=['GET'])
def verify_webhook():
    """Verify webhook for WhatsApp"""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    if mode == 'subscribe' and token == VERIFY_TOKEN:
        print("✅ Webhook verified")
        return challenge, 200
    else:
        print("❌ Webhook verification failed")
        return 'Forbidden', 403


@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming WhatsApp messages"""
    try:
        data = request.json
        print(f"\n{'='*50}")
        print(f"📥 Incoming webhook data: {data}")
        print(f"{'='*50}\n")
        
        if 'entry' in data:
            for entry in data['entry']:
                for change in entry.get('changes', []):
                    value = change.get('value', {})
                    
                    # Handle incoming messages
                    if 'messages' in value:
                        messages = value['messages']
                        for message in messages:
                            phone = message['from']
                            msg_type = message.get('type')
                            
                            print(f"📱 Message from: {phone}, Type: {msg_type}")
                            
                            # Handle text messages
                            if msg_type == 'text':
                                text = message['text']['body'].lower().strip()
                                print(f"💬 Text: '{text}'")
                                
                                # Greeting trigger
                                if text in ['hi', 'hello', 'hey', 'start']:
                                    print(f"👋 Greeting detected: '{text}'")
                                    
                                    # Check if customer exists
                                    customer_status = check_customer_exists(f"+{phone}")
                                    
                                    if customer_status['status'] == 'existing':
                                        # Existing customer - send personalized greeting
                                        print(f"🎯 Existing customer flow")
                                        send_greeting(phone, customer_status['name'])
                                    else:
                                        # New customer - send Join Us button
                                        print(f"🆕 New customer flow")
                                        send_signup_button(phone)
                            
                            # Handle button clicks
                            elif msg_type == 'interactive':
                                button_reply = message.get('interactive', {}).get('button_reply', {})
                                button_id = button_reply.get('id')
                                
                                print(f"🔘 Button clicked: {button_id}")
                                
                                if button_id == 'join_now':
                                    print(f"✨ Join Now button clicked - creating account")
                                    
                                    # Create customer account
                                    result = create_customer(phone, "New Customer")
                                    
                                    if result['status'] == 'success':
                                        # Send welcome message
                                        send_welcome_message(phone, "New Customer")
                                    else:
                                        # Send error message
                                        error_msg = "Sorry, we couldn't create your account. Please try again or contact support."
                                        payload = {
                                            "messaging_product": "whatsapp",
                                            "to": phone,
                                            "type": "text",
                                            "text": {"body": error_msg}
                                        }
                                        requests.post(WHATSAPP_API_URL, headers=WHATSAPP_HEADERS, json=payload)
        
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/', methods=['GET'])
def home():
    """Health check endpoint"""
    return jsonify({
        'status': 'running',
        'service': 'AJewelBot v2',
        'message': 'WhatsApp automation is active'
    }), 200


if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
