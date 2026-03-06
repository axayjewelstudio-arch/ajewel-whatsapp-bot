# -*- coding: utf-8 -*-
"""
A Jewel Studio — WhatsApp Bot
Flow: Hi -> Welcome + MENU -> Category List -> Sub-collection List -> WhatsApp Catalog (inside WA) -> Razorpay
Deploy: Render.com

Environment Variables:
    WHATSAPP_TOKEN
    WHATSAPP_PHONE_ID
    VERIFY_TOKEN
    WHATSAPP_CATALOG_ID       (Meta Commerce Manager)
    RAZORPAY_KEY_ID
    RAZORPAY_KEY_SECRET
    SHOPIFY_SHOP_DOMAIN
    SHOPIFY_ACCESS_TOKEN
    GOOGLE_SHEET_ID
    GOOGLE_SERVICE_ACCOUNT_KEY
"""

import os
import json
import logging
import razorpay
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import gspread
from google.oauth2.service_account import Credentials

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
WHATSAPP_TOKEN             = os.getenv('WHATSAPP_TOKEN', '')
WHATSAPP_PHONE_ID          = os.getenv('WHATSAPP_PHONE_ID', '')
VERIFY_TOKEN               = os.getenv('VERIFY_TOKEN', 'ajewel2024')
WHATSAPP_CATALOG_ID        = os.getenv('WHATSAPP_CATALOG_ID', '')
RAZORPAY_KEY_ID            = os.getenv('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET        = os.getenv('RAZORPAY_KEY_SECRET', '')
SHOPIFY_STORE              = os.getenv('SHOPIFY_SHOP_DOMAIN', 'a-jewel-studio-3.myshopify.com')
SHOPIFY_ACCESS_TOKEN       = os.getenv('SHOPIFY_ACCESS_TOKEN', '')
GOOGLE_SHEET_ID            = os.getenv('GOOGLE_SHEET_ID', '')
GOOGLE_SERVICE_ACCOUNT_KEY = os.getenv('GOOGLE_SERVICE_ACCOUNT_KEY', '')

WA_API = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_ID}/messages"

# ---------------------------------------------------------------------------
# Catalog — Category -> Sub-collections -> WhatsApp Set ID
# ---------------------------------------------------------------------------
CATALOG = {
    'cat_baby': {
        'label': 'Baby Jewellery',
        'subs': {
            'Baby Anklets Payal':    '26132380466413425',
            'Baby Bangles Kada':     '25812008941803035',
            'Baby Earrings':         '34197166099927645',
            'Baby Hair Accessories': '26930579176543121',
            'Baby Necklace Chain':   '34159752333640697',
            'Baby Rings':            '27130321023234461',
        }
    },
    'cat_women': {
        'label': 'Women Jewellery',
        'subs': {
            'Ear Bahubali':            '27263060009951006',
            'Ear Chandbali':           '26459908080267418',
            'Ear Chuk':                '26001425306208264',
            'Ear Cuff':                '25904630702480491',
            'Ear Drop':                '27085758917680509',
            'Ear Hoops':               '26507559175517690',
            'Ear Jhumka':              '26067705569545995',
            'Ear Kanser':              '24428630293501712',
            'Ear Studs':               '26648112538119124',
            'Ear Sui Dhaga':           '26527646070152559',
            'Head Kanser':             '26924099463860066',
            'Head Maang Tikka':        '34096814326631390',
            'Head Matha Patti':        '25972597769065393',
            'Head Passa':              '25853734394311094',
            'Head Sheesh Phool':       '25884225787909036',
            'Hair Clips':              '25923141554014968',
            'Nose Clip On':            '25956080384032593',
            'Nose Nath':               '26146672631634215',
            'Nose Pin':                '25816769131325224',
            'Nose Septum':             '26137405402565188',
            'Hand Baju Band':          '25741475325553252',
            'Hand Bangle Traditional': '25990285673976585',
            'Hand Bracelet':           '26479540271641962',
            'Hand Bracelet Chain':     '26553938717531086',
            'Hand Bracelet Charm':     '25889526627383303',
            'Hand Bracelet Cuff':      '26095567730084970',
            'Hand Kada':               '26202123256143866',
            'Hand Rings':              '26458893303705648',
            'Hand Rings Engagement':   '26577195808532633',
            'Hand Rings Fashion':      '26627787650158306',
            'Hand Rings Wedding':      '26283285724614486',
            'Lower Kamarband':         '25970100975978085',
            'Lower Payal Anklet':      '26108970985433226',
            'Lower Toe Rings':         '26041413228854859',
            'Neck Choker':             '34380933844854505',
            'Neck Matinee':            '34810362708554746',
            'Neck Princess':           '27036678569255877',
            'Neck Necklace':           '27022573597332099',
            'Neck Pendant':            '25892524293743018',
            'Neck Pendant Locket':     '34949414394649401',
            'Neck Pendant Solitaire':  '26345939121667071',
            'Neck Pendant Statement':  '34061823006795079',
            'Neck Special Sets':       '34181230154825697',
            'Neck Traditional Haar':   '34124391790542901',
        }
    },
    'cat_men': {
        'label': 'Men Jewellery',
        'subs': {
            'Bracelet Beaded':    '26526947026910291',
            'Bracelet Chain':     '26028399416826135',
            'Bracelet Cuff':      '26224048963949143',
            'Bracelet Leather':   '24614722568226121',
            'Brooches':           '27093254823609535',
            'Chain Gold':         '26614026711549117',
            'Chain Rope':         '25364645956543386',
            'Chain Silver':       '35305915439007559',
            'Cufflinks Classic':  '25956694700651645',
            'Cufflinks Designer': '25283486371327046',
            'Kada Modern':        '26028780853472858',
            'Kada Traditional':   '26080348848282889',
            'Pendant Initial':    '26251311201160440',
            'Pendant Religious':  '34138553902457530',
            'Pendant Stone':      '26441867825407906',
            'Rings Band':         '26048808064813747',
            'Rings Engagement':   '26205064579128433',
            'Rings Fashion':      '26353107324312966',
            'Rings Signet':       '26133044123050259',
            'Rings Stone':        '25392189793787605',
            'Rings Wedding':      '35279590828306838',
            'Tie Pins':           '34056958820614334',
        }
    },
    'cat_studio': {
        'label': 'Studio Special',
        'subs': {
            'Belts':          '26176082815414211',
            'Clutches':       '34514139158199452',
            'Keychains':      '26255788447385252',
            'Kids Watches':   '26311558718468909',
            'Luxury Watches': '26667915832816156',
            'Men Watches':    '34176915238618497',
            'Smart Watches':  '25912162851771673',
            'Sunglasses':     '25258040713868720',
            'Women Watches':  '26903528372573194',
        }
    },
    'cat_murti': {
        'label': 'Murti and Arts',
        'subs': {}  # Add set IDs when available
    },
}

# Flat map: set_id -> sub name (for reverse lookup)
SET_NAME_MAP = {}
for _cat_data in CATALOG.values():
    for _name, _sid in _cat_data['subs'].items():
        SET_NAME_MAP[_sid] = _name

# ---------------------------------------------------------------------------
# Google Sheets
# ---------------------------------------------------------------------------
def get_sheets_client():
    try:
        if not GOOGLE_SERVICE_ACCOUNT_KEY:
            return None
        creds = Credentials.from_service_account_info(
            json.loads(GOOGLE_SERVICE_ACCOUNT_KEY),
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        return gspread.authorize(creds)
    except Exception as e:
        logger.error(f"Sheets init error: {e}")
        return None

sheets_client = get_sheets_client()

def check_customer_in_sheets(phone):
    try:
        if not sheets_client or not GOOGLE_SHEET_ID:
            return {'exists': False}
        sheet = sheets_client.open_by_key(GOOGLE_SHEET_ID).worksheet('Registrations')
        phones = sheet.col_values(1)
        for i, p in enumerate(phones, 1):
            if p == phone:
                row = sheet.row_values(i)
                return {
                    'exists':     True,
                    'first_name': row[1] if len(row) > 1 else '',
                    'last_name':  row[2] if len(row) > 2 else ''
                }
        return {'exists': False}
    except Exception as e:
        logger.error(f"Sheets check error: {e}")
        return {'exists': False}

def log_phone_to_sheets(phone):
    try:
        if not sheets_client or not GOOGLE_SHEET_ID:
            return
        sheet = sheets_client.open_by_key(GOOGLE_SHEET_ID).worksheet('Registrations')
        sheet.append_row([phone])
    except Exception as e:
        logger.error(f"Sheets log error: {e}")

# ---------------------------------------------------------------------------
# Shopify
# ---------------------------------------------------------------------------
def check_customer_in_shopify(phone):
    try:
        if not SHOPIFY_ACCESS_TOKEN:
            return {'exists': False}
        url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/customers/search.json"
        r = requests.get(
            url,
            headers={'X-Shopify-Access-Token': SHOPIFY_ACCESS_TOKEN},
            params={'query': f'phone:{phone}'},
            timeout=10
        )
        if r.status_code == 200:
            customers = r.json().get('customers', [])
            if customers:
                c    = customers[0]
                tags = [t.strip() for t in c.get('tags', '').split(',')]
                return {
                    'exists':        True,
                    'first_name':    c.get('first_name', ''),
                    'last_name':     c.get('last_name', ''),
                    'customer_type': 'B2B' if any(t in ['B2B', 'Wholesale'] for t in tags) else 'Retail'
                }
        return {'exists': False}
    except Exception as e:
        logger.error(f"Shopify check error: {e}")
        return {'exists': False}

def detect_customer_status(phone):
    shopify = check_customer_in_shopify(phone)
    if shopify['exists']:
        ct = shopify.get('customer_type', 'Retail')
        return {
            'status':        'returning_b2b' if ct == 'B2B' else 'returning_retail',
            'customer_type': ct,
            'first_name':    shopify.get('first_name', 'Customer'),
            'last_name':     shopify.get('last_name', '')
        }
    sheets = check_customer_in_sheets(phone)
    if sheets['exists']:
        return {
            'status':     'incomplete_registration',
            'first_name': sheets.get('first_name', ''),
            'last_name':  sheets.get('last_name', '')
        }
    log_phone_to_sheets(phone)
    return {'status': 'new'}

# ---------------------------------------------------------------------------
# Razorpay
# ---------------------------------------------------------------------------
def create_razorpay_link(amount_paise, customer_name, phone, order_ref):
    try:
        if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
            return None
        client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        link = client.payment_link.create({
            'amount':           amount_paise,
            'currency':         'INR',
            'accept_partial':   False,
            'description':      f'A Jewel Studio — Order {order_ref}',
            'customer':         {'name': customer_name, 'contact': f'+{phone}'},
            'notify':           {'sms': False, 'email': False},
            'reminder_enable':  False,
            'notes':            {'order_ref': order_ref}
        })
        return link.get('short_url')
    except Exception as e:
        logger.error(f"Razorpay error: {e}")
        return None

# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------
user_sessions = {}

def get_session(phone):
    if phone not in user_sessions:
        user_sessions[phone] = {
            'created_at':    datetime.now(),
            'last_activity': datetime.now(),
            'customer_name': 'Customer',
            'cart_total':    0,
        }
    user_sessions[phone]['last_activity'] = datetime.now()
    return user_sessions[phone]

def update_session(phone, cust_data):
    s  = get_session(phone)
    fn = cust_data.get('first_name', 'Customer')
    ln = cust_data.get('last_name', '')
    s['customer_name'] = f"{fn} {ln}".strip() if ln else fn
    return s

# ---------------------------------------------------------------------------
# WhatsApp — Low-level sender
# ---------------------------------------------------------------------------
def _wa_post(payload):
    try:
        r = requests.post(
            WA_API,
            headers={'Authorization': f'Bearer {WHATSAPP_TOKEN}', 'Content-Type': 'application/json'},
            json=payload,
            timeout=10
        )
        if not r.ok:
            logger.error(f"WA API {r.status_code}: {r.text[:300]}")
        return r.ok
    except Exception as e:
        logger.error(f"WA post error: {e}")
        return False

# ---------------------------------------------------------------------------
# WhatsApp — Message helpers
# ---------------------------------------------------------------------------
def send_text(to, text):
    return _wa_post({
        'messaging_product': 'whatsapp',
        'to':   to,
        'type': 'text',
        'text': {'body': text}
    })


def send_button(to, body_text, btn_id, btn_title, footer=None):
    payload = {
        'messaging_product': 'whatsapp',
        'to':   to,
        'type': 'interactive',
        'interactive': {
            'type': 'button',
            'body': {'text': body_text},
            'action': {
                'buttons': [{'type': 'reply', 'reply': {'id': btn_id, 'title': btn_title}}]
            }
        }
    }
    if footer:
        payload['interactive']['footer'] = {'text': footer}
    return _wa_post(payload)


def send_list(to, header, body, btn_text, sections, footer=None):
    payload = {
        'messaging_product': 'whatsapp',
        'to':   to,
        'type': 'interactive',
        'interactive': {
            'type':   'list',
            'header': {'type': 'text', 'text': header},
            'body':   {'text': body},
            'action': {'button': btn_text, 'sections': sections}
        }
    }
    if footer:
        payload['interactive']['footer'] = {'text': footer}
    return _wa_post(payload)


def send_cta(to, body_text, btn_text, url):
    return _wa_post({
        'messaging_product': 'whatsapp',
        'to':   to,
        'type': 'interactive',
        'interactive': {
            'type': 'cta_url',
            'body': {'text': body_text},
            'action': {
                'name': 'cta_url',
                'parameters': {'display_text': btn_text, 'url': url}
            }
        }
    })


def send_catalog_set(to, set_id, set_name):
    """
    Opens WhatsApp Catalog INSIDE WhatsApp showing only the selected set's products.
    Uses product_list interactive message type.
    Meta Commerce API is called first to get retailer_ids for the set.
    """
    retailer_ids = _fetch_set_products(set_id)

    if not retailer_ids:
        logger.warning(f"No products for set {set_id}. Sending fallback link.")
        send_text(to, f"{set_name}\n\nView this collection: https://wa.me/c/{WHATSAPP_CATALOG_ID}")
        return

    _wa_post({
        'messaging_product': 'whatsapp',
        'to':   to,
        'type': 'interactive',
        'interactive': {
            'type':   'product_list',
            'header': {'type': 'text', 'text': 'A Jewel Studio'},
            'body':   {'text': set_name},
            'footer': {'text': 'Add to cart, then tap Place Order.'},
            'action': {
                'catalog_id': WHATSAPP_CATALOG_ID,
                'sections': [{
                    'title': set_name[:24],
                    'product_items': [
                        {'product_retailer_id': rid} for rid in retailer_ids[:30]
                    ]
                }]
            }
        }
    })


def _fetch_set_products(set_id):
    """Fetch retailer_ids for all products in a catalog set via Meta Commerce API."""
    try:
        url = f"https://graph.facebook.com/v19.0/{set_id}/products"
        r   = requests.get(url, params={
            'fields':       'retailer_id',
            'access_token': WHATSAPP_TOKEN,
            'limit':        30
        }, timeout=10)
        if r.ok:
            return [p['retailer_id'] for p in r.json().get('data', []) if 'retailer_id' in p]
        logger.error(f"Commerce API {r.status_code}: {r.text[:200]}")
    except Exception as e:
        logger.error(f"_fetch_set_products error: {e}")
    return []


def send_payment_link(to, customer_name, phone, total_paise=0):
    order_ref = f"AJS-{phone[-4:]}-{int(datetime.now().timestamp())}"
    rp_url    = create_razorpay_link(total_paise, customer_name, phone, order_ref)

    if rp_url:
        send_cta(
            to,
            f"Order Reference: {order_ref}\n\nTap below to complete your payment securely.",
            'Pay Now',
            rp_url
        )
    else:
        send_text(to, "To complete your order please contact us. We will share the payment link shortly.")

# ---------------------------------------------------------------------------
# Menu Builders
# ---------------------------------------------------------------------------
def send_welcome(to, customer_name):
    send_button(
        to,
        f"Welcome to A Jewel Studio, {customer_name}.\n\nBrowse our collections and place your order from this chat.",
        'OPEN_MENU',
        'MENU',
        footer='A Jewel Studio'
    )


def send_category_list(to):
    rows = [
        {'id': cat_id, 'title': cat_data['label']}
        for cat_id, cat_data in CATALOG.items()
    ]
    send_list(
        to,
        header='A Jewel Studio',
        body='Select a collection.',
        btn_text='View Collections',
        sections=[{'title': 'Collections', 'rows': rows}],
        footer='A Jewel Studio'
    )


def send_subcollection_list(to, cat_id):
    subs      = CATALOG[cat_id]['subs']
    cat_label = CATALOG[cat_id]['label']

    if not subs:
        send_text(to, f"{cat_label} collection is coming soon.")
        return

    all_rows = [
        {'id': f"SET_{set_id}", 'title': name[:24]}
        for name, set_id in subs.items()
    ]
    # Split into sections of max 10 rows (WhatsApp API limit)
    sections = []
    for i in range(0, len(all_rows), 10):
        sections.append({
            'title': cat_label if i == 0 else f"{cat_label} (continued)",
            'rows':  all_rows[i:i + 10]
        })

    send_list(
        to,
        header=cat_label,
        body='Select a set to view products.',
        btn_text='View Sets',
        sections=sections[:10],
        footer='A Jewel Studio'
    )

# ---------------------------------------------------------------------------
# Core Message Handler
# ---------------------------------------------------------------------------
def handle_message(phone, msg):
    msg_type  = msg.get('type')
    cust_data = detect_customer_status(phone)
    session   = update_session(phone, cust_data)
    cust_name = session['customer_name']
    join_url  = f"https://{SHOPIFY_STORE}/pages/join-us?wa={phone}"

    # Plain text
    if msg_type == 'text':
        status = cust_data['status']
        if status == 'new':
            send_cta(phone,
                     "Welcome to A Jewel Studio.\n\nRegister to access our full collection.",
                     "Register Now", join_url)
        elif status == 'incomplete_registration':
            send_cta(phone,
                     "Please complete your registration to continue.",
                     "Complete Registration", join_url)
        else:
            send_welcome(phone, cust_name)
        return

    # Interactive
    if msg_type == 'interactive':
        itype = msg.get('interactive', {}).get('type')

        if itype == 'button_reply':
            btn_id = msg['interactive']['button_reply']['id']
            if btn_id == 'OPEN_MENU':
                send_category_list(phone)
            elif btn_id == 'PAY_NOW':
                send_payment_link(phone, cust_name, phone, session.get('cart_total', 0))

        elif itype == 'list_reply':
            row_id = msg['interactive']['list_reply']['id']
            if row_id in CATALOG:
                send_subcollection_list(phone, row_id)
            elif row_id.startswith('SET_'):
                set_id   = row_id.replace('SET_', '')
                set_name = SET_NAME_MAP.get(set_id, 'Collection')
                send_catalog_set(phone, set_id, set_name)
        return

    # Order placed from catalog cart
    if msg_type == 'order':
        items  = msg.get('order', {}).get('product_items', [])
        total  = sum(int(float(i.get('item_price', 0)) * 100) * i.get('quantity', 1) for i in items)
        session['cart_total'] = total
        send_payment_link(phone, cust_name, phone, total)
        return

# ---------------------------------------------------------------------------
# Webhook Routes
# ---------------------------------------------------------------------------
@app.route('/webhook', methods=['GET'])
def verify():
    mode      = request.args.get('hub.mode')
    token     = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if mode == 'subscribe' and token == VERIFY_TOKEN:
        logger.info("Webhook verified.")
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
        for msg in msgs:
            phone = msg.get('from')
            if phone:
                handle_message(phone, msg)

    except Exception as e:
        logger.error(f"Webhook error: {e}")

    return jsonify({'status': 'ok'}), 200


@app.route('/', methods=['GET'])
@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': 'A Jewel Studio WhatsApp Bot'}), 200


@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options']        = 'DENY'
    return response

# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    logger.info("A Jewel Studio Bot starting...")
    app.run(host='0.0.0.0', port=port, debug=False)
