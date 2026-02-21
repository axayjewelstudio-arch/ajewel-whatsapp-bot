from flask import Flask, request, jsonify
import requests
import json
import os
import gspread
import razorpay
from google.oauth2.service_account import Credentials
from datetime import datetime

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "ajewel2024")
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", "")
PHONE_NUMBER_ID = "928999850307609"
SHEET_ID = "1w-4Zi65AqsQZFJIr1GLrDrW9BJNez8Wtr-dTL8oBLbs"
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")

WHATSAPP_CATALOG = "https://wa.me/c/918141356990"

# ---- GOOGLE SHEETS ----
def get_sheet():
    try:
        creds_json = os.environ.get("GOOGLE_CREDENTIALS", "")
        creds_dict = json.loads(creds_json)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).sheet1
        return sheet
    except Exception as e:
        print(f"Sheet error: {e}")
        return None

def save_to_sheet(row_data):
    try:
        sheet = get_sheet()
        if sheet:
            sheet.append_row(row_data)
            print("Order saved to sheet!")
    except Exception as e:
        print(f"Save error: {e}")

def update_sheet_status(order_id, status):
    try:
        sheet = get_sheet()
        if sheet:
            cell = sheet.find(order_id)
            if cell:
                sheet.update_cell(cell.row, 15, status)
                print(f"Status updated: {order_id} -> {status}")
    except Exception as e:
        print(f"Status update error: {e}")

def generate_order_id():
    now = datetime.now()
    return f"AJS{now.strftime('%d%m%y%H%M%S')}"

# ---- RAZORPAY ----
def create_payment_link(order_id, amount, name, phone, email, description):
    try:
        client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        data = {
            "amount": int(amount * 100),  # paise mein
            "currency": "INR",
            "accept_partial": False,
            "description": description,
            "reference_id": order_id,
            "customer": {
                "name": name,
                "contact": phone,
                "email": email
            },
            "notify": {
                "sms": False,
                "email": False
            },
            "reminder_enable": False,
            "callback_url": f"https://ajewel-whatsapp-bot.onrender.com/payment-callback",
            "callback_method": "get"
        }
        result = client.payment_link.create(data)
        return result.get("short_url", "")
    except Exception as e:
        print(f"Razorpay error: {e}")
        return ""

user_sessions = {}

# ---- SEND FUNCTIONS ----
def send_message(to, message):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": message}}
    r = requests.post(url, headers=headers, json=data)
    print(f"Message: {r.status_code} {r.text}")

def send_main_categories(to):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {
        "messaging_product": "whatsapp", "to": to, "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": "A Jewel Studio"},
            "body": {"text": "A Jewel Studio mein aapka swagat hai!\nApni category select karein:"},
            "footer": {"text": "3D Jewellery Designs"},
            "action": {
                "button": "Category Dekho",
                "sections": [{
                    "title": "Main Categories",
                    "rows": [
                        {"id": "face",  "title": "Face Jewellery",      "description": "Ear, Nose, Head, Lip and Eye"},
                        {"id": "neck",  "title": "Neck Jewellery",      "description": "Haar, Necklace, Pendant, Sets"},
                        {"id": "hand",  "title": "Hand Jewellery",      "description": "Bangles, Kada, Rings, Bracelet"},
                        {"id": "lower", "title": "Lower Body",          "description": "Payal, Bichhiya, Kamarband"},
                        {"id": "murti", "title": "Murti and Figurines", "description": "Hindu Gods, Animals, Mix"},
                        {"id": "baby",  "title": "Baby Jewellery",      "description": "Bangles, Anklets, Rings, Chain"}
                    ]
                }]
            }
        }
    }
    r = requests.post(url, headers=headers, json=data)
    print(f"Main cat: {r.status_code}")

def send_sub_categories(to, main_cat):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}

    sub_map = {
        "face":  [
            {"id": "face_ear",  "title": "Ear Jewellery",        "description": "Studs, Jhumka, Chandbali, Hoops"},
            {"id": "face_nose", "title": "Nose Jewellery",       "description": "Nath, Nathni, Laung, Septum"},
            {"id": "face_head", "title": "Head Jewellery",       "description": "Maang Tikka, Passa, Sheesh Phool"},
            {"id": "face_lip",  "title": "Lip and Eye",          "description": "Lip Pin, Eye Pin, Eyebrow Ring"},
        ],
        "neck":  [
            {"id": "neck_trad", "title": "Traditional Haar",     "description": "Kanthi, Mag Mala, Long Haar"},
            {"id": "neck_mod",  "title": "Modern Necklace",      "description": "Choker, Chains, Statement"},
            {"id": "neck_pend", "title": "Pendant and Butti",    "description": "Tanmanya, Locket, Nameplate"},
            {"id": "neck_set",  "title": "Special Sets",         "description": "Mangalsutra, Bridal Sets"},
        ],
        "hand":  [
            {"id": "hand_bangle",   "title": "Bangdi and Bangle",   "description": "Plain, Designer, Openable"},
            {"id": "hand_kada",     "title": "Kada",                "description": "Plain, Designer, Religious"},
            {"id": "hand_bracelet", "title": "Bracelet",            "description": "Chain, Tennis, Kaida"},
            {"id": "hand_baju",     "title": "Baju Band and Panja", "description": "Armlet, Haath Panja"},
            {"id": "hand_rings",    "title": "Rings",               "description": "Solitaire, Band, Traditional"},
        ],
        "lower": [
            {"id": "lower_payal", "title": "Payal and Anklet",      "description": "Traditional, Modern, Todi"},
            {"id": "lower_bich",  "title": "Bichhiya and Toe Ring", "description": "Traditional, Modern, Pag Panja"},
            {"id": "lower_kamar", "title": "Kamarband and Waist",   "description": "Kandora, Waist Chain, Belt"},
        ],
        "murti": [
            {"id": "murti_god",    "title": "Hindu God Murti",  "description": "Ganesh, Laxmi, Shiva, Krishna"},
            {"id": "murti_animal", "title": "Animal Murti",     "description": "Sacred, Royal, Birds, Aquatic"},
            {"id": "murti_mix",    "title": "Mix Designs",      "description": "Abstract, Tribal, Decorative"},
        ],
        "baby":  [
            {"id": "baby_bangle",  "title": "Baby Bangles and Kada",  "description": "Plain, Designer, Sets"},
            {"id": "baby_anklet",  "title": "Baby Anklets and Payal", "description": "Traditional, Modern"},
            {"id": "baby_rings",   "title": "Baby Rings",             "description": "Plain, Designer"},
            {"id": "baby_chain",   "title": "Baby Necklace and Chain","description": "Plain, Designer"},
            {"id": "baby_earring", "title": "Baby Earrings",          "description": "Studs, Small Jhumki"},
            {"id": "baby_hair",    "title": "Baby Hair Accessories",  "description": "Clips, Pins, Bands"},
        ],
    }

    rows = sub_map.get(main_cat, [])
    data = {
        "messaging_product": "whatsapp", "to": to, "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": "A Jewel Studio"},
            "body": {"text": "Ab sub category select karein:"},
            "footer": {"text": "3D Jewellery Designs"},
            "action": {
                "button": "Sub Category",
                "sections": [{"title": "Sub Categories", "rows": rows}]
            }
        }
    }
    r = requests.post(url, headers=headers, json=data)
    print(f"Sub cat: {r.status_code}")

def send_customer_type(to):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {
        "messaging_product": "whatsapp", "to": to, "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": "Aap kaun hain? Please select karein:"},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "retail", "title": "Retail Customer"}},
                    {"type": "reply", "reply": {"id": "b2b",    "title": "B2B / Wholesaler"}}
                ]
            }
        }
    }
    r = requests.post(url, headers=headers, json=data)
    print(f"Customer type: {r.status_code}")

# ---- WEBHOOK ----
@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print(f"Webhook: {json.dumps(data)}")
    try:
        entry = data["entry"][0]["changes"][0]["value"]
        if "messages" not in entry:
            return jsonify({"status": "ok"}), 200

        msg = entry["messages"][0]
        from_number = msg["from"]
        msg_type = msg["type"]
        session = user_sessions.get(from_number, {})

        if msg_type == "text":
            text = msg["text"]["body"].strip()
            text_lower = text.lower()
            step = session.get("step", "")

            if text_lower in ["hi", "hello", "hii", "hey", "start", "menu"]:
                user_sessions[from_number] = {}
                send_main_categories(from_number)

            elif step == "waiting_design":
                user_sessions[from_number]["design_code"] = text.upper()
                user_sessions[from_number]["step"] = "waiting_customer_type"
                send_customer_type(from_number)

            elif step == "waiting_name":
                user_sessions[from_number]["name"] = text
                user_sessions[from_number]["step"] = "waiting_phone"
                send_message(from_number, "Apna contact number batayein:")

            elif step == "waiting_phone":
                user_sessions[from_number]["phone"] = text
                user_sessions[from_number]["step"] = "waiting_email"
                send_message(from_number, "Apni email ID batayein:")

            elif step == "waiting_email":
                user_sessions[from_number]["email"] = text
                ctype = session.get("customer_type", "retail")
                if ctype == "retail":
                    user_sessions[from_number]["step"] = "waiting_address"
                    send_message(from_number, "Apna delivery address batayein (House No, Street, Area):")
                else:
                    user_sessions[from_number]["step"] = "waiting_company"
                    send_message(from_number, "Apni Company ya Shop ka naam batayein:")

            elif step == "waiting_address":
                user_sessions[from_number]["address"] = text
                user_sessions[from_number]["step"] = "waiting_city"
                send_message(from_number, "City aur Pincode batayein:")

            elif step == "waiting_city":
                user_sessions[from_number]["city"] = text
                s = user_sessions[from_number]
                order_id = generate_order_id()
                user_sessions[from_number]["order_id"] = order_id

                save_to_sheet([
                    datetime.now().strftime("%d-%m-%Y %H:%M"),
                    order_id,
                    "Retail Customer",
                    s.get("name", ""),
                    from_number,
                    s.get("phone", ""),
                    s.get("email", ""),
                    "",
                    "",
                    s.get("address", ""),
                    s.get("city", ""),
                    s.get("main_cat", ""),
                    s.get("sub_cat", ""),
                    s.get("design_code", ""),
                    "Pending Payment"
                ])

                # Razorpay payment link banao
                payment_link = create_payment_link(
                    order_id=order_id,
                    amount=299,  # Default amount — baad mein dynamic kar sakte hain
                    name=s.get("name", ""),
                    phone=s.get("phone", from_number),
                    email=s.get("email", ""),
                    description=f"A Jewel Studio - {s.get('design_code','')} - 3D Design File"
                )

                if payment_link:
                    send_message(from_number,
                        f"Namaste {s.get('name', '')} ji,\n\n"
                        f"Aapka order receive ho gaya hai!\n\n"
                        f"--- Order Details ---\n"
                        f"Order ID     : {order_id}\n"
                        f"Design Code  : {s.get('design_code','')}\n"
                        f"Amount       : Rs. 299\n\n"
                        f"Payment karne ke liye neeche diye link par click karein:\n"
                        f"{payment_link}\n\n"
                        f"Payment hone ke baad aapko design file ka download link mil jaayega.\n\n"
                        f"Koi bhi sawaal ho:\n"
                        f"WhatsApp / Call : +91 76000 56655\n"
                        f"Email           : ajewelstudio@gmail.com\n\n"
                        f"Dhanyawad!\nTeam A Jewel Studio"
                    )
                else:
                    # Payment link nahi bana toh manual review
                    send_message(from_number,
                        f"Namaste {s.get('name', '')} ji,\n\n"
                        f"Aapka order hamare team ko mil gaya hai!\n\n"
                        f"--- Order Details ---\n"
                        f"Order ID     : {order_id}\n"
                        f"Design Code  : {s.get('design_code','')}\n"
                        f"Customer Type: Retail\n\n"
                        f"Hamari team thodi der mein aapse contact karegi - "
                        f"pricing, payment aur delivery ke baare mein.\n\n"
                        f"Koi bhi sawaal ho:\n"
                        f"WhatsApp / Call : +91 76000 56655\n"
                        f"Email           : ajewelstudio@gmail.com\n\n"
                        f"Aapka vishwas humare liye bahut mayne rakhta hai.\n"
                        f"Dhanyawad!\nTeam A Jewel Studio"
                    )
                user_sessions.pop(from_number, None)

            # ---- B2B FLOW ----
            elif step == "waiting_company":
                user_sessions[from_number]["company"] = text
                user_sessions[from_number]["step"] = "waiting_gst"
                send_message(from_number, "GST Number batayein (nahi hai to NA likhein):")

            elif step == "waiting_gst":
                user_sessions[from_number]["gst"] = text
                user_sessions[from_number]["step"] = "waiting_b2b_address"
                send_message(from_number, "Business address batayein:")

            elif step == "waiting_b2b_address":
                user_sessions[from_number]["address"] = text
                user_sessions[from_number]["step"] = "waiting_b2b_city"
                send_message(from_number, "City aur Pincode batayein:")

            elif step == "waiting_b2b_city":
                user_sessions[from_number]["city"] = text
                s = user_sessions[from_number]
                order_id = generate_order_id()

                save_to_sheet([
                    datetime.now().strftime("%d-%m-%Y %H:%M"),
                    order_id,
                    "B2B / Wholesaler",
                    s.get("name", ""),
                    from_number,
                    s.get("phone", ""),
                    s.get("email", ""),
                    s.get("company", ""),
                    s.get("gst", ""),
                    s.get("address", ""),
                    s.get("city", ""),
                    s.get("main_cat", ""),
                    s.get("sub_cat", ""),
                    s.get("design_code", ""),
                    "Pending"
                ])

                # B2B ke liye manual contact — file aur pricing discuss hogi
                send_message(from_number,
                    f"Namaste {s.get('name', '')} ji,\n\n"
                    f"A Jewel Studio ke saath B2B inquiry karne ke liye bahut bahut shukriya!\n\n"
                    f"--- Order Details ---\n"
                    f"Order ID      : {order_id}\n"
                    f"Company       : {s.get('company','')}\n"
                    f"GST Number    : {s.get('gst','')}\n"
                    f"Design Code   : {s.get('design_code','')}\n"
                    f"Customer Type : B2B / Wholesaler\n\n"
                    f"Hamari B2B team 24 ghante ke andar aapse contact karegi - "
                    f"pricing, MOQ aur design file ke baare mein.\n\n"
                    f"Koi bhi sawaal ho:\n"
                    f"WhatsApp / Call : +91 76000 56655\n"
                    f"Email           : ajewelstudio@gmail.com\n\n"
                    f"Aapki partnership hamare liye bahut important hai.\n"
                    f"Dhanyawad!\nTeam A Jewel Studio"
                )
                user_sessions.pop(from_number, None)

            else:
                send_message(from_number, "Namaste! Menu ke liye Hi likho.")

        elif msg_type == "interactive":
            interactive = msg["interactive"]

            if interactive["type"] == "list_reply":
                selected_id = interactive["list_reply"]["id"]
                selected_title = interactive["list_reply"]["title"]

                if selected_id in ["face", "neck", "hand", "lower", "murti", "baby"]:
                    user_sessions[from_number] = {"main_cat": selected_id, "step": "sub_cat"}
                    send_sub_categories(from_number, selected_id)
                else:
                    user_sessions[from_number]["sub_cat"] = selected_id
                    user_sessions[from_number]["step"] = "waiting_design"
                    send_message(from_number,
                        f"Aapne select kiya: {selected_title}\n\n"
                        f"Hamara WhatsApp catalog dekho:\n{WHATSAPP_CATALOG}\n\n"
                        f"Catalog dekh kar apna Design Code enter karein\n"
                        f"(Example: FACE-EAR-STUDS-001):"
                    )

            elif interactive["type"] == "button_reply":
                button_id = interactive["button_reply"]["id"]
                if button_id in ["retail", "b2b"]:
                    user_sessions[from_number]["customer_type"] = button_id
                    user_sessions[from_number]["step"] = "waiting_name"
                    send_message(from_number, "Apna poora naam batayein:")

    except Exception as e:
        print(f"Error: {e}")

    return jsonify({"status": "ok"}), 200

# ---- PAYMENT CALLBACK ----
@app.route("/payment-callback", methods=["GET"])
def payment_callback():
    payment_id = request.args.get("razorpay_payment_id", "")
    payment_link_id = request.args.get("razorpay_payment_link_id", "")
    reference_id = request.args.get("razorpay_payment_link_reference_id", "")
    status = request.args.get("razorpay_payment_link_status", "")

    print(f"Payment callback: {payment_id} | {reference_id} | {status}")

    if status == "paid" and reference_id:
        # Sheet mein status update karo
        update_sheet_status(reference_id, "Paid")
        print(f"Payment successful: {reference_id}")

    return "Payment processed!", 200

# ---- RAZORPAY WEBHOOK ----
@app.route("/razorpay-webhook", methods=["POST"])
def razorpay_webhook():
    data = request.get_json()
    print(f"Razorpay webhook: {json.dumps(data)}")
    try:
        event = data.get("event", "")
        if event == "payment_link.paid":
            payload = data["payload"]["payment_link"]["entity"]
            order_id = payload.get("reference_id", "")
            customer = payload.get("customer", {})
            phone = customer.get("contact", "")

            # Sheet status update
            update_sheet_status(order_id, "Paid")

            # Customer ko download link bhejo
            if phone:
                whatsapp_number = phone.replace("+", "").replace(" ", "")
                send_message(whatsapp_number,
                    f"Payment receive ho gayi! Bahut shukriya!\n\n"
                    f"Order ID: {order_id}\n\n"
                    f"Aapki 3D design file ready hai.\n"
                    f"Hamari team aapko download link bhejegi.\n\n"
                    f"Koi bhi sawaal ho:\n"
                    f"WhatsApp / Call : +91 76000 56655\n"
                    f"Email           : ajewelstudio@gmail.com\n\n"
                    f"Dhanyawad!\nTeam A Jewel Studio"
                )

    except Exception as e:
        print(f"Razorpay webhook error: {e}")

    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
