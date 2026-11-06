from __future__ import annotations

import re
import unicodedata

_LEGAL_SUFFIX = re.compile(r"\b(?:gmbh|ag|se|kg|ug|inc|incorporated|ltd|limited|llc|plc|pty|sa|sas|bv|nv|ab|as|oy|sarl|srl|spa|sro|gbr|co|corp|corporation)\b", re.I)


def normalize_company_name(display_name: str) -> str:
    text = unicodedata.normalize("NFKD", display_name)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("°", " ").replace("˚", " ")
    text = _LEGAL_SUFFIX.sub(" ", text.lower())
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = " ".join(text.split())
    if text == "1komma5grad":
        return "1komma5"
    return text


def normalize_role(role: str) -> str:
    text = unicodedata.normalize("NFKD", role)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def cross_language_dedup_key(company_name: str, normalized_role: str, city: str | None) -> str:
    parts = (normalize_company_name(company_name), normalize_role(normalized_role), normalize_role(city or ""))
    return "|".join(parts)
