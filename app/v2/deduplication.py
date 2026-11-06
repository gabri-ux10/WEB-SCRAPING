from __future__ import annotations

import hashlib
import re

from app.v2.normalization import cross_language_dedup_key


def canonical_fingerprint(company: str, normalized_role: str, city: str | None) -> str:
    key = cross_language_dedup_key(company, normalized_role, city)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def description_fingerprint(description: str | None) -> str | None:
    if not description or not description.strip():
        return None
    compact = re.sub(r"\s+", " ", description).strip().casefold()[:300]
    return hashlib.sha256(compact.encode("utf-8")).hexdigest()
