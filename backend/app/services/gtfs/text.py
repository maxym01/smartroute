import unicodedata

# Letters that NFKD does not decompose into a base letter + combining diacritic.
_EXTRA_FOLD = str.maketrans({"ł": "l", "ø": "o", "đ": "d", "ß": "ss"})


def fold_text(value: str) -> str:
    """Normalize for search: case-insensitive, without Polish diacritics ("Łąkowa" → "lakowa")."""
    folded = unicodedata.normalize("NFKD", value.casefold().translate(_EXTRA_FOLD))
    return "".join(ch for ch in folded if not unicodedata.combining(ch)).strip()
