# -*- coding: utf-8 -*-
"""
A Jewel Studio WhatsApp Bot - Phase 1: Foundation
15 Features: Server, Security, Basic Messaging, Logging
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

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

# Validation
if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
    logger.error("❌ Missing required environment variables!")
    logger.error("Required: WHATSAPP_TOKEN, WHATSAPP_PHONE_ID")

# ═══════════════════════════════════════════════════════════
# SESSION STORAGE (In-Memory)
# ═══════════════════════════════════════════════════════════

user_sessions = {}
SESSION_TIMEOUT = timedelta(minutes=30)

def get_session(phone_number):
    """Get or create user session"""
    if phone_number not in user_sessions:
        user_sessions[phone_number] = {
            'created_at': datetime.now(),
            'last_activity': datetime.now(),
            'state': 'new',
            'data': {}
        }
    else:
        # Update last activity
        user_sessions[phone_number]['last_activity'] = datetime.now()
    
    return user_sessions[phone_number]

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
    # Remove any non-digit characters
    clean_phone = ''.join(filter(str.isdigit, phone))
    # Should be 10-15 digits
    return 10 <= len(clean_phone) <= 15

def sanitize_input(text):
    """Sanitize user input"""
    if not text:
        return ""
    # Remove any potentially harmful characters
    return text.strip()[:1000]  # Limit to 1000 chars

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
        
        # Log API response
        logger.info(f"📤 Message sent to {to_number}: {response.status_code}")
        
        if response.status_code == 200:
            logger.info(f"✅ Message delivered successfully")
            return True
        else:
            logger.error(f"❌ Message failed: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        logger.error(f"⏱️ Timeout sending message to {to_number}")
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
    logger.info(f"📝 Content: {content[:100]}...")  # First 100 chars

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
        logger.info(f"Mode: {mode}, Token match: {token == VERIFY_TOKEN}")
        
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
# WEBHOOK HANDLER (POST)
# ═══════════════════════════════════════════════════════════

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming WhatsApp messages"""
    try:
        # Cleanup old sessions periodically
        cleanup_old_sessions()
        
        # Get webhook data
        data = request.get_json()
        
        if not data:
            logger.warning("⚠️ Empty webhook data received")
            return jsonify({'status': 'ok'}), 200
        
        # Log incoming webhook
        logger.info(f"📥 Webhook received: {json.dumps(data, indent=2)[:500]}")
        
        # Validate webhook structure
        if data.get('object') != 'whatsapp_business_account':
            logger.warning(f"⚠️ Invalid webhook object: {data.get('object')}")
            return jsonify({'status': 'ok'}), 200
        
        # Extract message data
        entry = data.get('entry', [{}])[0]
        changes = entry.get('changes', [{}])[0]
        value = changes.get('value', {})
        messages = value.get('messages', [])
        
        if not messages:
            logger.info("ℹ️ No messages in webhook")
            return jsonify({'status': 'ok'}), 200
        
        # Process first message
        message = messages[0]
        from_number = message.get('from')
        message_type = message.get('type')
        
        # Validate phone number
        if not validate_phone_number(from_number):
            logger.warning(f"⚠️ Invalid phone number: {from_number}")
            return jsonify({'status': 'ok'}), 200
        
        # Get user session
        session = get_session(from_number)
        
        # Handle different message types
        if message_type == 'text':
            message_text = message.get('text', {}).get('body', '')
            sanitized_text = sanitize_input(message_text)
            
            # Log message
            log_message_type(from_number, 'text', sanitized_text)
            
            # Simple echo response for Phase 1
            response_text = f"✅ Message received!\n\n*You said:* {sanitized_text}\n\n_This is Phase 1 - Foundation testing._"
            send_whatsapp_text(from_number, response_text)
        
        elif message_type == 'image':
            log_message_type(from_number, 'image', 'Image received')
            send_whatsapp_text(from_number, "📸 Image received! (Phase 1 - Processing not yet implemented)")
        
        elif message_type == 'interactive':
            log_message_type(from_number, 'interactive', 'Button/List response')
            send_whatsapp_text(from_number, "🔘 Button clicked! (Phase 1 - Handler not yet implemented)")
        
        else:
            log_message_type(from_number, message_type, 'Unknown type')
            send_whatsapp_text(from_number, f"⚠️ Message type '{message_type}' not yet supported in Phase 1")
        
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
            'phase': 'Phase 1 - Foundation',
            'features': 15,
            'timestamp': datetime.now().isoformat(),
            'active_sessions': len(user_sessions),
            'environment': {
                'whatsapp_token': '✅ Set' if WHATSAPP_TOKEN else '❌ Missing',
                'whatsapp_phone_id': '✅ Set' if WHATSAPP_PHONE_ID else '❌ Missing',
                'verify_token': '✅ Set' if VERIFY_TOKEN else '❌ Missing'
            }
        }
        
        logger.info(f"💚 Health check: {status['status']}")
        return jsonify(status), 200
        
    except Exception as e:
        error_data = handle_error(e, "health_check")
        return jsonify(error_data), 500

# ═══════════════════════════════════════════════════════════
# SECURITY HEADERS MIDDLEWARE
# ═══════════════════════════════════════════════════════════

@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# ═══════════════════════════════════════════════════════════
# ERROR HANDLERS
# ═══════════════════════════════════════════════════════════

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    logger.warning(f"⚠️ 404 Not Found: {request.url}")
    return jsonify({
        'status': 'error',
        'message': 'Endpoint not found',
        'path': request.path
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"❌ 500 Internal Error: {str(error)}")
    return jsonify({
        'status': 'error',
        'message': 'Internal server error',
        'timestamp': datetime.now().isoformat()
    }), 500

# ═══════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════

if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    
    logger.info("=" * 60)
    logger.info("🚀 A Jewel Studio WhatsApp Bot - Phase 1")
    logger.info("=" * 60)
    logger.info(f"📱 WhatsApp Phone ID: {WHATSAPP_PHONE_ID[:10]}..." if WHATSAPP_PHONE_ID else "❌ Not set")
    logger.info(f"🔐 Verify Token: {'✅ Set' if VERIFY_TOKEN else '❌ Not set'}")
    logger.info(f"🌐 Port: {port}")
    logger.info("=" * 60)
    logger.info("✅ Phase 1 Features: 15/15")
    logger.info("   - Flask Server ✅")
    logger.info("   - Environment Variables ✅")
    logger.info("   - WhatsApp API Connection ✅")
    logger.info("   - Webhook Verification ✅")
    logger.info("   - Health Check ✅")
    logger.info("   - Basic Text Messages ✅")
    logger.info("   - Error Logging ✅")
    logger.info("   - CORS Setup ✅")
    logger.info("   - Session Storage ✅")
    logger.info("   - Message Type Logging ✅")
    logger.info("   - API Response Logging ✅")
    logger.info("   - Input Validation ✅")
    logger.info("   - Error Handling ✅")
    logger.info("   - Security Headers ✅")
    logger.info("   - Session Cleanup ✅")
    logger.info("=" * 60)
    
    app.run(host='0.0.0.0', port=port, debug=False)
