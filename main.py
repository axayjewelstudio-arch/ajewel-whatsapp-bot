# Line 1-10: Imports
import os
from flask import Flask, request, jsonify
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Line 11-20: Environment variables
SHOPIFY_STORE = os.getenv('SHOPIFY_STORE')
SHOPIFY_ACCESS_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN')
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN')
WHATSAPP_PHONE_ID = os.getenv('WHATSAPP_PHONE_ID')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN')

# Line 21-60: Check customer exists in Shopify
def check_customer_exists(phone_number):
    """Check if customer exists in Shopify by phone number"""
    url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/graphql.json"
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
        "Content-Type": "application/json"
    }
    
    # Format phone number for Shopify (add +91 if not present)
    if not phone_number.startswith('+'):
        phone_number = f"+{phone_number}"
    
    query = """
    query getCustomer($query: String!) {
      customers(first: 1, query: $query) {
        edges {
          node {
            id
            firstName
            lastName
            phone
            email
            createdAt
          }
        }
      }
    }
    """
    
    variables = {
        "query": f"phone:{phone_number}"
    }
    
    try:
        response = requests.post(url, json={"query": query, "variables": variables}, headers=headers)
        data = response.json()
        
        if data.get('data', {}).get('customers', {}).get('edges'):
            customer = data['data']['customers']['edges'][0]['node']
            return {
                'exists': True,
                'customer': customer
            }
        else:
            return {'exists': False, 'customer': None}
    except Exception as e:
        print(f"Error checking customer: {str(e)}")
        return {'exists': False, 'customer': None}

# Line 61-100: Send WhatsApp message (UPDATED)
def send_whatsapp_message(to_number, message_text):
    """Send message via WhatsApp Business API"""
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
        print(f"Sending message to {to_number}: {message_text}")
        response = requests.post(url, json=payload, headers=headers)
        result = response.json()
        print(f"WhatsApp API Response: {result}")
        
        if response.status_code == 200:
            print("Message sent successfully!")
        else:
            print(f"Error sending message: {result}")
        
        return result
    except Exception as e:
        print(f"Error sending WhatsApp message: {str(e)}")
        return None

# Line 101-150: WhatsApp webhook endpoint
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        # Verification for WhatsApp webhook
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            print("Webhook verified successfully!")
            return challenge, 200
        else:
            print("Webhook verification failed!")
            return 'Forbidden', 403
    
    elif request.method == 'POST':
        # Handle incoming WhatsApp messages
        data = request.get_json()
        
        try:
            # Extract message details
            if 'entry' in data:
                entry = data['entry'][0]
                changes = entry['changes'][0]
                value = changes['value']
                
                # Check if message exists
                if 'messages' in value:
                    message = value['messages'][0]
                    from_number = message['from']
                    
                    # Check if it's a text message
                    if message['type'] == 'text':
                        message_body = message['text']['body']
                        
                        print(f"Received message from {from_number}: {message_body}")
                        
                        # Check if customer exists in Shopify
                        result = check_customer_exists(from_number)
                        
                        if result['exists']:
                            # Old customer - Reply "Yes"
                            customer = result['customer']
                            customer_name = customer.get('firstName', 'Customer')
                            response_text = f"Yes ✅\n\nWelcome back {customer_name}! 🙏"
                            print(f"Old customer found: {customer_name}")
                        else:
                            # New customer - Reply "No"
                            response_text = "No ❌\n\nYou are a new customer. Welcome to A.Jewel.Studio! 👋"
                            print(f"New customer: {from_number}")
                        
                        # Send WhatsApp reply
                        send_whatsapp_message(from_number, response_text)
        
        except Exception as e:
            print(f"Error processing webhook: {str(e)}")
        
        return jsonify({"status": "ok"}), 200

# Line 151-160: Health check endpoint
@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "running",
        "app": "AJewelBot v2",
        "message": "WhatsApp bot is active"
    }), 200

# Line 161-165: Run the app
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"Starting AJewelBot on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=True)
