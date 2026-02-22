# main.py
from flask import Flask, request, redirect, session
import requests
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Environment variables
SHOPIFY_CLIENT_ID = os.getenv('SHOPIFY_CLIENT_ID')
SHOPIFY_CLIENT_SECRET = os.getenv('SHOPIFY_CLIENT_SECRET')
SHOPIFY_STORE = os.getenv('SHOPIFY_STORE')
SCOPES = 'read_products,write_products,read_customers,write_customers,read_orders,write_orders'
REDIRECT_URI = 'https://ajewel-whatsapp-bot.onrender.com/auth/callback'

# Step 1: Install URL
@app.route('/install')
def install():
    auth_url = f"https://{SHOPIFY_STORE}/admin/oauth/authorize"
    params = {
        'client_id': SHOPIFY_CLIENT_ID,
        'scope': SCOPES,
        'redirect_uri': REDIRECT_URI
    }
    url = f"{auth_url}?client_id={params['client_id']}&scope={params['scope']}&redirect_uri={params['redirect_uri']}"
    return redirect(url)

# Step 2: Callback - Exchange code for token
@app.route('/auth/callback')
def callback():
    code = request.args.get('code')
    
    # Exchange code for access token
    token_url = f"https://{SHOPIFY_STORE}/admin/oauth/access_token"
    payload = {
        'client_id': SHOPIFY_CLIENT_ID,
        'client_secret': SHOPIFY_CLIENT_SECRET,
        'code': code
    }
    
    response = requests.post(token_url, json=payload)
    data = response.json()
    
    access_token = data.get('access_token')
    
    # Save token (print for now)
    print(f"ACCESS TOKEN: {access_token}")
    
    # Save to file
    with open('token.txt', 'w') as f:
        f.write(access_token)
    
    return f"Token received! Check logs or token.txt file. Token: {access_token}"

# Home route
@app.route('/')
def home():
    return "AJewel WhatsApp Bot is running!"

if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
