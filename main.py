from flask import Flask, request, jsonify
import requests
import json
import os
import threading
import time

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "ajewel2024")
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", "")
PHONE_NUMBER_ID = "928999850307609"

# Main Category Catalog Links
CATALOG_LINKS = {
    "face": "https://a-jewel-studio-3.myshopify.com/collections/face-jewellery",
    "neck": "https://a-jewel-studio-3.myshopify.com/collections/neck-jewellery",
    "hand": "https://a-jewel-studio-3.myshopify.com/collections/hand-jewellery",
    "lower": "https://a-jewel-studio-3.myshopify.com/collections/lower-body-jewellery",
    "murti": "https://a-jewel-studio-3.myshopify.com/collections/murti-figurines",
    "baby": "https://a-jewel-studio-3.myshopify.com/collections/baby-jewellery"
}

# Sub Category Catalog Links
SUB_CATALOG_LINKS = {
    "face_ear": "https://a-jewel-studio-3.myshopify.com/collections/face-ear-jewellery",
    "face_nose": "https://a-jewel-studio-3.myshopify.com/collections/face-nose-jewellery",
    "face_head": "https://a-jewel-studio-3.myshopify.com/collections/face-head-jewellery",
    "face_lip": "https://a-jewel-studio-3.myshopify.com/collections/face-lip-eye-jewellery",
    "neck_traditional": "https://a-jewel-studio-3.myshopify.com/collections/neck-traditional-haar",
    "neck_modern": "https://a-jewel-studio-3.myshopify.com/collections/neck-modern-necklace",
    "neck_pendant": "https://a-jewel-studio-3.myshopify.com/collections/neck-pendant-butti",
    "neck_sets": "https://a-jewel-studio-3.myshopify.com/collections/neck-special-sets",
    "hand_bangle": "https://a-jewel-studio-3.myshopify.com/collections/hand-bangdi-bangle",
    "hand_kada": "https://a-jewel-studio-3.myshopify.com/collections/hand-kada",
    "hand_bracelet": "https://a-jewel-studio-3.myshopify.com/collections/hand-bracelet",
    "hand_baju": "https://a-jewel-studio-3.myshopify.com/collections/hand-baju-band-haath-panja",
    "hand_rings": "https://a-jewel-studio-3.myshopify.com/collections/hand-rings",
    "lower_payal": "https://a-jewel-studio-3.myshopify.com/collections/lower-payal-anklet",
    "lower_bichhiya": "https://a-jewel-studio-3.myshopify.com/collections/lower-bichhiya-toe-ring",
    "lower_kamarband": "https://a-jewel-studio-3.myshopify.com/collections/lower-kamarband-waist",
    "murti_god": "https://a-jewel-studio-3.myshopify.com/collections/murti-hindu-god-murti",
    "murti_animal": "https://a-jewel-studio-3.myshopify.com/collections/murti-animal-murti",
    "murti_mix": "https://a-jewel-studio-3.myshopify.com/collections/murti-mix-designs",
    "baby_bangle": "https://a-jewel-studio-3.myshopify.com/collections/baby-bangles-kada",
    "baby_payal": "https://a-jewel-studio-3.myshopify.com/collections/baby-anklets-payal",
    "baby_rings": "https://a-jewel-studio-3.myshopify.com/collections/baby-rings",
    "baby_necklace": "https://a-jewel-studio-3.myshopify.com/collections/baby-necklace-chain",
    "baby_earrings": "https://a-jewel-studio-3.myshopify.com/collections/baby-earrings",
    "baby_hair": "https://a-jewel-studio-3.myshopify.com/collections/baby-hair-accessories"
}

# Sub Categories per Main Category
SUB_CATEGORIES = {
    "face": [
        {"id": "face_ear", "title": "Ear Jewellery", "description": "Studs, Jhumka, Chandbali, Hoops, Cuff"},
        {"id": "face_nose", "title": "Nose Jewellery", "description": "Nath, Nathni, Laung, Septum"},
        {"id": "face_head", "title": "Head Jewellery", "description": "Maang Tikka, Maatha Patti, Passa"},
        {"id": "face_lip", "title": "Lip and Eye Jewellery", "description": "Lip Pin, Lip Ring, Eye Pin"}
    ],
    "neck": [
        {"id": "neck_traditional", "title": "Traditional Haar", "description": "Kanthi, Para Kanthi, Mag Mala, Haar"},
        {"id": "neck_modern", "title": "Modern Necklace", "description": "Choker, Chains, Statement Necklace"},
        {"id": "neck_pendant", "title": "Pendant and Butti", "description": "Pendant, Tanmanya, Locket, Sets"},
        {"id": "neck_sets", "title": "Special Sets", "description": "Mangalsutra, Bridal Set, Necklace Set"}
    ],
    "hand": [
        {"id": "hand_bangle", "title": "Bangdi and Bangle", "description": "Plain, Designer, Openable, Javri Set"},
        {"id": "hand_kada", "title": "Kada", "description": "Plain, Designer, Patla, Religious Kada"},
        {"id": "hand_bracelet", "title": "Bracelet", "description": "Chain, Tennis, Bangle Style, Kaida"},
        {"id": "hand_baju", "title": "Baju Band and Haath Panja", "description": "Armlet, Baju Band, Haath Panja"},
        {"id": "hand_rings", "title": "Rings", "description": "Solitaire, Band, Statement, Couple, Stack"}
    ],
    "lower": [
        {"id": "lower_payal", "title": "Payal and Anklet", "description": "Traditional, Modern, Todi, Bridal"},
        {"id": "lower_bichhiya", "title": "Bichhiya and Toe Ring", "description": "Traditional, Modern, Pag Panja"},
        {"id": "lower_kamarband", "title": "Kamarband and Waist", "description": "Kandora, Waist Chain, Hip Belt"}
    ],
    "murti": [
        {"id": "murti_god", "title": "Hindu God Murti", "description": "Ganesh, Laxmi, Shiva, Krishna, Ram"},
        {"id": "murti_animal", "title": "Animal Murti", "description": "Sacred, Royal, Birds, Aquatic Animals"},
        {"id": "murti_mix", "title": "Mix Designs", "description": "Abstract, Tribal, Decorative, Miniature"}
    ],
    "baby": [
        {"id": "baby_bangle", "title": "Baby Bangles and Kada", "description": "Plain, Designer, Openable, Pair"},
        {"id": "baby_payal", "title": "Baby Anklets and Payal", "description": "Plain, Ghunghroo, Chain, Charm"},
        {"id": "baby_rings", "title": "Baby Rings", "description": "Plain, Designer, Adjustable, Flower"},
        {"id": "baby_necklace", "title": "Baby Necklace and Chain", "description": "Plain, Pendant, Evil Eye, Religious"},
        {"id": "baby_earrings", "title": "Baby Earrings", "description": "Plain Studs, Flower, Small Bali, Stone"},
        {"id": "baby_hair", "title": "Baby Hair Accessories", "description": "Hair Pin, Juda Pin, Clip, Tikka Pin"}
    ]
}

user_sessions = {}
processed_messages = set()

# Keep Alive
def keep_alive():
    while True:
        time.sleep(840)
        try:
            requests.get("https://ajewel-whatsapp-bot.onrender.com/")
            print("Keep alive ping sent")
        except:
            pass

thread = threading.Thread(target=keep_alive)
thread.daemon = True
thread.start()

def send_message(to, message):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }
    response = requests.post(url, headers=headers, json=data)
    print(f"Send message: {response.status_code}")

def send_main_categories(to):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": "A Jewel Studio"},
            "body": {"text": "Welcome to A Jewel Studio!\nPremium 3D Jewellery Designs\n\nApni category select karein:"},
            "footer": {"text": "Professional 3D Jewellery Designs"},
            "action": {
                "button": "Category Dekho",
                "sections": [{
                    "title": "Jewellery Categories",
                    "rows": [
                        {"id": "face", "title": "Face Jewellery", "description": "Ear, Nose, Head, Lip and Eye"},
                        {"id": "neck", "title": "Neck Jewellery", "description": "Haar, Necklace, Pendant, Sets"},
                        {"id": "hand", "title": "Hand Jewellery", "description": "Bangles, Kada, Rings, Bracelet"},
                        {"id": "lower", "title": "Lower Body Jewellery", "description": "Payal, Bichhiya, Kamarband"},
                        {"id": "murti", "title": "Murti and Figurines", "description": "Hindu Gods, Animals, Mix Designs"},
                        {"id": "baby", "title": "Baby Jewellery", "description": "Bangles, Payal, Rings, Necklace"}
                    ]
                }]
            }
        }
    }
    response = requests.post(url, headers=headers, json=data)
    print(f"Main categories: {response.status_code}")

def send_sub_categories(to, main_cat):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    sub_cats = SUB_CATEGORIES.get(main_cat, [])
    cat_titles = {
        "face": "Face Jewellery", "neck": "Neck Jewellery",
        "hand": "Hand Jewellery", "lower": "Lower Body Jewellery",
        "murti": "Murti and Figurines", "baby": "Baby Jewellery"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": cat_titles.get(main_cat, "Category")},
            "body": {"text": "Sub category select karein:"},
            "footer": {"text": "A Jewel Studio - 3D Designs"},
            "action": {
                "button": "Sub Category Dekho",
                "sections": [{"title": "Sub Categories", "rows": sub_cats}]
            }
        }
    }
    response = requests.post(url, headers=headers, json=data)
    print(f"Sub categories: {response.status_code}")

def send_customer_type(to):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": "Aap kaun hain?\n\nRetail - Personal use ke liye\nB2B - Business or Wholesale ke liye"},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "retail", "title": "Retail Customer"}},
                    {"type": "reply", "reply": {"id": "b2b", "title": "B2B / Wholesaler"}}
                ]
            }
        }
    }
    response = requests.post(url, headers=headers, json=data)
    print(f"Customer type: {response.status_code}")

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
    print(f"Incoming webhook: {json.dumps(data)}")
    try:
        entry = data["entry"][0]["changes"][0]["value"]

        if "messages" in entry:
            msg = entry["messages"][0]
            msg_id = msg.get("id")
            from_number = msg["from"]
            msg_type = msg["type"]

            # Duplicate check
            if msg_id in processed_messages:
                print(f"Duplicate ignored: {msg_id}")
                return jsonify({"status": "ok"}), 200
            processed_messages.add(msg_id)
            if len(processed_messages) > 1000:
                processed_messages.clear()

            session = user_sessions.get(from_number, {})
            step = session.get("step", "")

            # ── TEXT MESSAGES ──────────────────────────────────────
            if msg_type == "text":
                text = msg["text"]["body"].strip()

                # Hi / Menu
                if text.lower() in ["hi", "hello", "hii", "hey", "start", "menu"]:
                    user_sessions[from_number] = {}
                    send_main_categories(from_number)

                # Name
                elif step == "waiting_name":
                    user_sessions[from_number]["name"] = text
                    user_sessions[from_number]["step"] = "waiting_number"
                    send_message(from_number,
                        "Aapka WhatsApp number kya hai?\n(Example: 9876543210)"
                    )

                # Phone
                elif step == "waiting_number":
                    user_sessions[from_number]["phone"] = text
                    user_sessions[from_number]["step"] = "waiting_email"
                    send_message(from_number,
                        "Aapka email address kya hai?\n(Example: name@email.com)"
                    )

                # Email - Send Order Summary
                elif step == "waiting_email":
                    user_sessions[from_number]["email"] = text
                    s = user_sessions[from_number]
                    cat_titles = {
                        "face": "Face Jewellery", "neck": "Neck Jewellery",
                        "hand": "Hand Jewellery", "lower": "Lower Body Jewellery",
                        "murti": "Murti and Figurines", "baby": "Baby Jewellery"
                    }
                    send_message(from_number,
                        f"Order Summary\n"
                        f"{'='*25}\n\n"
                        f"Name: {s.get('name', '')}\n"
                        f"Phone: {s.get('phone', '')}\n"
                        f"Email: {s.get('email', '')}\n\n"
                        f"Category: {cat_titles.get(s.get('main_category',''), '')}\n"
                        f"Sub Category: {s.get('sub_title', '')}\n"
                        f"Customer Type: {s.get('customer_type', '')}\n\n"
                        f"{'='*25}\n\n"
                        f"Thank you for choosing A Jewel Studio!\n\n"
                        f"Aapka order receive ho gaya hai.\n"
                        f"Jaldi hi payment link WhatsApp pe milega.\n"
                        f"Payment complete hone ke baad\n"
                        f"download link automatically aayega!\n\n"
                        f"Koi sawal? Reply karein."
                    )
                    user_sessions.pop(from_number, None)

                else:
                    send_message(from_number, "Namaste! Menu ke liye Hi likho.")

            # ── INTERACTIVE MESSAGES ───────────────────────────────
            elif msg_type == "interactive":
                interactive = msg["interactive"]

                if interactive["type"] == "list_reply":
                    selected_id = interactive["list_reply"]["id"]
                    selected_title = interactive["list_reply"]["title"]

                    # Main Category selected
                    if selected_id in SUB_CATEGORIES:
                        user_sessions[from_number] = {
                            "main_category": selected_id,
                            "main_title": selected_title,
                            "step": "waiting_sub_category"
                        }
                        send_sub_categories(from_number, selected_id)

                    # Sub Category selected
                    elif selected_id in SUB_CATALOG_LINKS:
                        sub_link = SUB_CATALOG_LINKS.get(selected_id, "")
                        user_sessions[from_number]["sub_category"] = selected_id
                        user_sessions[from_number]["sub_title"] = selected_title
                        user_sessions[from_number]["step"] = "waiting_customer_type"

                        send_message(from_number,
                            f"Aapne {selected_title} select kiya!\n\n"
                            f"Niche catalog link hai:\n{sub_link}\n\n"
                            f"Catalog dekh kar products cart mein add karein\n"
                            f"aur checkout karein.\n\n"
                            f"Aage badhne ke liye niche select karein:"
                        )
                        send_customer_type(from_number)

                # Retail / B2B Button
                elif interactive["type"] == "button_reply":
                    button_id = interactive["button_reply"]["id"]

                    if button_id in ["retail", "b2b"]:
                        customer_type = "Retail Customer" if button_id == "retail" else "B2B / Wholesaler"
                        user_sessions[from_number]["customer_type"] = customer_type
                        user_sessions[from_number]["step"] = "waiting_name"
                        send_message(from_number,
                            f"Aapne {customer_type} select kiya!\n\n"
                            f"Thodi si details chahiye:\n\n"
                            f"Aapka poora naam kya hai?"
                        )

                # WhatsApp Cart Order
                elif interactive["type"] == "order":
                    order = interactive.get("order", {})
                    items = order.get("product_items", [])
                    order_text = "New Cart Order Received!\n\nProducts:\n"
                    total = 0
                    for item in items:
                        pid = item.get("product_retailer_id", "")
                        qty = item.get("quantity", 1)
                        price = float(item.get("item_price", 0))
                        currency = item.get("currency", "INR")
                        subtotal = qty * price
                        total += subtotal
                        order_text += f"- {pid} x{qty} = {currency} {subtotal:.2f}\n"
                    order_text += f"\nTotal: INR {total:.2f}"

                    user_sessions[from_number] = {
                        "step": "waiting_customer_type",
                        "cart_order": order_text
                    }
                    send_message(from_number, order_text)
                    send_customer_type(from_number)

    except Exception as e:
        print(f"Error: {e}")

    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
