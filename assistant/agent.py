import datetime
import re

from . import booking, memory
from .config import ALL_DAYS, CURRENCY, MAX_RESULTS
from .data import all_listings, get_listing, summary_text
from .guardrails import decline_for
from .llm import complete, stream_complete, structured
from .matching import detect_make, detect_model
from .text import tokens
from .vocab import find_body, find_color
from .schemas import (
    BookingDetails,
    CancelSelection,
    ChatResponse,
    FilterQuery,
    IntentClassification,
)

ORDINALS = {
    "first": 0, "1st": 0, "one": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2,
    "fourth": 3, "4th": 3, "fifth": 4, "5th": 4, "last": -1,
}

PRICE_NOTE = (
    "Our current inventory catalog doesn't list exact prices, but I'll record your budget of "
    "{budget} {currency} in your profile so our sales team can follow up when we book your viewing."
)

PERSONA = (
    "<role>You are the Carma assistant. You help a user explore a used-car inventory, answer "
    "questions about specific listings, and book viewings.</role>\n"
    "<rules>\n"
    "1. Ground every claim only in the cars and facts given inside the <context> tags. Never invent or guess "
    "a car, price, mileage, colour, or specification.\n"
    "2. If a detail is not in <context>, say you do not have it rather than making one up.\n"
    "3. The catalog has no exact prices. If asked about price, say so plainly and offer to record the user's "
    "budget for the sales team when booking a viewing.\n"
    "4. Stay on the Carma inventory; do not discuss competitors, other car platforms, code, or general "
    "knowledge.\n"
    "5. Be concise, warm, and helpful; prefer two to four sentences.\n"
    "</rules>"
)

CLASSIFY_SYSTEM = (
    "<task>Classify the user's latest message for a used-car marketplace assistant into exactly one intent.</task>\n"
    "<intents>\n"
    "- chitchat: greetings, thanks, small talk, and questions about the user's own saved profile "
    "(their name, how long they have been a member, their budget, saved preferences, liked cars, or past viewings).\n"
    "- inventory_query: searching, filtering, or asking about cars in the inventory, including follow-ups "
    "about a car already shown.\n"
    "- booking_lead: wants to arrange a NEW viewing or test drive, or gives a budget for one.\n"
    "- manage_bookings: wants to see, list, or review their current viewings, or to cancel/remove/delete a "
    "booking (for example 'show my bookings', 'cancel my bentley viewing', 'remove all my bookings').\n"
    "- out_of_scope: non-automotive topics, competitor brands, other used-car platforms, writing code, or "
    "general knowledge and history. Also set refusal_category to one of competitor, other_platform, "
    "code_writing, non_automotive, history.\n"
    "</intents>\n"
    "<rules>If the message refers to a previously shown car (for example 'the first one', 'that Toyota', "
    "'is it under warranty'), copy that phrase into referenced_entity; otherwise leave it null. If the user "
    "states their own name (for example 'I'm Harshal', 'my name is Sara', \"name's Priya\"), put just the name "
    "in user_name; do not treat 'I'm looking for...' as a name.</rules>\n"
    "<examples>\n"
    "hi there -> {\"intent\":\"chitchat\",\"refusal_category\":null,\"referenced_entity\":null,\"user_name\":null}\n"
    "hi, name's Harshal, show me a bentley -> {\"intent\":\"inventory_query\",\"refusal_category\":null,\"referenced_entity\":null,\"user_name\":\"Harshal\"}\n"
    "what is my name and what did i like? -> {\"intent\":\"chitchat\",\"refusal_category\":null,\"referenced_entity\":null}\n"
    "show me a white toyota after 2019 -> {\"intent\":\"inventory_query\",\"refusal_category\":null,\"referenced_entity\":null}\n"
    "what is the mileage on the first one? -> {\"intent\":\"inventory_query\",\"refusal_category\":null,\"referenced_entity\":\"the first one\"}\n"
    "book me a viewing on Saturday at 3pm -> {\"intent\":\"booking_lead\",\"refusal_category\":null,\"referenced_entity\":null}\n"
    "who won the world cup in 1998? -> {\"intent\":\"out_of_scope\",\"refusal_category\":\"history\",\"referenced_entity\":null}\n"
    "</examples>"
)

FILTER_SYSTEM = (
    "<task>Extract structured search filters from the user's car request.</task>\n"
    "<rules>\n"
    "- Fill only fields the user clearly implies; leave the rest null.\n"
    "- Never fill a price field; price is not searchable, and a budget like 'under 20k' is not a filter.\n"
    "- Set color and body_type when the user names one; put any other soft attribute (condition, spec, "
    "features) into keywords, and do not put a year or a kilometre figure into keywords.\n"
    "- year_min/year_max express ranges: 'after 2018', 'newer than 2018', '2018 or newer' set year_min=2018; "
    "'before 2015', 'older than 2015' set year_max=2015; 'between 2016 and 2020' sets both.\n"
    "- mileage_max is a kilometre cap: 'under 80000 km' or 'less than 80,000 kms' sets mileage_max=80000; "
    "never confuse a km figure with a price.\n"
    "</rules>\n"
    "<examples>\n"
    "white toyota suv after 2019 -> {\"make\":\"toyota\",\"model\":null,\"year_min\":2019,\"year_max\":null,\"mileage_max\":null,\"color\":\"white\",\"body_type\":\"suv\",\"keywords\":[]}\n"
    "a mercedes under 80,000 km older than 2020 -> {\"make\":\"mercedes-benz\",\"model\":null,\"year_min\":null,\"year_max\":2020,\"mileage_max\":80000,\"color\":null,\"body_type\":null,\"keywords\":[]}\n"
    "</examples>"
)

BOOKING_SYSTEM = (
    "<task>Extract viewing-booking details from the user's message.</task>\n"
    "<fields>budget_aed (integer AED only if a budget is mentioned), requirements (free text), day, time, "
    "listing_id if they name a specific shown car by its id, and name (the person's name to book under, if "
    "they give one, for example 'book it under Sara' or 'my name is Sara'). Leave any field null when not "
    "provided.</fields>\n"
    "<examples>\n"
    "book listing 12 for Saturday at 3pm, budget 50k -> {\"budget_aed\":50000,\"requirements\":null,\"day\":\"Saturday\",\"time\":\"3pm\",\"listing_id\":12,\"name\":null}\n"
    "book it under Sara -> {\"budget_aed\":null,\"requirements\":null,\"day\":null,\"time\":null,\"listing_id\":null,\"name\":\"Sara\"}\n"
    "</examples>"
)


def _known_makes():
    return {l.make for l in all_listings()}


def _known_models():
    return {l.model for l in all_listings()}


YEAR_MIN_CUES = ("after", "since", "from", "newer than", "or newer", "above", "over", "later than", "younger than")
YEAR_MAX_CUES = ("before", "older than", "or older", "up to", "earlier than", "prior to", "below", "under")
MILEAGE_CUES = ("under", "below", "less than", "max", "up to", "within", "no more than")


def _detect_budget(message):
    text = re.sub(r"\d[\d,\.]*\s*(?:km|kms|kilomet\w*)\b", " ", message.lower())
    text = text.replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*k\b", text)
    if m:
        return int(float(m.group(1)) * 1000)
    m = re.search(r"(?:aed|dhs|\$|usd|budget|under|below|up to|around)\D{0,4}(\d{4,7})", text)
    if m:
        return int(m.group(1))
    return None


def _detect_mileage_max(message):
    text = message.lower().replace(",", "")
    m = re.search(r"(\d{3,7})\s*(?:km|kms|kilomet\w*)\b", text)
    if m and any(cue in text for cue in MILEAGE_CUES):
        return int(m.group(1))
    return None


def _resolve_reference(session_id, phrase):
    ids = memory.get_last_results(session_id)
    if not ids or not phrase:
        return None
    text = phrase.lower()
    for word, idx in ORDINALS.items():
        if re.search(rf"\b{re.escape(word)}\b", text):
            try:
                return ids[idx]
            except IndexError:
                return ids[-1]
    scored = []
    for lid in ids:
        listing = get_listing(lid)
        if not listing:
            continue
        score = 0
        if listing.model and listing.model.lower() in text:
            score += 2
        if listing.make and listing.make.lower() in text:
            score += 1
        if listing.year and str(listing.year) in text:
            score += 1
        scored.append((score, lid))
    if not scored:
        return None
    best = max(s for s, _ in scored)
    top = [lid for s, lid in scored if s == best]
    if best > 0 and len(top) == 1:
        return top[0]
    if len(ids) == 1 and re.search(r"\b(it|that|this|one|car|vehicle|model)\b", text):
        return ids[0]
    return None


def _listing_facts(listing):
    parts = [f"id={listing.listing_id}", f"{listing.year} {listing.make} {listing.model} {listing.trim}"]
    if listing.color:
        parts.append(f"colour {listing.color}")
    if listing.body_type:
        parts.append(f"body {listing.body_type}")
    if listing.mileage_km:
        parts.append(f"mileage {listing.mileage_km} km")
    if listing.price_aed:
        parts.append(f"stated price {listing.price_aed} {CURRENCY}")
    detail = summary_text(listing.listing_id)
    if detail:
        parts.append(f"details: {detail}")
    return "; ".join(parts)


def _classify(session_id, message):
    try:
        result = structured(IntentClassification, CLASSIFY_SYSTEM, message)
        if result is not None:
            return result
    except Exception:
        pass
    return _heuristic_intent(session_id, message)


def _heuristic_intent(session_id, message):
    text = message.lower()
    if any(w in text for w in ["write code", "python", "javascript", "write a function", "write a script", "program in"]):
        return IntentClassification(intent="out_of_scope", refusal_category="code_writing")
    if any(p in text for p in ["my name", "about me", "my profile", "my budget", "remember me", "my details", "member since", "how long have i", "what did i like", "did i book", "did you book", "my booking", "my viewing", "which car did"]):
        return IntentClassification(intent="chitchat")
    if any(w in text for w in ["cancel", "remove booking", "delete booking", "my bookings", "my viewings",
                               "show my booking", "view booking", "list booking", "my appointment"]):
        return IntentClassification(intent="manage_bookings")
    if any(w in text for w in ["book", "viewing", "test drive", "schedule", "appointment"]):
        return IntentClassification(intent="booking_lead")
    if any(w in text for w in ["hello", "hi ", "hey", "thanks", "thank you", "how are you"]) and len(text) < 25:
        return IntentClassification(intent="chitchat")
    ref = None
    if memory.get_last_results(session_id) and any(
        w in text for w in list(ORDINALS) + ["it", "that", "this"]
    ):
        ref = message
    return IntentClassification(intent="inventory_query", referenced_entity=ref)


def _merge_filters(primary, backup):
    return FilterQuery(
        make=primary.make or backup.make,
        model=primary.model or backup.model,
        year_min=primary.year_min if primary.year_min is not None else backup.year_min,
        year_max=primary.year_max if primary.year_max is not None else backup.year_max,
        mileage_max=primary.mileage_max if primary.mileage_max is not None else backup.mileage_max,
        color=primary.color or backup.color,
        body_type=primary.body_type or backup.body_type,
        keywords=primary.keywords or backup.keywords,
    )


def _extract_filter(message):
    heuristic = _heuristic_filter(message)
    try:
        result = structured(FilterQuery, FILTER_SYSTEM, message)
    except Exception:
        return heuristic
    if result is None:
        return heuristic
    return _merge_filters(result, heuristic)


def _heuristic_filter(message):
    text = message.lower()
    make = detect_make(message, _known_makes())
    model = detect_model(message, _known_models())
    years = [int(y) for y in re.findall(r"\b(19\d{2}|20\d{2})\b", text)]
    year_min = year_max = None
    if len(years) >= 2:
        year_min, year_max = min(years), max(years)
    elif len(years) == 1:
        year = years[0]
        if any(cue in text for cue in YEAR_MIN_CUES):
            year_min = year
        elif any(cue in text for cue in YEAR_MAX_CUES):
            year_max = year
        else:
            year_min = year_max = year
    keywords = [w for w in tokens(message) if not w.isdigit()]
    return FilterQuery(
        make=make,
        model=model,
        year_min=year_min,
        year_max=year_max,
        mileage_max=_detect_mileage_max(message),
        color=find_color(message),
        body_type=find_body(message),
        keywords=keywords,
    )


def _clean_name(message):
    text = message.strip()
    m = re.search(r"(?:my name is|i am|i'?m|it'?s|this is|call me|name'?s|book it under|under)\s+(.+)", text, re.I)
    explicit = bool(m)
    if m:
        text = m.group(1)
    if not explicit:
        if re.search(r"\d", text) or len(text.split()) > 4:
            return None
        if re.search(r"\b(book|viewing|showing|show|find|search|yes|no|car|price|code|cancel|stop|nevermind|"
                     r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", text, re.I):
            return None
    cleaned = re.sub(r"[^A-Za-z' \-]", "", text).strip()
    return cleaned[:60] or None


def _extract_intro_name(message):
    m = re.search(
        r"(?:my name is|the name is|name is|my name'?s|the name'?s|name'?s|call me|i go by)\s+([A-Za-z][A-Za-z' \-]{1,40})",
        message, re.I,
    )
    if not m:
        return None
    name = re.sub(r"[^A-Za-z' \-]", "", m.group(1)).strip()
    if not (1 <= len(name.split()) <= 4):
        return None
    if re.search(r"\b(looking|show|find|book|viewing|car|cars|the|for)\b", name, re.I):
        return None
    if detect_make(name, _known_makes()) or detect_model(name, _known_models()):
        return None
    return name[:60] or None


def _heuristic_booking(message):
    day = next((d for d in ALL_DAYS if d in message.lower()), None)
    time = None
    m = re.search(r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b", message.lower())
    if m:
        time = m.group(1)
    name = None
    m = re.search(r"(?:book it under|my name is|name'?s|book under)\s+(.+)", message, re.I)
    if m:
        name = _clean_name(m.group(0))
    return BookingDetails(budget_aed=_detect_budget(message), day=day.capitalize() if day else None, time=time, name=name)


def _extract_booking(message):
    heuristic = _heuristic_booking(message)
    try:
        result = structured(BookingDetails, BOOKING_SYSTEM, message)
    except Exception:
        return heuristic
    if result is None:
        return heuristic
    return BookingDetails(
        budget_aed=result.budget_aed or heuristic.budget_aed,
        requirements=result.requirements or heuristic.requirements,
        day=result.day or heuristic.day,
        time=result.time or heuristic.time,
        listing_id=result.listing_id or heuristic.listing_id,
        name=result.name or heuristic.name,
    )


def _compose(session_id, message, context, fallback):
    try:
        history = memory.get_session(session_id)["history"][-6:]
        user_msg = f"<context>\n{context}\n</context>\n\nUser question: {message}"
        return complete(PERSONA, history + [{"role": "user", "content": user_msg}])
    except Exception:
        return fallback


def _compose_stream(session_id, message, context, fallback):
    history = memory.get_session(session_id)["history"][-6:]
    user_msg = f"<context>\n{context}\n</context>\n\nUser question: {message}"
    emitted = False
    try:
        for chunk in stream_complete(PERSONA, history + [{"role": "user", "content": user_msg}]):
            if chunk:
                emitted = True
                yield chunk
    except Exception:
        pass
    if not emitted:
        yield fallback


def handle_chat(session_id, user_id, message):
    plan = _plan(session_id, user_id, message)
    if plan["context"] is not None:
        body = _compose(session_id, message, plan["context"], plan["fallback"])
    else:
        body = plan["fallback"]
    reply = plan["prefix"] + body
    memory.append_turn(session_id, "assistant", reply)
    return ChatResponse(
        reply=reply, intent=plan["intent"], listings=plan["listings"],
        bookings=plan.get("bookings", []),
        user=memory.get_session(session_id).get("captured_name"),
    )


def stream_chat(session_id, user_id, message):
    plan = _plan(session_id, user_id, message)
    accumulated = plan["prefix"]
    if plan["prefix"]:
        yield {"type": "token", "text": plan["prefix"]}
    if plan["context"] is not None:
        for chunk in _compose_stream(session_id, message, plan["context"], plan["fallback"]):
            accumulated += chunk
            yield {"type": "token", "text": chunk}
    else:
        accumulated += plan["fallback"]
        yield {"type": "token", "text": plan["fallback"]}
    memory.append_turn(session_id, "assistant", accumulated)
    yield {
        "type": "final",
        "intent": plan["intent"],
        "listings": [l.model_dump() for l in plan["listings"]],
        "bookings": plan.get("bookings", []),
        "user": memory.get_session(session_id).get("captured_name"),
    }


def _plan(session_id, user_id, message):
    memory.get_session(session_id, user_id)
    if user_id:
        memory.upsert_user(user_id, name=user_id)
    memory.append_turn(session_id, "user", message)

    classification = _classify(session_id, message)
    intent = classification.intent

    intro_name = classification.user_name or _extract_intro_name(message)
    if intro_name and not user_id:
        user_id = intro_name
        memory.get_session(session_id, user_id)
        memory.upsert_user(user_id, name=user_id)
        memory.get_session(session_id)["captured_name"] = user_id

    pending = memory.get_pending_booking(session_id)
    if pending and pending.get("stage") in ("name", "qualify"):
        if _looks_like_new_search(message):
            memory.clear_pending_booking(session_id)
        else:
            intent = "booking_lead"
    elif pending and pending.get("stage") == "confirm":
        if _is_browse_request(message):
            memory.clear_pending_booking(session_id)
        else:
            intent = "booking_lead"
    elif pending and intent != "out_of_scope":
        if pending.get("listing_id") is None:
            if _references_car(session_id, message) or _provides_slot(message):
                intent = "booking_lead"
        elif _is_browse_request(message):
            memory.clear_pending_booking(session_id)
        elif _provides_slot(message):
            intent = "booking_lead"

    if intent == "out_of_scope":
        return {"intent": intent, "listings": [], "prefix": "", "context": None,
                "fallback": decline_for(classification.refusal_category)}
    if intent == "chitchat":
        return _plan_chitchat(session_id, user_id, message)
    if intent == "manage_bookings":
        return _plan_manage_bookings(session_id, user_id, message)
    if intent == "booking_lead":
        return _plan_booking(session_id, user_id, message)
    return _plan_inventory(session_id, user_id, message, classification)


def _profile_context(user_id, profile):
    if not profile:
        if user_id:
            return f"The user's name is {user_id}, but no history is stored yet."
        return "The user has not shared their name yet."
    parts = [f"The user's name is {profile.name or user_id}."]
    if profile.member_since:
        parts.append(f"They have been with Carma since {profile.member_since[:10]}.")
    if profile.budget_aed:
        parts.append(f"Their stated budget is around {profile.budget_aed} AED.")
    if profile.preferences:
        parts.append(f"Saved preferences: {'; '.join(profile.preferences)}.")
    liked = []
    for lid in profile.liked_listings:
        listing = get_listing(lid)
        if listing:
            liked.append(f"{listing.year} {listing.make.title()} {listing.model.title()}")
    if liked:
        parts.append(f"Cars they liked: {', '.join(liked)}.")
    if profile.viewings:
        parts.append(f"Past viewing bookings: {'; '.join(profile.viewings)}.")
    parts.append(
        "You may answer questions about the user's own name, membership, budget, saved preferences, "
        "liked cars, and past viewings using only these stored details; never invent details."
    )
    return " ".join(parts)


def _plan_chitchat(session_id, user_id, message):
    profile = memory.get_profile(user_id) if user_id else None
    name = (profile.name if profile else None) or user_id
    greeting = f"Welcome back, {name}! " if name else ""
    fallback = (
        greeting
        + "I'm your Carma assistant. Tell me what you're after and I'll pull matching listings, "
        "or I can book you a viewing."
    ).strip()
    context = "This is casual conversation. " + _profile_context(user_id, profile)
    return {"intent": "chitchat", "listings": [], "prefix": "", "context": context, "fallback": fallback}


def _plan_inventory(session_id, user_id, message, classification):
    if classification.referenced_entity:
        lid = _resolve_reference(session_id, classification.referenced_entity)
        if lid is not None:
            listing = get_listing(lid)
            context = "The user is asking about this specific car.\n" + _listing_facts(listing)
            return {"intent": "inventory_query", "listings": [listing], "prefix": "",
                    "context": context, "fallback": _describe(listing)}

    budget = _detect_budget(message)
    prefix = ""
    if budget:
        prefix = PRICE_NOTE.format(budget=f"{budget:,}", currency=CURRENCY) + "\n\n"
        if user_id:
            memory.upsert_user(user_id, budget_aed=budget)
            memory.add_preference(user_id, f"budget around {budget} {CURRENCY}")

    query = _extract_filter(message)
    has_filter = any([
        query.make, query.model, query.year_min is not None, query.year_max is not None,
        query.mileage_max is not None, query.color, query.body_type,
    ])
    results = search_results(query)

    browsing = not has_filter
    if browsing:
        shown = set(memory.get_last_results(session_id))
        wants_more = any(w in message.lower() for w in ("other", "more", "else", "another", "different"))
        if wants_more and shown:
            pool = [l for l in all_listings() if l.listing_id not in shown]
            results = (pool or all_listings())[:MAX_RESULTS]
        elif not results:
            results = all_listings()[:MAX_RESULTS]

    memory.set_last_results(session_id, [l.listing_id for l in results])
    if user_id and query.make:
        memory.add_preference(user_id, f"interested in {query.make}")

    if not results:
        return {"intent": "inventory_query", "listings": [], "prefix": prefix, "context": None,
                "fallback": "I couldn't find any listings matching that. Want to try a different make, model, or year?"}

    context = "Matching listings (use only these facts):\n" + "\n".join(_listing_facts(l) for l in results)
    if browsing:
        context += (
            f"\nThis is a small sample of {len(all_listings())} cars in the inventory; many more are available. "
            "Do not claim these are the only cars or all the cars available."
        )
    if query.mileage_max is not None:
        context += "\nOnly listings with a stated mileage were considered; some listings do not list mileage."
    if prefix:
        context += "\nThe user's budget has been recorded and pricing is addressed separately; do not mention price or budget."
    return {"intent": "inventory_query", "listings": results, "prefix": prefix,
            "context": context, "fallback": _list_reply(results)}


def search_results(query):
    from .retrieval import search

    return search(query, limit=MAX_RESULTS)


def _user_bookings(user_id):
    booked = []
    for lead in memory.get_leads(user_id):
        listing = get_listing(lead["listing_id"]) if lead["listing_id"] else None
        car = f"{listing.year} {listing.make.title()} {listing.model.title()}" if listing else "Unspecified car"
        booked.append(
            {"rowid": lead["rowid"], "listing_id": lead["listing_id"], "car": car,
             "day": _clean_slot(lead["day"]), "time": _clean_slot(lead["time"])}
        )
    return booked


def _bookings_to_cancel(message, booked):
    text = message.lower()
    if any(w in text for w in ["all", "every", "everything"]):
        return booked
    matches = []
    for b in booked:
        car_tokens = [t for t in re.split(r"\W+", b["car"].lower()) if len(t) > 2]
        day = (b["day"] or "").lower()
        if any(t in text for t in car_tokens) or (day and day in text):
            matches.append(b)
    if matches:
        return matches
    if len(booked) == 1:
        return booked
    return []


CANCEL_SYSTEM = (
    "The user wants to cancel one or more of their car-viewing bookings. You are given their current bookings, "
    "each with a rowid. Return the rowids of only the bookings they want to cancel. If they ask to replace one "
    "booking with another, cancel only the one being removed, not the replacement. If they say cancel all, "
    "return every rowid. If it is unclear, return an empty list."
)


def _select_cancellations(message, booked):
    listed = "\n".join(f"rowid={b['rowid']}: {b['car']} on {b['day']} at {b['time']}" for b in booked)
    try:
        selection = structured(CancelSelection, CANCEL_SYSTEM, f"Bookings:\n{listed}\n\nUser: {message}")
    except Exception:
        selection = None
    if selection is not None:
        valid = {b["rowid"] for b in booked}
        chosen = [b for b in booked if b["rowid"] in set(selection.rowids) & valid]
        if chosen:
            return chosen
    return _bookings_to_cancel(message, booked)


def _plan_manage_bookings(session_id, user_id, message):
    if not user_id:
        return {"intent": "manage_bookings", "listings": [], "bookings": [], "prefix": "", "context": None,
                "fallback": "I can pull up your bookings once I know your name. What name are they under?"}
    booked = _user_bookings(user_id)
    if not booked:
        return {"intent": "manage_bookings", "listings": [], "bookings": [], "prefix": "", "context": None,
                "fallback": "You don't have any viewings booked yet. Would you like to book one?"}

    if any(w in message.lower() for w in ["cancel", "remove", "delete", "drop", "unbook"]):
        targets = _select_cancellations(message, booked)
        if not targets:
            listing_str = "; ".join(f"{b['car']} on {b['day']} at {b['time']}" for b in booked)
            return {"intent": "manage_bookings", "listings": [], "bookings": booked, "prefix": "", "context": None,
                    "fallback": "Which booking would you like to cancel? You have: " + listing_str}
        for target in targets:
            booking.cancel_lead(target["rowid"])
        cancelled = "; ".join(f"{t['car']} on {t['day']} at {t['time']}" for t in targets)
        remaining = _user_bookings(user_id)
        return {"intent": "manage_bookings", "listings": [], "bookings": remaining, "prefix": "", "context": None,
                "fallback": f"Done, I've cancelled: {cancelled}."}

    return {"intent": "manage_bookings", "listings": [], "bookings": booked, "prefix": "", "context": None,
            "fallback": "Here are your current viewings:"}


def _is_browse_request(message):
    return any(
        cue in message.lower()
        for cue in ("show me", "find me", "search", "looking for", "do you have",
                    "browse", "what do you have", "other options", "something else")
    )


def _looks_like_new_search(message):
    if detect_make(message, _known_makes()) or detect_model(message, _known_models()):
        return True
    return _is_browse_request(message)


def _clean_slot(value):
    if not value:
        return value
    return value.strip().strip(",.;:!? ").strip() or None


WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _relative_day(text, pending_day=None):
    t = text.lower()
    today = datetime.date.today()
    if "day after tomorrow" in t:
        return (today + datetime.timedelta(days=2)).strftime("%A")
    if "tomorrow" in t:
        return (today + datetime.timedelta(days=1)).strftime("%A")
    if re.search(r"\b(today|tonight)\b", t):
        return today.strftime("%A")
    if re.search(r"\b(next day|following day|day after)\b", t):
        if pending_day and pending_day.strip().lower() in WEEKDAYS:
            idx = WEEKDAYS.index(pending_day.strip().lower())
            return WEEKDAYS[(idx + 1) % 7].capitalize()
        return (today + datetime.timedelta(days=1)).strftime("%A")
    m = re.search(r"\b(?:next|this|coming)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", t)
    if m:
        return m.group(1).capitalize()
    return None


def _provides_slot(message):
    details = _heuristic_booking(message)
    return bool(details.day or details.time)


def _references_car(session_id, message):
    if detect_make(message, _known_makes()) or detect_model(message, _known_models()):
        return True
    text = message.lower()
    if memory.get_last_results(session_id):
        for word in list(ORDINALS) + ["it", "that", "this"]:
            if re.search(rf"\b{re.escape(word)}\b", text):
                return True
    return False


def _is_negative(message):
    text = message.strip().lower()
    return bool(re.search(r"\b(no|nope|nah|cancel|don'?t|stop|never ?mind)\b|not (yet|now|really)", text))


def _is_affirmative(message):
    text = message.strip().lower()
    if _is_negative(text):
        return False
    if any(phrase in text for phrase in ["book it", "confirm", "go ahead", "go for it", "please book",
                                         "do it", "lock it in", "make it happen", "let's do", "lets do",
                                         "sounds good", "that's right", "thats right", "correct",
                                         "this is the one", "that's the one", "thats the one"]):
        return True
    if re.search(r"\b(what|which|when|where|why|price|cost|tell me|more about|details|how much)\b", text):
        return False
    words = re.findall(r"[a-z']+", text)
    affirm_words = {"yes", "yeah", "yep", "yup", "sure", "ok", "okay", "y", "confirmed", "perfect",
                    "great", "absolutely", "definitely", "please", "yea", "ya"}
    return any(w in affirm_words for w in words)


def _plan_booking(session_id, user_id, message):
    details = _extract_booking(message)
    pending = memory.get_pending_booking(session_id) or {}

    lid = details.listing_id or pending.get("listing_id") or _resolve_reference(session_id, message)
    budget = details.budget_aed or pending.get("budget_aed")
    requirements = details.requirements or pending.get("requirements")
    day = _relative_day(message, pending.get("day")) or _clean_slot(details.day or pending.get("day"))
    time = _clean_slot(details.time or pending.get("time"))
    booking_name = user_id or details.name or pending.get("name")
    if pending.get("stage") == "name" and not booking_name:
        booking_name = _clean_name(message)
    if booking_name and not user_id:
        memory.get_session(session_id)["captured_name"] = booking_name

    prefix = ""
    if details.budget_aed:
        prefix = PRICE_NOTE.format(budget=f"{details.budget_aed:,}", currency=CURRENCY) + "\n\n"
        if user_id:
            memory.upsert_user(user_id, budget_aed=details.budget_aed)
            memory.add_preference(user_id, f"budget around {details.budget_aed} {CURRENCY}")

    if lid is None:
        query = _extract_filter(message)
        options = search_results(query) if any(
            [query.make, query.model, query.color, query.body_type, query.keywords]
        ) else []
        if len(options) == 1:
            lid = options[0].listing_id
        else:
            memory.set_pending_booking(
                session_id,
                {"listing_id": None, "budget_aed": budget, "requirements": requirements, "day": day, "time": time},
            )
            if options:
                memory.set_last_results(session_id, [l.listing_id for l in options])
                context = (
                    "The user wants to book a viewing but has not chosen a specific car yet. "
                    "Ask which of these listings they want to view, and do not confirm any booking yet.\n"
                    + "\n".join(_listing_facts(l) for l in options)
                )
                return {"intent": "booking_lead", "listings": options, "prefix": prefix,
                        "context": context, "fallback": "Which of these would you like to view? " + _list_reply(options)}
            return {"intent": "booking_lead", "listings": [], "prefix": prefix, "context": None,
                    "fallback": "I'd be glad to book a viewing, but I need to know which specific car. "
                                "Which make and model would you like to see, or shall I show you our inventory?"}

    valid, issue = booking.slot_is_valid(day, time)
    if not valid:
        memory.set_pending_booking(
            session_id,
            {"listing_id": lid, "budget_aed": budget, "requirements": requirements,
             "day": day, "time": time, "name": booking_name},
        )
        if lid is not None:
            memory.set_last_results(session_id, [lid])
        return {"intent": "booking_lead", "listings": [], "prefix": prefix, "context": None, "fallback": issue}

    if not booking_name:
        memory.set_pending_booking(
            session_id,
            {"listing_id": lid, "budget_aed": budget, "requirements": requirements,
             "day": day, "time": time, "stage": "name"},
        )
        return {"intent": "booking_lead", "listings": [], "prefix": prefix, "context": None,
                "fallback": "Sure. And whose name should I book this viewing under?"}

    if pending.get("stage") not in ("qualify", "confirm") and budget is None and not requirements:
        memory.set_pending_booking(
            session_id,
            {"listing_id": lid, "budget_aed": budget, "requirements": requirements,
             "day": day, "time": time, "name": booking_name, "stage": "qualify"},
        )
        return {"intent": "booking_lead", "listings": [], "prefix": prefix, "context": None,
                "fallback": "Before I confirm, what's your budget range and any must-have requirements "
                            "for our sales team? (or just say 'skip')"}

    uid = booking_name or session_id
    listing = get_listing(lid)
    car_name = f"the {listing.year} {listing.make.title()} {listing.model.title()}" if listing else "this car"
    if pending.get("stage") == "confirm" and _is_negative(message):
        memory.clear_pending_booking(session_id)
        return {"intent": "booking_lead", "listings": [], "prefix": prefix, "context": None,
                "fallback": "No problem, I won't book that. Anything else I can help with?"}
    if not (pending.get("stage") == "confirm" and _is_affirmative(message)):
        existing = [l for l in memory.get_leads(uid) if l["listing_id"] == lid]
        note = ""
        if existing:
            slots = ", ".join(f"{e['day']} at {_clean_slot(e['time'])}" for e in existing)
            note = f"Heads up: you already have a viewing for this car ({slots}). "
        memory.set_pending_booking(
            session_id,
            {"listing_id": lid, "budget_aed": budget, "requirements": requirements,
             "day": day, "time": time, "name": booking_name, "stage": "confirm"},
        )
        if listing:
            memory.set_last_results(session_id, [lid])
        summary = ""
        if listing and listing.summary:
            summary = f" ({listing.summary.strip().rstrip('.')[:120]})"
        fallback = note + (
            f"Shall I book {car_name}{summary} for {day} at {time} under {booking_name}? Just say yes to confirm."
        )
        return {"intent": "booking_lead", "listings": [listing] if listing else [],
                "prefix": prefix, "context": None, "fallback": fallback}

    conflict = booking.find_conflict(uid, day, time)
    if conflict:
        clash = get_listing(conflict["listing_id"]) if conflict.get("listing_id") else None
        clash_car = f" for the {clash.year} {clash.make.title()} {clash.model.title()}" if clash else ""
        memory.set_pending_booking(
            session_id,
            {"listing_id": lid, "budget_aed": budget, "requirements": requirements,
             "day": day, "time": None, "name": booking_name},
        )
        clash_msg = (
            f"You already have a viewing booked on {day} at {time}{clash_car}. "
            "Could you pick a different time so they don't clash?"
        )
        return {"intent": "booking_lead", "listings": [], "prefix": prefix, "context": None, "fallback": clash_msg}

    memory.clear_pending_booking(session_id)
    booking.record_lead(uid, lid, budget, requirements, day, time)
    memory.upsert_user(uid, name=booking_name)
    if lid is not None:
        memory.add_liked(uid, lid)

    car = ""
    if lid is not None:
        listing = get_listing(lid)
        if listing:
            car = f" for the {listing.year} {listing.make.title()} {listing.model.title()}"
    booked = (
        f"You're booked{car} on {day} at {time} under {booking_name}. Our team will confirm shortly. "
        "Is there anything else you'd like to know?"
    )
    return {"intent": "booking_lead", "listings": [], "prefix": prefix, "context": None, "fallback": booked}


def _describe(listing):
    if listing is None:
        return "I don't have that car on hand anymore. Would you like to see other options?"
    bits = [f"The {listing.year} {listing.make.title()} {listing.model.title()} ({listing.trim})"]
    if listing.color:
        bits.append(f"is {listing.color}")
    if listing.mileage_km:
        bits.append(f"has {listing.mileage_km:,} km")
    if listing.body_type:
        bits.append(f"is a {listing.body_type}")
    sentence = bits[0] + (" " + ", ".join(bits[1:]) if len(bits) > 1 else "") + "."
    if not listing.mileage_km:
        sentence += " I don't have the mileage listed for this one."
    return sentence


def _list_reply(results):
    lines = ["Here's what I found:"]
    for l in results:
        extra = []
        if l.color:
            extra.append(l.color)
        if l.mileage_km:
            extra.append(f"{l.mileage_km:,} km")
        tail = f" ({', '.join(extra)})" if extra else ""
        lines.append(f"- {l.year} {l.make.title()} {l.model.title()} {l.trim}{tail}")
    lines.append("Would you like more detail on any of these, or to book a viewing?")
    return "\n".join(lines)
