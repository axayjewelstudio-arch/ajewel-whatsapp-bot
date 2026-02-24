# main.py - AJewel WhatsApp Bot - Updated Flow
from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv
import json
import threading
import time
from datetime import datetime, timedelta
import hashlib

load_dotenv()

app = Flask(__name__)

# Environment Variables
SHOPIFY_STORE = os.getenv('SHOPIFY_STORE')
SHOPIFY_ACCESS_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN')
WHATSAPP_TOKEN = os.getenv('ACCESS_TOKEN')
WHATSAPP_PHONE_ID = os.getenv('PHONE_NUMBER_ID')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN')
RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET')

# Shopify API Headers
SHOPIFY_HEADERS = {
    'X-Shopify-Access-Token': SHOPIFY_ACCESS_TOKEN,
    'Content-Type': 'application/json'
}

# User session storage
user_sessions = {}

# ==================== HARDCODED COLLECTIONS ====================
# Facebook Commerce / WhatsApp Catalogue Collection IDs

MAIN_COLLECTIONS = [
    {"id": "25628597613502595", "title": "Baby Jewellery"},
    {"id": "25749951748007044", "title": "Face Jewellery"},
    {"id": "25770023742652990", "title": "Neck Jewellery"},
    {"id": "26078491468433934", "title": "Hand Jewellery"},
    {"id": "26473022232283999", "title": "Lower Body Jewellery"},
    {"id": "26328388420090334", "title": "Murti & Figurines"},
]

SUB_COLLECTIONS = {
    "25628597613502595": [  # Baby Jewellery
        {"id": "25948367958163570", "title": "Anklets & Payal"},
        {"id": "26693163706953517", "title": "Bangles & Kada"},
        {"id": "26008758518787659", "title": "Earrings"},
        {"id": "34573479015569657", "title": "Hair Accessories"},
        {"id": "25864345456526176", "title": "Necklace & Chain"},
        {"id": "26302662429369350", "title": "Rings"},
    ],
    "25749951748007044": [  # Face Jewellery
        {"id": "26090421433907722", "title": "Ear Jewellery"},
        {"id": "25629234596754210", "title": "Head Jewellery"},
        {"id": "25993617556990784", "title": "Lip & Eye Jewellery"},
        {"id": "26026555510330213", "title": "Nose Jewellery"},
    ],
    "25770023742652990": [  # Neck Jewellery
        {"id": "26277843851853890", "title": "Modern Necklace"},
        {"id": "25850209314636536", "title": "Pendant & Butti"},
        {"id": "26252397311060803", "title": "Special Sets"},
        {"id": "25892135267109218", "title": "Traditional Haar"},
    ],
    "26078491468433934": [  # Hand Jewellery
        {"id": "34397077723223821", "title": "Baju Band & Haath Panja"},
        {"id": "26079781681708309", "title": "Bangdi & Bangle"},
        {"id": "26349002784723474", "title": "Bracelet"},
        {"id": "26047371878255581", "title": "Kada"},
        {"id": "25891367957149672", "title": "Rings"},
    ],
    "26473022232283999": [  # Lower Body Jewellery
        {"id": "26118144874448091", "title": "Bichhiya & Toe Ring"},
        {"id": "25835297096142403", "title": "Kamarband & Waist"},
        {"id": "33976400778641336", "title": "Payal & Anklet"},
    ],
    "26328388420090334": [  # Murti & Figurines
        {"id": "33871729065808088", "title": "Animal Murti"},
        {"id": "26357708767188650", "title": "Hindu God Murti"},
        {"id": "34195647333383660", "title": "Mix Designs"},
    ],
}

# ==================== DEDUPLICATION ====================
processed_messages = {}
CACHE_DURATION = timedelta(minutes=5)

def clean_cache():
    now = datetime.now()
    expired = [k for k, v in processed_messages.items() if now - v > CACHE_DURATION]
    for k in expired:
        del processed_messages[k]

def generate_message_hash(sender, message_id, timestamp):
    data = f"{sender}_{message_id}_{timestamp}"
    return hashlib.md5(data.encode()).hexdigest()

def is_duplicate(message_hash):
    clean_cache()
    if message_hash in processed_messages:
        return True
    processed_messages[message_hash] = datetime.now()
    return False

# ==================== KEEP-ALIVE ====================
def keep_alive():
    while True:
        try:
            time.sleep(720)
            requests.get("https://ajewel-whatsapp-bot.onrender.com/")
            print("Keep-alive ping sent")
        except Exception as e:
            print(f"Keep-alive error: {e}")

# ==================== HELPER FUNCTIONS ====================

def send_whatsapp_message(phone_number, message):
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {'Authorization': f'Bearer {WHATSAPP_TOKEN}', 'Content-Type': 'application/json'}
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "text",
        "text": {"body": message}
    }
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

def send_whatsapp_buttons(phone_number, message, buttons):
    """Send interactive buttons (max 3)"""
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {'Authorization': f'Bearer {WHATSAPP_TOKEN}', 'Content-Type': 'application/json'}
    
    button_list = []
    for i, btn in enumerate(buttons[:3]):
        button_list.append({
            "type": "reply",
            "reply": {
                "id": f"btn_{i}_{btn.lower().replace(' ', '_')}",
                "title": btn[:20]
            }
        })
    
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": message},
            "action": {"buttons": button_list}
        }
    }
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

def send_cta_url_button(phone_number, message, button_text, url):
    """
    Send CTA URL button.
    WhatsApp opens CTA URLs in its own built-in browser (no external app).
    Auto-close on submit is handled by window.close() JS on the target page.
    """
    whatsapp_url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {'Authorization': f'Bearer {WHATSAPP_TOKEN}', 'Content-Type': 'application/json'}
    
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "interactive",
        "interactive": {
            "type": "cta_url",
            "body": {"text": message},
            "action": {
                "name": "cta_url",
                "parameters": {
                    "display_text": button_text,
                    "url": url
                }
            }
        }
    }
    
    response = requests.post(whatsapp_url, headers=headers, json=payload)
    return response.json()

def send_list_message(phone_number, header, body, button_text, sections):
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {'Authorization': f'Bearer {WHATSAPP_TOKEN}', 'Content-Type': 'application/json'}
    
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": header},
            "body": {"text": body},
            "action": {"button": button_text, "sections": sections}
        }
    }
    
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

def send_whatsapp_catalog(phone_number, body_text, collection_id):
    """
    Send WhatsApp Catalogue filtered by sub-collection ID.
    collection_id = Facebook Commerce sub-collection ID.
    Customer can browse, cart and order directly in WhatsApp.
    """
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {'Authorization': f'Bearer {WHATSAPP_TOKEN}', 'Content-Type': 'application/json'}
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone_number,
        "type": "interactive",
        "interactive": {
            "type": "catalog_message",
            "body": {"text": body_text},
            "action": {
                "name": "catalog_message",
                "parameters": {
                    "thumbnail_product_retailer_id": collection_id
                }
            }
        }
    }
    
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

# ==================== SHOPIFY FUNCTIONS ====================

def normalize_phone(phone):
    phone = phone.strip()
    if not phone.startswith('+'):
        return f"+{phone}"
    return phone

def get_shopify_customer(phone):
    """Check if customer exists in Shopify"""
    # Try with + prefix first, then without
    for phone_format in [f"+{phone}", phone]:
        url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/customers/search.json?query=phone:{phone_format}"
        response = requests.get(url, headers=SHOPIFY_HEADERS)
        data = response.json()
        if data.get('customers') and len(data['customers']) > 0:
            return data['customers'][0]
    return None

def generate_razorpay_link(amount, customer_name, customer_phone, order_id):
    import base64
    url = "https://api.razorpay.com/v1/payment_links"
    auth = base64.b64encode(f"{RAZORPAY_KEY_ID}:{RAZORPAY_KEY_SECRET}".encode()).decode()
    
    headers = {'Authorization': f'Basic {auth}', 'Content-Type': 'application/json'}
    
    payload = {
        "amount": int(amount * 100),
        "currency": "INR",
        "description": f"A Jewel Studio - Order #{order_id}",
        "customer": {
            "name": customer_name,
            "contact": normalize_phone(customer_phone)
        },
        "notify": {"sms": True, "whatsapp": True},
        "callback_url": "https://ajewel-whatsapp-bot.onrender.com/payment/callback",
        "callback_method": "get"
    }
    
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

# ==================== WEBHOOK ENDPOINTS ====================

@app.route('/')
@app.route('/health')
def home():
    return "AJewel WhatsApp Bot is Running! 🚀"

@app.route('/webhook', methods=['GET', 'POST'])
def whatsapp_webhook():
    
    # Verification
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            return challenge, 200
        return 'Forbidden', 403
    
    # Message handling
    if request.method == 'POST':
        data = request.json
        print(f"Webhook received: {json.dumps(data, indent=2)}")
        
        try:
            entry = data['entry'][0]
            changes = entry['changes'][0]
            value = changes['value']
            
            # Status updates (sent/delivered/read) ignore karo
            if 'statuses' in value and 'messages' not in value:
                return jsonify({"status": "ok"}), 200

            if 'messages' in value:
                message = value['messages'][0]
                from_number = message['from']
                message_id = message['id']
                timestamp = message['timestamp']
                message_type = message['type']
                
                # Deduplication
                msg_hash = generate_message_hash(from_number, message_id, timestamp)
                if is_duplicate(msg_hash):
                    print(f"Duplicate message: {message_id}")
                    return jsonify({"status": "ok"}), 200
                
                print(f"Processing: {message_type} from {from_number}")
                
                if message_type == 'text':
                    text = message['text']['body'].strip().lower()
                    handle_text_message(from_number, text)
                
                elif message_type == 'interactive':
                    interactive_type = message['interactive']['type']
                    
                    if interactive_type == 'button_reply':
                        button_id = message['interactive']['button_reply']['id']
                        button_title = message['interactive']['button_reply']['title']
                        handle_button_response(from_number, button_id, button_title)
                    
                    elif interactive_type == 'list_reply':
                        list_id = message['interactive']['list_reply']['id']
                        list_title = message['interactive']['list_reply']['title']
                        handle_list_response(from_number, list_id, list_title)
                
                elif message_type == 'order':
                    handle_order(from_number, message['order'])
        
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
        
        return jsonify({"status": "ok"}), 200

# ==================== MESSAGE HANDLERS ====================

def handle_text_message(phone, text):
    customer = get_shopify_customer(phone)
    
    if text in ['hi', 'hello', 'hey', 'start']:
        if customer:
            customer_name = customer.get('first_name', 'Customer')
            customer_tags = customer.get('tags', '')
            
            if 'B2B' in customer_tags or 'Wholesaler' in customer_tags:
                # B2B - directly show menu
                message = f"Hello {customer_name}! Welcome to A Jewel Studio 💎"
                send_whatsapp_buttons(phone, message, ["Menu"])
            else:
                # Retail - ask custom jewellery
                message = f"Hello {customer_name}! Welcome to A Jewel Studio 💎\n\nKya aap Custom Jewellery karvana chahte hain?"
                send_whatsapp_buttons(phone, message, ["Yes", "No"])
        else:
            # New customer - registration
            message = "Welcome to A Jewel Studio! 💎\n\nOrder karne ke liye pehle account banana hoga.\n\nNeeche diye gaye button se sign-up karein:"
            send_cta_url_button(phone, message, "Sign Up", f"https://{SHOPIFY_STORE}/pages/customer-registration")
    
    else:
        send_whatsapp_message(phone, "Main aapki madad ke liye yahan hoon! 'Hi' type karein.")

def handle_button_response(phone, button_id, button_title):
    customer = get_shopify_customer(phone)
    customer_name = customer.get('first_name', 'Customer') if customer else 'Customer'
    
    print(f"Button: {button_id} - {button_title}")
    
    # YES - Custom Jewellery Appointment
    # Page WhatsApp ke built-in browser mein khulega.
    # Auto-close: Shopify appointment page pe form submit ke baad window.close() JS daalna hoga.
    if 'yes' in button_id.lower():
        message = f"{customer_name}, thank you for choosing us! 💍\n\nAppoint book karein — yeh WhatsApp mein hi khulega:"
        send_cta_url_button(phone, message, "Book Appointment", f"https://{SHOPIFY_STORE}/apps/appointo")
    
    # NO or MENU - Show main 6 collections
    elif 'no' in button_id.lower() or 'menu' in button_id.lower():
        show_main_collections(phone, customer_name)
    
    # CATALOGUE button - open sub-collection catalogue in WhatsApp
    elif 'catalogue' in button_id.lower():
        session = user_sessions.get(phone, {})
        sub_id = session.get('selected_sub_id')
        sub_name = session.get('selected_sub_name', 'Products')
        
        if sub_id:
            send_whatsapp_catalog(
                phone,
                f"{sub_name} — cart karein aur order karein! 🛒",
                sub_id
            )
        else:
            send_whatsapp_message(phone, "Please pehle ek category select karein. 'Hi' type karein.")

def handle_list_response(phone, list_id, list_title):
    customer = get_shopify_customer(phone)
    customer_name = customer.get('first_name', 'Customer') if customer else 'Customer'
    
    # STEP 1: Main collection selected -> directly show sub-collections list
    if list_id.startswith('main_'):
        main_id = list_id.replace('main_', '')
        
        # Save to session
        if phone not in user_sessions:
            user_sessions[phone] = {}
        user_sessions[phone]['selected_main_id'] = main_id
        user_sessions[phone]['selected_main_name'] = list_title
        
        # Directly show sub-collections (no intermediate "Select Product" button)
        show_sub_collections(phone, main_id, list_title)
    
    # STEP 2: Sub-collection selected -> show Catalogue button
    elif list_id.startswith('sub_'):
        sub_id = list_id.replace('sub_', '')
        
        if phone not in user_sessions:
            user_sessions[phone] = {}
        user_sessions[phone]['selected_sub_id'] = sub_id
        user_sessions[phone]['selected_sub_name'] = list_title
        
        message = f"*{list_title}* collection ready hai! 💎\n\nCatalogue button dabao — WhatsApp mein products dekhein, cart karein aur order karein:"
        send_whatsapp_buttons(phone, message, ["Catalogue"])

def show_main_collections(phone, customer_name):
    """Show hardcoded 6 main collections as list"""
    rows = []
    for col in MAIN_COLLECTIONS:
        rows.append({
            "id": f"main_{col['id']}",
            "title": col['title']
        })
    
    sections = [{"title": "Categories", "rows": rows}]
    
    send_list_message(
        phone,
        "A Jewel Studio 💎",
        f"{customer_name}, kaunsi category dekhna chahenge?",
        "Categories",
        sections
    )

def show_sub_collections(phone, main_id, main_name):
    """Show sub-collections for selected main collection"""
    subs = SUB_COLLECTIONS.get(main_id, [])
    
    if not subs:
        send_whatsapp_message(phone, "Is category mein abhi koi sub-collection nahi hai.")
        return
    
    rows = []
    for sub in subs:
        rows.append({
            "id": f"sub_{sub['id']}",
            "title": sub['title']
        })
    
    sections = [{"title": main_name, "rows": rows}]
    
    send_list_message(
        phone,
        main_name,
        "Sub-category select karein:",
        "Select",
        sections
    )

def handle_order(phone, order_data):
    customer = get_shopify_customer(phone)
    
    if not customer:
        send_whatsapp_message(phone, "Please register first by sending 'Hi'")
        return
    
    customer_name = customer.get('first_name', 'Customer')
    customer_tags = customer.get('tags', '')
    product_items = order_data.get('product_items', [])
    
    order_summary = ""
    total_amount = 0
    total_items = 0
    
    for item in product_items:
        product_name = item.get('product_retailer_id', 'Unknown')
        quantity = item.get('quantity', 1)
        price = item.get('item_price', 0)
        currency = item.get('currency', 'INR')
        order_summary += f"• {product_name} x{quantity} — {currency} {price}\n"
        total_amount += price * quantity
        total_items += quantity
    
    if 'B2B' in customer_tags or 'Wholesaler' in customer_tags:
        # B2B - Razorpay payment
        # Payment link bhi WhatsApp ke built-in browser mein khulega (cta_url).
        # Auto-close: /payment/callback page pe window.close() JS daalna hoga.
        payment_response = generate_razorpay_link(
            total_amount,
            customer_name,
            phone,
            f"WA_{phone[-4:]}_{total_items}"
        )
        
        if payment_response.get('short_url'):
            if phone not in user_sessions:
                user_sessions[phone] = {}
            user_sessions[phone]['payment_link'] = payment_response['short_url']
            
            message = (
                f"Thank you {customer_name}! 🙏\n\n"
                f"Order Summary:\n{order_summary}\n"
                f"Total: ₹{total_amount}\n\n"
                "Neeche Pay Now dabao — payment WhatsApp mein hi complete hogi:"
            )
            send_cta_url_button(phone, message, "Pay Now", payment_response['short_url'])
        else:
            send_whatsapp_message(phone, "Payment link nahi bana. Please support se contact karein.")
    
    else:
        # Retail - manual follow-up
        message = (
            f"Thank you {customer_name} for choosing your products! 💎\n\n"
            "A Jewel Studio ki team aapse estimated cost, discounts, offers aur "
            "payment ki jankari ke liye jald hi contact karegi.\n\n"
            f"Aapka Order:\n{order_summary}"
        )
        send_whatsapp_message(phone, message)

# ==================== PAYMENT CALLBACK ====================

@app.route('/payment/callback', methods=['GET', 'POST'])
def payment_callback():
    
    if request.method == 'GET':
        # Razorpay success redirect
        # Auto-close: page pe window.close() JS daalna hoga.
        payment_id = request.args.get('razorpay_payment_id')
        print(f"Payment success: {payment_id}")
        # Return HTML with auto-close script
        return """
        <html>
        <body>
            <p>✅ Payment Successful! You can close this window.</p>
            <script>
                setTimeout(function() { window.close(); }, 2000);
            </script>
        </body>
        </html>
        """
    
    if request.method == 'POST':
        data = request.json
        print(f"Payment webhook: {json.dumps(data, indent=2)}")
        
        if data.get('event') == 'payment_link.paid':
            payment_link = data['payload']['payment_link']['entity']
            customer_phone = payment_link['customer']['contact'].lstrip('+')
            amount_paid = payment_link['amount'] / 100
            
            message = (
                f"✅ Payment Successful!\n\n"
                f"Amount Paid: ₹{amount_paid}\n\n"
                "Thank you for doing Business with A Jewel Studio! 💎\n\n"
                "Aapki design file aapke registered Email ID pe bhej di gayi hai."
            )
            send_cta_url_button(
                customer_phone,
                message,
                "View Orders",
                f"https://{SHOPIFY_STORE}/account/orders"
            )
        
        elif data.get('event') in ['payment_link.cancelled', 'payment_link.expired']:
            payment_link = data['payload']['payment_link']['entity']
            customer_phone = payment_link['customer']['contact'].lstrip('+')
            retry_link = user_sessions.get(customer_phone, {}).get('payment_link', payment_link.get('short_url'))
            
            message = "❌ Payment successful nahi hui.\n\nRetry karne ke liye Pay Now dabao:"
            send_cta_url_button(customer_phone, message, "Pay Now", retry_link)
        
        return jsonify({"status": "ok"}), 200

# ==================== RUN SERVER ====================

if __name__ == '__main__':
    keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
    keep_alive_thread.start()
    print("Server ready!")
    
    port = int(os.getenv('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
