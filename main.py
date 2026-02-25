# -*- coding: utf-8 -*-
"""
WhatsApp Bot for AJewel Studio
"""

import os
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

# CONFIG
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

SHOPIFY_STORE = os.getenv("SHOPIFY_STORE")
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")
SHOPIFY_API_VERSION = "2024-01"

SHOPIFY_GRAPHQL_URL = f"https://{SHOPIFY_STORE}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
SHOPIFY_HEADERS = {
    "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
    "Content-Type": "application/json"
}

WHATSAPP_API_URL = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_ID}/messages"
WHATSAPP_HEADERS = {
    "Authorization": f"Bearer {WHATSAPP_TOKEN}",
    "Content-Type": "application/json"
}

PORT = int(os.getenv("PORT", 10000))

app = Flask(__name__)

# WhatsApp Helpers
def send_whatsapp(payload):
    response = requests.post(WHATSAPP_API_URL, headers=WHATSAPP_HEADERS, json=payload)
    return response.json()

def text_message(to, body):
    return send_whatsapp({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body}
    })

def send_signup_button(phone):
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "cta_url",
            "body": {"text": "Welcome to A.Jewel.Studio! 💎\n\nPlease create your account to get started."},
            "action": {
                "name": "cta_url",
                "parameters": {
                    "display_text": "Join Us",
                    "url": f"https://{SHOPIFY_STORE}/pages/join-us"
                }
            }
        }
    }
    return send_whatsapp(payload)

def send_greeting(phone, name):
    message = f"Hello {name}! 👋\n\nWelcome back to A.Jewel.Studio! 💎\n\nHow can we help you today?"
    return text_message(phone, message)

# Shopify Customer Check
def check_customer_exists(phone):
    try:
        # Try multiple phone formats
        phone_variants = [
            phone,
            phone.replace('+', ''),
            phone.replace('+91', ''),
            f"+91{phone.replace('+91', '').replace('+', '')}"
        ]
        
        print(f"🔍 Checking customer with variants: {phone_variants}")
        
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
        
        for variant in phone_variants:
            variables = {"query": f"phone:{variant}"}
            response = requests.post(
                SHOPIFY_GRAPHQL_URL,
                json={'query': query, 'variables': variables},
                headers=SHOPIFY_HEADERS
            )
            
            print(f"📊 Shopify response for {variant}: {response.json()}")
            
            data = response.json().get('data', {})
            customers = data.get('customers', {}).get('edges', [])
            
            if customers:
                customer = customers[0]['node']
                name = f"{customer.get('firstName', '')} {customer.get('lastName', '')}".strip()
                print(f"✅ Customer found: {name}")
                return {
                    'status': 'existing',
                    'name': name or 'Valued Customer',
                    'email': customer.get('email'),
                    'phone': customer.get('phone')
                }
        
        print("👤 Customer not found")
        return {'status': 'new'}
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return {'status': 'new'}

# Routes
@app.route("/", methods=["GET"])
def home():
    return "AJewel WhatsApp Bot Running ✅"

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge"), 200
        return "Error", 403

    try:
        data = request.json
        print("=== DEBUG START ===")
        print(f"Received data: {data}")
        print("=== DEBUG END ===")
        
        if 'entry' in data:
            for entry in data['entry']:
                for change in entry.get('changes', []):
                    value = change.get('value', {})
                    
                    if 'messages' in value:
                        messages = value['messages']
                        for message in messages:
                            phone = message['from']
                            msg_type = message.get('type')
                            
                            print(f"📱 Phone: {phone}, Type: {msg_type}")
                            
                            if msg_type == 'text':
                                text = message['text']['body'].lower().strip()
                                print(f"💬 Text: '{text}'")
                                
                                if text in ['hi', 'hello', 'hey']:
                                    print(f"✅ Processing '{text}'")
                                    
                                    customer_status = check_customer_exists(f"+{phone}")
                                    print(f"👤 Result: {customer_status}")
                                    
                                    if customer_status['status'] == 'existing':
                                        print(f"👋 Sending greeting")
                                        send_greeting(phone, customer_status['name'])
                                    else:
                                        print(f"🆕 Sending signup")
                                        send_signup_button(phone)
                    else:
                        print("⚠️ No messages - status update")
        
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"status": "error"}), 500

@app.route("/form-submit", methods=["POST"])
def form_submit():
    try:
        data = request.json
        print(f"📝 Form data: {data}")
        
        # You can add customer creation logic here if needed
        
        return jsonify({
            "status": "success",
            "message": "Registration successful! Please check WhatsApp."
        }), 200
        
    except Exception as e:
        print(f"❌ Form error: {e}")
        return jsonify({
            "status": "error",
            "message": "Registration failed"
        }), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
