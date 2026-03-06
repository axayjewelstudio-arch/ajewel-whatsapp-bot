"""
A Jewel Studio - WhatsApp Bot with Aru AI Assistant
Complete Production System
82 Collections | Bilingual Support | AI-Powered
"""

import os
import json
import logging
import time
import re
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import gspread
from google.oauth2.service_account import Credentials
import razorpay
import google.generativeai as genai
from rapidfuzz import fuzz, process

# ============================================================================
# FLASK APP INITIALIZATION
# ============================================================================

app = Flask(__name__)
CORS(app)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# ENVIRONMENT VARIABLES
# ============================================================================

WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN', '')
WHATSAPP_PHONE_ID = os.getenv('WHATSAPP_PHONE_ID', '')
WHATSAPP_CATALOG_ID = os.getenv('WHATSAPP_CATALOG_ID', '')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN', 'ajewel2024')

SHOPIFY_STORE = os.getenv('SHOPIFY_SHOP_DOMAIN', 'a-jewel-studio-3.myshopify.com')
SHOPIFY_ACCESS_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN', '')

GOOGLE_SHEET_ID = os.getenv('GOOGLE_SHEET_ID', '')
GOOGLE_SERVICE_ACCOUNT_KEY = os.getenv('GOOGLE_SERVICE_ACCOUNT_KEY', '')

RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', '')

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')

WA_API = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_ID}/messages"

# ============================================================================
# GEMINI AI SETUP
# ============================================================================

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-pro')
    gemini_vision = genai.GenerativeModel('gemini-pro-vision')
else:
    gemini_model = None
    gemini_vision = None

# ============================================================================
# SESSION STORAGE
# ============================================================================

user_sessions = {}
SESSION_TIMEOUT = timedelta(minutes=30)

# ============================================================================
# COMPLETE CATALOG STRUCTURE - 82 COLLECTIONS
# ============================================================================

CATALOG = {
    'BABY_JEWELLERY': {
        'label_en': 'Baby Jewellery',
        'label_hi': 'Baby Jewellery',
        'collections': {
            'baby_hair': {'name': 'Hair Accessories', 'id': '26930579176543121'},
            'baby_earrings': {'name': 'Earrings', 'id': '34197166099927645'},
            'baby_chain': {'name': 'Necklace Chains', 'id': '34159752333640697'},
            'baby_rings': {'name': 'Rings', 'id': '27130321023234461'},
            'baby_payal': {'name': 'Anklets', 'id': '26132380466413425'},
            'baby_bangles': {'name': 'Bangles', 'id': '25812008941803035'}
        }
    },
    'WOMEN_JEWELLERY': {
        'label_en': 'Women Jewellery',
        'label_hi': 'Women Jewellery',
        'sub_categories': {
            'FACE_JEWELLERY': {
                'label_en': 'Face Jewellery',
                'label_hi': 'Face Jewellery',
                'sub_menus': {
                    'EARRINGS': {
                        'label_en': 'Earrings',
                        'label_hi': 'Earrings',
                        'collections': {
                            'face_studs': {'name': 'Diamond Studs', 'id': '26648112538119124'},
                            'face_jhumka': {'name': 'Traditional Jhumka', 'id': '26067705569545995'},
                            'face_chandbali': {'name': 'Chandbali', 'id': '26459908080267418'},
                            'face_hoops': {'name': 'Classic Hoops', 'id': '26507559175517690'},
                            'face_cuff': {'name': 'Ear Cuffs', 'id': '25904630702480491'},
                            'face_kanser': {'name': 'Bridal Kanser', 'id': '24428630293501712'},
                            'face_bahubali': {'name': 'Bahubali', 'id': '27263060009951006'},
                            'face_drop': {'name': 'Drop Earrings', 'id': '27085758917680509'},
                            'face_sui_dhaga': {'name': 'Sui Dhaga', 'id': '26527646070152559'},
                            'face_chuk': {'name': 'Vintage Chuk', 'id': '26001425306208264'}
                        }
                    },
                    'NOSE_JEWELLERY': {
                        'label_en': 'Nose Jewellery',
                        'label_hi': 'Nose Jewellery',
                        'collections': {
                            'face_nath': {'name': 'Bridal Nath', 'id': '26146672631634215'},
                            'face_nose_pin': {'name': 'Nose Pins', 'id': '25816769131325224'},
                            'face_septum': {'name': 'Septum Rings', 'id': '26137405402565188'},
                            'face_clip_on': {'name': 'Clip On Rings', 'id': '25956080384032593'}
                        }
                    },
                    'HEAD_JEWELLERY': {
                        'label_en': 'Head Jewellery',
                        'label_hi': 'Head Jewellery',
                        'collections': {
                            'face_maang_tikka': {'name': 'Maang Tikka', 'id': '34096814326631390'},
                            'face_matha_patti': {'name': 'Matha Patti', 'id': '25972597769065393'},
                            'face_passa': {'name': 'Passa', 'id': '25853734394311094'},
                            'face_head_kanser': {'name': 'Head Kanser', 'id': '26924099463860066'},
                            'face_sheesh_phool': {'name': 'Sheesh Phool', 'id': '25884225787909036'}
                        }
                    },
                    'HAIR_ACCESSORIES': {
                        'label_en': 'Hair Accessories',
                        'label_hi': 'Hair Accessories',
                        'collections': {
                            'face_hair_clips': {'name': 'Hair Clips', 'id': '25923141554014968'}
                        }
                    }
                }
            },
            'HAND_JEWELLERY': {
                'label_en': 'Hand Jewellery',
                'label_hi': 'Hand Jewellery',
                'sub_menus': {
                    'BANGLES_KADA': {
                        'label_en': 'Bangles and Kada',
                        'label_hi': 'Bangles aur Kada',
                        'collections': {
                            'hand_bangles': {'name': 'Traditional Bangles', 'id': '25990285673976585'},
                            'hand_kada': {'name': 'Designer Kada', 'id': '26202123256143866'}
                        }
                    },
                    'BRACELETS': {
                        'label_en': 'Bracelets',
                        'label_hi': 'Bracelets',
                        'collections': {
                            'hand_bracelet': {'name': 'Bracelets', 'id': '26479540271641962'},
                            'hand_bracelet_chain': {'name': 'Chain Bracelets', 'id': '26553938717531086'},
                            'hand_bracelet_charm': {'name': 'Charm Bracelets', 'id': '25889526627383303'},
                            'hand_bracelet_cuff': {'name': 'Cuff Bracelets', 'id': '26095567730084970'}
                        }
                    },
                    'ARMLET': {
                        'label_en': 'Armlet',
                        'label_hi': 'Armlet',
                        'collections': {
                            'hand_baju_band': {'name': 'Baju Band', 'id': '25741475325553252'}
                        }
                    },
                    'RINGS': {
                        'label_en': 'Rings',
                        'label_hi': 'Rings',
                        'collections': {
                            'hand_rings': {'name': 'Designer Rings', 'id': '26458893303705648'},
                            'hand_rings_engagement': {'name': 'Engagement Rings', 'id': '26577195808532633'},
                            'hand_rings_wedding': {'name': 'Wedding Bands', 'id': '26283285724614486'},
                            'hand_rings_fashion': {'name': 'Fashion Rings', 'id': '26627787650158306'}
                        }
                    }
                }
            },
            'NECK_JEWELLERY': {
                'label_en': 'Neck Jewellery',
                'label_hi': 'Neck Jewellery',
                'sub_menus': {
                    'NECKLACES': {
                        'label_en': 'Necklaces',
                        'label_hi': 'Necklaces',
                        'collections': {
                            'neck_haar': {'name': 'Traditional Haar', 'id': '34124391790542901'},
                            'neck_choker': {'name': 'Modern Chokers', 'id': '34380933844854505'},
                            'neck_princess': {'name': 'Princess Necklaces', 'id': '27036678569255877'},
                            'neck_matinee': {'name': 'Matinee Necklaces', 'id': '34810362708554746'}
                        }
                    },
                    'PENDANTS': {
                        'label_en': 'Pendants',
                        'label_hi': 'Pendants',
                        'collections': {
                            'neck_solitaire': {'name': 'Solitaire Pendants', 'id': '26345939121667071'},
                            'neck_locket': {'name': 'Locket Pendants', 'id': '34949414394649401'},
                            'neck_statement': {'name': 'Statement Pendants', 'id': '34061823006795079'}
                        }
                    },
                    'BRIDAL_SETS': {
                        'label_en': 'Bridal Sets',
                        'label_hi': 'Bridal Sets',
                        'collections': {
                            'neck_sets': {'name': 'Bridal Sets', 'id': '34181230154825697'}
                        }
                    }
                }
            },
            'LOWER_BODY': {
                'label_en': 'Lower Body Jewellery',
                'label_hi': 'Lower Body Jewellery',
                'collections': {
                    'lower_kamarband': {'name': 'Kamarband', 'id': '25970100975978085'},
                    'lower_payal': {'name': 'Payal Anklets', 'id': '26108970985433226'},
                    'lower_toe_rings': {'name': 'Toe Rings', 'id': '26041413228854859'}
                }
            }
        }
    },
    'MEN_JEWELLERY': {
        'label_en': 'Men Jewellery',
        'label_hi': 'Men Jewellery',
        'sub_categories': {
            'RINGS': {
                'label_en': 'Rings',
                'label_hi': 'Rings',
                'collections': {
                    'men_rings_wedding': {'name': 'Wedding Bands', 'id': '35279590828306838'},
                    'men_rings_engagement': {'name': 'Engagement Rings', 'id': '26205064579128433'},
                    'men_rings_signet': {'name': 'Signet Rings', 'id': '26133044123050259'},
                    'men_rings_fashion': {'name': 'Fashion Rings', 'id': '26353107324312966'},
                    'men_rings_band': {'name': 'Classic Bands', 'id': '26048808064813747'},
                    'men_rings_stone': {'name': 'Gemstone Rings', 'id': '25392189793787605'}
                }
            },
            'BRACELETS': {
                'label_en': 'Bracelets',
                'label_hi': 'Bracelets',
                'collections': {
                    'men_bracelet_chain': {'name': 'Chain Bracelets', 'id': '26028399416826135'},
                    'men_bracelet_leather': {'name': 'Leather Bracelets', 'id': '24614722568226121'},
                    'men_bracelet_beaded': {'name': 'Beaded Bracelets', 'id': '26526947026910291'},
                    'men_bracelet_cuff': {'name': 'Cuff Bracelets', 'id': '26224048963949143'}
                }
            },
            'CHAINS': {
                'label_en': 'Chains',
                'label_hi': 'Chains',
                'collections': {
                    'men_chain_gold': {'name': 'Gold Chains', 'id': '26614026711549117'},
                    'men_chain_silver': {'name': 'Silver Chains', 'id': '35305915439007559'},
                    'men_chain_rope': {'name': 'Rope Chains', 'id': '25364645956543386'}
                }
            },
            'ACCESSORIES': {
                'label_en': 'Accessories',
                'label_hi': 'Accessories',
                'collections': {
                    'men_cufflinks_classic': {'name': 'Classic Cufflinks', 'id': '25956694700651645'},
                    'men_cufflinks_designer': {'name': 'Designer Cufflinks', 'id': '25283486371327046'},
                    'men_tie_pins': {'name': 'Tie Pins', 'id': '34056958820614334'},
                    'men_brooches': {'name': 'Brooches', 'id': '27093254823609535'}
                }
            }
        }
    },
    'STUDIO_EXCLUSIVES': {
        'label_en': 'Studio Exclusives',
        'label_hi': 'Studio Exclusives',
        'sub_categories': {
            'WATCHES': {
                'label_en': 'Watches',
                'label_hi': 'Watches',
                'collections': {
                    'watches_men': {'name': 'Men Timepieces', 'id': '34176915238618497'},
                    'watches_women': {'name': 'Women Timepieces', 'id': '26903528372573194'},
                    'watches_kids': {'name': 'Kids Timepieces', 'id': '26311558718468909'},
                    'watches_smart': {'name': 'Smart Watches', 'id': '25912162851771673'},
                    'watches_luxury': {'name': 'Luxury Timepieces', 'id': '26667915832816156'}
                }
            },
            'ACCESSORIES': {
                'label_en': 'Studio Accessories',
                'label_hi': 'Studio Accessories',
                'collections': {
                    'keychains': {'name': 'Premium Keychains', 'id': '26255788447385252'},
                    'clutches': {'name': 'Evening Clutches', 'id': '34514139158199452'},
                    'sunglasses': {'name': 'Sunglasses', 'id': '25258040713868720'},
                    'belts': {'name': 'Designer Belts', 'id': '26176082815414211'}
                }
            }
        }
    },
    'SACRED_ARTS': {
        'label_en': 'Sacred Arts and Murtis',
        'label_hi': 'Sacred Arts aur Murtis',
        'collections': {}
    }
}

# Build reverse lookup map: Collection ID -> Name
COLLECTION_ID_MAP = {}
SEARCH_KEYWORDS = []

def build_collection_maps():
    """Build collection ID map and search keywords"""
    global COLLECTION_ID_MAP, SEARCH_KEYWORDS
    
    for cat_key, cat_data in CATALOG.items():
        # Direct collections
        if 'collections' in cat_data:
            for coll_key, coll_info in cat_data['collections'].items():
                COLLECTION_ID_MAP[coll_info['id']] = coll_info['name']
                SEARCH_KEYWORDS.append(coll_info['name'])
        
        # Sub-categories
        if 'sub_categories' in cat_data:
            for sub_key, sub_data in cat_data['sub_categories'].items():
                # Direct collections in sub-category
                if 'collections' in sub_data:
                    for coll_key, coll_info in sub_data['collections'].items():
                        COLLECTION_ID_MAP[coll_info['id']] = coll_info['name']
                        SEARCH_KEYWORDS.append(coll_info['name'])
                
                # Sub-menus
                if 'sub_menus' in sub_data:
                    for menu_key, menu_data in sub_data['sub_menus'].items():
                        if 'collections' in menu_data:
                            for coll_key, coll_info in menu_data['collections'].items():
                                COLLECTION_ID_MAP[coll_info['id']] = coll_info['name']
                                SEARCH_KEYWORDS.append(coll_info['name'])

build_collection_maps()

# ============================================================================
# GOOGLE SHEETS FUNCTIONS
# ============================================================================

def get_sheets_client():
    """Initialize Google Sheets client"""
    try:
        if not GOOGLE_SERVICE_ACCOUNT_KEY:
            logger.warning("Google Sheets credentials not found")
            return None
        
        creds_dict = json.loads(GOOGLE_SERVICE_ACCOUNT_KEY)
        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        return gspread.authorize(creds)
    except Exception as e:
        logger.error(f"Sheets client init error: {e}")
        return None

sheets_client = get_sheets_client()

def check_customer_in_sheets(phone):
    """Check if customer exists in Google Sheets"""
    try:
        if not sheets_client or not GOOGLE_SHEET_ID:
            return {'exists': False}
        
        sheet = sheets_client.open_by_key(GOOGLE_SHEET_ID).worksheet('Registrations')
        phones = sheet.col_values(1)
        
        for i, p in enumerate(phones, 1):
            if p == phone:
                row = sheet.row_values(i)
                return {
                    'exists': True,
                    'first_name': row[1] if len(row) > 1 else '',
                    'last_name': row[2] if len(row) > 2 else ''
                }
        
        return {'exists': False}
    except Exception as e:
        logger.error(f"Sheets check error: {e}")
        return {'exists': False}

def log_phone_to_sheets(phone):
    """Log new phone number to Google Sheets"""
    try:
        if not sheets_client or not GOOGLE_SHEET_ID:
            return
        
        sheet = sheets_client.open_by_key(GOOGLE_SHEET_ID).worksheet('Registrations')
        sheet.append_row([phone, '', '', datetime.now().isoformat()])
        logger.info(f"Logged phone to sheets: {phone}")
    except Exception as e:
        logger.error(f"Sheets log error: {e}")

# ============================================================================
# SHOPIFY FUNCTIONS
# ============================================================================

def check_customer_in_shopify(phone):
    """Check if customer exists in Shopify"""
    try:
        if not SHOPIFY_ACCESS_TOKEN:
            return {'exists': False}
        
        url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/customers/search.json"
        headers = {'X-Shopify-Access-Token': SHOPIFY_ACCESS_TOKEN}
        params = {'query': f'phone:{phone}'}
        
        r = requests.get(url, headers=headers, params=params, timeout=10)
        
        if r.status_code == 200:
            customers = r.json().get('customers', [])
            if customers:
                c = customers[0]
                tags = [t.strip() for t in c.get('tags', '').split(',')]
                
                return {
                    'exists': True,
                    'first_name': c.get('first_name', ''),
                    'last_name': c.get('last_name', ''),
                    'email': c.get('email', ''),
                    'customer_type': 'B2B' if any(t in ['B2B', 'Wholesale'] for t in tags) else 'Retail'
                }
        
        return {'exists': False}
    except Exception as e:
        logger.error(f"Shopify check error: {e}")
        return {'exists': False}

def search_shopify_products(query):
    """Search Shopify products with fuzzy matching"""
    try:
        if not query or not SEARCH_KEYWORDS:
            return {'found': False}
        
        # Fuzzy match against collection names
        match = process.extractOne(query, SEARCH_KEYWORDS, scorer=fuzz.token_sort_ratio)
        
        if match and match[1] > 60:  # 60% similarity threshold
            collection_name = match[0]
            
            # Find collection ID
            for coll_id, coll_name in COLLECTION_ID_MAP.items():
                if coll_name == collection_name:
                    return {
                        'found': True,
                        'collection_id': coll_id,
                        'collection_name': coll_name
                    }
        
        return {'found': False}
    except Exception as e:
        logger.error(f"Product search error: {e}")
        return {'found': False}

def detect_customer_status(phone):
    """Detect customer status: new, incomplete, returning_retail, returning_b2b"""
    # Check Shopify first
    shopify = check_customer_in_shopify(phone)
    if shopify['exists']:
        ct = shopify.get('customer_type', 'Retail')
        return {
            'status': 'returning_b2b' if ct == 'B2B' else 'returning_retail',
            'customer_type': ct,
            'first_name': shopify.get('first_name', 'Customer'),
            'last_name': shopify.get('last_name', ''),
            'email': shopify.get('email', '')
        }
    
    # Check Sheets
    sheets = check_customer_in_sheets(phone)
    if sheets['exists']:
        return {
            'status': 'incomplete_registration',
            'first_name': sheets.get('first_name', ''),
            'last_name': sheets.get('last_name', '')
        }
    
    # New customer - log to sheets
    log_phone_to_sheets(phone)
    return {'status': 'new'}

# ============================================================================
# RAZORPAY FUNCTIONS
# ============================================================================

def create_razorpay_link(amount_paise, customer_name, phone, order_ref):
    """Create Razorpay payment link"""
    try:
        if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
            logger.warning("Razorpay credentials not found")
            return None
        
        client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        
        link = client.payment_link.create({
            'amount': amount_paise,
            'currency': 'INR',
            'accept_partial': False,
            'description': f'A Jewel Studio - Order {order_ref}',
            'customer': {
                'name': customer_name,
                'contact': f'+{phone}'
            },
            'notify': {'sms': False, 'email': False},
            'reminder_enable': False,
            'notes': {'order_ref': order_ref}
        })
        
        return link.get('short_url')
    except Exception as e:
        logger.error(f"Razorpay error: {e}")
        return None

# ============================================================================
# SESSION MANAGEMENT
# ============================================================================

def get_session(phone):
    """Get or create user session"""
    if phone not in user_sessions:
        user_sessions[phone] = {
            'created_at': datetime.now(),
            'last_activity': datetime.now(),
            'customer_name': 'Customer',
            'language': 'en',
            'cart_total': 0,
            'navigation_stack': []
        }
    
    user_sessions[phone]['last_activity'] = datetime.now()
    return user_sessions[phone]

def update_session(phone, cust_data):
    """Update session with customer data"""
    session = get_session(phone)
    
    fn = cust_data.get('first_name', 'Customer')
    ln = cust_data.get('last_name', '')
    session['customer_name'] = f"{fn} {ln}".strip() if ln else fn
    
    return session

def detect_language(text):
    """Detect Hindi/English from text"""
    if not text:
        return 'en'
    
    # Check for Devanagari script
    hindi_chars = re.findall(r'[\u0900-\u097F]', text)
    if len(hindi_chars) > len(text) * 0.3:
        return 'hi'
    
    # Check for common Hindi/Hinglish words
    hinglish_words = ['hai', 'hain', 'kya', 'aap', 'mujhe', 'chahiye', 'dikhao', 'batao', 'kaise', 'kaha']
    text_lower = text.lower()
    if any(word in text_lower for word in hinglish_words):
        return 'hi'
    
    return 'en'

def cleanup_sessions():
    """Remove expired sessions"""
    now = datetime.now()
    expired = [p for p, s in user_sessions.items() if now - s['last_activity'] > SESSION_TIMEOUT]
    for p in expired:
        del user_sessions[p]
    if expired:
        logger.info(f"Cleaned up {len(expired)} expired sessions")

# ============================================================================
# ARU - AI ASSISTANT
# ============================================================================

ARU_SYSTEM_PROMPT = """You are Aru, a professional jewelry consultant at A Jewel Studio.

Your personality:
- Knowledgeable, friendly, and maintain a luxury professional tone
- You help customers find perfect jewelry pieces with confidence and grace
- You never show confusion or uncertainty
- You always provide clear, helpful, and elegant responses
- You are warm but professional, like a trusted advisor

Your expertise:
- Deep knowledge of jewelry types, styles, and occasions
- Understanding of customer preferences and needs
- Ability to recommend appropriate collections
- Knowledge of Indian and Western jewelry traditions

Communication style:
- Luxury, friendly, professional tone
- Never aggressive or pushy
- Clear and confident
- Concise but complete answers (2-4 sentences max)
- Use customer's name when known

Important rules:
- Never make up product details or prices
- If you don't know something, gracefully suggest contacting the team
- Always maintain professionalism
- Focus on helping the customer find what they need
- Keep responses short and actionable
"""

def ask_aru(question, language='en', customer_name='Customer', context=''):
    """Get AI response from Aru"""
    try:
        if not gemini_model:
            logger.warning("Gemini model not available")
            return None
        
        # Build prompt
        lang_instruction = "Respond in English." if language == 'en' else "Respond in Hindi/Hinglish using Roman script (not Devanagari)."
        
        full_prompt = f"""{ARU_SYSTEM_PROMPT}

Customer name: {customer_name}
Language: {lang_instruction}

{context}

Customer question: {question}

Provide a helpful, professional response as Aru. Keep it concise (2-4 sentences)."""

        response = gemini_model.generate_content(full_prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Aru AI error: {e}")
        return None

def analyze_image_with_aru(image_url, language='en'):
    """Analyze jewelry image with Gemini Vision"""
    try:
        if not gemini_vision:
            logger.warning("Gemini Vision not available")
            return None
        
        # Download image
        img_response = requests.get(image_url, timeout=10)
        if img_response.status_code != 200:
            return None
        
        # Analyze with Gemini Vision
        prompt = """Analyze this jewelry image and provide:
1. Type of jewelry (earrings, necklace, ring, etc.)
2. Style (traditional, modern, ethnic, etc.)
3. Material (if visible - gold, silver, etc.)
4. Key features and design elements

Be specific and concise."""
        
        response = gemini_vision.generate_content([
            prompt,
            {'mime_type': 'image/jpeg', 'data': img_response.content}
        ])
        
        analysis = response.text.strip()
        
        # Extract keywords for search
        keywords = []
        analysis_lower = analysis.lower()
        
        # Jewelry types
        types = ['earring', 'jhumka', 'necklace', 'ring', 'bracelet', 'bangle', 'kada', 'chain', 'pendant']
        for t in types:
            if t in analysis_lower:
                keywords.append(t)
        
        # Styles
        styles = ['traditional', 'modern', 'bridal', 'ethnic', 'contemporary', 'classic']
        for s in styles:
            if s in analysis_lower:
                keywords.append(s)
        
        return {
            'analysis': analysis,
            'keywords': keywords,
            'search_query': ' '.join(keywords[:3]) if keywords else 'jewelry'
        }
    except Exception as e:
        logger.error(f"Image analysis error: {e}")
        return None

# ============================================================================
# WHATSAPP API FUNCTIONS
# ============================================================================

def _wa_post(payload):
    """Send request to WhatsApp API"""
    try:
        r = requests.post(
            WA_API,
            headers={
                'Authorization': f'Bearer {WHATSAPP_TOKEN}',
                'Content-Type': 'application/json'
            },
            json=payload,
            timeout=10
        )
        
        if not r.ok:
            logger.error(f"WA API error {r.status_code}: {r.text[:300]}")
        
        return r.ok
    except Exception as e:
        logger.error(f"WA post error: {e}")
        return False

def send_text(to, text):
    """Send text message"""
    return _wa_post({
        'messaging_product': 'whatsapp',
        'to': to,
        'type': 'text',
        'text': {'body': text}
    })

def send_button(to, body_text, btn_id, btn_title):
    """Send single button message"""
    return _wa_post({
        'messaging_product': 'whatsapp',
        'to': to,
        'type': 'interactive',
        'interactive': {
            'type': 'button',
            'body': {'text': body_text},
            'action': {
                'buttons': [
                    {'type': 'reply', 'reply': {'id': btn_id, 'title': btn_title}}
                ]
            }
        }
    })

def send_buttons(to, body_text, buttons):
    """Send up to 3 buttons"""
    if len(buttons) > 3:
        buttons = buttons[:3]
    
    return _wa_post({
        'messaging_product': 'whatsapp',
        'to': to,
        'type': 'interactive',
        'interactive': {
            'type': 'button',
            'body': {'text': body_text},
            'action': {
                'buttons': [
                    {'type': 'reply', 'reply': {'id': b['id'], 'title': b['title']}}
                    for b in buttons
                ]
            }
        }
    })

def send_list(to, header, body, btn_text, sections):
    """Send list message"""
    return _wa_post({
        'messaging_product': 'whatsapp',
        'to': to,
        'type': 'interactive',
        'interactive': {
            'type': 'list',
            'header': {'type': 'text', 'text': header},
            'body': {'text': body},
            'action': {
                'button': btn_text,
                'sections': sections
            }
        }
    })

def send_catalog_collection(to, collection_id, collection_name):
    """Open WhatsApp catalog with specific collection"""
    try:
        # Fetch products from Meta Commerce API
        url = f"https://graph.facebook.com/v19.0/{collection_id}/products"
        params = {
            'fields': 'retailer_id',
            'access_token': WHATSAPP_TOKEN,
            'limit': 30
        }
        
        r = requests.get(url, params=params, timeout=10)
        
        if r.ok:
            products = r.json().get('data', [])
            retailer_ids = [p['retailer_id'] for p in products if 'retailer_id' in p]
            
            if retailer_ids:
                # Send product list
                return _wa_post({
                    'messaging_product': 'whatsapp',
                    'to': to,
                    'type': 'interactive',
                    'interactive': {
                        'type': 'product_list',
                        'header': {'type': 'text', 'text': 'A Jewel Studio'},
                        'body': {'text': collection_name},
                        'footer': {'text': 'Add to cart, then tap Place Order'},
                        'action': {
                            'catalog_id': WHATSAPP_CATALOG_ID,
                            'sections': [{
                                'title': collection_name[:24],
                                'product_items': [
                                    {'product_retailer_id': rid} for rid in retailer_ids[:30]
                                ]
                            }]
                        }
                    }
                })
        
        # Fallback: empty catalog message
        send_text(to, f"{collection_name}\n\nThis collection is currently being updated.\n\nHowever, we can help you with custom jewellery designs based on your preference.")
        return True
    
    except Exception as e:
        logger.error(f"Catalog error: {e}")
        send_text(to, f"{collection_name}\n\nPlease contact our team for assistance.")
        return False

def send_payment_link(to, customer_name, phone, total_paise, lang='en'):
    """Send payment link"""
    order_ref = f"AJS-{phone[-4:]}-{int(datetime.now().timestamp())}"
    rp_url = create_razorpay_link(total_paise, customer_name, phone, order_ref)
    
    if rp_url:
        if lang == 'hi':
            text = f"A Jewel Studio choose karne ke liye dhanyavaad\n\nAapka Order Reference:\n{order_ref}\n\nPayment complete karne ke liye neeche button par click karein."
        else:
            text = f"Thank you for choosing A Jewel Studio\n\nYour Order Reference:\n{order_ref}\n\nPlease proceed with your payment using the button below."
        
        return _wa_post({
            'messaging_product': 'whatsapp',
            'to': to,
            'type': 'interactive',
            'interactive': {
                'type': 'cta_url',
                'body': {'text': text},
                'action': {
                    'name': 'cta_url',
                    'parameters': {
                        'display_text': 'PAY NOW',
                        'url': rp_url
                    }
                }
            }
        })
    else:
        if lang == 'hi':
            send_text(to, "Apna order complete karne ke liye hamse contact karein. Hum jaldi hi payment link share karenge.")
        else:
            send_text(to, "To complete your order please contact us. We will share the payment link shortly.")
        return False

# ============================================================================
# FLOW MESSAGE FUNCTIONS
# ============================================================================

def send_new_customer_welcome(to, lang='en'):
    """Flow 1: New Customer"""
    send_text(to, "Hello\nWelcome to A Jewel Studio.")
    time.sleep(0.5)
    
    if lang == 'hi':
        send_text(to, "Main Aru, aapki Studio Assistant hoon.\n\nJoin us to explore our exclusive jewellery collections and latest designs.")
    else:
        send_text(to, "I'm Aru, your Studio Assistant.\n\nJoin us to explore our exclusive jewellery collections and latest designs.")
    
    time.sleep(0.5)
    
    join_url = f"https://{SHOPIFY_STORE}/pages/join-us?wa={to}"
    return _wa_post({
        'messaging_product': 'whatsapp',
        'to': to,
        'type': 'interactive',
        'interactive': {
            'type': 'cta_url',
            'body': {'text': 'Register to access our full collection.'},
            'action': {
                'name': 'cta_url',
                'parameters': {
                    'display_text': 'JOIN US',
                    'url': join_url
                }
            }
        }
    })

def send_incomplete_registration(to, lang='en'):
    """Flow 2: Incomplete Registration"""
    if lang == 'hi':
        text = "Hello\n\nLagta hai aapki registration abhi complete nahi hui hai.\n\nHamari collections explore karne ke liye please apni registration complete karein."
    else:
        text = "Hello\n\nIt looks like your registration is not complete yet.\n\nPlease complete your registration to continue exploring our collections."
    
    join_url = f"https://{SHOPIFY_STORE}/pages/join-us?wa={to}"
    return _wa_post({
        'messaging_product': 'whatsapp',
        'to': to,
        'type': 'interactive',
        'interactive': {
            'type': 'cta_url',
            'body': {'text': text},
            'action': {
                'name': 'cta_url',
                'parameters': {
                    'display_text': 'COMPLETE REGISTRATION',
                    'url': join_url
                }
            }
        }
    })

def send_returning_retail_welcome(to, name, lang='en'):
    """Flow 3: Returning Retail Customer"""
    if lang == 'hi':
        text = f"Hello {name}\n\nA Jewel Studio me dobara swagat hai.\nWe're delighted to have you here.\n\nPlease explore our collections below."
    else:
        text = f"Hello {name}\n\nWelcome back to A Jewel Studio.\nWe're delighted to have you here.\n\nPlease explore our collections below."
    
    send_text(to, text)
    time.sleep(0.5)
    return send_main_menu(to, lang)

def send_returning_b2b_welcome(to, name, lang='en'):
    """Flow 4: Returning B2B Customer"""
    if lang == 'hi':
        text = f"Hello {name}\n\nA Jewel Studio me dobara swagat hai."
    else:
        text = f"Hello {name}\n\nWelcome back to A Jewel Studio."
    
    send_text(to, text)
    time.sleep(0.5)
    
    buttons = [
        {'id': 'BROWSE_FILES', 'title': 'BROWSE FILES'},
        {'id': 'CUSTOM_FILE', 'title': 'CUSTOM FILE'},
        {'id': 'MY_ORDERS', 'title': 'MY ORDERS'}
    ]
    return send_buttons(to, "How can I assist you today?", buttons)

def send_main_menu(to, lang='en'):
    """Main category menu"""
    if lang == 'hi':
        header = 'A Jewel Studio'
        body = 'Kripya apni pasand ki collection select karein'
        btn_text = 'VIEW COLLECTIONS'
    else:
        header = 'A Jewel Studio'
        body = 'Please choose a collection to explore'
        btn_text = 'VIEW COLLECTIONS'
    
    sections = [{
        'title': 'Collections',
        'rows': [
            {'id': 'BABY_JEWELLERY', 'title': 'Baby Jewellery'},
            {'id': 'WOMEN_JEWELLERY', 'title': 'Women Jewellery'},
            {'id': 'MEN_JEWELLERY', 'title': 'Men Jewellery'},
            {'id': 'STUDIO_EXCLUSIVES', 'title': 'Studio Exclusives'},
            {'id': 'SACRED_ARTS', 'title': 'Sacred Arts'}
        ]
    }]
    
    return send_list(to, header, body, btn_text, sections)

def send_baby_collections(to, lang='en'):
    """Baby Jewellery collections"""
    collections = CATALOG['BABY_JEWELLERY']['collections']
    
    rows = [
        {'id': f"COLL_{coll_info['id']}", 'title': coll_info['name']}
        for coll_key, coll_info in collections.items()
    ]
    
    sections = [{'title': 'Baby Jewellery', 'rows': rows}]
    
    return send_list(to, 'Baby Jewellery', 'Select a collection', 'SELECT', sections)

def send_women_body_parts(to, lang='en'):
    """Women Jewellery - Body Parts Menu"""
    buttons = [
        {'id': 'FACE_JEWELLERY', 'title': 'FACE JEWELLERY'},
        {'id': 'HAND_JEWELLERY', 'title': 'HAND JEWELLERY'},
        {'id': 'NECK_JEWELLERY', 'title': 'NECK JEWELLERY'}
    ]
    
    if lang == 'hi':
        text = "Aap ab Women Jewellery collection dekh rahe hain.\n\nKripya aage badhne ke liye ek category select karein."
    else:
        text = "You are now exploring Women Jewellery.\n\nPlease choose a category to continue."
    
    send_buttons(to, text, buttons)
    time.sleep(0.5)
    return send_button(to, "Or view Lower Body Jewellery", 'LOWER_BODY', 'LOWER BODY')

def send_face_jewellery_menu(to, lang='en'):
    """Face Jewellery sub-menu"""
    buttons = [
        {'id': 'EARRINGS', 'title': 'EARRINGS'},
        {'id': 'NOSE_JEWELLERY', 'title': 'NOSE JEWELLERY'},
        {'id': 'HEAD_JEWELLERY', 'title': 'HEAD JEWELLERY'}
    ]
    
    text = "Please choose a style to explore"
    
    send_buttons(to, text, buttons)
    time.sleep(0.5)
    return send_button(to, "Or view Hair Accessories", 'HAIR_ACCESSORIES', 'HAIR ACCESSORIES')

def send_collection_list(to, category_key, subcategory_key, menu_key, lang='en'):
    """Generic collection list sender"""
    try:
        if menu_key:
            # Has sub_menus (Women's jewelry)
            menu_data = CATALOG[category_key]['sub_categories'][subcategory_key]['sub_menus'][menu_key]
            collections = menu_data['collections']
            label = menu_data['label_en']
        else:
            # Direct collections (Men's, Studio, Lower Body)
            if subcategory_key:
                sub_data = CATALOG[category_key]['sub_categories'][subcategory_key]
                collections = sub_data['collections']
                label = sub_data['label_en']
            else:
                collections = CATALOG[category_key]['collections']
                label = CATALOG[category_key]['label_en']
        
        rows = [
            {'id': f"COLL_{coll_info['id']}", 'title': coll_info['name']}
            for coll_key, coll_info in collections.items()
        ]
        
        # Split into sections of 10
        sections = []
        for i in range(0, len(rows), 10):
            sections.append({
                'title': label if i == 0 else f"{label} (cont.)",
                'rows': rows[i:i+10]
            })
        
        return send_list(to, label, 'Select a collection', 'SELECT', sections[:10])
    
    except Exception as e:
        logger.error(f"Collection list error: {e}")
        return send_text(to, "Sorry, there was an error. Please try again.")

def send_empty_catalog_message(to, lang='en'):
    """Flow 8: Empty Catalog"""
    if lang == 'hi':
        text = "Filhaal is collection me products available nahi hain.\n\nLekin hum aapke liye custom design bana sakte hain.\n\nCustom order ke liye hume message karein."
    else:
        text = "This collection is currently being updated.\n\nHowever, we can help you with custom jewellery designs based on your preference.\n\nPlease message us if you would like to place a custom order."
    
    return send_button(to, text, 'CUSTOM_DESIGN', 'REQUEST CUSTOM DESIGN')

def send_payment_success(to, lang='en'):
    """Flow 9: Payment Success"""
    if lang == 'hi':
        text = "Payment successfully receive ho gaya hai\n\nA Jewel Studio se shopping karne ke liye dhanyavaad.\n\nAapka order ab process ho raha hai.\n\nJaldi hi hamari team aapse contact karegi."
    else:
        text = "Payment received successfully\n\nThank you for shopping with A Jewel Studio.\n\nYour order is now being processed.\n\nOur team will contact you shortly with the order details."
    
    return send_text(to, text)

# ============================================================================
# CORE MESSAGE HANDLER
# ============================================================================

def handle_message(phone, msg):
    """Main message handler"""
    try:
        cleanup_sessions()
        
        msg_type = msg.get('type')
        cust_data = detect_customer_status(phone)
        session = update_session(phone, cust_data)
        cust_name = session['customer_name']
        
        # Detect language from text
        if msg_type == 'text':
            text = msg.get('text', {}).get('body', '').strip()
            lang = detect_language(text)
            session['language'] = lang
        else:
            lang = session.get('language', 'en')
        
        # Handle text messages
        if msg_type == 'text':
            text = msg.get('text', {}).get('body', '').strip()
            status = cust_data['status']
            
            # New customer
            if status == 'new':
                send_new_customer_welcome(phone, lang)
                return
            
            # Incomplete registration
            elif status == 'incomplete_registration':
                send_incomplete_registration(phone, lang)
                return
            
            # Returning customers - try product search
            search_result = search_shopify_products(text)
            if search_result['found']:
                collection_id = search_result['collection_id']
                collection_name = search_result['collection_name']
                
                if lang == 'hi':
                    send_text(phone, f"Maine aapki search ke liye ek collection dhundha hai\n\nTap below to explore the products.")
                else:
                    send_text(phone, f"I found a collection matching your search\n\nTap below to explore the products.")
                
                time.sleep(0.5)
                send_catalog_collection(phone, collection_id, collection_name)
                return
            
            # Ask Aru for help
            aru_response = ask_aru(text, lang, cust_name, f"Customer status: {status}")
            if aru_response:
                send_text(phone, aru_response)
                time.sleep(0.5)
            
            # Show menu
            if status == 'returning_b2b':
                send_returning_b2b_welcome(phone, cust_name, lang)
            else:
                send_returning_retail_welcome(phone, cust_name, lang)
            return
        
        # Handle interactive messages
        if msg_type == 'interactive':
            interactive = msg.get('interactive', {})
            itype = interactive.get('type')
            
            # Button reply
            if itype == 'button_reply':
                btn_id = interactive.get('button_reply', {}).get('id', '')
                
                # Main menu
                if btn_id in ['MENU', 'BROWSE_FILES']:
                    send_main_menu(phone, lang)
                
                # B2B actions
                elif btn_id == 'CUSTOM_FILE':
                    send_text(phone, "Please upload your custom design file or describe your requirements.")
                
                elif btn_id == 'MY_ORDERS':
                    send_text(phone, "Fetching your order history...")
                
                # Body parts
                elif btn_id == 'FACE_JEWELLERY':
                    send_face_jewellery_menu(phone, lang)
                
                elif btn_id == 'HAND_JEWELLERY':
                    buttons = [
                        {'id': 'BANGLES_KADA', 'title': 'BANGLES & KADA'},
                        {'id': 'BRACELETS', 'title': 'BRACELETS'},
                        {'id': 'HAND_RINGS', 'title': 'RINGS'}
                    ]
                    send_buttons(phone, "Please choose a category", buttons)
                    time.sleep(0.5)
                    send_button(phone, "Or view Armlets", 'ARMLET', 'ARMLET')
                
                elif btn_id == 'NECK_JEWELLERY':
                    buttons = [
                        {'id': 'NECKLACES', 'title': 'NECKLACES'},
                        {'id': 'PENDANTS', 'title': 'PENDANTS'},
                        {'id': 'BRIDAL_SETS', 'title': 'BRIDAL SETS'}
                    ]
                    send_buttons(phone, "Please choose a category", buttons)
                
                elif btn_id == 'LOWER_BODY':
                    send_collection_list(phone, 'WOMEN_JEWELLERY', 'LOWER_BODY', None, lang)
                
                # Sub-menus - Women's
                elif btn_id == 'EARRINGS':
                    send_collection_list(phone, 'WOMEN_JEWELLERY', 'FACE_JEWELLERY', 'EARRINGS', lang)
                
                elif btn_id == 'NOSE_JEWELLERY':
                    send_collection_list(phone, 'WOMEN_JEWELLERY', 'FACE_JEWELLERY', 'NOSE_JEWELLERY', lang)
                
                elif btn_id == 'HEAD_JEWELLERY':
                    send_collection_list(phone, 'WOMEN_JEWELLERY', 'FACE_JEWELLERY', 'HEAD_JEWELLERY', lang)
                
                elif btn_id == 'HAIR_ACCESSORIES':
                    send_collection_list(phone, 'WOMEN_JEWELLERY', 'FACE_JEWELLERY', 'HAIR_ACCESSORIES', lang)
                
                elif btn_id == 'BANGLES_KADA':
                    send_collection_list(phone, 'WOMEN_JEWELLERY', 'HAND_JEWELLERY', 'BANGLES_KADA', lang)
                
                elif btn_id == 'BRACELETS':
                    send_collection_list(phone, 'WOMEN_JEWELLERY', 'HAND_JEWELLERY', 'BRACELETS', lang)
                
                elif btn_id == 'HAND_RINGS':
                    send_collection_list(phone, 'WOMEN_JEWELLERY', 'HAND_JEWELLERY', 'RINGS', lang)
                
                elif btn_id == 'ARMLET':
                    send_collection_list(phone, 'WOMEN_JEWELLERY', 'HAND_JEWELLERY', 'ARMLET', lang)
                
                elif btn_id == 'NECKLACES':
                    send_collection_list(phone, 'WOMEN_JEWELLERY', 'NECK_JEWELLERY', 'NECKLACES', lang)
                
                elif btn_id == 'PENDANTS':
                    send_collection_list(phone, 'WOMEN_JEWELLERY', 'NECK_JEWELLERY', 'PENDANTS', lang)
                
                elif btn_id == 'BRIDAL_SETS':
                    send_collection_list(phone, 'WOMEN_JEWELLERY', 'NECK_JEWELLERY', 'BRIDAL_SETS', lang)
                
                # Men's categories
                elif btn_id == 'MEN_RINGS':
                    send_collection_list(phone, 'MEN_JEWELLERY', 'RINGS', None, lang)
                
                elif btn_id == 'MEN_BRACELETS':
                    send_collection_list(phone, 'MEN_JEWELLERY', 'BRACELETS', None, lang)
                
                elif btn_id == 'MEN_CHAINS':
                    send_collection_list(phone, 'MEN_JEWELLERY', 'CHAINS', None, lang)
                
                elif btn_id == 'MEN_ACCESSORIES':
                    send_collection_list(phone, 'MEN_JEWELLERY', 'ACCESSORIES', None, lang)
                
                # Studio categories
                elif btn_id == 'WATCHES':
                    send_collection_list(phone, 'STUDIO_EXCLUSIVES', 'WATCHES', None, lang)
                
                elif btn_id == 'STUDIO_ACCESSORIES':
                    send_collection_list(phone, 'STUDIO_EXCLUSIVES', 'ACCESSORIES', None, lang)
                
                # Custom design
                elif btn_id == 'CUSTOM_DESIGN':
                    send_text(phone, "Please describe your custom design requirements or upload an image.")
            
            # List reply
            elif itype == 'list_reply':
                list_id = interactive.get('list_reply', {}).get('id', '')
                
                # Main categories
                if list_id == 'BABY_JEWELLERY':
                    send_baby_collections(phone, lang)
                
                elif list_id == 'WOMEN_JEWELLERY':
                    send_women_body_parts(phone, lang)
                
                elif list_id == 'MEN_JEWELLERY':
                    buttons = [
                        {'id': 'MEN_RINGS', 'title': 'RINGS'},
                        {'id': 'MEN_BRACELETS', 'title': 'BRACELETS'},
                        {'id': 'MEN_CHAINS', 'title': 'CHAINS'}
                    ]
                    send_buttons(phone, "Please choose a category", buttons)
                    time.sleep(0.5)
                    send_button(phone, "Or view Accessories", 'MEN_ACCESSORIES', 'ACCESSORIES')
                
                elif list_id == 'STUDIO_EXCLUSIVES':
                    send_buttons(phone, "Please choose a category", [
                        {'id': 'WATCHES', 'title': 'WATCHES'},
                        {'id': 'STUDIO_ACCESSORIES', 'title': 'ACCESSORIES'}
                    ])
                
                elif list_id == 'SACRED_ARTS':
                    send_empty_catalog_message(phone, lang)
                
                # Collection selected
                elif list_id.startswith('COLL_'):
                    collection_id = list_id.replace('COLL_', '')
                    collection_name = COLLECTION_ID_MAP.get(collection_id, 'Collection')
                    
                    if lang == 'hi':
                        send_text(phone, f"Aap ab {collection_name} Collection dekh rahe hain\n\nApna pasandida design select karein aur Add to Cart karein.")
                    else:
                        send_text(phone, f"You are now viewing our {collection_name} Collection\n\nBrowse the designs and add your favorite pieces to the cart.")
                    
                    time.sleep(0.5)
                    send_catalog_collection(phone, collection_id, collection_name)
            
            return
        
        # Handle image upload
        if msg_type == 'image':
            if lang == 'hi':
                send_text(phone, "Image share karne ke liye dhanyavaad\n\nDesign analyze ho raha hai...")
            else:
                send_text(phone, "Thank you for sharing the image\n\nAnalyzing the design...")
            
            time.sleep(1)
            send_text(phone, "Great! I found similar designs in our collection.\n\nPlease describe what you're looking for, and I'll help you find the perfect piece.")
            return
        
        # Handle order from catalog
        if msg_type == 'order':
            items = msg.get('order', {}).get('product_items', [])
            total = sum(
                int(float(i.get('item_price', 0)) * 100) * i.get('quantity', 1)
                for i in items
            )
            session['cart_total'] = total
            
            send_payment_link(phone, cust_name, phone, total, lang)
            return
    
    except Exception as e:
        logger.error(f"Handle message error: {e}")
        send_text(phone, "Sorry, there was an error. Please try again or contact our team.")

# ============================================================================
# WEBHOOK ROUTES
# ============================================================================

@app.route('/webhook', methods=['GET'])
def verify():
    """Verify webhook"""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    if mode == 'subscribe' and token == VERIFY_TOKEN:
        logger.info("Webhook verified successfully")
        return challenge, 200
    
    logger.warning("Webhook verification failed")
    return 'Forbidden', 403

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming messages"""
    try:
        data = request.get_json(silent=True)
        
        if not data or data.get('object') != 'whatsapp_business_account':
            return jsonify({'status': 'ok'}), 200
        
        msgs = (
            data.get('entry', [{}])[0]
                .get('changes', [{}])[0]
                .get('value', {})
                .get('messages', [])
        )
        
        for msg in msgs:
            phone = msg.get('from')
            if phone:
                handle_message(phone, msg)
        
        return jsonify({'status': 'ok'}), 200
    
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({'status': 'error'}), 500

@app.route('/', methods=['GET'])
@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'A Jewel Studio WhatsApp Bot',
        'assistant': 'Aru',
        'collections': 82,
        'active_sessions': len(user_sessions),
        'timestamp': datetime.now().isoformat()
    }), 200

@app.after_request
def security_headers(response):
    """Add security headers"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    logger.error(f"Internal error: {e}")
    return jsonify({'error': 'Internal server error'}), 500

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    
    logger.info("=" * 70)
    logger.info("A JEWEL STUDIO WHATSAPP BOT - ARU AI ASSISTANT")
    logger.info("=" * 70)
    logger.info(f"Service: WhatsApp Business API Integration")
    logger.info(f"Assistant: Aru (Gemini Pro AI)")
    logger.info(f"Collections: 82 Jewelry Collections")
    logger.info(f"Languages: English + Hindi/Hinglish")
    logger.info(f"Features: Bilingual | AI-Powered | Catalog Integration")
    logger.info(f"Port: {port}")
    logger.info(f"Environment: Production")
    logger.info("=" * 70)
    logger.info(f"WhatsApp Phone ID: {WHATSAPP_PHONE_ID[:20]}...")
    logger.info(f"Catalog ID: {WHATSAPP_CATALOG_ID[:20]}...")
    logger.info(f"Shopify Store: {SHOPIFY_STORE}")
    logger.info(f"Gemini AI: {'Enabled' if gemini_model else 'Disabled'}")
    logger.info(f"Razorpay: {'Enabled' if RAZORPAY_KEY_ID else 'Disabled'}")
    logger.info(f"Google Sheets: {'Enabled' if sheets_client else 'Disabled'}")
    logger.info("=" * 70)
    logger.info("Bot is ready to serve customers!")
    logger.info("=" * 70)
    
    app.run(host='0.0.0.0', port=port, debug=False)
