# AJewelBot v3 - WhatsApp Bot with Flow Support
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
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN')
WHATSAPP_PHONE_ID = os.getenv('WHATSAPP_PHONE_ID')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN')
GOOGLE_CREDENTIALS = os.getenv('GOOGLE_CREDENTIALS')
LOGO_IMAGE_URL = os.getenv('LOGO_IMAGE_URL', 'https://cdn.shopify.com/s/files/1/0815/3248/5868/files/Welcome_Photo.jpg?v=1772108644')

SHEET_ID = "1w-4Zi65AqsQZFJIr1GLrDrW9BJNez8Wtr-dTL8oBLbs"
JOIN_US_URL = "https://a-jewel-studio-3.myshopify.com/pages/join-us"
CUSTOMER_CARE_NUMBER = "7600056655"

# ── Google Sheet Connection ──
def get_google_sheet():
    try:
        creds_dict = json.loads(GOOGLE_CREDENTIALS)
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID).worksheet('Registrations')
    except Exception as e:
        print(f"Google Sheets Error: {e}")
        return None
# ── Check Customer Status ──
def check_customer_status(phone_number):
    """
    Check customer in Google Sheet:
    - Column A: WhatsApp number
    - Column B: Gender (if filled, form completed)
    - Column Z: Customer Type (Retail/B2B)
    """
    try:
        sheet = get_google_sheet()
        if not sheet:
            return {'exists': False}
        
        all_data = sheet.get_all_values()
        
        for idx, row in enumerate(all_data[1:], start=2):  # Skip header
            if len(row) > 0 and row[0] == phone_number:  # Column A match
                # Check if form filled (Column B - Gender)
                has_form_data = bool(row[1]) if len(row) > 1 else False
                
                # Get customer type (Column Z - index 25)
                customer_type = row[25] if len(row) > 25 else 'Retail'
                
                # Get name from Note (Column AO - index 40)
                full_name = row[40] if len(row) > 40 else ''
                
                return {
                    'exists': True,
                    'has_form_data': has_form_data,
                    'customer_type': customer_type,
                    'name': full_name.split(' - ')[0] if full_name else '',
                    'row': idx
                }
        
        return {'exists': False}
    
    except Exception as e:
        print(f"Sheet check error: {e}")
        return {'exists': False}

# ── Add Number to Column A (No Duplicates) ──
def add_number_to_sheet(phone_number):
    """
    Add new number to Column A only (if not exists)
    """
    try:
        customer_status = check_customer_status(phone_number)
        
        if customer_status['exists']:
            print(f"Number already exists: {phone_number}")
            return False
        
        sheet = get_google_sheet()
        if sheet:
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

# ── WhatsApp: Send Interactive Buttons ──
def send_whatsapp_buttons(to_number, body_text, buttons):
    """
    Send interactive buttons (max 3 buttons)
    buttons = [
        {"id": "btn1", "title": "Button 1"},
        {"id": "btn2", "title": "Button 2"}
    ]
    """
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
            "body": {"text": body_text},
            "action": {
                "buttons": buttons[:3]  # Max 3 buttons
            }
        }
    }
    try:
        r = requests.post(url, json=payload, headers=headers)
        print(f"Buttons sent to {to_number}: {r.status_code}")
        return r.json()
    except Exception as e:
        print(f"WhatsApp buttons error: {e}")
        # Fallback to text
        button_text = "\n".join([f"{i+1}. {btn['title']}" for i, btn in enumerate(buttons)])
        return send_whatsapp_text(to_number, f"{body_text}\n\n{button_text}")

# ── WhatsApp: Send CTA URL Button ──
def send_whatsapp_cta_button(to_number, body_text, button_text, button_url):
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
            print(f"CTA button sent to {to_number}")
            return r.json()
        else:
            print(f"CTA button failed, sending text fallback")
            fallback = f"{body_text}\n\n{button_text}: {button_url}"
            return send_whatsapp_text(to_number, fallback)
    except Exception as e:
        print(f"WhatsApp CTA button error: {e}")
        fallback = f"{body_text}\n\n{button_text}: {button_url}"
        return send_whatsapp_text(to_number, fallback)
# ── FLOW 1: New Customer Welcome ──
def send_new_customer_welcome(to_number):
    """
    Flow 1: New customer first visit
    """
    # Send logo image
    if LOGO_IMAGE_URL:
        send_whatsapp_image(
            to_number,
            LOGO_IMAGE_URL,
            caption="Welcome to\n\n*A Jewel Studio*"
        )
    
    # Send Join Us button
    join_url = f"{JOIN_US_URL}?wa={to_number}"
    send_whatsapp_cta_button(
        to_number,
        "Tap Join Us below to become a part of our family.",
        "Join Us",
        join_url
    )

# ── FLOW 2A: Welcome Retail Customer ──
def send_retail_welcome(to_number, customer_name):
    """
    Flow 2A: Returning retail customer
    """
    message = f"Welcome, {customer_name}.\n\nWe are delighted to have you here.\nPlease select an option below to get started."
    
    buttons = [
        {"id": "browse_collections", "title": "Browse Collections"},
        {"id": "customise_product", "title": "Customise a Product"},
        {"id": "my_orders", "title": "My Orders"}
    ]
    
    send_whatsapp_buttons(to_number, message, buttons)

# ── FLOW 2B: Welcome B2B Customer ──
def send_b2b_welcome(to_number, customer_name):
    """
    Flow 2B: Returning B2B customer
    """
    message = f"Welcome, {customer_name}.\n\nWe are delighted to have you here.\nPlease select an option below to get started."
    
    buttons = [
        {"id": "browse_digital_files", "title": "Browse Digital Files"},
        {"id": "request_custom_file", "title": "Request Custom File"},
        {"id": "my_orders", "title": "My Orders"}
    ]
    
    send_whatsapp_buttons(to_number, message, buttons)

# ── Complete Registration Message ──
def send_complete_registration(to_number):
    """
    Customer logged but form not completed
    """
    message = "Hi! 👋\n\nI see you messaged us before but didn't complete registration.\n\nWould you like to complete your registration?"
    
    join_url = f"{JOIN_US_URL}?wa={to_number}"
    send_whatsapp_cta_button(
        to_number,
        message,
        "Complete Registration",
        join_url
    )
# ── Connect with Us Button ──
def send_connect_with_us(to_number, message_text):
    """
    Send message with Connect with Us button
    """
    buttons = [
        {"id": "connect_support", "title": "Connect with Us"}
    ]
    send_whatsapp_buttons(to_number, message_text, buttons)

# ── Unrecognised Message (Fallback) ──
def send_unrecognised_message(to_number, customer_type='Retail'):
    """
    Flow 14: Unrecognised message fallback
    """
    message = "Thank you for reaching out to A Jewel Studio.\nWe could not understand your message. Please select an option below so we can assist you better."
    
    if customer_type == 'B2B':
        buttons = [
            {"id": "browse_digital_files", "title": "Browse Digital Files"},
            {"id": "request_custom_file", "title": "Request Custom File"},
            {"id": "my_orders", "title": "My Orders"}
        ]
    else:
        buttons = [
            {"id": "browse_collections", "title": "Browse Collections"},
            {"id": "customise_product", "title": "Customise a Product"},
            {"id": "my_orders", "title": "My Orders"}
        ]
    
    send_whatsapp_buttons(to_number, message, buttons)

# ── Business Hours ──
def send_business_hours(to_number):
    """
    F47: Business hours enquiry
    """
    message = """Our business hours are:

Monday to Saturday: 10:00 AM to 7:00 PM
Sunday: Closed

For support outside these hours, please leave a message and our team will respond on the next business day."""
    
    send_whatsapp_text(to_number, message)

# ── About A Jewel Studio ──
def send_about_us(to_number):
    """
    F48: About A Jewel Studio
    """
    message = """A Jewel Studio is a premium 3D jewellery design studio specialising in creating high-quality digital jewellery files for B2B partners and exclusive jewellery collections for retail customers.

Our designs are crafted with precision and made available through a network of authorised partner stores across India."""
    
    buttons = [
        {"id": "browse_collections", "title": "Browse Collections"},
        {"id": "connect_support", "title": "Connect with Us"}
    ]
    
    send_whatsapp_buttons(to_number, message, buttons)
# ── Keyword Detection ──
def detect_keyword(message_text):
    """
    Detect keywords in customer message
    Returns: keyword type or None
    """
    message_lower = message_text.lower().strip()
    
    # Greetings
    if any(word in message_lower for word in ['hi', 'hello', 'hey', 'namaste', 'hii']):
        return 'greeting'
    
    # Business hours
    if any(word in message_lower for word in ['business hours', 'timing', 'when available', 'open']):
        return 'business_hours'
    
    # About
    if any(word in message_lower for word in ['about', 'tell me about', 'who are you']):
        return 'about'
    
    # Orders
    if any(word in message_lower for word in ['my orders', 'order status', 'track order']):
        return 'my_orders'
    
    # Size
    if 'size' in message_lower:
        return 'size_guide'
    
    # Weight
    if 'weight' in message_lower:
        return 'weight'
    
    # Material
    if any(word in message_lower for word in ['gold plated', 'solid gold', 'waterproof', 'material']):
        return 'material'
    
    # Stock
    if any(word in message_lower for word in ['stock', 'available', 'availability']):
        return 'stock'
    
    # Offers
    if any(word in message_lower for word in ['offer', 'discount', 'sale']):
        return 'offers'
    
    # Refund
    if 'refund' in message_lower:
        return 'refund'
    
    # Return
    if 'return' in message_lower:
        return 'return_policy'
    
    return None
# ── Handle Button Clicks ──
def handle_button_click(button_id, from_number, customer_type='Retail'):
    """
    Handle interactive button clicks
    """
    print(f"Button clicked: {button_id}")
    
    if button_id == 'browse_collections' or button_id == 'browse_digital_files':
        # Send category menu
        message = "Please select a category."
        buttons = [
            {"id": "cat_face", "title": "Face Jewellery"},
            {"id": "cat_hand", "title": "Hand & Wrist"},
            {"id": "cat_neck", "title": "Neck & Collar"}
        ]
        send_whatsapp_buttons(from_number, message, buttons)
    
    elif button_id == 'customise_product':
        # Book appointment flow
        message = "We would love to create something special for you.\n\nTo discuss your customisation requirements, please book an appointment with our design team."
        buttons = [
            {"id": "book_appointment", "title": "Book Appointment"}
        ]
        send_whatsapp_buttons(from_number, message, buttons)
    
    elif button_id == 'request_custom_file':
        # B2B custom file request
        message = "We would be happy to create a custom 3D jewellery file based on your requirements.\n\nPlease connect with our team directly. Share your photo or design reference and we will provide a quote at the earliest."
        buttons = [
            {"id": "connect_support", "title": "Connect with Our Team"}
        ]
        send_whatsapp_buttons(from_number, message, buttons)
    
    elif button_id == 'my_orders':
        # Fetch orders (placeholder)
        message = "Fetching your orders...\n\nThis feature is coming soon. Please connect with our team for order details."
        send_connect_with_us(from_number, message)
    
    elif button_id == 'connect_support':
        # Connect with customer care
        message = f"Our team is here to help you.\n\nBusiness Hours:\nMonday to Saturday: 10:00 AM to 7:00 PM\n\nPlease call or WhatsApp us at:\n+91 {CUSTOMER_CARE_NUMBER}"
        send_whatsapp_text(from_number, message)
    
    else:
        # Unknown button
        send_unrecognised_message(from_number, customer_type)
# ── Routes ──
@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "running", "app": "AJewelBot v3"}), 200

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # ── GET: Verification ──
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            print("Webhook verified")
            return challenge, 200
        return 'Forbidden', 403

    # ── POST: Incoming Message ──
    data = request.get_json()
    print("=" * 60)
    
    try:
        entry = data['entry'][0]
        changes = entry['changes'][0]
        value = changes['value']

        if 'messages' not in value:
            return jsonify({"status": "ok"}), 200

        message = value['messages'][0]
        from_number = message['from']
        message_type = message.get('type')

        print(f"Phone: {from_number} | Type: {message_type}")

        # Handle button clicks
        if message_type == 'interactive':
            interactive = message.get('interactive', {})
            button_reply = interactive.get('button_reply', {})
            button_id = button_reply.get('id', '')
            
            # Get customer type
            customer_status = check_customer_status(from_number)
            customer_type = customer_status.get('customer_type', 'Retail') if customer_status['exists'] else 'Retail'
            
            handle_button_click(button_id, from_number, customer_type)
            return jsonify({"status": "ok"}), 200

        # Handle text messages
        if message_type == 'text':
            message_body = message['text']['body']
            print(f"Message: {message_body}")

            # Check customer status
            customer_status = check_customer_status(from_number)

            # New customer
            if not customer_status['exists']:
                print("NEW CUSTOMER")
                add_number_to_sheet(from_number)
                send_new_customer_welcome(from_number)
            
            # Existing customer - form not completed
            elif customer_status['exists'] and not customer_status['has_form_data']:
                print("INCOMPLETE REGISTRATION")
                
                # Check for keywords
                keyword = detect_keyword(message_body)
                
                if keyword == 'greeting':
                    send_complete_registration(from_number)
                elif keyword:
                    # Handle specific keyword
                    if keyword == 'business_hours':
                        send_business_hours(from_number)
                    elif keyword == 'about':
                        send_about_us(from_number)
                    else:
                        send_complete_registration(from_number)
                else:
                    send_complete_registration(from_number)
            
            # Existing customer - form completed
            else:
                print("RETURNING CUSTOMER")
                customer_name = customer_status.get('name', 'Customer')
                customer_type = customer_status.get('customer_type', 'Retail')
                
                # Check for keywords
                keyword = detect_keyword(message_body)
                
                if keyword == 'greeting':
                    # Send welcome based on customer type
                    if customer_type == 'B2B':
                        send_b2b_welcome(from_number, customer_name)
                    else:
                        send_retail_welcome(from_number, customer_name)
                
                elif keyword == 'business_hours':
                    send_business_hours(from_number)
                
                elif keyword == 'about':
                    send_about_us(from_number)
                
                else:
                    # Unrecognised message
                    send_unrecognised_message(from_number, customer_type)

    except Exception as e:
        print(f"Webhook error: {e}")

    print("=" * 60)
    return jsonify({"status": "ok"}), 200

# ── Run ──
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"Starting AJewelBot v3 on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)
