from pathlib import Path

import yaml

SKILLS = [
    "Python",
    "Java",
    "JavaScript",
    "TypeScript",
    "C++",
    "C#",
    "Go",
    "Rust",
    "PHP",
    "Ruby",
    "Kotlin",
    "Swift",
    "React",
    "Angular",
    "Vue",
    "Next.js",
    "Node.js",
    "Django",
    "Flask",
    "FastAPI",
    "Spring",
    "PostgreSQL",
    "MySQL",
    "MongoDB",
    "Redis",
    "AWS",
    "Azure",
    "GCP",
    "Docker",
    "Kubernetes",
    "Terraform",
    "Git",
    "GitHub",
    "GitLab",
    "TensorFlow",
    "PyTorch",
    "scikit-learn",
    "Solidity",
    "Ethereum",
    "Web3",
    "Linux",
    "Networking",
    "Cybersecurity",
    "SIEM",
    "SOC",
]


def extract_skills(text: str | None) -> list[str]:
    path = Path(__file__).resolve().parents[2] / "config" / "skills.yml"
    skills = (
        yaml.safe_load(path.read_text(encoding="utf-8")).get("skills", SKILLS)
        if path.exists()
        else SKILLS
    )
    hay = " " + (text or "").lower() + " "
    return [
        s
        for s in skills
        if (" " + s.lower() + " ") in hay
        or (s.lower() in {"c++", "c#", ".net"} and s.lower() in hay)
    ]
