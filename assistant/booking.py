import csv
from datetime import datetime, timezone

from dateutil import parser

from .config import BOOKING_CLOSE_HOUR, BOOKING_DAYS, BOOKING_OPEN_HOUR, LEADS_CSV
from . import memory

LEADS_HEADER = ["user_id", "listing_id", "budget_aed", "requirements", "day", "time", "created_at"]


def slot_is_valid(day, time):
    if not day or not time:
        return False, "Please share a day (Monday to Saturday) and a time (8:00 AM to 8:00 PM)."
    if day.strip().capitalize() not in BOOKING_DAYS:
        return False, "Viewings run Monday to Saturday. Sundays aren't available; could you pick another day?"
    hour = _parse_hour(time)
    if hour is None:
        return False, "I couldn't read that time. Viewings run from 8:00 AM to 8:00 PM."
    if hour < BOOKING_OPEN_HOUR or hour >= BOOKING_CLOSE_HOUR:
        return False, "Viewing slots are between 8:00 AM and 8:00 PM. Could you pick a time in that window?"
    return True, ""


def _parse_hour(time):
    text = time.strip().lower()
    if "noon" in text:
        return 12
    if "midnight" in text:
        return 0
    try:
        return parser.parse(text, fuzzy=True).hour
    except (ValueError, OverflowError):
        return None


def find_conflict(user_id, day, time):
    target_day = (day or "").strip().capitalize()
    target_hour = _parse_hour(time or "")
    if target_hour is None:
        return None
    for lead in memory.get_leads(user_id):
        if (lead["day"] or "").strip().capitalize() == target_day and _parse_hour(lead["time"] or "") == target_hour:
            return lead
    return None


def cancel_lead(rowid):
    memory.delete_lead(rowid)
    rows = memory.all_leads()
    with open(LEADS_CSV, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEADS_HEADER)
        writer.writeheader()
        for r in rows:
            writer.writerow({
                "user_id": r["user_id"],
                "listing_id": r["listing_id"] if r["listing_id"] is not None else "",
                "budget_aed": r["budget_aed"] if r["budget_aed"] is not None else "",
                "requirements": r["requirements"] or "",
                "day": r["day"] or "",
                "time": r["time"] or "",
                "created_at": r["created_at"] or "",
            })


def record_lead(user_id, listing_id, budget_aed, requirements, day, time):
    memory.save_lead(user_id, listing_id, budget_aed, requirements, day, time)
    row = {
        "user_id": user_id,
        "listing_id": listing_id if listing_id is not None else "",
        "budget_aed": budget_aed if budget_aed is not None else "",
        "requirements": requirements or "",
        "day": day or "",
        "time": time or "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    exists = LEADS_CSV.exists()
    with open(LEADS_CSV, "a", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEADS_HEADER)
        if not exists:
            writer.writeheader()
        writer.writerow(row)
