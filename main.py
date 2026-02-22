# --------------------------------------------------------------
# main.py – A‑Jewel WhatsApp Bot (OAuth token version)
# --------------------------------------------------------------
"""
High‑level flow
1️⃣  User initiates conversation – The user sends “hi” on WhatsApp.
   The bot checks the Shopify store to see whether the customer is new or existing.
2️⃣  Bot presents the main menu – The bot replies with a “Menu” button that offers two options:
   • Catalog – Shows Shopify collections → products → variants.
   • Custom Jewellery – Directly asks the user for the name of the custom piece they want.
3️⃣  Variant selection – Whatever variant the customer picks is saved to a temporary cart‑list. 
4️⃣  Checkout – When the user types “checkout”, the bot:
   • Calculates the total amount for all items in the cart.
   • Generates a Razorpay payment‑link and sends it to the user. 
5️⃣  Payment confirmation – Razorpay sends a callback (GET) or webhook (POST) with the payment status.
   The bot then notifies the user with a success or failure message accordingly.  
6️⃣  Post‑checkout handling –
   • For B2B customers, the bot provides a “Download Now” button that delivers the digital 3‑D file.
   • For Retail customers, the bot sends a message saying “We will contact you soon.”  
7️⃣  Reminder for incomplete checkout – If the user never completes the checkout, a cron job
   (running on Render between 9 PM and 11 PM) automatically sends a reminder message.  
"""

import os
import json
import hmac
import hashlib
import logging
import random
import time
import threading
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Optional

import requests
import gspread
import razorpay
from flask import Flask, request, jsonify
from google.oauth2.service_account import Credentials

# ------------------------------------------------------------------
# 1️⃣  Flask app & logger
# ------------------------------------------------------------------
app = Flask(__name__)

log = logging.getLogger("ajewel_bot")
log.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
handler.setFormatter(formatter)
log.addHandler(handler)

# ------------------------------------------------------------------
# 2️⃣  Environment variables (Render → Environment → Add)
# ------------------------------------------------------------------
def env(name: str, required: bool = True, default: str = "") -> str:
    """Read env‑var, raise if required and missing."""
    v = os.getenv(name, default).strip()
    if required and not v:
        raise RuntimeError(f"❌ Missing required env‑var: {name}")
    return v


VERIFY_TOKEN          = env("VERIFY_TOKEN")                # WhatsApp webhook verify token
ACCESS_TOKEN          = env("ACCESS_TOKEN")                # Meta Graph API token (send messages)
PHONE_NUMBER_ID       = env("PHONE_NUMBER_ID")             # WhatsApp Business phone id
SHOPIFY_STORE         = env("SHOPIFY_STORE")               # e.g. a-jewel-studio-3.myshopify.com

# ---- OAuth client‑credentials credentials (new) ----
SHOPIFY_CLIENT_ID      = env("SHOPIFY_CLIENT_ID")          # 2251a2d4c5b1a048ab52e21f0be54dee
SHOPIFY_CLIENT_SECRET  = env("SHOPIFY_CLIENT_SECRET")      # shpss_…

# ---- Legacy keys (kept only for backward‑compatibility, not used) ----
# SHOPIFY_API_KEY   = env("SHOPIFY_API_KEY", required=False)
# SHOPIFY_PASSWORD  = env("SHOPIFY_PASSWORD", required=False)

RAZORPAY_KEY_ID       = env("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET   = env("RAZORPAY_KEY_SECRET")
GEMINI_API_KEY        = env("GEMINI_API_KEY")
GOOGLE_CRED_JSON      = env("GOOGLE_CREDENTIALS")          # service‑account JSON string
SHEET_ID              = env("SHEET_ID", required=False)   # optional audit sheet
META_BUSINESS_ID      = env("META_BUSINESS_ID")            # Facebook Business Account that owns the WhatsApp number

# ------------------------------------------------------------------
# 3️⃣  Global objects
# ------------------------------------------------------------------
rzp_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# ------------------------------------------------------------------
# 4️⃣  Token cache (client‑credentials) – thread‑safe
# ------------------------------------------------------------------
_token_cache = {
    "access_token": None,   # actual token string
    "expires_at": 0,         # epoch seconds when the token expires
    "lock": threading.Lock()
}


def _request_new_shopify_token() -> dict:
    """
    Calls Shopify's OAuth client‑credentials endpoint and returns the JSON payload:
    {
        "access_token": "...",
        "scope": "...",
        "expires_in": 86399
    }
    """
    url = f"https://{SHOPIFY_STORE}/admin/oauth/access_token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": SHOPIFY_CLIENT_ID,
        "client_secret": SHOPIFY_CLIENT_SECRET,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    resp = requests.post(url, data=payload, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_shopify_access_token() -> str:
    """
    Returns a valid X‑Shopify‑Access‑Token.
    Auto‑refreshes when the cached token is about to expire.
    """
    with _token_cache["lock"]:
        now = int(time.time())
        # Keep a 30‑second safety buffer before expiry
        if _token_cache["access_token"] and now < _token_cache["expires_at"] - 30:
            return _token_cache["access_token"]

        # Need a fresh token
        data = _request_new_shopify_token()
        _token_cache["access_token"] = data["access_token"]
        _token_cache["expires_at"] = now + int(data.get("expires_in", 86400))
        log.info("Fetched new Shopify access token (expires in %s secs)", data.get("expires_in"))
        return _token_cache["access_token"]


# ------------------------------------------------------------------
# 5️⃣  Dataclass – session per phone
# ------------------------------------------------------------------
@dataclass
class UserSession:
    phone: str
    step: str = "new"                     # new, old_greeted, awaiting_… etc.
    name: Optional[str] = None
    contact: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    gst: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    customer_type: Optional[str] = None   # "retail" or "b2b"
    cart: List[int] = field(default_factory=list)   # list of variant IDs
    order_id: Optional[str] = None
    amount: Optional[float] = None

# In‑memory store (Render restart = data loss, ok for demo)
sessions: Dict[str, UserSession] = {}

# ------------------------------------------------------------------
# 6️⃣  Gemini prompts (Professional + Hinglish)
# ------------------------------------------------------------------
SYSTEM_PROMPTS: Dict[str, str] = {
    "greeting": (
        "Tu A Jewel Studio ka professional WhatsApp assistant hai. "
        "Tera naam Akshay hai. Customer ko warmly welcome karo. "
        "Tone: Professional, warm, Hinglish. 2‑3 lines max."
    ),
    "registration": (
        "Tu A Jewel Studio ka WhatsApp assistant hai. "
        "Customer pehli baar aa raha hai. Politely batao ki order ke liye Shopify account banana zaroori hai. "
        "Tone: Professional, helpful, Hinglish. 3‑4 lines max."
    ),
    "catalog": (
        "Tu A Jewel Studio ka WhatsApp assistant hai. "
        "Customer catalog dekhna chahta hai. Professionally invite karo collection dekhne ke liye. "
        "Tone: Warm, Hinglish. 2 lines max."
    ),
    "customer_type": (
        "Tu A Jewel Studio ka WhatsApp assistant hai. "
        "Customer order karna chahta hai. Politely customer type select karne ko kaho. "
        "Tone: Professional, Hinglish. 1‑2 lines max."
    ),
    "retail_confirm": (
        "Tu A Jewel Studio ka WhatsApp assistant hai. Retail customer ka order receive hua. "
        "Professional thank‑you do. Batao team contact karegi design, pricing aur delivery ke liye. "
        "Tone: Warm, professional, Hinglish. 4‑5 lines max."
    ),
    "b2b_payment": (
        "Tu A Jewel Studio ka WhatsApp assistant hai. B2B customer ka order payment ke liye ready hai. "
        "Professional message do. Tone: Professional, Hinglish. 2‑3 lines max."
    ),
    "b2b_success": (
        "Tu A Jewel Studio ka WhatsApp assistant hai. B2B customer ki payment successful rahi. "
        "Warm thank‑you do aur batao files share ho gayi hain. Tone: Warm, professional, Hinglish. 3‑4 lines max."
    ),
    "b2b_failed": (
        "Tu A Jewel Studio ka WhatsApp assistant hai. Customer ki payment fail hui. "
        "Politely retry karne ko kaho. Tone: Helpful, Hinglish. 2 lines max."
    ),
    "collect_name":    "Customer se poora naam maango. Professional, friendly. 1 line.",
    "collect_phone":   "10 digit phone number maango. Professional. 1 line.",
    "collect_email":   "Email address maango. Professional. 1 line.",
    "collect_company":"B2B customer se company name maango. Professional. 1 line.",
    "collect_gst":    "GST number maango. NA likh sakte hain agar nahi hai. Professional. 1 line.",
    "collect_address":"Delivery address maango. Professional. 1 line.",
    "collect_city":   "City name maango. Professional. 1 line.",
    "general": (
        "Tu A Jewel Studio ka WhatsApp assistant hai. 3D jewellery designs bechta hai. "
        "Customer ke message ka professional Hinglish mein reply do. "
        "Agar samajh na aaye to 'Hi' type karne ko kaho. 3‑4 lines max."
    ),
}

# ------------------------------------------------------------------
# 7️⃣  Helper – Gemini call (safe fallback)
# ------------------------------------------------------------------
def gemini_reply(user_msg: str, ctx: str = "general", cust_name: str = "") -> str:
    """Call Gemini‑1.5‑Flash, return plain text. If anything fails → tiny fallback."""
    prompt = SYSTEM_PROMPTS.get(ctx, SYSTEM_PROMPTS["general"])
    if cust_name:
        prompt += f" Customer ka naam: {cust_name}."

    payload = {
        "contents": [{"parts": [{"text": f"{prompt}\n\nCustomer: {user_msg}"}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 200},
    }

    try:
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
            json=payload,
            timeout=10,
        )
        data = resp.json()
        cand = data.get("candidates")
        if not cand:
            raise ValueError("No candidates")
        return cand[0]["content"]["parts"][0]["text"].strip()
    except Exception as exc:
        log.error(f"Gemini error (ctx={ctx}): {exc}")
        # Very simple fallback – still Hinglish
        simple_fallback = {
            "greeting": "Namaste! A Jewel Studio mein aapka swagat hai. Menu button dabaye.",
            "registration": "Order ke liye Shopify account banana zaroori hai. Sign‑Up button dabaye.",
            "catalog": "Humara catalogue yahan hai – dekhne ke liye button dabaye.",
            "customer_type": "Retail ya B2B (wholesale) me se chunen.",
            "b2b_payment": "Payment ke liye button dabaye.",
            "b2b_success": "Payment successful! Files download karen.",
            "b2b_failed": "Payment fail hua. Retry button dabaye.",
            "retail_confirm": "Thank you! Hamari team aap se contact karegi.",
        }
        return simple_fallback.get(ctx, "Sorry, I didn’t get that. Type *menu*.")

# ------------------------------------------------------------------
# 8️⃣  Helper – WhatsApp send (single entry point)
# ------------------------------------------------------------------
def wa_send(to: str, body: str, typ: str = "text", extra: Optional[dict] = None) -> None:
    """
    typ = "text" | "interactive" | "cta_url"
    extra = dict payload for interactive / cta_url
    """
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    hdr = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"messaging_product": "whatsapp", "to": to, "type": typ}
    if typ == "text":
        payload["text"] = {"body": body}
    else:
        payload[typ] = extra

    try:
        r = requests.post(url, headers=hdr, json=payload, timeout=10)
        r.raise_for_status()
    except Exception as exc:
        log.error(f"WhatsApp send error (to={to}, typ={typ}): {exc}")

# ------------------------------------------------------------------
# 9️⃣  Helper – Shopify GET (now uses OAuth token)
# ------------------------------------------------------------------
def shopify_get(endpoint: str) -> dict:
    """
    Perform a GET against Shopify Admin API using the X‑Shopify‑Access‑Token header.
    """
    base_url = f"https://{SHOPIFY_STORE}/admin/api/2024-04/{endpoint}"
    headers = {
        "X-Shopify-Access-Token": get_shopify_access_token(),
        "Accept": "application/json",
    }
    try:
        r = requests.get(base_url, headers=headers, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        log.error(f"Shopify GET error ({endpoint}): {exc}")
        return {}

# ------------------------------------------------------------------
# 10️⃣  Helper – Google Sheet (optional order log)
# ------------------------------------------------------------------
def sheet() -> Optional[gspread.models.Spreadsheet]:
    if not SHEET_ID:
        return None
    try:
        cred_dict = json.loads(GOOGLE_CRED_JSON)
        creds = Credentials.from_service_account_info(
            cred_dict,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ],
        )
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID).sheet1
    except Exception as exc:
        log.error(f"Google Sheet init error: {exc}")
        return None


def log_to_sheet(row: List):
    sh = sheet()
    if sh:
        try:
            sh.append_row(row)
        except Exception as exc:
            log.error(f"Google Sheet write error: {exc}")

# ------------------------------------------------------------------
# 11️⃣  Helper – order‑id & Razorpay link
# ------------------------------------------------------------------
def generate_order_id() -> str:
    return "AJS" + datetime.now().strftime("%d%m%y%H%M%S")


def create_razorpay_link(amount_inr: float, order_id: str, name: str, phone: str) -> str:
    """Return short_url or empty string."""
    payload = {
        "amount": int(amount_inr * 100),          # paisa
        "currency": "INR",
        "description": f"A Jewel Studio Order {order_id}",
        "customer": {"name": name, "contact": phone},
        "callback_url": "https://<your-app>.onrender.com/payment-callback",
        "callback_method": "get",
        "notes": {"order_id": order_id},
    }
    try:
        resp = rzp_client.payment_link.create(payload)
        return resp.get("short_url", "")
    except Exception as exc:
        log.error(f"Razorpay link error (order={order_id}): {exc}")
        return ""

# ------------------------------------------------------------------
# 12️⃣  UI – Common send helpers
# ------------------------------------------------------------------
def send_menu(to: str):
    """Main menu – Catalog OR Custom Jewellery."""
    wa_send(
        to,
        "Select an option:",
        "interactive",
        {
            "type": "button",
            "body": {"text": "Menu"},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "catalog", "title": "Catalog"}},
                    {"type": "reply", "reply": {"id": "custom", "title": "Custom Jewellery"}},
                ]
            },
        },
    )


def show_collections(sess: UserSession):
    """Shopify collections → WhatsApp buttons (max 10)."""
    data = shopify_get("custom_collections.json")
    cols = data.get("custom_collections", [])[:10]
    if not cols:
        wa_send(sess.phone, "Sorry, no collections found.")
        return

    buttons = [
        {"type": "reply", "reply": {"id": str(c["id"]), "title": c["title"]}} for c in cols
    ]
    wa_send(
        sess.phone,
        "Select a collection:",
        "interactive",
        {"type": "button", "body": {"text": "Collections"}, "action": {"buttons": buttons}},
    )
    sess.step = "await_collection"


def show_products(sess: UserSession, collection_id: str):
    data = shopify_get(f"products.json?collection_id={collection_id}")
    prods = data.get("products", [])[:10]
    if not prods:
        wa_send(sess.phone, "No products in this collection.")
        return

    buttons = [
        {"type": "reply", "reply": {"id": str(p["id"]), "title": p["title"]}} for p in prods
    ]
    wa_send(
        sess.phone,
        "Select a product:",
        "interactive",
        {"type": "button", "body": {"text": "Products"}, "action": {"buttons": buttons}},
    )
    sess.step = "await_product"
    sess.collection_id = collection_id


def show_variants(sess: UserSession, product_id: str):
    data = shopify_get(f"products/{product_id}.json")
    variants = data.get("product", {}).get("variants", [])[:10]
    if not variants:
        wa_send(sess.phone, "No variants for this product.")
        return

    buttons = [
        {
            "type": "reply",
            "reply": {
                "id": str(v["id"]),
                "title": f"{v['title']} – ₹{v['price']}",
            },
        }
        for v in variants
    ]
    wa_send(
        sess.phone,
        "Pick a variant (size/color):",
        "interactive",
        {"type": "button", "body": {"text": "Variants"}, "action": {"buttons": buttons}},
    )
    sess.step = "await_variant"
    sess.product_id = product_id


def add_variant_to_cart(sess: UserSession, variant_id: str):
    sess.cart.append(int(variant_id))
    wa_send(sess.phone, "✅ Added to cart! Type *checkout* to pay or continue shopping.")
    sess.step = "browsing"


def ask_customer_type(sess: UserSession):
    wa_send(
        sess.phone,
        "Are you a Retail customer (physical jewellery) or B2B (digital files)?",
        "interactive",
        {
            "type": "button",
            "body": {"text": "Select type"},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "retail", "title": "Retail"}},
                    {"type": "reply", "reply": {"id": "b2b", "title": "B2B / Wholesale"}},
                ]
            },
        },
    )
    sess.step = "await_customer_type"


def start_checkout(sess: UserSession):
    """Calculate total, create Razorpay link, send CTA button."""
    total = 0.0
    for vid in sess.cart:
        var = shopify_get(f"variants/{vid}.json").get("variant")
        if var:
            total += float(var.get("price", 0))

    order_id = generate_order_id()
    sess.order_id = order_id
    sess.amount = total
    sess.step = "payment_pending"

    # Log order (optional)
    log_to_sheet(
        [
            datetime.now().isoformat(),
            order_id,
            "B2B" if sess.customer_type == "b2b" else "Retail",
            sess.name or "",
            sess.phone,
            total,
            "Pending",
        ]
    )

    # Razorpay link
    link = create_razorpay_link(total, order_id, sess.name or "Customer", sess.phone)
    if not link:
        wa_send(sess.phone, "Sorry, could not create payment link. Contact support.")
        return

    msg = gemini_reply(
        f"Order {order_id} ready for payment.",
        "b2b_payment" if sess.customer_type == "b2b" else "retail_confirm",
        sess.name or "",
    )
    wa_send(sess.phone, msg, "cta_url", {"display_text": "Pay Now", "url": link})


def payment_success(sess: UserSession):
    """B2B → download button, Retail → quotation note."""
    if sess.customer_type == "b2b":
        msg = gemini_reply("Payment successful – B2B", "b2b_success", sess.name or "")
        wa_send(sess.phone, msg)
        # Download button (Shopify Digital Asset URL – adjust if needed)
        wa_send(
            sess.phone,
            "Your digital design files are ready.",
            "cta_url",
            {"display_text": "Download Now", "url": "https://a-jewel-studio-3.myshopify.com/a/downloads"},
        )
    else:
        msg = gemini_reply("Payment successful – Retail", "retail_confirm", sess.name or "")
        wa_send(sess.phone, msg)
        wa_send(
            sess.phone,
            "Our team will contact you soon for quotation & delivery details.",
            "text",
        )
    log_to_sheet([datetime.now().isoformat(), sess.order_id, "Paid"])


def payment_failed(sess: UserSession):
    """Ask to retry, send fresh Razorpay link."""
    msg = gemini_reply("Payment failed", "b2b_failed", sess.name or "")
    new_link = create_razorpay_link(sess.amount or 0, sess.order_id or "tmp", sess.name or "", sess.phone)
    wa_send(
        sess.phone,
        msg,
        "cta_url",
        {"display_text": "Retry Payment", "url": new_link},
    )
    log_to_sheet([datetime.now().isoformat(), sess.order_id, "Failed"])

# ------------------------------------------------------------------
# 13️⃣  Flask Routes – WhatsApp webhook (GET verification & POST)
# ------------------------------------------------------------------
@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403


@app.route("/webhook", methods=["POST"])
def inbound():
    data = request.get_json()
    log.info(f"Incoming payload: {json.dumps(data)}")
    try:
        entry = data["entry"][0]["changes"][0]["value"]
        if "messages" not in entry:
            return jsonify({"status": "ok"}), 200

        msg = entry["messages"][0]
        phone = msg["from"]
        msg_type = msg["type"]

        # ---- Get or create session ----
        sess = sessions.setdefault(phone, UserSession(phone=phone))

        # ------------------------------------------------------------
        # 1️⃣  New / Old Customer detection (runs only once)
        # ------------------------------------------------------------
        if sess.step == "new":
            cust = shopify_get(f"customers/search.json?query=phone:{phone}")
            if cust.get("customers"):
                sess.step = "old_greeted"
                greet = gemini_reply("User is returning.", "greeting", "")
                wa_send(phone, greet)
                send_menu(phone)
            else:
                sess.step = "new_greeted"
                greet = gemini_reply("New user – ask to sign‑up.", "registration", "")
                wa_send(phone, greet)
                wa_send(
                    phone,
                    "Sign‑Up",
                    "cta_url",
                    {"title": "Create Shopify Account", "url": f"https://{SHOPIFY_STORE}/account/register"},
                )
            return jsonify({"status": "ok"}), 200

        # ------------------------------------------------------------
        # 2️⃣  Interactive button replies
        # ------------------------------------------------------------
        if msg_type == "interactive":
            btn_id = msg["interactive"]["button_reply"]["id"]

            # -------- Main menu --------
            if btn_id == "catalog":
                show_collections(sess)
                return jsonify({"status": "ok"}), 200

            if btn_id == "custom":
                # Custom jewellery – just ask for name and close
                wa_send(phone, "Kripya apna poora naam likhein:", "text")
                sess.step = "await_name_custom"
                return jsonify({"status": "ok"}), 200

            # -------- Collection selected ----------
            if sess.step == "await_collection":
                show_products(sess, btn_id)
                return jsonify({"status": "ok"}), 200

            # -------- Product selected ----------
            if sess.step == "await_product":
                show_variants(sess, btn_id)
                return jsonify({"status": "ok"}), 200

            # -------- Variant selected ----------
            if sess.step == "await_variant":
                add_variant_to_cart(sess, btn_id)
                return jsonify({"status": "ok"}), 200

            # -------- Custom‑Jewellery name capture ----------
            if sess.step == "await_name_custom":
                sess.name = btn_id
                wa_send(
                    phone,
                    f"Dhanyavaad {sess.name}, hamari team jald hi aapko estimate bhejegi.",
                    "text",
                )
                sess.step = "finished"
                return jsonify({"status": "ok"}), 200

            # -------- Customer‑type after cart ----------
            if sess.step == "await_customer_type":
                if btn_id in ("retail", "b2b"):
                    sess.customer_type = btn_id
                    wa_send(phone, "Kripya apna poora naam likhein:", "text")
                    sess.step = "await_name"
                return jsonify({"status": "ok"}), 200

        # ------------------------------------------------------------
        # 3️⃣  Text messages (commands, data capture, generic chat)
        # ------------------------------------------------------------
        if msg_type == "text":
            text = msg["text"]["body"].strip().lower()

            # ----- Simple commands -----
            if text in ("hi", "hello", "hey", "menu"):
                send_menu(phone)
                return jsonify({"status": "ok"}), 200

            if text == "checkout":
                if not sess.cart:
                    wa_send(phone, "Aapka cart khaali hai – pehle koi product jodhen.")
                else:
                    start_checkout(sess)
                return jsonify({"status": "ok"}), 200

            # ----- Data collection steps -----
            if sess.step and sess.step.startswith("await_"):
                field = sess.step.replace("await_", "")
                setattr(sess, field, text)

                # decide next field
                next_map = {
                    "name": ("contact", "collect_phone"),
                    "contact": ("email", "collect_email"),
                    "email": (
                        "company" if sess.customer_type == "b2b" else "address",
                        "collect_company" if sess.customer_type == "b2b" else "collect_address",
                    ),
                    "company": ("gst", "collect_gst"),
                    "gst": ("address", "collect_address"),
                    "address": ("city", "collect_city"),
                    "city": (None, None),   # all personal data collected
                }
                nxt, prompt_key = next_map.get(field, (None, None))
                if nxt:
                    sess.step = f"await_{nxt}"
                    prompt = gemini_reply("", prompt_key, sess.name or "")
                    wa_send(phone, prompt or f"कृपया {nxt} दें:")
                else:
                    # After personal data, ask Retail vs B2B
                    ask_customer_type(sess)
                return jsonify({"status": "ok"}), 200

            # ----- Generic fallback (chat) -----
            reply = gemini_reply(text, "general", sess.name or "")
            wa_send(phone, reply)
            return jsonify({"status": "ok"}), 200

    except Exception as exc:
        log.exception(f"Webhook processing error: {exc}")

    return jsonify({"status": "ok"}), 200


# ------------------------------------------------------------------
# 14️⃣  Razorpay GET callback (after user pays)
# ------------------------------------------------------------------
@app.route("/payment-callback", methods=["GET"])
def razorpay_callback():
    pid = request.args.get("razorpay_payment_id")
    plid = request.args.get("razorpay_payment_link_id")
    sig = request.args.get("razorpay_signature")
    status = request.args.get("razorpay_payment_link_status")

    # ---- Verify HMAC signature ----
    expected = hmac.new(
        RAZORPAY_KEY_SECRET.encode(),
        f"{plid}|{pid}".encode(),
        hashlib.sha256,
    ).hexdigest()

    if expected != sig:
        log.warning("Invalid Razorpay signature")
        return "Invalid signature", 400

    # ---- Find the session that is waiting for payment ----
    for sess in list(sessions.values()):
        if sess.order_id and sess.step == "payment_pending":
            if status == "paid":
                payment_success(sess)
                sessions.pop(sess.phone, None)
            else:
                payment_failed(sess)
            break

    return "OK", 200


# ------------------------------------------------------------------
# 15️⃣  Razorpay POST webhook (alternative, more reliable)
# ------------------------------------------------------------------
@app.route("/razorpay-webhook", methods=["POST"])
def razorpay_webhook():
    payload = request.get_data()
    header_sig = request.headers.get("X-Razorpay-Signature", "")
    computed_sig = hmac.new(RAZORPAY_KEY_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    if computed_sig != header_sig:
        log.warning("Razorpay webhook signature mismatch")
        return "Invalid signature", 400

    try:
        data = request.get_json()
        if data.get("event") == "payment_link.paid":
            notes = data["payload"]["payment_link"]["entity"].get("notes", {})
            order_id = notes.get("order_id")
            for sess in list(sessions.values()):
                if sess.order_id == order_id:
                    payment_success(sess)
                    sessions.pop(sess.phone, None)
                    break
    except Exception as exc:
        log.exception(f"Razorpay webhook error: {exc}")

    return "OK", 200


# ------------------------------------------------------------------
# 16️⃣  Daily reminder – Render cron (21‑23 h)
# ------------------------------------------------------------------
@app.route("/reminder", methods=["GET"])
def reminder():
    now = datetime.now()
    if not (21 <= now.hour <= 23):
        return "Out of window", 200

    for sess in sessions.values():
        if sess.cart and sess.step != "payment_pending":
            wa_send(
                sess.phone,
                "🛒 aapka cart abhi bhi hai – kripya *checkout* karein ya *menu* dabayein.",
                "text",
            )
    return "Reminder sent", 200


# ------------------------------------------------------------------
# 17️⃣  Run Flask (Render injects $PORT)
# ------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
