import re


def _css_color_names():
    try:
        import webcolors

        try:
            return set(webcolors.names("css3"))
        except Exception:
            return set(getattr(webcolors, "CSS3_NAMES_TO_HEX", {}).keys())
    except Exception:
        return set()


AUTOMOTIVE_COLORS = {
    "charcoal", "gunmetal", "champagne", "burgundy", "maroon", "beige", "ivory",
    "cream", "pearl", "metallic", "bronze", "graphite", "sand", "titanium",
    "platinum", "wine", "off-white", "matte black", "pearl white", "dark blue",
    "light blue", "dark grey", "dark gray", "light grey", "navy blue",
    "gunmetal grey", "space grey", "midnight black", "pearl black",
}

COLOR_NORMALIZE = {"grey": "gray"}

_COLOR_TERMS = sorted(_css_color_names() | AUTOMOTIVE_COLORS, key=len, reverse=True)
COLOR_RE = re.compile(r"\b(" + "|".join(re.escape(t) for t in _COLOR_TERMS) + r")\b", re.I)

BODY_NORMALIZE = {
    "crossover": "suv", "saloon": "sedan", "estate": "wagon",
    "cabriolet": "convertible", "4x4": "suv", "off-road": "suv", "mpv": "minivan",
}
_BODY_TERMS = sorted(
    [
        "suv", "sedan", "coupe", "hatchback", "convertible", "cabriolet", "roadster",
        "pickup", "truck", "crossover", "wagon", "estate", "van", "minivan", "mpv",
        "liftback", "fastback", "limousine", "saloon", "off-road", "4x4",
    ],
    key=len,
    reverse=True,
)
BODY_RE = re.compile(r"\b(" + "|".join(re.escape(t) for t in _BODY_TERMS) + r")\b", re.I)

SPEC_NORMALIZE = {
    "us": "usa", "us spec": "usa", "us specs": "usa", "american": "usa",
    "euro": "european", "euro spec": "european", "japan": "japanese",
    "japan spec": "japanese", "korea": "korean", "canada": "canadian",
    "gulf": "gcc", "gulf spec": "gcc", "khaleeji": "gcc", "china": "chinese",
}
_SPEC_TERMS = sorted(
    [
        "gcc", "usa", "american", "us spec", "us specs", "european", "euro spec",
        "japanese", "japan spec", "korean", "canadian", "gulf spec", "khaleeji",
        "chinese",
    ],
    key=len,
    reverse=True,
)
SPEC_RE = re.compile(r"\b(" + "|".join(re.escape(t) for t in _SPEC_TERMS) + r")\b", re.I)


def _first(regex, text, normalize):
    match = regex.search(text)
    if not match:
        return None
    value = match.group(1).lower()
    return normalize.get(value, value)


def find_color(text):
    return _first(COLOR_RE, text, COLOR_NORMALIZE)


def find_body(text):
    return _first(BODY_RE, text, BODY_NORMALIZE)


def find_spec(text):
    return _first(SPEC_RE, text, SPEC_NORMALIZE)
