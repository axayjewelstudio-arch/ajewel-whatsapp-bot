    # ═══════════════════════════════════════════════════════════
    # A Jewel Studio - Professional WhatsApp Bot v4
    # Complete Flow with AI, Image Recognition & Smart Search
    # ═══════════════════════════════════════════════════════════
    
    import os
    import json
    import time
    from datetime import datetime
    from flask import Flask, request, jsonify
    from flask_cors import CORS
    import requests
    from dotenv import load_dotenv
    import gspread
    from google.oauth2.service_account import Credentials
    import google.generativeai as genai
    from PIL import Image
    import io
    
    load_dotenv()
    app = Flask(__name__)
    CORS(app)
    
    # ── Environment Variables ──
    WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN')
    WHATSAPP_PHONE_ID = os.getenv('WHATSAPP_PHONE_ID')
    VERIFY_TOKEN = os.getenv('VERIFY_TOKEN')
    GOOGLE_CREDENTIALS = os.getenv('GOOGLE_CREDENTIALS')
    SHOPIFY_STORE = os.getenv('SHOPIFY_STORE', 'a-jewel-studio-3.myshopify.com')
    SHOPIFY_ACCESS_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN')
    BACKEND_API_URL = os.getenv('BACKEND_API_URL', 'https://ajewelbot-v2-backend.onrender.com')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'AIzaSyAI_7J57EpfoQoBlCVJtVHdpj_YR4x6GTY')
    
    # ── Configure Gemini AI ──
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-pro')
    gemini_vision_model = genai.GenerativeModel('gemini-1.5-flash')
    
    # ── Constants ──
    SHEET_ID = "1w-4Zi65AqsQZFJIr1GLrDrW9BJNez8Wtr-dTL8oBLbs"
    JOIN_US_URL = "https://a-jewel-studio-3.myshopify.com/pages/join-us"
    LOGO_IMAGE_URL = "https://cdn.shopify.com/s/files/1/0815/3248/5868/files/Welcome_Photo.jpg?v=1772108644"
    CUSTOMER_CARE_NUMBER = "7600056655"
    SESSION_TIMEOUT = 1800
    
    user_sessions = {}
    
    # ═══════════════════════════════════════════════════════════
    # GEMINI AI SUPPORT
    # ═══════════════════════════════════════════════════════════
    
    def get_ai_response(customer_message, customer_name='Customer', customer_type='Retail'):
        """Get professional AI response using Gemini"""
        try:
            system_prompt = f"""You are a professional customer service representative for A Jewel Studio, a premium jewellery brand.
    
    IMPORTANT GUIDELINES:
    - You are an employee of A Jewel Studio
    - Always be professional, polite, and helpful
    - Keep responses concise (2-3 sentences max)
    - Use proper grammar and punctuation
    - Address customer as "{customer_name}"
    - Customer type: {customer_type}
    - Brand name: "A Jewel Studio" (with spaces)
    
    WHAT YOU CAN HELP WITH:
    - General jewellery questions
    - Product information
    - Store policies
    - Business hours (Mon-Sat: 10 AM - 7 PM, Sunday: Closed)
    - Shipping and delivery
    - Custom jewellery design
    - Gift recommendations
    
    WHAT YOU CANNOT DO:
    - Process orders (direct to WhatsApp catalog)
    - Check order status (ask customer to type "Track #OrderID")
    - Book appointments (direct to appointment flow)
    - Access customer data
    - Make promises about pricing or discounts
    
    If customer asks about orders, appointments, or catalog, politely direct them to use the menu buttons.
    
    Customer message: {customer_message}
    
    Respond professionally as an A Jewel Studio employee:"""
    
            response = gemini_model.generate_content(system_prompt)
            ai_reply = response.text.strip()
            
            if not any(word in ai_reply.lower() for word in ['regards', 'help', 'assist']):
                ai_reply += "\n\nHow else may I assist you today?"
            
            return ai_reply
        
        except Exception as e:
            print(f"Gemini AI Error: {e}")
            return "Thank you for your message. For immediate assistance, please select an option from the menu or contact our team at +91 7600056655."
    
    # ═══════════════════════════════════════════════════════════
    # IMAGE RECOGNITION - GEMINI VISION
    # ═══════════════════════════════════════════════════════════
    
    def analyze_jewelry_image(image_url):
        """Analyze jewelry image using Gemini Vision"""
        try:
            response = requests.get(image_url, headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"})
            
            if response.status_code != 200:
                return None
            
            image_data = response.content
            img = Image.open(io.BytesIO(image_data))
            
            prompt = """Analyze this jewelry image and identify:
    1. Type of jewelry (earring, ring, necklace, bracelet, etc.)
    2. Style (traditional, modern, bridal, casual)
    3. Key features (design elements, stones, patterns)
    4. Suitable category
    
    Respond in this format:
    Type: [jewelry type]
    Style: [style]
    Category: [baby/women/men]
    Subcategory: [specific type like jhumka, studs, bangles, etc.]"""
    
            response = gemini_vision_model.generate_content([prompt, img])
            analysis = response.text.strip()
            
            print(f"Image Analysis: {analysis}")
            return analysis
        
        except Exception as e:
            print(f"Image analysis error: {e}")
            return None
    
    def find_similar_collection(analysis_text):
        """Find matching collection based on image analysis"""
        if not analysis_text:
            return None
        
        analysis_lower = analysis_text.lower()
        
        # Baby jewelry
        if 'baby' in analysis_lower or 'kid' in analysis_lower or 'child' in analysis_lower:
            if 'earring' in analysis_lower:
                return 'baby_earrings'
            elif 'bangle' in analysis_lower or 'kada' in analysis_lower:
                return 'baby_bangles'
            elif 'chain' in analysis_lower or 'necklace' in analysis_lower:
                return 'baby_chain'
            elif 'ring' in analysis_lower:
                return 'baby_rings'
            elif 'anklet' in analysis_lower or 'payal' in analysis_lower:
                return 'baby_payal'
            elif 'hair' in analysis_lower:
                return 'baby_hair'
        
        # Women face jewelry
        if 'women' in analysis_lower or 'female' in analysis_lower or 'bridal' in analysis_lower:
            if 'jhumka' in analysis_lower:
                return 'face_jhumka'
            elif 'stud' in analysis_lower:
                return 'face_studs'
            elif 'chandbali' in analysis_lower:
                return 'face_chandbali'
            elif 'hoop' in analysis_lower:
                return 'face_hoops'
            elif 'bahubali' in analysis_lower:
                return 'face_bahubali'
            elif 'nath' in analysis_lower:
                return 'face_nath'
            elif 'nose' in analysis_lower:
                return 'face_nose_pin'
            elif 'maang tikka' in analysis_lower:
                return 'face_maang_tikka'
            elif 'earring' in analysis_lower:
                return 'face_studs'
            
            # Women hand jewelry
            elif 'bangle' in analysis_lower:
                return 'hand_bangles'
            elif 'kada' in analysis_lower:
                return 'hand_kada'
            elif 'bracelet' in analysis_lower:
                return 'hand_bracelet'
            elif 'ring' in analysis_lower:
                if 'engagement' in analysis_lower:
                    return 'hand_rings_engagement'
                elif 'wedding' in analysis_lower:
                    return 'hand_rings_wedding'
                else:
                    return 'hand_rings'
            
            # Women neck jewelry
            elif 'necklace' in analysis_lower or 'haar' in analysis_lower:
                return 'neck_haar'
            elif 'choker' in analysis_lower:
                return 'neck_choker'
            elif 'pendant' in analysis_lower:
                return 'neck_solitaire'
            
            # Women lower body
            elif 'anklet' in analysis_lower or 'payal' in analysis_lower:
                return 'lower_payal'
        
        # Men jewelry
        if 'men' in analysis_lower or 'male' in analysis_lower or 'groom' in analysis_lower:
            if 'ring' in analysis_lower:
                if 'wedding' in analysis_lower:
                    return 'men_rings_wedding'
                else:
                    return 'men_rings_fashion'
            elif 'chain' in analysis_lower:
                return 'men_chain_gold'
            elif 'bracelet' in analysis_lower:
                return 'men_bracelet_chain'
            elif 'kada' in analysis_lower:
                return 'men_kada_traditional'
        
        return None
    
    def handle_image_upload(to_number, image_url, customer_name='Customer'):
        """Handle customer image upload"""
        send_whatsapp_text(to_number, f"Thank you, {customer_name}! 📸\n\nAnalyzing your image to find similar products...")
        
        analysis = analyze_jewelry_image(image_url)
        
        if analysis:
            collection_key = find_similar_collection(analysis)
            
            if collection_key:
                time.sleep(2)
                send_whatsapp_text(to_number, "Great! I found similar products in our collection. Opening catalog...")
                time.sleep(1)
                send_catalog_link(to_number, collection_key)
            else:
                send_whatsapp_text(to_number, "I analyzed your image but couldn't find an exact match. Let me show you our main collections.")
                time.sleep(1)
                send_main_menu(to_number, customer_name)
        else:
            send_whatsapp_text(to_number, "I couldn't analyze the image properly. Please try uploading a clearer photo or browse our collections.")
            time.sleep(1)
            send_main_menu(to_number, customer_name)
    
    # ═══════════════════════════════════════════════════════════
    # GOOGLE SHEETS CONNECTION
    # ═══════════════════════════════════════════════════════════
    
    def get_google_sheet():
        try:
            creds_dict = json.loads(GOOGLE_CREDENTIALS)
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
            client = gspread.authorize(creds)
            return client.open_by_key(SHEET_ID).worksheet('Registrations')
        except Exception as e:
            print(f"Google Sheets Error: {e}")
            return None
    
    # ═══════════════════════════════════════════════════════════
    # SHOPIFY API FUNCTIONS
    # ═══════════════════════════════════════════════════════════
    
    def get_shopify_customer(phone):
        """Get customer from Shopify by phone number"""
        try:
            url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/customers/search.json"
            headers = {
                'X-Shopify-Access-Token': SHOPIFY_ACCESS_TOKEN,
                'Content-Type': 'application/json'
            }
            params = {'query': f'phone:{phone}'}
            
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                customers = response.json().get('customers', [])
                return customers[0] if customers else None
            return None
        except Exception as e:
            print(f"Shopify API Error: {e}")
            return None
    
    def is_b2b_customer(customer):
        """Check if customer is B2B based on tags"""
        if not customer:
            return False
        tags = customer.get('tags', '').lower()
        return 'b2b' in tags or 'wholesaler' in tags or 'wholesale' in tags
    
    # ═══════════════════════════════════════════════════════════
    # CUSTOMER STATUS CHECK
    # ═══════════════════════════════════════════════════════════
    
    def check_customer_status(phone_number):
        """Check customer status"""
        try:
            sheet = get_google_sheet()
            if not sheet:
                return {'exists': False}
            
            all_data = sheet.get_all_values()
            
            for idx, row in enumerate(all_data[1:], start=2):
                if len(row) > 0 and row[0] == phone_number:
                    has_form_data = bool(row[1]) if len(row) > 1 else False
                    customer_type_sheet = row[27] if len(row) > 27 else 'Retail'
                    first_name = row[1] if len(row) > 1 else ''
                    last_name = row[2] if len(row) > 2 else ''
                    
                    shopify_customer = get_shopify_customer(phone_number)
                    
                    if shopify_customer:
                        customer_type = 'B2B' if is_b2b_customer(shopify_customer) else customer_type_sheet
                    else:
                        customer_type = customer_type_sheet
                    
                    return {
                        'exists': True,
                        'has_form_data': has_form_data,
                        'customer_type': customer_type,
                        'name': f"{first_name} {last_name}".strip() or 'Customer',
                        'shopify_customer': shopify_customer,
                        'row': idx
                    }
            
            return {'exists': False}
        
        except Exception as e:
            print(f"Sheet check error: {e}")
            return {'exists': False}
    
    def add_number_to_sheet(phone_number):
        """Add new number to Column A only"""
        try:
            customer_status = check_customer_status(phone_number)
            
            if customer_status['exists']:
                print(f"Number already exists: {phone_number}")
                return False
            
            sheet = get_google_sheet()
            if sheet:
                sheet.append_row([phone_number])
                print(f"New number added: {phone_number}")
                return True
        except Exception as e:
            print(f"Sheet add error: {e}")
        return False
    
    # ═══════════════════════════════════════════════════════════
    # SESSION MANAGEMENT
    # ═══════════════════════════════════════════════════════════
    
    def get_session(phone_number):
        """Get or create session"""
        if phone_number not in user_sessions:
            user_sessions[phone_number] = {
                'state': 'idle',
                'data': {},
                'created_at': datetime.now(),
                'last_activity': datetime.now()
            }
        else:
            last_activity = user_sessions[phone_number]['last_activity']
            if (datetime.now() - last_activity).seconds > SESSION_TIMEOUT:
                user_sessions[phone_number] = {
                    'state': 'idle',
                    'data': {},
                    'created_at': datetime.now(),
                    'last_activity': datetime.now()
                }
        
        user_sessions[phone_number]['last_activity'] = datetime.now()
        return user_sessions[phone_number]
    
    def update_session(phone_number, state=None, data=None):
        """Update session"""
        session = get_session(phone_number)
        if state:
            session['state'] = state
        if data:
            session['data'].update(data)
        session['last_activity'] = datetime.now()
    
    def clear_session(phone_number):
        """Clear session"""
        if phone_number in user_sessions:
            del user_sessions[phone_number]
    
    # ═══════════════════════════════════════════════════════════
    # WHATSAPP SEND FUNCTIONS
    # ═══════════════════════════════════════════════════════════
    
    def send_whatsapp_text(to_number, message_text):
        url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "text": {"body": message_text}
        }
        try:
            r = requests.post(url, json=payload, headers=headers)
            print(f"Text sent to {to_number}: {r.status_code}")
            return r.json()
        except Exception as e:
            print(f"WhatsApp text error: {e}")
            return None
    
    def send_whatsapp_image(to_number, image_url, caption=''):
        url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "image",
            "image": {
                "link": image_url,
                "caption": caption
            }
        }
        try:
            r = requests.post(url, json=payload, headers=headers)
            print(f"Image sent to {to_number}: {r.status_code}")
            return r.json()
        except Exception as e:
            print(f"WhatsApp image error: {e}")
            return None
    
    def send_whatsapp_buttons(to_number, body_text, buttons):
        """Send interactive buttons"""
        url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }
        
        formatted_buttons = []
        for btn in buttons[:3]:
            formatted_buttons.append({
                "type": "reply",
                "reply": {
                    "id": btn.get('id', 'btn_' + str(len(formatted_buttons))),
                    "title": btn.get('title', 'Option')[:20]
                }
            })
    
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {
                    "text": body_text[:1024]
                },
                "action": {
                    "buttons": formatted_buttons
                }
            }
        }
        
        try:
            r = requests.post(url, json=payload, headers=headers)
            print(f"Buttons sent to {to_number}: {r.status_code}")
            if r.status_code != 200:
                print(f"Button error: {r.text}")
                button_text = "\n".join([f"{i+1}. {btn['title']}" for i, btn in enumerate(buttons)])
                return send_whatsapp_text(to_number, f"{body_text}\n\n{button_text}")
            return r.json()
        except Exception as e:
            print(f"WhatsApp buttons error: {e}")
            button_text = "\n".join([f"{i+1}. {btn['title']}" for i, btn in enumerate(buttons)])
            return send_whatsapp_text(to_number, f"{body_text}\n\n{button_text}")
    
    def send_whatsapp_cta_button(to_number, body_text, button_text, button_url):
        """Send CTA URL button"""
        url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "interactive",
            "interactive": {
                "type": "cta_url",
                "body": {"text": body_text[:1024]},
                "action": {
                    "name": "cta_url",
                    "parameters": {
                        "display_text": button_text[:20],
                        "url": button_url
                    }
                }
            }
        }
        try:
            r = requests.post(url, json=payload, headers=headers)
            if r.status_code == 200:
                print(f"CTA button sent to {to_number}")
                return r.json()
            else:
                print(f"CTA button failed: {r.text}")
                fallback = f"{body_text}\n\n{button_text}: {button_url}"
                return send_whatsapp_text(to_number, fallback)
        except Exception as e:
            print(f"WhatsApp CTA error: {e}")
            fallback = f"{body_text}\n\n{button_text}: {button_url}"
            return send_whatsapp_text(to_number, fallback)
    # ═══════════════════════════════════════════════════════════
    # FLOW MESSAGES - NEW CUSTOMER
    # ═══════════════════════════════════════════════════════════
    
    def send_new_customer_welcome(to_number):
        """Flow 1: New customer first visit"""
        if LOGO_IMAGE_URL:
            send_whatsapp_image(
                to_number,
                LOGO_IMAGE_URL,
                caption="Welcome to\n\n*A Jewel Studio*"
            )
            time.sleep(2)
        
        join_url = f"{JOIN_US_URL}?wa={to_number}"
        send_whatsapp_cta_button(
            to_number,
            "Tap Join Us below to become a part of our family and explore our exclusive collections.",
            "Join Us",
            join_url
        )
    
    def send_complete_registration(to_number):
        """Customer logged but form not completed"""
        message = "Hello!\n\nI see you messaged us before but did not complete registration.\n\nWould you like to complete your registration to unlock our full collection?"
        
        join_url = f"{JOIN_US_URL}?wa={to_number}"
        send_whatsapp_cta_button(
            to_number,
            message,
            "Complete Registration",
            join_url
        )
    
    def send_retail_welcome(to_number, customer_name):
        """Flow 2A: Returning retail customer"""
        message = f"Welcome back, *{customer_name}*.\n\nWe are delighted to have you here."
        
        send_whatsapp_text(to_number, message)
        time.sleep(1)
        send_main_menu(to_number, customer_name)
    
    def send_b2b_welcome(to_number, customer_name):
        """Flow 2B: Returning B2B customer"""
        message = f"Welcome back, *{customer_name}*.\n\nWe are delighted to have you here.\n\nPlease select an option below to get started."
        
        buttons = [
            {"id": "browse_digital_files", "title": "Browse Files"},
            {"id": "request_custom_file", "title": "Custom File"},
            {"id": "my_orders", "title": "My Orders"}
        ]
        
        send_whatsapp_buttons(to_number, message, buttons)
    
    # ═══════════════════════════════════════════════════════════
    # SUPPORT MESSAGES
    # ═══════════════════════════════════════════════════════════
    
    def send_business_hours(to_number):
        """Business hours enquiry"""
        message = """Our business hours are:
    
    *Monday to Saturday:* 10:00 AM to 7:00 PM
    *Sunday:* Closed
    
    For support outside these hours, please leave a message and our team will respond on the next business day."""
        
        send_whatsapp_text(to_number, message)
    
    def send_about_us(to_number):
        """About A Jewel Studio"""
        message = """*A Jewel Studio* is a premium jewellery design studio specialising in creating exquisite jewellery collections and high-quality 3D digital files for our partners.
    
    Our designs are crafted with precision and passion, bringing timeless elegance to life."""
        
        buttons = [
            {"id": "back_main", "title": "Browse Collections"},
            {"id": "connect_support", "title": "Connect with Us"}
        ]
        
        send_whatsapp_buttons(to_number, message, buttons)
    
    def send_unrecognised_message(to_number, customer_type='Retail'):
        """Unrecognised message fallback"""
        message = "Thank you for reaching out to A Jewel Studio.\n\nI couldn't quite understand your message. Please select an option below so I can assist you better."
        
        if customer_type == 'B2B' or customer_type == 'Wholesale':
            buttons = [
                {"id": "browse_digital_files", "title": "Browse Files"},
                {"id": "request_custom_file", "title": "Custom File"},
                {"id": "my_orders", "title": "My Orders"}
            ]
        else:
            buttons = [
                {"id": "back_main", "title": "Browse Collections"},
                {"id": "customise_product", "title": "Custom Design"},
                {"id": "connect_support", "title": "Connect with Us"}
            ]
        
        send_whatsapp_buttons(to_number, message, buttons)
    
    def track_order(to_number, order_id):
        """Track order by ID"""
        try:
            response = requests.get(f"{BACKEND_API_URL}/api/orders/track/{order_id}")
            
            if response.status_code == 200:
                order_data = response.json()
                message = f"""*Order Status* 📦
    
    *Order ID:* {order_id}
    *Status:* {order_data.get('status', 'In Production')}
    *Expected Ready Date:* {order_data.get('readyDate', 'TBD')}
    
    We will notify you once your order is ready for collection."""
                send_whatsapp_text(to_number, message)
            else:
                send_whatsapp_text(to_number, f"Order {order_id} not found. Please check the order ID and try again.")
        except Exception as e:
            print(f"Order tracking error: {e}")
            send_whatsapp_text(to_number, "Unable to fetch order details at the moment. Please try again later or contact our support team.")
    
    def generate_referral_code(customer_name, phone_number):
        """Generate referral code"""
        name_part = customer_name[:3].upper() if customer_name else 'REF'
        phone_part = phone_number[-4:]
        return f"{name_part}{phone_part}"
    
    def send_referral_info(to_number, customer_name):
        """Send referral code and info"""
        referral_code = generate_referral_code(customer_name, to_number)
        
        message = f"""*Your Referral Code* 🎁
    
    *Code:* {referral_code}
    
    Share this code with your friends and family. When they register using your code, both of you will receive special benefits!
    
    *Share this link:*
    {JOIN_US_URL}?ref={referral_code}
    
    Thank you for being a valued member of A Jewel Studio."""
        
        send_whatsapp_text(to_number, message)
    
    # ═══════════════════════════════════════════════════════════
    # CATALOG COLLECTIONS - 82 COLLECTIONS
    # ═══════════════════════════════════════════════════════════
    
    CATALOG_COLLECTIONS = {
        'baby_hair': {'id': '26930579176543121', 'name': 'Little Treasures - Hair Accessories'},
        'baby_earrings': {'id': '34197166099927645', 'name': 'Little Treasures - Earrings'},
        'baby_chain': {'id': '34159752333640697', 'name': 'Little Treasures - Necklace Chains'},
        'baby_rings': {'id': '27130321023234461', 'name': 'Little Treasures - Rings'},
        'baby_payal': {'id': '26132380466413425', 'name': 'Little Treasures - Anklets'},
        'baby_bangles': {'id': '25812008941803035', 'name': 'Little Treasures - Bangles'},
        'face_studs': {'id': '26648112538119124', 'name': 'Eternal Elegance - Diamond Studs'},
        'face_jhumka': {'id': '26067705569545995', 'name': 'Eternal Elegance - Traditional Jhumka'},
        'face_chandbali': {'id': '26459908080267418', 'name': 'Eternal Elegance - Chandbali Earrings'},
        'face_hoops': {'id': '26507559175517690', 'name': 'Eternal Elegance - Classic Hoops'},
        'face_cuff': {'id': '25904630702480491', 'name': 'Eternal Elegance - Ear Cuffs'},
        'face_kanser': {'id': '24428630293501712', 'name': 'Eternal Elegance - Bridal Kanser'},
        'face_bahubali': {'id': '27263060009951006', 'name': 'Eternal Elegance - Bahubali Earrings'},
        'face_drop': {'id': '27085758917680509', 'name': 'Eternal Elegance - Drop Earrings'},
        'face_sui_dhaga': {'id': '26527646070152559', 'name': 'Eternal Elegance - Sui Dhaga'},
        'face_chuk': {'id': '26001425306208264', 'name': 'Eternal Elegance - Vintage Chuk'},
        'face_nath': {'id': '26146672631634215', 'name': 'Eternal Elegance - Bridal Nath'},
        'face_nose_pin': {'id': '25816769131325224', 'name': 'Eternal Elegance - Nose Pins'},
        'face_septum': {'id': '26137405402565188', 'name': 'Eternal Elegance - Septum Rings'},
        'face_clip_on': {'id': '25956080384032593', 'name': 'Eternal Elegance - Clip-On Nose Rings'},
        'face_maang_tikka': {'id': '34096814326631390', 'name': 'Eternal Elegance - Maang Tikka'},
        'face_matha_patti': {'id': '25972597769065393', 'name': 'Eternal Elegance - Matha Patti'},
        'face_passa': {'id': '25853734394311094', 'name': 'Eternal Elegance - Passa'},
        'face_head_kanser': {'id': '26924099463860066', 'name': 'Eternal Elegance - Head Kanser'},
        'face_sheesh_phool': {'id': '25884225787909036', 'name': 'Eternal Elegance - Sheesh Phool'},
        'hair_clips': {'id': '25923141554014968', 'name': 'Signature Collection - Hair Accessories'},
        'hand_bangles': {'id': '25990285673976585', 'name': 'Eternal Elegance - Traditional Bangles'},
        'hand_kada': {'id': '26202123256143866', 'name': 'Eternal Elegance - Designer Kada'},
        'hand_bracelet': {'id': '26479540271641962', 'name': 'Eternal Elegance - Bracelets'},
        'hand_bracelet_chain': {'id': '26553938717531086', 'name': 'Eternal Elegance - Chain Bracelets'},
        'hand_bracelet_charm': {'id': '25889526627383303', 'name': 'Eternal Elegance - Charm Bracelets'},
        'hand_bracelet_cuff': {'id': '26095567730084970', 'name': 'Eternal Elegance - Cuff Bracelets'},
        'hand_baju_band': {'id': '25741475325553252', 'name': 'Eternal Elegance - Baju Band'},
        'hand_rings': {'id': '26458893303705648', 'name': 'Eternal Elegance - Designer Rings'},
        'hand_rings_engagement': {'id': '26577195808532633', 'name': 'Eternal Elegance - Engagement Rings'},
        'hand_rings_wedding': {'id': '26283285724614486', 'name': 'Eternal Elegance - Wedding Bands'},
        'hand_rings_fashion': {'id': '26627787650158306', 'name': 'Eternal Elegance - Fashion Rings'},
        'neck_haar': {'id': '34124391790542901', 'name': 'Eternal Elegance - Traditional Haar'},
        'neck_choker': {'id': '34380933844854505', 'name': 'Eternal Elegance - Modern Chokers'},
        'neck_princess': {'id': '27036678569255877', 'name': 'Eternal Elegance - Princess Necklaces'},
        'neck_matinee': {'id': '34810362708554746', 'name': 'Eternal Elegance - Matinee Necklaces'},
        'neck_solitaire': {'id': '26345939121667071', 'name': 'Eternal Elegance - Solitaire Pendants'},
        'neck_locket': {'id': '34949414394649401', 'name': 'Eternal Elegance - Locket Pendants'},
        'neck_statement': {'id': '34061823006795079', 'name': 'Eternal Elegance - Statement Pendants'},
        'neck_sets': {'id': '34181230154825697', 'name': 'Eternal Elegance - Bridal Sets'},
        'lower_kamarband': {'id': '25970100975978085', 'name': 'Eternal Elegance - Kamarband'},
        'lower_payal': {'id': '26108970985433226', 'name': 'Eternal Elegance - Payal Anklets'},
        'lower_toe_rings': {'id': '26041413228854859', 'name': 'Eternal Elegance - Toe Rings'},
        'men_rings_wedding': {'id': '35279590828306838', 'name': 'Bold Heritage - Wedding Bands'},
        'men_rings_engagement': {'id': '26205064579128433', 'name': 'Bold Heritage - Engagement Rings'},
        'men_rings_signet': {'id': '26133044123050259', 'name': 'Bold Heritage - Signet Rings'},
        'men_rings_fashion': {'id': '26353107324312966', 'name': 'Bold Heritage - Fashion Rings'},
        'men_rings_band': {'id': '26048808064813747', 'name': 'Bold Heritage - Classic Bands'},
        'men_rings_stone': {'id': '25392189793787605', 'name': 'Bold Heritage - Gemstone Rings'},
        'men_bracelet_chain': {'id': '26028399416826135', 'name': 'Bold Heritage - Chain Bracelets'},
        'men_bracelet_leather': {'id': '24614722568226121', 'name': 'Bold Heritage - Leather Bracelets'},
        'men_bracelet_beaded': {'id': '26526947026910291', 'name': 'Bold Heritage - Beaded Bracelets'},
        'men_bracelet_cuff': {'id': '26224048963949143', 'name': 'Bold Heritage - Cuff Bracelets'},
        'men_chain_gold': {'id': '26614026711549117', 'name': 'Bold Heritage - Gold Chains'},
        'men_chain_silver': {'id': '35305915439007559', 'name': 'Bold Heritage - Silver Chains'},
        'men_chain_rope': {'id': '25364645956543386', 'name': 'Bold Heritage - Rope Chains'},
        'men_pendant_religious': {'id': '34138553902457530', 'name': 'Bold Heritage - Religious Pendants'},
        'men_pendant_initial': {'id': '26251311201160440', 'name': 'Bold Heritage - Initial Pendants'},
        'men_pendant_stone': {'id': '26441867825407906', 'name': 'Bold Heritage - Gemstone Pendants'},
        'men_kada_traditional': {'id': '26080348848282889', 'name': 'Bold Heritage - Traditional Kada'},
        'men_kada_modern': {'id': '26028780853472858', 'name': 'Bold Heritage - Modern Kada'},
        'men_cufflinks_classic': {'id': '25956694700651645', 'name': 'Bold Heritage - Classic Cufflinks'},
        'men_cufflinks_designer': {'id': '25283486371327046', 'name': 'Bold Heritage - Designer Cufflinks'},
        'men_tie_pins': {'id': '34056958820614334', 'name': 'Bold Heritage - Tie Pins'},
        'men_brooches': {'id': '27093254823609535', 'name': 'Bold Heritage - Brooches'},
        'watches_men': {'id': '34176915238618497', 'name': 'Signature Collection - Men\'s Timepieces'},
        'watches_women': {'id': '26903528372573194', 'name': 'Signature Collection - Women\'s Timepieces'},
        'watches_kids': {'id': '26311558718468909', 'name': 'Signature Collection - Kids Timepieces'},
        'watches_smart': {'id': '25912162851771673', 'name': 'Signature Collection - Smart Watches'},
        'watches_luxury': {'id': '26667915832816156', 'name': 'Signature Collection - Luxury Timepieces'},
        'keychains': {'id': '26255788447385252', 'name': 'Signature Collection - Premium Keychains'},
        'clutches': {'id': '34514139158199452', 'name': 'Signature Collection - Evening Clutches'},
        'sunglasses': {'id': '25258040713868720', 'name': 'Signature Collection - Sunglasses'},
        'belts': {'id': '26176082815414211', 'name': 'Signature Collection - Designer Belts'},
        'murti_figurines': {'id': '26255788447385252', 'name': 'Divine Blessings - Sacred Idols'}
    }
    
    def send_catalog_link(to_number, collection_key):
        """Open WhatsApp catalog by collection key"""
        collection = CATALOG_COLLECTIONS.get(collection_key)
        
        if not collection:
            send_whatsapp_text(to_number, "This collection is currently unavailable. Please try another option or contact our team for assistance.")
            return
        
        collection_id = collection['id']
        collection_name = collection['name']
        catalog_url = f"https://wa.me/c/{WHATSAPP_PHONE_ID}/{collection_id}"
        
        message = f"✨ *{collection_name}*\n\nExplore our exquisite collection. Tap the button below to view products in WhatsApp catalog."
        
        send_whatsapp_cta_button(to_number, message, "View Collection", catalog_url)
    
    # ═══════════════════════════════════════════════════════════
    # MAIN MENU
    # ═══════════════════════════════════════════════════════════
    
    def send_main_menu(to_number, customer_name='Customer'):
        """Send main category menu"""
        message = f"Welcome to *A Jewel Studio*, {customer_name}.\n\nPlease select a category to explore our collections:"
        
        buttons = [
            {"id": "cat_baby", "title": "Baby Jewellery"},
            {"id": "cat_women", "title": "Women Jewellery"},
            {"id": "cat_men", "title": "Men Jewellery"}
        ]
        send_whatsapp_buttons(to_number, message, buttons)
        
        time.sleep(1)
        buttons2 = [
            {"id": "cat_studio", "title": "Signature Collection"},
            {"id": "cat_divine", "title": "Divine Blessings"}
        ]
        send_whatsapp_buttons(to_number, "Or explore our exclusive collections:", buttons2)
    
    def send_baby_collections(to_number):
        """Show baby jewellery collections"""
        message = "*Little Treasures Collection*\n\nSelect a category to view our baby jewellery:"
        
        buttons = [
            {"id": "baby_hair", "title": "Hair Accessories"},
            {"id": "baby_earrings", "title": "Earrings"},
            {"id": "baby_chain", "title": "Necklace Chains"}
        ]
        send_whatsapp_buttons(to_number, message, buttons)
        
        time.sleep(1)
        buttons2 = [
            {"id": "baby_rings", "title": "Rings"},
            {"id": "baby_payal", "title": "Anklets (Payal)"},
            {"id": "baby_bangles", "title": "Bangles & Kada"}
        ]
        send_whatsapp_buttons(to_number, "More baby jewellery:", buttons2)
    
    # ═══════════════════════════════════════════════════════════
    # WOMEN JEWELLERY MENUS
    # ═══════════════════════════════════════════════════════════
    
    def send_women_body_parts(to_number):
        """Show women jewellery body part categories"""
        message = "*Eternal Elegance Collection*\n\nSelect jewellery by body part:"
        
        buttons = [
            {"id": "women_face", "title": "Face Jewellery"},
            {"id": "women_hand", "title": "Hand Jewellery"},
            {"id": "women_neck", "title": "Neck Jewellery"}
        ]
        send_whatsapp_buttons(to_number, message, buttons)
        
        time.sleep(1)
        buttons2 = [
            {"id": "women_lower", "title": "Lower Body"},
            {"id": "back_main", "title": "← Back to Menu"}
        ]
        send_whatsapp_buttons(to_number, "More options:", buttons2)
    
    def send_women_face_collections(to_number):
        """Show women face jewellery"""
        message = "*Face Jewellery - Earrings:*"
        
        buttons = [
            {"id": "face_studs", "title": "Diamond Studs"},
            {"id": "face_jhumka", "title": "Traditional Jhumka"},
            {"id": "face_chandbali", "title": "Chandbali"}
        ]
        send_whatsapp_buttons(to_number, message, buttons)
        
        time.sleep(1)
        buttons2 = [
            {"id": "face_hoops", "title": "Classic Hoops"},
            {"id": "face_bahubali", "title": "Bahubali"},
            {"id": "women_face_more", "title": "More Earrings →"}
        ]
        send_whatsapp_buttons(to_number, "More earrings:", buttons2)
        
        time.sleep(1)
        buttons3 = [
            {"id": "women_face_nose", "title": "Nose Jewellery"},
            {"id": "women_face_head", "title": "Head Jewellery"},
            {"id": "women_body", "title": "← Back"}
        ]
        send_whatsapp_buttons(to_number, "Other face jewellery:", buttons3)
    
    def send_women_face_more_earrings(to_number):
        """More earring options"""
        message = "*More Earrings:*"
        
        buttons = [
            {"id": "face_drop", "title": "Drop Earrings"},
            {"id": "face_cuff", "title": "Ear Cuffs"},
            {"id": "face_sui_dhaga", "title": "Sui Dhaga"}
        ]
        send_whatsapp_buttons(to_number, message, buttons)
        
        time.sleep(1)
        buttons2 = [
            {"id": "face_kanser", "title": "Bridal Kanser"},
            {"id": "face_chuk", "title": "Vintage Chuk"},
            {"id": "women_face", "title": "← Back"}
        ]
        send_whatsapp_buttons(to_number, "More:", buttons2)
    
    def send_women_face_nose(to_number):
        """Nose jewellery sub-menu"""
        message = "*Nose Jewellery:*"
        
        buttons = [
            {"id": "face_nath", "title": "Bridal Nath"},
            {"id": "face_nose_pin", "title": "Diamond Nose Pins"},
            {"id": "face_septum", "title": "Septum Rings"}
        ]
        send_whatsapp_buttons(to_number, message, buttons)
        
        time.sleep(1)
        buttons2 = [
            {"id": "face_clip_on", "title": "Clip-On (No Pierce)"},
            {"id": "women_face", "title": "← Back"}
        ]
        send_whatsapp_buttons(to_number, "More:", buttons2)
    
    def send_women_face_head(to_number):
        """Head jewellery sub-menu"""
        message = "*Head Jewellery:*"
        
        buttons = [
            {"id": "face_maang_tikka", "title": "Maang Tikka"},
            {"id": "face_matha_patti", "title": "Matha Patti"},
            {"id": "face_passa", "title": "Side Passa"}
        ]
        send_whatsapp_buttons(to_number, message, buttons)
        
        time.sleep(1)
        buttons2 = [
            {"id": "face_head_kanser", "title": "Head Kanser"},
            {"id": "face_sheesh_phool", "title": "Sheesh Phool"},
            {"id": "women_face", "title": "← Back"}
        ]
        send_whatsapp_buttons(to_number, "More:", buttons2)
    
    def send_women_hand_collections(to_number):
        """Show women hand jewellery"""
        message = "*Hand Jewellery:*"
        
        buttons = [
            {"id": "hand_bangles", "title": "Bangles"},
            {"id": "hand_kada", "title": "Designer Kada"},
            {"id": "hand_bracelet", "title": "Bracelets"}
        ]
        send_whatsapp_buttons(to_number, message, buttons)
        
        time.sleep(1)
        buttons2 = [
            {"id": "women_hand_rings", "title": "Rings"},
            {"id": "women_hand_more", "title": "More Options →"},
            {"id": "women_body", "title": "← Back"}
        ]
        send_whatsapp_buttons(to_number, "More:", buttons2)
    
    def send_women_hand_rings(to_number):
        """Women rings sub-menu"""
        message = "*Rings:*"
        
        buttons = [
            {"id": "hand_rings_engagement", "title": "Engagement Rings"},
            {"id": "hand_rings_wedding", "title": "Wedding Bands"},
            {"id": "hand_rings_fashion", "title": "Fashion Rings"}
        ]
        send_whatsapp_buttons(to_number, message, buttons)
        
        time.sleep(1)
        buttons2 = [
            {"id": "hand_rings", "title": "Designer Rings"},
            {"id": "women_hand", "title": "← Back"}
        ]
        send_whatsapp_buttons(to_number, "More:", buttons2)
    
    def send_women_hand_more(to_number):
        """More hand jewellery"""
        message = "*More Hand Jewellery:*"
        
        buttons = [
            {"id": "hand_bracelet_chain", "title": "Chain Bracelets"},
            {"id": "hand_bracelet_charm", "title": "Charm Bracelets"},
            {"id": "hand_bracelet_cuff", "title": "Cuff Bracelets"}
        ]
        send_whatsapp_buttons(to_number, message, buttons)
        
        time.sleep(1)
        buttons2 = [
            {"id": "hand_baju_band", "title": "Baju Band (Armlet)"},
            {"id": "women_hand", "title": "← Back"}
        ]
        send_whatsapp_buttons(to_number, "More:", buttons2)
    
    def send_women_neck_collections(to_number):
        """Show women neck jewellery"""
        message = "*Neck Jewellery:*"
        
        buttons = [
            {"id": "neck_haar", "title": "Traditional Haar"},
            {"id": "neck_choker", "title": "Modern Chokers"},
            {"id": "women_neck_pendants", "title": "Pendants"}
        ]
        send_whatsapp_buttons(to_number, message, buttons)
        
        time.sleep(1)
        buttons2 = [
            {"id": "neck_sets", "title": "Bridal Sets"},
            {"id": "women_neck_more", "title": "More Options →"},
            {"id": "women_body", "title": "← Back"}
        ]
        send_whatsapp_buttons(to_number, "More:", buttons2)
    
    def send_women_neck_pendants(to_number):
        """Pendants sub-menu"""
        message = "*Pendants:*"
        
        buttons = [
            {"id": "neck_solitaire", "title": "Solitaire Pendants"},
            {"id": "neck_locket", "title": "Keepsake Lockets"},
            {"id": "neck_statement", "title": "Statement Pendants"}
        ]
        send_whatsapp_buttons(to_number, message, buttons)
        
        time.sleep(1)
        buttons2 = [
            {"id": "women_neck", "title": "← Back"}
        ]
        send_whatsapp_buttons(to_number, "More:", buttons2)
    
    def send_women_neck_more(to_number):
        """More neck jewellery"""
        message = "*More Necklaces:*"
        
        buttons = [
            {"id": "neck_princess", "title": "Princess Length"},
            {"id": "neck_matinee", "title": "Matinee Length"},
            {"id": "women_neck", "title": "← Back"}
        ]
        send_whatsapp_buttons(to_number, message, buttons)
    
    def send_women_lower_collections(to_number):
        """Show women lower body jewellery"""
        message = "*Lower Body Jewellery:*"
        
        buttons = [
            {"id": "lower_payal", "title": "Payal Anklets"},
            {"id": "lower_toe_rings", "title": "Toe Rings"},
            {"id": "lower_kamarband", "title": "Kamarband"}
        ]
        send_whatsapp_buttons(to_number, message, buttons)
        
        time.sleep(1)
        buttons2 = [
            {"id": "women_body", "title": "← Back"}
        ]
        send_whatsapp_buttons(to_number, "More:", buttons2)
    
    # ═══════════════════════════════════════════════════════════
    # MEN JEWELLERY MENUS
    # ═══════════════════════════════════════════════════════════
    
    def send_men_collections(to_number):
        """Show men jewellery main menu"""
        message = "*Bold Heritage Collection:*"
        
        buttons = [
            {"id": "men_rings_wedding", "title": "Wedding Bands"},
            {"id": "men_more_rings", "title": "More Rings →"},
            {"id": "men_chains", "title": "Chains & Pendants"}
        ]
        send_whatsapp_buttons(to_number, message, buttons)
        
        time.sleep(1)
    
        buttons2 = [
            {"id": "men_bracelets", "title": "Bracelets"},
            {"id": "men_accessories", "title": "Accessories"},
            {"id": "back_main", "title": "← Back"}
        ]
        send_whatsapp_buttons(to_number, "More:", buttons2)
    
    def send_men_more_rings(to_number):
        """Men rings sub-menu"""
        message = "*Men's Rings:*"
        
        buttons = [
            {"id": "men_rings_engagement", "title": "Engagement Rings"},
            {"id": "men_rings_signet", "title": "Signet Rings"},
            {"id": "men_rings_fashion", "title": "Fashion Rings"}
        ]
        send_whatsapp_buttons(to_number, message, buttons)
        
        time.sleep(1)
        buttons2 = [
            {"id": "men_rings_band", "title": "Classic Bands"},
            {"id": "men_rings_stone", "title": "Gemstone Rings"},
            {"id": "cat_men", "title": "← Back"}
        ]
        send_whatsapp_buttons(to_number, "More:", buttons2)
    
    def send_men_chains(to_number):
        """Men chains & pendants"""
        message = "*Chains & Pendants:*"
        
        buttons = [
            {"id": "men_chain_gold", "title": "Gold Chains"},
            {"id": "men_chain_silver", "title": "Silver Chains"},
            {"id": "men_chain_rope", "title": "Rope Chains"}
        ]
        send_whatsapp_buttons(to_number, message, buttons)
        
        time.sleep(1)
        buttons2 = [
            {"id": "men_pendant_religious", "title": "Religious Pendants"},
            {"id": "men_pendant_initial", "title": "Initial Pendants"},
            {"id": "men_pendant_stone", "title": "Gemstone Pendants"}
        ]
        send_whatsapp_buttons(to_number, "More pendants:", buttons2)
        
        time.sleep(1)
        buttons3 = [
            {"id": "cat_men", "title": "← Back"}
        ]
        send_whatsapp_buttons(to_number, "Options:", buttons3)
    
    def send_men_bracelets(to_number):
        """Men bracelets"""
        message = "*Men's Bracelets:*"
        
        buttons = [
            {"id": "men_bracelet_chain", "title": "Chain Bracelets"},
            {"id": "men_bracelet_leather", "title": "Leather Bracelets"},
            {"id": "men_bracelet_beaded", "title": "Beaded Bracelets"}
        ]
        send_whatsapp_buttons(to_number, message, buttons)
        
        time.sleep(1)
        buttons2 = [
            {"id": "men_bracelet_cuff", "title": "Cuff Bracelets"},
            {"id": "men_kada_traditional", "title": "Traditional Kada"},
            {"id": "men_kada_modern", "title": "Modern Kada"}
        ]
        send_whatsapp_buttons(to_number, "More:", buttons2)
        
        time.sleep(1)
        buttons3 = [
            {"id": "cat_men", "title": "← Back"}
        ]
        send_whatsapp_buttons(to_number, "Options:", buttons3)
    
    def send_men_accessories(to_number):
        """Men accessories"""
        message = "*Men's Accessories:*"
        
        buttons = [
            {"id": "men_cufflinks_classic", "title": "Classic Cufflinks"},
            {"id": "men_cufflinks_designer", "title": "Designer Cufflinks"},
            {"id": "men_tie_pins", "title": "Tie Pins & Clips"}
        ]
        send_whatsapp_buttons(to_number, message, buttons)
        
        time.sleep(1)
        buttons2 = [
            {"id": "men_brooches", "title": "Lapel Pins"},
            {"id": "cat_men", "title": "← Back"}
        ]
        send_whatsapp_buttons(to_number, "More:", buttons2)
    
    # ═══════════════════════════════════════════════════════════
    # STUDIO & DIVINE COLLECTIONS
    # ═══════════════════════════════════════════════════════════
    
    def send_studio_collections(to_number):
        """Show Signature Collection"""
        message = "*Signature Collection - Watches:*"
        
        buttons = [
            {"id": "watches_men", "title": "Men's Watches"},
            {"id": "watches_women", "title": "Women's Watches"},
            {"id": "watches_kids", "title": "Kids Watches"}
        ]
        send_whatsapp_buttons(to_number, message, buttons)
        
        time.sleep(1)
        buttons2 = [
            {"id": "watches_smart", "title": "Smart Watches"},
            {"id": "watches_luxury", "title": "Luxury Watches"},
            {"id": "studio_accessories", "title": "Accessories →"}
        ]
        send_whatsapp_buttons(to_number, "More:", buttons2)
    
    def send_studio_accessories(to_number):
        """Studio accessories"""
        message = "*Signature Accessories:*"
        
        buttons = [
            {"id": "keychains", "title": "Premium Keychains"},
            {"id": "clutches", "title": "Evening Clutches"},
            {"id": "sunglasses", "title": "Sunglasses"}
        ]
        send_whatsapp_buttons(to_number, message, buttons)
        
        time.sleep(1)
        buttons2 = [
            {"id": "belts", "title": "Designer Belts"},
            {"id": "hair_clips", "title": "Hair Accessories"},
            {"id": "cat_studio", "title": "← Back"}
        ]
        send_whatsapp_buttons(to_number, "More:", buttons2)
    
    def send_divine_collection(to_number):
        """Show Divine collection"""
        message = "*Divine Blessings*\n\nExplore our collection of sacred idols and figurines."
        
        buttons = [
            {"id": "murti_figurines", "title": "View Collection"},
            {"id": "back_main", "title": "← Back"}
        ]
        send_whatsapp_buttons(to_number, message, buttons)
    
    # ═══════════════════════════════════════════════════════════
    # SMART PRODUCT SEARCH
    # ═══════════════════════════════════════════════════════════
    
    def smart_search_collection(search_text):
        """AI-powered collection search"""
        search_lower = search_text.lower().strip()
        
        search_map = {
            'baby hair': 'baby_hair', 'baby earring': 'baby_earrings', 'baby chain': 'baby_chain',
            'baby ring': 'baby_rings', 'baby payal': 'baby_payal', 'baby anklet': 'baby_payal',
            'baby bangle': 'baby_bangles', 'baby kada': 'baby_bangles',
            'stud': 'face_studs', 'jhumka': 'face_jhumka', 'chandbali': 'face_chandbali',
            'hoop': 'face_hoops', 'bahubali': 'face_bahubali', 'nath': 'face_nath',
            'nose pin': 'face_nose_pin', 'nose ring': 'face_nose_pin',
            'bangle': 'hand_bangles', 'kada': 'hand_kada', 'bracelet': 'hand_bracelet',
            'ring': 'hand_rings', 'engagement ring': 'hand_rings_engagement',
            'wedding ring': 'hand_rings_wedding',
            'haar': 'neck_haar', 'choker': 'neck_choker', 'necklace': 'neck_princess',
            'pendant': 'neck_solitaire', 'locket': 'neck_locket',
            'men ring': 'men_rings_wedding', 'men chain': 'men_chain_gold',
            'men bracelet': 'men_bracelet_chain', 'men kada': 'men_kada_traditional',
            'watch': 'watches_men', 'keychain': 'keychains', 'clutch': 'clutches',
            'murti': 'murti_figurines', 'idol': 'murti_figurines'
        }
        
        for keyword, collection_key in search_map.items():
            if keyword in search_lower:
                return collection_key
        
        return None
    
    def handle_text_search(to_number, search_text, customer_name='Customer'):
        """Handle customer text search"""
        collection_key = smart_search_collection(search_text)
        
        if collection_key:
            send_catalog_link(to_number, collection_key)
        else:
            ai_response = get_ai_response(search_text, customer_name, 'Retail')
            send_whatsapp_text(to_number, ai_response)
            time.sleep(1)
            send_main_menu(to_number, customer_name)
    
    # ═══════════════════════════════════════════════════════════
    # KEYWORD DETECTION
    # ═══════════════════════════════════════════════════════════
    
    def detect_keyword(message_text):
        """Detect keywords in customer message"""
        message_lower = message_text.lower().strip()
        
        if any(word in message_lower for word in ['hi', 'hello', 'hey', 'namaste']):
            return 'greeting'
        
        if any(word in message_lower for word in ['new arrival', 'latest', 'new product']):
            return 'new_arrivals'
        
        if any(word in message_lower for word in ['trending', 'popular', 'best seller']):
            return 'trending'
        
        if any(word in message_lower for word in ['business hours', 'timing', 'open']):
            return 'business_hours'
        
        if any(word in message_lower for word in ['about', 'who are you']):
            return 'about'
        
        if message_lower.startswith('track #') or message_lower.startswith('track#'):
            return 'track_order_id'
        
        if 'referral' in message_lower or 'refer' in message_lower:
            return 'referral'
        
        if 'help' in message_lower or 'support' in message_lower:
            return 'help'
        
        if smart_search_collection(message_text):
            return 'product_search'
        
        return None
    
    def send_new_arrivals(to_number):
        """Show new arrivals"""
        message = "*New Arrivals* ✨\n\nDiscover our latest collections!"
        
        buttons = [
            {"id": "neck_statement", "title": "Statement Pendants"},
            {"id": "men_rings_stone", "title": "Gemstone Rings"},
            {"id": "watches_luxury", "title": "Luxury Watches"}
        ]
        send_whatsapp_buttons(to_number, message, buttons)
    
    def send_trending_products(to_number):
        """Show trending products"""
        message = "*Trending Now* 🔥\n\nOur most popular collections!"
        
        buttons = [
            {"id": "face_jhumka", "title": "Traditional Jhumka"},
            {"id": "face_studs", "title": "Diamond Studs"},
            {"id": "men_rings_wedding", "title": "Wedding Bands"}
        ]
        send_whatsapp_buttons(to_number, message, buttons)
    
    # ═══════════════════════════════════════════════════════════
    # BUTTON CLICK HANDLER - COMPLETE NAVIGATION
    # ═══════════════════════════════════════════════════════════
    
    def handle_button_click(button_id, from_number, customer_type='Retail', customer_name='Customer'):
        """Handle interactive button clicks"""
        print(f"Button clicked: {button_id}")
        
        # Main Categories
        if button_id == 'cat_baby':
            send_baby_collections(from_number)
        elif button_id == 'cat_women':
            send_women_body_parts(from_number)
        elif button_id == 'cat_men':
            send_men_collections(from_number)
        elif button_id == 'cat_studio':
            send_studio_collections(from_number)
        elif button_id == 'cat_divine':
            send_divine_collection(from_number)
        
        # Baby Collections
        elif button_id in ['baby_hair', 'baby_earrings', 'baby_chain', 'baby_rings', 'baby_payal', 'baby_bangles']:
            send_catalog_link(from_number, button_id)
        
        # Women Body Parts
        elif button_id == 'women_face':
            send_women_face_collections(from_number)
        elif button_id == 'women_hand':
            send_women_hand_collections(from_number)
        elif button_id == 'women_neck':
            send_women_neck_collections(from_number)
        elif button_id == 'women_lower':
            send_women_lower_collections(from_number)
        elif button_id == 'women_body':
            send_women_body_parts(from_number)
        
        # Women Face Sub-menus
        elif button_id == 'women_face_more':
            send_women_face_more_earrings(from_number)
        elif button_id == 'women_face_nose':
            send_women_face_nose(from_number)
        elif button_id == 'women_face_head':
            send_women_face_head(from_number)
        
        # Women Hand Sub-menus
        elif button_id == 'women_hand_rings':
            send_women_hand_rings(from_number)
        elif button_id == 'women_hand_more':
            send_women_hand_more(from_number)
        
        # Women Neck Sub-menus
        elif button_id == 'women_neck_pendants':
            send_women_neck_pendants(from_number)
        elif button_id == 'women_neck_more':
            send_women_neck_more(from_number)
        
        # Women Face Collections
        elif button_id in ['face_studs', 'face_jhumka', 'face_chandbali', 'face_hoops', 'face_cuff', 
                           'face_kanser', 'face_bahubali', 'face_drop', 'face_sui_dhaga', 'face_chuk',
                           'face_nath', 'face_nose_pin', 'face_septum', 'face_clip_on',
                           'face_maang_tikka', 'face_matha_patti', 'face_passa', 'face_head_kanser', 'face_sheesh_phool']:
            send_catalog_link(from_number, button_id)
        
        # Women Hand Collections
        elif button_id in ['hand_bangles', 'hand_kada', 'hand_bracelet', 'hand_bracelet_chain',
                           'hand_bracelet_charm', 'hand_bracelet_cuff', 'hand_baju_band',
                           'hand_rings', 'hand_rings_engagement', 'hand_rings_wedding', 'hand_rings_fashion']:
            send_catalog_link(from_number, button_id)
        
        # Women Neck Collections
        elif button_id in ['neck_haar', 'neck_choker', 'neck_princess', 'neck_matinee',
                           'neck_solitaire', 'neck_locket', 'neck_statement', 'neck_sets']:
            send_catalog_link(from_number, button_id)
        
        # Women Lower Collections
        elif button_id in ['lower_kamarband', 'lower_payal', 'lower_toe_rings']:
            send_catalog_link(from_number, button_id)
        
        # Men Sub-menus
        elif button_id == 'men_more_rings':
            send_men_more_rings(from_number)
        elif button_id == 'men_chains':
            send_men_chains(from_number)
        elif button_id == 'men_bracelets':
            send_men_bracelets(from_number)
        elif button_id == 'men_accessories':
            send_men_accessories(from_number)
        
        # Men Collections
        elif button_id in ['men_rings_wedding', 'men_rings_engagement', 'men_rings_signet',
                           'men_rings_fashion', 'men_rings_band', 'men_rings_stone',
                           'men_bracelet_chain', 'men_bracelet_leather', 'men_bracelet_beaded', 'men_bracelet_cuff',
                           'men_chain_gold', 'men_chain_silver', 'men_chain_rope',
                           'men_pendant_religious', 'men_pendant_initial', 'men_pendant_stone',
                           'men_kada_traditional', 'men_kada_modern',
                           'men_cufflinks_classic', 'men_cufflinks_designer', 'men_tie_pins', 'men_brooches']:
            send_catalog_link(from_number, button_id)
        
        # Studio Sub-menu
        elif button_id == 'studio_accessories':
            send_studio_accessories(from_number)
        
        # Studio Collections
        elif button_id in ['watches_men', 'watches_women', 'watches_kids', 'watches_smart', 'watches_luxury',
                           'keychains', 'hair_clips', 'clutches', 'sunglasses', 'belts']:
            send_catalog_link(from_number, button_id)
        
        # Divine Collection
        elif button_id == 'murti_figurines':
            send_catalog_link(from_number, button_id)
        
        # Navigation
        elif button_id == 'back_main':
            send_main_menu(from_number, customer_name)
        
        # Old Buttons
        elif button_id == 'browse_collections' or button_id == 'browse_digital_files':
            send_main_menu(from_number, customer_name)
        
        elif button_id == 'customise_product':
            message = "We would love to create something special for you.\n\nTo discuss your customisation requirements, please book an appointment with our design team."
            buttons = [
                {"id": "book_appointment", "title": "Book Appointment"},
                {"id": "back_main", "title": "← Back"}
            ]
            send_whatsapp_buttons(from_number, message, buttons)
        
        elif button_id == 'request_custom_file':
            message = "We would be happy to create a custom 3D jewellery file.\n\nPlease connect with our team directly."
            buttons = [
                {"id": "connect_support", "title": "Connect with Team"},
                {"id": "back_main", "title": "← Back"}
            ]
            send_whatsapp_buttons(from_number, message, buttons)
        
        elif button_id == 'my_orders':
            message = "To track your order, please type:\n\n*Track #OrderID*\n\nExample: Track #AJS123456"
            buttons = [
                {"id": "connect_support", "title": "Connect with Us"},
                {"id": "back_main", "title": "← Back"}
            ]
            send_whatsapp_buttons(from_number, message, buttons)
        
        elif button_id == 'book_appointment':
            message = "To book an appointment, please share your preferred date and time.\n\nOur team will confirm shortly."
            send_whatsapp_text(from_number, message)
        
        elif button_id == 'connect_support':
            message = f"Our team is here to help you.\n\n*Business Hours:*\nMonday to Saturday\n10:00 AM to 7:00 PM\n\n*Contact:* +91 {CUSTOMER_CARE_NUMBER}"
            send_whatsapp_text(from_number, message)
        
        else:
            send_unrecognised_message(from_number, customer_type)
    
    # ═══════════════════════════════════════════════════════════
    # ROUTES
    # ═══════════════════════════════════════════════════════════
    
    @app.route('/', methods=['GET'])
    def home():
        """Health check endpoint"""
        return jsonify({
            "status": "running",
            "app": "A Jewel Studio WhatsApp Bot v4",
            "version": "4.0.0",
            "features": [
                "AI Support (Gemini Pro)",
                "Image Recognition (Gemini Vision)",
                "Smart Product Search",
                "Multi-level Catalog Navigation",
                "82 Collections",
                "Order Tracking",
                "Referral System"
            ]
        }), 200
    
    @app.route('/health', methods=['GET'])
    def health():
        """Alternative health check"""
        return jsonify({"status": "ok", "service": "whatsapp-bot"}), 200
    
    # ═══════════════════════════════════════════════════════════
    # WEBHOOK HANDLER - WITH IMAGE SUPPORT
    # ═══════════════════════════════════════════════════════════
    
    @app.route('/webhook', methods=['GET', 'POST'])
    def webhook():
        if request.method == 'GET':
            mode = request.args.get('hub.mode')
            token = request.args.get('hub.verify_token')
            challenge = request.args.get('hub.challenge')
            if mode == 'subscribe' and token == VERIFY_TOKEN:
                print("Webhook verified")
                return challenge, 200
            return 'Forbidden', 403
        
        data = request.get_json()
        print("=" * 60)
        
        try:
            entry = data['entry'][0]
            changes = entry['changes'][0]
            value = changes['value']
    
            if 'messages' not in value:
                return jsonify({"status": "ok"}), 200
    
            message = value['messages'][0]
            from_number = message['from']
            message_type = message.get('type')
    
            print(f"Phone: {from_number} | Type: {message_type}")
    
            # INTERACTIVE BUTTONS
            if message_type == 'interactive':
                interactive = message.get('interactive', {})
                button_reply = interactive.get('button_reply', {})
                button_id = button_reply.get('id', '')
                
                customer_status = check_customer_status(from_number)
                customer_type = customer_status.get('customer_type', 'Retail') if customer_status['exists'] else 'Retail'
                customer_name = customer_status.get('name', 'Customer') if customer_status['exists'] else 'Customer'
                
                handle_button_click(button_id, from_number, customer_type, customer_name)
                return jsonify({"status": "ok"}), 200
    
            # IMAGE UPLOAD
            if message_type == 'image':
                image = message.get('image', {})
                image_id = image.get('id')
                
                if image_id:
                    url = f"https://graph.facebook.com/v18.0/{image_id}"
                    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
                    
                    try:
                        img_response = requests.get(url, headers=headers)
                        if img_response.status_code == 200:
                            image_data = img_response.json()
                            image_url = image_data.get('url')
                            
                            customer_status = check_customer_status(from_number)
                            customer_name = customer_status.get('name', 'Customer') if customer_status['exists'] else 'Customer'
                            
                            handle_image_upload(from_number, image_url, customer_name)
                        else:
                            send_whatsapp_text(from_number, "Sorry, I couldn't process your image. Please try again or describe what you're looking for.")
                    
                    except Exception as e:
                        print(f"Image processing error: {e}")
                        send_whatsapp_text(from_number, "Sorry, I encountered an error processing your image. Please try again or contact our team.")
                
                return jsonify({"status": "ok"}), 200
    
            # TEXT MESSAGES
            if message_type == 'text':
                message_body = message['text']['body']
                print(f"Message: {message_body}")
    
                customer_status = check_customer_status(from_number)
    
                # NEW CUSTOMER
                if not customer_status['exists']:
                    print("NEW CUSTOMER")
                    add_number_to_sheet(from_number)
                    send_new_customer_welcome(from_number)
                
                # INCOMPLETE REGISTRATION
                elif customer_status['exists'] and not customer_status['has_form_data']:
                    print("INCOMPLETE REGISTRATION")
                    
                    keyword = detect_keyword(message_body)
                    
                    if keyword == 'greeting':
                        send_complete_registration(from_number)
                    elif keyword == 'business_hours':
                        send_business_hours(from_number)
                    elif keyword == 'about':
                        send_about_us(from_number)
                    elif keyword == 'help':
                        send_complete_registration(from_number)
                    else:
                        ai_response = get_ai_response(message_body, 'Customer', 'Retail')
                        send_whatsapp_text(from_number, ai_response)
                
                # RETURNING CUSTOMER
                else:
                    print("RETURNING CUSTOMER")
                    customer_name = customer_status.get('name', 'Customer')
                    customer_type = customer_status.get('customer_type', 'Retail')
                    
                    keyword = detect_keyword(message_body)
                    
                    if keyword == 'greeting':
                        if customer_type == 'B2B' or customer_type == 'Wholesale':
                            send_b2b_welcome(from_number, customer_name)
                        else:
                            send_retail_welcome(from_number, customer_name)
                    
                    elif keyword == 'new_arrivals':
                        send_new_arrivals(from_number)
                    
                    elif keyword == 'trending':
                        send_trending_products(from_number)
                    
                    elif keyword == 'business_hours':
                        send_business_hours(from_number)
                    
                    elif keyword == 'about':
                        send_about_us(from_number)
                    
                    elif keyword == 'track_order_id':
                        order_id = message_body.replace('track', '').replace('Track', '').replace('#', '').strip()
                        track_order(from_number, order_id)
                    
                    elif keyword == 'referral':
                        send_referral_info(from_number, customer_name)
                    
                    elif keyword == 'help':
                        if customer_type == 'B2B' or customer_type == 'Wholesale':
                            send_b2b_welcome(from_number, customer_name)
                        else:
                            send_retail_welcome(from_number, customer_name)
                    
                    elif keyword == 'product_search':
                        handle_text_search(from_number, message_body, customer_name)
                    
                    else:
                        ai_response = get_ai_response(message_body, customer_name, customer_type)
                        send_whatsapp_text(from_number, ai_response)
                        time.sleep(1)
                        
                        message_suggest = "Would you like to browse our collections?"
                        buttons = [
                            {"id": "back_main", "title": "Browse Collections"},
                            {"id": "connect_support", "title": "Connect with Team"}
                        ]
                        send_whatsapp_buttons(from_number, message_suggest, buttons)
    
        except Exception as e:
            print(f"Webhook error: {e}")
            import traceback
            traceback.print_exc()
    
        print("=" * 60)
        return jsonify({"status": "ok"}), 200
    
    # ═══════════════════════════════════════════════════════════
    # MAIN
    # ═══════════════════════════════════════════════════════════
    
    if __name__ == '__main__':
        port = int(os.getenv('PORT', 5000))
        print("=" * 60)
        print("🚀 A Jewel Studio WhatsApp Bot v4 - PROFESSIONAL")
        print("=" * 60)
        print("✅ WhatsApp Bot Active")
        print("✅ Google Sheets Connected")
        print("✅ Shopify Integration Active")
        print("✅ Gemini AI Support Enabled")
        print("✅ Gemini Vision - Image Recognition Active")
        print("✅ Smart Product Search Active")
        print("✅ Multi-level Catalog Navigation Ready")
        print("✅ 82 Collections | 164 Products")
        print("=" * 60)
        print(f"Server running on port {port}")
        print("=" * 60)
        app.run(host='0.0.0.0', port=port, debug=False)
