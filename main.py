# -------------------------------------------------
#   Shopify helpers
# -------------------------------------------------

def normalize(phone):
    return ''.join(filter(str.isdigit, phone))[-10:]


def find_shopify_customer_by_phone(phone: str):
    try:
        customers = shopify.Customer.search(query=f"phone:{phone}")
        for cust in customers:
            if cust.phone and normalize(cust.phone) == normalize(phone):
                return cust
    except Exception as e:
        app.logger.error(f"Shopify search error: {e}")
    return None


def add_whatsapp_tag(customer):
    existing_tags = customer.tags or ""
    tags = [tag.strip() for tag in existing_tags.split(",") if tag.strip()]
    
    if "whatsapp_verified" not in tags:
        tags.append("whatsapp_verified")
        customer.tags = ", ".join(tags)
        customer.save()


def has_whatsapp_tag(customer):
    if not customer or not customer.tags:
        return False

    tags = [tag.strip().lower() for tag in customer.tags.split(",")]
    return "whatsapp_verified" in tags


def is_wholesaler(customer):
    tags = (customer.tags or "").lower()
    return "wholesale" in tags
