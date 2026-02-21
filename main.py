# ---------------- PROFESSIONAL MESSAGE TEMPLATES ----------------

def send_greeting(to):
    send_button_message(
        to,
        "Welcome to *A Jewel Studio*\n"
        " \n\n"
        "Namaste,\n"
        "Main Akshay bol raha hoon.\n\n"
        "A Jewel Studio visit karne ke liye aapka dhanyavaad.\n\n"
        "Aage badhne ke liye niche *Menu* select karein.",
        [{"id": "menu", "title": "Menu"}]
    )


def send_registration(to):
    send_cta_button(
        to,
        "It appears that you are visiting us for the first time.\n\n"
        "Seamless aur personalized experience ke liye\n"
        "hum aapko account create karne ki salah dete hain.\n\n"
        "*Registered Customer Benefits:*\n"
        "• Faster Order Processing\n"
        "• Easy Order Tracking\n"
        "• Priority Updates on Latest Designs\n\n"
        "Kindly complete the registration process.\n"
        "Registration ke baad 'Hi' type karein.",
        "Sign Up",
        SHOPIFY_REGISTER
    )


def send_catalog(to):
    send_cta_button(
        to,
        "Kindly explore our *Exclusive Collection*.\n\n"
        "Niche button click karke apni preferred category select karein.",
        "View Catalog",
        CATALOG_LINK
    )


def send_customer_type(to):
    send_button_message(
        to,
        "Order process karne ke liye kripya apna *Customer Type* select karein.",
        [
            {"id": "retail", "title": "Retail Customer"},
            {"id": "b2b",    "title": "B2B / Wholesale"}
        ]
    )


def send_retail_confirmation(to, session):
    order_id  = generate_order_id()
    name      = session.get("name", "")
    main_cat  = session.get("main_title", "")
    sub_cat   = session.get("sub_title", "")
    phone     = session.get("contact", "")
    email     = session.get("email", "")
    address   = session.get("address", "")
    city      = session.get("city", "")
    cart      = session.get("cart_items", [])
    cart_text = ", ".join(cart) if cart else "-"

    msg = (
        "Thank you for choosing *A Jewel Studio*.\n\n"
        "Aapki order request successfully receive ho chuki hai.\n\n"
        "Hamari team jald hi aapse contact karegi taaki following details confirm ki ja sake:\n\n"
        "• Design Selection\n"
        "• Pricing Details\n"
        "• Delivery Timeline\n\n"
        "Hum aapko premium craftsmanship aur seamless buying experience dene ke liye committed hain.\n\n"
        "We appreciate your trust in us."
    )
    send_message(to, msg)

    now_str = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    save_to_sheet([
        now_str, order_id, "Retail", name, to, phone, email,
        "", "", address, city, main_cat, sub_cat, cart_text, "New"
    ])


def send_b2b_payment(to, session):
    order_id = generate_order_id()
    name     = session.get("name", "")
    phone    = session.get("contact", "")
    amount   = 500

    user_sessions[to]["order_id"] = order_id
    user_sessions[to]["step"]     = "payment_pending"
    user_sessions[to]["amount"]   = amount

    now_str  = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    main_cat = session.get("main_title", "")
    sub_cat  = session.get("sub_title", "")
    email    = session.get("email", "")
    company  = session.get("company", "")
    gst      = session.get("gst", "")
    address  = session.get("address", "")
    city     = session.get("city", "")
    cart     = session.get("cart_items", [])
    cart_text = ", ".join(cart) if cart else "-"

    save_to_sheet([
        now_str, order_id, "B2B", name, to, phone, email,
        company, gst, address, city, main_cat, sub_cat, cart_text, "Payment Pending"
    ])

    pay_link = create_razorpay_link(amount, order_id, name, phone)

    if pay_link:
        send_cta_button(
            to,
            f"Your Order is Ready for Payment.\n\n"
            f"*Order ID:* #{order_id}\n\n"
            f"Kindly click the button below to complete the secure payment process.",
            "Proceed to Payment",
            pay_link
        )
    else:
        send_message(to, "Payment link generate karne mein issue aaya hai. Kindly contact support.")


def send_b2b_success(to, order_id, amount):
    now      = datetime.now()
    date_str = now.strftime("%d/%m/%Y")

    msg = (
        "Payment Successfully Received.\n\n"
        "Thank you for doing business with *A Jewel Studio*.\n\n"
        "Your selected 3D digital file has been shared on your registered Email ID and WhatsApp number.\n\n"
        "----------------------------------\n"
        f"*Order ID:* #{order_id}\n"
        f"*Amount:* ₹{amount}\n"
        f"*Date:* {date_str}\n"
        "----------------------------------\n\n"
        "If you require any assistance, please feel free to contact us."
    )
    send_message(to, msg)

    send_cta_button(
        to,
        "Your digital files are ready.\nKindly click below to download.",
        "Download Now",
        SHOPIFY_DOWNLOADS
    )

    update_sheet_status(order_id, "Paid")


def send_b2b_failed(to, order_id, pay_link):
    send_cta_button(
        to,
        "Your payment was not completed.\n\n"
        "Kindly retry using the button below.\n"
        "Your order is still active.",
        "Retry Payment",
        pay_link
    )
    update_sheet_status(order_id, "Payment Failed")
