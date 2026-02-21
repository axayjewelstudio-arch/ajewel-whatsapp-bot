# --------------------------------------------------------------
#  main.py  –  Simple WhatsApp Cloud API bot (Flask)
# --------------------------------------------------------------

from flask import Flask, request, jsonify
import requests
import os
import json

app = Flask(__name__)

# ---------------  ENV VARIABLES (Meta console se set karein) ---------------
#   1. VERIFY_TOKEN   – webhook verification ke liye (aap koi bhi string de sakte hain)
#   2. ACCESS_TOKEN   – Meta Graph API token (WhatsApp Business Settings → API → Token)
#   3. PHONE_NUMBER_ID – WhatsApp Business phone number ka ID (Meta console me milega)

VERIFY_TOKEN    = os.getenv("VERIFY_TOKEN", "my_verify_token")
ACCESS_TOKEN    = os.getenv("ACCESS_TOKEN", "")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID", "")

# --------------------  HELPER : Send plain text --------------------
def send_message(to: str, text: str):
    """
    Simple text message bhejne ke liye.
    """
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    requests.post(url, headers=headers, json=payload)


# --------------------  HELPER : Send button (interactive) ---------------
def send_button_message(to: str, body: str, buttons: list):
    """
    Interactive button message bhejne ke liye.
    `buttons` ek list of dicts hai: [{"id": "catalog", "title": "Catalog"} , ...]
    """
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
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
    requests.post(url, headers=headers, json=payload)


# --------------------  HELPER : Send image from a public URL -------------
def send_image_by_link(to: str, img_url: str, caption: str = None):
    """
    Public URL se image bhejne ke liye.
    We keep the image in Render's `static/` folder, so the URL is:
        https://<your‑render‑app>.onrender.com/static/<file_name>
    """
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": {"link": img_url}
    }
    if caption:
        payload["image"]["caption"] = caption
    requests.post(url, headers=headers, json=payload)


# --------------------  HEALTH CHECK (Render scans this) ---------------
@app.route("/")
def health():
    return "OK", 200


# --------------------  WHATSAPP WEBHOOK VERIFICATION ------------------
@app.route("/webhook", methods=["GET"])
def verify():
    """
    Meta server GET request karta hai webhook verify karne ke liye.
    URL me `hub.mode=subscribe` aur `hub.verify_token` aata hai.
    Agar token match ho jata hai to `hub.challenge` return karte hain.
    """
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403


# --------------------  INCOMING MESSAGE HANDLER --------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    """
    Ye function tab fire hota hai jab user aapke WhatsApp number ko koi message bhejta hai.
    Hum sirf text aur button‑reply (interactive) handle kar rahe hain.
    """
    data = request.get_json()
    print("Incoming webhook:", json.dumps(data))  # Debug ke liye console me print

    try:
        entry = data["entry"][0]["changes"][0]["value"]
        if "messages" not in entry:
            return jsonify({"status": "ok"}), 200   # koi message nahi, ignore

        msg = entry["messages"][0]
        from_number = msg["from"]          # user ka WhatsApp number (with country code)
        msg_type = msg["type"]

        # ----------------- TEXT MESSAGE -----------------
        if msg_type == "text":
            text = msg["text"]["body"].strip().lower()

            # Simple greetings (Hi, Hello, Menu, etc.)
            if text in ["hi", "hello", "hey", "namaste", "menu"]:
                welcome_text = (
                    "👋 Hi! *A Jewel Studio* me aapka swagat hai.\n"
                    "Kripya niche diye gaye button se aage badhein."
                )
                # 2 buttons: Catalog & Contact (aap apni zaroorat ke hisaab se edit kar sakte hain)
                buttons = [
                    {"id": "catalog", "title": "📖 Catalog"},
                    {"id": "contact", "title": "📞 Contact Us"}
                ]
                send_button_message(to=from_number, body=welcome_text, buttons=buttons)
            else:
                # Agar user koi aur text bhejta hai, to ek fallback reply send karte hain
                send_message(to=from_number,
                             text="Sorry, samajh nahi aaya! Type 'Hi' ya 'Menu' to start.")
        # ----------------- BUTTON REPLY (interactive) -----------------
        elif msg_type == "interactive":
            button_id = msg["interactive"]["button_reply"]["id"]
            if button_id == "catalog":
                # static folder me `catalog.jpg` rakh le (ya koi bhi image)
                img_url = f"{BASE_URL}/static/catalog.jpg"
                caption = "🛍️ Ye hai hamara latest catalog. Dekhiye aur pasand karein!"
                send_image_by_link(to=from_number, img_url=img_url, caption=caption)
            elif button_id == "contact":
                contact_msg = (
                    "📞 Aap hume +91 98765 43210 par call kar sakte hain.\n"
                    "📧 Email: support@ajewelstudio.com"
                )
                send_message(to=from_number, text=contact_msg)
            else:
                send_message(to=from_number,
                             text="Koi invalid button press hua lagta hai.")
        else:
            # Agar koi aur message type aata hai (image, audio, etc.) – simple reply
            send_message(to=from_number,
                         text="Sorry, type abhi support nahi hota. Sirf text ya button reply try karein.")

    except Exception as e:
        # Production me aap proper logging karenge
        print("Webhook handling error:", e)

    return jsonify({"status": "ok"}), 200


# --------------------  RUN (local development) --------------------
if __name__ == "__main__":
    # Render `$PORT` env variable set karta hai; local testing ke liye default 5000.
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
