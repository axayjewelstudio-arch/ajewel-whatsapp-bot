import os
import json
import requests
from flask import Flask, request, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = Flask(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# Environment Variables
# ══════════════════════════════════════════════════════════════════════════════
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN')
WHATSAPP_PHONE_ID = os.getenv('WHATSAPP_PHONE_ID')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN')
GOOGLE_SHEET_ID = os.getenv('GOOGLE_SHEET_ID')
SHEET_NAME = 'Registrations'

# Google Credentials - Safe loading with error handling
try:
    GOOGLE_CREDENTIALS = json.loads(os.getenv('GOOGLE_CREDENTIALS', '{}'))
    if not GOOGLE_CREDENTIALS:
        print('⚠️ WARNING: GOOGLE_CREDENTIALS not set!')
except json.JSONDecodeError as e:
    print(f'❌ Error parsing GOOGLE_CREDENTIALS: {e}')
    GOOGLE_CREDENTIALS = {}

# ══════════════════════════════════════════════════════════════════════════════
# Google Sheets Setup
# ══════════════════════════════════════════════════════════════════════════════
sheets_service = None

try:
    if GOOGLE_CREDENTIALS:
        credentials = service_account.Credentials.from_service_account_info(
            GOOGLE_CREDENTIALS,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        sheets_service = build('sheets', 'v4', credentials=credentials)
        print('✅ Google Sheets service initialized')
    else:
        print('⚠️ Google Sheets service not initialized - missing credentials')
except Exception as e:
    print(f'❌ Google Sheets initialization error: {e}')

# ══════════════════════════════════════════════════════════════════════════════
# Helper Functions
# ══════════════════════════════════════════════════════════════════════════════

def check_customer_status(phone_number):
    """Check if customer exists in Google Sheet and has form data"""
    try:
        if not sheets_service or not GOOGLE_SHEET_ID:
            print('⚠️ Sheets service or Sheet ID not available')
            return {'exists': False}
        
        range_name = f'{SHEET_NAME}!A:C'
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=GOOGLE_SHEET_ID,
            range=range_name
        ).execute()
        
        rows = result.get('values', [])
        
        # Skip header row (start from index 1)
        for i, row in enumerate(rows[1:], start=2):
            if len(row) > 0 and row[0].strip() == phone_number.strip():
                first_name = row[1].strip() if len(row) > 1 else ''
                last_name = row[2].strip() if len(row) > 2 else ''
                has_form_data = bool(first_name or last_name)
                
                print(f'✅ Found customer: {first_name} {last_name}')
                
                return {
                    'exists': True,
                    'row_number': i,
                    'first_name': first_name,
                    'last_name': last_name,
                    'has_form_data': has_form_data
                }
        
        print(f'❌ Customer not found: {phone_number}')
        return {'exists': False}
    
    except Exception as e:
        print(f'❌ Error checking customer: {e}')
        return {'exists': False}

def log_phone_number(phone_number):
    """Log phone number to Google Sheet Column A (no duplicates)"""
    try:
        if not sheets_service or not GOOGLE_SHEET_ID:
            print('⚠️ Sheets service or Sheet ID not available')
            return False
        
        # Check if already exists
        customer = check_customer_status(phone_number)
        if customer['exists']:
            print(f'ℹ️ Number already exists: {phone_number}')
            return False
        
        range_name = f'{SHEET_NAME}!A:A'
        values = [[phone_number]]
        body = {'values': values}
        
        sheets_service.spreadsheets().values().append(
            spreadsheetId=GOOGLE_SHEET_ID,
            range=range_name,
            valueInputOption='RAW',
            body=body
        ).execute()
        
        print(f'✅ Logged new number: {phone_number}')
        return True
    
    except Exception as e:
        print(f'❌ Error logging number: {e}')
        return False


def send_whatsapp_message(to, message_text):
    """Send text message via WhatsApp"""
    try:
        if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
            print('⚠️ WhatsApp credentials not set')
            return False
        
        url = f'https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages'
        headers = {
            'Authorization': f'Bearer {WHATSAPP_TOKEN}',
            'Content-Type': 'application/json'
        }
        data = {
            'messaging_product': 'whatsapp',
            'to': to,
            'type': 'text',
            'text': {'body': message_text}
        }
        
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        print(f'✅ Message sent to {to}')
        return True
    
    except Exception as e:
        print(f'❌ Error sending message: {e}')
        return False


def send_welcome_back_message(to, first_name, last_name):
    """Send welcome back message to registered customer"""
    message = f"""Hello {first_name} {last_name}! 👋

Welcome back to A.Jewel.Studio.

How may I assist you today?

1️⃣ View Our Collection
2️⃣ Track Your Order
3️⃣ Speak with Support

Please reply with a number."""
    
    send_whatsapp_message(to, message)


def send_complete_registration_message(to):
    """Send message to customer who hasn't completed registration"""
    message = """Hi! 👋

I see you messaged us before but didn't complete registration.

Would you like to:

1️⃣ Complete Registration
🔗 https://a-jewel-studio-3.myshopify.com/pages/join-us

2️⃣ Browse Catalog
3️⃣ Talk to Support

Reply with a number to continue."""
    
    send_whatsapp_message(to, message)


def send_new_customer_message(to):
    """Send welcome message to new customer"""
    message = """Welcome to A.Jewel.Studio! 👋

You're a new customer!

Please complete registration:
🔗 https://a-jewel-studio-3.myshopify.com/pages/join-us

Or browse our catalog:
Reply "catalog" to see our latest collection! 💎"""
    
    send_whatsapp_message(to, message)


# ══════════════════════════════════════════════════════════════════════════════
# Routes
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'running',
        'app': 'AJewel WhatsApp Bot',
        'sheets_connected': sheets_service is not None,
        'whatsapp_configured': bool(WHATSAPP_TOKEN and WHATSAPP_PHONE_ID)
    }), 200


@app.route('/webhook', methods=['GET'])
def verify_webhook():
    """Webhook verification for WhatsApp"""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    if mode == 'subscribe' and token == VERIFY_TOKEN:
        print('✅ Webhook verified')
        return challenge, 200
    else:
        print('❌ Webhook verification failed')
        return 'Forbidden', 403


@app.route('/webhook', methods=['POST'])
def webhook():
    """Main webhook handler for incoming WhatsApp messages"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'status': 'no data'}), 200
        
        if data.get('object') == 'whatsapp_business_account':
            entry = data.get('entry', [{}])[0]
            changes = entry.get('changes', [{}])[0]
            value = changes.get('value', {})
            messages = value.get('messages', [])
            
            if messages:
                message = messages[0]
                from_number = message.get('from')
                
                # Only process text messages
                if message.get('type') != 'text':
                    return jsonify({'status': 'ok'}), 200
                
                message_text = message.get('text', {}).get('body', '').lower()
                
                print('=' * 60)
                print(f'📩 Message from {from_number}: {message_text}')
                
                # Check customer status
                customer_status = check_customer_status(from_number)
                
                # Log number if new
                if not customer_status['exists']:
                    log_phone_number(from_number)
                
                # Route based on customer status
                if customer_status['exists'] and customer_status['has_form_data']:
                    # ✅ Registered customer with complete data
                    print(f'✅ Registered customer: {customer_status["first_name"]} {customer_status["last_name"]}')
                    send_welcome_back_message(
                        from_number,
                        customer_status['first_name'],
                        customer_status['last_name']
                    )
                
                elif customer_status['exists'] and not customer_status['has_form_data']:
                    # ⚠️ Number logged but form not completed
                    print('⚠️ Incomplete registration')
                    send_complete_registration_message(from_number)
                
                else:
                    # 🆕 New customer
                    print('🆕 New customer')
                    send_new_customer_message(from_number)
                
                print('=' * 60)
        
        return jsonify({'status': 'ok'}), 200
    
    except Exception as e:
        print(f'❌ Webhook error: {e}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════════
# Run App
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    print(f'🚀 Starting AJewel WhatsApp Bot on port {port}...')
    app.run(host='0.0.0.0', port=port, debug=False)
