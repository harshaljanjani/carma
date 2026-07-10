import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

CLEANED_CSV = BASE_DIR / "cleaned_dataset.csv"
ENRICHED_JSON = DATA_DIR / "enriched.json"
MEMORY_DB = DATA_DIR / "memory.db"
LEADS_CSV = DATA_DIR / "leads.csv"

MODEL = os.getenv("MODEL", "gemini/gemini-2.5-pro")
HAS_LLM = bool(os.getenv("GEMINI_API_KEY"))

BOOKING_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
ALL_DAYS = [d.lower() for d in BOOKING_DAYS] + ["sunday"]
BOOKING_OPEN_HOUR = 8
BOOKING_CLOSE_HOUR = 20

CURRENCY = "AED"
MAX_RESULTS = 5
