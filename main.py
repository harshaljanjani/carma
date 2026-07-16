import json
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from assistant import booking, memory
from assistant.agent import handle_chat, search_results, stream_chat
from assistant.data import all_listings, get_listing
from assistant.schemas import (
    ChatRequest,
    ChatResponse,
    FilterQuery,
    LeadRequest,
    Listing,
    UserProfile,
)

app = FastAPI(title="Carma", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok", "listings": len(all_listings())}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="message is empty")
    return handle_chat(request.session_id, request.user_id, request.message)


@app.post("/chat/stream")
def chat_stream(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="message is empty")

    def events():
        for event in stream_chat(request.session_id, request.user_id, request.message):
            yield json.dumps(event) + "\n"

    return StreamingResponse(events(), media_type="application/x-ndjson")


@app.get("/inventory", response_model=List[Listing])
def inventory(
    make: Optional[str] = None,
    model: Optional[str] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    mileage_max: Optional[int] = None,
    color: Optional[str] = None,
    body_type: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 20,
):
    query = FilterQuery(
        make=make,
        model=model,
        year_min=year_min,
        year_max=year_max,
        mileage_max=mileage_max,
        color=color,
        body_type=body_type,
        keywords=[q] if q else [],
    )
    return search_results(query)[:limit] if any(
        [make, model, year_min, year_max, mileage_max, color, body_type, q]
    ) else all_listings()[:limit]


@app.get("/inventory/{listing_id}", response_model=Listing)
def inventory_item(listing_id: int):
    listing = get_listing(listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="listing not found")
    return listing


@app.post("/leads")
def create_lead(lead: LeadRequest):
    valid, issue = booking.slot_is_valid(lead.day, lead.time)
    if not valid:
        raise HTTPException(status_code=400, detail=issue)
    booking.record_lead(
        lead.user_id, lead.listing_id, lead.budget_aed, lead.requirements, lead.day, lead.time
    )
    if lead.budget_aed:
        memory.upsert_user(lead.user_id, budget_aed=lead.budget_aed)
    if lead.listing_id is not None:
        memory.add_liked(lead.user_id, lead.listing_id)
    return {"status": "recorded"}


@app.get("/users/{user_id}", response_model=UserProfile)
def user_profile(user_id: str):
    profile = memory.get_profile(user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="user not found")
    return profile
