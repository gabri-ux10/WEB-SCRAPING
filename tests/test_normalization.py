from app.classification.classifier import classify
from app.classification.skills import extract_skills
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
