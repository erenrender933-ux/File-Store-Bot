import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MONGO_URI = os.getenv("MONGO_URI", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
DB_CHANNEL_ID = int(os.getenv("DB_CHANNEL_ID", "0"))  # e.g. -100xxxxxxxxxx

MAX_FSUB_CHANNELS = 6
DELETE_AFTER = 10 * 60   # auto-delete time (seconds)
SWEEP_INTERVAL = 20      # how often to check due deletes (seconds)
BATCH_LIMIT = 200        # max files in one batch link
