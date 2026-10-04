from pathlib import Path

import yaml

from app.classification.categories import CATEGORIES
from app.classification.skills import extract_skills


def _categories():
    path = Path(__file__).resolve().parents[2] / "config" / "tech_categories.yml"
    if path.exists():
        configured = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return configured.get("categories", CATEGORIES)
    return CATEGORIES


def classify(title: str | None, description: str | None = None):
    title_text = " " + (title or "").lower() + " "
    hay = title_text + " " + (description or "").lower() + " "
    if "cloud security" in title_text:
        return "Cybersecurity", ["Cloud Security"]
    special = [
        ("Frontend Engineering", ["frontend", "front-end"]),
        ("Backend Engineering", ["backend", "back-end"]),
        ("Full Stack Engineering", ["full stack", "fullstack"]),
    ]
    for category, terms in special:
        if any(term in title_text for term in terms):
            return "Software Engineering", [category]
    matches = [
        cat for cat, terms in _categories().items() if any(term.lower() in hay for term in terms)
    ]
    if not matches:
        return "Other Technology", []
    primary = matches[0]
    return primary, list(dict.fromkeys(cat for cat in matches if cat != primary))


def enrich_classification(job):
    job.primary_category, job.secondary_categories = classify(job.title, job.description)
    job.skills = extract_skills(f"{job.title or ''} {job.description or ''}")
    return job
