from flask import Flask, request, jsonify
import requests
import json
import os
import gspread
import razorpay
import hmac
import hashlib
from google.oauth2.service_account import Credentials
from datetime import datetime

app = Flask(__name__)

VERIFY_TOKEN      = os.environ.get("VERIFY_TOKEN", "ajewel2024")
ACCESS_TOKEN      = os.environ.get("ACCESS_TOKEN", "")
PHONE_NUMBER_ID   = "928999850307609"
SHEET_ID          = "1w-4Zi65AqsQZFJIr1GLrDrW9BJNez8Wtr-dTL8oBLbs"
SHOPIFY_REGISTER  = "https://a-jewel-studio-3.myshopify.com/account/register"
SHOPIFY_DOWNLOADS = "https://a-jewel-studio-3.myshopify.com/a/downloads"
CATALOG_LINK      = "https://wa.me/c/918141356990"
RZP_KEY_ID        = os.environ.get("RAZORPAY_KEY_ID", "")
RZP_KEY_SECRET    = os.environ.get("RAZORPAY_KEY_SECRET", "")
GEMINI_API_KEY    = os.environ.get("GEMINI_API_KEY", "")

rzp_client = razorpay.Client(auth=(RZP_KEY_ID, RZP_KEY_SECRET))

# ---- GEMINI AI ----
SYSTEM_PROMPTS = {
    "greeting": (
        "Tu A Jewel Studio ka professional WhatsApp assistant hai. Tera naam Akshay hai. "
        "Customer ko warmly welcome kar. Tone: Professional, warm, Hinglish. 2-3 lines max. Sirf text do."
    ),
    "registration": (
        "Tu A Jewel Studio ka WhatsApp assistant hai. Customer pehli baar aa raha hai. "
        "Politely batao ki order ke liye Shopify account banana zaroori hai. "
        "Tone: Professional, helpful, Hinglish. 3-4 lines max."
    ),
    "catalog": (
        "Tu A Jewel Studio ka WhatsApp assistant hai. Customer catalog dekhna chahta hai. "
        "Professionally invite karo collection dekhne ke liye. Tone: Warm, Hinglish. 2 lines max."
    ),
    "customer_type": (
        "Tu A Jewel Studio ka WhatsApp assistant hai. Customer order karna chahta hai. "
        "Politely customer type select karne ko kaho. Tone: Professional, Hinglish. 1-2 lines max."
    ),
    "retail_confirm": (
        "Tu A Jewel Studio ka WhatsApp assistant hai. Retail customer ka order receive hua. "
        "Professional thank you do. Batao team contact karegi design, pricing aur delivery ke liye. "
        "Tone: Warm, professional, Hinglish. 4-5 lines max."
    ),
    "b2b_payment": (
        "Tu A Jewel Studio ka WhatsApp assistant hai. B2B customer ka order payment ke liye ready hai. "
        "Professional message do. Tone: Professional, Hinglish. 2-3 lines max."
    ),
    "b2b_success": (
        "Tu A Jewel Studio ka WhatsApp assistant hai. B2B customer ki payment successful rahi. "
        "Warm thank you do aur batao files share ho gayi hain. Tone: Warm, professional, Hinglish. 3-4 lines max."
    ),
    "b2b_failed": (
        "Tu A Jewel Studio ka WhatsApp assistant hai. Customer ki payment fail hui. "
        "Politely retry karne ko kaho. Tone: Helpful, Hinglish. 2 lines max."
    ),
    "collect_name":    "Tu A Jewel Studio ka assistant hai. Customer se poora naam maango. Professional, friendly. 1 line.",
    "collect_phone":   "Tu A Jewel Studio ka assistant hai. Customer se 10 digit phone number maango. 1 line.",
    "collect_email":   "Tu A Jewel Studio ka assistant hai. Customer se email address maango. 1 line.",
    "collect_company": "Tu A Jewel Studio ka assistant hai. B2B customer se company naam maango. 1 line.",
    "collect_gst":     "Tu A Jewel Studio ka assistant hai. GST number maango. NA likh sakte hain agar nahi hai. 1 line.",
    "collect_address": "Tu A Jewel Studio ka assistant hai. Delivery address maango. 1 line.",
    "collect_city":    "Tu A Jewel Studio ka assistant hai. City naam maango. 1 line.",
    "general": (
        "Tu A Jewel Studio ka WhatsApp assistant hai. 3D jewellery designs bechta hai. "
        "Customer ke message ka professional Hinglish mein reply do. "
        "Agar samajh na aaye to 'Hi' type karne ko kaho. 3-4 lines max."
    ),
}

def gemini_reply(user_message, context="general", customer_name=""):
    try:
        prompt = SYSTEM_PROMPTS.get(context, SYSTEM_PROMPTS["general"])
        if customer_name:
            prompt += f" Customer ka naam: {customer_name}."

        url  = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        body = {
            "contents": [{"parts": [{"text": f"{prompt}\n\nCustomer: {user_message}"}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 200}
        }
        r      = requests.post(url, headers={"Content-Type": "application/json"}, json=body, timeout=10)
        result = r.json()
        return result["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"Gemini error: {e}")
        return None

# ---- GOOGLE SHEETS ----
def get_sheet():
    try:
        creds_dict = json.loads(os.environ.get("GOOGLE_CREDENTIALS", ""))
        scopes     = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds      = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client     = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID).sheet1
    except Exception as e:
        print(f"Sheet error: {e}")
        return None

def save_to_sheet(row_data):
    try:
        sheet = get_sheet()
        if sheet:
            sheet.append_row(row_data)
    except Exception as e:
        print(f"Save error: {e}")

def update_sheet_status(order_id, status):
    try:
        sheet = get_sheet()
        if sheet:
            cell = sheet.find(order_id)
            if cell:
                sheet.update_cell(cell.row, 15, status)
    except Exception as e:
        print(f"Update error: {e}")

# ---- HELPERS ----
def generate_order_id():
    return "AJS" + datetime.now().strftime("%d%m%y%H%M%S")

def create_razorpay_link(amount_inr, order_id, name, phone):
    try:
        data = {
            "amount": int(amount_inr * 100), "currency": "INR",
            "accept_partial": False,
            "description": f"A Jewel Studio Order {order_id}",
            "customer": {"name": name, "contact": phone},
            "notify": {"sms": False, "email": False},
            "reminder_enable": False,
            "notes": {"order_id": order_id},
            "callback_url": "https://ajewel-whatsapp-bot.onrender.com/payment-callback",
            "callback_method": "get"
        }
        return rzp_client.payment_link.create(data).get("short_url", "")
    except Exception as e:
        print(f"Razorpay error: {e}")
        return ""

# ---- SEND FUNCTIONS ----
def send_message(to, message):
    url  = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    hdrs = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    requests.post(url, headers=hdrs, json={"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": message}})

def send_button_message(to, body, buttons):
    url  = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    hdrs = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    requests.post(url, headers=hdrs, json={
        "messaging_product": "whatsapp", "to": to, "type": "interactive",
        "interactive": {
            "type": "button", "body": {"text": body},
            "action": {"buttons": [{"type": "reply", "reply": {"id": b["id"], "title": b["title"]}} for b in buttons]}
        }
    })

def send_cta_button(to, body, button_text, url_link):
    url  = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    hdrs = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    requests.post(url, headers=hdrs, json={
        "messaging_product": "whatsapp", "to": to, "type": "interactive",
        "interactive": {
            "type": "cta_url", "body": {"text": body},
            "action": {"name": "cta_url", "parameters": {"display_text": button_text, "url": url_link}}
        }
    })

# ---- FLOW ----
user_sessions = {}

def do_greeting(to):
    name   = user_sessions.get(to, {}).get("name", "")
    ai_msg = gemini_reply("Customer ne Hi/Hello bola.", "greeting", name) or \
             "Welcome to *A Jewel Studio*\nWhere Creativity Meets Craftsmanship.\n\nMenu select karein."
    user_sessions[to] = {"step": "greeted"}
    send_button_message(to, ai_msg, [{"id": "menu", "title": "Menu"}])

def do_registration(to):
    ai_msg = gemini_reply("Naya customer.", "registration") or \
             "Order ke liye Shopify account banana zaroori hai.\nRegistration ke baad 'Hi' type karein."
    send_cta_button(to, ai_msg, "Sign Up", SHOPIFY_REGISTER)

def do_catalog(to):
    ai_msg = gemini_reply("Customer catalog dekhna chahta hai.", "catalog") or \
             "Kindly explore our Exclusive Collection."
    send_cta_button(to, ai_msg, "View Catalog", CATALOG_LINK)

def do_customer_type(to):
    ai_msg = gemini_reply("Customer type select karna hai.", "customer_type") or \
             "Order process ke liye apna *Customer Type* select karein."
    send_button_message(to, ai_msg, [
        {"id": "retail", "title": "Retail Customer"},
        {"id": "b2b",    "title": "B2B / Wholesale"}
    ])

def do_retail_confirmation(to, session):
    order_id  = generate_order_id()
    name      = session.get("name", "")
    phone     = session.get("contact", "")
    email     = session.get("email", "")
    address   = session.get("address", "")
    city      = session.get("city", "")
    main_cat  = session.get("main_title", "")
    sub_cat   = session.get("sub_title", "")
    cart_text = ", ".join(session.get("cart_items", [])) or "-"

    ai_msg = gemini_reply(f"Retail order placed by {name}.", "retail_confirm", name) or \
             f"Thank you for choosing *A Jewel Studio*, {name} ji.\nHamari team jald hi contact karegi."
    send_message(to, ai_msg)

    save_to_sheet([datetime.now().strftime("%d-%m-%Y %H:%M:%S"), order_id, "Retail",
                   name, to, phone, email, "", "", address, city, main_cat, sub_cat, cart_text, "New"])

def do_b2b_payment(to, session):
    order_id  = generate_order_id()
    name      = session.get("name", "")
    phone     = session.get("contact", "")
    amount    = 500
    email     = session.get("email", "")
    company   = session.get("company", "")
    gst       = session.get("gst", "")
    address   = session.get("address", "")
    city      = session.get("city", "")
    main_cat  = session.get("main_title", "")
    sub_cat   = session.get("sub_title", "")
    cart_text = ", ".join(session.get("cart_items", [])) or "-"

    user_sessions[to].update({"order_id": order_id, "step": "payment_pending", "amount": amount})

    save_to_sheet([datetime.now().strftime("%d-%m-%Y %H:%M:%S"), order_id, "B2B",
                   name, to, phone, email, company, gst, address, city, main_cat, sub_cat, cart_text, "Payment Pending"])

    pay_link = create_razorpay_link(amount, order_id, name, phone)
    ai_msg   = gemini_reply(f"Order {order_id} payment ready.", "b2b_payment", name) or \
               f"Your Order *#{order_id}* is ready.\nKindly proceed to payment."

    if pay_link:
        send_cta_button(to, ai_msg, "Proceed to Payment", pay_link)
    else:
        send_message(to, "Payment link issue. Contact +91 76000 56655.")

def do_b2b_success(to, order_id, amount):
    name     = user_sessions.get(to, {}).get("name", "")
    date_str = datetime.now().strftime("%d/%m/%Y")
    ai_msg   = gemini_reply(f"Payment successful. Order {order_id}.", "b2b_success", name) or \
               "Payment Successfully Received.\nThank you for doing business with *A Jewel Studio*."
    full_msg = ai_msg + f"\n\n----------------------------------\n*Order ID:* #{order_id}\n*Amount:* Rs.{amount}\n*Date:* {date_str}\n----------------------------------"
    send_message(to, full_msg)
    send_cta_button(to, "Your digital files are ready. Click below to download.", "Download Now", SHOPIFY_DOWNLOADS)
    update_sheet_status(order_id, "Paid")

def do_b2b_failed(to, order_id, pay_link):
    name   = user_sessions.get(to, {}).get("name", "")
    ai_msg = gemini_reply("Payment fail hui.", "b2b_failed", name) or \
             "Your payment was not completed.\nKindly retry using the button below."
    send_cta_button(to, ai_msg, "Retry Payment", pay_link)
    update_sheet_status(order_id, "Payment Failed")

# ---- WEBHOOK ----
@app.route("/webhook", methods=["GET"])
def verify():
    mode, token, challenge = request.args.get("hub.mode"), request.args.get("hub.verify_token"), request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print(f"Incoming: {json.dumps(data)}")
    try:
        entry = data["entry"][0]["changes"][0]["value"]
        if "messages" not in entry:
            return jsonify({"status": "ok"}), 200

        msg         = entry["messages"][0]
        from_number = msg["from"]
        msg_type    = msg["type"]
        session     = user_sessions.get(from_number, {})

        if msg_type == "text":
            text = msg["text"]["body"].strip()

            if text.lower() in ["hi", "hello", "hii", "hey", "start", "namaste", "menu"]:
                do_greeting(from_number)

            elif session.get("step") == "waiting_name":
                user_sessions[from_number]["name"] = text
                user_sessions[from_number]["step"]  = "waiting_number"
                ai = gemini_reply("", "collect_phone") or "Kindly enter your *contact number* (10 digits):"
                send_message(from_number, ai)

            elif session.get("step") == "waiting_number":
                user_sessions[from_number]["contact"] = text
                user_sessions[from_number]["step"]    = "waiting_email"
                ai = gemini_reply("", "collect_email") or "Kindly enter your *email address*:"
                send_message(from_number, ai)

            elif session.get("step") == "waiting_email":
                user_sessions[from_number]["email"] = text
                if session.get("customer_type") == "b2b":
                    user_sessions[from_number]["step"] = "waiting_company"
                    ai = gemini_reply("", "collect_company") or "Kindly enter your *Company Name*:"
                else:
                    user_sessions[from_number]["step"] = "waiting_address"
                    ai = gemini_reply("", "collect_address") or "Kindly enter your *Delivery Address*:"
                send_message(from_number, ai)

            elif session.get("step") == "waiting_company":
                user_sessions[from_number]["company"] = text
                user_sessions[from_number]["step"]    = "waiting_gst"
                ai = gemini_reply("", "collect_gst") or "Kindly enter your *GST Number* (NA if not applicable):"
                send_message(from_number, ai)

            elif session.get("step") == "waiting_gst":
                user_sessions[from_number]["gst"]  = text
                user_sessions[from_number]["step"] = "waiting_address"
                ai = gemini_reply("", "collect_address") or "Kindly enter your *Business Address*:"
                send_message(from_number, ai)

            elif session.get("step") == "waiting_address":
                user_sessions[from_number]["address"] = text
                user_sessions[from_number]["step"]    = "waiting_city"
                ai = gemini_reply("", "collect_city") or "Kindly enter your *City*:"
                send_message(from_number, ai)

            elif session.get("step") == "waiting_city":
                user_sessions[from_number]["city"] = text
                final = dict(user_sessions.get(from_number, {}))
                final["city"] = text
                if final.get("customer_type") == "b2b":
                    do_b2b_payment(from_number, final)
                else:
                    user_sessions.pop(from_number, None)
                    do_retail_confirmation(from_number, final)

            else:
                ai = gemini_reply(text, "general") or "Namaste! Type 'Hi' to access the menu."
                send_message(from_number, ai)

        elif msg_type == "order":
            items = msg.get("order", {}).get("product_items", [])
            existing = user_sessions.get(from_number, {})
            existing["cart_items"] = [f"{i.get('product_name','Product')} x{i.get('quantity',1)}" for i in items]
            existing["step"]       = "customer_type"
            user_sessions[from_number] = existing
            do_customer_type(from_number)

        elif msg_type == "interactive":
            btn_id = msg["interactive"]["button_reply"]["id"]
            if btn_id == "menu":
                user_sessions[from_number] = user_sessions.get(from_number, {})
                user_sessions[from_number]["step"] = "catalog_sent"
                do_catalog(from_number)
            elif btn_id in ["retail", "b2b"]:
                user_sessions[from_number]["customer_type"] = btn_id
                user_sessions[from_number]["step"]          = "waiting_name"
                ai = gemini_reply("", "collect_name") or "Kindly enter your *full name*:"
                send_message(from_number, ai)

    except Exception as e:
        print(f"Error: {e}")

    return jsonify({"status": "ok"}), 200

@app.route("/payment-callback", methods=["GET"])
def payment_callback():
    try:
        rzp_pid    = request.args.get("razorpay_payment_id", "")
        rzp_plid   = request.args.get("razorpay_payment_link_id", "")
        rzp_sig    = request.args.get("razorpay_signature", "")
        rzp_status = request.args.get("razorpay_payment_link_status", "")

        for number, sess in list(user_sessions.items()):
            order_id = sess.get("order_id", "")
            if sess.get("step") == "payment_pending" and order_id:
                if rzp_status == "paid":
                    gen_sig = hmac.new(RZP_KEY_SECRET.encode(), f"{rzp_plid}|{rzp_pid}".encode(), hashlib.sha256).hexdigest()
                    if gen_sig == rzp_sig:
                        do_b2b_success(number, order_id, sess.get("amount", 500))
                        user_sessions.pop(number, None)
                else:
                    new_link = create_razorpay_link(sess.get("amount", 500), order_id, sess.get("name", ""), sess.get("contact", ""))
                    do_b2b_failed(number, order_id, new_link)
    except Exception as e:
        print(f"Callback error: {e}")
    return "OK", 200

@app.route("/razorpay-webhook", methods=["POST"])
def razorpay_webhook():
    try:
        payload = request.get_data()
        sig     = request.headers.get("X-Razorpay-Signature", "")
        gen_sig = hmac.new(RZP_KEY_SECRET.encode(), payload, hashlib.sha256).hexdigest()
        if gen_sig != sig:
            return "Invalid signature", 400
        event = request.get_json()
        if event.get("event") == "payment_link.paid":
            notes    = event["payload"]["payment_link"]["entity"].get("notes", {})
            order_id = notes.get("order_id", "")
            amount   = event["payload"]["payment_link"]["entity"].get("amount", 0) // 100
            for number, sess in list(user_sessions.items()):
                if sess.get("order_id") == order_id:
                    do_b2b_success(number, order_id, amount)
                    user_sessions.pop(number, None)
                    break
    except Exception as e:
        print(f"RZP Webhook error: {e}")
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
