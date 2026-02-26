# Simple WhatsApp Bot - Test Version
import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# Environment variables
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN', 'ajewel2024')

# Home endpoint
@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "running",
        "app": "AJewelBot v2 - Test Mode",
        "message": "Bot is active and ready to receive messages"
    }), 200

# WhatsApp webhook
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        # Webhook verification
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            print("✅ Webhook verified successfully!")
            return challenge, 200
        else:
            print("❌ Webhook verification failed!")
            return 'Forbidden', 403
    
    elif request.method == 'POST':
        # Receive WhatsApp messages
        data = request.get_json()
        
        print("=" * 50)
        print("📩 NEW MESSAGE RECEIVED!")
        print("=" * 50)
        
        try:
            if 'entry' in data:
                entry = data['entry'][0]
                changes = entry['changes'][0]
                value = changes['value']
                
                if 'messages' in value:
                    message = value['messages'][0]
                    from_number = message['from']
                    message_type = message['type']
                    
                    if message_type == 'text':
                        message_body = message['text']['body']
                        
                        print(f"📱 From: {from_number}")
                        print(f"💬 Message: {message_body}")
                        print(f"⏰ Time: {message.get('timestamp', 'N/A')}")
                        print("=" * 50)
                    else:
                        print(f"📎 Message Type: {message_type}")
                        print("=" * 50)
                else:
                    print("ℹ️ No message in webhook data")
                    print("=" * 50)
        
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            print("=" * 50)
        
        return jsonify({"status": "ok"}), 200

# Run the app
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"🚀 Starting AJewelBot Test Mode on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=True)
