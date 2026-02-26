# AJewelBot v2 - WhatsApp Bot Only
import os
import json
from flask import Flask, request, jsonify
import requests
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

load_dotenv()
app = Flask(__name__)

# Environment variables
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN')
WHATSAPP_PHONE_ID = os.getenv('WHATSAPP_PHONE_ID')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN')
GOOGLE_CREDENTIALS = os.getenv('GOOGLE_CREDENTIALS')

SHEET_ID = "1w-4Zi65AqsQZFJIr1GLrDrW9BJNez8Wtr-dTL8oBLbs"
JOIN_US_URL = "https://a-jewel-studio-3.myshopify.com/pages/join-us"

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
        print(f"Google Sheets Error: {str(e)}")
        return None

def get_customer_from_sheet(phone_number):
    """Get customer data from Google Sheet by phone number"""
    try:
        sheet = get_google_sheet()
        if sheet:
            # Get all data
            all_data = sheet.get_all_values()
            
            # Skip header row, search in data rows
            for index, row in enumerate(all_data[1:], start=2):  # Start from row 2
                # Column B (index 1) has phone number
                if len(row) > 1 and row[1] == phone_number:
                    customer_name = row[0] if len(row) > 0 else ''  # Column A
                    print(f"Found customer: {customer_name} at row {index}")
                    return {
                        'exists': True,
                        'name': customer_name,
                        'row': index
                    }
            
            print(f"Customer not found: {phone_number}")
            return {'exists': False, 'name': None, 'row': None}
    except Exception as e:
        print(f"Sheet check error: {str(e)}")
        return {'exists': False, 'name': None, 'row': None}

def add_number_to_sheet(phone_number):
    """Add new number to Column B (only if not exists)"""
    try:
        # First check if already exists
        customer_data = get_customer_from_sheet(phone_number)
        
        if customer_data['exists']:
            print(f"Number already exists, skipping: {phone_number}")
            return False
        
        # Add new row
        sheet = get_google_sheet()
        if sheet:
            # Add empty name in A, phone in B
            sheet.append_row(['', phone_number, '', '', '', '', '', '', '', '', '', '', '', ''])
            print(f"Added new number: {phone_number}")
            return True
    except Exception as e:
        print(f"Sheet add error: {str(e)}")
    return False

def send_whatsapp_text(to_number, message_text):
    """Send simple text message"""
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
            print(f"Message sent to {to_number}")
        else:
            print(f"Message failed: {response.json()}")
        return response.json()
    except Exception as e:
        print(f"WhatsApp error: {str(e)}")
        return None

def send_whatsapp_button(to_number, body_text, button_text, button_url):
    """Send message with URL button"""
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "interactive",
        "interactive": {
            "type": "cta_url",
            "body": {
                "text": body_text
            },
            "action": {
                "name": "cta_url",
                "parameters": {
                    "display_text": button_text,
                    "url": button_url
                }
            }
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            print(f"Button message sent to {to_number}")
            return response.json()
        else:
            print(f"Button failed: {response.json()}, sending text fallback")
            fallback_text = f"{body_text}\n\n{button_text}: {button_url}"
            return send_whatsapp_text(to_number, fallback_text)
    except Exception as e:
        print(f"WhatsApp button error: {str(e)}")
        fallback_text = f"{body_text}\n\n{button_text}: {button_url}"
        return send_whatsapp_text(to_number, fallback_text)

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "running",
        "app": "AJewelBot v2",
        "message": "WhatsApp bot active"
    }), 200

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            print("Webhook verified successfully")
            return challenge, 200
        return 'Forbidden', 403
    
    elif request.method == 'POST':
        data = request.get_json()
        
        print("=" * 60)
        print("NEW MESSAGE RECEIVED")
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
                        
                        print(f"Phone: {from_number}")
                        print(f"Message: {message_body}")
                        
                        # Check if customer exists in Google Sheet
                        customer_data = get_customer_from_sheet(from_number)
                        
                        if customer_data['exists']:
                            # Existing customer - welcome with name
                            customer_name = customer_data['name']
                            
                            if customer_name:
                                print(f"EXISTING CUSTOMER: {customer_name}")
                                response_text = f"Welcome back {customer_name}!\n\nHow can we help you today?"
                            else:
                                print(f"EXISTING CUSTOMER (no name)")
                                response_text = "Welcome back!\n\nHow can we help you today?"
                            
                            send_whatsapp_text(from_number, response_text)
                        else:
                            # New customer - add to sheet + send Join Us button
                            print(f"NEW CUSTOMER")
                            add_number_to_sheet(from_number)
                            
                            body_text = "Welcome to A.Jewel.Studio!\n\nJoin our community to get exclusive updates and offers."
                            button_text = "Join Us"
                            
                            send_whatsapp_button(from_number, body_text, button_text, JOIN_US_URL)
                        
                        print("=" * 60)
        
        except Exception as e:
            print(f"Error: {str(e)}")
            print("=" * 60)
        
        return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"Starting AJewelBot v2 on port {port}...")
    print("WhatsApp bot active")
    app.run(host='0.0.0.0', port=port, debug=False)
