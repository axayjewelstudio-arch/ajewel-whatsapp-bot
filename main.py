# -*- coding: utf-8 -*-
"""
A Jewel Studio WhatsApp Bot - Phase 3: Messaging & UX
Phase 1 (15) + Phase 2 (10) + Phase 3 (15) = 40 Total Features
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

# ═══════════════════════════════════════════════════════════
# FLASK APP SETUP
# ═══════════════════════════════════════════════════════════

app = Flask(__name__)
CORS(app)

# ═══════════════════════════════════════════════════════════
# LOGGING CONFIGURATION
# ═══════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
# ENVIRONMENT VARIABLES
# ═══════════════════════════════════════════════════════════

WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN')
WHATSAPP_PHONE_ID = os.getenv('WHATSAPP_PHONE_ID')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN', 'ajewel_verify_token_2024')

SHOPIFY_STORE = os.getenv('SHOPIFY_STORE', 'a-jewel-studio-3.myshopify.com')
SHOPIFY_ACCESS_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN')

GOOGLE_SHEET_ID = os.getenv('GOOGLE_SHEET_ID')
GOOGLE_SERVICE_ACCOUNT_KEY = os.getenv('GOOGLE_SERVICE_ACCOUNT_KEY')

JOIN_US_URL = f"https://{SHOPIFY_STORE}/pages/join-us"
LOGO_IMAGE_URL = os.getenv('LOGO_IMAGE_URL', '')

if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
    logger.error("❌ Missing WhatsApp credentials!")

# ═══════════════════════════════════════════════════════════
# GOOGLE SHEETS SETUP
# ═══════════════════════════════════════════════════════════

def get_google_sheets_client():
    """Initialize Google Sheets client"""
    try:
        if not GOOGLE_SERVICE_ACCOUNT_KEY:
            return None
        credentials_dict = json.loads(GOOGLE_SERVICE_ACCOUNT_KEY)
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
        client = gspread.authorize(credentials)
        logger.info("✅ Google Sheets initialized")
        return client
    except Exception as e:
        logger.error(f"❌ Sheets error: {str(e)}")
        return None

sheets_client = get_google_sheets_client()

# ═══════════════════════════════════════════════════════════
# GOOGLE SHEETS FUNCTIONS
# ═══════════════════════════════════════════════════════════

def check_customer_in_sheets(phone_number):
    """Check if customer exists in Google Sheets"""
    try:
        if not sheets_client or not GOOGLE_SHEET_ID:
            return {'exists': False}
        
        sheet = sheets_client.open_by_key(GOOGLE_SHEET_ID)
        worksheet = sheet.worksheet('Registrations')
        phone_column = worksheet.col_values(1)
        
        for idx, cell_value in enumerate(phone_column, start=1):
            if cell_value == phone_number:
                row_data = worksheet.row_values(idx)
                first_name = row_data[1] if len(row_data) > 1 else ''
                last_name = row_data[2] if len(row_data) > 2 else ''
                
                return {
                    'exists': True,
                    'first_name': first_name,
                    'last_name': last_name,
                    'has_form_data': bool(first_name or last_name)
                }
        return {'exists': False}
    except Exception as e:
        logger.error(f"❌ Sheets lookup: {str(e)}")
        return {'exists': False}

def log_phone_to_sheets(phone_number):
    """Log phone to sheets"""
    try:
        if not sheets_client or not GOOGLE_SHEET_ID:
            return False
        sheet = sheets_client.open_by_key(GOOGLE_SHEET_ID)
        worksheet = sheet.worksheet('Registrations')
        worksheet.append_row([phone_number])
        logger.info(f"✅ Logged: {phone_number}")
        return True
    except Exception as e:
        logger.error(f"❌ Log error: {str(e)}")
        return False

# ═══════════════════════════════════════════════════════════
# SHOPIFY FUNCTIONS
# ═══════════════════════════════════════════════════════════

def check_customer_in_shopify(phone_number):
    """Check customer in Shopify"""
    try:
        if not SHOPIFY_ACCESS_TOKEN:
            return {'exists': False}
        
        url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/customers/search.json"
        headers = {
            'X-Shopify-Access-Token': SHOPIFY_ACCESS_TOKEN,
            'Content-Type': 'application/json'
        }
        params = {'query': f'phone:{phone_number}'}
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            customers = response.json().get('customers', [])
            if customers:
                customer = customers[0]
                tags = [t.strip() for t in customer.get('tags', '').split(',')]
                customer_type = 'B2B' if any(t in ['B2B', 'Wholesale'] for t in tags) else 'Retail'
                
                return {
                    'exists': True,
                    'first_name': customer.get('first_name', ''),
                    'last_name': customer.get('last_name', ''),
                    'customer_type': customer_type
                }
        return {'exists': False}
    except Exception as e:
        logger.error(f"❌ Shopify: {str(e)}")
        return {'exists': False}

def detect_customer_status(phone_number):
    """Detect customer status"""
    try:
        shopify_result = check_customer_in_shopify(phone_number)
        
        if shopify_result['exists']:
            customer_type = shopify_result.get('customer_type', 'Retail')
            return {
                'status': 'returning_b2b' if customer_type == 'B2B' else 'returning_retail',
                'customer_type': customer_type,
                'first_name': shopify_result.get('first_name', 'Customer'),
                'last_name': shopify_result.get('last_name', '')
            }
        
        sheets_result = check_customer_in_sheets(phone_number)
        if sheets_result['exists']:
            return {
                'status': 'incomplete_registration',
                'first_name': sheets_result.get('first_name', ''),
                'last_name': sheets_result.get('last_name', '')
            }
        
        log_phone_to_sheets(phone_number)
        return {'status': 'new'}
    except Exception as e:
        logger.error(f"❌ Detection: {str(e)}")
        return {'status': 'new'}

# ═══════════════════════════════════════════════════════════
# SESSION MANAGEMENT
# ═══════════════════════════════════════════════════════════

user_sessions = {}
SESSION_TIMEOUT = timedelta(minutes=30)

def get_session(phone_number):
    """Get or create session"""
    if phone_number not in user_sessions:
        user_sessions[phone_number] = {
            'created_at': datetime.now(),
            'last_activity': datetime.now(),
            'state': 'new',
            'customer_type': 'Retail',
            'customer_name': 'Customer'
        }
    else:
        user_sessions[phone_number]['last_activity'] = datetime.now()
    return user_sessions[phone_number]

def update_session_customer_data(phone_number, customer_data):
    """Update session"""
    session = get_session(phone_number)
    session['customer_status'] = customer_data.get('status')
    session['customer_type'] = customer_data.get('customer_type', 'Retail')
    
    first_name = customer_data.get('first_name', 'Customer')
    last_name = customer_data.get('last_name', '')
    session['customer_name'] = f"{first_name} {last_name}" if last_name else first_name
    
    return session

def cleanup_old_sessions():
    """Cleanup expired sessions"""
    current_time = datetime.now()
    expired = [
        phone for phone, session in user_sessions.items()
        if current_time - session['last_activity'] > SESSION_TIMEOUT
    ]
    for phone in expired:
        del user_sessions[phone]

# ═══════════════════════════════════════════════════════════
# WHATSAPP - TEXT MESSAGE
# ═══════════════════════════════════════════════════════════

def send_whatsapp_text(to_number, message_text):
    """Send text message"""
    try:
        url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
        headers = {
            'Authorization': f'Bearer {WHATSAPP_TOKEN}',
            'Content-Type': 'application/json'
        }
        payload = {
            'messaging_product': 'whatsapp',
            'to': to_number,
            'type': 'text',
            'text': {'body': message_text}
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        logger.info(f"📤 Text: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        logger.error(f"❌ Text error: {str(e)}")
        return False

# ═══════════════════════════════════════════════════════════
# WHATSAPP - IMAGE MESSAGE
# ═══════════════════════════════════════════════════════════

def send_whatsapp_image(to_number, image_url, caption=""):
    """Send image"""
    try:
        url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
        headers = {
            'Authorization': f'Bearer {WHATSAPP_TOKEN}',
            'Content-Type': 'application/json'
        }
        payload = {
            'messaging_product': 'whatsapp',
            'to': to_number,
            'type': 'image',
            'image': {'link': image_url, 'caption': caption}
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        logger.info(f"📸 Image: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        logger.error(f"❌ Image error: {str(e)}")
        return False

# ═══════════════════════════════════════════════════════════
# WHATSAPP - BUTTONS
# ═══════════════════════════════════════════════════════════

def send_whatsapp_buttons(to_number, message_text, buttons):
    """Send buttons (max 3)"""
    try:
        if len(buttons) > 3:
            buttons = buttons[:3]
        
        url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
        headers = {
            'Authorization': f'Bearer {WHATSAPP_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        button_objects = [
            {'type': 'reply', 'reply': {'id': btn['id'], 'title': btn['title'][:20]}}
            for btn in buttons
        ]
        
        payload = {
            'messaging_product': 'whatsapp',
            'to': to_number,
            'type': 'interactive',
            'interactive': {
                'type': 'button',
                'body': {'text': message_text},
                'action': {'buttons': button_objects}
            }
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        logger.info(f"🔘 Buttons: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        logger.error(f"❌ Buttons error: {str(e)}")
        return False

# ═══════════════════════════════════════════════════════════
# WHATSAPP - CTA BUTTON
# ═══════════════════════════════════════════════════════════

def send_whatsapp_cta_button(to_number, message_text, button_text, url_link):
    """Send CTA button"""
    try:
        url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
        headers = {
            'Authorization': f'Bearer {WHATSAPP_TOKEN}',
            'Content-Type': 'application/json'
        }
        payload = {
            'messaging_product': 'whatsapp',
            'to': to_number,
            'type': 'interactive',
            'interactive': {
                'type': 'cta_url',
                'body': {'text': message_text},
                'action': {
                    'name': 'cta_url',
                    'parameters': {
                        'display_text': button_text[:20],
                        'url': url_link
                    }
                }
            }
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        logger.info(f"🔗 CTA: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        logger.error(f"❌ CTA error: {str(e)}")
        return False

# ═══════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════

def validate_phone_number(phone):
    """Validate phone"""
    if not phone:
        return False
    clean = ''.join(filter(str.isdigit, phone))
    return 10 <= len(clean) <= 15

def sanitize_input(text):
    """Sanitize input"""
    return text.strip()[:1000] if text else ""

def typing_delay(length):
    """Calculate typing delay"""
    return min(0.5 + (length * 0.01), 2.0)

last_messages = {}

def is_duplicate_message(phone, text):
    """Check duplicate"""
    key = f"{phone}:{text}"
    now = datetime.now()
    
    if key in last_messages:
        if (now - last_messages[key]).total_seconds() < 5:
            return True
    
    last_messages[key] = now
    return False

# ═══════════════════════════════════════════════════════════
# WEBHOOK VERIFICATION
# ═══════════════════════════════════════════════════════════

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    """Verify webhook"""
    try:
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            logger.info("✅ Webhook verified")
            return challenge, 200
        return 'Forbidden', 403
    except Exception as e:
        logger.error(f"❌ Verify error: {str(e)}")
        return 'Error', 500

# ═══════════════════════════════════════════════════════════
# WEBHOOK HANDLER
# ═══════════════════════════════════════════════════════════

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle messages"""
    try:
        cleanup_old_sessions()
        data = request.get_json()
        
        if not data or data.get('object') != 'whatsapp_business_account':
            return jsonify({'status': 'ok'}), 200
        
        messages = data.get('entry', [{}])[0].get('changes', [{}])[0].get('value', {}).get('messages', [])
        
        if not messages:
            return jsonify({'status': 'ok'}), 200
        
        message = messages[0]
        from_number = message.get('from')
        message_type = message.get('type')
        
        if not validate_phone_number(from_number):
            return jsonify({'status': 'ok'}), 200
        
        # Detect customer
        customer_data = detect_customer_status(from_number)
        session = update_session_customer_data(from_number, customer_data)
        
        logger.info(f"👤 Status: {customer_data['status']}")
        
        # Handle text
        if message_type == 'text':
            text = sanitize_input(message.get('text', {}).get('body', ''))
            
            if is_duplicate_message(from_number, text):
                return jsonify({'status': 'ok'}), 200
            
            # New customer
            if customer_data['status'] == 'new':
                if LOGO_IMAGE_URL:
                    send_whatsapp_image(from_number, LOGO_IMAGE_URL, "Welcome to\n\n*A Jewel Studio*")
                    time.sleep(1)
                
                join_url = f"{JOIN_US_URL}?wa={from_number}"
                send_whatsapp_cta_button(
                    from_number,
                    "✨ Welcome to *A Jewel Studio*!\n\nTap Join Us below to explore our exclusive collections.",
                    "Join Us",
                    join_url
                )
            
            # Incomplete registration
            elif customer_data['status'] == 'incomplete_registration':
                send_whatsapp_buttons(
                    from_number,
                    "👋 Hello!\n\n⚠️ I see you started registration but didn't complete it.\n\nWould you like to complete your registration?",
                    [
                        {'id': 'complete_reg', 'title': 'Complete Now'},
                        {'id': 'browse', 'title': 'Browse Catalog'},
                        {'id': 'help', 'title': 'Need Help'}
                    ]
                )
            
            # Returning customer
            else:
                send_whatsapp_buttons(
                    from_number,
                    f"👋 Welcome back, *{session['customer_name']}*!\n\nHow can I assist you today?",
                    [{'id': 'menu', 'title': 'Menu'}]
                )
        
        # Handle button click
        elif message_type == 'interactive':
            button_id = message.get('interactive', {}).get('button_reply', {}).get('id', '')
            logger.info(f"🔘 Button: {button_id}")
            send_whatsapp_text(from_number, f"✅ Button '{button_id}' received!\n\n_Phase 3 active_")
        
        # Handle image
        elif message_type == 'image':
            send_whatsapp_text(from_number, "📸 Image received! Processing in Phase 4...")
        
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        logger.error(f"❌ Webhook error: {str(e)}")
        return jsonify({'status': 'error'}), 500

# ═══════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════

@app.route('/', methods=['GET'])
@app.route('/health', methods=['GET'])
def health_check():
    """Health check"""
    return jsonify({
        'status': 'healthy',
        'service': 'A Jewel Studio WhatsApp Bot',
        'phase': 'Phase 3 - Messaging & UX',
        'features': 40,
        'timestamp': datetime.now().isoformat(),
        'active_sessions': len(user_sessions),
        'environment': {
            'whatsapp_token': '✅' if WHATSAPP_TOKEN else '❌',
            'shopify_token': '✅' if SHOPIFY_ACCESS_TOKEN else '❌',
            'google_sheets': '✅' if GOOGLE_SERVICE_ACCOUNT_KEY else '❌'
        }
    }), 200

# ═══════════════════════════════════════════════════════════
# SECURITY HEADERS
# ═══════════════════════════════════════════════════════════

@app.after_request
def add_security_headers(response):
    """Security headers"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

# ═══════════════════════════════════════════════════════════
# ERROR HANDLERS
# ═══════════════════════════════════════════════════════════

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal error'}), 500

# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    
    logger.info("=" * 60)
    logger.info("🚀 Phase 3 - Messaging & UX")
    logger.info("=" * 60)
    logger.info("✅ Total Features: 40")
    logger.info("   Phase 1: 15 ✅")
    logger.info("   Phase 2: 10 ✅")
    logger.info("   Phase 3: 15 ✅")
    logger.info("=" * 60)
    
    app.run(host='0.0.0.0', port=port, debug=False)
