from flask import Flask
from datetime import datetime
import pytz

app = Flask(__name__)

# ---------------- GLOBAL STORAGE ----------------

user_sessions = {}

IST = pytz.timezone("Asia/Kolkata")

# ---------------- SAFE WRAPPER ----------------

def safe_send(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        print("Error:", e)
        return None

# ---------------- ORDER ID GENERATOR ----------------

def generate_order_id():
    return f"AJS{datetime.now(IST).strftime('%Y%m%d%H%M%S')}"

# ---------------- PROFESSIONAL MESSAGE TEMPLATES ----------------

def send_greeting(to):
    safe_send(
        send_button_message,
        to,
        "Welcome to *A Jewel Studio*\n"
        "Where Creativity Meets Craftsmanship.\n\n"
        "Namaste,\n"
        "Main Akshay bol raha hoon.\n\n"
        "A Jewel Studio visit karne ke liye aapka dhanyavaad.\n\n"
        "Aage badhne ke liye niche *Menu* select karein.",
        [{"id": "menu", "title": "Menu"}]
    )


def send_registration(to):
    safe_send(
        send_cta_button,
        to,
        "It appears that you are visiting us for the first time.\n\n"
        "Seamless aur personalized experience ke liye\n"
        "hum aapko account create karne ki salah dete hain.\n\n"
        "*Registered Customer Benefits:*\n"
        "• Faster Order Processing\n"
        "• Easy Order Tracking\n"
        "• Priority Updates on Latest Designs\n\n"
        "Kindly complete the registration process.\n"
        "Registration complete hone ke baad kindly \"Hi\" type karke conversation restart karein.",
        "Sign Up",
        SHOPIFY_REGISTER
    )


def send_catalog(to):
    safe_send(
        send_cta_button,
        to,
        "Kindly explore our *Exclusive Collection*.\n\n"
        "Niche button click karke apni preferred category select karein.",
        "View Catalog",
        CATALOG_LINK
    )


def send_customer_type(to):
    safe_send(
        send_button_message,
        to,
        "Order process karne ke liye kripya apna *Customer Type* select karein.",
        [
            {"id": "retail", "title": "Retail Customer"},
            {"id": "b2b", "title": "B2B / Wholesale"}
        ]
    )


def send_retail_confirmation(to, session):

    order_id = generate_order_id()

    cart = session.get("cart_items") or []
    cart_text = ", ".join(map(str, cart)) if cart else "-"

    msg = (
        "Thank you for choosing *A Jewel Studio*.\n\n"
        "Aapki order request successfully receive ho chuki hai.\n\n"
        "Hamari team jald hi aapse contact karegi.\n\n"
        "We appreciate your trust in us."
    )

    safe_send(send_message, to, msg)

    now_str = datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S")

    safe_send(save_to_sheet, [
        now_str,
        order_id,
        "Retail",
        session.get("name", ""),
        to,
        session.get("contact", ""),
        session.get("email", ""),
        "",
        "",
        session.get("address", ""),
        session.get("city", ""),
        session.get("main_title", ""),
        session.get("sub_title", ""),
        cart_text,
        "New"
    ])


def send_b2b_payment(to, session):

    order_id = generate_order_id()
    amount = 500

    if to not in user_sessions:
        user_sessions[to] = {}

    user_sessions[to].update({
        "order_id": order_id,
        "step": "payment_pending",
        "amount": amount
    })

    cart = session.get("cart_items") or []
    cart_text = ", ".join(map(str, cart)) if cart else "-"

    now_str = datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S")

    safe_send(save_to_sheet, [
        now_str,
        order_id,
        "B2B",
        session.get("name", ""),
        to,
        session.get("contact", ""),
        session.get("email", ""),
        session.get("company", ""),
        session.get("gst", ""),
        session.get("address", ""),
        session.get("city", ""),
        session.get("main_title", ""),
        session.get("sub_title", ""),
        cart_text,
        "Payment Pending"
    ])

    pay_link = create_razorpay_link(
        amount,
        order_id,
        session.get("name", ""),
        session.get("contact", "")
    )

    if pay_link and isinstance(pay_link, str):
        safe_send(
            send_cta_button,
            to,
            f"Your Order is Ready for Payment.\n\n"
            f"*Order ID:* #{order_id}\n\n"
            f"*Amount:* ₹{amount:,.2f}\n\n"
            f"Kindly click below to complete secure payment.",
            "Proceed to Payment",
            pay_link
        )
    else:
        safe_send(send_message, to,
                  "Payment link generate karne mein issue aaya hai. Kindly contact support.")


def send_b2b_success(to, order_id, amount):

    now = datetime.now(IST)
    date_str = now.strftime("%d/%m/%Y")

    msg = (
        "Payment Successfully Received.\n\n"
        "Thank you for doing business with *A Jewel Studio*.\n\n"
        "----------------------------------\n"
        f"*Order ID:* #{order_id}\n"
        f"*Amount:* ₹{amount:,.2f}\n"
        f"*Date:* {date_str}\n"
        "----------------------------------\n\n"
        "If you require any assistance, please feel free to contact us."
    )

    safe_send(send_message, to, msg)

    safe_send(
        send_cta_button,
        to,
        "Your digital files are ready.\nKindly click below to download.",
        "Download Now",
        SHOPIFY_DOWNLOADS
    )

    safe_send(update_sheet_status, order_id, "Paid")


def send_b2b_failed(to, order_id, pay_link):

    safe_send(
        send_cta_button,
        to,
        "Your payment was not completed.\n\n"
        "Kindly retry using the button below.\n"
        "Your order is still active.",
        "Retry Payment",
        pay_link
    )

    safe_send(update_sheet_status, order_id, "Payment Failed")
