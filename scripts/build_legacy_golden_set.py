"""Create an alias-labeled, reviewable golden-title set from legacy titles only."""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from pathlib import Path

from sqlalchemy import text

from app.database.session import engine as legacy_engine
from app.v2.classification import _normalized, _pattern, clean_title
from app.v2.taxonomy import load_taxonomy, taxonomy_aliases

OUTPUT = Path(__file__).resolve().parents[1] / "data" / "reference" / "golden_titles_legacy_v2.jsonl"


async def main() -> None:
    async with legacy_engine.connect() as conn:
        result = await conn.execute(text("SELECT title, COUNT(*) AS postings FROM jobs WHERE title IS NOT NULL GROUP BY title ORDER BY COUNT(*) DESC, title"))
        titles = [row.title for row in result]
    taxonomy = load_taxonomy()
    order = [s["id"] for c in taxonomy["categories"] for s in c["subdomains"]]
    aliases, _invalid_aliases = taxonomy_aliases(taxonomy)
    subdomains = {s["id"]: (c, s) for c in taxonomy["categories"] for s in c["subdomains"]}
    grouped: dict[str, list[dict]] = defaultdict(list)
    for raw_title in titles:
        if "\ufffd" in raw_title:
            continue
        clean = clean_title(raw_title)
        normalized = _normalized(clean)
        matches = []
        for subdomain_id, _language, alias in aliases:
            match = _pattern(alias).search(normalized)
            if match:
                matches.append((len(match.group()), subdomain_id))
        best_length = max((length for length, _ in matches), default=0)
        best_ids = {subdomain_id for length, subdomain_id in matches if length == best_length}
        if len(best_ids) == 1:
            subdomain_id = next(iter(best_ids))
            category, subdomain = subdomains[subdomain_id]
            if category["id"] not in {f"C{i}" for i in range(1, 8)}:
                continue
            grouped[subdomain_id].append({
                "raw_title": raw_title,
                "expected_category_id": category["id"],
                "expected_sub_domain_id": subdomain_id,
                "expected_clean_title": clean,
                "label_basis": "unique longest taxonomy alias match; legacy title",
                "label_status": "UNVERIFIED_MACHINE_EXPECTATION",
            })
    selected = []
    for depth in range(max((len(values) for values in grouped.values()), default=0)):
        for subdomain_id in order:
            if depth < len(grouped[subdomain_id]):
                selected.append(grouped[subdomain_id][depth])
                if len(selected) == 300:
                    break
        if len(selected) == 300:
            break
    if len(selected) < 300:
        raise RuntimeError(f"Only {len(selected)} clear, non-corrupted legacy titles matched; do not pad with synthetic titles")
    selected = selected[:300]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as stream:
        for row in selected:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    await legacy_engine.dispose()
    print(f"Wrote {len(selected)} distinct legacy titles to {OUTPUT.name}; labeled by unique longest taxonomy alias match.")


if __name__ == "__main__":
    asyncio.run(main())
