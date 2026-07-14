import sqlite3
from datetime import datetime, timezone

from .config import MEMORY_DB
from .schemas import UserProfile

_SESSIONS = {}


def _connect():
    conn = sqlite3.connect(MEMORY_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                name TEXT,
                budget_aed INTEGER,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS preferences (
                user_id TEXT,
                preference TEXT,
                created_at TEXT,
                UNIQUE(user_id, preference)
            );
            CREATE TABLE IF NOT EXISTS liked_listings (
                user_id TEXT,
                listing_id INTEGER,
                created_at TEXT,
                UNIQUE(user_id, listing_id)
            );
            CREATE TABLE IF NOT EXISTS leads (
                user_id TEXT,
                listing_id INTEGER,
                budget_aed INTEGER,
                requirements TEXT,
                day TEXT,
                time TEXT,
                created_at TEXT
            );
            """
        )


def get_session(session_id, user_id=None):
    session = _SESSIONS.setdefault(
        session_id, {"history": [], "last_result_ids": [], "user_id": user_id}
    )
    if user_id:
        session["user_id"] = user_id
    return session


def append_turn(session_id, role, content):
    session = get_session(session_id)
    session["history"].append({"role": role, "content": content})
    session["history"] = session["history"][-20:]


def set_last_results(session_id, listing_ids):
    get_session(session_id)["last_result_ids"] = list(listing_ids)


def get_last_results(session_id):
    return get_session(session_id).get("last_result_ids", [])


def get_pending_booking(session_id):
    return get_session(session_id).get("pending_booking")


def set_pending_booking(session_id, data):
    get_session(session_id)["pending_booking"] = data


def clear_pending_booking(session_id):
    get_session(session_id)["pending_booking"] = None


def upsert_user(user_id, name=None, budget_aed=None):
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        existing = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if existing is None:
            conn.execute(
                "INSERT INTO users (user_id, name, budget_aed, created_at) VALUES (?, ?, ?, ?)",
                (user_id, name, budget_aed, now),
            )
        else:
            new_name = name or existing["name"]
            new_budget = budget_aed if budget_aed is not None else existing["budget_aed"]
            conn.execute(
                "UPDATE users SET name = ?, budget_aed = ? WHERE user_id = ?",
                (new_name, new_budget, user_id),
            )


def add_preference(user_id, preference):
    if not preference:
        return
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO preferences (user_id, preference, created_at) VALUES (?, ?, ?)",
            (user_id, preference, now),
        )


def add_liked(user_id, listing_id):
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO liked_listings (user_id, listing_id, created_at) VALUES (?, ?, ?)",
            (user_id, int(listing_id), now),
        )


def save_lead(user_id, listing_id, budget_aed, requirements, day, time):
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO leads (user_id, listing_id, budget_aed, requirements, day, time, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, listing_id, budget_aed, requirements, day, time, now),
        )


def get_leads(user_id):
    with _connect() as conn:
        rows = conn.execute(
            "SELECT rowid, listing_id, day, time FROM leads WHERE user_id = ? ORDER BY created_at", (user_id,)
        ).fetchall()
    return [{"rowid": r["rowid"], "listing_id": r["listing_id"], "day": r["day"], "time": r["time"]} for r in rows]


def delete_lead(rowid):
    with _connect() as conn:
        conn.execute("DELETE FROM leads WHERE rowid = ?", (rowid,))


def all_leads():
    with _connect() as conn:
        rows = conn.execute(
            "SELECT user_id, listing_id, budget_aed, requirements, day, time, created_at FROM leads ORDER BY created_at"
        ).fetchall()
    return [dict(r) for r in rows]


def get_profile(user_id):
    with _connect() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if user is None:
            return None
        prefs = conn.execute(
            "SELECT preference FROM preferences WHERE user_id = ? ORDER BY created_at", (user_id,)
        ).fetchall()
        liked = conn.execute(
            "SELECT listing_id FROM liked_listings WHERE user_id = ? ORDER BY created_at", (user_id,)
        ).fetchall()
        leads = conn.execute(
            "SELECT listing_id, day, time FROM leads WHERE user_id = ? ORDER BY created_at", (user_id,)
        ).fetchall()
    return UserProfile(
        user_id=user["user_id"],
        name=user["name"],
        budget_aed=user["budget_aed"],
        member_since=user["created_at"],
        preferences=[r["preference"] for r in prefs],
        liked_listings=[r["listing_id"] for r in liked],
        viewings=[f"{r['day']} at {r['time']} (listing {r['listing_id']})" for r in leads],
    )


init()
