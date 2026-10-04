import hashlib
import re
from difflib import SequenceMatcher


def content_hash(job) -> str:
    material = "|".join(
        [
            job.company_name.lower().strip(),
            " ".join(job.title.lower().split()),
            (job.location or "").lower().strip(),
            re.sub(r"\s+", " ", (job.description or "").lower())[:1200],
        ]
    )
    return hashlib.sha256(material.encode()).hexdigest()


def similarity(a, b) -> float:
    company = SequenceMatcher(None, a.company_name.lower(), b.company_name.lower()).ratio()
    title = SequenceMatcher(
        None, a.normalized_title or a.title.lower(), b.normalized_title or b.title.lower()
    ).ratio()
    location = SequenceMatcher(None, (a.location or "").lower(), (b.location or "").lower()).ratio()
    desc = SequenceMatcher(
        None, (a.description or "")[:500].lower(), (b.description or "")[:500].lower()
    ).ratio()
    return round(0.30 * company + 0.30 * title + 0.15 * location + 0.25 * desc, 4)
