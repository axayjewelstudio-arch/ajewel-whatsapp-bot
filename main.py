# -*- coding: utf-8 -*-
"""
WhatsApp Bot for AJewel Studio
Flows:
1️⃣ New Customer → Sign‑Up → Welcome + Menu
2️⃣ Existing Retail → “Kya aap Custom Jewellery karvana chahte hain?” → Yes/No
3️⃣ B2B Wholesaler → Direct Catalog → Order → Razorpay Pay
4️⃣ Razorpay webhook → Success / Failure → Download link
"""

import os
import json
import time
import hashlib
import hmac
from datetime import datetime

from flask import Flask, request, abort, jsonify
import requests
import shopify
import razorpay
from dotenv import load_dotenv

load_dotenv()                      # 👈 reads .env (or Render env vars)

# -------------------------------------------------
#           Global Config / Clients
# -------------------------------------------------
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_CATALOG_PRODUCT_RETAILER_ID = os.getenv("WHATSAPP_CATALOG_PRODUCT_RETAILER_ID")

SHOPIFY_STORE = os.getenv("SHOPIFY_STORE")
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")
SHOPIFY_API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2023-10")
SHOPIFY_SITE = f"https://{SHOPIFY_STORE}/admin/api/{SHOPIFY_API_VERSION}"
shopify.ShopifyResource.set_site(SHOPIFY_SITE)
shopify.ShopifyResource.set_access_token(SHOPIFY_ACCESS_TOKEN)

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

APP_URL = os.getenv("APP_URL")
PORT = int(os.getenv("PORT", 10000))

# In‑memory session store (replace with DB/Google‑Sheet for production)
user_state = {}          # {phone: {"flow": "...", "step": "..."}}
order_map = {}           # {razorpay_payment_link_id: phone}

app = Flask(__name__)

# -------------------------------------------------
#   Helper – send message to WhatsApp
# -------------------------------------------------
def send_whatsapp(payload: dict):
    """POST payload to WhatsApp Cloud API."""
    url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    resp = requests.post(url, json=payload, headers=headers)
    if not resp.ok:
        app.logger.error(f"WhatsApp send error {resp.status_code}: {resp.text}")
    return resp.json()


def text_message(to: str, body: str):
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body}
    }
    return send_whatsapp(payload)


def interactive_reply_buttons(to: str, body: str, buttons: list):
    """
    Quick‑reply buttons (type: reply).  `buttons` is a list of
    dicts → {"id": "...", "title": "..."} (max 3).
    """
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body},
            "action": {
                "buttons": [
                    {"type": "reply",
                     "reply": {"id": b["id"], "title": b["title"]}}
                    for b in buttons
                ]
            }
        }
    }
    return send_whatsapp(payload)


def interactive_cta_url(to: str, body: str, label: str, url_link: str):
    """CTA‑URL button (type: cta_url)."""
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "cta_url",
            "body": {"text": body},
            "action": {
                "name": "cta_url",
                "parameters": {
                    "display_text": label,
                    "url": url_link
                }
            }
        }
    }
    return send_whatsapp(payload)


def catalog_message(to: str):
    """Shows WhatsApp native catalog (single click)."""
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "catalog_message",
            "body": {"text": "Our product catalog – browse & add items to cart."},
            "action": {
                "name": "catalog_message",
                "parameters": {
                    "thumbnail_product_retailer_id": WHATSAPP_CATALOG_PRODUCT_RETAILER_ID
                }
            }
        }
    }
    return send_whatsapp(payload)


# -------------------------------------------------
#   Shopify helpers
# -------------------------------------------------
def find_shopify_customer_by_phone(phone: str):
    """
    Shopify does not have a direct “search by phone” endpoint in the REST API,
    but we can use the search query endpoint.
    """
    q = f"phone:{phone}"
    try:
        result = shopify.Customer.search(query=q)   # uses GraphQL under the hood
        for cust in result:
            if cust.phone and cust.phone.replace("+", "").replace(" ", "") == phone.replace("+", "").replace(" ", ""):
                return cust
    except Exception as e:
        app.logger.error(f"Shopify search error: {e}")
    return None


def is_wholesaler(customer):
    """If Shopify tags contain ‘wholesale’ → B2B flow."""
    tags = (customer.tags or "").lower()
    return "wholesale" in tags


# -------------------------------------------------
#   Razorpay helpers
# -------------------------------------------------
def create_payment_link(amount_paise: int, phone: str, description="Custom Jewellery Order"):
    """
    Generates a Razorpay payment‑link.
    """
    data = {
        "amount": amount_paise,
        "currency": "INR",
        "accept_partial": False,
        "expire_by": int(time.time()) + 24 * 3600,         # 24 h expiry
        "reference_id": f"ajewel_{int(time.time())}",
        "description": description,
        "customer": {"phone": phone},
        "notify": {"sms": True, "email": False},
        "callback_url": f"{APP_URL}/payment/webhook",
        "callback_method": "post"
    }
    result = razorpay_client.payment_link.create(data)
    # remember mapping for webhook verification
    order_map[result["id"]] = phone
    return result


def verify_razorpay_signature(request_data: dict, signature: str) -> bool:
    """
    Razorpay sends a sha256 HMAC.  Payload is the concatenation of
    payment_id|payment_link_id|payment_link_reference_id|payment_link_status
    """
    payload = "|".join([
        request_data.get("razorpay_payment_id", ""),
        request_data.get("razorpay_payment_link_id", ""),
        request_data.get("razorpay_payment_link_reference_id", ""),
        request_data.get("razorpay_payment_link_status", "")
    ])
    expected = hmac.new(
        RAZORPAY_WEBHOOK_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# -------------------------------------------------
#   Flow Handlers
# -------------------------------------------------
def handle_new_customer(phone):
    """User not found in Shopify → send Sign‑Up CTA."""
    signup_url = f"https://{SHOPIFY_STORE}/account/register"
    interactive_cta_url(
        to=phone,
        body="Namaste! Aap abhi tak hamare store ke customer nahi hain. Kripya register kijiye.",
        label="Sign Up",
        url_link=signup_url
    )
    # Store a flag that we are waiting for registration
    user_state[phone] = {"flow": "new", "step": "await_signup"}


def welcome_existing_customer(phone, customer):
    """Welcome + main menu for already known users."""
    name = customer.first_name or "Friend"
    text_message(
        to=phone,
        body=f"Namaste {name}! Aap hamare store ke valued customer hain.\n\nMenu:\n1️⃣ Custom Jewellery (appointment)\n2️⃣ Retail Catalogue\n3️⃣ Wholesaler Catalogue"
    )
    user_state[phone] = {"flow": "existing", "step": "menu"}


def handle_existing_customer(phone, customer):
    """Decide Retail vs Wholesaler based on tags."""
    if is_wholesaler(customer):
        # B2B – directly show catalog (wholesaler)
        catalog_message(to=phone)
        user_state[phone] = {"flow": "wholesale", "step": "catalog_shown"}
    else:
        # Retail – ask custom jewellery question
        interactive_reply_buttons(
            to=phone,
            body="Kya aap Custom Jewellery karvana chahte hain?",
            buttons=[
                {"id": "yes_custom", "title": "Yes"},
                {"id": "no_custom", "title": "No"}
            ]
        )
        user_state[phone] = {"flow": "retail", "step": "asked_custom"}


def handle_retail_reply(phone, button_id):
    """User pressed Yes/No on custom‑jewellery question."""
    if button_id == "yes_custom":
        # send appointment CTA
        appointment_url = f"https://{SHOPIFY_STORE}/products/custom-jewellery-consultation"
        interactive_cta_url(
            to=phone,
            body="Great! Book a consultation now.",
            label="Book Appointment",
            url_link=appointment_url
        )
        user_state[phone] = {"flow": "retail", "step": "appointment_sent"}
    else:   # no_custom
        catalog_message(to=phone)
        user_state[phone] = {"flow": "retail", "step": "catalog_shown"}


def handle_order_message(phone, order_payload):
    """
    Called when WhatsApp sends an **order** payload (product items added to cart).
    Example payload reference 👉 line 663‑686 in docs 【18†L663-L686】.
    """
    items = order_payload.get("product_items", [])
    total_amount = 0
    for itm in items:
        qty = int(itm.get("quantity", 1))
        price = float(itm.get("item_price", 0))
        total_amount += qty * price

    # Convert to INR paisa (Razorpay expects integer paise)
    amount_paise = int(total_amount * 100)

    # Create Razorpay payment link & send Pay‑Now button
    link = create_payment_link(amount_paise, phone, description="AJewel B2B Order")
    pay_url = link["short_url"]
    interactive_cta_url(
        to=phone,
        body=f"Your order total is ₹{total_amount:.2f}. Click below to pay.",
        label="Pay Now",
        url_link=pay_url
    )
    user_state[phone] = {"flow": "wholesale", "step": "await_payment", "payment_link_id": link["id"]}


def handle_retail_order(phone):
    """Retail flow: after order we just thank & inform “Team will contact”. """
    text_message(
        to=phone,
        body="Thank you! Hamara team aapko pricing ke liye contact karega."
    )
    user_state[phone] = {"flow": "retail", "step": "order_thanked"}


# -------------------------------------------------
#   Flask Routes
# -------------------------------------------------
@app.route("/", methods=["GET"])
def home():
    return "AJewel WhatsApp Bot is running"


# ---- WhatsApp webhook -------------------------------------------------
@app.route("/webhook", methods=["GET", "POST"])
def whatsapp_webhook():
    if request.method == "GET":
        # Verification request from Facebook
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge, 200
        return "Invalid verification", 403

    # ---- POST – incoming messages ------------------------------------------------
    data = request.get_json()
    # Safety check
    if not data or data.get("object") != "whatsapp_business_account":
        return "Ignored", 200

    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]
        contacts = value.get("contacts", [])
        if not contacts:
            return "No contacts", 200
        phone = contacts[0]["wa_id"]          # customer WhatsApp ID (used as phone)
        messages = value.get("messages", [])
        if not messages:
            return "No messages", 200

        msg = messages[0]
        msg_type = msg.get("type")
        # -------------------------------------------------
        # 1️⃣ New Customer Flow
        # -------------------------------------------------
        if phone not in user_state:
            # Lookup in Shopify
            shop_cust = find_shopify_customer_by_phone(phone)
            if not shop_cust:
                handle_new_customer(phone)
                return "Handled new‑customer", 200
            # Existing → decide which path
            welcome_existing_customer(phone, shop_cust)
            # fallthrough to route further messages

        # -------------------------------------------------
        # 2️⃣ BUTTON REPLY (Yes/No) handling
        # -------------------------------------------------
        if msg_type == "button":
            # Interactive button_reply payload – see docs lines 494‑500 【6†L493-L500】
            button_reply = msg.get("button_reply", {})
            button_id = button_reply.get("id")
            if not button_id:
                return "No button id", 200

            state = user_state.get(phone, {})
            if state.get("flow") == "retail" and state.get("step") == "asked_custom":
                handle_retail_reply(phone, button_id)
                return "Retail reply processed", 200

        # -------------------------------------------------
        # 3️⃣ TEXT MESSAGE – fallback / simple commands
        # -------------------------------------------------
        if msg_type == "text":
            text = msg["text"]["body"].strip().lower()
            # If user says “hi” after registration – re‑check Shopify
            if text in ["hi", "hello", "hey"]:
                cust = find_shopify_customer_by_phone(phone)
                if cust:
                    welcome_existing_customer(phone, cust)
                else:
                    handle_new_customer(phone)
                return "Greeting processed", 200

        # -------------------------------------------------
        # 4️⃣ ORDER MESSAGE – comes from WhatsApp Catalog flow
        # -------------------------------------------------
        if msg_type == "order":
            order_payload = msg.get("order", {})
            # Determine if this user is a wholesaler (catalog flow) or retail
            state = user_state.get(phone, {})
            if state.get("flow") == "wholesale":
                handle_order_message(phone, order_payload)
            else:
                # Retail order – just thank
                handle_retail_order(phone)
            return "Order processed", 200

        # Default – echo / unknown
        text_message(to=phone, body="Sorry, main aapki request samajh nahi paaya. Kripya dobara koshish karein.")
        return "Default reply", 200

    except Exception as e:
        app.logger.exception(f"Webhook processing error: {e}")
        return "Error", 500


# ---- Razorpay webhook -------------------------------------------------
@app.route("/payment/webhook", methods=["POST"])
def razorpay_webhook():
    # Razorpay sends a `X-Razorpay-Signature` header
    signature = request.headers.get("X-Razorpay-Signature")
    payload = request.get_json()
    if not signature or not payload:
        return "Missing data", 400

    if not verify_razorpay_signature(payload, signature):
        return "Invalid signature", 400

    status = payload.get("razorpay_payment_link_status")
    phone = order_map.get(payload.get("razorpay_payment_link_id"))

    if not phone:
        return "Unknown payment link", 200

    if status == "paid":
        # Send download link (you can fetch order details from Shopify if needed)
        download_url = f"https://{SHOPIFY_STORE}/account/orders"
        text_message(
            to=phone,
            body=f"Payment successful! 🟢 Aapke design files yahan se download kar sakte hain: {download_url}"
        )
    else:
        # Failed / created – ask to retry
        retry_url = f"https://{SHOPIFY_STORE}/account/orders"
        interactive_cta_url(
            to=phone,
            body="Payment failed. Kripya dobara try karein.",
            label="Retry",
            url_link=retry_url
        )
    return jsonify({"status": "ok"}), 200


# -------------------------------------------------
#   Run the app (Render will set $PORT)
# -------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)
