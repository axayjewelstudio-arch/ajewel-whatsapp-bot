# AJewelBot v2 - Simple Version (Only WhatsApp to Sheet)
import os
import json
from flask import Flask, request, jsonify
import requests
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

load_dotenv()
app = Flask(__name__)

# Environment variables
SHOPIFY_STORE = os.getenv('SHOPIFY_STORE')
SHOPIFY_ACCESS_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN')
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN')
WHATSAPP_PHONE_ID = os.getenv('WHATSAPP_PHONE_ID')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN')
GOOGLE_CREDENTIALS = os.getenv('GOOGLE_CREDENTIALS')

SHEET_ID = "1w-4Zi65AqsQZFJIr1GLrDrW9BJNez8Wtr-dTL8oBLbs"

def get_google_sheet():
    """Connect to Google Sheet"""
    try:
        creds_dict = json.loads(GOOGLE_CREDENTIALS)
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).sheet1
        return sheet
    except Exception as e:
        print(f"❌ Google Sheets Error: {str(e)}")
        return None

def check_customer_exists(phone_number):
    """Check customer in Shopify"""
    url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/graphql.json"
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
        "Content-Type": "application/json"
    }
    
    if not phone_number.startswith('+'):
        phone_number = f"+{phone_number}"
    
    query = """
    query getCustomer($query: String!) {
      customers(first: 1, query: $query) {
        edges {
          node {
            id
            firstName
            lastName
            phone
            email
          }
        }
      }
    }
    """
    
    variables = {"query": f"phone:{phone_number}"}
    
    try:
        response = requests.post(url, json={"query": query, "variables": variables}, headers=headers)
        data = response.json()
        
        if data.get('data', {}).get('customers', {}).get('edges'):
            customer = data['data']['customers']['edges'][0]['node']
            return {'exists': True, 'customer': customer}
        else:
            return {'exists': False, 'customer': None}
    except Exception as e:
        print(f"❌ Shopify Error: {str(e)}")
        return {'exists': False, 'customer': None}

def add_to_sheet(log_name, log_whatsapp):
    """Add to Google Sheet - Only A & B columns"""
    try:
        sheet = get_google_sheet()
        if sheet:
            row = [log_name, log_whatsapp]
            sheet.append_row(row)
            print(f"✅ Added to Sheet: {row}")
            return True
    except Exception as e:
        print(f"❌ Sheet error: {str(e)}")
    return False

def send_whatsapp_message(to_number, message_text):
    """Send WhatsApp message"""
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "text": {"body": message_text}
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            print(f"✅ WhatsApp sent")
        return response.json()
    except Exception as e:
        print(f"❌ WhatsApp error: {str(e)}")
        return None

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "running",
        "app": "AJewelBot v2",
        "message": "Bot active - Simple mode"
    }), 200

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            print("✅ Webhook verified!")
            return challenge, 200
        return 'Forbidden', 403
    
    elif request.method == 'POST':
        data = request.get_json()
        
        print("=" * 60)
        print("📩 NEW MESSAGE")
        print("=" * 60)
        
        try:
            if 'entry' in data:
                entry = data['entry'][0]
                changes = entry['changes'][0]
                value = changes['value']
                
                if 'messages' in value:
                    message = value['messages'][0]
                    from_number = message['from']
                    
                    if message['type'] == 'text':
                        message_body = message['text']['body']
                        
                        print(f"📱 Phone: {from_number}")
                        print(f"💬 Message: {message_body}")
                        
                        # Check customer
                        result = check_customer_exists(from_number)
                        
                        if result['exists']:
                            customer = result['customer']
                            first_name = customer.get('firstName', '')
                            last_name = customer.get('lastName', '')
                            log_name = f"{first_name} {last_name}".strip()
                            
                            print(f"👤 Name: {log_name}")
                            print(f"✅ OLD CUSTOMER")
                            
                            response_text = f"Yes ✅\n\nWelcome back {first_name}! 🙏"
                        else:
                            log_name = "New Customer"
                            
                            print(f"👤 Name: {log_name}")
                            print(f"❌ NEW CUSTOMER")
                            
                            response_text = "No ❌\n\nYou are a new customer. Welcome to A.Jewel.Studio! 👋"
                        
                        # Add to Google Sheet (A & B only)
                        add_to_sheet(log_name, from_number)
                        
                        # Send WhatsApp reply
                        send_whatsapp_message(from_number, response_text)
                        
                        print("=" * 60)
        
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            print("=" * 60)
        
        return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"🚀 Starting AJewelBot v2 on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=True)
