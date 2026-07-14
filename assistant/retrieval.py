import re

from .config import MAX_RESULTS
from .data import all_listings, summary_text
from .enrich import load as load_enriched
from .matching import canonical_make, canonical_model
from .text import tokens as _tokens


def _norm(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower()) if value else ""


def _matches_make(listing, make):
    return _norm(make) in _norm(listing.make) or _norm(listing.make) in _norm(make)


def _matches_model(listing, model):
    return _norm(model) in _norm(listing.model) or _norm(listing.model) in _norm(model)


def search(query, limit=MAX_RESULTS):
    enriched = load_enriched()
    candidates = all_listings()

    if query.make:
        canon = canonical_make(query.make, {l.make for l in candidates})
        if canon:
            candidates = [l for l in candidates if l.make == canon]
        else:
            candidates = [l for l in candidates if _matches_make(l, query.make)]
    if query.model:
        canon = canonical_model(query.model, {l.model for l in candidates})
        if canon:
            candidates = [l for l in candidates if l.model == canon]
        else:
            candidates = [l for l in candidates if _matches_model(l, query.model)]
    if query.year_min is not None:
        candidates = [l for l in candidates if l.year >= query.year_min]
    if query.year_max is not None:
        candidates = [l for l in candidates if l.year <= query.year_max]
    if query.mileage_max is not None:
        candidates = [l for l in candidates if l.mileage_km is not None and l.mileage_km <= query.mileage_max]
    if query.color:
        candidates = [l for l in candidates if l.color and _norm(query.color) in _norm(l.color)]
    if query.body_type:
        candidates = [l for l in candidates if l.body_type and _norm(query.body_type) in _norm(l.body_type)]

    structured_applied = any(
        [query.make, query.model, query.year_min is not None, query.year_max is not None,
         query.mileage_max is not None, query.color, query.body_type]
    )

    if not query.keywords:
        return candidates[:limit]

    wanted = set()
    for kw in query.keywords:
        wanted.update(_tokens(kw))
    if not wanted:
        return candidates[:limit]

    scored = []
    for listing in candidates:
        hay = " ".join(
            [
                listing.make,
                listing.model,
                listing.trim,
                listing.title,
                summary_text(listing.listing_id),
                enriched.get(str(listing.listing_id), {}).get("color") or "",
                enriched.get(str(listing.listing_id), {}).get("body_type") or "",
                enriched.get(str(listing.listing_id), {}).get("spec") or "",
            ]
        )
        counts = {}
        for tok in _tokens(hay):
            counts[tok] = counts.get(tok, 0) + 1
        score = sum(1 + 0.1 * counts.get(w, 0) for w in wanted if w in counts)
        scored.append((score, listing))

    if not structured_applied:
        scored = [pair for pair in scored if pair[0] > 0]

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [listing for _, listing in scored[:limit]]
