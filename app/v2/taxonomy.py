from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

REFERENCE_DIR = Path(__file__).resolve().parents[2] / "data" / "reference"
TAXONOMY_PATH = REFERENCE_DIR / "cs_job_taxonomy_v2.json"
VOCABULARY_PATH = REFERENCE_DIR / "skills_vocabulary_v2.csv"
SOURCES_PATH = REFERENCE_DIR / "scrape_sources_v2.csv"


@dataclass(frozen=True)
class SkillTerm:
    slug: str
    label: str
    subdomain_ids: frozenset[str]
    roadmaps: tuple[str, ...]


def load_taxonomy(path: Path = TAXONOMY_PATH) -> dict:
    with path.open(encoding="utf-8") as file:
        taxonomy = json.load(file)
    if taxonomy.get("version") != "2.0":
        raise ValueError("Expected taxonomy version 2.0")
    if len(taxonomy.get("categories", [])) != 7:
        raise ValueError("Taxonomy must contain exactly seven categories")
    subdomains = [s for category in taxonomy["categories"] for s in category["subdomains"]]
    if len(subdomains) != 43:
        raise ValueError("Taxonomy must contain exactly 43 sub-domains")
    return taxonomy


def load_skills(path: Path = VOCABULARY_PATH) -> list[SkillTerm]:
    terms = []
    with path.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            label = (row.get("label") or "").strip()
            if not label or "\ufffd" in label:
                continue
            terms.append(SkillTerm(
                slug=row["slug"],
                label=label,
                subdomain_ids=frozenset(filter(None, (row.get("subdomain_ids") or "").split(";"))),
                roadmaps=tuple(filter(None, (row.get("roadmaps") or "").split(";"))),
            ))
    return terms


def taxonomy_aliases(taxonomy: dict) -> tuple[list[tuple[str, str, str]], list[dict]]:
    aliases = []
    invalid = []
    for category in taxonomy["categories"]:
        for subdomain in category["subdomains"]:
            values = [("en", a) for a in subdomain.get("title_aliases", [])]
            for lang, entries in subdomain.get("title_aliases_i18n", {}).items():
                values.extend((lang, a) for a in entries)
            for lang, value in values:
                if "\ufffd" in value:
                    invalid.append({"category_id": category["id"], "sub_domain_id": subdomain["id"], "language": lang, "alias": value})
                elif value.strip():
                    aliases.append((subdomain["id"], lang, value.strip()))
    return aliases, invalid
