@app.route("/webhook", methods=["GET", "POST"])
def webhook():

    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge"), 200
        return "Error", 403

    data = request.get_json()
    if not data:
        return "No data", 200

    try:
        print("=== WEBHOOK DEBUG ===")
        print(f"Full data: {data}")
        
        value = data["entry"][0]["changes"][0]["value"]
        print(f"Value: {value}")
        
        # Check if messages exist
        if "messages" not in value:
            print("⚠️ No messages - status update")
            return "No message event", 200
        
        print(f"Messages found: {value['messages']}")
        
        phone = value["contacts"][0]["wa_id"]
        msg = value["messages"][0]
        msg_type = msg["type"]
        
        print(f"📱 Phone: {phone}, Type: {msg_type}")
        
        if msg_type == "text":
            text = msg["text"]["body"]
            print(f"💬 Text: {text}")

        # First time user
        if phone not in user_state:
            print(f"🆕 New session for {phone}")
            cust = find_shopify_customer_by_phone(phone)
            print(f"👤 Customer found: {cust is not None}")
            
            if not cust:
                print("📤 Sending Join Us button")
                interactive_cta_url(
                    phone,
                    "Welcome to A.Jewel.Studio! 💎\n\nPlease create your account to get started.",
                    "Join Us",
                    f"https://{SHOPIFY_STORE}/pages/join-us"
                )
                user_state[phone] = {"flow": "new"}
                return "New user", 200
            else:
                # Greeting with name
                name = f"{cust.first_name or ''} {cust.last_name or ''}".strip() or "Valued Customer"
                print(f"👋 Greeting customer: {name}")
                text_message(phone, f"Hello {name}! 👋\n\nWelcome back to A.Jewel.Studio! 💎")
                
                user_state[phone] = {"flow": "wholesale" if is_wholesaler(cust) else "retail"}

                if is_wholesaler(cust):
                    print("📦 Sending catalog (wholesale)")
                    catalog_message(phone)
                else:
                    print("💍 Asking about custom jewellery (retail)")
                    interactive_reply_buttons(
                        phone,
                        "Kya aap Custom Jewellery karvana chahte hain?",
                        [
                            {"id": "yes_custom", "title": "Yes"},
                            {"id": "no_custom", "title": "No"}
                        ]
                    )
                return "Existing user", 200

        state = user_state.get(phone)

        # Button reply
        if msg_type == "button":
            button_id = msg["button"]["payload"]
            print(f"🔘 Button clicked: {button_id}")

            if state["flow"] == "retail":
                if button_id == "yes_custom":
                    interactive_cta_url(
                        phone,
                        "Book consultation below.",
                        "Book Now",
                        f"https://{SHOPIFY_STORE}/products/custom-jewellery-consultation"
                    )
                else:
                    catalog_message(phone)
@app.route("/payment/webhook", methods=["POST"])
def payment_webhook():
    signature = request.headers.get("X-Razorpay-Signature")
    data = request.get_json()

    if not verify_signature(data, signature):
        return "Invalid", 400

    phone = order_map.get(data.get("razorpay_payment_link_id"))

    if data.get("razorpay_payment_link_status") == "paid":
        text_message(phone, "Payment Successful! 🎉")
    else:
        text_message(phone, "Payment Failed. Please retry.")


    @app.route("/payment/webhook", methods=["POST"])
def payment_webhook():
    signature = request.headers.get("X-Razorpay-Signature")
    data = request.get_json()

    if not verify_signature(data, signature):
        return "Invalid", 400

    phone = order_map.get(data.get("razorpay_payment_link_id"))

    if data.get("razorpay_payment_link_status") == "paid":
        text_message(phone, "Payment Successful! 🎉")
    else:
        text_message(phone, "Payment Failed. Please retry.")

    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)

    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)

        # Order
        if msg_type == "order":
            print("🛒 Order received")
            items = msg["order"]["product_items"]
            total = sum(float(i["item_price"]) * int(i["quantity"]) for i in items)
            link = create_payment_link(int(total * 100), phone, "Order Payment")
            interactive_cta_url(phone, f"Total ₹{total}", "Pay Now", link["short_url"])

        return "OK", 200

    except Exception as e:
        print(f"❌ Error: {e}")
        app.logger.error(str(e))
        return "Error", 500
