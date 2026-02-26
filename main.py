# AJewelBot v2 - WhatsApp Bot + Auto Shopify Sync
import os
import json
from flask import Flask, request, jsonify
import requests
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials
import threading
import time
import schedule

load_dotenv()
app = Flask(__name__)

# Environment variables
SHOPIFY_STORE = os.getenv('SHOPIFY_STORE')
SHOPIFY_ACCESS_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN')
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN')
WHATSAPP_PHONE_ID = os.getenv('WHATSAPP_PHONE_ID')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN')
GOOGLE_CREDENTIALS = os.getenv('GOOGLE_CREDENTIALS')

SHEET_ID = "1w-4Zi65AqsQZFJIr1GLrDrW9BJNez8Wtr-dTL8oBLbs"
JOIN_US_URL = "https://a-jewel-studio-3.myshopify.com/pages/join-us"

def get_google_sheet():
    """Connect to Google Sheet"""
    try:
        creds_dict = json.loads(GOOGLE_CREDENTIALS)
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).sheet1
        return sheet
    except Exception as e:
        print(f"Google Sheets Error: {str(e)}")
        return None

# ========== SHOPIFY SYNC FUNCTIONS ==========

def get_all_customers_from_shopify():
    """Fetch all customers from Shopify"""
    url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/graphql.json"
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
        "Content-Type": "application/json"
    }
    
    query = """
    query getCustomers($cursor: String) {
      customers(first: 50, after: $cursor) {
        pageInfo {
          hasNextPage
          endCursor
        }
        edges {
          node {
            id
            firstName
            lastName
            phone
            email
            tags
            defaultAddress {
              address1
              city
              province
            }
          }
        }
      }
    }
    """
    
    all_customers = []
    cursor = None
    
    try:
        response = requests.post(url, json={"query": query, "variables": {"cursor": cursor}}, headers=headers)
        data = response.json()
        
        if 'data' in data and 'customers' in data['data']:
            edges = data['data']['customers']['edges']
            for edge in edges:
                all_customers.append(edge['node'])
            print(f"Fetched {len(all_customers)} customers from Shopify")
        
        return all_customers
    except Exception as e:
        print(f"Shopify fetch error: {str(e)}")
        return []

def sync_shopify_to_sheet():
    """Sync Shopify customers to Google Sheet"""
    print("Starting Shopify to Sheet sync...")
    
    customers = get_all_customers_from_shopify()
    if not customers:
        print("No customers to sync")
        return
    
    sheet = get_google_sheet()
    if not sheet:
        return
    
    try:
        column_b = sheet.col_values(2)
    except:
        column_b = []
    
    updated = 0
    added = 0
    
    for customer in customers:
        phone = customer.get('phone', '')
        if not phone:
            continue
        
        first_name = customer.get('firstName', '')
        last_name = customer.get('lastName', '')
        full_name = f"{first_name} {last_name}".strip()
        email = customer.get('email', '')
        tags = ', '.join(customer.get('tags', []))
        
        customer_type = 'Retail'
        if 'wholesale' in tags.lower():
            customer_type = 'Wholesale'
        
        address_obj = customer.get('defaultAddress', {})
        city = address_obj.get('city', '')
        state = address_obj.get('province', '')
        
        if phone in column_b:
            row_index = column_b.index(phone) + 1
            try:
                sheet.update(f'A{row_index}', [[full_name]])
                sheet.update(f'C{row_index}', [[customer_type]])
                sheet.update(f'E{row_index}', [[email]])
                sheet.update(f'I{row_index}', [[city]])
                sheet.update(f'J{row_index}', [[state]])
                updated += 1
            except:
                pass
        else:
            try:
                row = [full_name, phone, customer_type, phone, email, customer_type, '', '', city, state, tags, '', '', '']
                sheet.append_row(row)
                added += 1
            except:
                pass
        
        time.sleep(0.3)
    
    print(f"Sync complete! Updated: {updated}, Added: {added}")

def run_scheduled_sync():
    """Run sync every 3 hours"""
    schedule.every(3).hours.do(sync_shopify_to_sheet)
    
    # Run immediately on start
    sync_shopify_to_sheet()
    
    while True:
        schedule.run_pending()
        time.sleep(60)

# ========== WHATSAPP BOT FUNCTIONS ==========

def get_customer_name_from_sheet(phone_number):
    """Get customer name from Google Sheet"""
    try:
        sheet = get_google_sheet()
        if sheet:
            column_b = sheet.col_values(2)  # Phone numbers
            if phone_number in column_b:
                row_index = column_b.index(phone_number) + 1
                column_a = sheet.col_values(1)  # Names
                if len(column_a) >= row_index:
                    name = column_a[row_index - 1]
                    return {'exists': True, 'name': name}
        return {'exists': False, 'name': None}
    except Exception as e:
        print(f"Sheet check error: {str(e)}")
        return {'exists': False, 'name': None}

def add_number_to_sheet(phone_number):
    """Add new number to Column B"""
    try:
        sheet = get_google_sheet()
        if sheet:
            sheet.append_row(['', phone_number])
            print(f"Added number: {phone_number}")
            return True
    except Exception as e:
        print(f"Sheet add error: {str(e)}")
    return False

def send_whatsapp_text(to_number, message_text):
    """Send simple text message"""
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
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            print(f"Message sent to {to_number}")
        return response.json()
    except Exception as e:
        print(f"WhatsApp error: {str(e)}")
        return None

def send_whatsapp_button(to_number, body_text, button_text, button_url):
    """Send message with URL button"""
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "interactive",
        "interactive": {
            "type": "cta_url",
            "body": {
                "text": body_text
            },
            "action": {
                "name": "cta_url",
                "parameters": {
                    "display_text": button_text,
                    "url": button_url
                }
            }
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            print(f"Button message sent to {to_number}")
            return response.json()
        else:
            print(f"Button failed, sending text fallback")
            fallback_text = f"{body_text}\n\n{button_text}: {button_url}"
            return send_whatsapp_text(to_number, fallback_text)
    except Exception as e:
        print(f"WhatsApp button error: {str(e)}")
        fallback_text = f"{body_text}\n\n{button_text}: {button_url}"
        return send_whatsapp_text(to_number, fallback_text)

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "running",
        "app": "AJewelBot v2",
        "message": "WhatsApp bot with auto Shopify sync every 3 hours"
    }), 200

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            print("Webhook verified successfully")
            return challenge, 200
        return 'Forbidden', 403
    
    elif request.method == 'POST':
        data = request.get_json()
        
        print("=" * 60)
        print("NEW MESSAGE RECEIVED")
        print("=" * 60)
        
        try:
            if 'entry' in data:
                entry = data['entry'][0]
                changes = entry['changes'][0]
                value = changes['value']
                
                if 'messages' in value:
                    message = value['messages'][0]
                    from_number = message['from']
                    
                    if message['type'] == 'text':
                        message_body = message['text']['body']
                        
                        print(f"Phone: {from_number}")
                        print(f"Message: {message_body}")
                        
                        # Check if customer exists
                        customer_data = get_customer_name_from_sheet(from_number)
                        
                        if customer_data['exists']:
                            # Existing customer - welcome with name
                            customer_name = customer_data['name']
                            print(f"EXISTING CUSTOMER: {customer_name}")
                            
                            response_text = f"Welcome back {customer_name}!\n\nHow can we help you today?"
                            send_whatsapp_text(from_number, response_text)
                        else:
                            # New customer - add to sheet + send Join Us button
                            print(f"NEW CUSTOMER")
                            add_number_to_sheet(from_number)
                            
                            body_text = "Welcome to A.Jewel.Studio!\n\nJoin our community to get exclusive updates and offers."
                            button_text = "Join Us"
                            
                            send_whatsapp_button(from_number, body_text, button_text, JOIN_US_URL)
                        
                        print("=" * 60)
        
        except Exception as e:
            print(f"Error: {str(e)}")
            print("=" * 60)
        
        return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    # Start background sync thread
    sync_thread = threading.Thread(target=run_scheduled_sync, daemon=True)
    sync_thread.start()
    print("Background sync started - runs every 3 hours")
    
    # Start Flask app
    port = int(os.getenv('PORT', 5000))
    print(f"Starting AJewelBot v2 on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)
