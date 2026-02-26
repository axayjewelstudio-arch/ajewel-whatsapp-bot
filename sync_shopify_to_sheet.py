# sync_shopify_to_sheet.py - Sync Shopify to Google Sheet every 3 hours
import os
import json
import requests
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
import time
import schedule

load_dotenv()

SHOPIFY_STORE = os.getenv('SHOPIFY_STORE')
SHOPIFY_ACCESS_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN')
GOOGLE_CREDENTIALS = os.getenv('GOOGLE_CREDENTIALS')
SHEET_ID = "1w-4Zi65AqsQZFJIr1GLrDrW9BJNez8Wtr-dTL8oBLbs"

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
        print(f"❌ Google Sheets Error: {str(e)}")
        return None

def get_all_customers_from_shopify():
    """Fetch all customers from Shopify with complete details"""
    url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/graphql.json"
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
        "Content-Type": "application/json"
    }
    
    query = """
    query getCustomers($cursor: String) {
      customers(first: 250, after: $cursor) {
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
              address2
              city
              province
              zip
              country
            }
            metafields(first: 20) {
              edges {
                node {
                  namespace
                  key
                  value
                }
              }
            }
          }
        }
      }
    }
    """
    
    all_customers = []
    cursor = None
    has_next_page = True
    
    try:
        while has_next_page:
            variables = {"cursor": cursor}
            response = requests.post(url, json={"query": query, "variables": variables}, headers=headers)
            data = response.json()
            
            if 'data' in data and 'customers' in data['data']:
                customers_data = data['data']['customers']
                edges = customers_data['edges']
                
                for edge in edges:
                    all_customers.append(edge['node'])
                
                page_info = customers_data['pageInfo']
                has_next_page = page_info['hasNextPage']
                cursor = page_info.get('endCursor')
                
                print(f"📥 Fetched {len(edges)} customers... Total: {len(all_customers)}")
            else:
                break
        
        print(f"✅ Total customers fetched: {len(all_customers)}")
        return all_customers
    
    except Exception as e:
        print(f"❌ Shopify fetch error: {str(e)}")
        return []

def sync_to_sheet():
    """Sync Shopify customers to Google Sheet"""
    print("🔄 Starting Shopify → Sheet sync...")
    
    # Get customers from Shopify
    customers = get_all_customers_from_shopify()
    
    if not customers:
        print("⚠️ No customers to sync")
        return
    
    # Get Google Sheet
    sheet = get_google_sheet()
    if not sheet:
        print("❌ Could not connect to Google Sheet")
        return
    
    # Get existing phone numbers from column B
    try:
        column_b = sheet.col_values(2)  # Column B (Phone numbers)
        print(f"📊 Found {len(column_b)} existing entries in sheet")
    except:
        column_b = []
    
    updated_count = 0
    added_count = 0
    
    for customer in customers:
        phone = customer.get('phone', '')
        
        if not phone:
            continue  # Skip customers without phone
        
        # Prepare customer data
        first_name = customer.get('firstName', '')
        last_name = customer.get('lastName', '')
        full_name = f"{first_name} {last_name}".strip()
        email = customer.get('email', '')
        tags = ', '.join(customer.get('tags', []))
        
        # Customer type from tags
        customer_type = 'Retail'
        if 'wholesale' in tags.lower() or 'b2b' in tags.lower():
            customer_type = 'Wholesale'
        
        # Address
        address_obj = customer.get('defaultAddress', {})
        address = f"{address_obj.get('address1', '')} {address_obj.get('address2', '')}".strip()
        city = address_obj.get('city', '')
        state = address_obj.get('province', '')
        
        # Metafields
        metafields = customer.get('metafields', {}).get('edges', [])
        gst_number = ''
        gender = ''
        age_group = ''
        
        for mf in metafields:
            node = mf['node']
            key = node['key']
            value = node['value']
            
            if key == 'gst_number':
                gst_number = value
            elif key == 'gender':
                gender = value
            elif key == 'age_group':
                age_group = value
        
        # Check if phone exists in sheet
        if phone in column_b:
            # Update existing row
            row_index = column_b.index(phone) + 1
            
            try:
                # Update columns A, C-N (skip B as it has phone)
                sheet.update(f'A{row_index}', [[full_name]])  # A: Customer Name
                sheet.update(f'C{row_index}', [[customer_type]])  # C: Customer Type
                sheet.update(f'D{row_index}', [[phone]])  # D: Phone
                sheet.update(f'E{row_index}', [[email]])  # E: Email
                sheet.update(f'F{row_index}', [[customer_type]])  # F: Customer Type (duplicate)
                sheet.update(f'G{row_index}', [[gst_number]])  # G: GST Number
                sheet.update(f'H{row_index}', [[address]])  # H: Address
                sheet.update(f'I{row_index}', [[city]])  # I: City
                sheet.update(f'J{row_index}', [[state]])  # J: State
                sheet.update(f'K{row_index}', [[tags]])  # K: Tags
                sheet.update(f'M{row_index}', [[gender]])  # M: Gender
                sheet.update(f'N{row_index}', [[age_group]])  # N: Age Group
                
                updated_count += 1
                print(f"✅ Updated: {full_name} ({phone})")
            except Exception as e:
                print(f"❌ Update error for {phone}: {str(e)}")
        else:
            # Add new row
            try:
                row = [
                    full_name,      # A: Customer Name
                    phone,          # B: Phone (WhatsApp)
                    customer_type,  # C: Customer Type
                    phone,          # D: Phone
                    email,          # E: Email
                    customer_type,  # F: Customer Type
                    gst_number,     # G: GST Number
                    address,        # H: Address
                    city,           # I: City
                    state,          # J: State
                    tags,           # K: Tags
                    '',             # L: Empty
                    gender,         # M: Gender
                    age_group       # N: Age Group
                ]
                
                sheet.append_row(row)
                added_count += 1
                print(f"➕ Added: {full_name} ({phone})")
            except Exception as e:
                print(f"❌ Add error for {phone}: {str(e)}")
        
        # Rate limiting - avoid API quota
        time.sleep(0.5)
    
    print("=" * 60)
    print(f"✅ Sync complete!")
    print(f"📊 Updated: {updated_count} customers")
    print(f"➕ Added: {added_count} customers")
    print("=" * 60)

def run_sync_job():
    """Run sync job"""
    try:
        sync_to_sheet()
    except Exception as e:
        print(f"❌ Sync job error: {str(e)}")

if __name__ == '__main__':
    print("🚀 Starting Shopify → Sheet Sync Service")
    print("⏰ Sync will run every 3 hours")
    print("=" * 60)
    
    # Run immediately on start
    run_sync_job()
    
    # Schedule to run every 3 hours
    schedule.every(3).hours.do(run_sync_job)
    
    # Keep running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute
