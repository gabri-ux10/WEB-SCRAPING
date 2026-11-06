"""Build a stratified 100-title manual review sheet with unverified expectations."""

from __future__ import annotations

import asyncio
import csv
import hashlib
import random
from collections import defaultdict
from pathlib import Path

from sqlalchemy import text

from app.database.session import engine as legacy_engine
from app.v2.classification import _normalized, _pattern, clean_title, _GENERIC_NONTECH
from app.v2.language import detect_language
from app.v2.taxonomy import load_taxonomy, taxonomy_aliases

OUTPUT = Path(__file__).resolve().parents[1] / "data/reference/cs_job_title_manual_review_v2.csv"


async def main() -> None:
    async with legacy_engine.connect() as conn:
        rows = (await conn.execute(text("""
            SELECT title, COUNT(*) AS occurrences FROM jobs
            WHERE title IS NOT NULL GROUP BY title ORDER BY title
        """))).all()
    taxonomy = load_taxonomy()
    aliases, _ = taxonomy_aliases(taxonomy)
    subdomains = {s["id"]: c["id"] for c in taxonomy["categories"] for s in c["subdomains"]}
    candidates = []
    for row in rows:
        raw = row.title
        if "\ufffd" in raw:
            continue
        try:
            clean = clean_title(raw)
        except ValueError:
            continue
        normalized = _normalized(clean)
        matches = []
        for subdomain_id, _language, alias in aliases:
            hit = _pattern(alias).search(normalized)
            if hit:
                matches.append((len(hit.group()), subdomain_id))
        best_length = max((length for length, _ in matches), default=0)
        best_ids = {sid for length, sid in matches if length == best_length}
        if len(best_ids) == 1:
            expected_subdomain = next(iter(best_ids))
            expected_category = subdomains[expected_subdomain]
        elif _GENERIC_NONTECH.search(clean):
            expected_subdomain = ""
            expected_category = "N"
        else:
            expected_subdomain = ""
            expected_category = "U"
        language, _confidence = detect_language(raw)
        language = language or "und"
        candidates.append({
            "raw_title": raw,
            "clean_title_expected_unverified": clean,
            "title_language_estimate": language,
            "legacy_posting_occurrences": row.occurrences,
            "expected_category_id_unverified": expected_category,
            "expected_sub_domain_id_unverified": expected_subdomain,
            "expected_label_status": "UNVERIFIED_MACHINE_EXPECTATION",
            "label_basis": "rules-only longest taxonomy alias; narrow non-tech title keywords; else Unclassified",
            "manual_category_id": "",
            "manual_sub_domain_id": "",
            "manual_clean_title": "",
            "reviewer_notes": "",
        })

    buckets = defaultdict(list)
    rng = random.Random(20261106)
    for row in candidates:
        buckets[(row["expected_category_id_unverified"], row["title_language_estimate"])].append(row)
    for bucket in buckets.values():
        bucket.sort(key=lambda item: hashlib.sha256(item["raw_title"].encode("utf-8")).hexdigest())
        rng.shuffle(bucket)
    bucket_keys = sorted(buckets, key=lambda item: (item[0], item[1]))
    selected = []
    while len(selected) < 100 and any(buckets.values()):
        for key in bucket_keys:
            if buckets[key] and len(selected) < 100:
                selected.append(buckets[key].pop())
    if len(selected) != 100:
        raise RuntimeError(f"Only {len(selected)} eligible distinct legacy titles found")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fields = list(selected[0])
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(selected)
    await legacy_engine.dispose()
    print(f"Wrote {len(selected)} stratified title rows to {OUTPUT}")
    for key in bucket_keys:
        count = sum(1 for row in selected if (row["expected_category_id_unverified"], row["title_language_estimate"]) == key)
        if count:
            print(f"stratum {key[0]} / {key[1]}: {count}")


if __name__ == "__main__":
    asyncio.run(main())
