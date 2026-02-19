from flask import Flask, request, jsonify
import requests
import json
import os

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "ajewel2024")
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", "")
PHONE_NUMBER_ID = "928999850307609"

CATALOG_LINKS = {
    "face": "https://a-jewel-studio-3.myshopify.com/collections/face-jewellery",
    "neck": "https://a-jewel-studio-3.myshopify.com/collections/neck-jewellery",
    "hand": "https://a-jewel-studio-3.myshopify.com/collections/hand-jewellery",
    "lower": "https://a-jewel-studio-3.myshopify.com/collections/lower-body-jewellery",
    "murti": "https://a-jewel-studio-3.myshopify.com/collections/murti-figurines"
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
    response = requests.post(url, headers=headers, json=data)
    print(f"Send message response: {response.status_code} - {response.text}")

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
            "body": {"text": "Welcome to A Jewel Studio!\nApni category select karein:"},
            "footer": {"text": "3D Jewellery Designs"},
            "action": {
                "button": "Category Dekho",
                "sections": [{
                    "title": "Jewellery Categories",
                    "rows": [
                        {"id": "face", "title": "Face Jewellery", "description": "Ear, Nose, Head, Lip and Eye"},
                        {"id": "neck", "title": "Neck Jewellery", "description": "Haar, Necklace, Pendant, Sets"},
                        {"id": "hand", "title": "Hand Jewellery", "description": "Bangles, Kada, Rings, Bracelet"},
                        {"id": "lower", "title": "Lower Body", "description": "Payal, Bichhiya, Kamarband"},
                        {"id": "murti", "title": "Murti and Figurines", "description": "Hindu Gods, Animals, Mix"}
                    ]
                }]
            }
        }
    }
    response = requests.post(url, headers=headers, json=data)
    print(f"Send list response: {response.status_code} - {response.text}")

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
    response = requests.post(url, headers=headers, json=data)
    print(f"Send customer type response: {response.status_code} - {response.text}")

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
            from_number = msg["from"]
            msg_type = msg["type"]

            if msg_type == "text":
                text = msg["text"]["body"].strip().lower()
                print(f"Text from {from_number}: {text}")

                if text in ["hi", "hello", "hii", "hey", "start", "menu"]:
                    user_sessions[from_number] = {}
                    send_list_message(from_number)

                elif from_number in user_sessions and user_sessions[from_number].get("step") == "waiting_design":
                    user_sessions[from_number]["design_code"] = text
                    user_sessions[from_number]["step"] = "waiting_customer_type"
                    send_customer_type(from_number)

                else:
                    send_message(from_number, "Namaste! Menu ke liye Hi likho.")

            elif msg_type == "interactive":
                interactive = msg["interactive"]

                if interactive["type"] == "list_reply":
                    selected_id = interactive["list_reply"]["id"]
                    selected_title = interactive["list_reply"]["title"]
                    user_sessions[from_number] = {
                        "category": selected_id,
                        "step": "waiting_design"
                    }
                    catalog_link = CATALOG_LINKS.get(selected_id, "Link unavailable")
                    send_message(from_number,
                        f"Aapne {selected_title} select kiya!\n\n"
                        f"Catalog link:\n{catalog_link}\n\n"
                        f"Catalog dekh kar apna design code enter karein\n"
                        f"(Example: FACE-EAR-STUDS-001):"
                    )

                elif interactive["type"] == "button_reply":
                    button_id = interactive["button_reply"]["id"]

                    if button_id in ["retail", "b2b"] and from_number in user_sessions:
                        session = user_sessions[from_number]
                        design_code = session.get("design_code", "N/A")
                        category = session.get("category", "N/A")
                        customer_type = "Retail Customer" if button_id == "retail" else "B2B / Wholesaler"

                        send_message(from_number,
                            f"Order Received!\n\n"
                            f"Category: {category.title()}\n"
                            f"Design Code: {design_code.upper()}\n"
                            f"Customer Type: {customer_type}\n\n"
                            f"Hum jaldi aapse contact karenge\n"
                            f"payment aur download link ke saath!\n\n"
                            f"Thank you for choosing A Jewel Studio!"
                        )
                        user_sessions.pop(from_number, None)

    except Exception as e:
        print(f"Error: {e}")

    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
