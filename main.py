#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AJewel WhatsApp Bot – single‑file version
================================================

What changed?
-------------
* When a phone number is **not** found in Shopify we no longer force a
  “sign‑up” step. The bot treats the user as a normal retail customer
  and immediately shows the collection menu (or a welcome catalogue).
* Order handling also works for “guest” users – the bot creates a temporary
  placeholder customer so the flow (order summary → payment for B2B, thank‑you
  for retail) continues without interruption.
* All other features remain the same:
  - phone normalisation + URL‑encoded Shopify search
  - 5‑minute deduplication cache
  - Main‑collection → Sub‑collection list flow
  - Native WhatsApp catalogue button
  - Razorpay payment link for B2B customers
  - Keep‑alive ping (Render)
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

SHOPIFY_STORE        = os.getenv('SHOPIFY_STORE')          # e.g. my-store.myshopify.com (no https://)
SHOPIFY_ACCESS_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN')
WHATSAPP_TOKEN       = os.getenv('ACCESS_TOKEN')
WHATSAPP_PHONE_ID    = os.getenv('PHONE_NUMBER_ID')
VERIFY_TOKEN         = os.getenv('VERIFY_TOKEN')
RAZORPAY_KEY_ID      = os.getenv('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET  = os.getenv('RAZORPAY_KEY_SECRET')
PORT                 = int(os.getenv('PORT', 10000))

# -------------------------------------------------
# Shopify API headers
# -------------------------------------------------
SHOPIFY_HEADERS = {
    'X-Shopify-Access-Token': SHOPIFY_ACCESS_TOKEN,
    'Content-Type': 'application/json'
}

# -------------------------------------------------
# Global storages
# -------------------------------------------------
user_sessions      = {}          # per‑phone session (selected collections, etc.)
processed_messages = {}          # deduplication cache
CACHE_DURATION    = timedelta(minutes=5)

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
    """Return only digits, drop any leading '00' (e.g. 0091 → 91)."""
    digits = re.sub(r'\D', '', raw_phone or '')
    if digits.startswith('00'):
        digits = digits[2:]
    return digits

def _shopify_query(phone: str) -> str:
    """Build a URL‑encoded query that matches '+91…' and '91…'."""
    clean = _clean_phone(phone)
    parts = [
        urllib.parse.quote(f"phone:+{clean}"),
        urllib.parse.quote(f"phone:{clean}")
    ]
    return ','.join(parts)   # comma works as OR for Shopify search

def get_shopify_customer(phone: str):
    """Return first matching Shopify customer dict, or None."""
    query = _shopify_query(phone)
    url   = f"https://{SHOPIFY_STORE}/admin/api/2024-01/customers/search.json?query={query}"
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

    # pick the one whose cleaned phone matches exactly
    target = _clean_phone(phone)
    for c in customers:
        if _clean_phone(c.get('phone', '')) == target:
            return c
    return customers[0]   # fallback – first match

def _placeholder_customer(phone: str):
    """Create a minimal guest‑customer dict when no Shopify record exists."""
    return {
        "first_name": f"Guest_{phone[-4:]}",   # e.g. Guest_1234
        "tags": ""                           # treat as Retail
    }

def generate_razorpay_link(amount, customer_name, customer_phone, order_id):
    """Create a Razorpay payment link (amount in INR)."""
    clean_phone = f"+{_clean_phone(customer_phone)}"
    url = "https://api.razorpay.com/v1/payment_links"
    auth = base64.b64encode(f"{RAZORPAY_KEY_ID}:{RAZORPAY_KEY_SECRET}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json"
    }
    payload = {
        "amount": int(amount * 100),                 # INR → paisa
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

# -------------- Deduplication --------------
def _msg_hash(sender, msg_id, ts):
    return hashlib.sha256(f"{sender}_{msg_id}_{ts}".encode()).hexdigest()

def is_duplicate(hash_key):
    now = datetime.now()
    # prune old entries
    for k in list(processed_messages):
        if now - processed_messages[k] > CACHE_DURATION:
            del processed_messages[k]
    if hash_key in processed_messages:
        return True
    processed_messages[hash_key] = now
    return False

# -------------- Keep‑alive (Render) --------------
def keep_alive():
    """Ping the own URL every 12 minutes to avoid dyno idling."""
    ping_url = os.getenv('PING_URL', 'https://ajewel-whatsapp-bot.onrender.com/')
    while True:
        try:
            time.sleep(720)          # 12 min
            requests.get(ping_url)
            print("✅ Keep‑alive ping sent")
        except Exception as e:
            print(f"❌ Keep‑alive error: {e}")

# -------------------------------------------------
# WhatsApp API helper functions
# -------------------------------------------------
def send_whatsapp_message(phone, text):
    api = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    hdr = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": text}
    }
    return requests.post(api, headers=hdr, json=payload).json()

def send_whatsapp_buttons(phone, body, buttons):
    """Up to 3 quick‑reply buttons."""
    api = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    hdr = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    btn_list = []
    for i, b in enumerate(buttons[:3]):
        btn_list.append({
            "type": "reply",
            "reply": {
                "id": f"btn_{i}_{b.lower().replace(' ', '_')}",
                "title": b[:20]
            }
        })
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body},
            "action": {"buttons": btn_list}
        }
    }
    return requests.post(api, headers=hdr, json=payload).json()

def send_cta_url_button(phone, body, button_text, url_link):
    api = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    hdr = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "cta_url",
            "body": {"text": body},
            "action": {
                "name": "cta_url",
                "parameters": {"display_text": button_text, "url": url_link}
            }
        }
    }
    return requests.post(api, headers=hdr, json=payload).json()

def send_whatsapp_catalog(phone, body_text="Browse our jewellery collection 💎"):
    api = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    hdr = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
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
    hdr = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
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
# Collection‑display helpers (menu flow)
# -------------------------------------------------
def show_main_collections(phone, cust_name):
    """Show the 6 hard‑coded main collections as a WhatsApp list."""
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
    """Show sub‑collections for the selected main collection."""
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
# Message handling
# -------------------------------------------------
def handle_text_message(phone, text):
    """Entry point for any plain‑text message."""
    cust = get_shopify_customer(phone)

    greetings = ['hi', 'hello', 'hey', 'start', 'menu']
    if text in greetings:
        if cust:
            name = cust.get('first_name', 'Customer')
            tags = cust.get('tags', '')

            if 'B2B' in tags or 'Wholesaler' in tags:
                # B2B – send full catalogue right away
                send_whatsapp_catalog(phone, f"Hello {name}! 📦\n\nBrowse our full catalogue:")
            else:
                # Retail – ask about custom jewellery
                send_whatsapp_buttons(
                    phone,
                    f"Hello {name}! 👋\n\nKya aap Custom Jewellery karwana chahte hain?",
                    ["Yes", "No"]
                )
        else:
            # **NEW CUSTOMER – no sign‑up required**
            # Show the main menu (or you could send a generic welcome catalogue)
            placeholder_name = "Friend"
            send_whatsapp_message(phone, "Welcome to A Jewel Studio! 💎")
            show_main_collections(phone, placeholder_name)
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
    """Process list‑reply (main collection or sub‑collection)."""
    # USER picked a main collection → show its sub‑collections
    if list_id.startswith('main_'):
        main_id = list_id.replace('main_', '')
        user_sessions.setdefault(phone, {})['selected_main_id'] = main_id
        user_sessions[phone]['selected_main_name'] = list_title
        show_sub_collections(phone, main_id, list_title)
        return

    # USER picked a sub‑collection → store & present catalogue button
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
        # Treat unknown phone as a guest/retail customer
        cust = _placeholder_customer(phone)

    name = cust.get('first_name', 'Customer')
    tags = cust.get('tags', '')

    items = order_data.get('product_items', [])
    if not items:
        send_whatsapp_message(phone, "Koi product select nahi hua lagta.")
        return

    # Build order summary
    summary = ""
    total_amount = 0
    total_qty = 0
    for it in items:
        prod = it.get('product_retailer_id', 'Unknown')
        qty = it.get('quantity', 1)
        price = it.get('item_price', 0)
        cur = it.get('currency', 'INR')
        summary += f"• {prod} x{qty} — {cur} {price}\n"
        total_amount += price * qty
        total_qty += qty

    # B2B customers → Razorpay payment link
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

    # ----- message handling (POST) -----
    if request.method == 'POST':
        data = request.json
        print(f"🔔 webhook payload:\n{json.dumps(data, indent=2)}")

        try:
            entry   = data['entry'][0]
            change  = entry['changes'][0]
            value   = change['value']

            # ignore status‑only updates
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
    # Successful redirect after payment (GET)
    if request.method == 'GET':
        pid = request.args.get('razorpay_payment_id')
        print(f"✅ Razorpay success (payment_id={pid})")
        return """
        <html><body>
        <p>✅ Payment successful! You may close this window.</p>
        <script>setTimeout(()=>window.close(),2000);</script>
        </body></html>
        """

    # Webhook from Razorpay (POST)
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
    threading.Thread(target=keep_alive, daemon=True).start()
    print(f"🚀 Server starting on 0.0.0.0:{PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False)
