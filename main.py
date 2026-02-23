# main.py - AJewel WhatsApp Bot Complete Flow
from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv
import json

load_dotenv()

app = Flask(__name__)

# Environment Variables
SHOPIFY_STORE = os.getenv('SHOPIFY_STORE')
SHOPIFY_ACCESS_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN')
WHATSAPP_TOKEN = os.getenv('ACCESS_TOKEN')
WHATSAPP_PHONE_ID = os.getenv('PHONE_NUMBER_ID')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN')
RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET')

# Shopify API Headers
SHOPIFY_HEADERS = {
    'X-Shopify-Access-Token': SHOPIFY_ACCESS_TOKEN,
    'Content-Type': 'application/json'
}

# ==================== HELPER FUNCTIONS ====================

def send_whatsapp_message(phone_number, message):
    """Send text message via WhatsApp"""
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        'Authorization': f'Bearer {WHATSAPP_TOKEN}',
        'Content-Type': 'application/json'
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "text",
        "text": {"body": message}
    }
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

def send_whatsapp_buttons(phone_number, message, buttons):
    """Send interactive buttons"""
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        'Authorization': f'Bearer {WHATSAPP_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    button_list = []
    for i, btn in enumerate(buttons[:3]):  # Max 3 buttons
        button_list.append({
            "type": "reply",
            "reply": {
                "id": f"btn_{i}",
                "title": btn
            }
        })
    
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": message},
            "action": {"buttons": button_list}
        }
    }
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

def get_shopify_customer(phone):
    """Check if customer exists in Shopify"""
    url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/customers/search.json?query=phone:{phone}"
    response = requests.get(url, headers=SHOPIFY_HEADERS)
    data = response.json()
    
    if data.get('customers') and len(data['customers']) > 0:
        return data['customers'][0]
    return None

def create_shopify_customer(name, phone, email, customer_type="Retailer"):
    """Create new customer in Shopify"""
    url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/customers.json"
    
    payload = {
        "customer": {
            "first_name": name,
            "phone": phone,
            "email": email,
            "tags": customer_type,
            "note": f"Registered via WhatsApp - Type: {customer_type}"
        }
    }
    
    response = requests.post(url, headers=SHOPIFY_HEADERS, json=payload)
    return response.json()

def get_shopify_collections():
    """Get all collections"""
    url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/custom_collections.json"
    response = requests.get(url, headers=SHOPIFY_HEADERS)
    data = response.json()
    return data.get('custom_collections', [])

def get_collection_products(collection_id):
    """Get products from a collection"""
    url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/products.json?collection_id={collection_id}"
    response = requests.get(url, headers=SHOPIFY_HEADERS)
    data = response.json()
    return data.get('products', [])

def create_draft_order(customer_id, line_items):
    """Create draft order"""
    url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/draft_orders.json"
    
    payload = {
        "draft_order": {
            "customer": {"id": customer_id},
            "line_items": line_items,
            "note": "Order placed via WhatsApp Bot"
        }
    }
    
    response = requests.post(url, headers=SHOPIFY_HEADERS, json=payload)
    return response.json()

def generate_razorpay_link(amount, customer_name, customer_phone):
    """Generate Razorpay payment link"""
    import base64
    
    url = "https://api.razorpay.com/v1/payment_links"
    auth = base64.b64encode(f"{RAZORPAY_KEY_ID}:{RAZORPAY_KEY_SECRET}".encode()).decode()
    
    headers = {
        'Authorization': f'Basic {auth}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        "amount": int(amount * 100),  # Amount in paise
        "currency": "INR",
        "description": "A Jewel Studio - Design Purchase",
        "customer": {
            "name": customer_name,
            "contact": customer_phone
        },
        "notify": {
            "sms": True,
            "email": False,
            "whatsapp": True
        },
        "callback_url": f"https://ajewel-whatsapp-bot.onrender.com/payment/callback",
        "callback_method": "get"
    }
    
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

# ==================== WEBHOOK ENDPOINTS ====================

@app.route('/')
def home():
    return "AJewel WhatsApp Bot is Running! 🚀"

@app.route('/webhook', methods=['GET', 'POST'])
def whatsapp_webhook():
    """WhatsApp webhook - Main entry point"""
    
    # Verification (GET request)
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            return challenge, 200
        return 'Forbidden', 403
    
    # Message handling (POST request)
    if request.method == 'POST':
        data = request.json
        
        try:
            # Extract message details
            entry = data['entry'][0]
            changes = entry['changes'][0]
            value = changes['value']
            
            if 'messages' in value:
                message = value['messages'][0]
                from_number = message['from']
                message_type = message['type']
                
                # Handle text messages
                if message_type == 'text':
                    text = message['text']['body'].strip().lower()
                    handle_text_message(from_number, text)
                
                # Handle button responses
                elif message_type == 'interactive':
                    button_reply = message['interactive']['button_reply']['title']
                    handle_button_response(from_number, button_reply)
        
        except Exception as e:
            print(f"Error: {e}")
        
        return jsonify({"status": "ok"}), 200

def handle_text_message(phone, text):
    """Handle incoming text messages"""
    
    # Check if customer exists
    customer = get_shopify_customer(phone)
    
    if text in ['hi', 'hello', 'hey', 'start']:
        if customer:
            # Existing customer
            customer_name = customer.get('first_name', 'Customer')
            customer_tags = customer.get('tags', '')
            
            if 'B2B' in customer_tags or 'Wholesaler' in customer_tags:
                # B2B Customer Flow
                message = f"Hello {customer_name}! Welcome to A Jewel Studio 💎"
                send_whatsapp_buttons(phone, message, ["Browse Products", "My Orders", "Support"])
            else:
                # Retail Customer Flow
                message = f"Hello {customer_name}! Welcome to A Jewel Studio 💎\n\nKya aap Custom Jewellery karvana chahte hain?"
                send_whatsapp_buttons(phone, message, ["Yes - Custom", "No - Browse Products"])
        else:
            # New customer - Registration flow
            message = "Welcome to A Jewel Studio! 💎\n\nOrder karne ke liye pehle account banana hoga.\n\nKripya apna naam bhejein:"
            send_whatsapp_message(phone, message)
    
    elif text == 'menu':
        # Show collections
        collections = get_shopify_collections()
        if collections:
            message = "📂 Our Collections:\n\n"
            for i, col in enumerate(collections[:5], 1):
                message += f"{i}. {col['title']}\n"
            message += "\nCollection number bhejein (e.g., 1)"
            send_whatsapp_message(phone, message)
        else:
            send_whatsapp_message(phone, "Collections load nahi ho paye. Kripya baad mein try karein.")
    
    else:
        # Default response
        send_whatsapp_message(phone, "Main aapki madad ke liye yahan hoon! 'Hi' type karein to start karein.")

def handle_button_response(phone, button_text):
    """Handle button click responses"""
    
    customer = get_shopify_customer(phone)
    
    if button_text == "Browse Products":
        collections = get_shopify_collections()
        if collections:
            message = "📂 Select Category:\n\n"
            for i, col in enumerate(collections[:5], 1):
                message += f"{i}. {col['title']}\n"
            send_whatsapp_message(phone, message)
    
    elif button_text == "Yes - Custom":
        message = "Great! Custom jewellery ke liye appointment book karein:\n\n"
        message += "🔗 Book Appointment: https://a-jewel-studio-3.myshopify.com/pages/appointment\n\n"
        message += "Humari team aapse jald hi contact karegi!"
        send_whatsapp_message(phone, message)
    
    elif button_text == "No - Browse Products":
        collections = get_shopify_collections()
        if collections:
            message = "📂 Our Collections:\n\n"
            for i, col in enumerate(collections[:5], 1):
                message += f"{i}. {col['title']}\n"
            send_whatsapp_message(phone, message)

# ==================== RAZORPAY WEBHOOKS ====================

@app.route('/payment/callback', methods=['GET', 'POST'])
def payment_callback():
    """Handle Razorpay payment status"""
    
    if request.method == 'GET':
        # Payment success redirect
        return "Payment successful! Check WhatsApp for confirmation."
    
    if request.method == 'POST':
        # Webhook from Razorpay
        data = request.json
        
        if data.get('event') == 'payment_link.paid':
            # Payment successful
            payment_link = data['payload']['payment_link']['entity']
            customer_phone = payment_link['customer']['contact']
            
            message = "✅ Payment Successful!\n\n"
            message += "Thank you for your purchase! 💎\n\n"
            message += "Design files aapke email pe bhej di gayi hain.\n\n"
            message += "Download link: [Check your email]"
            
            send_whatsapp_message(customer_phone, message)
        
        return jsonify({"status": "ok"}), 200

# ==================== RUN SERVER ====================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
