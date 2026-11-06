from app.classification.classifier import classify
from app.classification.skills import (
    extract_skills,
    infer_contextual_skills,
    infer_domains,
    is_tech_role,
)
from app.normalization.locations import normalize_location
from app.normalization.salaries import parse_salary


def test_known_city_location_and_remote():
    data = normalize_location("Nairobi, Kenya")
    assert data["city"] == "Nairobi" and data["country_code"] == "KE"
    assert normalize_location("Remote - Kenya")["remote_type"] == "remote"


def test_salary_does_not_convert_currency():
    assert parse_salary("KES 100,000 - 150,000/month") == {
        "salary_min": 100000,
        "salary_max": 150000,
        "salary_currency": "KES",
        "salary_period": "month",
        "salary_raw": "KES 100,000 - 150,000/month",
    }
    assert parse_salary("USD 81K – 87K annual")["salary_min"] == 81000


def test_classification_examples():
    assert classify("Senior Backend Engineer")[0] == "Software Engineering"
    assert "Backend Engineering" in classify("Senior Backend Engineer")[1]
    assert classify("Data Scientist")[0] == "Data Science"
    assert classify("Cloud Security Engineer") == ("Cybersecurity", ["Cloud Security"])
    assert classify("DevOps Engineer")[0] == "DevOps"


def test_skill_extraction_requires_text_match():
    assert extract_skills("Build services with Python and PostgreSQL") == ["Python", "PostgreSQL"]
    assert extract_skills("No technologies mentioned") == []


def test_domain_fallback_uses_role_and_responsibility_context():
    assert "Backend" in infer_domains("Backend Engineer", "Build reliable services")
    assert "DevOps/Cloud" in infer_domains("Platform Engineer", "Own deployment pipelines and production operations")
    assert infer_domains("Finance Manager", "Prepare monthly reconciliations") == []


def test_contextual_skill_extraction_maps_explicit_action_phrases():
    assert infer_contextual_skills("Building REST APIs and writing unit tests") == ["REST APIs", "Unit Testing"]


def test_tech_role_flag_excludes_nontechnical_titles_and_domain_only_fallbacks():
    assert is_tech_role("Backend Engineer", ["Python"])
    assert not is_tech_role("Finance Systems Analyst", ["Python"])
    assert not is_tech_role("Backend Engineer", ["Domain: Backend"])
    assert not is_tech_role("Backend Engineer", [])
