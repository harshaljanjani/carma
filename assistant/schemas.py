from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class IntentClassification(BaseModel):
    intent: Literal["chitchat", "inventory_query", "booking_lead", "manage_bookings", "out_of_scope"]
    refusal_category: Optional[
        Literal["competitor", "other_platform", "code_writing", "non_automotive", "history"]
    ] = None
    referenced_entity: Optional[str] = None
    user_name: Optional[str] = None


class FilterQuery(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    mileage_max: Optional[int] = None
    color: Optional[str] = None
    body_type: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)


class EnrichedListing(BaseModel):
    listing_id: int
    price_aed: Optional[int] = None
    price_is_estimate: bool = False
    mileage_km: Optional[int] = None
    color: Optional[str] = None
    body_type: Optional[str] = None
    spec: Optional[str] = None
    en_summary: str = ""


class BookingDetails(BaseModel):
    budget_aed: Optional[int] = None
    requirements: Optional[str] = None
    day: Optional[str] = None
    time: Optional[str] = None
    listing_id: Optional[int] = None
    name: Optional[str] = None


class ChatRequest(BaseModel):
    session_id: str
    user_id: Optional[str] = None
    message: str


class Listing(BaseModel):
    listing_id: int
    year: int
    make: str
    model: str
    trim: str
    title: str
    color: Optional[str] = None
    body_type: Optional[str] = None
    mileage_km: Optional[int] = None
    price_aed: Optional[int] = None
    price_is_estimate: bool = False
    photo_url: Optional[str] = None
    summary: Optional[str] = None


class Booking(BaseModel):
    rowid: Optional[int] = None
    listing_id: Optional[int] = None
    car: str
    day: Optional[str] = None
    time: Optional[str] = None


class CancelSelection(BaseModel):
    rowids: List[int] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    intent: str
    listings: List[Listing] = Field(default_factory=list)
    bookings: List[Booking] = Field(default_factory=list)
    user: Optional[str] = None


class LeadRequest(BaseModel):
    user_id: str
    listing_id: Optional[int] = None
    budget_aed: Optional[int] = None
    requirements: Optional[str] = None
    day: Optional[str] = None
    time: Optional[str] = None


class UserProfile(BaseModel):
    user_id: str
    name: Optional[str] = None
    budget_aed: Optional[int] = None
    member_since: Optional[str] = None
    preferences: List[str] = Field(default_factory=list)
    liked_listings: List[int] = Field(default_factory=list)
    viewings: List[str] = Field(default_factory=list)
