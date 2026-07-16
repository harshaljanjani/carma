import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval_retrieval import enr, evaluate, report

HELDOUT = [
    ("make", "any nissan please", lambda l: l.make == "nissan"),
    ("make", "i want a porsche", lambda l: l.make == "porsche"),
    ("make_alias", "got any chevy", lambda l: l.make == "chevrolet"),
    ("make_alias", "show me a bimmer", lambda l: l.make == "bmw"),
    ("make_alias", "a landrover", lambda l: l.make == "land rover"),
    ("year_range", "audi 2019 or newer", lambda l: l.make == "audi" and l.year >= 2019),
    ("year_range", "cars made before 2012", lambda l: l.year <= 2012),
    ("year_range", "ford between 2010 and 2016", lambda l: l.make == "ford" and 2010 <= l.year <= 2016),
    ("year_range", "anything since 2021", lambda l: l.year >= 2021),
    ("year_range", "a bentley older than 2020", lambda l: l.make == "bentley" and l.year <= 2020),
    ("mileage", "nissan below 100000 km", lambda l: l.make == "nissan" and enr(l).get("mileage_km") is not None and enr(l).get("mileage_km") <= 100000),
    ("mileage", "cars with less than 40000 km", lambda l: enr(l).get("mileage_km") is not None and enr(l).get("mileage_km") <= 40000),
    ("color", "silver cars", lambda l: "silver" in (enr(l).get("color") or "").lower()),
    ("color", "a blue bmw", lambda l: l.make == "bmw" and "blue" in (enr(l).get("color") or "").lower()),
    ("body", "show me a coupe", lambda l: (enr(l).get("body_type") or "").lower() == "coupe"),
    ("combined", "black mercedes after 2019", lambda l: l.make == "mercedes-benz" and l.year >= 2019 and "black" in (enr(l).get("color") or "").lower()),
    ("combined", "toyota suv under 90000 km", lambda l: l.make == "toyota" and (enr(l).get("body_type") or "").lower() == "suv" and enr(l).get("mileage_km") is not None and enr(l).get("mileage_km") <= 90000),
    ("no_match", "any kia from 2024", lambda l: l.make == "kia" and l.year >= 2024),
]

if __name__ == "__main__":
    print("HELD-OUT generalization set (queries the fixes were never tuned against):\n")
    report(evaluate(HELDOUT))
