import re

from rapidfuzz import fuzz, process

MAKE_ALIASES = {
    "vw": "volkswagen", "volks": "volkswagen", "volkswagon": "volkswagen",
    "chevy": "chevrolet", "chev": "chevrolet",
    "merc": "mercedes-benz", "mercedes": "mercedes-benz", "benz": "mercedes-benz",
    "mercedes benz": "mercedes-benz",
    "beemer": "bmw", "bimmer": "bmw",
    "range rover": "land rover", "rangerover": "land rover", "landrover": "land rover",
    "land-rover": "land rover", "rover": "land rover",
    "rolls": "rolls-royce", "roller": "rolls-royce", "rolls royce": "rolls-royce",
    "aston": "aston martin", "lambo": "lamborghini", "mitsu": "mitsubishi",
    "mini cooper": "mini", "vette": "chevrolet", "landy": "land rover",
}

MAKE_THRESHOLD = 82
MODEL_THRESHOLD = 85


def _norm(value):
    return re.sub(r"\s+", " ", str(value).strip().lower())


def canonical_make(query, known_makes):
    if not query:
        return None
    q = _norm(query)
    if q in known_makes:
        return q
    alias = MAKE_ALIASES.get(q)
    if alias and alias in known_makes:
        return alias
    match = process.extractOne(q, list(known_makes), scorer=fuzz.WRatio)
    if match and match[1] >= MAKE_THRESHOLD:
        return match[0]
    return None


def canonical_model(query, known_models):
    if not query:
        return None
    q = _norm(query)
    if q in known_models:
        return q
    match = process.extractOne(q, list(known_models), scorer=fuzz.WRatio)
    if match and match[1] >= MODEL_THRESHOLD:
        return match[0]
    return None


def detect_make(text, known_makes):
    t = _norm(text)
    mapping = {m: m for m in known_makes}
    for alias, canon in MAKE_ALIASES.items():
        if canon in known_makes:
            mapping.setdefault(alias, canon)
    for phrase in sorted(mapping, key=len, reverse=True):
        if re.search(r"\b" + re.escape(phrase) + r"\b", t):
            return mapping[phrase]
    return None


def detect_model(text, known_models):
    t = _norm(text)
    for model in sorted(known_models, key=len, reverse=True):
        if len(model) < 2:
            continue
        variants = {model, model.replace("-", " "), model.replace(" ", "-")}
        if any(re.search(r"\b" + re.escape(v) + r"\b", t) for v in variants):
            return model
    return None
