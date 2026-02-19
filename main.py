from flask import Flask, request, jsonify
import requests
import json

app = Flask(__name__)

# ===== APNI INFO YAHAN BHARO =====
VERIFY_TOKEN = "ajewel2024"
ACCESS_TOKEN = "TUMHARA_PERMANENT_TOKEN_YAHAN"
PHONE_NUMBER_ID = "928999850307609"
# ==================================

CATALOG_LINKS = {
    "rings": "https://drive.google.com/rings-catalog-link",
    "necklace": "https://drive.google.com/necklace-catalog-link",
    "earrings": "https://drive.google.com/earrings-catalog-link",
    "bangles": "https://drive.google.com/bangles-catalog-link",
    "pendant": "https://drive.google.com/pendant-catalog-link",
    "murti": "https://drive.google.com/murti-catalog-link"
}

user_sessions = {}

def send_message(to, message):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }
    requests.post(url, headers=headers, json=data)

def send_list_message(to):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": "A Jewel Studio"},
            "body": {"text": "Welcome! Apni category select karein:"},
            "footer": {"text": "3D Jewellery Designs"},
            "action": {
                "button": "Category Dekho",
                "sections": [{
                    "title": "Categories",
                    "rows": [
                        {"id": "rings", "title": "Rings", "description": "3D Ring Designs"},
                        {"id": "necklace", "title": "Necklace", "description": "3D Necklace Designs"},
                        {"id": "earrings", "title": "Earrings", "description": "3D Earring Designs"},
                        {"id": "bangles", "title": "Bangles", "description": "3D Bangle Designs"},
                        {"id": "pendant", "title": "Pendant", "description": "3D Pendant Designs"},
                        {"id": "murti", "title": "Murti", "description": "3D Murti Designs"}
                    ]
                }]
            }
        }
    }
    requests.post(url, headers=headers, json=data)

def send_customer_type(to):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": "Aap kaun hain?"},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "retail", "title": "Retail Customer"}},
                    {"type": "reply", "reply": {"id": "b2b", "title": "B2B / Wholesaler"}}
                ]
            }
        }
    }
    requests.post(url, headers=headers, json=data)

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
    try:
        entry = data["entry"][0]["changes"][0]["value"]
        
        # Interactive message (list/button reply)
        if "messages" in entry:
            msg = entry["messages"][0]
            from_number = msg["from"]
            msg_type = msg["type"]

            if msg_type == "text":
                text = msg["text"]["body"].strip().lower()
                
                if text in ["hi", "hello", "hii", "hey", "start", "menu"]:
                    user_sessions[from_number] = {}
                    send_list_message(from_number)
                
                elif from_number in user_sessions and user_sessions[from_number].get("step") == "waiting_design":
                    category = user_sessions[from_number].get("category")
                    user_sessions[from_number]["design_code"] = text
                    user_sessions[from_number]["step"] = "waiting_customer_type"
                    send_customer_type(from_number)
                
                else:
                    send_message(from_number, "Namaste! Menu ke liye 'Hi' likho.")

            elif msg_type == "interactive":
                interactive = msg["interactive"]
                
                if interactive["type"] == "list_reply":
                    selected_id = interactive["list_reply"]["id"]
                    user_sessions[from_number] = {
                        "category": selected_id,
                        "step": "waiting_design"
                    }
                    catalog_link = CATALOG_LINKS.get(selected_id, "Link unavailable")
                    send_message(from_number, 
                        f"Aapne *{selected_id.title()}* select kiya!\n\n"
                        f"Catalog link: {catalog_link}\n\n"
                        f"Design code enter karein (Example: ring001):"
                    )

                elif interactive["type"] == "button_reply":
                    button_id = interactive["button_reply"]["id"]
                    
                    if button_id in ["retail", "b2b"] and from_number in user_sessions:
                        session = user_sessions[from_number]
                        design_code = session.get("design_code", "N/A")
                        category = session.get("category", "N/A")
                        customer_type = "Retail Customer" if button_id == "retail" else "B2B / Wholesaler"
                        
                        send_message(from_number,
                            f"*Order Received!*\n\n"
                            f"Category: {category.title()}\n"
                            f"Design Code: {design_code}\n"
                            f"Customer Type: {customer_type}\n\n"
                            f"Hum jaldi aapse contact karenge payment aur download link ke saath!\n\n"
                            f"Thank you for choosing A Jewel Studio!"
                        )
                        user_sessions.pop(from_number, None)

    except Exception as e:
        print(f"Error: {e}")
    
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
