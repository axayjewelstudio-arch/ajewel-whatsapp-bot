# AJewelBot v2 - Google Sheet Based (No Shopify)
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
JOIN_US_LINK = "https://a-jewel-studio-3.myshopify.com/account/register"

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

def check_number_in_sheet(phone_number):
    """Check if number exists in Column B"""
    try:
        sheet = get_google_sheet()
        if sheet:
            # Get all values from column B
            column_b = sheet.col_values(2)  # Column B (index 2)
            
            # Check if number exists
            if phone_number in column_b:
                row_index = column_b.index(phone_number) + 1
                print(f"✅ Number found in row {row_index}")
                return True
            else:
                print(f"❌ Number not found")
                return False
    except Exception as e:
        print(f"❌ Sheet check error: {str(e)}")
    return False

def add_number_to_sheet(phone_number):
    """Add new number to Column B"""
    try:
        sheet = get_google_sheet()
        if sheet:
            # Add to next empty row in column B
            sheet.append_row(['', phone_number])  # A is empty, B has number
            print(f"✅ Added number to sheet: {phone_number}")
            return True
    except Exception as e:
        print(f"❌ Sheet add error: {str(e)}")
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
            print(f"✅ Message sent")
        return response.json()
    except Exception as e:
        print(f"❌ WhatsApp error: {str(e)}")
        return None

def send_whatsapp_button(to_number, message_text, button_text, button_url):
    """Send message with button"""
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
            "type": "button",
            "body": {
                "text": message_text
            },
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {
                            "id": "join_us",
                            "title": button_text
                        }
                    }
                ]
            }
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            print(f"✅ Button message sent")
        return response.json()
    except Exception as e:
        print(f"❌ WhatsApp button error: {str(e)}")
        # Fallback to text with link
        fallback_text = f"{message_text}\n\n{button_text}: {button_url}"
        return send_whatsapp_text(to_number, fallback_text)

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "running",
        "app": "AJewelBot v2",
        "message": "Google Sheet based bot"
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
                        
                        # Check if number exists in Google Sheet
                        number_exists = check_number_in_sheet(from_number)
                        
                        if number_exists:
                            # Existing customer - Welcome message
                            print(f"✅ EXISTING CUSTOMER")
                            response_text = "Welcome back to A.Jewel.Studio! 🙏\n\nHow can we help you today?"
                            send_whatsapp_text(from_number, response_text)
                        else:
                            # New customer - Add to sheet + Join Us link
                            print(f"❌ NEW CUSTOMER")
                            add_number_to_sheet(from_number)
                            
                            response_text = "Welcome to A.Jewel.Studio! 👋\n\nWe're excited to have you here."
                            button_text = "Join Us"
                            
                            send_whatsapp_button(from_number, response_text, button_text, JOIN_US_LINK)
                        
                        print("=" * 60)
        
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            print("=" * 60)
        
        return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"🚀 Starting AJewelBot v2 on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=True)
