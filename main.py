# -*- coding: utf-8 -*-
"""
A Jewel Studio WhatsApp Bot - Phase 2: Customer Management
Phase 1 (15) + Phase 2 (10) = 25 Total Features
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

# Shopify
SHOPIFY_STORE = os.getenv('SHOPIFY_STORE', 'a-jewel-studio-3.myshopify.com')
SHOPIFY_ACCESS_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN')

# Google Sheets
GOOGLE_SHEET_ID = os.getenv('GOOGLE_SHEET_ID')
GOOGLE_SERVICE_ACCOUNT_KEY = os.getenv('GOOGLE_SERVICE_ACCOUNT_KEY')

# Validation
if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
    logger.error("❌ Missing WhatsApp credentials!")

# ═══════════════════════════════════════════════════════════
# GOOGLE SHEETS SETUP
# ═══════════════════════════════════════════════════════════

def get_google_sheets_client():
    """Initialize Google Sheets client"""
    try:
        if not GOOGLE_SERVICE_ACCOUNT_KEY:
            logger.warning("⚠️ Google Sheets credentials not configured")
            return None
        
        credentials_dict = json.loads(GOOGLE_SERVICE_ACCOUNT_KEY)
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
        client = gspread.authorize(credentials)
        
        logger.info("✅ Google Sheets client initialized")
        return client
    except Exception as e:
        logger.error(f"❌ Google Sheets setup error: {str(e)}")
        return None

# Initialize client
sheets_client = get_google_sheets_client()

# ═══════════════════════════════════════════════════════════
# GOOGLE SHEETS - CUSTOMER LOOKUP
# ═══════════════════════════════════════════════════════════

def check_customer_in_sheets(phone_number):
    """Check if customer exists in Google Sheets"""
    try:
        if not sheets_client or not GOOGLE_SHEET_ID:
            logger.warning("⚠️ Google Sheets not configured")
            return {'exists': False, 'source': 'sheets_not_configured'}
        
        sheet = sheets_client.open_by_key(GOOGLE_SHEET_ID)
        worksheet = sheet.worksheet('Registrations')
        
        # Get all values from column A (phone numbers)
        phone_column = worksheet.col_values(1)
        
        # Search for phone number
        for idx, cell_value in enumerate(phone_column, start=1):
            if cell_value == phone_number:
                # Get row data (columns A to C for name)
                row_data = worksheet.row_values(idx)
                
                first_name = row_data[1] if len(row_data) > 1 else ''
                last_name = row_data[2] if len(row_data) > 2 else ''
                
                has_data = bool(first_name or last_name)
                
                logger.info(f"✅ Customer found in sheets: Row {idx}, Has data: {has_data}")
                
                return {
                    'exists': True,
                    'row': idx,
                    'first_name': first_name,
                    'last_name': last_name,
                    'has_form_data': has_data,
                    'source': 'google_sheets'
                }
        
        logger.info(f"ℹ️ Customer not found in sheets: {phone_number}")
        return {'exists': False, 'source': 'google_sheets'}
        
    except Exception as e:
        logger.error(f"❌ Google Sheets lookup error: {str(e)}")
        return {'exists': False, 'source': 'sheets_error', 'error': str(e)}

def log_phone_to_sheets(phone_number):
    """Log new phone number to Google Sheets (Column A only)"""
    try:
        if not sheets_client or not GOOGLE_SHEET_ID:
            logger.warning("⚠️ Google Sheets not configured - cannot log")
            return False
        
        sheet = sheets_client.open_by_key(GOOGLE_SHEET_ID)
        worksheet = sheet.worksheet('Registrations')
        
        # Append phone number to column A
        worksheet.append_row([phone_number])
        
        logger.info(f"✅ Logged phone number to sheets: {phone_number}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error logging to sheets: {str(e)}")
        return False

# ═══════════════════════════════════════════════════════════
# SHOPIFY - CUSTOMER LOOKUP
# ═══════════════════════════════════════════════════════════

def check_customer_in_shopify(phone_number):
    """Check if customer exists in Shopify"""
    try:
        if not SHOPIFY_ACCESS_TOKEN:
            logger.warning("⚠️ Shopify credentials not configured")
            return {'exists': False, 'source': 'shopify_not_configured'}
        
        url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/customers/search.json"
        headers = {
            'X-Shopify-Access-Token': SHOPIFY_ACCESS_TOKEN,
            'Content-Type': 'application/json'
        }
        params = {'query': f'phone:{phone_number}'}
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            customers = data.get('customers', [])
            
            if customers:
                customer = customers[0]
                tags = customer.get('tags', '').split(',')
                tags = [tag.strip() for tag in tags]
                
                # Detect customer type from tags
                customer_type = 'Retail'
                if any(tag in ['B2B', 'Wholesale', 'Partner'] for tag in tags):
                    customer_type = 'B2B'
                
                logger.info(f"✅ Customer found in Shopify: {customer.get('first_name')} ({customer_type})")
                
                return {
                    'exists': True,
                    'first_name': customer.get('first_name', ''),
                    'last_name': customer.get('last_name', ''),
                    'email': customer.get('email', ''),
                    'customer_type': customer_type,
                    'tags': tags,
                    'source': 'shopify'
                }
            else:
                logger.info(f"ℹ️ Customer not found in Shopify: {phone_number}")
                return {'exists': False, 'source': 'shopify'}
        else:
            logger.error(f"❌ Shopify API error: {response.status_code}")
            return {'exists': False, 'source': 'shopify_error', 'error': response.text}
            
    except Exception as e:
        logger.error(f"❌ Shopify lookup error: {str(e)}")
        return {'exists': False, 'source': 'shopify_error', 'error': str(e)}

# ═══════════════════════════════════════════════════════════
# CUSTOMER DETECTION & RECOGNITION
# ═══════════════════════════════════════════════════════════

def detect_customer_status(phone_number):
    """
    Comprehensive customer detection
    Returns: new, incomplete_registration, returning_retail, returning_b2b
    """
    try:
        # Check Google Sheets first
        sheets_result = check_customer_in_sheets(phone_number)
        
        # Check Shopify
        shopify_result = check_customer_in_shopify(phone_number)
        
        # Decision logic
        if shopify_result['exists']:
            # Customer exists in Shopify - returning customer
            customer_type = shopify_result.get('customer_type', 'Retail')
            
            return {
                'status': 'returning_b2b' if customer_type == 'B2B' else 'returning_retail',
                'customer_type': customer_type,
                'first_name': shopify_result.get('first_name', 'Customer'),
                'last_name': shopify_result.get('last_name', ''),
                'email': shopify_result.get('email', ''),
                'tags': shopify_result.get('tags', []),
                'source': 'shopify'
            }
        
        elif sheets_result['exists'] and sheets_result['has_form_data']:
            # In sheets with data but not in Shopify yet
            return {
                'status': 'incomplete_registration',
                'first_name': sheets_result.get('first_name', ''),
                'last_name': sheets_result.get('last_name', ''),
                'source': 'google_sheets'
            }
        
        elif sheets_result['exists'] and not sheets_result['has_form_data']:
            # In sheets but no form data
            return {
                'status': 'incomplete_registration',
                'first_name': '',
                'last_name': '',
                'source': 'google_sheets'
            }
        
        else:
            # New customer - log to sheets
            log_phone_to_sheets(phone_number)
            
            return {
                'status': 'new',
                'source': 'new_customer'
            }
            
    except Exception as e:
        logger.error(f"❌ Customer detection error: {str(e)}")
        return {
            'status': 'new',
            'source': 'error',
            'error': str(e)
        }

def extract_customer_name(customer_data):
    """Extract full customer name"""
    first_name = customer_data.get('first_name', 'Customer')
    last_name = customer_data.get('last_name', '')
    
    if last_name:
        return f"{first_name} {last_name}"
    return first_name

# ═══════════════════════════════════════════════════════════
# SESSION STORAGE (Enhanced)
# ═══════════════════════════════════════════════════════════

user_sessions = {}
SESSION_TIMEOUT = timedelta(minutes=30)

def get_session(phone_number):
    """Get or create user session with customer data"""
    if phone_number not in user_sessions:
        user_sessions[phone_number] = {
            'created_at': datetime.now(),
            'last_activity': datetime.now(),
            'state': 'new',
            'customer_status': None,
            'customer_type': 'Retail',
            'customer_name': 'Customer',
            'data': {}
        }
    else:
        user_sessions[phone_number]['last_activity'] = datetime.now()
    
    return user_sessions[phone_number]

def update_session_customer_data(phone_number, customer_data):
    """Update session with customer information"""
    session = get_session(phone_number)
    session['customer_status'] = customer_data.get('status')
    session['customer_type'] = customer_data.get('customer_type', 'Retail')
    session['customer_name'] = extract_customer_name(customer_data)
    session['state'] = customer_data.get('status', 'new')
    return session

def cleanup_old_sessions():
    """Remove sessions older than timeout"""
    current_time = datetime.now()
    expired = [
        phone for phone, session in user_sessions.items()
        if current_time - session['last_activity'] > SESSION_TIMEOUT
    ]
    for phone in expired:
        del user_sessions[phone]
        logger.info(f"🗑️ Cleaned up expired session: {phone}")

# ═══════════════════════════════════════════════════════════
# INPUT VALIDATION
# ═══════════════════════════════════════════════════════════

def validate_phone_number(phone):
    """Validate phone number format"""
    if not phone:
        return False
    clean_phone = ''.join(filter(str.isdigit, phone))
    return 10 <= len(clean_phone) <= 15

def sanitize_input(text):
    """Sanitize user input"""
    if not text:
        return ""
    return text.strip()[:1000]

# ═══════════════════════════════════════════════════════════
# WHATSAPP API - SEND TEXT MESSAGE
# ═══════════════════════════════════════════════════════════

def send_whatsapp_text(to_number, message_text):
    """Send basic text message via WhatsApp"""
    try:
        url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
        
        headers = {
            'Authorization': f'Bearer {WHATSAPP_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': to_number,
            'type': 'text',
            'text': {
                'preview_url': False,
                'body': message_text
            }
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        logger.info(f"📤 Message sent to {to_number}: {response.status_code}")
        
        if response.status_code == 200:
            logger.info(f"✅ Message delivered successfully")
            return True
        else:
            logger.error(f"❌ Message failed: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error sending message: {str(e)}")
        return False

# ═══════════════════════════════════════════════════════════
# MESSAGE TYPE LOGGING
# ═══════════════════════════════════════════════════════════

def log_message_type(phone_number, message_type, content):
    """Log incoming message types"""
    logger.info(f"📨 Message Type: {message_type}")
    logger.info(f"👤 From: {phone_number}")
    logger.info(f"📝 Content: {content[:100]}...")

# ═══════════════════════════════════════════════════════════
# ERROR HANDLING
# ═══════════════════════════════════════════════════════════

def handle_error(error, context=""):
    """Centralized error handling"""
    error_msg = f"❌ Error in {context}: {str(error)}"
    logger.error(error_msg)
    return {
        'status': 'error',
        'message': str(error),
        'context': context,
        'timestamp': datetime.now().isoformat()
    }

# ═══════════════════════════════════════════════════════════
# WEBHOOK VERIFICATION (GET)
# ═══════════════════════════════════════════════════════════

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    """Verify webhook with WhatsApp"""
    try:
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        logger.info(f"🔐 Webhook verification attempt")
        
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            logger.info("✅ Webhook verified successfully!")
            return challenge, 200
        else:
            logger.warning("❌ Webhook verification failed!")
            return 'Forbidden', 403
            
    except Exception as e:
        logger.error(f"❌ Webhook verification error: {str(e)}")
        return 'Error', 500

# ═══════════════════════════════════════════════════════════
# WEBHOOK HANDLER (POST) - Enhanced with Customer Detection
# ═══════════════════════════════════════════════════════════

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming WhatsApp messages with customer detection"""
    try:
        cleanup_old_sessions()
        
        data = request.get_json()
        
        if not data:
            return jsonify({'status': 'ok'}), 200
        
        logger.info(f"📥 Webhook received")
        
        if data.get('object') != 'whatsapp_business_account':
            return jsonify({'status': 'ok'}), 200
        
        entry = data.get('entry', [{}])[0]
        changes = entry.get('changes', [{}])[0]
        value = changes.get('value', {})
        messages = value.get('messages', [])
        
        if not messages:
            return jsonify({'status': 'ok'}), 200
        
        message = messages[0]
        from_number = message.get('from')
        message_type = message.get('type')
        
        if not validate_phone_number(from_number):
            logger.warning(f"⚠️ Invalid phone number: {from_number}")
            return jsonify({'status': 'ok'}), 200
        
        # ═══════════════════════════════════════════════════════════
        # CUSTOMER DETECTION (NEW IN PHASE 2)
        # ═══════════════════════════════════════════════════════════
        
        logger.info(f"🔍 Detecting customer status for: {from_number}")
        customer_data = detect_customer_status(from_number)
        
        # Update session with customer data
        session = update_session_customer_data(from_number, customer_data)
        
        logger.info(f"👤 Customer Status: {customer_data['status']}")
        logger.info(f"📊 Customer Type: {session['customer_type']}")
        logger.info(f"👋 Customer Name: {session['customer_name']}")
        
        # Handle message based on type
        if message_type == 'text':
            message_text = message.get('text', {}).get('body', '')
            sanitized_text = sanitize_input(message_text)
            
            log_message_type(from_number, 'text', sanitized_text)
            
            # Response based on customer status
            if customer_data['status'] == 'new':
                response = f"👋 Welcome to *A Jewel Studio*!\n\n✨ You're a new customer.\n\n_Phase 2 Testing - Customer Status: NEW_\n_Session ID: {session['created_at'].strftime('%H%M%S')}_"
            
            elif customer_data['status'] == 'incomplete_registration':
                response = f"👋 Hello!\n\n⚠️ I see you started registration but didn't complete it.\n\n_Phase 2 Testing - Status: INCOMPLETE_\n_Name: {session['customer_name']}_"
            
            elif customer_data['status'] == 'returning_retail':
                response = f"👋 Welcome back, *{session['customer_name']}*!\n\n💎 Retail Customer\n\n_Phase 2 Testing - Status: RETURNING RETAIL_\n_Type: {session['customer_type']}_"
            
            elif customer_data['status'] == 'returning_b2b':
                response = f"👋 Welcome back, *{session['customer_name']}*!\n\n🏢 B2B Partner\n\n_Phase 2 Testing - Status: RETURNING B2B_\n_Type: {session['customer_type']}_"
            
            else:
                response = f"✅ Message received!\n\n*You said:* {sanitized_text}\n\n_Phase 2 - Customer Management Active_"
            
            send_whatsapp_text(from_number, response)
        
        elif message_type == 'image':
            log_message_type(from_number, 'image', 'Image received')
            send_whatsapp_text(from_number, f"📸 Image received, {session['customer_name']}! (Phase 2 - Processing pending)")
        
        else:
            log_message_type(from_number, message_type, 'Other type')
            send_whatsapp_text(from_number, f"Message type '{message_type}' received (Phase 2)")
        
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        error_data = handle_error(e, "webhook_handler")
        logger.error(f"Full error: {error_data}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ═══════════════════════════════════════════════════════════
# HEALTH CHECK ENDPOINT
# ═══════════════════════════════════════════════════════════

@app.route('/', methods=['GET'])
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        status = {
            'status': 'healthy',
            'service': 'A Jewel Studio WhatsApp Bot',
            'phase': 'Phase 2 - Customer Management',
            'features': 25,
            'timestamp': datetime.now().isoformat(),
            'active_sessions': len(user_sessions),
            'environment': {
                'whatsapp_token': '✅ Set' if WHATSAPP_TOKEN else '❌ Missing',
                'whatsapp_phone_id': '✅ Set' if WHATSAPP_PHONE_ID else '❌ Missing',
                'shopify_token': '✅ Set' if SHOPIFY_ACCESS_TOKEN else '❌ Missing',
                'google_sheets': '✅ Set' if GOOGLE_SERVICE_ACCOUNT_KEY else '❌ Missing'
            }
        }
        
        logger.info(f"💚 Health check: {status['status']}")
        return jsonify(status), 200
        
    except Exception as e:
        error_data = handle_error(e, "health_check")
        return jsonify(error_data), 500

# ═══════════════════════════════════════════════════════════
# SECURITY HEADERS
# ═══════════════════════════════════════════════════════════

@app.after_request
def add_security_headers(response):
    """Add security headers"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000'
    return response

# ═══════════════════════════════════════════════════════════
# ERROR HANDLERS
# ═══════════════════════════════════════════════════════════

@app.errorhandler(404)
def not_found(error):
    """Handle 404"""
    return jsonify({'status': 'error', 'message': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500"""
    return jsonify({'status': 'error', 'message': 'Internal error'}), 500

# ═══════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════

if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    
    logger.info("=" * 60)
    logger.info("🚀 A Jewel Studio WhatsApp Bot - Phase 2")
    logger.info("=" * 60)
    logger.info(f"📱 WhatsApp: {'✅' if WHATSAPP_TOKEN else '❌'}")
    logger.info(f"🛍️ Shopify: {'✅' if SHOPIFY_ACCESS_TOKEN else '❌'}")
    logger.info(f"📊 Google Sheets: {'✅' if GOOGLE_SERVICE_ACCOUNT_KEY else '❌'}")
    logger.info("=" * 60)
    logger.info("✅ Phase 1 Features: 15/15")
    logger.info("✅ Phase 2 Features: 10/10")
    logger.info("   - Google Sheets Integration ✅")
    logger.info("   - Shopify Customer Lookup ✅")
    logger.info("   - New Customer Detection ✅")
    logger.info("   - Returning Customer Recognition ✅")
    logger.info("   - Incomplete Registration Detection ✅")
    logger.info("   - Customer Type Detection (B2B/Retail) ✅")
    logger.info("   - B2B Tag Detection ✅")
    logger.info("   - Customer Name Extraction ✅")
    logger.info("   - Enhanced Session Management ✅")
    logger.info("   - Session State Tracking ✅")
    logger.info("=" * 60)
    logger.info("📊 TOTAL: 25 Features Active")
    logger.info("=" * 60)
    
    app.run(host='0.0.0.0', port=port, debug=False)
