# main.py - AJewel WhatsApp Bot Complete Flow with All Buttons
from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv
import json

load_dotenv()

app = Flask(__name__)

# Environment Variables
SHOPIFY_STORE = os.getenv('SHOPIFY_STORE')
SHOPIFY_ACCESS_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN')
WHATSAPP_TOKEN = os.getenv('ACCESS_TOKEN')
WHATSAPP_PHONE_ID = os.getenv('PHONE_NUMBER_ID')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN')
RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET')

# Shopify API Headers
SHOPIFY_HEADERS = {
    'X-Shopify-Access-Token': SHOPIFY_ACCESS_TOKEN,
    'Content-Type': 'application/json'
}

# User session storage (temporary - use database in production)
user_sessions = {}

# ==================== HELPER FUNCTIONS ====================

def send_whatsapp_message(phone_number, message):
    """Send text message via WhatsApp"""
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        'Authorization': f'Bearer {WHATSAPP_TOKEN}',
        'Content-Type': 'application/json'
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "text",
        "text": {"body": message}
    }
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

def send_whatsapp_buttons(phone_number, message, buttons):
    """Send interactive buttons (max 3)"""
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        'Authorization': f'Bearer {WHATSAPP_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    button_list = []
    for i, btn in enumerate(buttons[:3]):
        button_list.append({
            "type": "reply",
            "reply": {
                "id": f"btn_{i}_{btn.lower().replace(' ', '_')}",
                "title": btn[:20]  # Max 20 chars
            }
        })
    
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": message},
            "action": {"buttons": button_list}
        }
    }
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

def send_signup_button(phone_number, message):
    """Send sign-up button with Shopify registration link"""
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        'Authorization': f'Bearer {WHATSAPP_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    signup_url = f"https://{SHOPIFY_STORE}/account/register"
    
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "interactive",
        "interactive": {
            "type": "cta_url",
            "body": {"text": message},
            "action": {
                "name": "cta_url",
                "parameters": {
                    "display_text": "Sign Up",
                    "url": signup_url
                }
            }
        }
    }
    
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

def send_appointment_button(phone_number, message):
    """Send appointment booking button"""
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        'Authorization': f'Bearer {WHATSAPP_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    appointment_url = f"https://{SHOPIFY_STORE}/pages/appointment"
    
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "interactive",
        "interactive": {
            "type": "cta_url",
            "body": {"text": message},
            "action": {
                "name": "cta_url",
                "parameters": {
                    "display_text": "Book Appointment",
                    "url": appointment_url
                }
            }
        }
    }
    
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

def send_payment_button(phone_number, message, payment_link):
    """Send payment retry button"""
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        'Authorization': f'Bearer {WHATSAPP_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "interactive",
        "interactive": {
            "type": "cta_url",
            "body": {"text": message},
            "action": {
                "name": "cta_url",
                "parameters": {
                    "display_text": "Pay Now",
                    "url": payment_link
                }
            }
        }
    }
    
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

def send_download_button(phone_number, message, download_link):
    """Send download button for design files"""
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        'Authorization': f'Bearer {WHATSAPP_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "interactive",
        "interactive": {
            "type": "cta_url",
            "body": {"text": message},
            "action": {
                "name": "cta_url",
                "parameters": {
                    "display_text": "Click Here to Download",
                    "url": download_link
                }
            }
        }
    }
    
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

def send_list_message(phone_number, header, body, button_text, sections):
    """Send interactive list (for collections/categories)"""
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        'Authorization': f'Bearer {WHATSAPP_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": header},
            "body": {"text": body},
            "action": {
                "button": button_text,
                "sections": sections
            }
        }
    }
    
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

def send_catalogue(phone_number, catalogue_id):
    """Send WhatsApp catalogue"""
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        'Authorization': f'Bearer {WHATSAPP_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "interactive",
        "interactive": {
            "type": "catalog_message",
            "body": {"text": "Browse our products"},
            "action": {
                "name": "catalog_message",
                "parameters": {
                    "thumbnail_product_retailer_id": catalogue_id
                }
            }
        }
    }
    
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

# ==================== SHOPIFY FUNCTIONS ====================

def get_shopify_customer(phone):
    """Check if customer exists in Shopify"""
    url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/customers/search.json?query=phone:{phone}"
    response = requests.get(url, headers=SHOPIFY_HEADERS)
    data = response.json()
    
    if data.get('customers') and len(data['customers']) > 0:
        return data['customers'][0]
    return None

def get_shopify_collections():
    """Get all main collections"""
    url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/custom_collections.json"
    response = requests.get(url, headers=SHOPIFY_HEADERS)
    data = response.json()
    return data.get('custom_collections', [])

def get_collection_products(collection_id):
    """Get products from a collection"""
    url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/products.json?collection_id={collection_id}"
    response = requests.get(url, headers=SHOPIFY_HEADERS)
    data = response.json()
    return data.get('products', [])

def generate_razorpay_link(amount, customer_name, customer_phone, order_id):
    """Generate Razorpay payment link"""
    import base64
    
    url = "https://api.razorpay.com/v1/payment_links"
    auth = base64.b64encode(f"{RAZORPAY_KEY_ID}:{RAZORPAY_KEY_SECRET}".encode()).decode()
    
    headers = {
        'Authorization': f'Basic {auth}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        "amount": int(amount * 100),
        "currency": "INR",
        "description": f"A Jewel Studio - Order #{order_id}",
        "customer": {
            "name": customer_name,
            "contact": customer_phone
        },
        "notify": {
            "sms": True,
            "whatsapp": True
        },
        "callback_url": f"https://ajewel-whatsapp-bot.onrender.com/payment/callback",
        "callback_method": "get"
    }
    
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

# ==================== WEBHOOK ENDPOINTS ====================

@app.route('/')
def home():
    return "AJewel WhatsApp Bot is Running! 🚀"

@app.route('/webhook', methods=['GET', 'POST'])
def whatsapp_webhook():
    """WhatsApp webhook - Main entry point"""
    
    # Verification (GET request)
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            return challenge, 200
        return 'Forbidden', 403
    
    # Message handling (POST request)
    if request.method == 'POST':
        data = request.json
        
        try:
            entry = data['entry'][0]
            changes = entry['changes'][0]
            value = changes['value']
            
            if 'messages' in value:
                message = value['messages'][0]
                from_number = message['from']
                message_type = message['type']
                
                # Handle text messages
                if message_type == 'text':
                    text = message['text']['body'].strip().lower()
                    handle_text_message(from_number, text)
                
                # Handle button responses
                elif message_type == 'interactive':
                    interactive_type = message['interactive']['type']
                    
                    if interactive_type == 'button_reply':
                        button_id = message['interactive']['button_reply']['id']
                        button_title = message['interactive']['button_reply']['title']
                        handle_button_response(from_number, button_id, button_title)
                    
                    elif interactive_type == 'list_reply':
                        list_id = message['interactive']['list_reply']['id']
                        list_title = message['interactive']['list_reply']['title']
                        handle_list_response(from_number, list_id, list_title)
                
                # Handle order messages (catalogue orders)
                elif message_type == 'order':
                    order_data = message['order']
                    handle_order(from_number, order_data)
        
        except Exception as e:
            print(f"Error: {e}")
        
        return jsonify({"status": "ok"}), 200

def handle_text_message(phone, text):
    """Handle incoming text messages"""
    
    customer = get_shopify_customer(phone)
    
    if text in ['hi', 'hello', 'hey', 'start', 'menu']:
        if customer:
            # EXISTING CUSTOMER
            customer_name = customer.get('first_name', 'Customer')
            customer_tags = customer.get('tags', '')
            
            if 'B2B' in customer_tags or 'Wholesaler' in customer_tags:
                # B2B CUSTOMER FLOW
                message = f"Hello {customer_name}! Welcome to A Jewel Studio 💎"
                send_whatsapp_buttons(phone, message, ["Menu"])
                
            else:
                # RETAIL CUSTOMER FLOW
                message = f"Hello {customer_name}! Welcome to A Jewel Studio 💎\n\nKya aap Custom Jewellery karvana chahte hain?"
                send_whatsapp_buttons(phone, message, ["Yes", "No"])
        else:
            # NEW CUSTOMER - Registration Flow
            message = "Welcome to A Jewel Studio! 💎\n\nOrder karne ke liye pehle account banana hoga.\n\nNeeche diye gaye button se sign-up karein:"
            send_signup_button(phone, message)
    
    else:
        send_whatsapp_message(phone, "Main aapki madad ke liye yahan hoon! 'Hi' type karein to start karein.")

def handle_button_response(phone, button_id, button_title):
    """Handle button click responses"""
    
    customer = get_shopify_customer(phone)
    customer_name = customer.get('first_name', 'Customer') if customer else 'Customer'
    customer_tags = customer.get('tags', '') if customer else ''
    
    # RETAIL - Custom Jewellery (Yes)
    if 'yes' in button_id.lower():
        message = f"Thank you {customer_name} for choosing us! 💍\n\nPlease Appointment book karein:"
        send_appointment_button(phone, message)
    
    # RETAIL - Browse Products (No)
    elif 'no' in button_id.lower() or 'menu' in button_id.lower():
        show_main_collections(phone, customer_name)
    
    # Select Product Button
    elif 'select_product' in button_id.lower():
        collection_id = user_sessions.get(phone, {}).get('selected_collection')
        if collection_id:
            show_sub_collections(phone, collection_id)

def handle_list_response(phone, list_id, list_title):
    """Handle list selection responses"""
    
    # Main Collection Selected
    if 'collection_' in list_id:
        collection_id = list_id.replace('collection_', '')
        user_sessions[phone] = {'selected_collection': collection_id}
        
        message = f"You selected: {list_title}\n\nClick below to select products:"
        send_whatsapp_buttons(phone, message, ["Select Product"])
    
    # Sub-Collection Selected - Show Catalogue
    elif 'subcollection_' in list_id:
        subcollection_id = list_id.replace('subcollection_', '')
        
        # Send catalogue
        message = "Here's our catalogue for your selected category:"
        send_whatsapp_buttons(phone, message, ["Catalogue"])
        
        # Store for later
        user_sessions[phone]['subcollection'] = subcollection_id

def show_main_collections(phone, customer_name):
    """Show main collections list"""
    collections = get_shopify_collections()
    
    if not collections:
        send_whatsapp_message(phone, "Sorry, collections load nahi ho paye. Please try again later.")
        return
    
    # Prepare list sections
    rows = []
    for col in collections[:10]:  # Max 10 items
        rows.append({
            "id": f"collection_{col['id']}",
            "title": col['title'][:24],  # Max 24 chars
            "description": col.get('body_html', '')[:72] if col.get('body_html') else ""
        })
    
    sections = [{
        "title": "Categories",
        "rows": rows
    }]
    
    send_list_message(
        phone,
        "A Jewel Studio",
        f"Hello {customer_name}! Select a category:",
        "Menu",
        sections
    )

def show_sub_collections(phone, collection_id):
    """Show sub-collections for selected main collection"""
    products = get_collection_products(collection_id)
    
    if not products:
        send_whatsapp_message(phone, "No products found in this category.")
        return
    
    # Group by product type (sub-categories)
    sub_categories = {}
    for product in products:
        product_type = product.get('product_type', 'Other')
        if product_type not in sub_categories:
            sub_categories[product_type] = []
        sub_categories[product_type].append(product)
    
    # Prepare list
    rows = []
    for sub_cat, prods in list(sub_categories.items())[:10]:
        rows.append({
            "id": f"subcollection_{sub_cat}",
            "title": sub_cat[:24],
            "description": f"{len(prods)} products"
        })
    
    sections = [{
        "title": "Sub-Categories",
        "rows": rows
    }]
    
    send_list_message(
        phone,
        "Select Sub-Category",
        "Choose a sub-category to view products:",
        "Select Product",
        sections
    )

def handle_order(phone, order_data):
    """Handle catalogue order placement"""
    customer = get_shopify_customer(phone)
    
    if not customer:
        send_whatsapp_message(phone, "Please register first by sending 'Hi'")
        return
    
    customer_name = customer.get('first_name', 'Customer')
    customer_tags = customer.get('tags', '')
    
    # Extract order details
    product_items = order_data.get('product_items', [])
    
    if 'B2B' in customer_tags or 'Wholesaler' in customer_tags:
        # B2B - Payment Required
        # Calculate total (dummy calculation - implement proper logic)
        total_amount = len(product_items) * 1000  # Example
        
        # Generate payment link
        payment_response = generate_razorpay_link(
            total_amount,
            customer_name,
            phone,
            f"ORDER_{phone}_{len(product_items)}"
        )
        
        if payment_response.get('short_url'):
            message = f"Thank you {customer_name}!\n\nTotal Amount: ₹{total_amount}\n\nPlease complete payment:"
            send_payment_button(phone, message, payment_response['short_url'])
        else:
            send_whatsapp_message(phone, "Payment link generation failed. Please contact support.")
    
    else:
        # RETAIL - No Payment, Manual Follow-up
        message = f"Thank you {customer_name} for choosing your products! 💎\n\n"
        message += "A Jewel Studio ki team aapse estimated cost, discounts, offers aur payment ki jankari ke liye jald hi contact karegi.\n\n"
        message += f"Your Order Details:\n"
        for item in product_items:
            message += f"• {item.get('product_retailer_id', 'Product')}\n"
        
        send_whatsapp_message(phone, message)

# ==================== PAYMENT WEBHOOKS ====================

@app.route('/payment/callback', methods=['GET', 'POST'])
def payment_callback():
    """Handle Razorpay payment status"""
    
    if request.method == 'GET':
        # Payment success redirect
        payment_id = request.args.get('razorpay_payment_id')
        payment_link_id = request.args.get('razorpay_payment_link_id')
        
        return "Payment successful! Check WhatsApp for confirmation."
    
    if request.method == 'POST':
        # Webhook from Razorpay
        data = request.json
        
        if data.get('event') == 'payment_link.paid':
            # Payment successful
            payment_link = data['payload']['payment_link']['entity']
            customer_phone = payment_link['customer']['contact']
            
            # Send success message with download link
            message = "✅ Payment Successful!\n\n"
            message += "Thank you for doing Business with A Jewel Studio! 💎\n\n"
            message += "Aapki Design File aapke registered Email ID pe bhej di gayi hai.\n\n"
            
            download_link = f"https://{SHOPIFY_STORE}/account/orders"  # Example
            send_download_button(customer_phone, message, download_link)
        
        elif data.get('event') == 'payment_link.cancelled' or data.get('event') == 'payment_link.expired':
            # Payment failed
            payment_link = data['payload']['payment_link']['entity']
            customer_phone = payment_link['customer']['contact']
            
            message = "❌ Your Payment was not successful.\n\nPlease click the Pay Now button to retry:"
            send_payment_button(customer_phone, message, payment_link['short_url'])
        
        return jsonify({"status": "ok"}), 200

# ==================== RUN SERVER ====================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
