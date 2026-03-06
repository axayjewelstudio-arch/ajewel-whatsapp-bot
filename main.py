"""
╔══════════════════════════════════════════════════════════════════╗
║           A JEWEL STUDIO — WhatsApp Bot  (main.py)              ║
║           82 Real Catalog Collections | Gemini AI               ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import time
import json
import logging
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# ─────────────────────────────────────────────
#  SETUP
# ─────────────────────────────────────────────
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
app    = Flask(__name__)

# ─────────────────────────────────────────────
#  ENVIRONMENT VARIABLES
# ─────────────────────────────────────────────
WHATSAPP_TOKEN    = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID   = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN      = os.getenv("VERIFY_TOKEN")
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY")
BACKEND_API_URL   = os.getenv("BACKEND_API_URL")
GOOGLE_SHEETS_URL = os.getenv("GOOGLE_SHEETS_URL")

# ──────────────────────────────────────────────────────────────────
#  WHATSAPP CATALOG CONFIGURATION
#
#  CATALOG_ID kahan milega:
#    Facebook Business Manager → Commerce Manager
#    → Catalog → Settings → Catalog ID
#
#  WHATSAPP_CATALOG_ID .env file mein daalo:
#    WHATSAPP_CATALOG_ID=your_catalog_id_here
# ──────────────────────────────────────────────────────────────────
CATALOG_ID      = os.getenv("WHATSAPP_CATALOG_ID", "YOUR_CATALOG_ID_HERE")
SHOP_BASE_URL   = "https://a-jewel-studio-3.myshopify.com"
JOIN_US_PAGE    = f"{SHOP_BASE_URL}/pages/join-us"
WA_API_URL      = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
HEADERS         = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}

# ──────────────────────────────────────────────────────────────────
#  82 CATALOG COLLECTIONS — Real WhatsApp Collection IDs
#
#  KEY FORMAT: category_type
#  collection_id → WhatsApp catalog mein jo ID hai
#  name          → Customer ko dikhne wala naam
# ──────────────────────────────────────────────────────────────────
COLLECTIONS: dict[str, dict] = {

    # ── Baby Jewellery — Little Treasures ────────────────────────
    "baby_hair":              {"name": "Little Treasures - Hair Accessories",  "collection_id": "26930579176543121"},
    "baby_earrings":          {"name": "Little Treasures - Earrings",          "collection_id": "34197166099927645"},
    "baby_chain":             {"name": "Little Treasures - Necklace Chains",   "collection_id": "34159752333640697"},
    "baby_rings":             {"name": "Little Treasures - Rings",             "collection_id": "27130321023234461"},
    "baby_payal":             {"name": "Little Treasures - Anklets",           "collection_id": "26132380466413425"},
    "baby_bangles":           {"name": "Little Treasures - Bangles",           "collection_id": "25812008941803035"},

    # ── Women Face — Eternal Elegance — Earrings ─────────────────
    "face_studs":             {"name": "Eternal Elegance - Diamond Studs",     "collection_id": "26648112538119124"},
    "face_jhumka":            {"name": "Eternal Elegance - Traditional Jhumka","collection_id": "26067705569545995"},
    "face_chandbali":         {"name": "Eternal Elegance - Chandbali Earrings","collection_id": "26459908080267418"},
    "face_hoops":             {"name": "Eternal Elegance - Classic Hoops",     "collection_id": "26507559175517690"},
    "face_cuff":              {"name": "Eternal Elegance - Ear Cuffs",         "collection_id": "25904630702480491"},
    "face_kanser":            {"name": "Eternal Elegance - Bridal Kanser",     "collection_id": "24428630293501712"},
    "face_bahubali":          {"name": "Eternal Elegance - Bahubali Earrings", "collection_id": "27263060009951006"},
    "face_drop":              {"name": "Eternal Elegance - Drop Earrings",     "collection_id": "27085758917680509"},
    "face_sui_dhaga":         {"name": "Eternal Elegance - Sui Dhaga",         "collection_id": "26527646070152559"},
    "face_chuk":              {"name": "Eternal Elegance - Vintage Chuk",      "collection_id": "26001425306208264"},

    # ── Women Face — Nose Jewellery ───────────────────────────────
    "face_nath":              {"name": "Eternal Elegance - Bridal Nath",       "collection_id": "26146672631634215"},
    "face_nose_pin":          {"name": "Eternal Elegance - Nose Pins",         "collection_id": "25816769131325224"},
    "face_septum":            {"name": "Eternal Elegance - Septum Rings",      "collection_id": "26137405402565188"},
    "face_clip_on":           {"name": "Eternal Elegance - Clip-On Nose Rings","collection_id": "25956080384032593"},

    # ── Women Face — Head Jewellery ───────────────────────────────
    "face_maang_tikka":       {"name": "Eternal Elegance - Maang Tikka",       "collection_id": "34096814326631390"},
    "face_matha_patti":       {"name": "Eternal Elegance - Matha Patti",       "collection_id": "25972597769065393"},
    "face_passa":             {"name": "Eternal Elegance - Passa",             "collection_id": "25853734394311094"},
    "face_head_kanser":       {"name": "Eternal Elegance - Head Kanser",       "collection_id": "26924099463860066"},
    "face_sheesh_phool":      {"name": "Eternal Elegance - Sheesh Phool",      "collection_id": "25884225787909036"},

    # ── Hair ──────────────────────────────────────────────────────
    "hair_clips":             {"name": "Signature Collection - Hair Accessories","collection_id": "25923141554014968"},

    # ── Women Hand — Bangles & Kada ───────────────────────────────
    "hand_bangles":           {"name": "Eternal Elegance - Traditional Bangles","collection_id": "25990285673976585"},
    "hand_kada":              {"name": "Eternal Elegance - Designer Kada",     "collection_id": "26202123256143866"},

    # ── Women Hand — Bracelets ────────────────────────────────────
    "hand_bracelet":          {"name": "Eternal Elegance - Bracelets",         "collection_id": "26479540271641962"},
    "hand_bracelet_chain":    {"name": "Eternal Elegance - Chain Bracelets",   "collection_id": "26553938717531086"},
    "hand_bracelet_charm":    {"name": "Eternal Elegance - Charm Bracelets",   "collection_id": "25889526627383303"},
    "hand_bracelet_cuff":     {"name": "Eternal Elegance - Cuff Bracelets",    "collection_id": "26095567730084970"},

    # ── Women Hand — Armlet ───────────────────────────────────────
    "hand_baju_band":         {"name": "Eternal Elegance - Baju Band",         "collection_id": "25741475325553252"},

    # ── Women Hand — Rings ────────────────────────────────────────
    "hand_rings":             {"name": "Eternal Elegance - Designer Rings",    "collection_id": "26458893303705648"},
    "hand_rings_engagement":  {"name": "Eternal Elegance - Engagement Rings",  "collection_id": "26577195808532633"},
    "hand_rings_wedding":     {"name": "Eternal Elegance - Wedding Bands",     "collection_id": "26283285724614486"},
    "hand_rings_fashion":     {"name": "Eternal Elegance - Fashion Rings",     "collection_id": "26627787650158306"},

    # ── Women Neck — Necklaces ────────────────────────────────────
    "neck_haar":              {"name": "Eternal Elegance - Traditional Haar",  "collection_id": "34124391790542901"},
    "neck_choker":            {"name": "Eternal Elegance - Modern Chokers",    "collection_id": "34380933844854505"},
    "neck_princess":          {"name": "Eternal Elegance - Princess Necklaces","collection_id": "27036678569255877"},
    "neck_matinee":           {"name": "Eternal Elegance - Matinee Necklaces", "collection_id": "34810362708554746"},

    # ── Women Neck — Pendants ─────────────────────────────────────
    "neck_solitaire":         {"name": "Eternal Elegance - Solitaire Pendants","collection_id": "26345939121667071"},
    "neck_locket":            {"name": "Eternal Elegance - Locket Pendants",   "collection_id": "34949414394649401"},
    "neck_statement":         {"name": "Eternal Elegance - Statement Pendants","collection_id": "34061823006795079"},

    # ── Women Neck — Sets ─────────────────────────────────────────
    "neck_sets":              {"name": "Eternal Elegance - Bridal Sets",       "collection_id": "34181230154825697"},

    # ── Women Lower Body ──────────────────────────────────────────
    "lower_kamarband":        {"name": "Eternal Elegance - Kamarband",         "collection_id": "25970100975978085"},
    "lower_payal":            {"name": "Eternal Elegance - Payal Anklets",     "collection_id": "26108970985433226"},
    "lower_toe_rings":        {"name": "Eternal Elegance - Toe Rings",         "collection_id": "26041413228854859"},

    # ── Men — Rings ───────────────────────────────────────────────
    "men_rings_wedding":      {"name": "Bold Heritage - Wedding Bands",        "collection_id": "35279590828306838"},
    "men_rings_engagement":   {"name": "Bold Heritage - Engagement Rings",     "collection_id": "26205064579128433"},
    "men_rings_signet":       {"name": "Bold Heritage - Signet Rings",         "collection_id": "26133044123050259"},
    "men_rings_fashion":      {"name": "Bold Heritage - Fashion Rings",        "collection_id": "26353107324312966"},
    "men_rings_band":         {"name": "Bold Heritage - Classic Bands",        "collection_id": "26048808064813747"},
    "men_rings_stone":        {"name": "Bold Heritage - Gemstone Rings",       "collection_id": "25392189793787605"},

    # ── Men — Bracelets ───────────────────────────────────────────
    "men_bracelet_chain":     {"name": "Bold Heritage - Chain Bracelets",      "collection_id": "26028399416826135"},
    "men_bracelet_leather":   {"name": "Bold Heritage - Leather Bracelets",    "collection_id": "24614722568226121"},
    "men_bracelet_beaded":    {"name": "Bold Heritage - Beaded Bracelets",     "collection_id": "26526947026910291"},
    "men_bracelet_cuff":      {"name": "Bold Heritage - Cuff Bracelets",       "collection_id": "26224048963949143"},

    # ── Men — Chains ──────────────────────────────────────────────
    "men_chain_gold":         {"name": "Bold Heritage - Gold Chains",          "collection_id": "26614026711549117"},
    "men_chain_silver":       {"name": "Bold Heritage - Silver Chains",        "collection_id": "35305915439007559"},
    "men_chain_rope":         {"name": "Bold Heritage - Rope Chains",          "collection_id": "25364645956543386"},

    # ── Men — Pendants ────────────────────────────────────────────
    "men_pendant_religious":  {"name": "Bold Heritage - Religious Pendants",   "collection_id": "34138553902457530"},
    "men_pendant_initial":    {"name": "Bold Heritage - Initial Pendants",     "collection_id": "26251311201160440"},
    "men_pendant_stone":      {"name": "Bold Heritage - Gemstone Pendants",    "collection_id": "26441867825407906"},

    # ── Men — Kada ────────────────────────────────────────────────
    "men_kada_traditional":   {"name": "Bold Heritage - Traditional Kada",     "collection_id": "26080348848282889"},
    "men_kada_modern":        {"name": "Bold Heritage - Modern Kada",          "collection_id": "26028780853472858"},

    # ── Men — Accessories ─────────────────────────────────────────
    "men_cufflinks_classic":  {"name": "Bold Heritage - Classic Cufflinks",    "collection_id": "25956694700651645"},
    "men_cufflinks_designer": {"name": "Bold Heritage - Designer Cufflinks",   "collection_id": "25283486371327046"},
    "men_tie_pins":           {"name": "Bold Heritage - Tie Pins",             "collection_id": "34056958820614334"},
    "men_brooches":           {"name": "Bold Heritage - Brooches",             "collection_id": "27093254823609535"},

    # ── Studio Special — Watches ──────────────────────────────────
    "watches_men":            {"name": "Signature Collection - Men Timepieces",    "collection_id": "34176915238618497"},
    "watches_women":          {"name": "Signature Collection - Women Timepieces",  "collection_id": "26903528372573194"},
    "watches_kids":           {"name": "Signature Collection - Kids Timepieces",   "collection_id": "26311558718468909"},
    "watches_smart":          {"name": "Signature Collection - Smart Watches",     "collection_id": "25912162851771673"},
    "watches_luxury":         {"name": "Signature Collection - Luxury Timepieces", "collection_id": "26667915832816156"},

    # ── Studio Special — Accessories ──────────────────────────────
    "keychains":              {"name": "Signature Collection - Premium Keychains", "collection_id": "26255788447385252"},
    "clutches":               {"name": "Signature Collection - Evening Clutches",  "collection_id": "34514139158199452"},
    "sunglasses":             {"name": "Signature Collection - Sunglasses",        "collection_id": "25258040713868720"},
    "belts":                  {"name": "Signature Collection - Designer Belts",    "collection_id": "26176082815414211"},

    # ── Murti & Art ───────────────────────────────────────────────
    "murti_figurines":        {"name": "Divine Blessings - Sacred Idols",          "collection_id": "26255788447385252"},
}

# ─────────────────────────────────────────────
#  KEYWORD → COLLECTION KEY MAP
# ─────────────────────────────────────────────
KEYWORD_MAP: dict[str, str] = {
    # Jhumka
    "jhumka": "face_jhumka", "jumka": "face_jhumka", "jhoomka": "face_jhumka",
    # Nath
    "nath": "face_nath", "nathni": "face_nath", "bridal nath": "face_nath",
    # Baby
    "baby kada": "baby_bangles", "baby bangle": "baby_bangles", "baby bangles": "baby_bangles",
    "baby earring": "baby_earrings", "baby necklace": "baby_chain",
    # Bangles
    "bangles": "hand_bangles", "bangle": "hand_bangles", "kada": "hand_kada",
    # Choker
    "choker": "neck_choker",
    # Necklace
    "necklace": "neck_haar", "haar": "neck_haar",
    # Anklet
    "anklet": "lower_payal", "payal": "lower_payal",
    # Maang Tikka
    "maang tikka": "face_maang_tikka", "tikka": "face_maang_tikka",
    # Matha Patti
    "matha patti": "face_matha_patti",
    # Haath Phool — no direct collection, map to bracelet
    "haath phool": "hand_bracelet",
    # Kamarband
    "kamarbandh": "lower_kamarband", "kamarband": "lower_kamarband",
    # Rings
    "ring": "hand_rings", "rings": "hand_rings",
    "engagement ring": "hand_rings_engagement",
    "wedding band": "hand_rings_wedding",
    # Bracelets
    "bracelet": "hand_bracelet",
    # Studs
    "studs": "face_studs", "stud": "face_studs",
    # Chandbali
    "chandbali": "face_chandbali",
    # Nose pin
    "nose pin": "face_nose_pin", "nosepin": "face_nose_pin",
    # Murti
    "ganesh": "murti_figurines", "ganesha": "murti_figurines", "murti": "murti_figurines",
    "laxmi": "murti_figurines",
    # Men
    "men chain": "men_chain_gold", "men bracelet": "men_bracelet_chain",
    "men ring": "men_rings_fashion", "men kada": "men_kada_traditional",
    # Watches
    "watch": "watches_men", "watches": "watches_men",
    # Passa
    "passa": "face_passa",
    # Sheesh Phool
    "sheesh phool": "face_sheesh_phool", "shish phool": "face_sheesh_phool",
    # Cufflinks
    "cufflinks": "men_cufflinks_classic",
    # Sets
    "bridal set": "neck_sets", "bridal sets": "neck_sets",
}

# ─────────────────────────────────────────────
#  SESSION STORE  (30-min TTL)
# ─────────────────────────────────────────────
sessions: dict = {}
SESSION_TTL    = 1800

def get_session(phone: str) -> dict:
    now = time.time()
    s   = sessions.get(phone)
    if s and (now - s["ts"]) < SESSION_TTL:
        s["ts"] = now
        return s
    sessions[phone] = {"nav": [], "ts": now}
    return sessions[phone]

def push_nav(phone: str, state: str):
    get_session(phone)["nav"].append(state)

def pop_nav(phone: str) -> str | None:
    nav = get_session(phone)["nav"]
    return nav.pop() if nav else None

# ─────────────────────────────────────────────
#  GOOGLE SHEETS HELPER
# ─────────────────────────────────────────────
def get_customer(phone: str) -> dict | None:
    try:
        r = requests.get(GOOGLE_SHEETS_URL, params={"action": "get", "phone": phone}, timeout=5)
        data = r.json()
        return data if data.get("exists") else None
    except Exception as e:
        logger.error(f"Sheets GET error: {e}")
        return None

def add_customer_phone(phone: str):
    try:
        requests.post(GOOGLE_SHEETS_URL, json={"action": "add", "phone": phone}, timeout=5)
    except Exception as e:
        logger.error(f"Sheets ADD error: {e}")

# ─────────────────────────────────────────────
#  WHATSAPP API — BASE SENDER
# ─────────────────────────────────────────────
def _send(payload: dict) -> dict | None:
    try:
        r = requests.post(WA_API_URL, headers=HEADERS, json=payload, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        logger.error(f"WhatsApp API error: {e}")
        return None

# ─────────────────────────────────────────────
#  WHATSAPP API — MESSAGE TYPES
# ─────────────────────────────────────────────
def send_text(to: str, text: str):
    _send({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text, "preview_url": False}
    })

def send_image(to: str, image_url: str, caption: str = ""):
    _send({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": {"link": image_url, "caption": caption}
    })

def send_cta_button(to: str, body_text: str, button_text: str, url: str):
    _send({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "cta_url",
            "body": {"text": body_text},
            "action": {
                "name": "cta_url",
                "parameters": {"display_text": button_text, "url": url}
            }
        }
    })

def send_reply_buttons(to: str, body_text: str, buttons: list[str]):
    """Max 3 quick-reply buttons. Falls back to numbered text if API fails."""
    if len(buttons) > 3:
        send_text(to, body_text + "\n\n" + "\n".join(f"{i+1}. {b}" for i, b in enumerate(buttons)))
        return
    btn_list = [
        {"type": "reply", "reply": {"id": f"btn_{i}", "title": b}}
        for i, b in enumerate(buttons)
    ]
    result = _send({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body_text},
            "action": {"buttons": btn_list}
        }
    })
    if not result:
        send_text(to, body_text + "\n\n" + "\n".join(f"{i+1}. {b}" for i, b in enumerate(buttons)))

def send_list_menu(to: str, header: str, body: str, button_label: str, sections: list[dict]):
    _send({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": header},
            "body": {"text": body},
            "action": {"button": button_label, "sections": sections}
        }
    })

# ─────────────────────────────────────────────
#  CATALOG COLLECTION SENDER
#
#  WhatsApp product_list message with product_collection_id
#  Yeh directly specific collection kholega — pura catalog nahi
# ─────────────────────────────────────────────
def send_catalog_collection(to: str, collection_key: str):
    """
    Specific WhatsApp catalog collection send karta hai.
    product_collection_id se sirf wo collection khulegi.
    """
    col = COLLECTIONS.get(collection_key)
    if not col:
        logger.warning(f"Collection key not found: {collection_key}")
        send_text(to, "Sorry, this collection is not available right now.")
        return

    collection_name = col["name"]
    collection_id   = col["collection_id"]

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "product_list",
            "header": {
                "type": "text",
                "text": collection_name
            },
            "body": {
                "text": "Explore our collection. Tap any item to view details and place an order."
            },
            "footer": {
                "text": "A Jewel Studio — Premium Handcrafted Jewellery"
            },
            "action": {
                "catalog_id": CATALOG_ID,
                "sections": [
                    {
                        "title": collection_name,
                        "product_collection_id": collection_id
                        # Note: WhatsApp automatically loads all products
                        # from this collection_id — no need to list product IDs manually
                    }
                ]
            }
        }
    }

    result = _send(payload)

    # Fallback: agar product_list kaam na kare toh catalog_message bhejna
    if not result:
        logger.warning(f"product_list failed for {collection_key}, trying catalog_message fallback")
        _send_catalog_message_fallback(to, collection_name)

def _send_catalog_message_fallback(to: str, collection_name: str):
    """Fallback: catalog_message type — pura catalog khulega."""
    _send({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "catalog_message",
            "body": {"text": f"View our {collection_name} collection below."},
            "action": {
                "name": "catalog_message",
                "parameters": {}
            }
        }
    })

# ─────────────────────────────────────────────
#  SMART SEARCH
# ─────────────────────────────────────────────
def smart_search(query: str) -> str | None:
    q = query.lower().strip()
    # Direct match
    for keyword, key in KEYWORD_MAP.items():
        if keyword in q:
            return key
    # Word-level partial match
    for keyword, key in KEYWORD_MAP.items():
        if any(w in q for w in keyword.split()):
            return key
    return None

# ─────────────────────────────────────────────
#  ORDER TRACKING
# ─────────────────────────────────────────────
def track_order(order_id: str) -> str:
    try:
        r    = requests.get(f"{BACKEND_API_URL}/orders/{order_id}", timeout=5)
        data = r.json()
        return (
            f"*Order Status*\n\n"
            f"Order ID: {order_id}\n"
            f"Status: {data.get('status', 'Unknown')}\n"
            f"Expected Date: {data.get('readyDate', 'TBD')}"
        )
    except Exception:
        return f"Could not fetch order *{order_id}*. Please try again or contact us."

# ─────────────────────────────────────────────
#  REFERRAL CODE
# ─────────────────────────────────────────────
def generate_referral_code(name: str, phone: str) -> str:
    initials = "".join(w[0].upper() for w in name.split()[:2])
    return f"{initials}{phone[-4:]}"

# ─────────────────────────────────────────────
#  GEMINI AI FALLBACK
# ─────────────────────────────────────────────
def get_ai_response(message: str, customer_name: str, customer_type: str) -> str:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model  = genai.GenerativeModel("gemini-1.5-flash")
        prompt = (
            f"You are a helpful assistant for 'A Jewel Studio', a premium Indian jewellery brand. "
            f"Customer name: {customer_name}. Customer type: {customer_type}. "
            f"Reply warmly and professionally in under 3 sentences. "
            f"If unsure, suggest browsing collections or contacting the team.\n\n"
            f"Customer: {message}"
        )
        return model.generate_content(prompt).text.strip()
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        return f"Thank you for reaching out, {customer_name}. Our team will assist you shortly."

# ─────────────────────────────────────────────
#  IMAGE ANALYSIS (Gemini Vision)
# ─────────────────────────────────────────────
def analyze_jewelry_image(image_url: str) -> dict:
    try:
        import base64
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model    = genai.GenerativeModel("gemini-1.5-flash")
        img_data = requests.get(image_url, headers=HEADERS, timeout=10).content
        encoded  = base64.b64encode(img_data).decode("utf-8")
        response = model.generate_content([
            'Analyze this jewelry image. Reply ONLY in JSON: '
            '{"type":"Earring","style":"Traditional","category":"Women","subcategory":"jhumka"}. '
            'subcategory must match one of: jhumka, studs, chandbali, hoops, cuff, nath, '
            'nose_pin, maang_tikka, matha_patti, passa, sheesh_phool, bangles, bracelet, '
            'rings, necklace, choker, anklet, kamarband',
            {"mime_type": "image/jpeg", "data": encoded}
        ])
        text = response.text.strip().strip("```json").strip("```")
        return json.loads(text)
    except Exception as e:
        logger.error(f"Image analysis error: {e}")
        return {}

def find_collection_from_analysis(analysis: dict) -> str | None:
    subcategory = analysis.get("subcategory", "").lower()
    return KEYWORD_MAP.get(subcategory)

# ─────────────────────────────────────────────
#  MENUS
# ─────────────────────────────────────────────
def send_main_menu(to: str):
    push_nav(to, "main_menu")
    send_list_menu(
        to,
        header="A Jewel Studio",
        body="What are you looking for today? Choose a category.",
        button_label="Browse Categories",
        sections=[{
            "title": "Collections",
            "rows": [
                {"id": "cat_baby",   "title": "Baby Jewellery",   "description": "Cute and safe for little ones"},
                {"id": "cat_women",  "title": "Women Jewellery",  "description": "Earrings, necklaces, bangles and more"},
                {"id": "cat_men",    "title": "Men Jewellery",    "description": "Rings, chains and bracelets"},
                {"id": "cat_studio", "title": "Studio Special",   "description": "Watches, accessories and custom pieces"},
                {"id": "cat_murti",  "title": "Murti and Art",    "description": "Divine idols and decorative art"},
            ]
        }]
    )

def send_women_body_menu(to: str):
    push_nav(to, "women_body")
    send_reply_buttons(to, "Women Jewellery\n\nChoose a category:",
                       ["Face Jewellery", "Hand Jewellery", "Neck Jewellery", "Lower Body"])

def send_face_jewellery_menu(to: str):
    push_nav(to, "face_menu")
    send_list_menu(
        to,
        header="Face Jewellery",
        body="Select a type to explore the collection:",
        button_label="View Types",
        sections=[
            {
                "title": "Earrings",
                "rows": [
                    {"id": "face_studs",     "title": "Diamond Studs"},
                    {"id": "face_jhumka",    "title": "Traditional Jhumka"},
                    {"id": "face_chandbali", "title": "Chandbali Earrings"},
                    {"id": "face_hoops",     "title": "Classic Hoops"},
                    {"id": "face_cuff",      "title": "Ear Cuffs"},
                    {"id": "face_kanser",    "title": "Bridal Kanser"},
                    {"id": "face_bahubali",  "title": "Bahubali Earrings"},
                    {"id": "face_drop",      "title": "Drop Earrings"},
                    {"id": "face_sui_dhaga", "title": "Sui Dhaga"},
                    {"id": "face_chuk",      "title": "Vintage Chuk"},
                ]
            },
            {
                "title": "Nose Jewellery",
                "rows": [
                    {"id": "face_nath",    "title": "Bridal Nath"},
                    {"id": "face_nose_pin","title": "Nose Pins"},
                    {"id": "face_septum",  "title": "Septum Rings"},
                    {"id": "face_clip_on", "title": "Clip-On Nose Rings"},
                ]
            },
            {
                "title": "Head Jewellery",
                "rows": [
                    {"id": "face_maang_tikka",  "title": "Maang Tikka"},
                    {"id": "face_matha_patti",  "title": "Matha Patti"},
                    {"id": "face_passa",        "title": "Passa"},
                    {"id": "face_head_kanser",  "title": "Head Kanser"},
                    {"id": "face_sheesh_phool", "title": "Sheesh Phool"},
                ]
            }
        ]
    )

def send_hand_jewellery_menu(to: str):
    push_nav(to, "hand_menu")
    send_list_menu(
        to,
        header="Hand Jewellery",
        body="Select a type:",
        button_label="View Types",
        sections=[
            {
                "title": "Bangles and Kada",
                "rows": [
                    {"id": "hand_bangles", "title": "Traditional Bangles"},
                    {"id": "hand_kada",    "title": "Designer Kada"},
                ]
            },
            {
                "title": "Bracelets",
                "rows": [
                    {"id": "hand_bracelet",       "title": "Bracelets"},
                    {"id": "hand_bracelet_chain",  "title": "Chain Bracelets"},
                    {"id": "hand_bracelet_charm",  "title": "Charm Bracelets"},
                    {"id": "hand_bracelet_cuff",   "title": "Cuff Bracelets"},
                ]
            },
            {
                "title": "Rings",
                "rows": [
                    {"id": "hand_rings",            "title": "Designer Rings"},
                    {"id": "hand_rings_engagement", "title": "Engagement Rings"},
                    {"id": "hand_rings_wedding",    "title": "Wedding Bands"},
                    {"id": "hand_rings_fashion",    "title": "Fashion Rings"},
                ]
            },
            {
                "title": "Armlet",
                "rows": [
                    {"id": "hand_baju_band", "title": "Baju Band"},
                ]
            }
        ]
    )

def send_neck_jewellery_menu(to: str):
    push_nav(to, "neck_menu")
    send_list_menu(
        to,
        header="Neck Jewellery",
        body="Select a type:",
        button_label="View Types",
        sections=[
            {
                "title": "Necklaces",
                "rows": [
                    {"id": "neck_haar",     "title": "Traditional Haar"},
                    {"id": "neck_choker",   "title": "Modern Chokers"},
                    {"id": "neck_princess", "title": "Princess Necklaces"},
                    {"id": "neck_matinee",  "title": "Matinee Necklaces"},
                ]
            },
            {
                "title": "Pendants",
                "rows": [
                    {"id": "neck_solitaire", "title": "Solitaire Pendants"},
                    {"id": "neck_locket",    "title": "Locket Pendants"},
                    {"id": "neck_statement", "title": "Statement Pendants"},
                ]
            },
            {
                "title": "Sets",
                "rows": [
                    {"id": "neck_sets", "title": "Bridal Sets"},
                ]
            }
        ]
    )

def send_lower_body_menu(to: str):
    push_nav(to, "lower_menu")
    send_list_menu(
        to,
        header="Lower Body Jewellery",
        body="Select a type:",
        button_label="View Types",
        sections=[{
            "title": "Lower Body",
            "rows": [
                {"id": "lower_kamarband",  "title": "Kamarband"},
                {"id": "lower_payal",      "title": "Payal Anklets"},
                {"id": "lower_toe_rings",  "title": "Toe Rings"},
            ]
        }]
    )

def send_baby_jewellery_menu(to: str):
    push_nav(to, "baby_menu")
    send_list_menu(
        to,
        header="Baby Jewellery",
        body="Cute and safe jewellery for little ones:",
        button_label="View Types",
        sections=[{
            "title": "Baby Collection",
            "rows": [
                {"id": "baby_bangles",  "title": "Bangles"},
                {"id": "baby_earrings", "title": "Earrings"},
                {"id": "baby_chain",    "title": "Necklace Chains"},
                {"id": "baby_rings",    "title": "Rings"},
                {"id": "baby_payal",    "title": "Anklets"},
                {"id": "baby_hair",     "title": "Hair Accessories"},
            ]
        }]
    )

def send_men_jewellery_menu(to: str):
    push_nav(to, "men_menu")
    send_list_menu(
        to,
        header="Men Jewellery",
        body="Bold Heritage collection — select a type:",
        button_label="View Types",
        sections=[
            {
                "title": "Rings",
                "rows": [
                    {"id": "men_rings_wedding",    "title": "Wedding Bands"},
                    {"id": "men_rings_engagement",  "title": "Engagement Rings"},
                    {"id": "men_rings_signet",      "title": "Signet Rings"},
                    {"id": "men_rings_fashion",     "title": "Fashion Rings"},
                    {"id": "men_rings_band",        "title": "Classic Bands"},
                    {"id": "men_rings_stone",       "title": "Gemstone Rings"},
                ]
            },
            {
                "title": "Bracelets",
                "rows": [
                    {"id": "men_bracelet_chain",   "title": "Chain Bracelets"},
                    {"id": "men_bracelet_leather",  "title": "Leather Bracelets"},
                    {"id": "men_bracelet_beaded",   "title": "Beaded Bracelets"},
                    {"id": "men_bracelet_cuff",     "title": "Cuff Bracelets"},
                ]
            },
            {
                "title": "Chains",
                "rows": [
                    {"id": "men_chain_gold",   "title": "Gold Chains"},
                    {"id": "men_chain_silver",  "title": "Silver Chains"},
                    {"id": "men_chain_rope",    "title": "Rope Chains"},
                ]
            },
            {
                "title": "Pendants",
                "rows": [
                    {"id": "men_pendant_religious", "title": "Religious Pendants"},
                    {"id": "men_pendant_initial",   "title": "Initial Pendants"},
                    {"id": "men_pendant_stone",     "title": "Gemstone Pendants"},
                ]
            },
            {
                "title": "Kada and Accessories",
                "rows": [
                    {"id": "men_kada_traditional",  "title": "Traditional Kada"},
                    {"id": "men_kada_modern",       "title": "Modern Kada"},
                    {"id": "men_cufflinks_classic", "title": "Classic Cufflinks"},
                    {"id": "men_cufflinks_designer","title": "Designer Cufflinks"},
                    {"id": "men_tie_pins",          "title": "Tie Pins"},
                    {"id": "men_brooches",          "title": "Brooches"},
                ]
            }
        ]
    )

def send_studio_special_menu(to: str):
    push_nav(to, "studio_menu")
    send_list_menu(
        to,
        header="Studio Special",
        body="Signature Collection — select a category:",
        button_label="View Types",
        sections=[
            {
                "title": "Timepieces",
                "rows": [
                    {"id": "watches_men",    "title": "Men Timepieces"},
                    {"id": "watches_women",  "title": "Women Timepieces"},
                    {"id": "watches_kids",   "title": "Kids Timepieces"},
                    {"id": "watches_smart",  "title": "Smart Watches"},
                    {"id": "watches_luxury", "title": "Luxury Timepieces"},
                ]
            },
            {
                "title": "Accessories",
                "rows": [
                    {"id": "keychains",  "title": "Premium Keychains"},
                    {"id": "clutches",   "title": "Evening Clutches"},
                    {"id": "sunglasses", "title": "Sunglasses"},
                    {"id": "belts",      "title": "Designer Belts"},
                    {"id": "hair_clips", "title": "Hair Accessories"},
                ]
            }
        ]
    )

# ─────────────────────────────────────────────
#  CORE MESSAGE HANDLER
# ─────────────────────────────────────────────
def handle_message(phone: str, message_type: str, body: str, interactive_id: str = ""):
    customer = get_customer(phone)

    # ── Flow 1: New Customer ─────────────────────────────────────
    if customer is None:
        add_customer_phone(phone)
        send_image(phone,
            image_url=f"{SHOP_BASE_URL}/cdn/shop/files/logo.png",
            caption="Welcome to A Jewel Studio\nPremium Handcrafted Jewellery")
        time.sleep(2)
        send_cta_button(phone,
            "Join our exclusive community to browse collections, track orders, and get personalised recommendations.",
            "Join Us",
            f"{JOIN_US_PAGE}?wa={phone}")
        return

    has_form    = customer.get("name") and customer.get("type")
    cust_name   = customer.get("name", "Valued Customer")
    cust_type   = customer.get("type", "Retail")

    # ── Flow 2: Incomplete Registration ─────────────────────────
    if not has_form:
        send_text(phone, "It looks like you messaged us before but did not complete registration.")
        send_cta_button(phone,
            "Complete your registration to unlock the full experience.",
            "Complete Registration",
            f"{JOIN_US_PAGE}?wa={phone}")
        return

    # ── Registered Customers ─────────────────────────────────────
    text   = body.strip().lower() if body else ""
    nav_id = interactive_id.lower() if interactive_id else ""

    # Back navigation
    if text in ("back", "menu", "main menu"):
        prev = pop_nav(phone)
        if prev in ("women_body", "face_menu", "hand_menu", "neck_menu", "lower_menu"):
            send_women_body_menu(phone)
        else:
            _welcome_back(phone, cust_name, cust_type)
        return

    # Greetings
    if text in ("hi", "hello", "hey", "hlo", "hii", "namaste", "start"):
        _welcome_back(phone, cust_name, cust_type)
        return

    # Order tracking
    if "track" in text or text.upper().startswith("AJS"):
        words    = text.split()
        order_id = next((w.upper() for w in words if w.upper().startswith("AJS")), None)
        if order_id:
            send_text(phone, track_order(order_id))
        else:
            send_text(phone, "Please send your Order ID.\nExample: Track AJS123456")
        return

    # Referral
    if text == "referral":
        code = generate_referral_code(cust_name, phone)
        send_text(phone,
            f"*Your Referral Code*\n\nCode: *{code}*\n\n"
            f"Share this link:\n{JOIN_US_PAGE}?ref={code}")
        return

    # Help
    if text == "help":
        if cust_type == "B2B":
            send_reply_buttons(phone, "How can I help you?", ["Browse Files", "Custom File", "My Orders"])
        else:
            send_reply_buttons(phone, "How can I help you?", ["Browse Collections", "Custom Design", "Connect with Us"])
        return

    # Business hours
    if "hour" in text or "timing" in text:
        send_text(phone,
            "*Business Hours*\n\n"
            "Monday to Saturday\n10:00 AM – 7:00 PM\n\n"
            "Sunday\n11:00 AM – 5:00 PM")
        return

    # About
    if text == "about":
        send_text(phone,
            "*About A Jewel Studio*\n\n"
            "Premium handcrafted jewellery crafted with love, tradition, and artistry. "
            "From bridal masterpieces to everyday elegance — each piece tells a story.")
        return

    # Interactive (list / button replies)
    if interactive_id:
        _handle_interactive(phone, interactive_id, cust_name, cust_type)
        return

    # Image upload
    if message_type == "image":
        _handle_image(phone, body)
        return

    # Smart text search
    col_key = smart_search(text)
    if col_key:
        send_catalog_collection(phone, col_key)
        return

    # AI Fallback
    ai_reply = get_ai_response(body, cust_name, cust_type)
    send_text(phone, ai_reply)
    time.sleep(1)
    if cust_type == "B2B":
        send_reply_buttons(phone, "Can I help with anything else?", ["Browse Files", "Custom File", "Connect with Team"])
    else:
        send_reply_buttons(phone, "Can I help with anything else?", ["Browse Collections", "Connect with Team"])

# ─────────────────────────────────────────────
#  INTERACTIVE HANDLER
# ─────────────────────────────────────────────
def _handle_interactive(phone: str, iid: str, name: str, ctype: str):
    # Main menu
    if iid == "cat_women":  send_women_body_menu(phone);  return
    if iid == "cat_baby":   send_baby_jewellery_menu(phone); return
    if iid == "cat_men":    send_men_jewellery_menu(phone);  return
    if iid == "cat_studio": send_studio_special_menu(phone); return
    if iid == "cat_murti":  send_catalog_collection(phone, "murti_figurines"); return

    # Women body parts (from reply buttons)
    if "face jewellery" in iid or iid == "btn_0":  send_face_jewellery_menu(phone); return
    if "hand jewellery" in iid or iid == "btn_1":  send_hand_jewellery_menu(phone); return
    if "neck jewellery" in iid or iid == "btn_2":  send_neck_jewellery_menu(phone); return
    if "lower body"     in iid or iid == "btn_3":  send_lower_body_menu(phone);     return

    # B2B
    if "browse files" in iid: send_main_menu(phone); return
    if "custom file"  in iid:
        send_text(phone, "Please send your custom design requirements or upload a reference image.")
        return
    if "my orders" in iid:
        send_text(phone, "Please send your Order ID.\nExample: Track AJS123456")
        return

    # Direct catalog collection keys (from list menus)
    if iid in COLLECTIONS:
        send_catalog_collection(phone, iid)
        return

    # Fallback
    send_main_menu(phone)

# ─────────────────────────────────────────────
#  WELCOME BACK
# ─────────────────────────────────────────────
def _welcome_back(phone: str, name: str, ctype: str):
    if ctype == "B2B":
        send_text(phone, f"Welcome back, *{name}*.\nHow can we assist you today?")
        send_reply_buttons(phone, "Select an option:", ["Browse Files", "Custom File", "My Orders"])
    else:
        send_text(phone, f"Welcome back, *{name}*.\nWe are delighted to have you here.")
        time.sleep(1)
        send_main_menu(phone)

# ─────────────────────────────────────────────
#  IMAGE HANDLER
# ─────────────────────────────────────────────
def _handle_image(phone: str, image_url: str):
    send_text(phone, "Analyzing your image, please wait...")
    analysis = analyze_jewelry_image(image_url)
    if not analysis:
        send_text(phone, "Could not analyze the image. Please try a clearer photo or type a product name.")
        return
    col_key  = find_collection_from_analysis(analysis)
    atype    = analysis.get("type", "jewellery")
    astyle   = analysis.get("style", "")
    time.sleep(2)
    send_text(phone, f"I found similar products for *{astyle} {atype}*.")
    time.sleep(1)
    if col_key:
        send_catalog_collection(phone, col_key)
    else:
        send_main_menu(phone)

# ─────────────────────────────────────────────
#  HEALTH CHECK  (Render / uptime monitors)
# ─────────────────────────────────────────────
@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "running", "service": "A Jewel Studio WhatsApp Bot"}), 200

# ─────────────────────────────────────────────
#  WEBHOOK ROUTES
# ─────────────────────────────────────────────
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode      = request.args.get("hub.mode")
    token     = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("Webhook verified.")
        return challenge, 200
    return "Forbidden", 403

@app.route("/webhook", methods=["POST"])
def receive_message():
    data = request.get_json()
    try:
        entry        = data["entry"][0]["changes"][0]["value"]
        phone        = entry["contacts"][0]["wa_id"]
        msg          = entry["messages"][0]
        msg_type     = msg["type"]
        body         = ""
        interactive_id = ""

        if msg_type == "text":
            body = msg["text"]["body"]

        elif msg_type == "interactive":
            itype = msg["interactive"]["type"]
            if itype == "button_reply":
                interactive_id = msg["interactive"]["button_reply"]["title"]
                body           = interactive_id
            elif itype == "list_reply":
                interactive_id = msg["interactive"]["list_reply"]["id"]
                body           = msg["interactive"]["list_reply"]["title"]

        elif msg_type == "image":
            image_id  = msg["image"]["id"]
            media_res = requests.get(
                f"https://graph.facebook.com/v18.0/{image_id}",
                headers=HEADERS, timeout=5
            )
            body     = media_res.json().get("url", "")
            msg_type = "image"

        handle_message(phone, msg_type, body, interactive_id)

    except (KeyError, IndexError) as e:
        logger.warning(f"Webhook parse error: {e}")

    return jsonify({"status": "ok"}), 200

# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"A Jewel Studio Bot running on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
