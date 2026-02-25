# -*- coding: utf-8 -*-

import os
import hashlib
import hmac
from flask import Flask, request, jsonify
import requests
import shopify
import razorpay
from dotenv import load_dotenv

load_dotenv()

# =================================================
# CONFIG
# =================================================
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_CATALOG_PRODUCT_RETAILER_ID = os.getenv("WHATSAPP_CATALOG_PRODUCT_RETAILER_ID")

SHOPIFY_STORE = os.getenv("SHOPIFY_STORE")
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")
SHOPIFY_API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2023-10")

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")

PORT = int(os.getenv("PORT", 10000))

# =================================================
# INIT
# =================================================
app = Flask(__name__)

shop_url = f"https://{SHOPIFY_STORE}/admin/api/{SHOPIFY_API_VERSION}"
shopify.ShopifyResource.set_site(shop_url)
shopify.ShopifyResource.set_access_token(SHOPIFY_ACCESS_TOKEN)

razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

user_state = {}
order_map = {}

# =================================================
# WhatsApp Send
# =================================================
def send_whatsapp(payload):
    url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    requests.post(url, json=payload, headers=headers)


def send_text(to, body):
    send_whatsapp({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body}
    })


def send_buttons(to, body, buttons):
    send_whatsapp({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": b} for b in buttons
                ]
            }
        }
    })


def send_cta(to, body, label, url):
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
                    "url": url
                }
            }
        }
    })


def send_catalog(to):
    send_whatsapp({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "catalog_message",
            "body": {"text": "Browse our jewellery collection below 👇"},
            "action": {
                "name": "catalog_message",
                "parameters": {
                    "thumbnail_product_retailer_id":
                        WHATSAPP_CATALOG_PRODUCT_RETAILER_ID
                }
            }
        }
    })

# =================================================
# Shopify Helpers
# =================================================
def normalize(phone):
    return ''.join(filter(str.isdigit, phone))[-10:]


def find_customer(phone):
    try:
        customers = shopify.Customer.search(query=f"phone:{phone}")
        for c in customers:
            if c.phone and normalize(c.phone) == normalize(phone):
                return c
    except Exception as e:
        app.logger.error(f"Shopify error: {e}")
    return None


def is_wholesale(customer):
    return "wholesale" in (customer.tags or "").lower()

# =================================================
# Razorpay
# =================================================
def create_payment_link(amount, phone):
    data = {
        "amount": amount,
        "currency": "INR",
        "description": "Jewellery Order Payment",
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

# =================================================
# ROUTES
# =================================================
@app.route("/", methods=["GET"])
def home():
    return "Bot Running Successfully"

@app.route("/webhook", methods=["GET", "POST"])
def webhook():

    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge"), 200
        return "Verification failed", 403

    data = request.get_json()

    if not data:
        return "No data", 200

    try:
        value = data["entry"][0]["changes"][0]["value"]

        # 🔥 IMPORTANT FIX — Ignore status updates
        if "messages" not in value:
            return "Status ignored", 200

        phone = value["contacts"][0]["wa_id"]
        msg = value["messages"][0]
        msg_type = msg["type"]

        # First interaction
        if phone not in user_state:
            customer = find_customer(phone)

            if not customer:
                send_cta(
                    phone,
                    "Please register first to continue.",
                    "Sign Up",
                    f"https://{SHOPIFY_STORE}/account/register"
                )
                user_state[phone] = {"flow": "new"}
                return "New user", 200

            user_state[phone] = {
                "flow": "wholesale" if is_wholesale(customer) else "retail"
            }

            if is_wholesale(customer):
                send_catalog(phone)
            else:
                send_buttons(
                    phone,
                    "Kya aap Custom Jewellery karvana chahte hain?",
                    [
                        {"id": "yes_custom", "title": "Yes"},
                        {"id": "no_custom", "title": "No"}
                    ]
                )
            return "Existing user", 200

        state = user_state.get(phone)

        # Button flow
        if msg_type == "button":
            payload = msg["button"]["payload"]

            if state["flow"] == "retail":
                if payload == "yes_custom":
                    send_cta(
                        phone,
                        "Book consultation below 👇",
                        "Book Now",
                        f"https://{SHOPIFY_STORE}/products/custom-jewellery-consultation"
                    )
                else:
                    send_catalog(phone)

        # Order flow
        if msg_type == "order":
            items = msg["order"]["product_items"]
            total = sum(
                float(i["item_price"]) * int(i["quantity"])
                for i in items
            )

            payment = create_payment_link(int(total * 100), phone)

            send_cta(
                phone,
                f"Total Amount: ₹{total}",
                "Pay Now",
                payment["short_url"]
            )

        return "OK", 200

    except Exception as e:
        app.logger.error(str(e))
        return "Server Error", 500

@app.route("/payment/webhook", methods=["POST"])
def payment_webhook():

    signature = request.headers.get("X-Razorpay-Signature")
    data = request.get_json()

    if not verify_signature(data, signature):
        return "Invalid signature", 400

    phone = order_map.get(data.get("razorpay_payment_link_id"))

    if data.get("razorpay_payment_link_status") == "paid":
        send_text(phone, "Payment Successful 🎉 Thank you!")
    else:
        send_text(phone, "Payment Failed ❌ Please try again.")

    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
