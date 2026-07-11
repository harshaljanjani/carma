import pandas as pd

from .config import CLEANED_CSV
from .enrich import load as load_enriched
from .schemas import Listing

_CATALOG = None


def _build():
    df = pd.read_csv(CLEANED_CSV)
    enriched = load_enriched()
    catalog = {}
    for _, row in df.iterrows():
        lid = int(row["Listing_ID"])
        ext = enriched.get(str(lid), {})
        catalog[lid] = Listing(
            listing_id=lid,
            year=int(row["year"]),
            make=str(row["make"]),
            model=str(row["model"]),
            trim=str(row["trim"]),
            title=str(row["title"]),
            color=ext.get("color"),
            body_type=ext.get("body_type"),
            mileage_km=ext.get("mileage_km"),
            price_aed=ext.get("price_aed"),
            price_is_estimate=ext.get("price_is_estimate", False),
            photo_url=str(row["photo_url"]),
            summary=ext.get("en_summary"),
        )
    return catalog


def catalog():
    global _CATALOG
    if _CATALOG is None:
        _CATALOG = _build()
    return _CATALOG


def all_listings():
    return list(catalog().values())


def get_listing(listing_id):
    return catalog().get(int(listing_id))


def summary_text(listing_id):
    enriched = load_enriched()
    return enriched.get(str(int(listing_id)), {}).get("en_summary", "")
