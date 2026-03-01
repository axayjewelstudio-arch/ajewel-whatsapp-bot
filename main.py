# AJewelBot v3 - WhatsApp Bot (Number Logging Only)
import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

load_dotenv()
app = Flask(__name__)
CORS(app)

# ── Environment Variables ──
WHATSAPP_TOKEN    = os.getenv('WHATSAPP_TOKEN')
WHATSAPP_PHONE_ID = os.getenv('WHATSAPP_PHONE_ID')
VERIFY_TOKEN      = os.getenv('VERIFY_TOKEN')
GOOGLE_CREDENTIALS = os.getenv('GOOGLE_CREDENTIALS')
LOGO_IMAGE_URL = os.getenv('LOGO_IMAGE_URL', 'https://cdn.shopify.com/s/files/1/0815/3248/5868/files/Welcome_Photo.jpg?v=1772108644')

SHEET_ID    = "1w-4Zi65AqsQZFJIr1GLrDrW9BJNez8Wtr-dTL8oBLbs"
JOIN_US_URL = "https://a-jewel-studio-3.myshopify.com/pages/join-us"

# ── Google Sheet Connection ──
def get_google_sheet():
    try:
        creds_dict = json.loads(GOOGLE_CREDENTIALS)
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        creds  = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID).worksheet('Registrations')
    except Exception as e:
        print(f"Google Sheets Error: {e}")
        return None

# ── Check if Number Exists in Column A ──
def number_exists_in_sheet(phone_number):
    """
    Column A mein number check karo (duplicate avoid karne ke liye)
    """
    try:
        sheet = get_google_sheet()
        if not sheet:
            return False
        
        # Column A ke saare values
        column_a = sheet.col_values(1)
        
        # Check if number already exists
        return phone_number in column_a
    except Exception as e:
        print(f"Sheet check error: {e}")
        return False

# ── Add Number to Column A (No Duplicates) ──
def add_number_to_sheet(phone_number):
    """
    Sirf Column A mein number add karo (agar already nahi hai)
    """
    try:
        # Check duplicate
        if number_exists_in_sheet(phone_number):
            print(f"Number already exists: {phone_number}")
            return False
        
        sheet = get_google_sheet()
        if sheet:
            # Sirf Column A mein number add karo
            sheet.append_row([phone_number])
            print(f"New number added to Column A: {phone_number}")
            return True
    except Exception as e:
        print(f"Sheet add error: {e}")
    return False

# ── WhatsApp: Send Text ──
def send_whatsapp_text(to_number, message_text):
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
        r = requests.post(url, json=payload, headers=headers)
        print(f"Text sent to {to_number}: {r.status_code}")
        return r.json()
    except Exception as e:
        print(f"WhatsApp text error: {e}")
        return None

# ── WhatsApp: Send Image ──
def send_whatsapp_image(to_number, image_url, caption=''):
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "image",
        "image": {
            "link": image_url,
            "caption": caption
        }
    }
    try:
        r = requests.post(url, json=payload, headers=headers)
        print(f"Image sent to {to_number}: {r.status_code}")
        return r.json()
    except Exception as e:
        print(f"WhatsApp image error: {e}")
        return None

# ── WhatsApp: Send Button ──
def send_whatsapp_button(to_number, body_text, button_text, button_url):
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
            "body": {"text": body_text},
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
        r = requests.post(url, json=payload, headers=headers)
        if r.status_code == 200:
            print(f"Button sent to {to_number}")
            return r.json()
        else:
            print(f"Button failed, sending text fallback")
            fallback = f"{body_text}\n\n{button_text}: {button_url}"
            return send_whatsapp_text(to_number, fallback)
    except Exception as e:
        print(f"WhatsApp button error: {e}")
        fallback = f"{body_text}\n\n{button_text}: {button_url}"
        return send_whatsapp_text(to_number, fallback)

# ── Routes ──
@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "running", "app": "AJewelBot v3"}), 200

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # ── GET: Verification ──
    if request.method == 'GET':
        mode      = request.args.get('hub.mode')
        token     = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            print("Webhook verified")
            return challenge, 200
        return 'Forbidden', 403

    # ── POST: Incoming Message ──
    data = request.get_json()
    print("=" * 60)
    try:
        entry   = data['entry'][0]
        changes = entry['changes'][0]
        value   = changes['value']

        if 'messages' not in value:
            return jsonify({"status": "ok"}), 200

        message = value['messages'][0]
        from_number = message['from']

        if message['type'] != 'text':
            return jsonify({"status": "ok"}), 200

        message_body = message['text']['body']
        print(f"Phone: {from_number} | Message: {message_body}")

        # ✅ Column A mein number add karo (no duplicates)
        add_number_to_sheet(from_number)

        # ✅ Welcome message with logo
        if LOGO_IMAGE_URL:
            send_whatsapp_image(
                from_number,
                LOGO_IMAGE_URL,
                caption="Welcome to *A Jewel Studio*\n\nPlease complete your registration to continue."
            )

        # ✅ Join Us button with phone number in URL
        join_url = f"{JOIN_US_URL}?wa={from_number}"
        send_whatsapp_button(
            from_number,
            "Join our community and explore exclusive collections.",
            "Join Us",
            join_url
        )

    except Exception as e:
        print(f"Webhook error: {e}")

    print("=" * 60)
    return jsonify({"status": "ok"}), 200

# ── Run ──
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"Starting AJewelBot v3 on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)
