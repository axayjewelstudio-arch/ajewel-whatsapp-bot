# -*- coding: utf-8 -*-
"""
A JEWEL STUDIO — WhatsApp Bot  v4
Aru AI Assistant | 82 Collections | Bilingual | Full Production

WELCOME FLOW (Retail + B2B)
  Hello {name} + MENU button
  MENU → scroll list: CATALOGS / CUSTOMISE JEWELRY / MY ORDERS
  CATALOGS → Baby Jewelry / Women Jewelry / Men Jewelry / Studio Special / Sacred Arts
  CUSTOMISE JEWELRY → custom order description
  MY ORDERS → order reference prompt

MEN JEWELRY
  Scroll list (4 rows): Rings / Bracelets / Chains / Accessories
  Each → per-category scroll list → catalog

WHATSAPP LIST LIMIT: total rows across ALL sections <= 10
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

WA_TOKEN      = os.getenv('WHATSAPP_TOKEN', '')
WA_PHONE_ID   = os.getenv('WHATSAPP_PHONE_ID', '')
CATALOG_ID    = os.getenv('WHATSAPP_CATALOG_ID', '')
VERIFY_TOKEN  = os.getenv('VERIFY_TOKEN', 'ajewel2024')
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
    _gm = genai.GenerativeModel('gemini-pro')
    _gv = genai.GenerativeModel('gemini-pro-vision')
else:
    _gm = _gv = None

# ─────────────────────────────────────────────────────────────
# DEDUPLICATION
# ─────────────────────────────────────────────────────────────

_processed: list = []
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
# ─────────────────────────────────────────────────────────────

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
    'Bridal Nath':   '26146672631634215',
    'Nose Pins':     '25816769131325224',
    'Septum Rings':  '26137405402565188',
    'Clip On Rings': '25956080384032593',
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

# Flat id → name
ID_TO_NAME: dict = {}
def _reg(d): [ID_TO_NAME.update({cid: name}) for name, cid in d.items()]
for _d in [BABY, FACE_EARRINGS, FACE_NOSE, FACE_HEAD, FACE_HAIR,
           HAND_BANGLES, HAND_BRACELETS, HAND_ARMLETS, HAND_RINGS,
           NECK_NECKLACES, NECK_PENDANTS, NECK_BRIDAL, LOWER,
           MEN_RINGS, MEN_BRACELETS, MEN_CHAINS, MEN_ACCESSORIES,
           WATCHES, STUDIO_ACCESSORIES]:
    _reg(_d)

ALL_NAMES = list(ID_TO_NAME.values())

# ─────────────────────────────────────────────────────────────
# HELPERS
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
        ws     = _gc.open_by_key(SHEET_ID).worksheet('Registrations')
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
                    'b2b':        bool(tags & {'B2B', 'Wholesale', 'b2b', 'wholesale'}),
                }
        return {'exists': False}
    except Exception as e:
        log.error(f"Shopify: {e}")
        return {'exists': False}

def customer_status(phone: str) -> dict:
    s = shopify_lookup(phone)
    if s['exists']:
        return {
            'status':     'b2b' if s['b2b'] else 'retail',
            'first_name': s['first_name'] or 'Customer',
        }
    sh = sheets_lookup(phone)
    if sh['exists']:
        return {
            'status':     'incomplete',
            'first_name': sh['first_name'] or 'Customer',
        }
    sheets_log(phone)
    return {'status': 'new', 'first_name': 'Customer'}

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
# REFERRAL
# ─────────────────────────────────────────────────────────────

def referral_code(first_name: str, phone: str) -> str:
    prefix = first_name[:3].upper() if len(first_name) >= 3 else 'AJS'
    return f"AJS-{prefix}-{phone[-4:]}"

# ─────────────────────────────────────────────────────────────
# LANGUAGE
# ─────────────────────────────────────────────────────────────

_HI = {
    'hai', 'hain', 'kya', 'aap', 'mujhe', 'chahiye', 'dikhao', 'batao',
    'kaise', 'kaha', 'nahi', 'accha', 'theek', 'zaroor', 'bhi', 'aur',
    'woh', 'yeh', 'abhi', 'jaldi', 'bol', 'raha', 'rahe', 'samaj', 'nai',
}

def detect_lang(text: str) -> str:
    if not text:
        return 'en'
    if len(re.findall(r'[\u0900-\u097F]', text)) > len(text) * 0.25:
        return 'hi'
    if set(text.lower().split()) & _HI:
        return 'hi'
    return 'en'

# ─────────────────────────────────────────────────────────────
# ARU — AI ASSISTANT
# ─────────────────────────────────────────────────────────────

_ARU = """You are Aru, a professional jewelry consultant at A Jewel Studio.
Personality: Luxury, warm, confident, professional.
Rules:
- Max 2 sentences. Sharp and elegant.
- No emojis, no icons, no raw URLs.
- Address customer by first name.
- If unsure about price or stock, say the team will confirm.
"""

def ask_aru(question: str, lang: str, first_name: str, context: str = '') -> str | None:
    try:
        if not _gm:
            return None
        lang_note = (
            "Respond in English only."
            if lang == 'en' else
            "Respond in Hindi/Hinglish using Roman script only."
        )
        prompt = (
            f"{_ARU}\nCustomer: {first_name}\nLanguage: {lang_note}\n"
            f"Context: {context}\n\nCustomer says: {question}\n\n"
            "Reply as Aru — max 2 sentences, no emojis."
        )
        return _gm.generate_content(prompt).text.strip()
    except Exception as e:
        log.error(f"Aru: {e}")
        return None

def is_design_desc(text: str) -> bool:
    words = set(re.findall(r'\w+', text.lower()))
    design_words = {
        'ring', 'necklace', 'bracelet', 'earring', 'bangle', 'kada', 'chain',
        'pendant', 'anklet', 'choker', 'gold', 'silver', 'diamond', 'stone',
        'bridal', 'wedding', 'engagement', 'design', 'material', 'occasion',
        'budget', 'style', 'type', 'weight', 'gram', 'sona', 'chandi',
        'haar', 'payal', 'jhumka', 'kangan', 'angoothi', 'shaadi', 'dulhan',
    }
    return bool(words & design_words)

def aru_vision(image_url: str) -> dict | None:
    try:
        if not _gv:
            return None
        img = requests.get(image_url, timeout=10)
        if not img.ok:
            return None
        resp = _gv.generate_content([
            "Identify jewelry type and style in this image. One sentence.",
            {'mime_type': 'image/jpeg', 'data': img.content}
        ])
        al = resp.text.strip().lower()
        kw = [t for t in ['earring', 'jhumka', 'necklace', 'ring', 'bracelet',
                           'bangle', 'kada', 'chain', 'pendant', 'anklet',
                           'traditional', 'modern', 'bridal'] if t in al]
        return {'query': ' '.join(kw[:3]) or 'jewelry'}
    except Exception as e:
        log.error(f"Vision: {e}")
        return None

# ─────────────────────────────────────────────────────────────
# WHATSAPP SENDERS
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
    return _post({'messaging_product': 'whatsapp', 'to': to,
                  'type': 'text', 'text': {'body': text}})

def btn1(to: str, body: str, bid: str, label: str) -> bool:
    return _post({
        'messaging_product': 'whatsapp', 'to': to, 'type': 'interactive',
        'interactive': {
            'type': 'button', 'body': {'text': body},
            'action': {'buttons': [
                {'type': 'reply', 'reply': {'id': bid, 'title': label[:20]}}
            ]}
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
    total = sum(len(s.get('rows', [])) for s in sections)
    if total > 10:
        log.error(f"scroll() {total} rows — exceeds WA limit of 10!")
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
        log.warning(f"No products: {cid}")
        return False
    except Exception as e:
        log.error(f"open_catalog: {e}")
        return False

def _p(t: float = 0.4):
    time.sleep(t)

# ─────────────────────────────────────────────────────────────
# FLOWS
# ─────────────────────────────────────────────────────────────

# ── NEW CUSTOMER ──────────────────────────────────────────────
def flow_new_customer(to: str, lang: str):
    if lang == 'hi':
        tx(to, "Hello\nA Jewel Studio mein aapka swagat hai.")
        _p()
        cta(to,
            "Main Aru hoon, aapki Studio Assistant.\n"
            "Hamari exclusive jewelry collections explore karne ke liye register karein.",
            "JOIN US",
            f"https://{SHOPIFY_STORE}/pages/join-us?wa={to}")
    else:
        tx(to, "Hello\nWelcome to A Jewel Studio.")
        _p()
        cta(to,
            "I am Aru, your Studio Assistant.\n"
            "Register to explore our exclusive jewelry collections.",
            "JOIN US",
            f"https://{SHOPIFY_STORE}/pages/join-us?wa={to}")

# ── INCOMPLETE REGISTRATION ───────────────────────────────────
def flow_incomplete(to: str, lang: str):
    if lang == 'hi':
        cta(to,
            "Hello\nAapki registration complete nahi hui hai.\n"
            "Please registration complete karein.",
            "COMPLETE REGISTRATION",
            f"https://{SHOPIFY_STORE}/pages/join-us?wa={to}")
    else:
        cta(to,
            "Hello\nYour registration is not yet complete.\n"
            "Please complete it to continue.",
            "COMPLETE REGISTRATION",
            f"https://{SHOPIFY_STORE}/pages/join-us?wa={to}")

# ── WELCOME (Retail + B2B both get MENU button) ───────────────
def flow_welcome(to: str, first_name: str, lang: str):
    if lang == 'hi':
        tx(to, f"Hello {first_name}\nA Jewel Studio mein dobara swagat hai.")
    else:
        tx(to, f"Hello {first_name}\nWelcome back to A Jewel Studio.")
    _p()
    btn1(to, "How may I assist you today?" if lang == 'en' else "Aaj main aapki kya madad kar sakti hoon?",
         'MENU', 'MENU')

# ── ACTION MENU (MENU button click) ──────────────────────────
# Scroll list: CATALOGS / CUSTOMISE JEWELRY / MY ORDERS
def flow_action_menu(to: str, lang: str):
    scroll(to,
        header='A Jewel Studio',
        body='Please select an option.' if lang == 'en' else 'Ek option select karein.',
        btn_text='SELECT',
        sections=[{'title': 'Options', 'rows': [
            {'id': 'ACT_CATALOGS',  'title': 'Catalogs'},
            {'id': 'ACT_CUSTOMISE', 'title': 'Customise Jewelry'},
            {'id': 'ACT_ORDERS',    'title': 'My Orders'},
        ]}]
    )

# ── CATALOGS LIST ─────────────────────────────────────────────
def flow_catalogs(to: str, lang: str):
    scroll(to,
        header='Catalogs',
        body='Select a category.' if lang == 'en' else 'Ek category select karein.',
        btn_text='SELECT',
        sections=[{'title': 'Collections', 'rows': [
            {'id': 'CAT_BABY',   'title': 'Baby Jewelry'},
            {'id': 'CAT_WOMEN',  'title': 'Women Jewelry'},
            {'id': 'CAT_MEN',    'title': 'Men Jewelry'},
            {'id': 'CAT_STUDIO', 'title': 'Studio Special'},
            {'id': 'CAT_SACRED', 'title': 'Sacred Arts'},
        ]}]
    )

# ── BABY ──────────────────────────────────────────────────────
def flow_baby(to: str, lang: str):
    scroll(to, 'Baby Jewelry',
        'Select a collection.' if lang == 'en' else 'Collection select karein.',
        'SELECT', [_sec('Baby Jewelry', BABY)])

# ── WOMEN ─────────────────────────────────────────────────────
def flow_women_body(to: str, lang: str):
    btns(to,
        'Select a category.' if lang == 'en' else 'Ek category select karein.',
        [
            {'id': 'W_FACE', 'title': 'FACE JEWELRY'},
            {'id': 'W_HAND', 'title': 'HAND JEWELRY'},
            {'id': 'W_NECK', 'title': 'NECK JEWELRY'},
        ]
    )
    _p()
    btn1(to, 'Or explore Lower Body Jewelry.', 'W_LOWER', 'LOWER BODY')

def flow_face_menu(to: str, lang: str):
    btns(to,
        'Select a style.' if lang == 'en' else 'Ek style select karein.',
        [
            {'id': 'F_EARRINGS', 'title': 'EARRINGS'},
            {'id': 'F_NOSE',     'title': 'NOSE JEWELRY'},
            {'id': 'F_HEAD',     'title': 'HEAD JEWELRY'},
        ]
    )
    _p()
    btn1(to, 'Or explore Hair Accessories.', 'F_HAIR', 'HAIR ACCESSORIES')

def flow_face_earrings(to: str, lang: str):
    scroll(to, 'Earrings', 'Select a collection.', 'SELECT',
           [_sec('Earrings', FACE_EARRINGS)])

def flow_face_nose(to: str, lang: str):
    scroll(to, 'Nose Jewelry', 'Select a collection.', 'SELECT',
           [_sec('Nose Jewelry', FACE_NOSE)])

def flow_face_head(to: str, lang: str):
    scroll(to, 'Head Jewelry', 'Select a collection.', 'SELECT',
           [_sec('Head Jewelry', FACE_HEAD)])

def flow_face_hair(to: str, lang: str):
    flow_open_collection(to, FACE_HAIR['Hair Clips'], 'Hair Clips', lang)

def flow_hand_menu(to: str, lang: str):
    btns(to,
        'Select a category.' if lang == 'en' else 'Ek category select karein.',
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
           [_sec('Bangles and Kada', HAND_BANGLES)])

def flow_hand_bracelets(to: str, lang: str):
    scroll(to, 'Bracelets', 'Select a collection.', 'SELECT',
           [_sec('Bracelets', HAND_BRACELETS)])

def flow_hand_armlets(to: str, lang: str):
    flow_open_collection(to, HAND_ARMLETS['Baju Band'], 'Baju Band', lang)

def flow_hand_rings(to: str, lang: str):
    scroll(to, 'Rings', 'Select a collection.', 'SELECT',
           [_sec('Rings', HAND_RINGS)])

def flow_neck_menu(to: str, lang: str):
    # 10 rows total — OK
    scroll(to, 'Neck Jewelry',
        'Select a style.' if lang == 'en' else 'Ek style select karein.',
        'SELECT',
        [
            _sec('Necklaces',   NECK_NECKLACES),   # 5
            _sec('Pendants',    NECK_PENDANTS),     # 4
            _sec('Bridal Sets', NECK_BRIDAL),       # 1
        ]
    )

def flow_lower(to: str, lang: str):
    scroll(to, 'Lower Body Jewelry', 'Select a collection.', 'SELECT',
           [_sec('Lower Body', LOWER)])

# ── MEN — scroll list first (4 sub-cats), then each sub has its own list ──
def flow_men_menu(to: str, lang: str):
    # 4 rows — sub-category picker via scroll list
    scroll(to, 'Men Jewelry',
        'Select a category.' if lang == 'en' else 'Ek category select karein.',
        'SELECT',
        [{'title': 'Men Jewelry', 'rows': [
            {'id': 'M_RINGS',      'title': 'Rings'},
            {'id': 'M_BRACELETS',  'title': 'Bracelets'},
            {'id': 'M_CHAINS',     'title': 'Chains'},
            {'id': 'M_ACCESSORIES','title': 'Accessories'},
        ]}]
    )

def flow_men_rings(to: str, lang: str):
    scroll(to, 'Men Rings', 'Select a collection.', 'SELECT',
           [_sec('Rings', MEN_RINGS)])

def flow_men_bracelets(to: str, lang: str):
    scroll(to, 'Men Bracelets', 'Select a collection.', 'SELECT',
           [_sec('Bracelets', MEN_BRACELETS)])

def flow_men_chains(to: str, lang: str):
    scroll(to, 'Men Chains', 'Select a collection.', 'SELECT',
           [_sec('Chains', MEN_CHAINS)])

def flow_men_accessories(to: str, lang: str):
    scroll(to, 'Men Accessories', 'Select a collection.', 'SELECT',
           [_sec('Accessories', MEN_ACCESSORIES)])

# ── STUDIO ────────────────────────────────────────────────────
def flow_studio_menu(to: str, lang: str):
    btns(to, 'Select a category.', [
        {'id': 'S_WATCHES', 'title': 'WATCHES'},
        {'id': 'S_ACCSS',   'title': 'ACCESSORIES'},
    ])

def flow_watches(to: str, lang: str):
    scroll(to, 'Watches', 'Select a collection.', 'SELECT',
           [_sec('Watches', WATCHES)])

def flow_studio_acc(to: str, lang: str):
    scroll(to, 'Studio Accessories', 'Select a collection.', 'SELECT',
           [_sec('Studio Accessories', STUDIO_ACCESSORIES)])

# ── CATALOG OPEN ──────────────────────────────────────────────
def flow_open_collection(to: str, cid: str, cname: str, lang: str):
    tx(to,
        f"You are viewing our {cname} Collection.\n"
        "Add your favourites to the cart and tap Place Order."
        if lang == 'en' else
        f"Aap {cname} Collection dekh rahe hain.\n"
        "Pasandida design cart mein add karein aur Place Order tap karein."
    )
    _p()
    if not open_catalog(to, cid, cname):
        flow_empty_catalog(to, lang)

# ── EMPTY CATALOG ─────────────────────────────────────────────
def flow_empty_catalog(to: str, lang: str):
    tx(to,
        "This collection is being updated.\n\n"
        "We accept custom orders — our team can craft a design of your choice."
        if lang == 'en' else
        "Yeh collection update ho rahi hai.\n\n"
        "Hum custom orders accept karte hain — aapki pasand ka design bana sakte hain."
    )
    _p()
    btns(to,
        'How would you like to proceed?' if lang == 'en' else 'Kaise aage badhna chahenge?',
        [
            {'id': 'ACT_CUSTOMISE', 'title': 'CUSTOMISE JEWELRY'},
            {'id': 'ACT_CATALOGS',  'title': 'CATALOGS'},
            {'id': 'CONTACT_TEAM',  'title': 'CONTACT TEAM'},
        ]
    )

# ── CUSTOM ORDER ──────────────────────────────────────────────
def flow_custom_start(to: str, first_name: str, phone: str, is_b2b: bool, lang: str):
    get_session(phone)['custom_step'] = 'awaiting_description'
    if lang == 'hi':
        tx(to,
            f"Hume aapke liye custom piece banana bahut khushi hogi, {first_name}.\n\n"
            "Apni requirements batayein — jewelry ka type, material, occasion, aur design idea."
        )
    else:
        tx(to,
            f"We would be delighted to create a custom piece for you, {first_name}.\n\n"
            "Please describe your requirements — jewelry type, material, occasion, and any design ideas."
        )
    if is_b2b:
        _p()
        btn1(to, 'You may also upload a reference design file.', 'UPLOAD_FILE', 'UPLOAD DESIGN FILE')

def flow_custom_done(to: str, first_name: str, phone: str, desc: str, is_b2b: bool, lang: str):
    tx(to,
        "Thank you. Our design team will review your request and contact you within 24 hours."
        if lang == 'en' else
        "Shukriya. Hamari design team 24 ghante mein aapse contact karegi."
    )
    admin_email(
        subject=f"Custom Order — {first_name} — {phone}",
        body=f"Custom order request.\n\nCustomer: {first_name}\nPhone: {phone}\nType: {'B2B' if is_b2b else 'Retail'}\n\nRequirements:\n{desc}"
    )

# ── ORDER PLACED ──────────────────────────────────────────────
def flow_order_placed(to: str, phone: str, first_name: str, items: list, lang: str):
    total = sum(int(float(i.get('item_price', 0)) * 100) * i.get('quantity', 1) for i in items)
    ref   = f"AJS-{phone[-4:]}-{int(datetime.now().timestamp())}"
    url   = rzp_link(total, first_name, phone, ref)
    if url:
        body = (
            f"Thank you for choosing A Jewel Studio.\n\nOrder Reference: {ref}\n\n"
            "Please complete your payment using the button below."
            if lang == 'en' else
            f"A Jewel Studio choose karne ke liye dhanyavaad.\n\nOrder Reference: {ref}\n\n"
            "Payment ke liye neeche tap karein."
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

# ─────────────────────────────────────────────────────────────
# KEYWORDS
# ─────────────────────────────────────────────────────────────

_KW = {
    'greet':    {'hi', 'hello', 'hey', 'hlo', 'hii', 'start', 'namaste'},
    'tracking': {'order', 'track', 'status', 'delivery'},
    'referral': {'referral', 'refer', 'code', 'invite'},
    'custom':   {'custom', 'customize', 'bespoke', 'customise'},
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
            if is_design_desc(text):
                s['custom_step'] = None
                flow_custom_done(phone, first_name, phone, text, status == 'b2b', lang)
            else:
                aru = ask_aru(text, lang, first_name,
                    "Customer is being asked for custom jewelry requirements. "
                    "They seem confused. Gently ask for jewelry type, material, occasion.")
                tx(phone, aru if aru else (
                    "Please describe the jewelry you have in mind — type, material, occasion, and design."
                    if lang == 'en' else
                    "Jewelry ki requirements batayein — type, material, occasion, aur design."
                ))
            return

        # Order reference
        if re.match(r'AJS-[A-Z0-9]+-\d+', text.upper()):
            tx(phone,
                f"To track order {text.upper()}, please contact our team and they will update you shortly."
                if lang == 'en' else
                f"Order {text.upper()} ke liye hamari team se contact karein. Woh jald update karenge."
            )
            return

        kw = detect_kw(text)

        if kw == 'greet':
            flow_welcome(phone, first_name, lang); return

        if kw == 'tracking':
            tx(phone,
                f"Please share your Order Reference (AJS-XXXX-XXXXXXXXXX), {first_name}. "
                "Our team will update you shortly."
                if lang == 'en' else
                f"Order Reference share karein (AJS-XXXX-XXXXXXXXXX), {first_name}. "
                "Team jald update karegi."
            )
            return

        if kw == 'referral':
            code = referral_code(first_name, phone)
            url  = f"https://{SHOPIFY_STORE}/pages/join-us?ref={code}"
            cta(phone,
                f"Your Referral Code: {code}\n\n"
                "Share with friends and family to invite them to A Jewel Studio."
                if lang == 'en' else
                f"Aapka Referral Code: {code}\n\n"
                "Doston aur family ke saath share karein.",
                'SHARE REFERRAL', url)
            return

        if kw == 'custom':
            flow_custom_start(phone, first_name, phone, status == 'b2b', lang); return

        if kw == 'hours':
            tx(phone,
                "A Jewel Studio\nMonday to Saturday: 10:00 AM – 7:00 PM\nSunday: By Appointment Only"
                if lang == 'en' else
                "A Jewel Studio\nSomvar se Shanivar: Subah 10 – Shaam 7\nItwar: Sirf Appointment par"
            )
            return

        if kw == 'about':
            tx(phone,
                "A Jewel Studio is a premium jewelry brand offering handcrafted pieces for every occasion."
                if lang == 'en' else
                "A Jewel Studio ek premium jewelry brand hai — har occasion ke liye exclusive handcrafted pieces."
            )
            return

        # Fuzzy search
        result = fuzzy_search(text)
        if result['found']:
            tx(phone,
                f"Found a matching collection for your search."
                if lang == 'en' else
                f"Aapki search ke liye matching collection mila."
            )
            _p()
            flow_open_collection(phone, result['id'], result['name'], lang)
            return

        # Aru
        aru = ask_aru(text, lang, first_name,
                      f"Status: {status}. Topics: products, availability, recommendations.")
        if aru:
            result2 = fuzzy_search(aru)
            if result2['found']:
                tx(phone, aru)
                _p()
                flow_open_collection(phone, result2['id'], result2['name'], lang)
                return
            tx(phone, aru)
            _p()

        flow_welcome(phone, first_name, lang)
        return

    # ── INTERACTIVE ───────────────────────────────────────────
    if mtype == 'interactive':
        itype = msg['interactive'].get('type')

        # Button reply
        if itype == 'button_reply':
            bid = msg['interactive']['button_reply']['id']
            log.info(f"Button: {bid}")

            if bid == 'MENU':
                flow_action_menu(phone, lang)

            elif bid == 'W_FACE':     flow_face_menu(phone, lang)
            elif bid == 'W_HAND':     flow_hand_menu(phone, lang)
            elif bid == 'W_NECK':     flow_neck_menu(phone, lang)
            elif bid == 'W_LOWER':    flow_lower(phone, lang)
            elif bid == 'F_EARRINGS': flow_face_earrings(phone, lang)
            elif bid == 'F_NOSE':     flow_face_nose(phone, lang)
            elif bid == 'F_HEAD':     flow_face_head(phone, lang)
            elif bid == 'F_HAIR':     flow_face_hair(phone, lang)
            elif bid == 'H_BANGLES':  flow_hand_bangles(phone, lang)
            elif bid == 'H_BRACELETS':flow_hand_bracelets(phone, lang)
            elif bid == 'H_ARMLETS':  flow_hand_armlets(phone, lang)
            elif bid == 'H_RINGS':    flow_hand_rings(phone, lang)
            elif bid == 'S_WATCHES':  flow_watches(phone, lang)
            elif bid == 'S_ACCSS':    flow_studio_acc(phone, lang)

            elif bid == 'ACT_CUSTOMISE':
                flow_custom_start(phone, first_name, phone, status == 'b2b', lang)

            elif bid == 'ACT_CATALOGS':
                flow_catalogs(phone, lang)

            elif bid == 'CONTACT_TEAM':
                tx(phone,
                    "Our team is available Mon–Sat, 10 AM to 7 PM. Someone will reach out shortly."
                    if lang == 'en' else
                    "Hamari team Somvar se Shanivar, 10 AM–7 PM available hai. Koi jald contact karega."
                )

            elif bid == 'UPLOAD_FILE':
                tx(phone,
                    "Please upload your design file or reference image in this chat. "
                    "Our team will review it within 24 hours."
                    if lang == 'en' else
                    "Design file ya reference image is chat mein upload karein. "
                    "Team 24 ghante mein review karegi."
                )

        # List reply
        elif itype == 'list_reply':
            lid = msg['interactive']['list_reply']['id']
            log.info(f"List: {lid}")

            if lid == 'ACT_CATALOGS':
                flow_catalogs(phone, lang)
            elif lid == 'ACT_CUSTOMISE':
                flow_custom_start(phone, first_name, phone, status == 'b2b', lang)
            elif lid == 'ACT_ORDERS':
                tx(phone,
                    f"Please share your Order Reference Number, {first_name} (format: AJS-XXXX-XXXXXXXXXX)."
                    if lang == 'en' else
                    f"Order Reference Number share karein, {first_name} (format: AJS-XXXX-XXXXXXXXXX)."
                )

            elif lid == 'CAT_BABY':   flow_baby(phone, lang)
            elif lid == 'CAT_WOMEN':  flow_women_body(phone, lang)
            elif lid == 'CAT_MEN':    flow_men_menu(phone, lang)
            elif lid == 'CAT_STUDIO': flow_studio_menu(phone, lang)
            elif lid == 'CAT_SACRED': flow_empty_catalog(phone, lang)

            # Men sub-categories (from scroll list)
            elif lid == 'M_RINGS':       flow_men_rings(phone, lang)
            elif lid == 'M_BRACELETS':   flow_men_bracelets(phone, lang)
            elif lid == 'M_CHAINS':      flow_men_chains(phone, lang)
            elif lid == 'M_ACCESSORIES': flow_men_accessories(phone, lang)

            elif lid.startswith('C_'):
                cid   = lid[2:]
                cname = ID_TO_NAME.get(cid, 'Collection')
                flow_open_collection(phone, cid, cname, lang)

        return

    # ── IMAGE ─────────────────────────────────────────────────
    if mtype == 'image':
        image_id = msg.get('image', {}).get('id')
        tx(phone,
            "Analyzing the design, please wait."
            if lang == 'en' else
            "Design analyze ho raha hai, please wait."
        )
        _p(1)
        if image_id:
            url_r = requests.get(
                f"https://graph.facebook.com/v19.0/{image_id}",
                headers={'Authorization': f'Bearer {WA_TOKEN}'}, timeout=10
            )
            if url_r.ok:
                vision = aru_vision(url_r.json().get('url', ''))
                if vision:
                    result = fuzzy_search(vision['query'])
                    if result['found']:
                        tx(phone,
                            "Found a similar collection for this design."
                            if lang == 'en' else "Is design ke liye similar collection mila."
                        )
                        _p()
                        flow_open_collection(phone, result['id'], result['name'], lang)
                        return
        tx(phone,
            "Please describe what you are looking for and I will help you find the perfect piece."
            if lang == 'en' else
            "Batayein aap kya dhundh rahe hain — main perfect piece dhundhne mein madad karungi."
        )
        _p()
        btn1(phone, 'Would you like a custom order?', 'ACT_CUSTOMISE', 'CUSTOMISE JEWELRY')
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
        'status':    'healthy',
        'service':   'A Jewel Studio WhatsApp Bot',
        'assistant': 'Aru',
        'sessions':  len(_sessions),
        'timestamp': datetime.now().isoformat(),
    }), 200

@app.after_request
def security(r):
    r.headers.update({'X-Content-Type-Options': 'nosniff',
                      'X-Frame-Options': 'DENY',
                      'X-XSS-Protection': '1; mode=block'})
    return r

@app.errorhandler(404)
def not_found(_): return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(e):
    log.error(e); return jsonify({'error': 'Server error'}), 500

# ─────────────────────────────────────────────────────────────
# ENTRY
# ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    log.info("A Jewel Studio Bot — Starting on port %s", port)
    app.run(host='0.0.0.0', port=port, debug=False)
