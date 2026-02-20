from flask import Flask, request, jsonify
import requests
import json
import os

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "ajewel2024")
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", "")
PHONE_NUMBER_ID = "928999850307609"

def catalog_url(set_id):
    return "https://wa.me/c/918141356990"

MAIN_CATEGORIES = {
    "face": {"title": "Face Jewellery", "desc": "Ear, Nose, Head, Lip and Eye", "set_id": "25749951748007044"},
    "neck": {"title": "Neck Jewellery", "desc": "Haar, Necklace, Pendant, Sets", "set_id": "25770023742652990"},
    "hand": {"title": "Hand Jewellery", "desc": "Bangles, Kada, Rings, Bracelet", "set_id": "26078491468433934"},
    "lower": {"title": "Lower Body Jewellery", "desc": "Payal, Bichhiya, Kamarband", "set_id": "26473022232283999"},
    "murti": {"title": "Murti and Figurines", "desc": "Hindu Gods, Animals, Mix", "set_id": "26328388420090334"},
    "baby": {"title": "Baby Jewellery", "desc": "Bangles, Anklets, Rings, Chain", "set_id": "25628597613502595"},
}

SUB_CATEGORIES = {
    "face": [
        {"id": "face_ear", "title": "Ear Jewellery", "desc": "Studs, Jhumka, Chandbali, Hoops", "set_id": "26090421433907722"},
        {"id": "face_nose", "title": "Nose Jewellery", "desc": "Nath, Nathni, Laung, Septum", "set_id": "26026555510330213"},
        {"id": "face_head", "title": "Head Jewellery", "desc": "Maang Tikka, Maatha Patti, Passa", "set_id": "25629234596754210"},
        {"id": "face_lip", "title": "Lip and Eye Jewellery", "desc": "Lip Pin, Lip Ring, Eye Pin", "set_id": "25993617556990784"},
    ],
    "neck": [
        {"id": "neck_trad", "title": "Traditional Haar", "desc": "Kanthi, Para Kanthi, Mag Mala", "set_id": "25892135267109218"},
        {"id": "neck_mod", "title": "Modern Necklace", "desc": "Choker, Chains, Statement", "set_id": "26277843851853890"},
        {"id": "neck_pend", "title": "Pendant and Butti", "desc": "Tanmanya, Locket, Nameplate", "set_id": "25850209314636536"},
        {"id": "neck_set", "title": "Special Sets", "desc": "Mangalsutra, Necklace Set, Bridal", "set_id": "26252397311060803"},
    ],
    "hand": [
        {"id": "hand_bangle", "title": "Bangdi and Bangle", "desc": "Plain, Designer, Openable, Javri", "set_id": "26079781681708309"},
        {"id": "hand_kada", "title": "Kada", "desc": "Plain, Designer, Patla, Religious", "set_id": "26047371878255581"},
        {"id": "hand_bracelet", "title": "Bracelet", "desc": "Chain, Tennis, Kaida Bracelet", "set_id": "26349002784723474"},
        {"id": "hand_baju", "title": "Baju Band and Haath Panja", "desc": "Armlet, Haath Panja, Baju Band", "set_id": "34397077723223821"},
        {"id": "hand_rings", "title": "Rings", "desc": "Solitaire, Band, Statement, Couple", "set_id": "25891367957149672"},
    ],
    "lower": [
        {"id": "lower_payal", "title": "Payal and Anklet", "desc": "Traditional Payal, Modern Anklet, Todi", "set_id": "33976400778641336"},
        {"id": "lower_bichhiya", "title": "Bichhiya and Toe Ring", "desc": "Traditional, Modern, Pag Panja", "set_id": "26118144874448091"},
        {"id": "lower_kamar", "title": "Kamarband and Waist", "desc": "Kandora, Waist Chain, Hip Belt", "set_id": "25835297096142403"},
    ],
    "murti": [
        {"id": "murti_god", "title": "Hindu God Murti", "desc": "Ganesh, Laxmi, Shiva, Krishna", "set_id": "26357708767188650"},
        {"id": "murti_animal", "title": "Animal Murti", "desc": "Sacred, Royal Animals, Birds", "set_id": "33871729065808088"},
        {"id": "murti_mix", "title": "Mix Designs", "desc": "Abstract, Tribal, Decorative", "set_id": "34195647333383660"},
    ],
    "baby": [
        {"id": "baby_bangle", "title": "Baby Bangles and Kada", "desc": "Plain, Designer, Openable Bangle", "set_id": "26693163706953517"},
        {"id": "baby_anklet", "title": "Baby Anklets and Payal", "desc": "Plain, Ghunghroo, Chain Anklet", "set_id": "25948367958163570"},
        {"id": "baby_rings", "title": "Baby Rings", "desc": "Plain, Designer, Adjustable Ring", "set_id": "26302662429369350"},
        {"id": "baby_chain", "title": "Baby Necklace and Chain", "desc": "Plain Chain, Pendant, Nameplate", "set_id": "25864345456526176"},
        {"id": "baby_earrings", "title": "Baby Earrings", "desc": "Plain Studs, Flower, Small Bali", "set_id": "26008758518787659"},
        {"id": "baby_hair", "title": "Baby Hair Accessories", "desc": "Hair Pin, Juda Pin, Hair Clip", "set_id": "34573479015569657"},
    ],
}

# sub_id -> parent_main_id mapping
SUB_TO_MAIN = {}
for main_id, subs in SUB_CATEGORIES.items():
    for sub in subs:
        SUB_TO_MAIN[sub["id"]] = main_id

user_sessions = {}

def send_message(to, message):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": message}}
    r = requests.post(url, headers=headers, json=data)
    print(f"send_message: {r.status_code} {r.text}")

def send_list_message(to, header, body, button_label, sections):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {
        "messaging_product": "whatsapp", "to": to, "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": header},
            "body": {"text": body},
            "footer": {"text": "A Jewel Studio - 3D Jewellery Designs"},
            "action": {"button": button_label, "sections": sections}
        }
    }
    r = requests.post(url, headers=headers, json=data)
    print(f"send_list: {r.status_code} {r.text}")

def send_button_message(to, body, buttons):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {
        "messaging_product": "whatsapp", "to": to, "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body},
            "action": {"buttons": [{"type": "reply", "reply": {"id": b["id"], "title": b["title"]}} for b in buttons]}
        }
    }
    r = requests.post(url, headers=headers, json=data)
    print(f"send_button: {r.status_code} {r.text}")

def send_catalog_button(to, body, button_text, url_link):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {
        "messaging_product": "whatsapp", "to": to, "type": "interactive",
        "interactive": {
            "type": "cta_url",
            "body": {"text": body},
            "action": {"name": "cta_url", "parameters": {"display_text": button_text, "url": url_link}}
        }
    }
    r = requests.post(url, headers=headers, json=data)
    print(f"send_catalog_btn: {r.status_code} {r.text}")

def send_main_category_menu(to):
    rows = [{"id": k, "title": v["title"], "description": v["desc"]} for k, v in MAIN_CATEGORIES.items()]
    send_list_message(to, "A Jewel Studio", "Namaste! Apni jewellery category select karein:", "Category Dekho",
                      [{"title": "Main Categories", "rows": rows}])

def send_sub_category_menu(to, main_id):
    subs = SUB_CATEGORIES.get(main_id, [])
    main_title = MAIN_CATEGORIES[main_id]["title"]
    rows = [{"id": s["id"], "title": s["title"], "description": s["desc"]} for s in subs]
    send_list_message(to, main_title, "Sub-category select karein:", "Sub Category Dekho",
                      [{"title": main_title, "rows": rows}])

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
    print(f"Incoming: {json.dumps(data)}")
    try:
        entry = data["entry"][0]["changes"][0]["value"]
        if "messages" not in entry:
            return jsonify({"status": "ok"}), 200

        msg = entry["messages"][0]
        from_number = msg["from"]
        msg_type = msg["type"]
        session = user_sessions.get(from_number, {})

        if msg_type == "text":
            text = msg["text"]["body"].strip().lower()

            if text in ["hi", "hello", "hii", "hey", "start", "menu"]:
                user_sessions[from_number] = {"step": "main_category"}
                send_main_category_menu(from_number)

            elif session.get("step") == "waiting_name":
                user_sessions[from_number]["name"] = msg["text"]["body"].strip()
                user_sessions[from_number]["step"] = "waiting_number"
                send_message(from_number, "Apna contact number likhein (10 digit):")

            elif session.get("step") == "waiting_number":
                user_sessions[from_number]["contact"] = msg["text"]["body"].strip()
                user_sessions[from_number]["step"] = "waiting_email"
                send_message(from_number, "Apna email address likhein:")

            elif session.get("step") == "waiting_email":
                user_sessions[from_number]["email"] = msg["text"]["body"].strip()
                # Send order summary
                s = user_sessions[from_number]
                summary = (
                    f"Order Summary\n\n"
                    f"Category: {s.get('main_title','')}\n"
                    f"Sub Category: {s.get('sub_title','')}\n"
                    f"Customer Type: {s.get('customer_type','')}\n"
                    f"Name: {s.get('name','')}\n"
                    f"Contact: {s.get('contact','')}\n"
                    f"Email: {s.get('email','')}\n\n"
                    f"Aapka order register ho gaya hai!\n"
                    f"Payment link aapko jaldi WhatsApp pe milega.\n\n"
                    f"Thank you for choosing A Jewel Studio!"
                )
                send_message(from_number, summary)
                user_sessions.pop(from_number, None)

            else:
                send_message(from_number, "Namaste! Menu ke liye 'Hi' likhein.")

        elif msg_type == "interactive":
            interactive = msg["interactive"]

            if interactive["type"] == "list_reply":
                selected_id = interactive["list_reply"]["id"]
                selected_title = interactive["list_reply"]["title"]

                # Main category selected
                if selected_id in MAIN_CATEGORIES:
                    user_sessions[from_number] = {"step": "sub_category", "main_id": selected_id, "main_title": selected_title}
                    send_sub_category_menu(from_number, selected_id)

                # Sub category selected
                elif selected_id in SUB_TO_MAIN:
                    main_id = SUB_TO_MAIN[selected_id]
                    sub_info = next(s for s in SUB_CATEGORIES[main_id] if s["id"] == selected_id)
                    set_id = sub_info["set_id"]
                    user_sessions[from_number]["step"] = "catalog_sent"
                    user_sessions[from_number]["sub_id"] = selected_id
                    user_sessions[from_number]["sub_title"] = selected_title
                    link = catalog_url(set_id)
                    send_catalog_button(from_number,
                        f"{selected_title} catalog dekho.Pasand aaye to cart karein aur checkout karein.Payment ke baad 'done' likhein.",
                        "Catalog Dekho", link)

            elif interactive["type"] == "button_reply":
                button_id = interactive["button_reply"]["id"]

                if button_id in ["retail", "b2b"]:
                    ctype = "Retail - Personal use" if button_id == "retail" else "B2B - Business / Wholesale"
                    user_sessions[from_number]["customer_type"] = ctype
                    user_sessions[from_number]["step"] = "waiting_name"
                    send_message(from_number, "Aapka naam likhein:")

        # "done" trigger for retail/b2b
        if msg_type == "text" and msg["text"]["body"].strip().lower() == "done":
            if session.get("step") == "catalog_sent":
                user_sessions[from_number]["step"] = "customer_type"
                send_button_message(from_number, "Aap kaun hain?", [
                    {"id": "retail", "title": "Retail Customer"},
                    {"id": "b2b", "title": "B2B / Wholesaler"}
                ])

    except Exception as e:
        print(f"Error: {e}")

    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
