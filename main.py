#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AJewel WhatsApp Bot – single‑file, production‑ready version.

Features
--------
* Proper phone‑normalisation + URL‑encoded Shopify search → existing customers are recognised.
* 5‑minute deduplication cache to ignore duplicate webhook events.
* Main‑collection → sub‑collection list flow (6 hard‑coded categories).
* WhatsApp native catalogue button (shows the selected sub‑collection name).
* B2B customers get a Razorpay payment link; retail customers get a manual follow‑up.
* Keep‑alive ping for Render free dynos.
* All configuration via .env.
"""

from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv
import json
import threading
import time
import re
import urllib.parse
import hashlib
from datetime import datetime, timedelta
import base64
import traceback

# -------------------------------------------------
# Load environment variables
# -------------------------------------------------
load_dotenv()

app = Flask(__name__)

SHOPIFY_STORE          = os.getenv('SHOPIFY_STORE')          # e.g. my-store.myshopify.com (no https://)
SHOPIFY_ACCESS_TOKEN   = os.getenv('SHOPIFY_ACCESS_TOKEN')
WHATSAPP_TOKEN         = os.getenv('ACCESS_TOKEN')
WHATSAPP_PHONE_ID      = os.getenv('PHONE_NUMBER_ID')
VERIFY_TOKEN           = os.getenv('VERIFY_TOKEN')
RAZORPAY_KEY_ID        = os.getenv('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET    = os.getenv('RAZORPAY_KEY_SECRET')
PORT                   = int(os.getenv('PORT', 10000))

# -------------------------------------------------
# Global constants
# -------------------------------------------------
SHOPIFY_HEADERS = {
    'X-Shopify-Access-Token': SHOPIFY_ACCESS_TOKEN,
    'Content-Type': 'application/json'
}

# session data per phone number (selected collection ids, etc.)
user_sessions = {}

# deduplication cache (hash → datetime)
processed_messages = {}
CACHE_DURATION = timedelta(minutes=5)

# -------------------------------------------------
# Hard‑coded collections (Facebook Commerce / WhatsApp catalogue)
# -------------------------------------------------
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

# -------------------------------------------------
# Utility functions
# -------------------------------------------------
def _clean_phone(raw_phone: str) -> str:
    """Return only digits, dropping leading '00' if present."""
    digits = re.sub(r'\D', '', raw_phone or '')
    if digits.startswith('00'):
        digits = digits[2:]
    return digits

def _shopify_query(phone: str) -> str:
    """Build a URL‑encoded query that matches both '+91…' and '91…'."""
    clean = _clean_phone(phone)
    parts = [
        urllib.parse.quote(f"phone:+{clean}"),
        urllib.parse.quote(f"phone:{clean}")
    ]
    return ','.join(parts)        # comma works as OR for Shopify search

def get_shopify_customer(phone: str):
    """Return the first matching Shopify customer dict, or None."""
    query = _shopify_query(phone)
    url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/customers/search.json?query={query}"
    try:
        resp = requests.get(url, headers=SHOPIFY_HEADERS, timeout=8)
    except Exception as exc:
        print(f"[SHOPIFY] request error: {exc}")
        return None

    if resp.status_code != 200:
        print(f"[SHOPIFY] status {resp.status_code}: {resp.text}")
        return None

    try:
        data = resp.json()
    except ValueError:
        print("[SHOPIFY] JSON decode error")
        return None

    customers = data.get('customers', [])
    if not customers:
        return None

    # Extra safety: compare cleaned numbers
    target = _clean_phone(phone)
    for cust in customers:
        if _clean_phone(cust.get('phone', '')) == target:
            return cust

    return customers[0]

def generate_razorpay_link(amount, customer_name, customer_phone, order_id):
    """Create a Razorpay payment link (amount in INR)."""
    clean_phone = f"+{_clean_phone(customer_phone)}"
    url = "https://api.razorpay.com/v1/payment_links"
    auth = base64.b64encode(f"{RAZORPAY_KEY_ID}:{RAZORPAY_KEY_SECRET}".encode()).decode()
    headers = {
        'Authorization': f'Basic {auth}',
        'Content-Type': 'application/json'
    }
    payload = {
        "amount": int(amount * 100),                 # INR → paise
        "currency": "INR",
        "description": f"A Jewel Studio - Order #{order_id}",
        "customer": {"name": customer_name, "contact": clean_phone},
        "notify": {"sms": True, "whatsapp": True},
        "callback_url": f"https://{SHOPIFY_STORE}/payment/callback",
        "callback_method": "get"
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=8)
    try:
        return resp.json()
    except ValueError:
        print("[RAZORPAY] JSON decode error")
        return {}

# ---------- Deduplication ----------
def _msg_hash(sender, msg_id, ts):
    return hashlib.sha256(f"{sender}_{msg_id}_{ts}".encode()).hexdigest()

def is_duplicate(hash_key):
    now = datetime.now()
    # Remove stale entries
    for k in list(processed_messages):
        if now - processed_messages[k] > CACHE_DURATION:
            del processed_messages[k]
    if hash_key in processed_messages:
        return True
    processed_messages[hash_key] = now
    return False

# ---------- Keep‑alive ----------
def keep_alive():
    """Ping the deployed URL every 12 minutes (Render free dynos)."""
    PING_URL = os.getenv('PING_URL', 'https://ajewel-whatsapp-bot.onrender.com/')
    while True:
        try:
            time.sleep(720)
            requests.get(PING_URL)
            print("✅ Keep‑alive ping sent")
        except Exception as e:
            print(f"❌ Keep‑alive error: {e}")

# -------------------------------------------------
# WhatsApp API helper functions
# -------------------------------------------------
def send_whatsapp_message(phone, text):
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    hdr = {'Authorization': f'Bearer {WHATSAPP_TOKEN}', 'Content-Type': 'application/json'}
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": text}
    }
    return requests.post(url, headers=hdr, json=payload).json()

def send_whatsapp_buttons(phone, body, buttons):
    """Send up to 3 quick‑reply buttons."""
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    hdr = {'Authorization': f'Bearer {WHATSAPP_TOKEN}', 'Content-Type': 'application/json'}
    btns = []
    for i, btn in enumerate(buttons[:3]):
        btns.append({
            "type": "reply",
            "reply": {
                "id": f"btn_{i}_{btn.lower().replace(' ', '_')}",
                "title": btn[:20]
            }
        })
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body},
            "action": {"buttons": btns}
        }
    }
    return requests.post(url, headers=hdr, json=payload).json()

def send_cta_url_button(phone, body, button_text, url_link):
    api = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    hdr = {'Authorization': f'Bearer {WHATSAPP_TOKEN}', 'Content-Type': 'application/json'}
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "cta_url",
            "body": {"text": body},
            "action": {
                "name": "cta_url",
                "parameters": {
                    "display_text": button_text,
                    "url": url_link
                }
            }
        }
    }
    return requests.post(api, headers=hdr, json=payload).json()

def send_whatsapp_catalog(phone, body_text="Browse our jewellery collection 💎"):
    """Native WhatsApp catalogue message."""
    api = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    hdr = {'Authorization': f'Bearer {WHATSAPP_TOKEN}', 'Content-Type': 'application/json'}
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "catalog_message",
            "body": {"text": body_text},
            "action": {"name": "catalog_message"}
        }
    }
    resp = requests.post(api, headers=hdr, json=payload)
    print(f"📦 Catalogue sent → {resp.status_code}")
    return resp.json()

def send_list_message(phone, header, body, button_text, sections):
    api = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    hdr = {'Authorization': f'Bearer {WHATSAPP_TOKEN}', 'Content-Type': 'application/json'}
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": header},
            "body": {"text": body},
            "action": {"button": button_text, "sections": sections}
        }
    }
    return requests.post(api, headers=hdr, json=payload).json()

# -------------------------------------------------
# Flow helpers (collections → catalogue)
# -------------------------------------------------
def show_main_collections(phone, cust_name):
    rows = [{"id": f"main_{c['id']}", "title": c['title']} for c in MAIN_COLLECTIONS]
    sections = [{"title": "Categories", "rows": rows}]
    send_list_message(
        phone,
        "A Jewel Studio 💎",
        f"{cust_name}, kaunsi category dekhna chahenge?",
        "Select Category",
        sections
    )

def show_sub_collections(phone, main_id, main_title):
    subs = SUB_COLLECTIONS.get(main_id, [])
    if not subs:
        send_whatsapp_message(phone, "Is category mein abhi koi sub‑collection nahi hai.")
        return
    rows = [{"id": f"sub_{s['id']}", "title": s['title']} for s in subs]
    sections = [{"title": main_title, "rows": rows}]
    send_list_message(
        phone,
        main_title,
        "Sub‑category select karein:",
        "Select",
        sections
    )

# -------------------------------------------------
# Message handlers
# -------------------------------------------------
def handle_text_message(phone, text):
    """Entry point for plain‑text messages."""
    cust = get_shopify_customer(phone)

    greetings = ['hi', 'hello', 'hey', 'start', 'menu']
    if text in greetings:
        if cust:
            name = cust.get('first_name', 'Customer')
            tags = cust.get('tags', '')

            if 'B2B' in tags or 'Wholesaler' in tags:
                # B2B – send full catalogue immediately
                send_whatsapp_catalog(phone, f"Hello {name}! 📦\n\nBrowse our full catalogue:")
            else:
                # Retail – ask about custom jewellery
                send_whatsapp_buttons(
                    phone,
                    f"Hello {name}! 👋\n\nKya aap Custom Jewellery karwana chahte hain?",
                    ["Yes", "No"]
                )
        else:
            # New user – ask to sign‑up
            signup_url = f"https://{SHOPIFY_STORE}/account/register"
            send_cta_url_button(
                phone,
                "Welcome to A Jewel Studio! 💎\n\nOrder karne ke liye pehle account banana hoga.",
                "Sign Up",
                signup_url
            )
    else:
        send_whatsapp_message(phone, "Main aapki madad ke liye yahan hoon! 'Hi' type karein to start karein.")

def handle_button_response(phone, btn_id, btn_title):
    cust = get_shopify_customer(phone)
    cust_name = cust.get('first_name', 'Customer') if cust else 'Customer'

    # YES → Custom jewellery appointment
    if 'yes' in btn_id.lower():
        appt_url = f"https://{SHOPIFY_STORE}/apps/appointo"
        send_cta_url_button(
            phone,
            f"{cust_name}, thank you for choosing us! 💍\n\nAppointment book karne ke liye neeche click karein:",
            "Book Appointment",
            appt_url
        )
        return

    # NO or MENU → show main collections
    if 'no' in btn_id.lower() or 'menu' in btn_id.lower():
        show_main_collections(phone, cust_name)
        return

    # Catalogue button (after sub‑collection selection)
    if 'catalogue' in btn_id.lower():
        sess = user_sessions.get(phone, {})
        sub_name = sess.get('selected_sub_name', 'Products')
        body = f"{sub_name} — WhatsApp mein browse, cart aur order karein."
        send_whatsapp_catalog(phone, body)
        return

    # fallback
    send_whatsapp_message(phone, "Koi action samajh nahi aaya. 'Hi' se shuru karein.")

def handle_list_response(phone, list_id, list_title):
    """
    list_id pattern:
        main_<collection_id> → show its sub‑collections
        sub_<sub_collection_id> → store in session & present catalogue button
    """
    # USER selected a main collection
    if list_id.startswith('main_'):
        main_id = list_id.replace('main_', '')
        user_sessions.setdefault(phone, {})['selected_main_id'] = main_id
        user_sessions[phone]['selected_main_name'] = list_title
        show_sub_collections(phone, main_id, list_title)
        return

    # USER selected a sub‑collection
    if list_id.startswith('sub_'):
        sub_id = list_id.replace('sub_', '')
        user_sessions.setdefault(phone, {})
        user_sessions[phone]['selected_sub_id'] = sub_id
        user_sessions[phone]['selected_sub_name'] = list_title
        msg = (
            f"*{list_title}* collection ready hai! 💎\n\n"
            "Catalogue button dabao — WhatsApp mein products dekhein, cart karein aur order karein."
        )
        send_whatsapp_buttons(phone, msg, ["Catalogue"])
        return

def handle_whatsapp_cart_order(phone, order_data):
    """Process a native WhatsApp catalogue order."""
    cust = get_shopify_customer(phone)
    if not cust:
        send_whatsapp_message(phone, "Please register first by sending 'Hi'")
        return

    name = cust.get('first_name', 'Customer')
    tags = cust.get('tags', '')

    items = order_data.get('product_items', [])
    if not items:
        send_whatsapp_message(phone, "Koi product select nahi hua lagta.")
        return

    # Build summary
    summary = ""
    total_amount = 0
    total_qty = 0
    for it in items:
        prod = it.get('product_retailer_id', 'Unknown')
        qty = it.get('quantity', 1)
        price = it.get('item_price', 0)
        curr = it.get('currency', 'INR')
        summary += f"• {prod} x{qty} — {curr} {price}\n"
        total_amount += price * qty
        total_qty += qty

    # B2B → payment link
    if 'B2B' in tags or 'Wholesaler' in tags:
        payment = generate_razorpay_link(
            total_amount,
            name,
            phone,
            f"WA_{phone[-4:]}_{total_qty}"
        )
        if payment.get('short_url'):
            msg = (
                f"✅ Order Received!\n"
                f"Customer: {name}\n"
                f"Items: {total_qty}\n\n"
                f"Details:\n{summary}\n"
                f"Total: ₹{total_amount}\n\n"
                "Pay now to confirm your order:"
            )
            send_cta_url_button(phone, msg, "Pay Now", payment['short_url'])
        else:
            send_whatsapp_message(phone, "Payment link generate nahi hua. Support se contact karein.")
    else:
        # Retail – manual follow‑up
        msg = (
            f"✅ Thank you {name} for your order! 💎\n\n"
            f"Order Details:\n{summary}\n"
            f"Total items: {total_qty}\n\n"
            "Aapki team jald hi cost, discount, offers aur payment ki jankari ke liye contact karegi."
        )
        send_whatsapp_message(phone, msg)

# -------------------------------------------------
# Flask routes
# -------------------------------------------------
@app.route('/')
@app.route('/health')
def home():
    return "AJewel WhatsApp Bot is Running! 🚀"

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # ----- verification (GET) -----
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            print("✅ webhook verified")
            return challenge, 200
        return 'Forbidden', 403

    # ----- incoming messages (POST) -----
    if request.method == 'POST':
        data = request.json
        print(f"🔔 webhook payload:\n{json.dumps(data, indent=2)}")

        try:
            entry = data['entry'][0]
            change = entry['changes'][0]
            value = change['value']

            # ignore delivery/read status packets
            if 'statuses' in value and 'messages' not in value:
                return jsonify({"status": "ok"}), 200

            if 'messages' not in value:
                return jsonify({"status": "ok"}), 200

            msg = value['messages'][0]
            phone = msg['from']
            msg_id = msg['id']
            ts = msg['timestamp']
            msg_type = msg['type']

            # deduplication
            h = _msg_hash(phone, msg_id, ts)
            if is_duplicate(h):
                print(f"🔁 duplicate ignored ({msg_id})")
                return jsonify({"status": "ok"}), 200

            if msg_type == 'text':
                txt = msg['text']['body'].strip().lower()
                handle_text_message(phone, txt)

            elif msg_type == 'interactive':
                i_type = msg['interactive']['type']
                if i_type == 'button_reply':
                    btn_id = msg['interactive']['button_reply']['id']
                    btn_title = msg['interactive']['button_reply']['title']
                    handle_button_response(phone, btn_id, btn_title)
                elif i_type == 'list_reply':
                    list_id = msg['interactive']['list_reply']['id']
                    list_title = msg['interactive']['list_reply']['title']
                    handle_list_response(phone, list_id, list_title)

            elif msg_type == 'order':
                # native catalogue order
                handle_whatsapp_cart_order(phone, msg['order'])

        except Exception as e:
            print(f"❌ webhook processing error: {e}")
            traceback.print_exc()

        return jsonify({"status": "ok"}), 200

# -------------------------------------------------
# Razorpay payment callbacks
# -------------------------------------------------
@app.route('/payment/callback', methods=['GET', 'POST'])
def payment_callback():
    if request.method == 'GET':
        # Razorpay redirects here after successful payment
        pid = request.args.get('razorpay_payment_id')
        print(f"✅ Razorpay success (payment_id={pid})")
        return """
        <html><body>
        <p>✅ Payment successful! You may close this window.</p>
        <script>setTimeout(()=>window.close(),2000);</script>
        </body></html>
        """

    # POST – webhook from Razorpay
    data = request.json
    print(f"🔔 Razorpay webhook:\n{json.dumps(data, indent=2)}")

    if data.get('event') == 'payment_link.paid':
        pl = data['payload']['payment_link']['entity']
        cust_phone = pl['customer']['contact'].lstrip('+')
        amount = pl['amount'] / 100
        msg = (
            f"✅ Payment Successful!\n\n"
            f"Amount Paid: ₹{amount}\n\n"
            "Thank you for doing Business with A Jewel Studio! 💎\n\n"
            "Aapki design file aapke registered Email ID pe bhej di gayi hai."
        )
        orders_url = f"https://{SHOPIFY_STORE}/account/orders"
        send_cta_url_button(cust_phone, msg, "View Orders", orders_url)

    elif data.get('event') in ['payment_link.cancelled', 'payment_link.expired']:
        pl = data['payload']['payment_link']['entity']
        cust_phone = pl['customer']['contact'].lstrip('+')
        retry_url = pl.get('short_url')
        msg = "❌ Payment not completed.\n\nRetry by clicking Pay Now:"
        send_cta_url_button(cust_phone, msg, "Pay Now", retry_url)

    return jsonify({"status": "ok"}), 200

# -------------------------------------------------
# Server start
# -------------------------------------------------
if __name__ == '__main__':
    # start keep‑alive thread
    threading.Thread(target=keep_alive, daemon=True).start()
    print(f"🚀 Server starting on 0.0.0.0:{PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False)
