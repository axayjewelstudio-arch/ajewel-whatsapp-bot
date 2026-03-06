# -*- coding: utf-8 -*-
"""
A Jewel Studio WhatsApp Bot - Product List Fixed
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Environment
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN')
WHATSAPP_PHONE_ID = os.getenv('WHATSAPP_PHONE_ID')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN', 'ajewel_verify_token_2024')
SHOPIFY_STORE = os.getenv('SHOPIFY_STORE', 'a-jewel-studio-3.myshopify.com')
SHOPIFY_ACCESS_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN')
GOOGLE_SHEET_ID = os.getenv('GOOGLE_SHEET_ID')
GOOGLE_SERVICE_ACCOUNT_KEY = os.getenv('GOOGLE_SERVICE_ACCOUNT_KEY')
JOIN_US_URL = f"https://{SHOPIFY_STORE}/pages/join-us"

# Google Sheets
def get_sheets_client():
    try:
        if not GOOGLE_SERVICE_ACCOUNT_KEY:
            return None
        creds = Credentials.from_service_account_info(json.loads(GOOGLE_SERVICE_ACCOUNT_KEY), scopes=['https://www.googleapis.com/auth/spreadsheets'])
        return gspread.authorize(creds)
    except:
        return None

sheets_client = get_sheets_client()

def check_customer_in_sheets(phone):
    try:
        if not sheets_client or not GOOGLE_SHEET_ID:
            return {'exists': False}
        sheet = sheets_client.open_by_key(GOOGLE_SHEET_ID).worksheet('Registrations')
        phones = sheet.col_values(1)
        for i, p in enumerate(phones, 1):
            if p == phone:
                row = sheet.row_values(i)
                return {'exists': True, 'first_name': row[1] if len(row) > 1 else '', 'last_name': row[2] if len(row) > 2 else '', 'has_form_data': bool(row[1] if len(row) > 1 else '')}
        return {'exists': False}
    except:
        return {'exists': False}

def log_phone_to_sheets(phone):
    try:
        if not sheets_client or not GOOGLE_SHEET_ID:
            return False
        sheet = sheets_client.open_by_key(GOOGLE_SHEET_ID).worksheet('Registrations')
        sheet.append_row([phone])
        return True
    except:
        return False

# Shopify
def check_customer_in_shopify(phone):
    try:
        if not SHOPIFY_ACCESS_TOKEN:
            return {'exists': False}
        url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/customers/search.json"
        r = requests.get(url, headers={'X-Shopify-Access-Token': SHOPIFY_ACCESS_TOKEN}, params={'query': f'phone:{phone}'}, timeout=10)
        if r.status_code == 200:
            customers = r.json().get('customers', [])
            if customers:
                c = customers[0]
                tags = [t.strip() for t in c.get('tags', '').split(',')]
                return {'exists': True, 'first_name': c.get('first_name', ''), 'last_name': c.get('last_name', ''), 'customer_type': 'B2B' if any(t in ['B2B', 'Wholesale'] for t in tags) else 'Retail'}
        return {'exists': False}
    except:
        return {'exists': False}

def detect_customer_status(phone):
    shopify = check_customer_in_shopify(phone)
    if shopify['exists']:
        ct = shopify.get('customer_type', 'Retail')
        return {'status': 'returning_b2b' if ct == 'B2B' else 'returning_retail', 'customer_type': ct, 'first_name': shopify.get('first_name', 'Customer'), 'last_name': shopify.get('last_name', '')}
    sheets = check_customer_in_sheets(phone)
    if sheets['exists']:
        return {'status': 'incomplete_registration', 'first_name': sheets.get('first_name', ''), 'last_name': sheets.get('last_name', '')}
    log_phone_to_sheets(phone)
    return {'status': 'new'}

# Session
user_sessions = {}

def get_session(phone):
    if phone not in user_sessions:
        user_sessions[phone] = {'created_at': datetime.now(), 'last_activity': datetime.now(), 'customer_name': 'Customer'}
    else:
        user_sessions[phone]['last_activity'] = datetime.now()
    return user_sessions[phone]

def update_session(phone, data):
    s = get_session(phone)
    fn = data.get('first_name', 'Customer')
    ln = data.get('last_name', '')
    s['customer_name'] = f"{fn} {ln}" if ln else fn
    return s

# WhatsApp - Text
def send_text(to, text):
    try:
        url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
        r = requests.post(url, headers={'Authorization': f'Bearer {WHATSAPP_TOKEN}', 'Content-Type': 'application/json'},
                         json={'messaging_product': 'whatsapp', 'to': to, 'type': 'text', 'text': {'body': text}}, timeout=10)
        return r.status_code == 200
    except:
        return False

# WhatsApp - Button
def send_button(to, text, btn_id, btn_title):
    try:
        url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
        r = requests.post(url, headers={'Authorization': f'Bearer {WHATSAPP_TOKEN}', 'Content-Type': 'application/json'},
                         json={'messaging_product': 'whatsapp', 'to': to, 'type': 'interactive',
                              'interactive': {'type': 'button', 'body': {'text': text}, 'action': {'buttons': [{'type': 'reply', 'reply': {'id': btn_id, 'title': btn_title}}]}}}, timeout=10)
        return r.status_code == 200
    except:
        return False

# WhatsApp - List
def send_list(to, header, body, btn_text, sections):
    try:
        url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
        r = requests.post(url, headers={'Authorization': f'Bearer {WHATSAPP_TOKEN}', 'Content-Type': 'application/json'},
                         json={'messaging_product': 'whatsapp', 'to': to, 'type': 'interactive',
                              'interactive': {'type': 'list', 'header': {'type': 'text', 'text': header}, 'body': {'text': body},
                                            'action': {'button': btn_text, 'sections': sections}}}, timeout=10)
        return r.status_code == 200
    except:
        return False

# WhatsApp - CTA
def send_cta(to, text, btn_text, url_link):
    try:
        url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
        r = requests.post(url, headers={'Authorization': f'Bearer {WHATSAPP_TOKEN}', 'Content-Type': 'application/json'},
                         json={'messaging_product': 'whatsapp', 'to': to, 'type': 'interactive',
                              'interactive': {'type': 'cta_url', 'body': {'text': text}, 'action': {'name': 'cta_url', 'parameters': {'display_text': btn_text, 'url': url_link}}}}, timeout=10)
        return r.status_code == 200
    except:
        return False

# WhatsApp - Product List (FIXED - Collection Specific)
def send_product_list(to, collection_id, collection_name):
    """Send product list for specific collection"""
    try:
        url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
        payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': to,
            'type': 'interactive',
            'interactive': {
                'type': 'product_list',
                'header': {
                    'type': 'text',
                    'text': collection_name
                },
                'body': {
                    'text': 'Browse our collection'
                },
                'action': {
                    'catalog_id': WHATSAPP_PHONE_ID,
                    'sections': [{
                        'title': collection_name,
                        'product_items': [
                            {'product_retailer_id': collection_id}
                        ]
                    }]
                }
            }
        }
        
        r = requests.post(url, headers={'Authorization': f'Bearer {WHATSAPP_TOKEN}', 'Content-Type': 'application/json'},
                         json=payload, timeout=10)
        logger.info(f"Product list sent: {r.status_code} - {r.text}")
        return r.status_code == 200
    except Exception as e:
        logger.error(f"Product list error: {str(e)}")
        return False

# Main Categories
MAIN_CATEGORIES = [
    {'id': 'cat_baby', 'title': 'Baby Jewellery'},
    {'id': 'cat_women', 'title': 'Women Jewellery'},
    {'id': 'cat_men', 'title': 'Men Jewellery'},
    {'id': 'cat_studio', 'title': 'Signature Collection'},
    {'id': 'cat_divine', 'title': 'Divine Blessings'}
]

# Sub Categories with Collection IDs
SUB_CATEGORIES = {
    'cat_baby': [
        {'id': 'baby_hair', 'title': 'Hair Accessories', 'collection_id': '26930579176543121'},
        {'id': 'baby_earrings', 'title': 'Earrings', 'collection_id': '34197166099927645'},
        {'id': 'baby_chain', 'title': 'Necklace Chains', 'collection_id': '34159752333640697'},
        {'id': 'baby_rings', 'title': 'Rings', 'collection_id': '27130321023234461'},
        {'id': 'baby_payal', 'title': 'Anklets', 'collection_id': '26132380466413425'},
        {'id': 'baby_bangles', 'title': 'Bangles', 'collection_id': '25812008941803035'}
    ],
    'cat_women': [
        {'id': 'women_face', 'title': 'Face Jewellery', 'collection_id': '26648112538119124'},
        {'id': 'women_hand', 'title': 'Hand Jewellery', 'collection_id': '25990285673976585'},
        {'id': 'women_neck', 'title': 'Neck Jewellery', 'collection_id': '34124391790542901'},
        {'id': 'women_lower', 'title': 'Lower Body', 'collection_id': '25970100975978085'}
    ],
    'cat_men': [
        {'id': 'men_rings', 'title': 'Rings', 'collection_id': '35279590828306838'},
        {'id': 'men_bracelets', 'title': 'Bracelets', 'collection_id': '26028399416826135'},
        {'id': 'men_chains', 'title': 'Chains', 'collection_id': '26614026711549117'},
        {'id': 'men_accessories', 'title': 'Accessories', 'collection_id': '25956694700651645'}
    ]
}

# Webhook Verification
@app.route('/webhook', methods=['GET'])
def verify():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if mode == 'subscribe' and token == VERIFY_TOKEN:
        return challenge, 200
    return 'Forbidden', 403

# Webhook Handler
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        if not data or data.get('object') != 'whatsapp_business_account':
            return jsonify({'status': 'ok'}), 200
        
        msgs = data.get('entry', [{}])[0].get('changes', [{}])[0].get('value', {}).get('messages', [])
        if not msgs:
            return jsonify({'status': 'ok'}), 200
        
        msg = msgs[0]
        from_num = msg.get('from')
        msg_type = msg.get('type')
        
        # Detect customer
        cust_data = detect_customer_status(from_num)
        session = update_session(from_num, cust_data)
        
        # Handle text
        if msg_type == 'text':
            text = msg.get('text', {}).get('body', '').strip()
            
            if cust_data['status'] == 'new':
                send_cta(from_num, "Welcome to *A Jewel Studio*.\n\nTap Join Us to explore our collections.", "Join Us", f"{JOIN_US_URL}?wa={from_num}")
            elif cust_data['status'] == 'incomplete_registration':
                send_cta(from_num, "Hello.\n\nComplete your registration to unlock our full collection.", "Complete Now", f"{JOIN_US_URL}?wa={from_num}")
            else:
                send_button(from_num, f"Welcome back, *{session['customer_name']}*.\n\nHow can I assist you?", 'menu', 'Menu')
        
        # Handle interactive
        elif msg_type == 'interactive':
            interactive = msg.get('interactive', {})
            
            # Button click
            if interactive.get('type') == 'button_reply':
                btn_id = interactive.get('button_reply', {}).get('id', '')
                
                if btn_id == 'menu':
                    sections = [{'title': 'Categories', 'rows': [{'id': cat['id'], 'title': cat['title']} for cat in MAIN_CATEGORIES]}]
                    send_list(from_num, 'Main Menu', 'Please select a category', 'Select Category', sections)
            
            # List selection
            elif interactive.get('type') == 'list_reply':
                list_id = interactive.get('list_reply', {}).get('id', '')
                
                # Main category selected
                if list_id in [c['id'] for c in MAIN_CATEGORIES]:
                    if list_id in SUB_CATEGORIES:
                        sections = [{'title': 'Sub Categories', 'rows': [{'id': sub['id'], 'title': sub['title']} for sub in SUB_CATEGORIES[list_id]]}]
                        send_list(from_num, 'Select Collection', 'Choose a sub-category', 'Select', sections)
                    else:
                        send_text(from_num, "Coming soon.")
                
                # Sub-category selected - Send Product List
                else:
                    # Find collection
                    for cat_subs in SUB_CATEGORIES.values():
                        for sub in cat_subs:
                            if sub['id'] == list_id:
                                send_product_list(from_num, sub['collection_id'], sub['title'])
                                break
        
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify({'status': 'error'}), 500

# Health
@app.route('/', methods=['GET'])
@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': 'A Jewel Studio WhatsApp Bot'}), 200

# Security
@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    return response

# Main
if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    logger.info("A Jewel Studio WhatsApp Bot - Product List API")
    app.run(host='0.0.0.0', port=port, debug=False)
