from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable

from app.v2.taxonomy import SkillTerm, load_skills, load_taxonomy, taxonomy_aliases

_GENDER = re.compile(
    r"\s*(?:\(\s*(?:m\s*/\s*w\s*/\s*d|m\s*/\s*f\s*/\s*d|w\s*/\s*m\s*/\s*d|m\s*/\s*w\s*/\s*đ|m\s*/\s*w\s*/\s*i|f\s*/\s*m\s*/\s*x)\s*\)|\bm\s*\|\s*w\s*\|\s*d\b)\s*",
    re.I,
)
_ASIAN_TAG = re.compile(
    r"(?:【[^】]*[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af][^】]*】|\[[^\]]*(?:正社員|中途|新卒|契約社員|派遣|アルバイト|正職員|兼职|全职|合同工|정규직|계약직)[^\]]*\])"
)
_MODE_SUFFIX = re.compile(
    r"\s*(?:\((?:remote|hybrid|on[- ]?site|onsite|remoto|híbrido|hybride|home[- ]based)\)|\[(?:remote|hybrid|on[- ]?site|onsite)\]|[-–—|]\s*(?:remote|hybrid|on[- ]?site|onsite))\s*$",
    re.I,
)
_LOCATION_SUFFIXES = (
    "Berlin / Germany", "Berlin, Germany", "Berlin", "Nairobi", "London", "New York", "San Francisco",
    "Paris", "Amsterdam", "Munich", "München", "Singapore", "Tokyo", "Toronto", "Dublin",
    "Madrid", "Stockholm", "Zurich", "Zürich", "São Paulo", "Sao Paulo", "Milano",
)
_GENERIC_NONTECH = re.compile(
    r"\b(sales|marketing|healthcare|nurse|physician|doctor|human resources|hr|recruiter|recruitment|finance|accountant|lawyer|legal|operations|retail|seo specialist|content creator|customer service)\b",
    re.I,
)
_SENIORITY = [
    ("Intern / Werkstudent / Praktikum", re.compile(r"\b(intern|internship|werkstudent\w*|praktik\w*|apprentice|stagiaire|pasante|tirocinante|stagista)\b", re.I)),
    ("Junior", re.compile(r"\b(junior|jr\.?|entry[- ]level|berufseinsteiger\w*|débutant\w*|júnior)\b", re.I)),
    ("Mid-Level", re.compile(r"\b(mid[- ]level|middle[- ]level|medior)\b", re.I)),
    ("Senior", re.compile(r"\b(senior|sr\.?)\b", re.I)),
    ("Staff", re.compile(r"\bstaff\b", re.I)),
    ("Principal", re.compile(r"\bprincipal\b", re.I)),
    ("Lead", re.compile(r"\b(lead|tech lead|team lead)\b", re.I)),
    ("Head / Director", re.compile(r"\b(head|director|directeur|directrice|leiter|leiterin)\b", re.I)),
    ("III", re.compile(r"(?:^|\s)III(?:$|\s|[,(/-])", re.I)),
    ("II", re.compile(r"(?:^|\s)II(?:$|\s|[,(/-])", re.I)),
]
_SYNONYMS = {
    "js": "javascript", "postgres": "postgresql", "k8s": "kubernetes",
    "amazon web services": "aws", "nodejs": "node.js", "node js": "node.js",
    "reactjs": "react", "react.js": "react", "golang": "go",
    "google cloud platform": "google cloud", "ml": "machine learning",
}
_GENERIC_SKILLS = {"introduction", "testing", "fundamentals", "basics", "roadmap", "career path", "getting started"}
_AMBIGUOUS_SKILLS = {"go", "r", "c", "swift", "rust", "spring", "express", "flutter", "sql", "html", "css"}


@dataclass(frozen=True)
class Classification:
    clean_title: str
    clean_title_en: str
    title_language: str
    translation_method: str
    normalized_role: str
    seniority: str
    domain_specialization: str | None
    category: str
    sub_domain: str
    is_tech_role: bool
    confidence_flag: str
    category_id: str
    sub_domain_id: str | None
    tier: str | None
    role_confidence: float
    reason_code: str | None
    taxonomy_version: str
    classifier_version: str = "2.0.0"
    description_language: str | None = None
    language_confidence: float | None = None


def clean_title(raw_title: str | None) -> str:
    text = unicodedata.normalize("NFC", " ".join((raw_title or "").split()))
    if "\ufffd" in text:
        raise ValueError("title contains U+FFFD and must be quarantined for review")
    try:
        from ftfy import fix_text
        text = fix_text(text)
    except ImportError:
        pass
    text = _GENDER.sub(" ", text)
    text = re.sub(r"(?<=\w)[:*]in\b", "", text, flags=re.I)
    text = _ASIAN_TAG.sub(" ", text)
    while _MODE_SUFFIX.search(text):
        text = _MODE_SUFFIX.sub("", text).rstrip()
    for location in _LOCATION_SUFFIXES:
        text = re.sub(
            rf"\s*(?:\(|\[|\|\s*|[-–—]\s*){re.escape(location)}(?:\s*[/,]\s*[^)\]]+)?(?:\)|\])?\s*$",
            "", text, flags=re.I,
        )
    return " ".join(text.split()).strip(" \t-–—|,;")


def extract_seniority(title: str) -> str:
    for value, pattern in _SENIORITY:
        if pattern.search(title):
            return value
    return "Mid/Unspecified"


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower().replace("–", "-").replace("—", "-").strip())


@lru_cache(maxsize=10000)
def _pattern(alias: str) -> re.Pattern:
    escaped = re.escape(_normalized(alias)).replace(r"\ ", r"\s+")
    return re.compile(rf"(?<!\w){escaped}(?!\w)", re.I)


@lru_cache(maxsize=2)
def _cached_reference(taxonomy_path: str, vocabulary_path: str):
    taxonomy = load_taxonomy(Path(taxonomy_path))
    aliases, invalid = taxonomy_aliases(taxonomy)
    skills = load_skills(Path(vocabulary_path))
    subdomain_map = {s["id"]: (c, s) for c in taxonomy["categories"] for s in c["subdomains"]}
    return taxonomy, aliases, invalid, skills, subdomain_map


def extract_skills(text: str, terms: list[SkillTerm] | None = None) -> list[SkillTerm]:
    terms = terms if terms is not None else load_skills()
    haystack = f" {_normalized(text)} "
    found = []
    for term in terms:
        label = term.label.strip()
        low = label.lower()
        if low in _GENERIC_SKILLS or len(low) < 2:
            continue
        aliases = {low, *[key for key, value in _SYNONYMS.items() if value == low]}
        if low in _AMBIGUOUS_SKILLS and not re.search(
            r"\b(programming|developer|engineer|code|framework|database|language)\b", haystack, re.I
        ):
            continue
        if any(_pattern(alias).search(haystack) for alias in aliases):
            found.append(term)
    return found


def classify(
    raw_title: str | None,
    description: str | None = None,
    skills: list[str] | None = None,
    *,
    source_language: str | None = None,
    include_extensions: bool = True,
    llm_fallback: Callable[[str, list[str]], dict | None] | None = None,
    translator: Callable[[str], str | None] | None = None,
    taxonomy_path: Path = Path(__file__).resolve().parents[2] / "data/reference/cs_job_taxonomy_v2.json",
    vocabulary_path: Path = Path(__file__).resolve().parents[2] / "data/reference/skills_vocabulary_v2.csv",
) -> Classification:
    from app.v2.language import detect_language

    raw_title = raw_title or ""
    description = description or ""
    title = clean_title(raw_title)
    seniority = extract_seniority(title)
    taxonomy, aliases, _invalid_aliases, skill_terms, subdomain_map = _cached_reference(str(taxonomy_path), str(vocabulary_path))
    normalized_title = _normalized(title)
    alias_matches = []
    for subdomain_id, _language, alias in aliases:
        match = _pattern(alias).search(normalized_title)
        if match:
            alias_matches.append((len(match.group()), subdomain_id))
    best_length = max((length for length, _ in alias_matches), default=0)
    best_ids = sorted({sid for length, sid in alias_matches if length == best_length})
    decision_id = best_ids[0] if len(best_ids) == 1 else None

    # A clear title match cannot be overridden by skills; only scan the full vocabulary
    # when the title needs a tie-break or fallback decision.
    matched_skills = [] if decision_id else extract_skills(f"{title} {description}", skill_terms)
    skill_labels = list(dict.fromkeys((skills or []) + [term.label for term in matched_skills]))
    votes: dict[str, int] = {}
    for term in matched_skills:
        for subdomain_id in term.subdomain_ids:
            votes[subdomain_id] = votes.get(subdomain_id, 0) + 1
    confidence = 0.92
    reason_code = None

    if len(best_ids) > 1:
        ranked = sorted(((votes.get(sid, 0), sid) for sid in best_ids), reverse=True)
        if ranked[0][0] >= 3 and ranked[0][0] >= 2 * max(1, ranked[1][0]):
            decision_id, confidence = ranked[0][1], 0.76
        else:
            reason_code = "conflicting_skills" if any(votes.values()) else "ambiguous_title"
    elif decision_id is None:
        ranked = sorted(((count, sid) for sid, count in votes.items()), reverse=True)
        if ranked and ranked[0][0] >= 3 and ranked[0][0] >= 2 * (ranked[1][0] if len(ranked) > 1 else 0):
            decision_id, confidence = ranked[0][1], 0.76
        elif ranked:
            reason_code = "conflicting_skills"

    title_language, title_confidence = detect_language(raw_title, source_language)
    description_language, description_confidence = detect_language(description, source_language)
    language_confidence = description_confidence if description_confidence is not None else title_confidence
    title_language = title_language or "und"

    if decision_id is None:
        if _GENERIC_NONTECH.search(title):
            fallback = taxonomy["fallback_categories"]["N"]
            return Classification(
                title, title, title_language, "fallback_role", title, seniority, None,
                fallback["name"], fallback["sub_domain"], False, "HIGH", "N", None, None,
                0.9, "clearly_non_cs", taxonomy["version"], description_language=description_language,
                language_confidence=language_confidence,
            )
        reason_code = reason_code or ("unparseable_text" if not title else (
            "non_english_unmatched" if title_language not in {"en", "und"} else "ambiguous_title"
        ))
        if llm_fallback and title:
            suggestion = llm_fallback(title, skill_labels)
            if suggestion and suggestion.get("sub_domain_id") in subdomain_map:
                decision_id = suggestion["sub_domain_id"]
                confidence = float(suggestion.get("role_confidence", 0.0))
                reason_code = None
        if decision_id is None:
            fallback = taxonomy["fallback_categories"]["U"]
            return Classification(
                title, title, title_language, "fallback_role", title, seniority, None,
                fallback["name"], fallback["sub_domain"], False, "LOW", "U", None, None,
                0.4, reason_code, taxonomy["version"], description_language=description_language,
                language_confidence=language_confidence,
            )

    category, subdomain = subdomain_map[decision_id]
    if subdomain.get("source") == "extension" and not include_extensions:
        fallback = taxonomy["fallback_categories"]["U"]
        return Classification(
            title, title, title_language, "fallback_role", title, seniority, None,
            fallback["name"], fallback["sub_domain"], False, "LOW", "U", None, None,
            0.4, "extension_disabled", taxonomy["version"], description_language=description_language,
            language_confidence=language_confidence,
        )

    normalized_role = subdomain.get("normalized_roles", [subdomain["name"]])[0]
    specialization = None
    if "," in title:
        suffix = title.rsplit(",", 1)[1].strip()
        if suffix and suffix.lower() not in {"remote", "hybrid"}:
            specialization = suffix
    translated = translator(title) if title_language != "en" and translator else None
    clean_title_en = translated or (f"{seniority} {normalized_role}" if title_language != "en" else title)
    translation_method = "llm" if translated else ("fallback_role" if title_language != "en" else "original_english")
    category_id = category["id"]
    is_tech = category_id in {f"C{i}" for i in range(1, 8)}
    flag = "HIGH" if confidence >= 0.85 else ("MEDIUM" if confidence >= 0.70 else "LOW")
    if flag == "LOW":
        fallback = taxonomy["fallback_categories"]["U"]
        return Classification(
            title, clean_title_en, title_language, translation_method, title, seniority,
            specialization, fallback["name"], fallback["sub_domain"], False, "LOW", "U",
            None, None, confidence, "low_confidence", taxonomy["version"],
            description_language=description_language, language_confidence=language_confidence,
        )
    return Classification(
        title, clean_title_en, title_language, translation_method, normalized_role,
        seniority, specialization, category["name"], subdomain["name"], is_tech,
        flag, category_id, subdomain["id"], subdomain.get("tier"), confidence,
        None, taxonomy["version"], description_language=description_language,
        language_confidence=language_confidence,
    )
