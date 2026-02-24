def check_customer_exists(phone):
    """Check if customer exists in Shopify - flexible phone matching"""
    try:
        # Try multiple phone formats
        phone_variants = [
            phone,                           # +917600056655
            phone.replace('+', ''),          # 917600056655
            phone.replace('+91', ''),        # 7600056655
            f"+91{phone.replace('+91', '').replace('+', '')}"  # Normalize to +91
        ]
        
        print(f"🔍 Checking customer with variants: {phone_variants}")
        
        query = """
        query($query: String!) {
            customers(first: 10, query: $query) {
                edges {
                    node {
                        id
                        firstName
                        lastName
                        email
                        phone
                    }
                }
            }
        }
        """
        
        # Try each phone variant
        for variant in phone_variants:
            variables = {"query": f"phone:{variant}"}
            response = requests.post(
                SHOPIFY_GRAPHQL_URL,
                json={'query': query, 'variables': variables},
                headers=SHOPIFY_HEADERS
            )
            
            print(f"📊 Shopify response for {variant}: {response.json()}")
            
            data = response.json().get('data', {})
            customers = data.get('customers', {}).get('edges', [])
            
            if customers:
                customer = customers[0]['node']
                name = f"{customer.get('firstName', '')} {customer.get('lastName', '')}".strip()
                print(f"✅ Customer found: {name}")
                return {
                    'status': 'existing',
                    'name': name or 'Valued Customer',
                    'email': customer.get('email'),
                    'phone': customer.get('phone')
                }
        
        print("👤 Customer not found in any format")
        return {'status': 'new'}
        
    except Exception as e:
        print(f"❌ Error checking customer: {e}")
        return {'status': 'new'}


def send_greeting(phone, name):
    """Send personalized greeting to existing customer"""
    message = f"Hello {name}! 👋\n\nWelcome back to A.Jewel.Studio! 💎\n\nHow can we help you today?"
    
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": message}
    }
    
    print(f"📤 Sending greeting to {name} at {phone}")
    
    response = requests.post(
        WHATSAPP_API_URL,
        headers=WHATSAPP_HEADERS,
        json=payload
    )
    
    print(f"📥 Greeting response: {response.json()}")
    return response.json()


# Update webhook handler
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        print("=== DEBUG START ===")
        print(f"Received data: {data}")
        print("=== DEBUG END ===")
        
        if 'entry' in data:
            for entry in data['entry']:
                for change in entry.get('changes', []):
                    value = change.get('value', {})
                    
                    if 'messages' in value:
                        messages = value['messages']
                        for message in messages:
                            phone = message['from']
                            msg_type = message.get('type')
                            
                            print(f"📱 Phone: {phone}, Type: {msg_type}")
                            
                            if msg_type == 'text':
                                text = message['text']['body'].lower().strip()
                                print(f"💬 Text received: '{text}'")
                                
                                if text == 'hi' or text == 'hello' or text == 'hey':
                                    print(f"✅ Processing '{text}' command")
                                    
                                    # Check customer
                                    print(f"🔍 Checking customer: +{phone}")
                                    customer_status = check_customer_exists(f"+{phone}")
                                    print(f"👤 Customer check result: {customer_status}")
                                    
                                    if customer_status['status'] == 'existing':
                                        # Send personalized greeting
                                        print(f"👋 Existing customer - sending greeting")
                                        send_greeting(phone, customer_status['name'])
                                    else:
                                        # New customer - send signup button
                                        print(f"🆕 New customer - sending signup button")
                                        send_signup_button(phone)
                    else:
                        print("⚠️ No messages - might be status update")
        
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        print(f"❌ Error in webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
