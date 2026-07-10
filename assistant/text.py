import re

DOMAIN_STOPWORDS = {
    "car", "cars", "vehicle", "vehicles", "used", "sale", "sell", "selling", "buy",
    "want", "wanted", "looking", "show", "find", "get", "need", "please", "like",
    "dealer", "dealership", "showroom", "contact", "call", "whatsapp", "price",
    "offer", "deal", "gcc", "spec", "specs", "km", "kms", "aed", "condition",
    "available", "service", "warranty", "us", "our", "we", "al",
    "inventory", "see", "options", "option", "best", "selection", "browse",
    "stuff", "thing", "things", "something", "anything", "list",
}

_STOPWORDS = None


def _load_nltk_stopwords():
    try:
        import nltk
        from nltk.corpus import stopwords

        def collect():
            return set(stopwords.words("english")) | set(stopwords.words("arabic"))

        try:
            return collect()
        except LookupError:
            nltk.download("stopwords", quiet=True)
            return collect()
    except Exception:
        return set()


def stopwords_set():
    global _STOPWORDS
    if _STOPWORDS is None:
        _STOPWORDS = _load_nltk_stopwords() | DOMAIN_STOPWORDS
    return _STOPWORDS


def tokens(text):
    stops = stopwords_set()
    return [
        t
        for t in re.findall(r"[^\W_]+", str(text).lower(), re.UNICODE)
        if t not in stops and len(t) > 1
    ]
