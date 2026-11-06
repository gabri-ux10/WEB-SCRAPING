import csv
import json
from pathlib import Path

import pytest

from app.v2.classification import classify, clean_title, extract_seniority, extract_skills
from app.v2.taxonomy import SkillTerm

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("marker", ["(m/w/d)", "(m/f/d)", "(w/m/d)", "(m/w/đ)", "(m/w/i)", "(f/m/x)", "m|w|d"])
def test_each_gender_marker_is_removed(marker):
    assert clean_title(f"Software Engineer {marker}") == "Software Engineer"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Applikationsmanager:in", "Applikationsmanager"),
        ("Cloud Entwickler*in", "Cloud Entwickler"),
        ("【正社員】Webエンジニア", "Webエンジニア"),
        ("[中途]バックエンドエンジニア", "バックエンドエンジニア"),
        ("[정규직] 소프트웨어 엔지니어", "소프트웨어 엔지니어"),
        ("[兼职]云平台工程师", "云平台工程师"),
        ("Senior Engineer (Remote)", "Senior Engineer"),
        ("Senior Engineer [Hybrid]", "Senior Engineer"),
        ("Senior Engineer - Remote", "Senior Engineer"),
        ("Senior Engineer (Berlin / Germany)", "Senior Engineer"),
        ("Senior Engineer | Nairobi", "Senior Engineer"),
        ("Staff Software Engineer, Web3 (Remote)", "Staff Software Engineer, Web3"),
    ],
)
def test_suffix_and_specialization_cleaning_rules(raw, expected):
    assert clean_title(raw) == expected


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Intern Backend Developer", "Intern / Werkstudent / Praktikum"),
        ("Werkstudent Softwareentwicklung", "Intern / Werkstudent / Praktikum"),
        ("Junior Data Engineer", "Junior"),
        ("Mid-Level Software Engineer", "Mid-Level"),
        ("Senior Cloud Engineer", "Senior"),
        ("Staff Software Engineer", "Staff"),
        ("Principal Engineer", "Principal"),
        ("Lead DevOps Engineer", "Lead"),
        ("Director of Engineering", "Head / Director"),
        ("Software Engineer II", "II"),
        ("Software Engineer III", "III"),
        ("Backend Developer", "Mid/Unspecified"),
    ],
)
def test_only_explicit_seniority_is_extracted(title, expected):
    assert extract_seniority(title) == expected


def test_clear_title_alias_wins_over_conflicting_description_skills():
    result = classify("Software Engineer", "Python, Java, Kubernetes, Terraform")
    assert result.sub_domain_id == "S03"
    assert result.category_id == "C1"
    assert result.is_tech_role is True


def test_alias_tie_uses_skills_fallback_and_needs_three_to_two_ratio(tmp_path):
    vocab = tmp_path / "skills.csv"
    with vocab.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["slug", "label", "n_roadmaps", "roadmaps", "subdomain_ids", "n_subdomains"])
        writer.writeheader()
        for name, domain in [("alpha", "S22"), ("beta", "S22"), ("gamma", "S22"), ("delta", "S23"), ("epsilon", "S23")]:
            writer.writerow({"slug": name, "label": name, "n_roadmaps": 1, "roadmaps": "test", "subdomain_ids": domain, "n_subdomains": 1})
    result = classify("Technical Analyst", "alpha beta gamma delta", vocabulary_path=vocab)
    assert result.sub_domain_id == "S22"
    assert result.confidence_flag == "MEDIUM"
    ambiguous = classify("Technical Analyst", "alpha beta gamma delta epsilon", vocabulary_path=vocab)
    assert ambiguous.category_id == "U"
    assert ambiguous.reason_code == "conflicting_skills"


def test_generic_title_and_nontech_fallbacks():
    assert classify("Software Engineer").sub_domain_id == "S03"
    nontech = classify("Marketing Manager")
    assert nontech.category_id == "N" and nontech.is_tech_role is False
    unresolved = classify("Engineer")
    assert unresolved.category_id == "U" and unresolved.reason_code == "ambiguous_title"


def test_extension_toggle_uses_unclassified_fallback():
    result = classify("AR Developer", include_extensions=False)
    assert result.category_id == "U"
    assert result.reason_code == "extension_disabled"
    assert result.is_tech_role is False


def test_taxonomy_adjacency_still_counts_as_tech():
    result = classify("Product Manager")
    assert result.category_id == "C5"
    assert result.is_tech_role is True


def test_llm_result_is_validated_against_taxonomy_and_confidence():
    invalid = classify("Technical Analyst", llm_fallback=lambda *_: {"sub_domain_id": "S999", "role_confidence": 0.99})
    assert invalid.category_id == "U"
    valid = classify("Technical Analyst", llm_fallback=lambda *_: {"sub_domain_id": "S22", "role_confidence": 0.8})
    assert valid.sub_domain_id == "S22" and valid.confidence_flag == "MEDIUM"
    low = classify("Technical Analyst", llm_fallback=lambda *_: {"sub_domain_id": "S22", "role_confidence": 0.69})
    assert low.category_id == "U"


def test_special_character_skills_use_clean_boundaries():
    labels = ["C++", "C#", ".NET", "Node.js", "CI/CD", "HTML5/CSS3"]
    terms = [SkillTerm(x.lower(), x, frozenset(), ()) for x in labels]
    found = {term.label for term in extract_skills("C++ C# .NET Node.js CI/CD HTML5/CSS3", terms)}
    assert found == set(labels)
    assert not extract_skills("AC++ish CSharpish NETNode.jsx", terms)


def test_encoding_fixture_has_at_least_50_cases_and_all_clean():
    fixtures = json.loads((ROOT / "data/reference/title_encoding_fixtures_v2.json").read_text(encoding="utf-8"))
    assert len(fixtures) >= 50
    for fixture in fixtures:
        assert clean_title(fixture["raw_title"]) == fixture["clean_title"]


def test_golden_titles_from_legacy_are_distinct_and_match_their_labels():
    path = ROOT / "data/reference/golden_titles_legacy_v2.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) >= 300
    assert len({row["raw_title"] for row in rows}) == len(rows)
    assert all("\ufffd" not in row["raw_title"] for row in rows)
    for row in rows:
        result = classify(row["raw_title"])
        assert result.category_id == row["expected_category_id"]
        assert result.sub_domain_id == row["expected_sub_domain_id"]
        assert result.clean_title == row["expected_clean_title"]
