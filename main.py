"""
A JEWEL STUDIO — WhatsApp Bot
Aru AI Assistant | 82 Collections | Bilingual | Full Production

NAVIGATION TREE
===============
MAIN MENU (scroll list)
  Baby Jewellery     → scroll list (6 collections) → catalog
  Women Jewellery    → buttons (3 body areas + lower body)
    Face Jewellery   → scroll list with 4 sections (Earrings/Nose/Head/Hair)
    Hand Jewellery   → scroll list with 4 sections (Bangles/Bracelets/Armlets/Rings)
    Neck Jewellery   → scroll list with 3 sections (Necklaces/Pendants/Bridal)
    Lower Body       → scroll list (3 collections) → catalog
  Men Jewellery      → scroll list with 4 sections (Rings/Bracelets/Chains/Accessories)
  Studio Special     → buttons (Watches | Accessories)
    Watches          → scroll list (5 collections) → catalog
    Accessories      → scroll list (4 collections) → catalog
  Sacred Arts        → empty catalog message

CUSTOMER FLOWS
==============
New Customer           → Welcome msg + JOIN US button
Incomplete Reg         → Reminder + COMPLETE REGISTRATION button
Returning Retail       → Personalised welcome + main menu
Returning B2B          → Welcome + BROWSE COLLECTIONS / CUSTOM ORDER / MY ORDERS
Text / Image           → Aru handles (fuzzy search + AI + catalog)
Order (cart)           → Razorpay payment link
Empty catalog          → Custom order offer + admin email

ENVIRONMENT VARIABLES
=====================
WHATSAPP_TOKEN, WHATSAPP_PHONE_ID, WHATSAPP_CATALOG_ID, VERIFY_TOKEN
SHOPIFY_SHOP_DOMAIN, SHOPIFY_ACCESS_TOKEN
GOOGLE_SHEET_ID, GOOGLE_SERVICE_ACCOUNT_KEY
RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET
GEMINI_API_KEY
GMAIL_USER, GMAIL_PASSWORD
ADMIN_EMAIL_1 (axaysoni90@gmail.com), ADMIN_EMAIL_2 (mahaajanakshay@gmail.com)
"""

import os
import json
import logging
import time
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import gspread
from google.oauth2.service_account import Credentials
import razorpay
import google.generativeai as genai
from rapidfuzz import fuzz, process

# ─────────────────────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────────────────────

app = Flask(__name__)
CORS(app)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-7s  %(message)s'
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────

WA_TOKEN     = os.getenv('WHATSAPP_TOKEN', '')
WA_PHONE_ID  = os.getenv('WHATSAPP_PHONE_ID', '')
CATALOG_ID   = os.getenv('WHATSAPP_CATALOG_ID', '')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN', 'ajewel2024')

SHOPIFY_STORE = os.getenv('SHOPIFY_SHOP_DOMAIN', 'a-jewel-studio-3.myshopify.com')
SHOPIFY_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN', '')

SHEET_ID      = os.getenv('GOOGLE_SHEET_ID', '')
SHEET_KEY     = os.getenv('GOOGLE_SERVICE_ACCOUNT_KEY', '')

RZP_KEY_ID    = os.getenv('RAZORPAY_KEY_ID', '')
RZP_KEY_SEC   = os.getenv('RAZORPAY_KEY_SECRET', '')

GEMINI_KEY    = os.getenv('GEMINI_API_KEY', '')

GMAIL_USER    = os.getenv('GMAIL_USER', '')
GMAIL_PASS    = os.getenv('GMAIL_PASSWORD', '')
ADMIN_1       = os.getenv('ADMIN_EMAIL_1', 'axaysoni90@gmail.com')
ADMIN_2       = os.getenv('ADMIN_EMAIL_2', 'mahaajanakshay@gmail.com')

WA_API = f"https://graph.facebook.com/v19.0/{WA_PHONE_ID}/messages"

# ─────────────────────────────────────────────────────────────
# GEMINI
# ─────────────────────────────────────────────────────────────

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    _gm_text   = genai.GenerativeModel('gemini-pro')
    _gm_vision = genai.GenerativeModel('gemini-pro-vision')
else:
    _gm_text   = None
    _gm_vision = None

# ─────────────────────────────────────────────────────────────
# SESSION
# ─────────────────────────────────────────────────────────────

_sessions: dict = {}
_TIMEOUT = timedelta(minutes=30)

def get_session(phone: str) -> dict:
    now = datetime.now()
    if phone not in _sessions:
        _sessions[phone] = {
            'created':      now,
            'last':         now,
            'name':         'Valued Customer',
            'lang':         'en',
            'custom_step':  None,
        }
    _sessions[phone]['last'] = now
    return _sessions[phone]

def _cleanup():
    now = datetime.now()
    dead = [p for p, s in _sessions.items() if now - s['last'] > _TIMEOUT]
    for p in dead:
        del _sessions[p]

# ─────────────────────────────────────────────────────────────
# CATALOG — 82 COLLECTIONS
# ─────────────────────────────────────────────────────────────

# Structure: used to build scroll-list sections and flat lookup map.
# Each "leaf" collection has {'name': str, 'id': str}

BABY = {
    'Hair Accessories': '26930579176543121',
    'Earrings':         '34197166099927645',
    'Necklace Chains':  '34159752333640697',
    'Rings':            '27130321023234461',
    'Anklets':          '26132380466413425',
    'Bangles':          '25812008941803035',
}

FACE_EARRINGS = {
    'Diamond Studs':      '26648112538119124',
    'Traditional Jhumka': '26067705569545995',
    'Chandbali':          '26459908080267418',
    'Classic Hoops':      '26507559175517690',
    'Ear Cuffs':          '25904630702480491',
    'Bridal Kanser':      '24428630293501712',
    'Bahubali':           '27263060009951006',
    'Drop Earrings':      '27085758917680509',
    'Sui Dhaga':          '26527646070152559',
    'Vintage Chuk':       '26001425306208264',
}

FACE_NOSE = {
    'Bridal Nath':  '26146672631634215',
    'Nose Pins':    '25816769131325224',
    'Septum Rings': '26137405402565188',
    'Clip On Rings':'25956080384032593',
}

FACE_HEAD = {
    'Maang Tikka':  '34096814326631390',
    'Matha Patti':  '25972597769065393',
    'Passa':        '25853734394311094',
    'Head Kanser':  '26924099463860066',
    'Sheesh Phool': '25884225787909036',
}

FACE_HAIR = {
    'Hair Clips': '25923141554014968',
}

HAND_BANGLES = {
    'Traditional Bangles': '25990285673976585',
    'Designer Kada':       '26202123256143866',
}

HAND_BRACELETS = {
    'Classic Bracelets': '26479540271641962',
    'Chain Bracelets':   '26553938717531086',
    'Charm Bracelets':   '25889526627383303',
    'Cuff Bracelets':    '26095567730084970',
}

HAND_ARMLETS = {
    'Baju Band': '25741475325553252',
}

HAND_RINGS = {
    'Designer Rings':   '26458893303705648',
    'Engagement Rings': '26577195808532633',
    'Wedding Bands':    '26283285724614486',
    'Fashion Rings':    '26627787650158306',
}

NECK_NECKLACES = {
    'Traditional Haar':   '34124391790542901',
    'Modern Chokers':     '34380933844854505',
    'Princess Necklaces': '27036678569255877',
    'Matinee Necklaces':  '34810362708554746',
    'Necklace':           '27022573597332099',
}

NECK_PENDANTS = {
    'Pendants':           '25892524293743018',
    'Solitaire Pendants': '26345939121667071',
    'Locket Pendants':    '34949414394649401',
    'Statement Pendants': '34061823006795079',
}

NECK_BRIDAL = {
    'Bridal Sets': '34181230154825697',
}

LOWER = {
    'Kamarband':     '25970100975978085',
    'Payal Anklets': '26108970985433226',
    'Toe Rings':     '26041413228854859',
}

MEN_RINGS = {
    'Wedding Bands':    '35279590828306838',
    'Engagement Rings': '26205064579128433',
    'Signet Rings':     '26133044123050259',
    'Fashion Rings':    '26353107324312966',
    'Classic Bands':    '26048808064813747',
    'Gemstone Rings':   '25392189793787605',
}

MEN_BRACELETS = {
    'Chain Bracelets':   '26028399416826135',
    'Leather Bracelets': '24614722568226121',
    'Beaded Bracelets':  '26526947026910291',
    'Cuff Bracelets':    '26224048963949143',
}

MEN_CHAINS = {
    'Gold Chains':   '26614026711549117',
    'Silver Chains': '35305915439007559',
    'Rope Chains':   '25364645956543386',
}

MEN_ACCESSORIES = {
    'Classic Cufflinks':  '25956694700651645',
    'Designer Cufflinks': '25283486371327046',
    'Tie Pins':           '34056958820614334',
    'Brooches':           '27093254823609535',
    'Kada Modern':        '26028780853472858',
    'Kada Traditional':   '26080348848282889',
    'Pendant Initial':    '26251311201160440',
    'Pendant Religious':  '34138553902457530',
    'Pendant Stone':      '26441867825407906',
}

WATCHES = {
    'Men Timepieces':    '34176915238618497',
    'Women Timepieces':  '26903528372573194',
    'Kids Timepieces':   '26311558718468909',
    'Smart Watches':     '25912162851771673',
    'Luxury Timepieces': '26667915832816156',
}

STUDIO_ACCESSORIES = {
    'Premium Keychains': '26255788447385252',
    'Evening Clutches':  '34514139158199452',
    'Sunglasses':        '25258040713868720',
    'Designer Belts':    '26176082815414211',
}

# Flat id→name lookup (all 82 collections)
ID_TO_NAME: dict = {}

def _register(coll_dict: dict):
    for name, cid in coll_dict.items():
        ID_TO_NAME[cid] = name

for _c in [
    BABY, FACE_EARRINGS, FACE_NOSE, FACE_HEAD, FACE_HAIR,
    HAND_BANGLES, HAND_BRACELETS, HAND_ARMLETS, HAND_RINGS,
    NECK_NECKLACES, NECK_PENDANTS, NECK_BRIDAL, LOWER,
    MEN_RINGS, MEN_BRACELETS, MEN_CHAINS, MEN_ACCESSORIES,
    WATCHES, STUDIO_ACCESSORIES,
]:
    _register(_c)

ALL_NAMES = list(ID_TO_NAME.values())  # for fuzzy search

# ─────────────────────────────────────────────────────────────
# SCROLL-LIST ROW BUILDERS
# (WhatsApp list: max 10 rows per section, max 10 sections)
# ─────────────────────────────────────────────────────────────

def _rows(coll_dict: dict) -> list:
    """Convert a collection dict to WhatsApp list rows."""
    return [{'id': f"C_{cid}", 'title': name[:24]}
            for name, cid in coll_dict.items()]

def _section(title: str, coll_dict: dict) -> dict:
    return {'title': title[:24], 'rows': _rows(coll_dict)}

# ─────────────────────────────────────────────────────────────
# EMAIL
# ─────────────────────────────────────────────────────────────

def admin_email(subject: str, body: str):
    try:
        if not GMAIL_USER or not GMAIL_PASS:
            log.warning("Gmail not configured — skipping email.")
            return
        for recipient in filter(None, [ADMIN_1, ADMIN_2]):
            msg = MIMEMultipart()
            msg['From']    = GMAIL_USER
            msg['To']      = recipient
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as srv:
                srv.login(GMAIL_USER, GMAIL_PASS)
                srv.sendmail(GMAIL_USER, recipient, msg.as_string())
        log.info(f"Admin email sent: {subject}")
    except Exception as e:
        log.error(f"Email error: {e}")

# ─────────────────────────────────────────────────────────────
# GOOGLE SHEETS
# ─────────────────────────────────────────────────────────────

def _sheets():
    try:
        if not SHEET_KEY:
            return None
        creds = Credentials.from_service_account_info(
            json.loads(SHEET_KEY),
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        return gspread.authorize(creds)
    except Exception as e:
        log.error(f"Sheets init: {e}")
        return None

_gc = _sheets()

def sheets_lookup(phone: str) -> dict:
    try:
        if not _gc or not SHEET_ID:
            return {'exists': False}
        ws     = _gc.open_by_key(SHEET_ID).worksheet('Registrations')
        phones = ws.col_values(1)
        for i, p in enumerate(phones, 1):
            if p == phone:
                row = ws.row_values(i)
                return {
                    'exists':     True,
                    'first_name': row[1] if len(row) > 1 else '',
                    'last_name':  row[2] if len(row) > 2 else '',
                }
        return {'exists': False}
    except Exception as e:
        log.error(f"Sheets lookup: {e}")
        return {'exists': False}

def sheets_log(phone: str):
    try:
        if not _gc or not SHEET_ID:
            return
        ws = _gc.open_by_key(SHEET_ID).worksheet('Registrations')
        ws.append_row([phone, '', '', datetime.now().isoformat()])
    except Exception as e:
        log.error(f"Sheets log: {e}")

# ─────────────────────────────────────────────────────────────
# SHOPIFY
# ─────────────────────────────────────────────────────────────

def shopify_lookup(phone: str) -> dict:
    try:
        if not SHOPIFY_TOKEN:
            return {'exists': False}
        r = requests.get(
            f"https://{SHOPIFY_STORE}/admin/api/2024-01/customers/search.json",
            headers={'X-Shopify-Access-Token': SHOPIFY_TOKEN},
            params={'query': f'phone:{phone}'},
            timeout=10
        )
        if r.ok:
            customers = r.json().get('customers', [])
            if customers:
                c    = customers[0]
                tags = {t.strip() for t in c.get('tags', '').split(',')}
                return {
                    'exists':     True,
                    'first_name': c.get('first_name', ''),
                    'last_name':  c.get('last_name', ''),
                    'email':      c.get('email', ''),
                    'b2b':        bool(tags & {'B2B', 'Wholesale', 'b2b', 'wholesale'}),
                }
        return {'exists': False}
    except Exception as e:
        log.error(f"Shopify lookup: {e}")
        return {'exists': False}

def customer_status(phone: str) -> dict:
    """Returns status: new | incomplete | retail | b2b"""
    s = shopify_lookup(phone)
    if s['exists']:
        fn  = s.get('first_name', '') or 'Valued Customer'
        ln  = s.get('last_name', '') or ''
        return {
            'status': 'b2b' if s['b2b'] else 'retail',
            'name':   f"{fn} {ln}".strip(),
            'email':  s.get('email', ''),
        }
    sh = sheets_lookup(phone)
    if sh['exists']:
        fn  = sh.get('first_name', '') or ''
        ln  = sh.get('last_name', '') or ''
        return {
            'status': 'incomplete',
            'name':   f"{fn} {ln}".strip() or 'Valued Customer',
            'email':  '',
        }
    sheets_log(phone)
    return {'status': 'new', 'name': 'Valued Customer', 'email': ''}

# ─────────────────────────────────────────────────────────────
# FUZZY SEARCH
# ─────────────────────────────────────────────────────────────

def fuzzy_search(query: str) -> dict:
    """Return best matching collection for a text query."""
    try:
        if not query:
            return {'found': False}
        match = process.extractOne(query, ALL_NAMES, scorer=fuzz.token_sort_ratio)
        if match and match[1] >= 55:
            cname = match[0]
            for cid, name in ID_TO_NAME.items():
                if name == cname:
                    return {'found': True, 'id': cid, 'name': cname}
        return {'found': False}
    except Exception as e:
        log.error(f"Fuzzy search: {e}")
        return {'found': False}

# ─────────────────────────────────────────────────────────────
# RAZORPAY
# ─────────────────────────────────────────────────────────────

def razorpay_link(amount_paise: int, cust_name: str, phone: str, ref: str) -> str | None:
    try:
        if not RZP_KEY_ID or not RZP_KEY_SEC:
            return None
        client = razorpay.Client(auth=(RZP_KEY_ID, RZP_KEY_SEC))
        link   = client.payment_link.create({
            'amount':          amount_paise,
            'currency':        'INR',
            'accept_partial':  False,
            'description':     f'A Jewel Studio - Order {ref}',
            'customer':        {'name': cust_name, 'contact': f'+{phone}'},
            'notify':          {'sms': False, 'email': False},
            'reminder_enable': False,
            'notes':           {'order_ref': ref},
        })
        return link.get('short_url')
    except Exception as e:
        log.error(f"Razorpay: {e}")
        return None

# ─────────────────────────────────────────────────────────────
# REFERRAL
# ─────────────────────────────────────────────────────────────

def referral_code(name: str, phone: str) -> str:
    prefix = name[:3].upper() if len(name) >= 3 else 'AJS'
    return f"AJS-{prefix}-{phone[-4:]}"

# ─────────────────────────────────────────────────────────────
# LANGUAGE DETECTION
# ─────────────────────────────────────────────────────────────

_HINGLISH = {
    'hai', 'hain', 'kya', 'aap', 'mujhe', 'chahiye', 'dikhao', 'batao',
    'kaise', 'kaha', 'nahi', 'accha', 'theek', 'zaroor', 'bhi', 'aur',
    'woh', 'yeh', 'iska', 'uska', 'hamara', 'abhi', 'jaldi',
}

def detect_lang(text: str) -> str:
    if not text:
        return 'en'
    if len(re.findall(r'[\u0900-\u097F]', text)) > len(text) * 0.25:
        return 'hi'
    words = set(text.lower().split())
    if words & _HINGLISH:
        return 'hi'
    return 'en'

# ─────────────────────────────────────────────────────────────
# ARU — AI ASSISTANT
# ─────────────────────────────────────────────────────────────

_ARU_SYSTEM = """You are Aru, a professional jewelry consultant and full-time employee at A Jewel Studio.

Personality:
- Luxury, warm, confident, professional — like a trusted personal stylist
- Never confused, never uncertain, always composed
- Represent the A Jewel Studio brand with elegance at all times

Responsibilities:
- Answer product questions, availability, and recommendations
- Handle custom order inquiries with enthusiasm
- Generate referral codes when asked (format: AJS-XXX-XXXX)
- Share new arrivals, trends, and brand story
- Respond to any question that is not a menu button click
- Guide customers with budget-based jewelry recommendations

Rules:
- Never include raw URLs or hyperlinks in your text
- Maximum 3 sentences per response — keep it sharp
- No emojis, no icons, no casual language
- If asked for a price you are unsure of, say our team will confirm
- Always address the customer by name if provided
"""

def ask_aru(question: str, lang: str, name: str, context: str = '') -> str | None:
    try:
        if not _gm_text:
            return None
        lang_note = (
            "Respond in English only." if lang == 'en'
            else "Respond in Hindi/Hinglish using Roman script (no Devanagari)."
        )
        prompt = f"""{_ARU_SYSTEM}
Customer name: {name}
Language: {lang_note}
Context: {context}

Customer says: {question}

Reply as Aru — maximum 3 sentences, no emojis."""
        return _gm_text.generate_content(prompt).text.strip()
    except Exception as e:
        log.error(f"Aru error: {e}")
        return None

def aru_vision(image_url: str) -> dict | None:
    """Analyze jewelry image and return search keywords."""
    try:
        if not _gm_vision:
            return None
        img = requests.get(image_url, timeout=10)
        if not img.ok:
            return None
        resp = _gm_vision.generate_content([
            "Analyze this jewelry image. Identify: jewelry type, style (traditional/modern/bridal), material. Be concise, 1-2 sentences.",
            {'mime_type': 'image/jpeg', 'data': img.content}
        ])
        analysis = resp.text.strip()
        al       = analysis.lower()
        kw = []
        for t in ['earring', 'jhumka', 'necklace', 'ring', 'bracelet', 'bangle',
                  'kada', 'chain', 'pendant', 'anklet', 'payal', 'choker', 'maang']:
            if t in al:
                kw.append(t)
        for s in ['traditional', 'modern', 'bridal', 'ethnic', 'classic']:
            if s in al:
                kw.append(s)
        return {'analysis': analysis, 'query': ' '.join(kw[:3]) or 'jewellery'}
    except Exception as e:
        log.error(f"Vision: {e}")
        return None

# ─────────────────────────────────────────────────────────────
# WHATSAPP — CORE SENDERS
# ─────────────────────────────────────────────────────────────

def _post(payload: dict) -> bool:
    try:
        r = requests.post(
            WA_API,
            headers={'Authorization': f'Bearer {WA_TOKEN}',
                     'Content-Type':  'application/json'},
            json=payload, timeout=10
        )
        if not r.ok:
            log.error(f"WA {r.status_code}: {r.text[:300]}")
        return r.ok
    except Exception as e:
        log.error(f"WA post: {e}")
        return False

def tx(to: str, text: str) -> bool:
    """Send plain text message."""
    return _post({'messaging_product': 'whatsapp', 'to': to,
                  'type': 'text', 'text': {'body': text}})

def btn1(to: str, body: str, bid: str, label: str) -> bool:
    """Single reply button."""
    return _post({
        'messaging_product': 'whatsapp', 'to': to, 'type': 'interactive',
        'interactive': {
            'type': 'button', 'body': {'text': body},
            'action': {'buttons': [{'type': 'reply', 'reply': {'id': bid, 'title': label[:20]}}]}
        }
    })

def btns(to: str, body: str, buttons: list) -> bool:
    """Up to 3 reply buttons. Each button: {'id': str, 'title': str}"""
    return _post({
        'messaging_product': 'whatsapp', 'to': to, 'type': 'interactive',
        'interactive': {
            'type': 'button', 'body': {'text': body},
            'action': {'buttons': [
                {'type': 'reply', 'reply': {'id': b['id'], 'title': b['title'][:20]}}
                for b in buttons[:3]
            ]}
        }
    })

def scroll(to: str, header: str, body: str, btn_text: str, sections: list) -> bool:
    """Scroll list — max 10 sections, max 10 rows per section."""
    return _post({
        'messaging_product': 'whatsapp', 'to': to, 'type': 'interactive',
        'interactive': {
            'type': 'list',
            'header': {'type': 'text', 'text': header[:60]},
            'body':   {'text': body},
            'action': {'button': btn_text[:20], 'sections': sections[:10]}
        }
    })

def cta(to: str, body: str, label: str, url: str) -> bool:
    """CTA URL button — customer taps to open URL. No raw link in text."""
    return _post({
        'messaging_product': 'whatsapp', 'to': to, 'type': 'interactive',
        'interactive': {
            'type': 'cta_url', 'body': {'text': body},
            'action': {'name': 'cta_url',
                       'parameters': {'display_text': label[:20], 'url': url}}
        }
    })

def open_catalog(to: str, collection_id: str, collection_name: str) -> bool:
    """
    Open WhatsApp catalog INSIDE WhatsApp showing ONLY the selected collection.
    Step 1: Fetch retailer_ids from Meta Commerce API.
    Step 2: Send product_list interactive message.
    """
    try:
        r = requests.get(
            f"https://graph.facebook.com/v19.0/{collection_id}/products",
            params={'fields': 'retailer_id', 'access_token': WA_TOKEN, 'limit': 30},
            timeout=10
        )
        if r.ok:
            rids = [p['retailer_id'] for p in r.json().get('data', []) if 'retailer_id' in p]
            if rids:
                return _post({
                    'messaging_product': 'whatsapp', 'to': to, 'type': 'interactive',
                    'interactive': {
                        'type':   'product_list',
                        'header': {'type': 'text', 'text': 'A Jewel Studio'},
                        'body':   {'text': collection_name},
                        'footer': {'text': 'Add to cart, then tap Place Order.'},
                        'action': {
                            'catalog_id': CATALOG_ID,
                            'sections': [{
                                'title': collection_name[:24],
                                'product_items': [{'product_retailer_id': rid} for rid in rids[:30]]
                            }]
                        }
                    }
                })
        log.warning(f"No products for collection {collection_id}")
        return False
    except Exception as e:
        log.error(f"open_catalog: {e}")
        return False

def _p(delay: float = 0.4):
    """Typing pause between messages."""
    time.sleep(delay)

# ─────────────────────────────────────────────────────────────
# FLOW FUNCTIONS
# ─────────────────────────────────────────────────────────────

def flow_new_customer(to: str, lang: str):
    if lang == 'hi':
        tx(to, "Hello\nA Jewel Studio mein aapka swagat hai.")
        _p()
        cta(to,
            "Main Aru hoon, aapki Studio Assistant.\n"
            "Hamari exclusive jewellery collections aur latest designs explore karne ke liye register karein.",
            "JOIN US",
            f"https://{SHOPIFY_STORE}/pages/join-us?wa={to}"
        )
    else:
        tx(to, "Hello\nWelcome to A Jewel Studio.")
        _p()
        cta(to,
            "I am Aru, your Studio Assistant.\n"
            "Register to explore our exclusive jewellery collections and latest designs.",
            "JOIN US",
            f"https://{SHOPIFY_STORE}/pages/join-us?wa={to}"
        )


def flow_incomplete(to: str, lang: str):
    if lang == 'hi':
        cta(to,
            "Hello\n\nAapki registration abhi tak complete nahi hui hai.\n"
            "Hamari collections explore karne ke liye registration complete karein.",
            "COMPLETE REGISTRATION",
            f"https://{SHOPIFY_STORE}/pages/join-us?wa={to}"
        )
    else:
        cta(to,
            "Hello\n\nYour registration is not yet complete.\n"
            "Please complete it to continue exploring our collections.",
            "COMPLETE REGISTRATION",
            f"https://{SHOPIFY_STORE}/pages/join-us?wa={to}"
        )


def flow_retail_welcome(to: str, name: str, lang: str):
    if lang == 'hi':
        tx(to, f"Hello {name}\n\nA Jewel Studio mein dobara swagat hai.\nAapko yahan pakar humein khushi hui.")
    else:
        tx(to, f"Hello {name}\n\nWelcome back to A Jewel Studio.\nWe are delighted to have you here.")
    _p()
    flow_main_menu(to, lang)


def flow_b2b_welcome(to: str, name: str, lang: str):
    if lang == 'hi':
        tx(to, f"Hello {name}\n\nA Jewel Studio mein dobara swagat hai.")
    else:
        tx(to, f"Hello {name}\n\nWelcome back to A Jewel Studio.")
    _p()
    btns(to,
        "How may I assist you today?" if lang == 'en' else "Aaj main aapki kya madad kar sakti hoon?",
        [
            {'id': 'BROWSE',        'title': 'BROWSE COLLECTIONS'},
            {'id': 'CUSTOM_ORDER',  'title': 'CUSTOM ORDER'},
            {'id': 'MY_ORDERS',     'title': 'MY ORDERS'},
        ]
    )


def flow_main_menu(to: str, lang: str):
    scroll(
        to,
        header='A Jewel Studio',
        body=(
            'Please choose a collection to explore.'
            if lang == 'en' else
            'Apni pasand ki collection select karein.'
        ),
        btn_text='MENU',
        sections=[{
            'title': 'Collections',
            'rows': [
                {'id': 'CAT_BABY',   'title': 'Baby Jewellery'},
                {'id': 'CAT_WOMEN',  'title': 'Women Jewellery'},
                {'id': 'CAT_MEN',    'title': 'Men Jewellery'},
                {'id': 'CAT_STUDIO', 'title': 'Studio Special'},
                {'id': 'CAT_SACRED', 'title': 'Sacred Arts'},
            ]
        }]
    )


def flow_baby_menu(to: str, lang: str):
    scroll(
        to,
        header='Baby Jewellery',
        body=(
            'Select a collection to explore.'
            if lang == 'en' else
            'Ek collection select karein.'
        ),
        btn_text='SELECT',
        sections=[_section('Baby Jewellery', BABY)]
    )


def flow_women_body_menu(to: str, lang: str):
    """
    Women Jewellery has 4 body areas.
    WhatsApp max = 3 buttons, so we send 3 + 1 separate button.
    """
    btns(to,
        (
            'You are exploring Women Jewellery.\nPlease choose a category.'
            if lang == 'en' else
            'Aap Women Jewellery dekh rahi hain.\nEk category select karein.'
        ),
        [
            {'id': 'W_FACE', 'title': 'FACE JEWELLERY'},
            {'id': 'W_HAND', 'title': 'HAND JEWELLERY'},
            {'id': 'W_NECK', 'title': 'NECK JEWELLERY'},
        ]
    )
    _p()
    btn1(to, 'Or explore Lower Body Jewellery.', 'W_LOWER', 'LOWER BODY')


def flow_face_menu(to: str, lang: str):
    """
    Face Jewellery — single scroll list with 4 sections.
    Customer picks directly from the list and catalog opens.
    """
    scroll(
        to,
        header='Face Jewellery',
        body=(
            'Please choose a style to explore.'
            if lang == 'en' else
            'Apni pasand ka style select karein.'
        ),
        btn_text='SELECT',
        sections=[
            _section('Earrings',         FACE_EARRINGS),
            _section('Nose Jewellery',   FACE_NOSE),
            _section('Head Jewellery',   FACE_HEAD),
            _section('Hair Accessories', FACE_HAIR),
        ]
    )


def flow_hand_menu(to: str, lang: str):
    scroll(
        to,
        header='Hand Jewellery',
        body=(
            'Please choose a style to explore.'
            if lang == 'en' else
            'Apni pasand ka style select karein.'
        ),
        btn_text='SELECT',
        sections=[
            _section('Bangles and Kada', HAND_BANGLES),
            _section('Bracelets',        HAND_BRACELETS),
            _section('Armlets',          HAND_ARMLETS),
            _section('Rings',            HAND_RINGS),
        ]
    )


def flow_neck_menu(to: str, lang: str):
    scroll(
        to,
        header='Neck Jewellery',
        body=(
            'Please choose a style to explore.'
            if lang == 'en' else
            'Apni pasand ka style select karein.'
        ),
        btn_text='SELECT',
        sections=[
            _section('Necklaces',    NECK_NECKLACES),
            _section('Pendants',     NECK_PENDANTS),
            _section('Bridal Sets',  NECK_BRIDAL),
        ]
    )


def flow_lower_menu(to: str, lang: str):
    scroll(
        to,
        header='Lower Body Jewellery',
        body=(
            'Please choose a collection.'
            if lang == 'en' else
            'Ek collection select karein.'
        ),
        btn_text='SELECT',
        sections=[_section('Lower Body', LOWER)]
    )


def flow_men_menu(to: str, lang: str):
    """
    Men Jewellery — one scroll list with 4 sections.
    Rings (6) + Bracelets (4) + Chains (3) + Accessories (9) = 22 items across 4 sections.
    """
    scroll(
        to,
        header='Men Jewellery',
        body=(
            'Please choose a collection to explore.'
            if lang == 'en' else
            'Apni pasand ki collection select karein.'
        ),
        btn_text='SELECT',
        sections=[
            _section('Rings',        MEN_RINGS),
            _section('Bracelets',    MEN_BRACELETS),
            _section('Chains',       MEN_CHAINS),
            _section('Accessories',  MEN_ACCESSORIES),
        ]
    )


def flow_studio_menu(to: str, lang: str):
    btns(to,
        (
            'Please choose a category.'
            if lang == 'en' else
            'Ek category select karein.'
        ),
        [
            {'id': 'S_WATCHES', 'title': 'WATCHES'},
            {'id': 'S_ACCSS',   'title': 'ACCESSORIES'},
        ]
    )


def flow_watches_menu(to: str, lang: str):
    scroll(
        to, 'Watches', 'Select a collection.', 'SELECT',
        [_section('Watches', WATCHES)]
    )


def flow_studio_acc_menu(to: str, lang: str):
    scroll(
        to, 'Studio Accessories', 'Select a collection.', 'SELECT',
        [_section('Studio Accessories', STUDIO_ACCESSORIES)]
    )


def flow_open_collection(to: str, cid: str, cname: str, lang: str):
    tx(to,
        f"You are now viewing our {cname} Collection.\n"
        "Browse the designs and add your favourites to the cart."
        if lang == 'en' else
        f"Aap ab {cname} Collection dekh rahe hain.\n"
        "Apna pasandida design select karein aur cart mein add karein."
    )
    _p()
    if not open_catalog(to, cid, cname):
        flow_empty_catalog(to, lang)


def flow_empty_catalog(to: str, lang: str):
    tx(to,
        "This collection is currently being updated.\n\n"
        "We accept custom orders and can create a design of your choice with the finest craftsmanship."
        if lang == 'en' else
        "Yeh collection abhi update ho rahi hai.\n\n"
        "Hum custom orders accept karte hain aur aapki pasand ka design finest craftsmanship se bana sakte hain."
    )
    _p()
    btns(to,
        "How would you like to proceed?" if lang == 'en' else "Aap kaise aage badhna chahenge?",
        [
            {'id': 'CUSTOM_ORDER',  'title': 'CUSTOM ORDER'},
            {'id': 'BROWSE',        'title': 'BROWSE COLLECTIONS'},
            {'id': 'CONTACT_TEAM',  'title': 'CONTACT TEAM'},
        ]
    )


def flow_custom_order(to: str, name: str, phone: str, is_b2b: bool, lang: str):
    s = get_session(phone)
    s['custom_step'] = 'awaiting_description'
    if lang == 'hi':
        tx(to,
            f"Hume aapke liye custom piece banana bahut khushi hogi, {name}.\n\n"
            "Apni requirements batayein — jewellery ka type, material, occasion aur koi specific design idea."
        )
    else:
        tx(to,
            f"We would be delighted to create a custom piece for you, {name}.\n\n"
            "Please describe your requirements — jewellery type, material preference, occasion, and any design ideas."
        )
    if is_b2b:
        _p()
        btn1(to, 'You may also upload a reference design file.', 'UPLOAD_FILE', 'UPLOAD DESIGN FILE')


def flow_custom_order_received(to: str, name: str, phone: str, description: str, is_b2b: bool, lang: str):
    tx(to,
        "Thank you for sharing your requirements.\n\n"
        "Our design team will review your request and get back to you within 24 hours."
        if lang == 'en' else
        "Aapki requirements share karne ke liye shukriya.\n\n"
        "Hamari design team 24 ghante mein aapse contact karegi."
    )
    admin_email(
        subject=f"Custom Order Request — {name} — {phone}",
        body=(
            f"Custom order request received.\n\n"
            f"Customer : {name}\n"
            f"Phone    : {phone}\n"
            f"Type     : {'B2B' if is_b2b else 'Retail'}\n\n"
            f"Requirements:\n{description}"
        )
    )


def flow_order_placed(to: str, phone: str, name: str, items: list, lang: str):
    total     = sum(
        int(float(i.get('item_price', 0)) * 100) * i.get('quantity', 1)
        for i in items
    )
    ref       = f"AJS-{phone[-4:]}-{int(datetime.now().timestamp())}"
    rp_url    = razorpay_link(total, name, phone, ref)

    if rp_url:
        body = (
            f"A Jewel Studio choose karne ke liye dhanyavaad.\n\n"
            f"Order Reference: {ref}\n\n"
            "Payment complete karne ke liye neeche tap karein."
            if lang == 'hi' else
            f"Thank you for choosing A Jewel Studio.\n\n"
            f"Order Reference: {ref}\n\n"
            "Please complete your payment using the button below."
        )
        cta(to, body, 'PAY NOW', rp_url)
    else:
        tx(to, "To complete your order please contact our team. A payment link will be shared shortly.")

    # Admin notification
    item_lines = '\n'.join(
        f"  - {i.get('product_name', 'Item')} x{i.get('quantity', 1)} @ Rs.{i.get('item_price', 0)}"
        for i in items
    )
    admin_email(
        subject=f"New Order — {ref} — {name}",
        body=(
            f"New order received.\n\n"
            f"Reference : {ref}\n"
            f"Customer  : {name}\n"
            f"Phone     : {phone}\n\n"
            f"Items:\n{item_lines}\n\n"
            f"Total: Rs.{total / 100:.2f}"
        )
    )


def flow_payment_success(to: str, lang: str):
    tx(to,
        "Payment received successfully.\n\n"
        "Thank you for choosing A Jewel Studio. Your order is confirmed and is now being processed.\n\n"
        "Our team will contact you shortly with further updates."
        if lang == 'en' else
        "Payment successfully receive ho gaya hai.\n\n"
        "A Jewel Studio choose karne ke liye dhanyavaad. Aapka order confirm ho gaya hai.\n\n"
        "Hamari team jald hi aapse contact karegi."
    )


def flow_referral(to: str, name: str, phone: str, lang: str):
    code = referral_code(name, phone)
    url  = f"https://{SHOPIFY_STORE}/pages/join-us?ref={code}"
    body = (
        f"Your Referral Code\n\n"
        f"Code: {code}\n\n"
        "Share this with your friends and family. When they register using your code, "
        "they become part of the A Jewel Studio family."
        if lang == 'en' else
        f"Aapka Referral Code\n\n"
        f"Code: {code}\n\n"
        "Yeh code apne doston aur family ke saath share karein. Jab woh aapke code se "
        "register karenge, woh A Jewel Studio family ka hissa ban jayenge."
    )
    cta(to, body, 'SHARE REFERRAL', url)


def flow_order_tracking(to: str, name: str, lang: str):
    tx(to,
        f"To track your order, {name}, please share your Order Reference Number (format: AJS-XXXX-XXXXXXXXXX).\n\n"
        "Our team will provide the latest status shortly."
        if lang == 'en' else
        f"Apna order track karne ke liye, {name}, apna Order Reference Number share karein (format: AJS-XXXX-XXXXXXXXXX).\n\n"
        "Hamari team jald hi latest status batayegi."
    )


def flow_aru_fallback(to: str, name: str, lang: str):
    btns(to,
        (
            f"Thank you for reaching out, {name}.\n"
            "Our team is here to assist you with any query."
            if lang == 'en' else
            f"Humse contact karne ke liye shukriya, {name}.\n"
            "Hamari team aapki har query mein madad ke liye available hai."
        ),
        [
            {'id': 'BROWSE',       'title': 'BROWSE COLLECTIONS'},
            {'id': 'CUSTOM_ORDER', 'title': 'CUSTOM ORDER'},
            {'id': 'CONTACT_TEAM', 'title': 'CONTACT TEAM'},
        ]
    )

# ─────────────────────────────────────────────────────────────
# KEYWORD GROUPS
# ─────────────────────────────────────────────────────────────

_KW = {
    'greet':    {'hi', 'hello', 'hey', 'hlo', 'hii', 'helo', 'start', 'namaste', 'salam'},
    'tracking': {'order', 'track', 'status', 'delivery', 'shipping', 'kahan hai', 'mera order'},
    'referral': {'referral', 'refer', 'code', 'invite'},
    'custom':   {'custom', 'customize', 'bespoke', 'special order', 'custom order', 'design banao'},
    'hours':    {'timing', 'time', 'open', 'close', 'hours', 'ghante'},
    'about':    {'about', 'kaun ho', 'brand', 'studio', 'company'},
    'help':     {'help', 'support', 'assist', 'problem'},
    'payment':  {'payment', 'pay', 'razorpay', 'link'},
}

def detect_keyword(text: str) -> str | None:
    tl = set(text.lower().split())
    for ktype, words in _KW.items():
        if tl & words:
            return ktype
    return None

# ─────────────────────────────────────────────────────────────
# MAIN MESSAGE HANDLER
# ─────────────────────────────────────────────────────────────

def handle(phone: str, msg: dict):
    _cleanup()

    mtype  = msg.get('type')
    cdata  = customer_status(phone)
    s      = get_session(phone)
    s['name'] = cdata['name']

    lang   = s.get('lang', 'en')
    name   = s['name']
    status = cdata['status']

    # Detect language from incoming text
    if mtype == 'text':
        text = msg.get('text', {}).get('body', '').strip()
        lang = detect_lang(text)
        s['lang'] = lang

    # ── TEXT ──────────────────────────────────────────────────
    if mtype == 'text':
        text = msg.get('text', {}).get('body', '').strip()

        # Unregistered
        if status == 'new':
            flow_new_customer(phone, lang)
            return
        if status == 'incomplete':
            flow_incomplete(phone, lang)
            return

        # Awaiting custom order description
        if s.get('custom_step') == 'awaiting_description':
            s['custom_step'] = None
            is_b2b = (status == 'b2b')
            flow_custom_order_received(phone, name, phone, text, is_b2b, lang)
            return

        # Order reference lookup
        if re.match(r'AJS-[A-Z0-9]+-\d+', text.upper()):
            flow_order_tracking(phone, name, lang)
            return

        # Keyword routing
        kw = detect_keyword(text)

        if kw == 'greet':
            if status == 'b2b':
                flow_b2b_welcome(phone, name, lang)
            else:
                flow_retail_welcome(phone, name, lang)
            return

        if kw == 'tracking':
            flow_order_tracking(phone, name, lang)
            return

        if kw == 'referral':
            flow_referral(phone, name, phone, lang)
            return

        if kw == 'custom':
            flow_custom_order(phone, name, phone, status == 'b2b', lang)
            return

        if kw == 'hours':
            tx(phone,
                "A Jewel Studio\n\n"
                "Business Hours:\n"
                "Monday to Saturday — 10:00 AM to 7:00 PM\n"
                "Sunday — By Appointment Only"
                if lang == 'en' else
                "A Jewel Studio\n\n"
                "Kaam ke Ghante:\n"
                "Somvar se Shanivar — Subah 10 baje se Shaam 7 baje tak\n"
                "Itwar — Sirf Appointment par"
            )
            return

        if kw == 'about':
            tx(phone,
                "A Jewel Studio is a premium jewellery brand offering an exclusive range of "
                "handcrafted pieces for every occasion — from traditional bridal sets to modern everyday designs."
                if lang == 'en' else
                "A Jewel Studio ek premium jewellery brand hai jo har occasion ke liye exclusive "
                "handcrafted pieces offer karta hai — traditional bridal sets se lekar modern everyday designs tak."
            )
            return

        if kw == 'help':
            flow_aru_fallback(phone, name, lang)
            return

        # Fuzzy product search → catalog
        result = fuzzy_search(text)
        if result['found']:
            tx(phone,
                f"I found a matching collection for your search.\n"
                "Explore the products below."
                if lang == 'en' else
                "Aapki search ke liye ek matching collection mila.\n"
                "Neeche products dekhen."
            )
            _p()
            flow_open_collection(phone, result['id'], result['name'], lang)
            return

        # Aru handles everything else
        aru = ask_aru(
            text, lang, name,
            f"Customer status: {status}. They might be asking about products, availability, or general queries."
        )

        if aru:
            # Check if Aru's response hints at a collection
            result2 = fuzzy_search(aru)
            if result2['found']:
                tx(phone, aru)
                _p()
                flow_open_collection(phone, result2['id'], result2['name'], lang)
                return
            tx(phone, aru)
            _p()

        # Fallback to menu
        if status == 'b2b':
            flow_b2b_welcome(phone, name, lang)
        else:
            flow_main_menu(phone, lang)
        return

    # ── INTERACTIVE ───────────────────────────────────────────
    if mtype == 'interactive':
        itype = msg['interactive'].get('type')

        # ── BUTTON REPLY ──
        if itype == 'button_reply':
            bid = msg['interactive']['button_reply']['id']
            log.info(f"Button: {bid}")

            if bid in ('BROWSE', 'MENU'):
                flow_main_menu(phone, lang)

            elif bid == 'W_FACE':
                flow_face_menu(phone, lang)

            elif bid == 'W_HAND':
                flow_hand_menu(phone, lang)

            elif bid == 'W_NECK':
                flow_neck_menu(phone, lang)

            elif bid == 'W_LOWER':
                flow_lower_menu(phone, lang)

            elif bid == 'S_WATCHES':
                flow_watches_menu(phone, lang)

            elif bid == 'S_ACCSS':
                flow_studio_acc_menu(phone, lang)

            elif bid == 'CUSTOM_ORDER':
                flow_custom_order(phone, name, phone, status == 'b2b', lang)

            elif bid == 'MY_ORDERS':
                flow_order_tracking(phone, name, lang)

            elif bid == 'CONTACT_TEAM':
                tx(phone,
                    "Our team is available Monday to Saturday, 10 AM to 7 PM.\n\n"
                    "Your message has been noted. Someone will reach out to you shortly."
                    if lang == 'en' else
                    "Hamari team Somvar se Shanivar, Subah 10 baje se Shaam 7 baje tak available hai.\n\n"
                    "Aapka message note kar liya gaya hai. Koi jald hi contact karega."
                )

            elif bid == 'UPLOAD_FILE':
                tx(phone,
                    "Please upload your design file or reference image directly in this chat.\n"
                    "Our team will review and respond within 24 hours."
                    if lang == 'en' else
                    "Apna design file ya reference image seedha is chat mein upload karein.\n"
                    "Hamari team 24 ghante mein review karke respond karegi."
                )

        # ── LIST REPLY ──
        elif itype == 'list_reply':
            lid = msg['interactive']['list_reply']['id']
            log.info(f"List: {lid}")

            if lid == 'CAT_BABY':
                flow_baby_menu(phone, lang)

            elif lid == 'CAT_WOMEN':
                flow_women_body_menu(phone, lang)

            elif lid == 'CAT_MEN':
                flow_men_menu(phone, lang)

            elif lid == 'CAT_STUDIO':
                flow_studio_menu(phone, lang)

            elif lid == 'CAT_SACRED':
                flow_empty_catalog(phone, lang)

            elif lid.startswith('C_'):
                # Direct collection pick from any scroll list
                cid   = lid[2:]   # strip 'C_' prefix
                cname = ID_TO_NAME.get(cid, 'Collection')
                flow_open_collection(phone, cid, cname, lang)

        return

    # ── IMAGE ─────────────────────────────────────────────────
    if mtype == 'image':
        image_id = msg.get('image', {}).get('id')
        tx(phone,
            "Thank you for sharing the image.\nAnalyzing the design, please wait."
            if lang == 'en' else
            "Image share karne ke liye shukriya.\nDesign analyze ho raha hai, please wait."
        )
        _p(1)

        if image_id:
            url_r = requests.get(
                f"https://graph.facebook.com/v19.0/{image_id}",
                headers={'Authorization': f'Bearer {WA_TOKEN}'},
                timeout=10
            )
            if url_r.ok:
                vision = aru_vision(url_r.json().get('url', ''))
                if vision:
                    result = fuzzy_search(vision['query'])
                    if result['found']:
                        tx(phone,
                            "I found a similar collection for this design.\nExplore the products below."
                            if lang == 'en' else
                            "Is design ke liye ek similar collection mila.\nNeeche products dekhen."
                        )
                        _p()
                        flow_open_collection(phone, result['id'], result['name'], lang)
                        return

        tx(phone,
            "Thank you for the reference. Please describe what you are looking for "
            "and I will help you find the perfect piece."
            if lang == 'en' else
            "Reference ke liye shukriya. Batayein aap kya dhundh rahe hain "
            "aur main perfect piece dhundhne mein help karungi."
        )
        _p()
        btn1(phone, 'Would you like to place a custom order?', 'CUSTOM_ORDER', 'CUSTOM ORDER')
        return

    # ── ORDER (from catalog cart) ─────────────────────────────
    if mtype == 'order':
        items = msg.get('order', {}).get('product_items', [])
        flow_order_placed(phone, phone, name, items, lang)
        return

# ─────────────────────────────────────────────────────────────
# WEBHOOK
# ─────────────────────────────────────────────────────────────

@app.route('/webhook', methods=['GET'])
def verify():
    mode      = request.args.get('hub.mode')
    token     = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if mode == 'subscribe' and token == VERIFY_TOKEN:
        log.info("Webhook verified.")
        return challenge, 200
    return 'Forbidden', 403


@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json(silent=True)
        if not data or data.get('object') != 'whatsapp_business_account':
            return jsonify({'status': 'ok'}), 200
        msgs = (
            data.get('entry',   [{}])[0]
                .get('changes', [{}])[0]
                .get('value',   {})
                .get('messages', [])
        )
        for m in msgs:
            phone = m.get('from')
            if phone:
                handle(phone, m)
    except Exception as e:
        log.error(f"Webhook: {e}")
    return jsonify({'status': 'ok'}), 200


@app.route('/', methods=['GET'])
@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status':          'healthy',
        'service':         'A Jewel Studio WhatsApp Bot',
        'assistant':       'Aru',
        'collections':     82,
        'active_sessions': len(_sessions),
        'timestamp':       datetime.now().isoformat(),
    }), 200


@app.after_request
def security(r):
    r.headers.update({
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options':        'DENY',
        'X-XSS-Protection':       '1; mode=block',
    })
    return r


@app.errorhandler(404)
def not_found(_):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def server_error(e):
    log.error(e)
    return jsonify({'error': 'Server error'}), 500

# ─────────────────────────────────────────────────────────────
# ENTRY
# ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    log.info("A Jewel Studio Bot — Starting on port %s", port)
    app.run(host='0.0.0.0', port=port, debug=False)
