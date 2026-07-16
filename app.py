import json
import os
import uuid

import httpx
import streamlit as st

BACKEND = os.getenv("BACKEND_URL", "http://localhost:8000")
LOGO = "https://logosandtypes.com/wp-content/uploads/2020/07/dubizzle.svg"
USER_LOGO = "https://static.dubizzle.com/frontend-web/static-resources/assets/images/dubizzle-logo@2x.png"

st.set_page_config(page_title="Carma", page_icon=LOGO, layout="centered")


def load_css():
    path = os.path.join(os.path.dirname(__file__), "style.css")
    if os.path.exists(path):
        with open(path) as handle:
            st.markdown(f"<style>{handle.read()}</style>", unsafe_allow_html=True)


def stream_reply(payload, holder):
    with httpx.stream("POST", f"{BACKEND}/chat/stream", json=payload, timeout=None) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line:
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("type") == "token":
                yield event["text"]
            elif event.get("type") == "final":
                holder["listings"] = event.get("listings", [])
                holder["bookings"] = event.get("bookings", [])
                holder["user"] = event.get("user")


def fmt_make(make):
    return make.upper() if make.lower() in {"bmw", "gmc", "mg"} else make.title()


def render_cards(listings):
    for listing in listings:
        title = f"{listing['year']} {fmt_make(listing['make'])} {listing['model'].title()}"
        chips = []
        if listing.get("color"):
            chips.append(listing["color"].title())
        if listing.get("mileage_km"):
            chips.append(f"{listing['mileage_km']:,} km")
        if listing.get("price_aed"):
            chips.append(f"{listing['price_aed']:,} AED")
        label = f"{title}  ·  {'  ·  '.join(chips)}" if chips else title
        with st.expander(label):
            if listing.get("photo_url"):
                st.image(listing["photo_url"], width="stretch")
            if listing.get("summary"):
                st.markdown(listing["summary"])
            details = []
            if listing.get("trim") and listing["trim"] not in ("other", "standard"):
                details.append(f"**Trim:** {listing['trim'].title()}")
            if listing.get("color"):
                details.append(f"**Colour:** {listing['color'].title()}")
            if listing.get("body_type"):
                details.append(f"**Body type:** {listing['body_type'].upper()}")
            if listing.get("mileage_km"):
                details.append(f"**Mileage:** {listing['mileage_km']:,} km")
            if listing.get("price_aed"):
                details.append(f"**Price:** {listing['price_aed']:,} AED")
            details.append(f"**Listing ID:** {listing['listing_id']}")
            st.markdown("  \n".join(details))


def render_bookings(bookings):
    if not bookings:
        return
    rows = [
        {"Car": b.get("car", ""), "Day": b.get("day") or "-", "Time": b.get("time") or "-"}
        for b in bookings
    ]
    st.table(rows)


load_css()

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_name" in st.session_state:
    if not st.session_state.get("user_id"):
        st.session_state["user_id"] = st.session_state["pending_name"]
    del st.session_state["pending_name"]

left, right = st.columns([5, 3])
with left:
    st.markdown(
        f'<div class="dz-header"><img src="{LOGO}" alt="Carma">'
        f'<div class="dz-title">Carma</div></div>',
        unsafe_allow_html=True,
    )
with right:
    user_id = st.text_input(
        "name", key="user_id", placeholder="Your Name", label_visibility="collapsed"
    )

if not st.session_state.messages:
    st.markdown(
        '<div class="dz-hero"><h1>Find your next car with <b>Carma</b></h1>'
        "<p>Ask about our inventory or book a viewing. Tell me your name and I'll remember what you like.</p></div>",
        unsafe_allow_html=True,
    )

for message in st.session_state.messages:
    avatar = LOGO if message["role"] == "assistant" else USER_LOGO
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])
        render_cards(message.get("listings", []))
        render_bookings(message.get("bookings", []))

prompt = st.chat_input("Ask about cars, or book a viewing...")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=USER_LOGO):
        st.markdown(prompt)
    with st.chat_message("assistant", avatar=LOGO):
        payload = {
            "session_id": st.session_state.session_id,
            "user_id": user_id or None,
            "message": prompt,
        }
        holder = {"listings": []}
        try:
            reply = st.write_stream(stream_reply(payload, holder))
        except Exception as exc:
            reply = f"I couldn't reach the backend at {BACKEND}. Is it running? ({exc})"
            st.markdown(reply)
        render_cards(holder["listings"])
        render_bookings(holder.get("bookings", []))
    st.session_state.messages.append(
        {"role": "assistant", "content": reply, "listings": holder["listings"],
         "bookings": holder.get("bookings", [])}
    )
    captured = holder.get("user")
    if captured and not (user_id or "").strip():
        st.session_state["pending_name"] = captured
        st.rerun()
