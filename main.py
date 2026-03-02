import os
import json
import requests
from flask import Flask, request, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = Flask(__name__)

# Environment variables
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN')
WHATSAPP_PHONE_ID = os.getenv('WHATSAPP_PHONE_ID')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN')
GOOGLE_CREDENTIALS = json.loads(os.getenv('GOOGLE_CREDENTIALS'))
SPREADSHEET_ID = os.getenv('GOOGLE_SHEET_ID')
SHEET_NAME = 'Registrations'

# Google Sheets setup
credentials = service_account.Credentials.from_service_account_info(
    GOOGLE_CREDENTIALS,
    scopes=['https://www.googleapis.com/auth/spreadsheets']
)
sheets_service = build('sheets', 'v4', credentials=credentials)

# ✅ Check customer registration status
def check_customer_status(phone_number):
    try:
        range_name = f'{SHEET_NAME}!A:C'
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=range_name
        ).execute()
        
        rows = result.get('values', [])
        
        for i, row in enumerate(rows):
            if len(row) > 0 and row[0] == phone_number:
                first_name = row[1] if len(row) > 1 else ''
                last_name = row[2] if len(row) > 2 else ''
                has_form_data = bool(first_name or last_name)
                
                return {
                    'exists': True,
                    'row_number': i + 1,
                    'first_name': first_name,
                    'last_name': last_name,
                    'has_form_data': has_form_data
                }
        
        return {'exists': False}
    
    except Exception as e:
        print(f'Error checking customer: {e}')
        return {'exists': False}

# ✅ Log phone number to Google Sheet (Column A only)
def log_phone_number(phone_number):
    try:
        range_name = f'{SHEET_NAME}!A:A'
        values = [[phone_number]]
        body = {'values': values}
        
        sheets_service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=range_name,
            valueInputOption='RAW',
            body=body
        ).execute()
        
        print(f'✅ Logged new number: {phone_number}')
        return True
    
    except Exception as e:
        print(f'Error logging number: {e}')
        return False

# ✅ Send WhatsApp message
def send_whatsapp_message(to, message_text):
    try:
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
        print(f'Error sending message: {e}')
        return False

# ✅ Welcome back message (registered customer)
def send_welcome_back_message(to, first_name, last_name):
    message = f"""Welcome back, {first_name} {last_name}! 👋

How can I help you today?

1️⃣ View Catalog
2️⃣ Track Order
3️⃣ Contact Support

Reply with a number to continue."""
    
    send_whatsapp_message(to, message)

# ✅ Complete registration message (number logged, no form)
def send_complete_registration_message(to):
    message = """Hi! 👋

I see you messaged us before but didn't complete registration.

Would you like to:

1️⃣ Complete Registration
🔗 https://a-jewel-studio-3.myshopify.com/pages/join-us

2️⃣ Browse Catalog
3️⃣ Talk to Support

Reply with a number to continue."""
    
    send_whatsapp_message(to, message)

# ✅ New customer welcome
def send_new_customer_message(to):
    message = """Welcome to A.Jewel.Studio! 👋

You're a new customer!

Please complete registration:
🔗 https://a-jewel-studio-3.myshopify.com/pages/join-us

Or browse our catalog:
Reply "catalog" to see our latest collection! 💎"""
    
    send_whatsapp_message(to, message)

# Webhook verification
@app.route('/webhook', methods=['GET'])
def verify_webhook():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    if mode == 'subscribe' and token == VERIFY_TOKEN:
        print('✅ Webhook verified')
        return challenge, 200
    else:
        return 'Forbidden', 403

# ✅ Webhook handler - Main logic
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        
        if data.get('object') == 'whatsapp_business_account':
            entry = data.get('entry', [{}])[0]
            changes = entry.get('changes', [{}])[0]
            value = changes.get('value', {})
            messages = value.get('messages', [])
            
            if messages:
                message = messages[0]
                from_number = message.get('from')
                message_text = message.get('text', {}).get('body', '').lower()
                
                print(f'📩 Message from {from_number}: {message_text}')
                
                # Check customer status
                customer_status = check_customer_status(from_number)
                
                # Log number if new
                if not customer_status['exists']:
                    log_phone_number(from_number)
                
                # Route based on customer status
                if customer_status['exists'] and customer_status['has_form_data']:
                    # ✅ Registered customer with complete data
                    send_welcome_back_message(
                        from_number,
                        customer_status['first_name'],
                        customer_status['last_name']
                    )
                
                elif customer_status['exists'] and not customer_status['has_form_data']:
                    # ⚠️ Number logged but form not completed
                    send_complete_registration_message(from_number)
                
                else:
                    # 🆕 New customer
                    send_new_customer_message(from_number)
        
        return jsonify({'status': 'ok'}), 200
    
    except Exception as e:
        print(f'Webhook error: {e}')
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Health check
@app.route('/', methods=['GET'])
def health_check():
    return jsonify({'status': 'AJewel WhatsApp Bot is running'}), 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
