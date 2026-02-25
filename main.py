# -*- coding: utf-8 -*-
"""
WhatsApp Bot for AJewel Studio
Flows:
1️⃣ New Customer → Sign-Up → Welcome + Menu
2️⃣ Existing Retail → Custom Jewellery → Yes/No
3️⃣ B2B Wholesaler → Direct Catalog → Order → Razorpay Pay
4️⃣ Razorpay webhook → Success / Failure → Download link
"""

import os
import time
import hashlib
import hmac
from flask import Flask, request, jsonify
import requests
import razorpay
from dotenv import load_dotenv

load_dotenv()

# -------------------------------------------------
# CONFIG
# -------------------------------------------------
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_CATALOG_PRODUCT_RETAILER_ID = os.getenv("WHATSAPP_CATALOG_PRODUCT_RETAILER_ID")

SHOPIFY_STORE = os.getenv("SHOPIFY_STORE")
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")
SHOPIFY_API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2024-01")

# Shopify GraphQL endpoint
SHOPIFY_GRAPHQL_URL = f"https://{SHOPIFY_STORE}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
SHOPIFY_HEADERS = {
    "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
    "Content-Type": "application/json"
}

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")

razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

APP_URL = os.getenv("APP_URL")
PORT = int(os.getenv("PORT", 10000))

user_state = {}
order_map = {}

app = Flask(__name__)

# -------------------------------------------------
# WhatsApp Send
# -------------------------------------------------
def send_whatsapp(payload):
    url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    requests.post(url, json=payload, headers=headers)


def text_message(to, body):
    send_whatsapp({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body}
    })


def interactive_reply_buttons(to, body, buttons):
    send_whatsapp({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": b}
                    for b in buttons
                ]
            }
        }
    })


def interactive_cta_url(to, body, label, url_link):
    send_whatsapp({
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
    })


def catalog_message(to):
    send_whatsapp({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "catalog_message",
            "body": {"text": "Browse our catalog below."},
            "action": {
                "name": "catalog_message",
                "parameters": {
                    "thumbnail_product_retailer_id": WHATSAPP_CATALOG_PRODUCT_RETAILER_ID
                }
            }
        }
    })


# -------------------------------------------------
# Shopify Helpers (GraphQL)
# -------------------------------------------------
def normalize(phone):
    return ''.join(filter(str.isdigit, phone))[-10:]


def find_shopify_customer_by_phone(phone):
    try:
        # Try multiple phone formats
        variants = [
            phone,
            f"+91{normalize(phone)}",
            normalize(phone)
        ]
        
        query = """
        query($query: String!) {
            customers(first: 10, query: $query) {
                edges {
                    node {
                        id
                        firstName
                        lastName
                        email
                        phone
                        tags
                    }
                }
            }
        }
        """
        
        for variant in variants:
            variables = {"query": f"phone:{variant}"}
            response = requests.post(
                SHOPIFY_GRAPHQL_URL,
                json={'query': query, 'variables': variables},
                headers=SHOPIFY_HEADERS
            )
            
            data = response.json().get('data', {})
            customers = data.get('customers', {}).get('edges', [])
            
            if customers:
                customer = customers[0]['node']
                # Return customer object with attributes
                class Customer:
                    def __init__(self, data):
                        self.first_name = data.get('firstName')
                        self.last_name = data.get('lastName')
                        self.email = data.get('email')
                        self.phone = data.get('phone')
                        self.tags = data.get('tags', [])
                
                return Customer(customer)
        
        return None
        
    except Exception as e:
        app.logger.error(f"Shopify error: {e}")
        return None


def is_wholesaler(customer):
    return "wholesale" in (customer.tags or "").lower()


# -------------------------------------------------
# Razorpay
# -------------------------------------------------
def create_payment_link(amount_paise, phone, description):
    data = {
        "amount": amount_paise,
        "currency": "INR",
        "description": description,
        "customer": {"phone": phone}
    }
    result = razorpay_client.payment_link.create(data)
    order_map[result["id"]] = phone
    return result


def verify_signature(data, signature):
    payload = "|".join([
        data.get("razorpay_payment_id", ""),
        data.get("razorpay_payment_link_id", ""),
        data.get("razorpay_payment_link_reference_id", ""),
        data.get("razorpay_payment_link_status", "")
    ])
    expected = hmac.new(
        RAZORPAY_WEBHOOK_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# -------------------------------------------------
# Routes
# -------------------------------------------------
@app.route("/", methods=["GET"])
def home():
    return "Bot Running"
    try:
        print("=== WEBHOOK DEBUG ===")
        print(f"Full data: {data}")
        
        value = data["entry"][0]["changes"][0]["value"]
        print(f"Value: {value}")
        
        # ✅ Fix: Check if messages exist
        if "messages" not in value:
            print("⚠️ No messages - status update")
            return "No message event", 200
        
        print(f"Messages found: {value['messages']}")
        
        phone = value["contacts"][0]["wa_id"]
        msg = value["messages"][0]
        msg_type = msg["type"]
        
        print(f"📱 Phone: {phone}, Type: {msg_type}")
        
        if msg_type == "text":
            text = msg["text"]["body"]
            print(f"💬 Text: {text}")


@app.route("/webhook", methods=["GET", "POST"])
def webhook():

    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge"), 200
        return "Error", 403

    data = request.get_json()
    if not data:
        return "No data", 200

    try:
        value = data["entry"][0]["changes"][0]["value"]
        
        # ✅ Fix: Check if messages exist
        if "messages" not in value:
            return "No message event", 200
        
        phone = value["contacts"][0]["wa_id"]
        msg = value["messages"][0]
        msg_type = msg["type"]

        # First time user
        if phone not in user_state:
            cust = find_shopify_customer_by_phone(phone)
            if not cust:
                interactive_cta_url(
                    phone,
                    "Welcome to A.Jewel.Studio! 💎\n\nPlease create your account to get started.",
                    "Join Us",
                    f"https://{SHOPIFY_STORE}/pages/join-us"
                )
                user_state[phone] = {"flow": "new"}
                return "New user", 200
            else:
                # Greeting with name
                name = f"{cust.first_name or ''} {cust.last_name or ''}".strip() or "Valued Customer"
                text_message(phone, f"Hello {name}! 👋\n\nWelcome back to A.Jewel.Studio! 💎")
                
                user_state[phone] = {"flow": "wholesale" if is_wholesaler(cust) else "retail"}

                if is_wholesaler(cust):
                    catalog_message(phone)
                else:
                    interactive_reply_buttons(
                        phone,
                        "Kya aap Custom Jewellery karvana chahte hain?",
                        [
                            {"id": "yes_custom", "title": "Yes"},
                            {"id": "no_custom", "title": "No"}
                        ]
                    )
                return "Existing user", 200

        state = user_state.get(phone)

        # Button reply
        if msg_type == "button":
            button_id = msg["button"]["payload"]

            if state["flow"] == "retail":
                if button_id == "yes_custom":
                    interactive_cta_url(
                        phone,
                        "Book consultation below.",
                        "Book Now",
                        f"https://{SHOPIFY_STORE}/products/custom-jewellery-consultation"
                    )
                else:
                    catalog_message(phone)

        # Order
        if msg_type == "order":
            items = msg["order"]["product_items"]
            total = sum(float(i["item_price"]) * int(i["quantity"]) for i in items)
            link = create_payment_link(int(total * 100), phone, "Order Payment")
            interactive_cta_url(phone, f"Total ₹{total}", "Pay Now", link["short_url"])

        return "OK", 200

    except Exception as e:
        app.logger.error(str(e))
        return "Error", 500


@app.route("/payment/webhook", methods=["POST"])
def payment_webhook():
    signature = request.headers.get("X-Razorpay-Signature")
    data = request.get_json()

    if not verify_signature(data, signature):
        return "Invalid", 400

    phone = order_map.get(data.get("razorpay_payment_link_id"))

    if data.get("razorpay_payment_link_status") == "paid":
        text_message(phone, "Payment Successful! 🎉")
    else:
        text_message(phone, "Payment Failed. Please retry.")

    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
