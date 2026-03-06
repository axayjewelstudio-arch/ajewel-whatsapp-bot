# -*- coding: utf-8 -*-
"""
A Jewel Studio WhatsApp Bot - Collection Based Catalog
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Environment
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN')
WHATSAPP_PHONE_ID = os.getenv('WHATSAPP_PHONE_ID')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN', 'ajewel_verify_token_2024')
SHOPIFY_STORE = os.getenv('SHOPIFY_STORE', 'a-jewel-studio-3.myshopify.com')
SHOPIFY_ACCESS_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN')
GOOGLE_SHEET_ID = os.getenv('GOOGLE_SHEET_ID')
GOOGLE_SERVICE_ACCOUNT_KEY = os.getenv('GOOGLE_SERVICE_ACCOUNT_KEY')
JOIN_US_URL = f"https://{SHOPIFY_STORE}/pages/join-us"

# Google Sheets
def get_sheets_client():
    try:
        if not GOOGLE_SERVICE_ACCOUNT_KEY:
            return None
        creds = Credentials.from_service_account_info(json.loads(GOOGLE_SERVICE_ACCOUNT_KEY), scopes=['https://www.googleapis.com/auth/spreadsheets'])
        return gspread.authorize(creds)
    except:
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
                return {'exists': True, 'first_name': row[1] if len(row) > 1 else '', 'last_name': row[2] if len(row) > 2 else ''}
        return {'exists': False}
    except:
        return {'exists': False}

def log_phone_to_sheets(phone):
    try:
        if not sheets_client or not GOOGLE_SHEET_ID:
            return False
        sheet = sheets_client.open_by_key(GOOGLE_SHEET_ID).worksheet('Registrations')
        sheet.append_row([phone])
        return True
    except:
        return False

# Shopify
def check_customer_in_shopify(phone):
    try:
        if not SHOPIFY_ACCESS_TOKEN:
            return {'exists': False}
        url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/customers/search.json"
        r = requests.get(url, headers={'X-Shopify-Access-Token': SHOPIFY_ACCESS_TOKEN}, params={'query': f'phone:{phone}'}, timeout=10)
        if r.status_code == 200:
            customers = r.json().get('customers', [])
            if customers:
                c = customers[0]
                tags = [t.strip() for t in c.get('tags', '').split(',')]
                return {'exists': True, 'first_name': c.get('first_name', ''), 'last_name': c.get('last_name', ''), 'customer_type': 'B2B' if any(t in ['B2B', 'Wholesale'] for t in tags) else 'Retail'}
        return {'exists': False}
    except:
        return {'exists': False}

def detect_customer_status(phone):
    shopify = check_customer_in_shopify(phone)
    if shopify['exists']:
        ct = shopify.get('customer_type', 'Retail')
        return {'status': 'returning_b2b' if ct == 'B2B' else 'returning_retail', 'customer_type': ct, 'first_name': shopify.get('first_name', 'Customer'), 'last_name': shopify.get('last_name', '')}
    sheets = check_customer_in_sheets(phone)
    if sheets['exists']:
        return {'status': 'incomplete_registration', 'first_name': sheets.get('first_name', ''), 'last_name': sheets.get('last_name', '')}
    log_phone_to_sheets(phone)
    return {'status': 'new'}

# Session
user_sessions = {}

def get_session(phone):
    if phone not in user_sessions:
        user_sessions[phone] = {'created_at': datetime.now(), 'last_activity': datetime.now(), 'customer_name': 'Customer'}
    else:
        user_sessions[phone]['last_activity'] = datetime.now()
    return user_sessions[phone]

def update_session(phone, data):
    s = get_session(phone)
    fn = data.get('first_name', 'Customer')
    ln = data.get('last_name', '')
    s['customer_name'] = f"{fn} {ln}" if ln else fn
    return s

# WhatsApp - Text
def send_text(to, text):
    try:
        url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
        r = requests.post(url, headers={'Authorization': f'Bearer {WHATSAPP_TOKEN}', 'Content-Type': 'application/json'},
                         json={'messaging_product': 'whatsapp', 'to': to, 'type': 'text', 'text': {'body': text}}, timeout=10)
        return r.status_code == 200
    except:
        return False

# WhatsApp - Button
def send_button(to, text, btn_id, btn_title):
    try:
        url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
        r = requests.post(url, headers={'Authorization': f'Bearer {WHATSAPP_TOKEN}', 'Content-Type': 'application/json'},
                         json={'messaging_product': 'whatsapp', 'to': to, 'type': 'interactive',
                              'interactive': {'type': 'button', 'body': {'text': text}, 'action': {'buttons': [{'type': 'reply', 'reply': {'id': btn_id, 'title': btn_title}}]}}}, timeout=10)
        return r.status_code == 200
    except:
        return False

# WhatsApp - List
def send_list(to, header, body, btn_text, sections):
    try:
        url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
        r = requests.post(url, headers={'Authorization': f'Bearer {WHATSAPP_TOKEN}', 'Content-Type': 'application/json'},
                         json={'messaging_product': 'whatsapp', 'to': to, 'type': 'interactive',
                              'interactive': {'type': 'list', 'header': {'type': 'text', 'text': header}, 'body': {'text': body},
                                            'action': {'button': btn_text, 'sections': sections}}}, timeout=10)
        return r.status_code == 200
    except:
        return False

# WhatsApp - CTA
def send_cta(to, text, btn_text, url_link):
    try:
        url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
        r = requests.post(url, headers={'Authorization': f'Bearer {WHATSAPP_TOKEN}', 'Content-Type': 'application/json'},
                         json={'messaging_product': 'whatsapp', 'to': to, 'type': 'interactive',
                              'interactive': {'type': 'cta_url', 'body': {'text': text}, 'action': {'name': 'cta_url', 'parameters': {'display_text': btn_text, 'url': url_link}}}}, timeout=10)
        return r.status_code == 200
    except:
        return False

# WhatsApp - Open Catalog Collection (FINAL FIX)
def open_catalog_collection(to, collection_id, collection_name):
    """Open WhatsApp catalog with specific collection"""
    try:
        # Direct WhatsApp catalog link
        catalog_url = f"https://wa.me/c/{collection_id}"
        send_text(to, f"{collection_name}\n\n{catalog_url}")
        return True
    except Exception as e:
        logger.error(f"Catalog error: {str(e)}")
        return False

# Main Categories
MAIN_CATEGORIES = [
    {'id': 'cat_baby', 'title': 'Baby Jewellery'},
    {'id': 'cat_women', 'title': 'Women Jewellery'},
    {'id': 'cat_men', 'title': 'Men Jewellery'},
    {'id': 'cat_studio', 'title': 'Studio Collection'},
    {'id': 'cat_divine', 'title': 'Divine Blessings'}
]

# Sub Categories with ALL Collection IDs
SUB_CATEGORIES = {
    'cat_baby': [
        {'id': 'baby_hair', 'title': 'Hair Accessories', 'collection_id': '26930579176543121'},
        {'id': 'baby_earrings', 'title': 'Earrings', 'collection_id': '34197166099927645'},
        {'id': 'baby_chain', 'title': 'Necklace Chains', 'collection_id': '34159752333640697'},
        {'id': 'baby_rings', 'title': 'Rings', 'collection_id': '27130321023234461'},
        {'id': 'baby_payal', 'title': 'Anklets', 'collection_id': '26132380466413425'},
        {'id': 'baby_bangles', 'title': 'Bangles', 'collection_id': '25812008941803035'}
    ],
    'cat_women': [
        {'id': 'women_face', 'title': 'Face Jewellery', 'sub': True},
        {'id': 'women_hand', 'title': 'Hand Jewellery', 'sub': True},
        {'id': 'women_neck', 'title': 'Neck Jewellery', 'sub': True},
        {'id': 'women_lower', 'title': 'Lower Body', 'sub': True}
    ],
    'cat_men': [
        {'id': 'men_rings', 'title': 'Rings', 'sub': True},
        {'id': 'men_bracelets', 'title': 'Bracelets', 'sub': True},
        {'id': 'men_chains', 'title': 'Chains', 'sub': True},
        {'id': 'men_accessories', 'title': 'Accessories', 'sub': True}
    ],
    'cat_studio': [
        {'id': 'studio_watches', 'title': 'Watches', 'sub': True},
        {'id': 'studio_accessories', 'title': 'Accessories', 'sub': True}
    ]
}

# Women Face Sub-categories
WOMEN_FACE_SUBS = [
    {'id': 'face_earrings', 'title': 'Earrings', 'sub': True},
    {'id': 'face_nose', 'title': 'Nose Jewellery', 'sub': True},
    {'id': 'face_head', 'title': 'Head Jewellery', 'sub': True},
    {'id': 'face_hair', 'title': 'Hair Accessories', 'collection_id': '25923141554014968'}
]

# Women Face Earrings
FACE_EARRINGS = [
    {'id': 'face_studs', 'title': 'Diamond Studs', 'collection_id': '26648112538119124'},
    {'id': 'face_jhumka', 'title': 'Traditional Jhumka', 'collection_id': '26067705569545995'},
    {'id': 'face_chandbali', 'title': 'Chandbali', 'collection_id': '26459908080267418'},
    {'id': 'face_hoops', 'title': 'Classic Hoops', 'collection_id': '26507559175517690'},
    {'id': 'face_cuff', 'title': 'Ear Cuffs', 'collection_id': '25904630702480491'},
    {'id': 'face_kanser', 'title': 'Bridal Kanser', 'collection_id': '24428630293501712'},
    {'id': 'face_bahubali', 'title': 'Bahubali', 'collection_id': '27263060009951006'},
    {'id': 'face_drop', 'title': 'Drop Earrings', 'collection_id': '27085758917680509'},
    {'id': 'face_sui_dhaga', 'title': 'Sui Dhaga', 'collection_id': '26527646070152559'},
    {'id': 'face_chuk', 'title': 'Vintage Chuk', 'collection_id': '26001425306208264'}
]

# Women Face Nose
FACE_NOSE = [
    {'id': 'face_nath', 'title': 'Bridal Nath', 'collection_id': '26146672631634215'},
    {'id': 'face_nose_pin', 'title': 'Nose Pins', 'collection_id': '25816769131325224'},
    {'id': 'face_septum', 'title': 'Septum Rings', 'collection_id': '26137405402565188'},
    {'id': 'face_clip_on', 'title': 'Clip-On Rings', 'collection_id': '25956080384032593'}
]

# Women Face Head
FACE_HEAD = [
    {'id': 'face_maang_tikka', 'title': 'Maang Tikka', 'collection_id': '34096814326631390'},
    {'id': 'face_matha_patti', 'title': 'Matha Patti', 'collection_id': '25972597769065393'},
    {'id': 'face_passa', 'title': 'Passa', 'collection_id': '25853734394311094'},
    {'id': 'face_head_kanser', 'title': 'Head Kanser', 'collection_id': '26924099463860066'},
    {'id': 'face_sheesh_phool', 'title': 'Sheesh Phool', 'collection_id': '25884225787909036'}
]

# Women Hand Sub-categories
WOMEN_HAND_SUBS = [
    {'id': 'hand_bangles_kada', 'title': 'Bangles & Kada', 'sub': True},
    {'id': 'hand_bracelets', 'title': 'Bracelets', 'sub': True},
    {'id': 'hand_armlet', 'title': 'Armlet', 'collection_id': '25741475325553252'},
    {'id': 'hand_rings', 'title': 'Rings', 'sub': True}
]

# Hand Bangles & Kada
HAND_BANGLES_KADA = [
    {'id': 'hand_bangles', 'title': 'Traditional Bangles', 'collection_id': '25990285673976585'},
    {'id': 'hand_kada', 'title': 'Designer Kada', 'collection_id': '26202123256143866'}
]

# Hand Bracelets
HAND_BRACELETS = [
    {'id': 'hand_bracelet', 'title': 'Bracelets', 'collection_id': '26479540271641962'},
    {'id': 'hand_bracelet_chain', 'title': 'Chain Bracelets', 'collection_id': '26553938717531086'},
    {'id': 'hand_bracelet_charm', 'title': 'Charm Bracelets', 'collection_id': '25889526627383303'},
    {'id': 'hand_bracelet_cuff', 'title': 'Cuff Bracelets', 'collection_id': '26095567730084970'}
]

# Hand Rings
HAND_RINGS = [
    {'id': 'hand_rings_designer', 'title': 'Designer Rings', 'collection_id': '26458893303705648'},
    {'id': 'hand_rings_engagement', 'title': 'Engagement Rings', 'collection_id': '26577195808532633'},
    {'id': 'hand_rings_wedding', 'title': 'Wedding Bands', 'collection_id': '26283285724614486'},
    {'id': 'hand_rings_fashion', 'title': 'Fashion Rings', 'collection_id': '26627787650158306'}
]

# Women Neck Sub-categories
WOMEN_NECK_SUBS = [
    {'id': 'neck_necklaces', 'title': 'Necklaces', 'sub': True},
    {'id': 'neck_pendants', 'title': 'Pendants', 'sub': True},
    {'id': 'neck_sets', 'title': 'Bridal Sets', 'collection_id': '34181230154825697'}
]

# Neck Necklaces
NECK_NECKLACES = [
    {'id': 'neck_haar', 'title': 'Traditional Haar', 'collection_id': '34124391790542901'},
    {'id': 'neck_choker', 'title': 'Modern Chokers', 'collection_id': '34380933844854505'},
    {'id': 'neck_princess', 'title': 'Princess Necklaces', 'collection_id': '27036678569255877'},
    {'id': 'neck_matinee', 'title': 'Matinee Necklaces', 'collection_id': '34810362708554746'}
]

# Neck Pendants
NECK_PENDANTS = [
    {'id': 'neck_solitaire', 'title': 'Solitaire Pendants', 'collection_id': '26345939121667071'},
    {'id': 'neck_locket', 'title': 'Locket Pendants', 'collection_id': '34949414394649401'},
    {'id': 'neck_statement', 'title': 'Statement Pendants', 'collection_id': '34061823006795079'}
]

# Women Lower
WOMEN_LOWER = [
    {'id': 'lower_kamarband', 'title': 'Kamarband', 'collection_id': '25970100975978085'},
    {'id': 'lower_payal', 'title': 'Payal Anklets', 'collection_id': '26108970985433226'},
    {'id': 'lower_toe_rings', 'title': 'Toe Rings', 'collection_id': '26041413228854859'}
]

# Men Rings Sub
MEN_RINGS = [
    {'id': 'men_rings_wedding', 'title': 'Wedding Bands', 'collection_id': '35279590828306838'},
    {'id': 'men_rings_engagement', 'title': 'Engagement Rings', 'collection_id': '26205064579128433'},
    {'id': 'men_rings_signet', 'title': 'Signet Rings', 'collection_id': '26133044123050259'},
    {'id': 'men_rings_fashion', 'title': 'Fashion Rings', 'collection_id': '26353107324312966'},
    {'id': 'men_rings_band', 'title': 'Classic Bands', 'collection_id': '26048808064813747'},
    {'id': 'men_rings_stone', 'title': 'Gemstone Rings', 'collection_id': '25392189793787605'}
]

# Men Bracelets
MEN_BRACELETS = [
    {'id': 'men_bracelet_chain', 'title': 'Chain Bracelets', 'collection_id': '26028399416826135'},
    {'id': 'men_bracelet_leather', 'title': 'Leather Bracelets', 'collection_id': '24614722568226121'},
    {'id': 'men_bracelet_beaded', 'title': 'Beaded Bracelets', 'collection_id': '26526947026910291'},
    {'id': 'men_bracelet_cuff', 'title': 'Cuff Bracelets', 'collection_id': '26224048963949143'}
]

# Men Chains
MEN_CHAINS = [
    {'id': 'men_chain_gold', 'title': 'Gold Chains', 'collection_id': '26614026711549117'},
    {'id': 'men_chain_silver', 'title': 'Silver Chains', 'collection_id': '35305915439007559'},
    {'id': 'men_chain_rope', 'title': 'Rope Chains', 'collection_id': '25364645956543386'}
]

# Men Accessories
MEN_ACCESSORIES = [
    {'id': 'men_cufflinks_classic', 'title': 'Classic Cufflinks', 'collection_id': '25956694700651645'},
    {'id': 'men_cufflinks_designer', 'title': 'Designer Cufflinks', 'collection_id': '25283486371327046'},
    {'id': 'men_tie_pins', 'title': 'Tie Pins', 'collection_id': '34056958820614334'},
    {'id': 'men_brooches', 'title': 'Brooches', 'collection_id': '27093254823609535'}
]

# Studio Watches
STUDIO_WATCHES = [
    {'id': 'watches_men', 'title': 'Men Timepieces', 'collection_id': '34176915238618497'},
    {'id': 'watches_women', 'title': 'Women Timepieces', 'collection_id': '26903528372573194'},
    {'id': 'watches_kids', 'title': 'Kids Timepieces', 'collection_id': '26311558718468909'},
    {'id': 'watches_smart', 'title': 'Smart Watches', 'collection_id': '25912162851771673'},
    {'id': 'watches_luxury', 'title': 'Luxury Timepieces', 'collection_id': '26667915832816156'}
]

# Studio Accessories
STUDIO_ACCESSORIES = [
    {'id': 'keychains', 'title': 'Premium Keychains', 'collection_id': '26255788447385252'},
    {'id': 'clutches', 'title': 'Evening Clutches', 'collection_id': '34514139158199452'},
    {'id': 'sunglasses', 'title': 'Sunglasses', 'collection_id': '25258040713868720'},
    {'id': 'belts', 'title': 'Designer Belts', 'collection_id': '26176082815414211'}
]

# Helper function to get sub-list
def get_sub_list(list_id):
    """Get appropriate sub-list based on ID"""
    if list_id == 'women_face':
        return WOMEN_FACE_SUBS
    elif list_id == 'face_earrings':
        return FACE_EARRINGS
    elif list_id == 'face_nose':
        return FACE_NOSE
    elif list_id == 'face_head':
        return FACE_HEAD
    elif list_id == 'women_hand':
        return WOMEN_HAND_SUBS
    elif list_id == 'hand_bangles_kada':
        return HAND_BANGLES_KADA
    elif list_id == 'hand_bracelets':
        return HAND_BRACELETS
    elif list_id == 'hand_rings':
        return HAND_RINGS
    elif list_id == 'women_neck':
        return WOMEN_NECK_SUBS
    elif list_id == 'neck_necklaces':
        return NECK_NECKLACES
    elif list_id == 'neck_pendants':
        return NECK_PENDANTS
    elif list_id == 'women_lower':
        return WOMEN_LOWER
    elif list_id == 'men_rings':
        return MEN_RINGS
    elif list_id == 'men_bracelets':
        return MEN_BRACELETS
    elif list_id == 'men_chains':
        return MEN_CHAINS
    elif list_id == 'men_accessories':
        return MEN_ACCESSORIES
    elif list_id == 'studio_watches':
        return STUDIO_WATCHES
    elif list_id == 'studio_accessories':
        return STUDIO_ACCESSORIES
    return None

# Webhook Verification
@app.route('/webhook', methods=['GET'])
def verify():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if mode == 'subscribe' and token == VERIFY_TOKEN:
        return challenge, 200
    return 'Forbidden', 403

# Webhook Handler
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        if not data or data.get('object') != 'whatsapp_business_account':
            return jsonify({'status': 'ok'}), 200
        
        msgs = data.get('entry', [{}])[0].get('changes', [{}])[0].get('value', {}).get('messages', [])
        if not msgs:
            return jsonify({'status': 'ok'}), 200
        
        msg = msgs[0]
        from_num = msg.get('from')
        msg_type = msg.get('type')
        
        # Detect customer
        cust_data = detect_customer_status(from_num)
        session = update_session(from_num, cust_data)
        
        # Handle text
        if msg_type == 'text':
            text = msg.get('text', {}).get('body', '').strip()
            
            if cust_data['status'] == 'new':
                send_cta(from_num, "Welcome to *A Jewel Studio*.\n\nTap Join Us to explore our collections.", "Join Us", f"{JOIN_US_URL}?wa={from_num}")
            elif cust_data['status'] == 'incomplete_registration':
                send_cta(from_num, "Hello.\n\nComplete your registration to unlock our full collection.", "Complete Now", f"{JOIN_US_URL}?wa={from_num}")
            else:
                send_button(from_num, f"Welcome back, *{session['customer_name']}*.\n\nHow can I assist you?", 'menu', 'Menu')
        
        # Handle interactive
        elif msg_type == 'interactive':
            interactive = msg.get('interactive', {})
            
            # Button click
            if interactive.get('type') == 'button_reply':
                btn_id = interactive.get('button_reply', {}).get('id', '')
                
                if btn_id == 'menu':
                    sections = [{'title': 'Categories', 'rows': [{'id': cat['id'], 'title': cat['title']} for cat in MAIN_CATEGORIES]}]
                    send_list(from_num, 'Main Menu', 'Please select a category', 'Select Category', sections)
            
            # List selection
            elif interactive.get('type') == 'list_reply':
                list_id = interactive.get('list_reply', {}).get('id', '')
                
                # Check if main category
                if list_id in [c['id'] for c in MAIN_CATEGORIES]:
                    if list_id in SUB_CATEGORIES:
                        sections = [{'title': 'Sub Categories', 'rows': [{'id': sub['id'], 'title': sub['title']} for sub in SUB_CATEGORIES[list_id]]}]
                        send_list(from_num, 'Select Collection', 'Choose a sub-category', 'Select', sections)
                
                # Check if has further sub-categories
                else:
                    sub_list = get_sub_list(list_id)
                    if sub_list:
                        sections = [{'title': 'Collections', 'rows': [{'id': item['id'], 'title': item['title']} for item in sub_list]}]
                        send_list(from_num, 'Select Collection', 'Choose a collection', 'Select', sections)
                    else:
                        # Find and open collection
                        all_collections = (SUB_CATEGORIES.get('cat_baby', []) + FACE_EARRINGS + FACE_NOSE + FACE_HEAD + 
                                         HAND_BANGLES_KADA + HAND_BRACELETS + HAND_RINGS + NECK_NECKLACES + NECK_PENDANTS + 
                                         WOMEN_LOWER + MEN_RINGS + MEN_BRACELETS + MEN_CHAINS + MEN_ACCESSORIES + 
                                         STUDIO_WATCHES + STUDIO_ACCESSORIES + WOMEN_FACE_SUBS + WOMEN_HAND_SUBS + WOMEN_NECK_SUBS)
                        
                        for item in all_collections:
                            if item['id'] == list_id and 'collection_id' in item:
                                open_catalog_collection(from_num, item['collection_id'], item['title'])
                                break
        
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify({'status': 'error'}), 500

# Health
@app.route('/', methods=['GET'])
@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': 'A Jewel Studio WhatsApp Bot - 82 Collections'}), 200

# Security
@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    return response

# Main
if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    logger.info("A Jewel Studio WhatsApp Bot - 82 Collections")
    app.run(host='0.0.0.0', port=port, debug=False)
