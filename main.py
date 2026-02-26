from dotenv import load_dotenv
import os

load_dotenv()

token = os.getenv("META_SYSTEM_USER_TOKEN")
print(token)
