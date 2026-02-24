#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AJewel WhatsApp Bot - Custom App Version
=========================================
Uses Shopify Admin API with custom app authentication
"""

from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv
import json
import threading
import time
import re
import urllib.parse
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Shopify Custom App Configuration
SHOPIFY_STORE        = os.getenv('SHOPIFY_STORE')
SHOPIFY_ACCESS_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN')
SHOPIFY_API_VERSION  = '2024-01'

# WhatsApp Configuration
WHATSAPP_TOKEN    = os.getenv('ACCESS_TOKEN')
WHATSAPP_PHONE_ID = os.getenv('PHONE_NUMBER_ID')
VERIFY_TOKEN      = os.getenv('VERIFY_TOKEN')

# Razorpay Configuration
RAZORPAY_KEY_ID     = os.getenv('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET')

PORT = int(os.getenv('PORT', 10000))

# Shopify API Setup
SHOPIFY_API_BASE = f"https://{SHOPIFY_STORE}/admin/api/{SHOPIFY_API_VERSION}"
SHOPIFY_HEADERS = {
    'X-Shopify-Access-Token': SHOPIFY_ACCESS_TOKEN,
    'Content-Type': 'application/json'
}

# Global storage
user_sessions = {}
processed_messages = {}
CACHE_DURATION = timedelta(minutes=5)

# Collections (WhatsApp Catalogue IDs)
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
# Utility Functions
# ============================================

def normalize_phone(phone):
    """Normalize phone number to E.164 format"""
    phone = re.sub(r'\D', '', phone)
    if phone.startswith('91') and len(phone) == 12:
        return f"+{phone}"
    elif len(phone) == 10:
        return f"+91{phone}"
    return f"+{phone}"

def search_customer_by_phone(phone):
    """Search customer in Shopify by phone"""
    normalized = normalize_phone(phone)
    encoded = urllib.parse.quote(normalized)
    url = f"{SHOPIFY_API_BASE}/customers/search.json?query=phone:{encoded}"
    
    try:
        response = requests.get(url, headers=SHOPIFY_HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        customers = data.get('customers', [])
        return customers[0] if customers else None
    except Exception as e:
        print(f"Error searching customer: {e}")
        return None

def send_whatsapp_message(phone, message):
    """Send text message via WhatsApp"""
    url = f"https://graph.facebook.com/v17.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": message}
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error sending message: {e}")
        return False

def send_catalogue_message(phone, catalogue_id, body_text="Browse our collection"):
    """Send WhatsApp catalogue message"""
    url = f"https://graph.facebook.com/v17.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "catalog_message",
            "body": {"text": body_text},
            "action": {
                "name": "catalog_message",
                "parameters": {"thumbnail_product_retailer_id": catalogue_id}
            }
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error sending catalogue: {e}")
        return False

def send_interactive_buttons(phone, body_text, buttons):
    """Send interactive button message"""
    url = f"https://graph.facebook.com/v17.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    button_components = []
    for idx, btn in enumerate(buttons[:3]):  # Max 3 buttons
        button_components.append({
            "type": "reply",
            "reply": {
                "id": f"btn_{idx}",
                "title": btn["title"][:20]  # Max 20 chars
            }
        })
    
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body_text},
            "action": {"buttons": button_components}
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error sending buttons: {e}")
        return False

def send_list_message(phone, body_text, button_text, sections):
    """Send interactive list message"""
    url = f"https://graph.facebook.com/v17.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": body_text},
            "action": {
                "button": button_text,
                "sections": sections
            }
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error sending list: {e}")
        return False

# ============================================
# Message Handlers
# ============================================

def handle_main_menu(phone):
    """Show main collection menu"""
    sections = [{
        "title": "Main Categories",
        "rows": [
            {"id": col["id"], "title": col["title"][:24]}
            for col in MAIN_COLLECTIONS
        ]
    }]
    
    send_list_message(
        phone,
        "Welcome to A.Jewel Studio! 💎\n\nSelect a category to explore:",
        "View Categories",
        sections
    )

def handle_sub_menu(phone, main_collection_id):
    """Show sub-collection menu"""
    subs = SUB_COLLECTIONS.get(main_collection_id, [])
    
    if not subs:
        send_whatsapp_message(phone, "No sub-categories available.")
        return
    
    sections = [{
        "title": "Sub Categories",
        "rows": [
            {"id": sub["id"], "title": sub["title"][:24]}
            for sub in subs
        ]
    }]
    
    send_list_message(
        phone,
        "Choose a sub-category:",
        "Select",
        sections
    )
    
    user_sessions[phone] = {"main_collection": main_collection_id}

def handle_catalogue_view(phone, catalogue_id):
    """Show WhatsApp catalogue"""
    send_catalogue_message(phone, catalogue_id, "Here are our products:")

# ============================================
# Webhook Routes
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
    try:
        data = request.get_json()
        
        if not data.get('entry'):
            return jsonify({"status": "no entry"}), 200
        
        for entry in data['entry']:
            for change in entry.get('changes', []):
                value = change.get('value', {})
                messages = value.get('messages', [])
                
                for message in messages:
                    phone = message.get('from')
                    msg_id = message.get('id')
                    
                    # Deduplication
                    if msg_id in processed_messages:
                        continue
                    processed_messages[msg_id] = datetime.now()
                    
                    # Handle text messages
                    if message.get('type') == 'text':
                        text = message['text']['body'].lower().strip()
                        
                        if text in ['hi', 'hello', 'start', 'menu']:
                            handle_main_menu(phone)
                    
                    # Handle interactive responses
                    elif message.get('type') == 'interactive':
                        interactive = message.get('interactive', {})
                        
                        if interactive.get('type') == 'list_reply':
                            selected_id = interactive['list_reply']['id']
                            
                            # Check if main collection
                            if any(col['id'] == selected_id for col in MAIN_COLLECTIONS):
                                handle_sub_menu(phone, selected_id)
                            else:
                                # Sub-collection selected - show catalogue
                                handle_catalogue_view(phone, selected_id)
        
        # Cleanup old cache
        cutoff = datetime.now() - CACHE_DURATION
        processed_messages.clear()
        
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        print(f"Webhook error: {e}")
        return jsonify({"status": "error"}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()}), 200

@app.route('/', methods=['GET'])
def home():
    """Home route"""
    return jsonify({
        "service": "AJewel WhatsApp Bot",
        "version": "2.0",
        "status": "running"
    }), 200

# ============================================
# Keep-Alive for Render
# ============================================

def keep_alive():
    """Ping server every 10 minutes to prevent sleep"""
    while True:
        time.sleep(600)  # 10 minutes
        try:
            requests.get(f"http://localhost:{PORT}/health", timeout=5)
            print(f"Keep-alive ping at {datetime.now()}")
        except:
            pass

# ============================================
# Main
# ============================================

if __name__ == '__main__':
    # Start keep-alive thread
    threading.Thread(target=keep_alive, daemon=True).start()
    
    print(f"🚀 AJewel Bot starting on port {PORT}")
    print(f"📱 Shopify Store: {SHOPIFY_STORE}")
    
    app.run(host='0.0.0.0', port=PORT, debug=False)
