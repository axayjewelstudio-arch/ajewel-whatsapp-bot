# ═══════════════════════════════════════════════════════════
# WEBHOOK HANDLER - Enhanced with Phase 3 Features
# ═══════════════════════════════════════════════════════════

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming messages with Phase 3 features"""
    try:
        cleanup_old_sessions()
        data = request.get_json()
        
        if not data or data.get('object') != 'whatsapp_business_account':
            return jsonify({'status': 'ok'}), 200
        
        entry = data.get('entry', [{}])[0]
        changes = entry.get('changes', [{}])[0]
        value = changes.get('value', {})
        messages = value.get('messages', [])
        
        if not messages:
            return jsonify({'status': 'ok'}), 200
        
        message = messages[0]
        from_number = message.get('from')
        message_type = message.get('type')
        
        if not validate_phone_number(from_number):
            return jsonify({'status': 'ok'}), 200
        
        # Customer detection
        customer_data = detect_customer_status(from_number)
        session = update_session_customer_data(from_number, customer_data)
        
        # Handle message
        if message_type == 'text':
            message_text = message.get('text', {}).get('body', '')
            sanitized_text = sanitize_input(message_text)
            
            # Check for duplicates
            if is_duplicate_message(from_number, sanitized_text):
                return jsonify({'status': 'ok'}), 200
            
            log_message_type(from_number, 'text', sanitized_text)
            
            # Send welcome image for new customers
            if customer_data['status'] == 'new' and LOGO_IMAGE_URL:
                send_whatsapp_image(
                    from_number,
                    LOGO_IMAGE_URL,
                    caption="Welcome to\n\n*A Jewel Studio*"
                )
                time.sleep(typing_delay(20))
            
            # Response with formatting
            if customer_data['status'] == 'new':
                join_url = f"{JOIN_US_URL}?wa={from_number}"
                send_whatsapp_cta_button(
                    from_number,
                    "✨ Welcome to *A Jewel Studio*!\n\nTap Join Us below to explore our exclusive collections.",
                    "Join Us",
                    join_url
                )
            
            elif customer_data['status'] == 'incomplete_registration':
                message = f"👋 Hello!\n\n⚠️ I see you started registration but didn't complete it.\n\nWould you like to complete your registration?"
                buttons = [
                    {'id': 'complete_reg', 'title': 'Complete Now'},
                    {'id': 'browse', 'title': 'Browse Catalog'},
                    {'id': 'help', 'title': 'Need Help'}
                ]
                send_whatsapp_buttons(from_number, message, buttons)
            
            elif customer_data['status'] in ['returning_retail', 'returning_b2b']:
                customer_name = session['customer_name']
                message = f"👋 Welcome back, {format_bold(customer_name)}!\n\nHow can I assist you today?"
                
                buttons = [
                    {'id': 'menu', 'title': 'Menu'}
                ]
                send_whatsapp_buttons(from_number, message, buttons)
        
        elif message_type == 'interactive':
            # Handle button clicks
            interactive = message.get('interactive', {})
            button_reply = interactive.get('button_reply', {})
            button_id = button_reply.get('id', '')
            
            logger.info(f"🔘 Button clicked: {button_id}")
            send_whatsapp_text(from_number, f"✅ Button '{button_id}' received!\n\n_Phase 3 - Button handler active_")
        
        elif message_type == 'image':
            log_message_type(from_number, 'image', 'Image received')
            send_whatsapp_text(from_number, "📸 Image received! Processing coming in Phase 4...")
        
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        handle_error(e, "webhook")
        return jsonify({'status': 'error'}), 500

# ═══════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════

@app.route('/', methods=['GET'])
@app.route('/health', methods=['GET'])
def health_check():
    """Health check"""
    status = {
        'status': 'healthy',
        'service': 'A Jewel Studio WhatsApp Bot',
        'phase': 'Phase 3 - Messaging & UX',
        'features': 40,
        'timestamp': datetime.now().isoformat(),
        'active_sessions': len(user_sessions),
        'environment': {
            'whatsapp_token': '✅ Set' if WHATSAPP_TOKEN else '❌ Missing',
            'whatsapp_phone_id': '✅ Set' if WHATSAPP_PHONE_ID else '❌ Missing',
            'shopify_token': '✅ Set' if SHOPIFY_ACCESS_TOKEN else '❌ Missing',
            'google_sheets': '✅ Set' if GOOGLE_SERVICE_ACCOUNT_KEY else '❌ Missing'
        }
    }
    return jsonify(status), 200

# ═══════════════════════════════════════════════════════════
# SECURITY HEADERS
# ═══════════════════════════════════════════════════════════

@app.after_request
def add_security_headers(response):
    """Add security headers"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

# ═══════════════════════════════════════════════════════════
# ERROR HANDLERS
# ═══════════════════════════════════════════════════════════

@app.errorhandler(404)
def not_found(error):
    return jsonify({'status': 'error', 'message': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'status': 'error', 'message': 'Internal error'}), 500

# ═══════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════

if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    
    logger.info("=" * 60)
    logger.info("🚀 Phase 3 - Messaging & UX")
    logger.info("=" * 60)
    logger.info("✅ Phase 1: 15 features")
    logger.info("✅ Phase 2: 10 features")
    logger.info("✅ Phase 3: 15 features")
    logger.info("   - Interactive Buttons ✅")
    logger.info("   - CTA URL Buttons ✅")
    logger.info("   - List Messages ✅")
    logger.info("   - Image Messages ✅")
    logger.info("   - Message Formatting ✅")
    logger.info("   - Typing Delays ✅")
    logger.info("   - Welcome Image ✅")
    logger.info("   - Message Chunking ✅")
    logger.info("   - Emoji Support ✅")
    logger.info("   - Bold Text ✅")
    logger.info("   - Professional Tone ✅")
    logger.info("   - Message Fallback ✅")
    logger.info("   - Loop Prevention ✅")
    logger.info("   - Concise Responses ✅")
    logger.info("   - Error Messages ✅")
    logger.info("=" * 60)
    logger.info("📊 TOTAL: 40 Features Active")
    logger.info("=" * 60)
    
    app.run(host='0.0.0.0', port=port, debug=False)
