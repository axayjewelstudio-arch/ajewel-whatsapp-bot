# -*- coding: utf-8 -*-
"""
A JEWEL STUDIO — WhatsApp Bot  v3
Aru AI Assistant | 82 Collections | Bilingual | Full Production

FIXES IN THIS VERSION
---------------------
1. Message deduplication     — Meta sends duplicate webhooks; each msg_id processed once only
2. Row count fixed            — WhatsApp hard limit: max 10 TOTAL rows across all sections
   Face Jewellery  (20 rows) → buttons first, then per-style scroll lists
   Hand Jewellery  (11 rows) → buttons first, then per-category scroll lists
   Men Jewellery   (22 rows) → buttons first, then per-category scroll lists
   Neck Jewellery  (10 rows) → single list (within limit, OK)
3. Aru custom_step fix        — validates input is actually a design description
4. Customer name display      — first_name only in greetings (avoids Shopify last-name truncation)

WHATSAPP LIST CONSTRAINT: total rows across ALL sections in ONE list <= 10
"""

import os, json, logging, time, re, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests, gspread
from google.oauth2.service_account import Credentials
import razorpay
import google.generativeai as genai
from rapidfuzz import fuzz, process

# ─────────────────────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────────────────────

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO, format='%(asctime)s  %(levelname)-7s  %(message)s')
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
    _gm  = genai.GenerativeModel('gemini-pro')
    _gv  = genai.GenerativeModel('gemini-pro-vision')
else:
    _gm = _gv = None

# ─────────────────────────────────────────────────────────────
# DEDUPLICATION  ← NEW
# Keeps last 500 processed message IDs (auto-purges oldest)
# ─────────────────────────────────────────────────────────────

_processed: list = []   # ordered list of msg_ids
_DEDUP_MAX = 500

def _already_seen(msg_id: str) -> bool:
    if msg_id in _processed:
        return True
    _processed.append(msg_id)
    if len(_processed) > _DEDUP_MAX:
        _processed.pop(0)
    return False

# ─────────────────────────────────────────────────────────────
# SESSION
# ─────────────────────────────────────────────────────────────

_sessions: dict = {}
_TIMEOUT = timedelta(minutes=30)

def get_session(phone: str) -> dict:
    now = datetime.now()
    if phone not in _sessions:
        _sessions[phone] = {
            'created':     now,
            'last':        now,
            'first_name':  'Customer',
            'lang':        'en',
            'custom_step': None,
        }
    _sessions[phone]['last'] = now
    return _sessions[phone]

def _cleanup():
    now  = datetime.now()
    dead = [p for p, s in _sessions.items() if now - s['last'] > _TIMEOUT]
    for p in dead:
        del _sessions[p]

# ─────────────────────────────────────────────────────────────
# CATALOG — 82 COLLECTIONS
# WhatsApp limit: max 10 TOTAL rows in one list message.
# Groups that exceed 10 rows use buttons → per-group lists.
# ─────────────────────────────────────────────────────────────

# Baby (6) — fits in one list
BABY = {
    'Hair Accessories': '26930579176543121',
    'Earrings':         '34197166099927645',
    'Necklace Chains':  '34159752333640697',
    'Rings':            '27130321023234461',
    'Anklets':          '26132380466413425',
    'Bangles':          '25812008941803035',
}

# Face — shown via buttons, then per-group list
FACE_EARRINGS = {          # 10 rows — single list
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
FACE_NOSE = {              # 4 rows
    'Bridal Nath':   '26146672631634215',
    'Nose Pins':     '25816769131325224',
    'Septum Rings':  '26137405402565188',
    'Clip On Rings': '25956080384032593',
}
FACE_HEAD = {              # 5 rows
    'Maang Tikka':  '34096814326631390',
    'Matha Patti':  '25972597769065393',
    'Passa':        '25853734394311094',
    'Head Kanser':  '26924099463860066',
    'Sheesh Phool': '25884225787909036',
}
FACE_HAIR = {              # 1 row
    'Hair Clips': '25923141554014968',
}

# Hand — shown via buttons, then per-group list (total 11 — split needed)
HAND_BANGLES = {           # 2 rows
    'Traditional Bangles': '25990285673976585',
    'Designer Kada':       '26202123256143866',
}
HAND_BRACELETS = {         # 4 rows
    'Classic Bracelets': '26479540271641962',
    'Chain Bracelets':   '26553938717531086',
    'Charm Bracelets':   '25889526627383303',
    'Cuff Bracelets':    '26095567730084970',
}
HAND_ARMLETS = {           # 1 row
    'Baju Band': '25741475325553252',
}
HAND_RINGS = {             # 4 rows
    'Designer Rings':   '26458893303705648',
    'Engagement Rings': '26577195808532633',
    'Wedding Bands':    '26283285724614486',
    'Fashion Rings':    '26627787650158306',
}

# Neck — 10 rows total, fits in one list
NECK_NECKLACES = {         # 5 rows
    'Traditional Haar':   '34124391790542901',
    'Modern Chokers':     '34380933844854505',
    'Princess Necklaces': '27036678569255877',
    'Matinee Necklaces':  '34810362708554746',
    'Necklace':           '27022573597332099',
}
NECK_PENDANTS = {          # 4 rows
    'Pendants':           '25892524293743018',
    'Solitaire Pendants': '26345939121667071',
    'Locket Pendants':    '34949414394649401',
    'Statement Pendants': '34061823006795079',
}
NECK_BRIDAL = {            # 1 row
    'Bridal Sets': '34181230154825697',
}

LOWER = {                  # 3 rows
    'Kamarband':     '25970100975978085',
    'Payal Anklets': '26108970985433226',
    'Toe Rings':     '26041413228854859',
}

# Men — shown via buttons, then per-group list (total 22 — split needed)
MEN_RINGS = {              # 6 rows
    'Wedding Bands':    '35279590828306838',
    'Engagement Rings': '26205064579128433',
    'Signet Rings':     '26133044123050259',
    'Fashion Rings':    '26353107324312966',
    'Classic Bands':    '26048808064813747',
    'Gemstone Rings':   '25392189793787605',
}
MEN_BRACELETS = {          # 4 rows
    'Chain Bracelets':   '26028399416826135',
    'Leather Bracelets': '24614722568226121',
    'Beaded Bracelets':  '26526947026910291',
    'Cuff Bracelets':    '26224048963949143',
}
MEN_CHAINS = {             # 3 rows
    'Gold Chains':   '26614026711549117',
    'Silver Chains': '35305915439007559',
    'Rope Chains':   '25364645956543386',
}
MEN_ACCESSORIES = {        # 9 rows
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

WATCHES = {                # 5 rows
    'Men Timepieces':    '34176915238618497',
    'Women Timepieces':  '26903528372573194',
    'Kids Timepieces':   '26311558718468909',
    'Smart Watches':     '25912162851771673',
    'Luxury Timepieces': '26667915832816156',
}
STUDIO_ACCESSORIES = {     # 4 rows
    'Premium Keychains': '26255788447385252',
    'Evening Clutches':  '34514139158199452',
    'Sunglasses':        '25258040713868720',
    'Designer Belts':    '26176082815414211',
}

# Flat id → name lookup
ID_TO_NAME: dict = {}

def _reg(d: dict):
    for name, cid in d.items():
        ID_TO_NAME[cid] = name

for _d in [BABY, FACE_EARRINGS, FACE_NOSE, FACE_HEAD, FACE_HAIR,
           HAND_BANGLES, HAND_BRACELETS, HAND_ARMLETS, HAND_RINGS,
           NECK_NECKLACES, NECK_PENDANTS, NECK_BRIDAL, LOWER,
           MEN_RINGS, MEN_BRACELETS, MEN_CHAINS, MEN_ACCESSORIES,
           WATCHES, STUDIO_ACCESSORIES]:
    _reg(_d)

ALL_NAMES = list(ID_TO_NAME.values())

# ─────────────────────────────────────────────────────────────
# HELPERS — build scroll-list rows/sections
# ─────────────────────────────────────────────────────────────

def _rows(d: dict) -> list:
    return [{'id': f"C_{cid}", 'title': name[:24]} for name, cid in d.items()]

def _sec(title: str, d: dict) -> dict:
    return {'title': title[:24], 'rows': _rows(d)}

# ─────────────────────────────────────────────────────────────
# EMAIL
# ─────────────────────────────────────────────────────────────

def admin_email(subject: str, body: str):
    try:
        if not GMAIL_USER or not GMAIL_PASS:
            log.warning("Gmail not configured.")
            return
        for addr in filter(None, [ADMIN_1, ADMIN_2]):
            msg = MIMEMultipart()
            msg['From']    = GMAIL_USER
            msg['To']      = addr
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as srv:
                srv.login(GMAIL_USER, GMAIL_PASS)
                srv.sendmail(GMAIL_USER, addr, msg.as_string())
        log.info(f"Admin email: {subject}")
    except Exception as e:
        log.error(f"Email: {e}")

# ─────────────────────────────────────────────────────────────
# GOOGLE SHEETS
# ─────────────────────────────────────────────────────────────

def _make_gc():
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

_gc = _make_gc()

def sheets_lookup(phone: str) -> dict:
    try:
        if not _gc or not SHEET_ID:
            return {'exists': False}
        ws = _gc.open_by_key(SHEET_ID).worksheet('Registrations')
        phones = ws.col_values(1)
        for i, p in enumerate(phones, 1):
            if p == phone:
                row = ws.row_values(i)
                return {'exists': True,
                        'first_name': row[1] if len(row) > 1 else '',
                        'last_name':  row[2] if len(row) > 2 else ''}
        return {'exists': False}
    except Exception as e:
        log.error(f"Sheets lookup: {e}")
        return {'exists': False}

def sheets_log(phone: str):
    try:
        if not _gc or not SHEET_ID:
            return
        _gc.open_by_key(SHEET_ID).worksheet('Registrations').append_row(
            [phone, '', '', datetime.now().isoformat()]
        )
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
            custs = r.json().get('customers', [])
            if custs:
                c    = custs[0]
                tags = {t.strip() for t in c.get('tags', '').split(',')}
                return {
                    'exists':     True,
                    'first_name': c.get('first_name', '') or '',
                    'last_name':  c.get('last_name',  '') or '',
                    'email':      c.get('email',      '') or '',
                    'b2b':        bool(tags & {'B2B', 'Wholesale', 'b2b', 'wholesale'}),
                }
        return {'exists': False}
    except Exception as e:
        log.error(f"Shopify: {e}")
        return {'exists': False}

def customer_status(phone: str) -> dict:
    """Returns status: new | incomplete | retail | b2b"""
    s = shopify_lookup(phone)
    if s['exists']:
        fn = s['first_name'] or 'Customer'
        return {
            'status':     'b2b' if s['b2b'] else 'retail',
            'first_name': fn,
            'email':      s['email'],
        }
    sh = sheets_lookup(phone)
    if sh['exists']:
        return {
            'status':     'incomplete',
            'first_name': sh['first_name'] or 'Customer',
            'email':      '',
        }
    sheets_log(phone)
    return {'status': 'new', 'first_name': 'Customer', 'email': ''}

# ─────────────────────────────────────────────────────────────
# FUZZY SEARCH
# ─────────────────────────────────────────────────────────────

def fuzzy_search(query: str) -> dict:
    try:
        if not query:
            return {'found': False}
        match = process.extractOne(query, ALL_NAMES, scorer=fuzz.token_sort_ratio)
        if match and match[1] >= 55:
            for cid, name in ID_TO_NAME.items():
                if name == match[0]:
                    return {'found': True, 'id': cid, 'name': name}
        return {'found': False}
    except Exception as e:
        log.error(f"Fuzzy: {e}")
        return {'found': False}

# ─────────────────────────────────────────────────────────────
# RAZORPAY
# ─────────────────────────────────────────────────────────────

def rzp_link(amount_paise: int, name: str, phone: str, ref: str):
    try:
        if not RZP_KEY_ID or not RZP_KEY_SEC:
            return None
        client = razorpay.Client(auth=(RZP_KEY_ID, RZP_KEY_SEC))
        link   = client.payment_link.create({
            'amount':          amount_paise,
            'currency':        'INR',
            'accept_partial':  False,
            'description':     f'A Jewel Studio - Order {ref}',
            'customer':        {'name': name, 'contact': f'+{phone}'},
            'notify':          {'sms': False, 'email': False},
            'reminder_enable': False,
            'notes':           {'order_ref': ref},
        })
        return link.get('short_url')
    except Exception as e:
        log.error(f"Razorpay: {e}")
        return None

# ─────────────────────────────────────────────────────────────
# REFERRAL CODE
# ─────────────────────────────────────────────────────────────

def referral_code(first_name: str, phone: str) -> str:
    prefix = first_name[:3].upper() if len(first_name) >= 3 else 'AJS'
    return f"AJS-{prefix}-{phone[-4:]}"

# ─────────────────────────────────────────────────────────────
# LANGUAGE DETECTION
# ─────────────────────────────────────────────────────────────

_HI_WORDS = {
    'hai', 'hain', 'kya', 'aap', 'mujhe', 'chahiye', 'dikhao', 'batao',
    'kaise', 'kaha', 'nahi', 'accha', 'theek', 'zaroor', 'bhi', 'aur',
    'woh', 'yeh', 'abhi', 'jaldi', 'kaisa', 'kaisi', 'bol', 'raha', 'rahe',
    'samaj', 'samajh', 'nai', 'nahi',
}

def detect_lang(text: str) -> str:
    if not text:
        return 'en'
    if len(re.findall(r'[\u0900-\u097F]', text)) > len(text) * 0.25:
        return 'hi'
    if set(text.lower().split()) & _HI_WORDS:
        return 'hi'
    return 'en'

# ─────────────────────────────────────────────────────────────
# ARU — AI ASSISTANT
# ─────────────────────────────────────────────────────────────

_ARU = """You are Aru, a professional jewelry consultant at A Jewel Studio.

Personality: Luxury, warm, confident, professional — like a trusted personal stylist.
Never confused or uncertain. Always composed and elegant.

Responsibilities:
- Answer product questions, availability, recommendations
- Handle custom order inquiries with enthusiasm
- Generate referral codes (format: AJS-XXX-XXXX)
- Share new arrivals, trends, brand story
- Guide budget-based jewelry selection
- Respond to any non-menu question

Rules:
- Maximum 3 sentences — sharp and elegant
- No emojis, no icons
- No raw URLs or links in your text
- If price is uncertain, say the team will confirm
- Address customer by first name if known
- If customer seems confused or asks a general question, guide them warmly
"""

def ask_aru(question: str, lang: str, first_name: str, context: str = '') -> str | None:
    try:
        if not _gm:
            return None
        lang_note = (
            "Respond in English only."
            if lang == 'en' else
            "Respond in Hindi/Hinglish using Roman script only (no Devanagari)."
        )
        prompt = f"""{_ARU}
Customer first name: {first_name}
Language: {lang_note}
Context: {context}

Customer says: {question}

Reply as Aru — max 3 sentences, no emojis, no links."""
        return _gm.generate_content(prompt).text.strip()
    except Exception as e:
        log.error(f"Aru: {e}")
        return None

def is_design_description(text: str) -> bool:
    """
    Check if a text message is actually a jewelry design description.
    Prevents confused customer messages being treated as custom order details.
    """
    text_lower = text.lower()
    # Must have at least some jewelry/design related words
    design_words = {
        'ring', 'necklace', 'bracelet', 'earring', 'bangle', 'kada', 'chain',
        'pendant', 'anklet', 'choker', 'gold', 'silver', 'diamond', 'stone',
        'bridal', 'wedding', 'engagement', 'traditional', 'modern', 'design',
        'material', 'size', 'colour', 'color', 'occasion', 'gift', 'budget',
        # Hindi/Hinglish
        'sona', 'chandi', 'heera', 'haar', 'payal', 'mangalsutra', 'jhumka',
        'kangan', 'angoothi', 'shaadi', 'dulhan', 'design', 'banao', 'chahiye',
        'style', 'type', 'weight', 'gram',
    }
    words = set(re.findall(r'\w+', text_lower))
    return bool(words & design_words)

def aru_vision(image_url: str) -> dict | None:
    try:
        if not _gv:
            return None
        img = requests.get(image_url, timeout=10)
        if not img.ok:
            return None
        resp = _gv.generate_content([
            "Analyze this jewelry image. State: jewelry type, style (traditional/modern/bridal), material. One sentence.",
            {'mime_type': 'image/jpeg', 'data': img.content}
        ])
        analysis = resp.text.strip()
        al = analysis.lower()
        kw = []
        for t in ['earring', 'jhumka', 'necklace', 'ring', 'bracelet', 'bangle',
                  'kada', 'chain', 'pendant', 'anklet', 'payal', 'choker']:
            if t in al: kw.append(t)
        for s in ['traditional', 'modern', 'bridal', 'ethnic', 'classic']:
            if s in al: kw.append(s)
        return {'query': ' '.join(kw[:3]) or 'jewellery'}
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
            headers={'Authorization': f'Bearer {WA_TOKEN}', 'Content-Type': 'application/json'},
            json=payload, timeout=10
        )
        if not r.ok:
            log.error(f"WA {r.status_code}: {r.text[:300]}")
        return r.ok
    except Exception as e:
        log.error(f"WA post: {e}")
        return False

def tx(to: str, text: str) -> bool:
    return _post({'messaging_product': 'whatsapp', 'to': to,
                  'type': 'text', 'text': {'body': text}})

def btn1(to: str, body: str, bid: str, label: str) -> bool:
    return _post({
        'messaging_product': 'whatsapp', 'to': to, 'type': 'interactive',
        'interactive': {
            'type': 'button', 'body': {'text': body},
            'action': {'buttons': [{'type': 'reply', 'reply': {'id': bid, 'title': label[:20]}}]}
        }
    })

def btns(to: str, body: str, buttons: list) -> bool:
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
    """
    Single scroll list.
    HARD LIMIT: total rows across ALL sections must be <= 10.
    """
    total = sum(len(s.get('rows', [])) for s in sections)
    if total > 10:
        log.error(f"scroll() called with {total} rows — exceeds WhatsApp limit of 10.")
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
    return _post({
        'messaging_product': 'whatsapp', 'to': to, 'type': 'interactive',
        'interactive': {
            'type': 'cta_url', 'body': {'text': body},
            'action': {'name': 'cta_url',
                       'parameters': {'display_text': label[:20], 'url': url}}
        }
    })

def open_catalog(to: str, cid: str, cname: str) -> bool:
    """Open WhatsApp catalog inside WhatsApp — only selected collection's products."""
    try:
        r = requests.get(
            f"https://graph.facebook.com/v19.0/{cid}/products",
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
                        'body':   {'text': cname},
                        'footer': {'text': 'Add to cart, then tap Place Order.'},
                        'action': {
                            'catalog_id': CATALOG_ID,
                            'sections': [{
                                'title': cname[:24],
                                'product_items': [{'product_retailer_id': rid} for rid in rids[:30]]
                            }]
                        }
                    }
                })
        log.warning(f"No products in collection {cid}")
        return False
    except Exception as e:
        log.error(f"open_catalog: {e}")
        return False

def _p(t: float = 0.4):
    time.sleep(t)

# ─────────────────────────────────────────────────────────────
# FLOWS
# ─────────────────────────────────────────────────────────────

def flow_new_customer(to: str, lang: str):
    if lang == 'hi':
        tx(to, "Hello\nA Jewel Studio mein aapka swagat hai.")
        _p()
        cta(to,
            "Main Aru hoon, aapki Studio Assistant.\n"
            "Hamari exclusive collections explore karne ke liye register karein.",
            "JOIN US",
            f"https://{SHOPIFY_STORE}/pages/join-us?wa={to}")
    else:
        tx(to, "Hello\nWelcome to A Jewel Studio.")
        _p()
        cta(to,
            "I am Aru, your Studio Assistant.\n"
            "Register to explore our exclusive jewellery collections.",
            "JOIN US",
            f"https://{SHOPIFY_STORE}/pages/join-us?wa={to}")

def flow_incomplete(to: str, lang: str):
    if lang == 'hi':
        cta(to,
            "Hello\n\nAapki registration abhi complete nahi hui.\n"
            "Please registration complete karein.",
            "COMPLETE REGISTRATION",
            f"https://{SHOPIFY_STORE}/pages/join-us?wa={to}")
    else:
        cta(to,
            "Hello\n\nYour registration is not yet complete.\n"
            "Please complete it to continue.",
            "COMPLETE REGISTRATION",
            f"https://{SHOPIFY_STORE}/pages/join-us?wa={to}")

def flow_main_menu(to: str, lang: str):
    scroll(to,
        header='A Jewel Studio',
        body=(
            'Please choose a collection to explore.'
            if lang == 'en' else
            'Apni pasand ki collection select karein.'
        ),
        btn_text='MENU',
        sections=[{'title': 'Collections', 'rows': [
            {'id': 'CAT_BABY',   'title': 'Baby Jewellery'},
            {'id': 'CAT_WOMEN',  'title': 'Women Jewellery'},
            {'id': 'CAT_MEN',    'title': 'Men Jewellery'},
            {'id': 'CAT_STUDIO', 'title': 'Studio Special'},
            {'id': 'CAT_SACRED', 'title': 'Sacred Arts'},
        ]}]
    )

def flow_retail_welcome(to: str, first_name: str, lang: str):
    if lang == 'hi':
        tx(to, f"Hello {first_name}\n\nA Jewel Studio mein dobara swagat hai.")
    else:
        tx(to, f"Hello {first_name}\n\nWelcome back to A Jewel Studio.")
    _p()
    flow_main_menu(to, lang)

def flow_b2b_welcome(to: str, first_name: str, lang: str):
    if lang == 'hi':
        tx(to, f"Hello {first_name}\n\nA Jewel Studio mein dobara swagat hai.")
    else:
        tx(to, f"Hello {first_name}\n\nWelcome back to A Jewel Studio.")
    _p()
    btns(to,
        "How may I assist you today?" if lang == 'en' else "Aaj main aapki kya madad kar sakti hoon?",
        [
            {'id': 'BROWSE',       'title': 'BROWSE COLLECTIONS'},
            {'id': 'CUSTOM_ORDER', 'title': 'CUSTOM ORDER'},
            {'id': 'MY_ORDERS',    'title': 'MY ORDERS'},
        ]
    )

# Baby — single list (6 rows, within limit)
def flow_baby(to: str, lang: str):
    scroll(to, 'Baby Jewellery',
        'Select a collection.' if lang == 'en' else 'Ek collection select karein.',
        'SELECT', [_sec('Baby Jewellery', BABY)])

# Women body-part selector
def flow_women_body(to: str, lang: str):
    btns(to,
        ('You are exploring Women Jewellery.\nPlease choose a category.'
         if lang == 'en' else
         'Aap Women Jewellery dekh rahi hain.\nEk category select karein.'),
        [
            {'id': 'W_FACE', 'title': 'FACE JEWELLERY'},
            {'id': 'W_HAND', 'title': 'HAND JEWELLERY'},
            {'id': 'W_NECK', 'title': 'NECK JEWELLERY'},
        ]
    )
    _p()
    btn1(to, 'Or explore Lower Body Jewellery.', 'W_LOWER', 'LOWER BODY')

# Face — buttons then per-style list
def flow_face_menu(to: str, lang: str):
    btns(to,
        'Please choose a style to explore.' if lang == 'en' else 'Ek style select karein.',
        [
            {'id': 'F_EARRINGS', 'title': 'EARRINGS'},
            {'id': 'F_NOSE',     'title': 'NOSE JEWELLERY'},
            {'id': 'F_HEAD',     'title': 'HEAD JEWELLERY'},
        ]
    )
    _p()
    btn1(to, 'Or explore Hair Accessories.', 'F_HAIR', 'HAIR ACCESSORIES')

def flow_face_earrings(to: str, lang: str):
    scroll(to, 'Earrings', 'Select a collection.', 'SELECT',
           [_sec('Earrings', FACE_EARRINGS)])      # 10 rows — OK

def flow_face_nose(to: str, lang: str):
    scroll(to, 'Nose Jewellery', 'Select a collection.', 'SELECT',
           [_sec('Nose Jewellery', FACE_NOSE)])     # 4 rows

def flow_face_head(to: str, lang: str):
    scroll(to, 'Head Jewellery', 'Select a collection.', 'SELECT',
           [_sec('Head Jewellery', FACE_HEAD)])     # 5 rows

def flow_face_hair(to: str, lang: str):
    # Only 1 item — open catalog directly
    cname = 'Hair Clips'
    cid   = FACE_HAIR['Hair Clips']
    flow_open_collection(to, cid, cname, lang)

# Hand — buttons then per-category list
def flow_hand_menu(to: str, lang: str):
    btns(to,
        'Please choose a category.' if lang == 'en' else 'Ek category select karein.',
        [
            {'id': 'H_BANGLES',   'title': 'BANGLES AND KADA'},
            {'id': 'H_BRACELETS', 'title': 'BRACELETS'},
            {'id': 'H_RINGS',     'title': 'RINGS'},
        ]
    )
    _p()
    btn1(to, 'Or explore Armlets.', 'H_ARMLETS', 'ARMLETS')

def flow_hand_bangles(to: str, lang: str):
    scroll(to, 'Bangles and Kada', 'Select a collection.', 'SELECT',
           [_sec('Bangles and Kada', HAND_BANGLES)])   # 2 rows

def flow_hand_bracelets(to: str, lang: str):
    scroll(to, 'Bracelets', 'Select a collection.', 'SELECT',
           [_sec('Bracelets', HAND_BRACELETS)])         # 4 rows

def flow_hand_armlets(to: str, lang: str):
    cname = 'Baju Band'
    cid   = HAND_ARMLETS['Baju Band']
    flow_open_collection(to, cid, cname, lang)

def flow_hand_rings(to: str, lang: str):
    scroll(to, 'Rings', 'Select a collection.', 'SELECT',
           [_sec('Rings', HAND_RINGS)])                 # 4 rows

# Neck — single list (10 rows, exactly at limit)
def flow_neck_menu(to: str, lang: str):
    scroll(to, 'Neck Jewellery',
        'Please choose a style.' if lang == 'en' else 'Ek style select karein.',
        'SELECT',
        [
            _sec('Necklaces',   NECK_NECKLACES),   # 5
            _sec('Pendants',    NECK_PENDANTS),     # 4
            _sec('Bridal Sets', NECK_BRIDAL),       # 1
        ]
    )   # total = 10 — OK

def flow_lower(to: str, lang: str):
    scroll(to, 'Lower Body Jewellery', 'Select a collection.', 'SELECT',
           [_sec('Lower Body', LOWER)])   # 3 rows

# Men — buttons then per-category list
def flow_men_menu(to: str, lang: str):
    btns(to,
        'Please choose a category.' if lang == 'en' else 'Ek category select karein.',
        [
            {'id': 'M_RINGS',      'title': 'RINGS'},
            {'id': 'M_BRACELETS',  'title': 'BRACELETS'},
            {'id': 'M_CHAINS',     'title': 'CHAINS'},
        ]
    )
    _p()
    btn1(to, 'Or explore Men Accessories.', 'M_ACCESSORIES', 'ACCESSORIES')

def flow_men_rings(to: str, lang: str):
    scroll(to, 'Men Rings', 'Select a collection.', 'SELECT',
           [_sec('Rings', MEN_RINGS)])           # 6 rows

def flow_men_bracelets(to: str, lang: str):
    scroll(to, 'Men Bracelets', 'Select a collection.', 'SELECT',
           [_sec('Bracelets', MEN_BRACELETS)])   # 4 rows

def flow_men_chains(to: str, lang: str):
    scroll(to, 'Men Chains', 'Select a collection.', 'SELECT',
           [_sec('Chains', MEN_CHAINS)])         # 3 rows

def flow_men_accessories(to: str, lang: str):
    scroll(to, 'Men Accessories', 'Select a collection.', 'SELECT',
           [_sec('Accessories', MEN_ACCESSORIES)])  # 9 rows

# Studio
def flow_studio_menu(to: str, lang: str):
    btns(to,
        'Please choose a category.' if lang == 'en' else 'Ek category select karein.',
        [
            {'id': 'S_WATCHES', 'title': 'WATCHES'},
            {'id': 'S_ACCSS',   'title': 'ACCESSORIES'},
        ]
    )

def flow_watches(to: str, lang: str):
    scroll(to, 'Watches', 'Select a collection.', 'SELECT',
           [_sec('Watches', WATCHES)])                       # 5 rows

def flow_studio_acc(to: str, lang: str):
    scroll(to, 'Studio Accessories', 'Select a collection.', 'SELECT',
           [_sec('Studio Accessories', STUDIO_ACCESSORIES)]) # 4 rows

# Catalog open
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

# Empty catalog
def flow_empty_catalog(to: str, lang: str):
    tx(to,
        "This collection is currently being updated.\n\n"
        "We accept custom orders and can craft a design of your choice."
        if lang == 'en' else
        "Yeh collection abhi update ho rahi hai.\n\n"
        "Hum custom orders accept karte hain aur aapki pasand ka design bana sakte hain."
    )
    _p()
    btns(to,
        'How would you like to proceed?' if lang == 'en' else 'Aap kaise aage badhna chahenge?',
        [
            {'id': 'CUSTOM_ORDER',  'title': 'CUSTOM ORDER'},
            {'id': 'BROWSE',        'title': 'BROWSE COLLECTIONS'},
            {'id': 'CONTACT_TEAM',  'title': 'CONTACT TEAM'},
        ]
    )

# Custom order
def flow_custom_order_start(to: str, first_name: str, phone: str, is_b2b: bool, lang: str):
    get_session(phone)['custom_step'] = 'awaiting_description'
    if lang == 'hi':
        tx(to,
            f"Hume aapke liye custom piece banana bahut khushi hogi, {first_name}.\n\n"
            "Apni requirements batayein — jewellery ka type, material, occasion, aur koi specific design idea."
        )
    else:
        tx(to,
            f"We would be delighted to create a custom piece for you, {first_name}.\n\n"
            "Please describe your requirements — jewellery type, material, occasion, and any design ideas."
        )
    if is_b2b:
        _p()
        btn1(to, 'You may also upload a reference design file.', 'UPLOAD_FILE', 'UPLOAD DESIGN FILE')

def flow_custom_order_done(to: str, first_name: str, phone: str, description: str, is_b2b: bool, lang: str):
    tx(to,
        "Thank you for sharing your requirements.\n\n"
        "Our design team will review your request and get back to you within 24 hours."
        if lang == 'en' else
        "Aapki requirements share karne ke liye shukriya.\n\n"
        "Hamari design team 24 ghante mein aapse contact karegi."
    )
    admin_email(
        subject=f"Custom Order — {first_name} — {phone}",
        body=(
            f"Custom order request received.\n\n"
            f"Customer : {first_name}\n"
            f"Phone    : {phone}\n"
            f"Type     : {'B2B' if is_b2b else 'Retail'}\n\n"
            f"Requirements:\n{description}"
        )
    )

# Order placed
def flow_order_placed(to: str, phone: str, first_name: str, items: list, lang: str):
    total = sum(int(float(i.get('item_price', 0)) * 100) * i.get('quantity', 1) for i in items)
    ref   = f"AJS-{phone[-4:]}-{int(datetime.now().timestamp())}"
    url   = rzp_link(total, first_name, phone, ref)
    if url:
        body = (
            f"A Jewel Studio choose karne ke liye dhanyavaad.\n\nOrder Reference: {ref}\n\n"
            "Payment ke liye neeche tap karein."
            if lang == 'hi' else
            f"Thank you for choosing A Jewel Studio.\n\nOrder Reference: {ref}\n\n"
            "Please complete your payment using the button below."
        )
        cta(to, body, 'PAY NOW', url)
    else:
        tx(to, "To complete your order please contact our team. A payment link will be shared shortly.")

    item_lines = '\n'.join(
        f"  - {i.get('product_name','Item')} x{i.get('quantity',1)} @ Rs.{i.get('item_price',0)}"
        for i in items
    )
    admin_email(
        subject=f"New Order — {ref} — {first_name}",
        body=f"New order.\n\nRef: {ref}\nCustomer: {first_name}\nPhone: {phone}\n\nItems:\n{item_lines}\n\nTotal: Rs.{total/100:.2f}"
    )

# Fallback
def flow_aru_fallback(to: str, first_name: str, lang: str):
    btns(to,
        (
            f"Thank you for reaching out, {first_name}.\n"
            "Our team is here to assist you."
            if lang == 'en' else
            f"Humse contact karne ke liye shukriya, {first_name}.\n"
            "Hamari team aapki madad ke liye available hai."
        ),
        [
            {'id': 'BROWSE',       'title': 'BROWSE COLLECTIONS'},
            {'id': 'CUSTOM_ORDER', 'title': 'CUSTOM ORDER'},
            {'id': 'CONTACT_TEAM', 'title': 'CONTACT TEAM'},
        ]
    )

# ─────────────────────────────────────────────────────────────
# KEYWORDS
# ─────────────────────────────────────────────────────────────

_KW = {
    'greet':    {'hi', 'hello', 'hey', 'hlo', 'hii', 'start', 'namaste'},
    'tracking': {'order', 'track', 'status', 'delivery', 'shipping'},
    'referral': {'referral', 'refer', 'code', 'invite'},
    'custom':   {'custom', 'customize', 'bespoke', 'special order', 'custom order'},
    'hours':    {'timing', 'time', 'open', 'close', 'hours'},
    'about':    {'about', 'brand', 'studio', 'company'},
    'help':     {'help', 'support', 'assist'},
}

def detect_kw(text: str) -> str | None:
    words = set(text.lower().split())
    for ktype, kwords in _KW.items():
        if words & kwords:
            return ktype
    return None

# ─────────────────────────────────────────────────────────────
# MAIN HANDLER
# ─────────────────────────────────────────────────────────────

def handle(phone: str, msg: dict):
    _cleanup()

    mtype  = msg.get('type')
    cdata  = customer_status(phone)
    s      = get_session(phone)
    s['first_name'] = cdata['first_name']

    lang       = s.get('lang', 'en')
    first_name = s['first_name']
    status     = cdata['status']

    if mtype == 'text':
        raw  = msg.get('text', {}).get('body', '').strip()
        lang = detect_lang(raw)
        s['lang'] = lang

    # ── TEXT ──────────────────────────────────────────────────
    if mtype == 'text':
        text = msg.get('text', {}).get('body', '').strip()

        if status == 'new':
            flow_new_customer(phone, lang); return
        if status == 'incomplete':
            flow_incomplete(phone, lang); return

        # Custom order description step
        if s.get('custom_step') == 'awaiting_description':
            if is_design_description(text):
                # Valid description — save and confirm
                s['custom_step'] = None
                flow_custom_order_done(phone, first_name, phone, text,
                                       status == 'b2b', lang)
            else:
                # Customer seems confused — Aru responds, keeps step active
                aru = ask_aru(text, lang, first_name,
                              "Customer is being asked to describe a custom jewelry order. "
                              "They seem confused. Gently clarify what details we need "
                              "(jewelry type, material, occasion, design ideas).")
                if aru:
                    tx(phone, aru)
                else:
                    tx(phone,
                        "No worries. Please tell us what kind of jewellery you would like — "
                        "type, material, occasion, and any design preference."
                        if lang == 'en' else
                        "Koi baat nahi. Batayein aap kaise jewellery chahte hain — "
                        "type, material, occasion, aur koi design idea."
                    )
            return

        # Order reference
        if re.match(r'AJS-[A-Z0-9]+-\d+', text.upper()):
            tx(phone,
                f"To track order {text.upper()}, {first_name}, please contact our team "
                "and they will provide the latest status shortly."
                if lang == 'en' else
                f"Order {text.upper()} track karne ke liye, {first_name}, hamari team se contact karein. "
                "Woh jald hi latest status batayenge."
            )
            return

        kw = detect_kw(text)

        if kw == 'greet':
            if status == 'b2b':
                flow_b2b_welcome(phone, first_name, lang)
            else:
                flow_retail_welcome(phone, first_name, lang)
            return

        if kw == 'tracking':
            tx(phone,
                f"To track your order, {first_name}, please share your Order Reference "
                "(format: AJS-XXXX-XXXXXXXXXX). Our team will update you shortly."
                if lang == 'en' else
                f"Order track karne ke liye, {first_name}, Order Reference share karein "
                "(format: AJS-XXXX-XXXXXXXXXX). Hamari team jald hi update karegi."
            )
            return

        if kw == 'referral':
            code = referral_code(first_name, phone)
            url  = f"https://{SHOPIFY_STORE}/pages/join-us?ref={code}"
            body = (
                f"Your Referral Code\n\nCode: {code}\n\n"
                "Share this with friends and family. When they register using your code, "
                "they join the A Jewel Studio family."
                if lang == 'en' else
                f"Aapka Referral Code\n\nCode: {code}\n\n"
                "Yeh code doston aur family ke saath share karein. Jab woh aapke code se "
                "register karenge, woh A Jewel Studio family ka hissa ban jayenge."
            )
            cta(phone, body, 'SHARE REFERRAL', url)
            return

        if kw == 'custom':
            flow_custom_order_start(phone, first_name, phone, status == 'b2b', lang)
            return

        if kw == 'hours':
            tx(phone,
                "A Jewel Studio\n\nBusiness Hours:\n"
                "Monday to Saturday — 10:00 AM to 7:00 PM\n"
                "Sunday — By Appointment Only"
                if lang == 'en' else
                "A Jewel Studio\n\nKaam ke Ghante:\n"
                "Somvar se Shanivar — Subah 10 baje se Shaam 7 baje tak\n"
                "Itwar — Sirf Appointment par"
            )
            return

        if kw == 'about':
            tx(phone,
                "A Jewel Studio is a premium jewellery brand offering an exclusive range of "
                "handcrafted pieces for every occasion — traditional bridal to modern everyday designs."
                if lang == 'en' else
                "A Jewel Studio ek premium jewellery brand hai jo har occasion ke liye "
                "exclusive handcrafted pieces offer karta hai."
            )
            return

        # Fuzzy product search
        result = fuzzy_search(text)
        if result['found']:
            tx(phone,
                "I found a matching collection for your search.\nExplore the products below."
                if lang == 'en' else
                "Aapki search ke liye ek matching collection mila.\nNeeche products dekhen."
            )
            _p()
            flow_open_collection(phone, result['id'], result['name'], lang)
            return

        # Aru handles everything else
        aru = ask_aru(text, lang, first_name,
                      f"Customer status: {status}. Any topic possible — products, availability, recommendations, general.")
        if aru:
            result2 = fuzzy_search(aru)
            if result2['found']:
                tx(phone, aru)
                _p()
                flow_open_collection(phone, result2['id'], result2['name'], lang)
                return
            tx(phone, aru)
            _p()

        if status == 'b2b':
            flow_b2b_welcome(phone, first_name, lang)
        else:
            flow_main_menu(phone, lang)
        return

    # ── INTERACTIVE ───────────────────────────────────────────
    if mtype == 'interactive':
        itype = msg['interactive'].get('type')

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
                flow_lower(phone, lang)
            elif bid == 'F_EARRINGS':
                flow_face_earrings(phone, lang)
            elif bid == 'F_NOSE':
                flow_face_nose(phone, lang)
            elif bid == 'F_HEAD':
                flow_face_head(phone, lang)
            elif bid == 'F_HAIR':
                flow_face_hair(phone, lang)
            elif bid == 'H_BANGLES':
                flow_hand_bangles(phone, lang)
            elif bid == 'H_BRACELETS':
                flow_hand_bracelets(phone, lang)
            elif bid == 'H_ARMLETS':
                flow_hand_armlets(phone, lang)
            elif bid == 'H_RINGS':
                flow_hand_rings(phone, lang)
            elif bid == 'M_RINGS':
                flow_men_rings(phone, lang)
            elif bid == 'M_BRACELETS':
                flow_men_bracelets(phone, lang)
            elif bid == 'M_CHAINS':
                flow_men_chains(phone, lang)
            elif bid == 'M_ACCESSORIES':
                flow_men_accessories(phone, lang)
            elif bid == 'S_WATCHES':
                flow_watches(phone, lang)
            elif bid == 'S_ACCSS':
                flow_studio_acc(phone, lang)
            elif bid == 'CUSTOM_ORDER':
                flow_custom_order_start(phone, first_name, phone, status == 'b2b', lang)
            elif bid == 'MY_ORDERS':
                tx(phone,
                    f"To track your order, {first_name}, please share your Order Reference Number."
                    if lang == 'en' else
                    f"Order track karne ke liye, {first_name}, Order Reference Number share karein."
                )
            elif bid == 'CONTACT_TEAM':
                tx(phone,
                    "Our team is available Monday to Saturday, 10 AM to 7 PM.\n"
                    "Someone will reach out to you shortly."
                    if lang == 'en' else
                    "Hamari team Somvar se Shanivar, 10 AM se 7 PM tak available hai.\n"
                    "Koi jald hi aapse contact karega."
                )
            elif bid == 'UPLOAD_FILE':
                tx(phone,
                    "Please upload your design file or reference image directly in this chat.\n"
                    "Our team will review it within 24 hours."
                    if lang == 'en' else
                    "Apna design file ya reference image seedha is chat mein upload karein.\n"
                    "Hamari team 24 ghante mein review karegi."
                )

        elif itype == 'list_reply':
            lid = msg['interactive']['list_reply']['id']
            log.info(f"List: {lid}")

            if lid == 'CAT_BABY':
                flow_baby(phone, lang)
            elif lid == 'CAT_WOMEN':
                flow_women_body(phone, lang)
            elif lid == 'CAT_MEN':
                flow_men_menu(phone, lang)
            elif lid == 'CAT_STUDIO':
                flow_studio_menu(phone, lang)
            elif lid == 'CAT_SACRED':
                flow_empty_catalog(phone, lang)
            elif lid.startswith('C_'):
                cid   = lid[2:]
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
            "Thank you for the reference.\nPlease describe what you are looking for "
            "and I will help you find the perfect piece."
            if lang == 'en' else
            "Reference ke liye shukriya.\nBatayein aap kya dhundh rahe hain "
            "aur main perfect piece dhundhne mein madad karungi."
        )
        _p()
        btn1(phone, 'Would you like to place a custom order?', 'CUSTOM_ORDER', 'CUSTOM ORDER')
        return

    # ── ORDER (catalog cart) ──────────────────────────────────
    if mtype == 'order':
        items = msg.get('order', {}).get('product_items', [])
        flow_order_placed(phone, phone, first_name, items, lang)
        return

# ─────────────────────────────────────────────────────────────
# WEBHOOK
# ─────────────────────────────────────────────────────────────

@app.route('/webhook', methods=['GET'])
def verify():
    if (request.args.get('hub.mode') == 'subscribe'
            and request.args.get('hub.verify_token') == VERIFY_TOKEN):
        return request.args.get('hub.challenge'), 200
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
            phone  = m.get('from')
            msg_id = m.get('id', '')
            if phone and msg_id:
                if _already_seen(msg_id):
                    log.info(f"Duplicate skipped: {msg_id}")
                    continue
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
def not_found(_): return jsonify({'error': 'Not found'}), 404

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
