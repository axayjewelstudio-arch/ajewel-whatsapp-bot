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

# Razorpay client
rzp_client = razorpay.Client(auth=(RZP_KEY_ID, RZP_KEY_SECRET))

# ---- GOOGLE SHEETS ----
def get_sheet():
    try:
        creds_json = os.environ.get("GOOGLE_CREDENTIALS", "")
        creds_dict = json.loads(creds_json)
        scopes     = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds  = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        sheet  = client.open_by_key(SHEET_ID).sheet1
        return sheet
    except Exception as e:
        print(f"Sheet error: {e}")
        return None

def is_existing_customer(whatsapp_number):
    try:
        sheet = get_sheet()
        if sheet:
            numbers = sheet.col_values(5)  # Column E = WhatsApp Number
            return whatsapp_number in numbers
    except Exception as e:
        print(f"Check error: {e}")
    return False

def save_to_sheet(row_data):
    try:
        sheet = get_sheet()
        if sheet:
            sheet.append_row(row_data)
            print("Saved to sheet!")
    except Exception as e:
        print(f"Save error: {e}")

def update_sheet_status(order_id, status):
    try:
        sheet = get_sheet()
        if sheet:
            cell = sheet.find(order_id)
            if cell:
                sheet.update_cell(cell.row, 15, status)  # Column O = Status
    except Exception as e:
        print(f"Update error: {e}")

# ---- ORDER ID ----
def generate_order_id():
    return "AJS" + datetime.now().strftime("%d%m%y%H%M%S")

# ---- RAZORPAY ----
def create_razorpay_link(amount_inr, order_id, customer_name, customer_phone):
    try:
        data = {
            "amount": int(amount_inr * 100),  # paise mein
            "currency": "INR",
            "accept_partial": False,
            "description": f"A Jewel Studio Order {order_id}",
            "customer": {
                "name": customer_name,
                "contact": customer_phone,
            },
            "notify": {"sms": False, "email": False},
            "reminder_enable": False,
            "notes": {"order_id": order_id},
            "callback_url": "https://ajewel-whatsapp-bot.onrender.com/payment-callback",
            "callback_method": "get"
        }
        link = rzp_client.payment_link.create(data)
        return link.get("short_url", "")
    except Exception as e:
        print(f"Razorpay error: {e}")
        return ""

# ---- SEND FUNCTIONS ----
def send_message(to, message):
    url     = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data    = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": message}}
    r       = requests.post(url, headers=headers, json=data)
    print(f"send_message: {r.status_code}")

def send_button_message(to, body, buttons):
    url     = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data    = {
        "messaging_product": "whatsapp", "to": to, "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": b["id"], "title": b["title"]}}
                    for b in buttons
                ]
            }
        }
    }
    r = requests.post(url, headers=headers, json=data)
    print(f"send_button: {r.status_code}")

def send_cta_button(to, body, button_text, url_link):
    url     = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data    = {
        "messaging_product": "whatsapp", "to": to, "type": "interactive",
        "interactive": {
            "type": "cta_url",
            "body": {"text": body},
            "action": {
                "name": "cta_url",
                "parameters": {"display_text": button_text, "url": url_link}
            }
        }
    }
    r = requests.post(url, headers=headers, json=data)
    print(f"send_cta: {r.status_code}")

# ---- FLOW STEPS ----
def send_greeting(to):
    send_button_message(
        to,
        "💎 A Jewel Studio mein aapka swagat hai!\n"
        "Jahan Creativity milti hai Craftsmanship se.\n\n"
        "Namaste! Main Akshay hoon. 🙏\n"
        "A Jewel Studio visit karne ke liye\n"
        "aapka dil se dhanyavaad.\n\n"
        "Aage badhne ke liye niche Menu select karein:",
        [{"id": "menu", "title": "Menu"}]
    )

def send_registration(to):
    send_cta_button(
        to,
        "👋 Lagta hai aap pehli baar aa rahe hain!\n\n"
        "Smooth aur personalized experience ke liye\n"
        "hum aapko account create karne ki salah dete hain.\n\n"
        "✅ Registered customers ko milta hai:\n"
        "   • Faster order processing\n"
        "   • Easy order tracking\n"
        "   • Latest designs par priority updates\n\n"
        "Niche Sign Up karein aur wapas aakar\n"
        "'Hi' type karein — hum ready hain! 😊",
        "Sign Up",
        SHOPIFY_REGISTER
    )

def send_catalog(to):
    send_cta_button(
        to,
        "💍 Hamari exclusive collection explore karein!\n\n"
        "Niche button click karein aur apni\n"
        "pasandida category chunein.",
        "View Catalog",
        CATALOG_LINK
    )

def send_customer_type(to):
    send_button_message(
        to,
        "Aapka order process karne ke liye\n"
        "hum aapka customer type jaanna chahte hain.\n\n"
        "Kripya niche se select karein: 👇",
        [
            {"id": "retail", "title": "Retail Customer"},
            {"id": "b2b",    "title": "B2B / Wholesale"}
        ]
    )

# ---- RETAIL CONFIRMATION ----
def send_retail_confirmation(to, session):
    order_id  = generate_order_id()
    name      = session.get("name", "")
    main_cat  = session.get("main_title", "")
    sub_cat   = session.get("sub_title", "")
    phone     = session.get("contact", "")
    email     = session.get("email", "")
    address   = session.get("address", "")
    city      = session.get("city", "")
    cart      = session.get("cart_items", [])
    cart_text = ", ".join(cart) if cart else "-"

    msg = (
        "✨ A Jewel Studio ko choose karne ke\n"
        "liye aapka bahut bahut dhanyavaad!\n\n"
        "Aapki order request hume successfully\n"
        "mil gayi hai.\n\n"
        "Hamari team jald hi aapse contact karegi\n"
        "taaki ye confirm ho sake:\n"
        "   • Design selection\n"
        "   • Pricing details\n"
        "   • Delivery timeline\n\n"
        "Hum aapko premium craftsmanship aur\n"
        "ek seamless buying experience dene ke\n"
        "liye poori tarah pratibaddh hain. 🙏\n\n"
        "Aapke bharose ke liye hum aabhari hain!"
    )
    send_message(to, msg)

    now_str = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    save_to_sheet([
        now_str, order_id, "Retail", name, to, phone, email,
        "", "", address, city, main_cat, sub_cat, cart_text, "New"
    ])

# ---- B2B PAYMENT LINK ----
def send_b2b_payment(to, session):
    order_id = generate_order_id()
    name     = session.get("name", "")
    phone    = session.get("contact", "")
    amount   = 500  # Default — baad mein dynamic karenge

    # Store order_id in session for webhook
    user_sessions[to]["order_id"] = order_id
    user_sessions[to]["step"]     = "payment_pending"

    # Save to sheet with Pending status
    now_str  = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    main_cat = session.get("main_title", "")
    sub_cat  = session.get("sub_title", "")
    email    = session.get("email", "")
    company  = session.get("company", "")
    gst      = session.get("gst", "")
    address  = session.get("address", "")
    city     = session.get("city", "")
    cart     = session.get("cart_items", [])
    cart_text = ", ".join(cart) if cart else "-"

    save_to_sheet([
        now_str, order_id, "B2B", name, to, phone, email,
        company, gst, address, city, main_cat, sub_cat, cart_text, "Payment Pending"
    ])

    # Create Razorpay payment link
    pay_link = create_razorpay_link(amount, order_id, name, phone)

    if pay_link:
        send_cta_button(
            to,
            f"💳 Aapka order ready hai!\n\n"
            f"Order ID : #{order_id}\n\n"
            f"Niche button click karke\n"
            f"secure payment karein:",
            "Payment Karein",
            pay_link
        )
    else:
        send_message(to, "Payment link generate karne mein problem aayi. Kripya +91 76000 56655 par contact karein.")

# ---- B2B PAYMENT SUCCESS ----
def send_b2b_success(to, order_id, amount):
    now      = datetime.now()
    date_str = now.strftime("%d/%m/%Y")

    msg = (
        "✅ Payment Successfully Received!\n\n"
        "A Jewel Studio mein shopping karne ke\n"
        "liye aapka dhanyavaad. 🙏\n\n"
        "Aapki selected design ki 3D digital file\n"
        "aapke registered Email ID aur WhatsApp\n"
        "number par successfully share kar\n"
        "di gayi hai. 📩\n\n"
        "Kripya niche apna invoice dekhein. 👇\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🧾 Order ID   : #{order_id}\n"
        f"💰 Amount     : ₹{amount}\n"
        f"📅 Date       : {date_str}\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "A Jewel Studio ki poori team hamesha\n"
        "aapki seva ke liye tatpar hai.\n\n"
        "Aapke saath kaam karke humein sachchi\n"
        "khushi hoti hai. Dobara swagat hai! 💎"
    )
    send_message(to, msg)

    # Send Download Now button
    send_cta_button(
        to,
        "Aapki digital files ready hain! 📦\n"
        "Niche button click karke download karein:",
        "Download Now",
        SHOPIFY_DOWNLOADS
    )

    update_sheet_status(order_id, "Paid")

# ---- B2B PAYMENT FAILED ----
def send_b2b_failed(to, order_id, pay_link):
    send_cta_button(
        to,
        "❌ Aapki payment complete nahi hui.\n\n"
        "Kripya dobara try karein —\n"
        "aapka order abhi bhi active hai. 😊",
        "Dobara Try Karein",
        pay_link
    )
    update_sheet_status(order_id, "Payment Failed")

# ---- SESSION STORE ----
user_sessions = {}

# ---- FLASK ROUTES ----
@app.route("/webhook", methods=["GET"])
def verify():
    mode      = request.args.get("hub.mode")
    token     = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
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

        # ---- TEXT ----
        if msg_type == "text":
            text = msg["text"]["body"].strip()

            if text.lower() in ["hi", "hello", "hii", "hey", "start", "namaste", "menu"]:
                user_sessions[from_number] = {"step": "greeted"}
                send_greeting(from_number)

            elif session.get("step") == "waiting_name":
                user_sessions[from_number]["name"] = text
                user_sessions[from_number]["step"] = "waiting_number"
                send_message(from_number, "Aapka *contact number* likhein (10 digit):")

            elif session.get("step") == "waiting_number":
                user_sessions[from_number]["contact"] = text
                user_sessions[from_number]["step"]    = "waiting_email"
                send_message(from_number, "Aapka *email address* likhein:")

            elif session.get("step") == "waiting_email":
                user_sessions[from_number]["email"] = text
                ctype = session.get("customer_type", "retail")
                if ctype == "b2b":
                    user_sessions[from_number]["step"] = "waiting_company"
                    send_message(from_number, "Aapki *company ka naam* likhein:")
                else:
                    user_sessions[from_number]["step"] = "waiting_address"
                    send_message(from_number, "Aapka *delivery address* likhein:\n(Ghar/Shop ka pura address)")

            elif session.get("step") == "waiting_company":
                user_sessions[from_number]["company"] = text
                user_sessions[from_number]["step"]    = "waiting_gst"
                send_message(from_number, "Aapka *GST Number* likhein:\n(Nahi hai toh 'NA' likhein)")

            elif session.get("step") == "waiting_gst":
                user_sessions[from_number]["gst"]  = text
                user_sessions[from_number]["step"] = "waiting_address"
                send_message(from_number, "Aapka *delivery address* likhein:\n(Company/Shop ka pura address)")

            elif session.get("step") == "waiting_address":
                user_sessions[from_number]["address"] = text
                user_sessions[from_number]["step"]    = "waiting_city"
                send_message(from_number, "Aapka *sheher (city)* likhein:")

            elif session.get("step") == "waiting_city":
                user_sessions[from_number]["city"] = text
                final_session = dict(user_sessions.get(from_number, {}))
                final_session["city"] = text
                if final_session.get("customer_type") == "b2b":
                    send_b2b_payment(from_number, final_session)
                else:
                    user_sessions.pop(from_number, None)
                    send_retail_confirmation(from_number, final_session)

            else:
                send_message(from_number, "Namaste! Menu ke liye 'Hi' likhein. 😊")

        # ---- ORDER (Send to business) ----
        elif msg_type == "order":
            order_data = msg.get("order", {})
            items      = order_data.get("product_items", [])
            item_list  = []
            for item in items:
                pname = item.get("product_name", "Product")
                qty   = item.get("quantity", 1)
                item_list.append(f"{pname} x{qty}")

            existing               = user_sessions.get(from_number, {})
            existing["cart_items"] = item_list

            if is_existing_customer(from_number):
                existing["step"]           = "customer_type"
                user_sessions[from_number] = existing
                send_customer_type(from_number)
            else:
                existing["step"]           = "waiting_registration"
                user_sessions[from_number] = existing
                send_registration(from_number)

        # ---- INTERACTIVE ----
        elif msg_type == "interactive":
            interactive = msg["interactive"]

            if interactive["type"] == "button_reply":
                button_id = interactive["button_reply"]["id"]

                if button_id == "menu":
                    if is_existing_customer(from_number):
                        user_sessions[from_number] = {"step": "catalog_sent"}
                        send_catalog(from_number)
                    else:
                        user_sessions[from_number] = {"step": "waiting_registration"}
                        send_registration(from_number)

                elif button_id in ["retail", "b2b"]:
                    ctype = "retail" if button_id == "retail" else "b2b"
                    user_sessions[from_number]["customer_type"] = ctype
                    user_sessions[from_number]["step"]          = "waiting_name"
                    send_message(from_number, "Aapka *poora naam* likhein please: 😊")

    except Exception as e:
        print(f"Error: {e}")

    return jsonify({"status": "ok"}), 200

# ---- RAZORPAY PAYMENT CALLBACK ----
@app.route("/payment-callback", methods=["GET"])
def payment_callback():
    try:
        rzp_payment_id   = request.args.get("razorpay_payment_id", "")
        rzp_payment_link = request.args.get("razorpay_payment_link_id", "")
        rzp_signature    = request.args.get("razorpay_signature", "")
        rzp_status       = request.args.get("razorpay_payment_link_status", "")

        # Find customer by order from sessions
        for number, session in list(user_sessions.items()):
            order_id = session.get("order_id", "")
            if session.get("step") == "payment_pending" and order_id:

                if rzp_status == "paid":
                    # Verify signature
                    msg_str  = f"{rzp_payment_link}|{rzp_payment_id}"
                    gen_sig  = hmac.new(RZP_KEY_SECRET.encode(), msg_str.encode(), hashlib.sha256).hexdigest()
                    if gen_sig == rzp_signature:
                        amount = session.get("amount", 500)
                        send_b2b_success(number, order_id, amount)
                        user_sessions.pop(number, None)
                else:
                    # Payment failed — resend payment link
                    name  = session.get("name", "")
                    phone = session.get("contact", "")
                    amount = session.get("amount", 500)
                    new_link = create_razorpay_link(amount, order_id, name, phone)
                    send_b2b_failed(number, order_id, new_link)

    except Exception as e:
        print(f"Callback error: {e}")

    return "OK", 200

# ---- RAZORPAY WEBHOOK ----
@app.route("/razorpay-webhook", methods=["POST"])
def razorpay_webhook():
    try:
        payload   = request.get_data()
        signature = request.headers.get("X-Razorpay-Signature", "")
        gen_sig   = hmac.new(RZP_KEY_SECRET.encode(), payload, hashlib.sha256).hexdigest()

        if gen_sig != signature:
            return "Invalid signature", 400

        event = request.get_json()
        print(f"RZP Webhook: {json.dumps(event)}")

        if event.get("event") == "payment_link.paid":
            notes    = event["payload"]["payment_link"]["entity"].get("notes", {})
            order_id = notes.get("order_id", "")
            amount   = event["payload"]["payment_link"]["entity"].get("amount", 0) // 100

            # Find customer
            for number, session in list(user_sessions.items()):
                if session.get("order_id") == order_id:
                    send_b2b_success(number, order_id, amount)
                    user_sessions.pop(number, None)
                    break

    except Exception as e:
        print(f"RZP Webhook error: {e}")

    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
