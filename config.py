import os
from dotenv import load_dotenv

load_dotenv()

# data.gov.sg resource ID for HDB resale flat prices
RESOURCE_ID = "d_8b84c4ee58e3cfc0ece0d773c8ca6abc"
API_BASE = "https://data.gov.sg/api/action/datastore_search"

# How many months of history to backfill on first run
BACKFILL_MONTHS = 24

# Fetch page size (API max is 100)
PAGE_SIZE = 100

ALL_TOWNS = [
    "ANG MO KIO", "BEDOK", "BISHAN", "BUKIT BATOK", "BUKIT MERAH",
    "BUKIT PANJANG", "BUKIT TIMAH", "CENTRAL AREA", "CHOA CHU KANG",
    "CLEMENTI", "GEYLANG", "HOUGANG", "JURONG EAST", "JURONG WEST",
    "KALLANG/WHAMPOA", "MARINE PARADE", "PASIR RIS", "PUNGGOL",
    "QUEENSTOWN", "SEMBAWANG", "SENGKANG", "SERANGOON", "TAMPINES",
    "TOA PAYOH", "WOODLANDS", "YISHUN",
]

ALL_FLAT_TYPES = [
    "2 ROOM", "3 ROOM", "4 ROOM", "5 ROOM", "EXECUTIVE",
]

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# SQLite path
DB_PATH = os.getenv("DB_PATH", "hdb_tracker.db")
