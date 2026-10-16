import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MONGO_URI = os.getenv("MONGO_URI", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

MAX_FSUB_CHANNELS = 6
DELETE_AFTER = 10 * 60   # file auto-delete time (seconds)
SWEEP_INTERVAL = 20      # how often to check for due deletes (seconds)
