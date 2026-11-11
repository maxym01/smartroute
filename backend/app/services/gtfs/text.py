import unicodedata

# Litery, których NFKD nie rozkłada na literę bazową + znak diakrytyczny.
_EXTRA_FOLD = str.maketrans({"ł": "l", "ø": "o", "đ": "d", "ß": "ss"})


def fold_text(value: str) -> str:
    """Normalizacja do wyszukiwania: bez wielkości liter i polskich znaków ("Łąkowa" → "lakowa")."""
    folded = unicodedata.normalize("NFKD", value.casefold().translate(_EXTRA_FOLD))
    return "".join(ch for ch in folded if not unicodedata.combining(ch)).strip()
