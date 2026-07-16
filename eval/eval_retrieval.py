import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from assistant.agent import _extract_filter, _heuristic_filter
from assistant.data import all_listings
from assistant.enrich import load as load_enriched
from assistant.retrieval import search

EXTRACT = _extract_filter if os.getenv("EVAL_LLM") else _heuristic_filter

ENR = load_enriched()


def enr(l):
    return ENR.get(str(l.listing_id), {})


CASES = [
    ("make", "show me toyota cars", lambda l: l.make == "toyota"),
    ("make", "any mercedes", lambda l: l.make == "mercedes-benz"),
    ("make_alias", "do you have a vw", lambda l: l.make == "volkswagen"),
    ("make_alias", "looking for a range rover", lambda l: l.make == "land rover"),
    ("year_range", "toyota after 2020", lambda l: l.make == "toyota" and l.year >= 2020),
    ("year_range", "cars before 2010", lambda l: l.year <= 2010),
    ("year_range", "mercedes between 2015 and 2018", lambda l: l.make == "mercedes-benz" and 2015 <= l.year <= 2018),
    ("year_range", "bmw newer than 2019", lambda l: l.make == "bmw" and l.year >= 2019),
    ("year_range", "a nissan older than 2018", lambda l: l.make == "nissan" and l.year <= 2018),
    ("year_exact", "2020 bmw", lambda l: l.make == "bmw" and l.year == 2020),
    ("mileage", "toyota under 80000 km", lambda l: l.make == "toyota" and enr(l).get("mileage_km") is not None and enr(l).get("mileage_km") <= 80000),
    ("mileage", "cars under 50000 km", lambda l: enr(l).get("mileage_km") is not None and enr(l).get("mileage_km") <= 50000),
    ("color", "white cars", lambda l: "white" in (enr(l).get("color") or "").lower()),
    ("color", "black mercedes", lambda l: l.make == "mercedes-benz" and "black" in (enr(l).get("color") or "").lower()),
    ("body", "show me an suv", lambda l: (enr(l).get("body_type") or "").lower() == "suv"),
    ("body", "any convertible", lambda l: (enr(l).get("body_type") or "").lower() == "convertible"),
    ("combined", "white toyota after 2018", lambda l: l.make == "toyota" and l.year >= 2018 and "white" in (enr(l).get("color") or "").lower()),
    ("no_match", "honda cars", lambda l: l.make == "honda"),
    ("no_match", "cars after 2030", lambda l: l.year >= 2030),
]


def evaluate(cases=CASES):
    listings = all_listings()
    rows = []
    for category, query, pred in cases:
        gold = {l.listing_id for l in listings if pred(l)}
        got = {l.listing_id for l in search(EXTRACT(query), limit=100)}
        tp = len(got & gold)
        precision = tp / len(got) if got else (1.0 if not gold else 0.0)
        recall = tp / len(gold) if gold else 1.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        exact = got == gold
        rows.append((category, query, len(gold), len(got), precision, recall, f1, exact))
    return rows


def report(rows):
    print(f"{'category':<12}{'query':<38}{'gold':>5}{'got':>5}{'P':>6}{'R':>6}{'F1':>6}  exact")
    print("-" * 92)
    for c, q, g, n, p, r, f, e in rows:
        print(f"{c:<12}{q[:37]:<38}{g:>5}{n:>5}{p:>6.2f}{r:>6.2f}{f:>6.2f}  {'PASS' if e else 'FAIL'}")
    n = len(rows)
    print("-" * 92)
    print(f"macro precision {sum(r[4] for r in rows)/n:.3f} | macro recall {sum(r[5] for r in rows)/n:.3f} "
          f"| macro F1 {sum(r[6] for r in rows)/n:.3f} | exact-match {sum(1 for r in rows if r[7])/n:.1%}")


if __name__ == "__main__":
    report(evaluate())
