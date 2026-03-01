# AJewelBot v3 - WhatsApp Bot + Google Sheet Integration
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
CORS(app)  # Shopify ke liye CORS allow karna zaroori hai

# ── Environment Variables ──────────────────────────────────────────────────────
WHATSAPP_TOKEN    = os.getenv('WHATSAPP_TOKEN')
WHATSAPP_PHONE_ID = os.getenv('WHATSAPP_PHONE_ID')
VERIFY_TOKEN      = os.getenv('VERIFY_TOKEN')
GOOGLE_CREDENTIALS = os.getenv('GOOGLE_CREDENTIALS')

# Logo ka publicly hosted URL (Shopify ya CDN pe upload karo)
# Example: "https://cdn.shopify.com/s/files/.../A_Jewel_Studio.png"
LOGO_IMAGE_URL = os.getenv('LOGO_IMAGE_URL', 'https://cdn.shopify.com/s/files/1/0815/3248/5868/files/Welcome_Photo.jpg?v=1772108644')

SHEET_ID    = "1w-4Zi65AqsQZFJIr1GLrDrW9BJNez8Wtr-dTL8oBLbs"
JOIN_US_URL = "https://a-jewel-studio-3.myshopify.com/pages/join-us"

# ── Google Sheet Connection ────────────────────────────────────────────────────
def get_google_sheet():
    try:
        creds_dict = json.loads(GOOGLE_CREDENTIALS)
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        creds  = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID).sheet1
    except Exception as e:
        print(f"Google Sheets Error: {e}")
        return None

# ── Customer Check ─────────────────────────────────────────────────────────────
def get_customer_from_sheet(phone_number):
    try:
        sheet    = get_google_sheet()
        all_data = sheet.get_all_values() if sheet else []
        for idx, row in enumerate(all_data[1:], start=2):
            if len(row) > 1 and row[1] == phone_number:
                return {'exists': True, 'name': row[0] if row[0] else '', 'row': idx}
        return {'exists': False, 'name': None, 'row': None}
    except Exception as e:
        print(f"Sheet check error: {e}")
        return {'exists': False, 'name': None, 'row': None}

# ── Add New Number ─────────────────────────────────────────────────────────────
def add_number_to_sheet(phone_number):
    try:
        existing = get_customer_from_sheet(phone_number)
        if existing['exists']:
            return False
        sheet = get_google_sheet()
        if sheet:
            # A=Name(blank), B=Phone Log, C..N=blank
            sheet.append_row([phone_number, '', '', '', '', '', '', '', '', '', '', '', ''])
            print(f"New number added: {phone_number}")
            return True
    except Exception as e:
        print(f"Sheet add error: {e}")
    return False

# ── Update Row After Form Submit ───────────────────────────────────────────────
def update_customer_in_sheet(wa_number, form_data):
    """
    Form submit hone ke baad Column B mein wa_number dhundo
    aur us row ke baaki columns update karo.
    Sheet columns:
      A=Customer Name | B=Phone Log | C=Customer Type | D=Phone |
      E=Email | F=Customer Type(dup) | G=GST | H=Address |
      I=City | J=State | K=Tags | L=Note | M=Gender | N=Age
    """
    try:
        sheet    = get_google_sheet()
        all_data = sheet.get_all_values() if sheet else []

        target_row = None
        for idx, row in enumerate(all_data[1:], start=2):
            if len(row) > 1 and row[1] == wa_number:
                target_row = idx
                break

        if not target_row:
            # Number nahi mila — naya row add karo
            print(f"WA number not found in sheet, adding new row: {wa_number}")
            sheet.append_row([
                form_data.get('name', ''),
                wa_number,
                form_data.get('customer_type', ''),
                form_data.get('phone', ''),
                form_data.get('email', ''),
                form_data.get('customer_type', ''),
                form_data.get('gst', ''),
                form_data.get('business_address', ''),
                form_data.get('city', ''),
                form_data.get('state', ''),
                form_data.get('tags', ''),
                '',
                form_data.get('gender', ''),
                form_data.get('age', ''),
            ])
            return True

        # Row mili — update karo
        # gspread update_cell(row, col, value) — col 1-indexed
        updates = {
            1:  form_data.get('name', ''),              # A - Customer Name
            3:  form_data.get('customer_type', ''),     # C - Customer Type
            4:  form_data.get('phone', ''),             # D - Phone
            5:  form_data.get('email', ''),             # E - Email
            6:  form_data.get('customer_type', ''),     # F - Customer Type (dup)
            7:  form_data.get('gst', ''),               # G - GST
            8:  form_data.get('business_address', ''),  # H - Address
            9:  form_data.get('city', ''),              # I - City
            10: form_data.get('state', ''),             # J - State
            11: form_data.get('tags', ''),              # K - Tags
            13: form_data.get('gender', ''),            # M - Gender
            14: form_data.get('age', ''),               # N - Age
        }

        for col, value in updates.items():
            if value:
                sheet.update_cell(target_row, col, value)

        print(f"Row {target_row} updated for WA: {wa_number}")
        return True

    except Exception as e:
        print(f"Sheet update error: {e}")
        return False

# ── WhatsApp: Simple Text ──────────────────────────────────────────────────────
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

# ── WhatsApp: Image Message ────────────────────────────────────────────────────
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

# ── WhatsApp: Button (CTA URL) ─────────────────────────────────────────────────
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

# ── Routes ─────────────────────────────────────────────────────────────────────
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

        customer = get_customer_from_sheet(from_number)

        if customer['exists'] and customer['name']:
            # ── Existing Customer (name hai = form bhara hua hai) ──
            name = customer['name']
            caption = f"Welcome back, {name}.\n\nHow can we help you today?"
            if LOGO_IMAGE_URL:
                send_whatsapp_image(from_number, LOGO_IMAGE_URL, caption=caption)
            else:
                send_whatsapp_text(from_number, caption)

        else:
            # ── New Customer ya form pending ──
            # Number nahi tha to save karo, tha to skip (already saved)
            if not customer['exists']:
                add_number_to_sheet(from_number)

            # Logo + Welcome caption
            if LOGO_IMAGE_URL:
                send_whatsapp_image(
                    from_number,
                    LOGO_IMAGE_URL,
                    caption=(
                        "Welcome to *A Jewel Studio*\n\n"
                        ""
                    )
                )

            # Join Us button
            join_url = f"{JOIN_US_URL}?wa={from_number}"
            send_whatsapp_button(
                from_number,
                "Join our community.",
                "Join Us",
                join_url
            )

    except Exception as e:
        print(f"Webhook error: {e}")

    print("=" * 60)
    return jsonify({"status": "ok"}), 200


@app.route('/update-sheet', methods=['POST', 'OPTIONS'])
def update_sheet():
    """
    Shopify Join Us form submit hone pe yeh endpoint call hota hai.
    Form se data aata hai, Google Sheet mein update hota hai.
    """
    # CORS preflight
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers['Access-Control-Allow-Origin']  = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        return response, 200

    try:
        data = request.get_json()
        print(f"Form data received: {data}")

        wa_number = data.get('wa_number', '').strip()
        if not wa_number:
            return jsonify({"status": "error", "message": "wa_number required"}), 400

        # Name join karo
        first = data.get('first_name', '').strip()
        last  = data.get('last_name', '').strip()
        full_name = f"{first} {last}".strip()

        form_data = {
            'name':             full_name,
            'phone':            data.get('phone', ''),
            'email':            data.get('email', ''),
            'customer_type':    data.get('customer_type', 'Retailer'),
            'gender':           data.get('gender', ''),
            'age':              data.get('age', ''),
            'city':             data.get('city', ''),
            'state':            data.get('state', ''),
            'gst':              data.get('gst', ''),
            'business_address': data.get('business_address', ''),
            'tags':             data.get('tags', 'Retailer'),
        }

        success = update_customer_in_sheet(wa_number, form_data)

        if success:
            return jsonify({"status": "success", "message": "Sheet updated"}), 200
        else:
            return jsonify({"status": "error",   "message": "Sheet update failed"}), 500

    except Exception as e:
        print(f"/update-sheet error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ── Run ────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"Starting AJewelBot v3 on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)
