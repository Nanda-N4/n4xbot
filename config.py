import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
MY_USER_ID = int(os.getenv("ADMIN_ID"))
ADMIN_LINK = os.getenv("ADMIN_LINK")

# Default Assets
IMG_WELCOME = 'assets/welcome.jpg'
