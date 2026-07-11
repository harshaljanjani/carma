import json
import re
import sys
import time

import pandas as pd

from .config import CLEANED_CSV, ENRICHED_JSON, HAS_LLM
from .schemas import EnrichedListing
from .vocab import find_body, find_color, find_spec

INSTALL = re.compile(r"month|/mo\b|per month|installment|instal|finance|emi|monthy|down\s*payment|deposit", re.I)
CUR = re.compile(r"(?:aed|dhs?|درهم)\s*[:\-]?\s*(\d[\d,\.]{3,9})|(\d[\d,\.]{3,9})\s*(?:aed|dhs?)\b", re.I)
MILE = re.compile(r"(\d[\d,\.]{1,9})\s*(?:km|kms|kilometer|kilometre|kilometers|kilometres)\b", re.I)


def _to_int(token):
    digits = re.sub(r"[^\d]", "", token or "")
    return int(digits) if digits else None


def _regex_enrich(row):
    text = f"{row['title']} {row['description']}"
    color = find_color(text)
    body = find_body(text)
    spec = find_spec(text)

    mileage = None
    m = MILE.search(text)
    if m:
        value = _to_int(m.group(1))
        if value and 100 <= value <= 900000:
            mileage = value

    price = None
    for match in CUR.finditer(text):
        near = text[max(0, match.start() - 45) : match.end() + 25]
        if INSTALL.search(near):
            continue
        value = _to_int(match.group(0))
        if value and 12000 <= value <= 6000000:
            price = value
            break

    return EnrichedListing(
        listing_id=int(row["Listing_ID"]),
        price_aed=price,
        price_is_estimate=False,
        mileage_km=mileage,
        color=color,
        body_type=body,
        spec=spec,
        en_summary=str(row["description"]).strip()[:600],
    )


ENRICH_SYSTEM = (
    "<task>Extract structured facts from one used-car listing that may be written in English or Arabic.</task>\n"
    "<rules>\n"
    "- Return only facts explicitly stated in the text. If a field is not stated, return null; never guess or "
    "invent values.\n"
    "- price_aed must be a genuine full sale price in AED, not a monthly installment, deposit, or reference "
    "number; if only an installment or no price is stated, return null.\n"
    "- Write en_summary as a concise English description (make, model, year, condition, notable features), "
    "with dealer contact details, phone numbers, and marketing spam removed.\n"
    "</rules>\n"
    "<example>\n"
    "Text: 2019 Toyota Camry GCC, 60,000 km, only AED 1,400 monthly, call us now -> "
    "{\"price_aed\":null,\"mileage_km\":60000,\"color\":null,\"body_type\":\"sedan\",\"spec\":\"gcc\","
    "\"en_summary\":\"2019 Toyota Camry, GCC spec, 60,000 km.\"}\n"
    "</example>"
)


def _llm_enrich(row):
    from .llm import LLMUnavailable, structured

    text = f"Listing_ID: {row['Listing_ID']}\nTitle: {row['title']}\nDescription: {row['description']}"
    for attempt in range(3):
        try:
            result = structured(EnrichedListing, ENRICH_SYSTEM, text)
        except LLMUnavailable:
            return _regex_enrich(row), "no_key"
        except Exception:
            time.sleep(2 ** attempt)
            continue
        if result is None:
            return _regex_enrich(row), "parse_fallback"
        result.listing_id = int(row["Listing_ID"])
        result.color = result.color.lower() if result.color else None
        result.body_type = result.body_type.lower() if result.body_type else None
        result.spec = result.spec.lower() if result.spec else None
        if not result.en_summary:
            result.en_summary = str(row["description"]).strip()[:600]
        return result, "llm"
    return _regex_enrich(row), "error_fallback"


def build(use_llm=None):
    if use_llm is None:
        use_llm = HAS_LLM
    df = pd.read_csv(CLEANED_CSV)
    records = {}
    counts = {}
    total = len(df)
    for i, (_, row) in enumerate(df.iterrows(), start=1):
        if use_llm:
            item, source = _llm_enrich(row)
        else:
            item, source = _regex_enrich(row), "regex"
        records[str(item.listing_id)] = item.model_dump()
        counts[source] = counts.get(source, 0) + 1
        if i % 10 == 0 or i == total:
            ENRICHED_JSON.write_text(json.dumps(records, ensure_ascii=False, indent=2))
            print(f"  enriched {i}/{total} | sources={counts}", flush=True)
    return records


def load():
    if not ENRICHED_JSON.exists():
        build()
    return json.loads(ENRICHED_JSON.read_text())


if __name__ == "__main__":
    force_llm = "--llm" in sys.argv
    force_regex = "--regex" in sys.argv
    mode = True if force_llm else (False if force_regex else None)
    built = build(use_llm=mode)
    priced = sum(1 for v in built.values() if v.get("price_aed"))
    print(f"enriched {len(built)} listings -> {ENRICHED_JSON}")
    print(f"price present: {priced} | mileage present: {sum(1 for v in built.values() if v.get('mileage_km'))}")
