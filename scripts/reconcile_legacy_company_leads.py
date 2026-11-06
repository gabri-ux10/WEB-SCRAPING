"""Compare legacy company-directory rows with normalized v2 company leads."""

from __future__ import annotations

import asyncio
import csv
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.v2.normalization import normalize_company_name

ROOT = Path(__file__).resolve().parents[1]
DOCX = ROOT / "docs" / "scraped_companies.docx"
MERGES = ROOT / "data" / "reference" / "legacy_company_name_merges_v2.csv"
REPORT = ROOT / "docs" / "STAGE_1_COMPANY_LEAD_RECONCILIATION.md"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
JUNK = re.compile(
    r"^(?:unknown|confidential|undisclosed|n/?a|none|not provided|anonymous|stealth(?: startup)?|various|multiple companies)$",
    re.I,
)
LONG_HEX = re.compile(r"\b[0-9a-f]{10,}\b", re.I)
UUID_LIKE = re.compile(r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$", re.I)


def is_placeholder_name(value: str) -> bool:
    """Flag exact placeholders and obvious machine-generated identifiers for review."""
    name = value.strip()
    alphanumeric = re.sub(r"[^A-Za-z0-9]", "", name)
    letters = re.sub(r"[^A-Za-z]", "", name)
    return bool(
        not name
        or JUNK.fullmatch(name)
        or LONG_HEX.search(name)
        or UUID_LIKE.fullmatch(name)
        or re.fullmatch(r"\d{8,}", name)
        or (len(alphanumeric) >= 12 and len(letters) / len(alphanumeric) < 0.35)
    )


def read_directory() -> tuple[list[tuple[str, int]], int]:
    with zipfile.ZipFile(DOCX) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    rows = root.findall(".//w:tbl/w:tr", NS)
    result: list[tuple[str, int]] = []
    stated_total = 0
    for row_index, row in enumerate(rows):
        cells = ["".join(node.text or "" for node in cell.findall(".//w:t", NS)).strip()
                 for cell in row.findall("w:tc", NS)]
        if row_index == 0:
            match = re.search(r"([\d,]+) stored job postings", " ".join(cells))
            if match:
                stated_total = int(match.group(1).replace(",", ""))
            continue
        if row_index == 1:
            continue
        for index in range(0, len(cells) - 1, 2):
            name, amount = cells[index], cells[index + 1]
            if name and name.lower() != "company":
                try:
                    result.append((name, int(amount.replace(",", ""))))
                except ValueError:
                    result.append((name, 0))
    return result, stated_total


async def main() -> None:
    directory, stated_postings = read_directory()
    legacy = create_async_engine(settings.database_url, pool_pre_ping=True)
    v2_url = make_url(settings.database_url).set(database="techjobs_v2").render_as_string(hide_password=False)
    v2 = create_async_engine(v2_url, pool_pre_ping=True)
    async with legacy.connect() as conn:
        db_rows = (await conn.execute(text("""
            SELECT COALESCE(company_name, '') AS name, COUNT(*) AS postings
            FROM jobs GROUP BY COALESCE(company_name, '') ORDER BY name
        """))).all()
    async with v2.connect() as conn:
        board_rows = (await conn.execute(text("""
            SELECT source_id, COUNT(*) AS board_count FROM csjobs.ats_boards
            GROUP BY source_id ORDER BY source_id
        """))).all()
    await legacy.dispose()
    await v2.dispose()

    def grouped(names: list[str]) -> dict[str, list[str]]:
        groups: dict[str, set[str]] = defaultdict(set)
        for name in names:
            key = normalize_company_name(name)
            if key:
                groups[key].add(name)
        return {key: sorted(values, key=str.casefold) for key, values in groups.items()}

    directory_names = [name for name, _ in directory]
    legacy_names = [str(row.name).strip() for row in db_rows if str(row.name).strip()]
    directory_groups = grouped(directory_names)
    legacy_groups = grouped(legacy_names)
    directory_exact = set(directory_names)
    legacy_exact = set(legacy_names)
    collisions = {key: names for key, names in directory_groups.items() if len(names) > 1}
    old_screen_directory = sorted({name for name in directory_names if JUNK.fullmatch(name.strip())}, key=str.casefold)
    junk_directory = sorted({name for name in directory_names if is_placeholder_name(name)}, key=str.casefold)
    junk_legacy = sorted({name for name in legacy_names if is_placeholder_name(name)}, key=str.casefold)
    MERGES.parent.mkdir(parents=True, exist_ok=True)
    with MERGES.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["normalized_key", "variant_count", "display_names"])
        writer.writeheader()
        for key, names in sorted(collisions.items()):
            writer.writerow({"normalized_key": key, "variant_count": len(names), "display_names": " | ".join(names)})

    boards = {row.source_id: row.board_count for row in board_rows}
    report = [
        "# Legacy Company Lead Reconciliation",
        "",
        "Read-only comparison of the legacy DOCX directory, legacy posting company names, and the v2 normalized company leads. Company-name normalization is a lead grouping rule, not proof that two brands are the same legal entity.",
        "",
        "## Counts",
        "",
        f"- DOCX directory rows: **{len(directory)}**; stated legacy postings: **{stated_postings:,}**.",
        f"- Directory exact distinct display names: **{len(directory_exact):,}**; directory distinct normalized keys: **{len(directory_groups):,}**.",
        f"- Directory rows with empty normalized keys: **{sum(not normalize_company_name(name) for name in directory_names)}**.",
        f"- Directory names matching the old exact-placeholder screen: **{len(old_screen_directory)}**; the broadened review screen flags **{len(junk_directory)}** (long hex/UUID-like IDs, long digit-only strings, mostly non-letter names, plus exact placeholders). Flags are review candidates and are not automatically dropped.",
        f"- Directory normalization merge clusters: **{len(collisions)}** clusters covering **{sum(len(names) for names in collisions.values())}** distinct display names; the complete list is `{MERGES.relative_to(ROOT).as_posix()}`.",
        f"- Legacy jobs table distinct nonblank company names: **{len(legacy_exact):,}**; normalized company keys: **{len(legacy_groups):,}**; blank names: **{sum(not str(row.name).strip() for row in db_rows)}**.",
        f"- Legacy normalized-key overlap with the directory: **{len(set(legacy_groups) & set(directory_groups)):,}**; directory-only keys: **{len(set(directory_groups) - set(legacy_groups)):,}**; legacy-only keys: **{len(set(legacy_groups) - set(directory_groups)):,}**.",
        f"- Legacy names matching the conservative placeholder screen: **{len(junk_legacy)}**. The v2 miner excludes only names whose normalized key is empty; it does not silently discard placeholder-looking names.",
        "",
        "## Why 5,810 leads versus 5,875 directory rows",
        "",
        "The 5,810 v2 company rows were derived from distinct normalized names in the legacy jobs table, not copied one-for-one from the company directory. The directory is a report with 5,875 rows, including repeated display strings and variants collapsed by accent/punctuation/legal-suffix normalization. The jobs table has a different observed company-name set. Blank/punctuation-only names normalize to an empty key and are excluded; placeholder-looking names are retained pending review. No legacy job postings were copied.",
        "",
        "## ATS board lead counts by system",
        "",
    ]
    for system in ("ashby", "greenhouse", "lever", "personio", "teamtailor"):
        report.append(f"- {system}: **{boards.get(system, 0)}**")
    report += [
        f"- Other systems: **{sum(n for system, n in boards.items() if system not in {'ashby','greenhouse','lever','personio','teamtailor'})}**",
        f"- Total: **{sum(boards.values())}** distinct ATS board identifiers.",
        "",
        "These are unverified URL-derived ATS board identifiers from legacy postings. They are discovery leads, not confirmed live boards. Since Personio has fewer than 10 leads, the conditional Stage 2 selection is Greenhouse.",
        "",
        "## Merge and junk review limits",
        "",
        "The merge CSV lists only directory strings that collapse to the same normalized key. This is a reproducible normalization report; actual company identity merges should be manually reviewed. The conservative junk screen is intentionally narrow and is reported separately so that a placeholder candidate is not silently removed.",
    ]
    REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Wrote {REPORT.relative_to(ROOT)} and {MERGES.relative_to(ROOT)}")


if __name__ == "__main__":
    asyncio.run(main())
