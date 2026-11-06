"""Normalize job description text and extract configured technology skills."""

from __future__ import annotations

import html
import re
from collections import deque
from functools import lru_cache
from pathlib import Path

import yaml

SKILLS = [
    "Python", "Java", "JavaScript", "TypeScript", "C", "C++", "C#", "Go", "Rust",
    "PHP", "Ruby", "Kotlin", "Swift", "Scala", "R", "Dart", "MATLAB", "Elixir",
    "Erlang", "Clojure", "Haskell", "Perl", "Lua", "Objective-C", "Bash",
    "PowerShell", "Groovy", "F#", "Fortran", "SQL", "HTML", "CSS", "XML", "JSON",
    "YAML", "React", "Angular", "Vue", "Svelte", "Next.js", "Nuxt", "Node.js",
    "Express.js", "NestJS", "Django", "Flask", "FastAPI", "Spring Boot", ".NET",
    "ASP.NET", "Laravel", "Ruby on Rails", "GraphQL", "REST APIs", "gRPC",
    "WebSockets", "Microservices", "Serverless", "Distributed Systems",
    "Event-Driven Architecture", "PostgreSQL", "MySQL", "MariaDB", "SQLite",
    "SQL Server", "Oracle Database", "MongoDB", "DynamoDB", "Cassandra", "Redis",
    "Elasticsearch", "OpenSearch", "Neo4j", "Snowflake", "BigQuery", "Redshift",
    "Databricks", "ClickHouse", "Supabase", "Firebase", "Firestore", "Cosmos DB",
    "InfluxDB", "AWS", "Azure", "GCP", "Oracle Cloud", "Cloudflare", "DigitalOcean",
    "Vercel", "Netlify", "Heroku", "Docker", "Kubernetes", "Helm", "Terraform",
    "Pulumi", "Ansible", "Jenkins", "GitHub Actions", "GitLab CI/CD", "CircleCI",
    "Argo CD", "OpenShift", "Istio", "Linux", "Git", "GitHub", "GitLab", "CI/CD",
    "DevOps", "SRE", "Platform Engineering", "Infrastructure as Code", "Prometheus",
    "Grafana", "Datadog", "New Relic", "Splunk", "OpenTelemetry", "ELK Stack",
    "Apache Kafka", "RabbitMQ", "TensorFlow", "PyTorch", "Keras", "scikit-learn",
    "Hugging Face", "LangChain", "LlamaIndex", "OpenAI", "Large Language Models",
    "Generative AI", "Machine Learning", "Artificial Intelligence", "NLP",
    "Computer Vision", "MLOps", "Pandas", "NumPy", "Apache Spark", "Airflow", "dbt",
    "Jest", "Vitest", "Mocha", "Cypress", "Playwright", "Selenium", "Pytest", "JUnit",
    "NUnit", "TestNG", "RSpec", "Postman", "k6", "Unit Testing", "Integration Testing",
    "End-to-End Testing", "Test Automation", "TDD", "QA", "Agile", "Scrum", "Kanban",
    "SAFe", "Cybersecurity", "OWASP", "OAuth", "SAML", "JWT", "IAM", "SIEM", "SOC",
    "Zero Trust", "Application Security", "Figma", "Adobe Photoshop", "Adobe Illustrator",
    "Sketch", "Jira", "Confluence", "Salesforce", "ServiceNow", "SAP", "IoT",
    "Embedded Systems", "Firmware", "Robotics", "ROS", "CAD", "SolidWorks", "AutoCAD",
    "3D Printing", "PLC",
]

_TOKEN_RE = re.compile(r"[^\W_]+|[+#]+|[./_-]", re.UNICODE)

# Domain labels deliberately live outside the technology taxonomy. They are
# suitable as fallback signals when a posting describes a technical role but
# names no concrete technology.
DOMAIN_PATTERNS: dict[str, tuple[str, ...]] = {
    "Backend": (
        r"\bback[ -]?end\b", r"\bserver[ -]?side\b", r"\bbackend engineer\b",
        r"\bapi (?:engineer|development|design)\b", r"\bbuild(?:ing)? (?:web )?services\b",
        r"\bservice reliability\b", r"\bdistributed services\b",
    ),
    "Frontend": (
        r"\bfront[ -]?end\b", r"\bclient[ -]?side\b", r"\bweb interface\b",
        r"\buser interface development\b", r"\bui engineer\b",
    ),
    "Full-Stack": (r"\bfull[ -]?stack\b", r"\bfullstack\b"),
    "Mobile": (
        r"\bmobile (?:app|application|development|engineer|developer)\b",
        r"\bios (?:app|application|development|engineer|developer)\b",
        r"\bandroid (?:app|application|development|engineer|developer)\b",
        r"\bmobile platform\b",
    ),
    "DevOps/Cloud": (
        r"\bdevops\b", r"\bsite reliability\b", r"\bcloud (?:engineer|infrastructure|platform|operations)\b",
        r"\binfrastructure (?:engineer|operations|as code)\b", r"\bplatform engineer(?:ing)?\b",
        r"\bdeployment pipelines?\b", r"\bci\s*/\s*cd\b", r"\bproduction operations\b",
    ),
    "Data Engineering": (
        r"\bdata engineer(?:ing)?\b", r"\bdata pipelines?\b", r"\betl\b",
        r"\bdata warehouse\b", r"\bdata platform\b", r"\bstream processing\b",
    ),
    "Data Science": (
        r"\bdata scientist\b", r"\bdata science\b", r"\bmachine learning\b",
        r"\bstatistical (?:modeling|analysis)\b", r"\bpredictive model(?:ing)?\b",
    ),
    "System Administration": (
        r"\bsystem administrator\b", r"\bsystems administrator\b", r"\bsysadmin\b",
        r"\blinux administrator\b", r"\bnetwork administrator\b", r"\bit infrastructure support\b",
    ),
    "QA/Testing": (
        r"\bquality assurance\b", r"\bqa engineer\b", r"\btest engineer\b",
        r"\bsoftware testing\b", r"\btest automation\b", r"\bautomated testing\b",
    ),
    "Cybersecurity": (
        r"\bcyber ?security\b", r"\binformation security\b", r"\bapplication security\b",
        r"\bsecurity engineer\b", r"\bsecurity operations\b", r"\bthreat (?:detection|intelligence|hunting)\b",
        r"\bsecurity analyst\b",
    ),
}

DOMAIN_PHRASES: dict[str, tuple[str, ...]] = {
    "Backend": ("backend", "back end", "back-end", "server side", "server-side", "backend engineer", "api development", "service reliability", "distributed services"),
    "Frontend": ("frontend", "front end", "front-end", "client side", "client-side", "web interface", "user interface development", "ui engineer"),
    "Full-Stack": ("full stack", "full-stack", "fullstack"),
    "Mobile": ("mobile app", "mobile application", "mobile development", "mobile engineer", "ios development", "android development"),
    "DevOps/Cloud": ("devops", "site reliability", "cloud engineer", "cloud infrastructure", "cloud platform", "infrastructure engineer", "platform engineering", "deployment pipeline", "ci/cd", "production operations"),
    "Data Engineering": ("data engineering", "data engineer", "data pipeline", "etl", "data warehouse", "data platform", "stream processing"),
    "Data Science": ("data scientist", "data science", "machine learning", "statistical modeling", "statistical analysis", "predictive modeling"),
    "System Administration": ("system administrator", "systems administrator", "sysadmin", "linux administrator", "network administrator", "it infrastructure support"),
    "QA/Testing": ("quality assurance", "qa engineer", "test engineer", "software testing", "test automation", "automated testing"),
    "Cybersecurity": ("cybersecurity", "cyber security", "information security", "application security", "security engineer", "security operations", "threat detection", "threat intelligence", "threat hunting", "security analyst"),
}

_DOMAIN_REGEXES = {name: tuple(re.compile(pattern, re.I) for pattern in patterns)
                   for name, patterns in DOMAIN_PATTERNS.items()}

_NON_TECH_TITLE_RE = re.compile(
    r"\b(?:marketing|sales|finance|financial|accounting|accountant|human resources|hr|"
    r"recruit(?:er|ing|ment)|health ?care|healthcare|physician|doctor|nurse|clinical|"
    r"medical|patient|warehouse|logistics|customer success|customer support|customer service|"
    r"legal|attorney|administrative|office manager|operations?)\b",
    re.I,
)


def is_tech_role(title: str | None, skills: list[str] | None) -> bool:
    """True only for roles with a specific extracted tech skill and tech title."""
    has_specific_skill = any(
        skill and not skill.startswith("Domain: ") for skill in (skills or [])
    )
    return bool(has_specific_skill and not _NON_TECH_TITLE_RE.search(title or ""))

# Conservative phrase-level inference handles common responsibility language
# where a concept is described as an action rather than listed as a skill.
_CONTEXT_SKILL_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("REST APIs", re.compile(r"\b(?:design|build|develop|implement|maintain)(?:ing)?\s+(?:scalable\s+|secure\s+)?(?:rest(?:ful)?\s+)?apis?\b", re.I)),
    ("CI/CD", re.compile(r"\b(?:build|manage|maintain|automate|improve)(?:ing)?\s+(?:the\s+)?ci\s*/\s*cd\s+(?:pipeline|workflow)s?\b", re.I)),
    ("Microservices", re.compile(r"\b(?:design|build|deploy|operate|maintain)(?:ing)?\s+(?:distributed\s+)?microservices\b", re.I)),
    ("Unit Testing", re.compile(r"\b(?:write|writing|create|creating|maintain|maintaining|execute|executing)\s+unit tests?\b", re.I)),
    ("Test Automation", re.compile(r"\b(?:automate|automating|automation of)\s+(?:software\s+)?tests?\b", re.I)),
)


@lru_cache(maxsize=1)
def _spacy_language():
    """Load the installed English pipeline, falling back to spaCy's blank tokenizer."""
    try:
        import spacy
    except ImportError:
        return None
    try:
        return spacy.load(
            "en_core_web_sm", disable=["ner", "parser", "tagger", "lemmatizer"]
        )
    except OSError:
        return spacy.blank("en")


@lru_cache(maxsize=1)
def _spacy_domain_matcher():
    """Return an optional spaCy PhraseMatcher for domain phrase recognition.

    No statistical model download is needed. When spaCy is not installed, the
    equivalent conservative regex rules remain available.
    """
    nlp = _spacy_language()
    if nlp is None:
        return None
    from spacy.matcher import PhraseMatcher

    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    for domain, phrases in DOMAIN_PHRASES.items():
        docs = [nlp.make_doc(phrase) for phrase in phrases]
        if docs:
            matcher.add(domain, docs)
    return nlp, matcher


@lru_cache(maxsize=1)
def _spacy_skill_matcher():
    """Build an optional spaCy PhraseMatcher over configured skill aliases."""
    nlp = _spacy_language()
    if nlp is None:
        return None
    from spacy.matcher import PhraseMatcher

    nodes, validators, _ = _compiled_skill_pattern()
    del nodes
    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    aliases_by_skill: dict[str, set[str]] = {}
    ambiguous_short = {"c", "r", "go", "ai", "ki", "ia", "ml", "solid"}
    for _, canonical, alias in validators:
        if alias.casefold() not in ambiguous_short:
            aliases_by_skill.setdefault(canonical, set()).add(alias)
    for canonical, aliases in aliases_by_skill.items():
        matcher.add(canonical, [nlp.make_doc(alias) for alias in aliases])
    return nlp, matcher


def infer_domains(title: str | None, description: str | None) -> list[str]:
    """Infer high-level technical domains from a title and job description."""
    text = _plain_text(f"{title or ''} {description or ''}")
    if not text:
        return []
    found: set[str] = set()
    spacy_matcher = _spacy_domain_matcher()
    if spacy_matcher:
        nlp, matcher = spacy_matcher
        doc = nlp.make_doc(text)
        found.update(nlp.vocab.strings[match_id] for match_id, _, _ in matcher(doc))
    else:
        for domain, patterns in _DOMAIN_REGEXES.items():
            if any(pattern.search(text) for pattern in patterns):
                found.add(domain)
    return [domain for domain in DOMAIN_PATTERNS if domain in found]


def infer_contextual_skills(text: str | None) -> list[str]:
    """Infer a small set of canonical skills from explicit action phrases."""
    visible = _plain_text(text)
    found = [skill for skill, pattern in _CONTEXT_SKILL_RULES if pattern.search(visible)]
    return found


def _plain_text(text: str | None) -> str:
    if not text:
        return ""
    decoded = str(text)
    # Some ATS feeds double-escape HTML (for example, &amp;lt;p&amp;gt;).
    for _ in range(3):
        next_text = html.unescape(decoded)
        if next_text == decoded:
            break
        decoded = next_text
    # ATS descriptions are frequently escaped HTML. Strip markup after
    # unescaping so text in qualifications and responsibilities remains.
    decoded = re.sub(r"(?is)<(script|style)\b[^>]*>.*?</\1>", " ", decoded)
    visible = re.sub(r"(?s)<[^>]*>", " ", decoded)
    return re.sub(r"\s+", " ", html.unescape(visible)).strip()


@lru_cache(maxsize=1)
def _compiled_skill_pattern():
    """Build a literal trie and regex validators for its boundary matches."""
    path = Path(__file__).resolve().parents[2] / "config" / "skills.yml"
    configured = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    configured = (configured or {}).get("skills", SKILLS)

    groups: dict[str, list[str]] = {}
    if isinstance(configured, dict):
        for canonical, aliases in configured.items():
            alternatives = [canonical]
            if isinstance(aliases, str):
                alternatives.append(aliases)
            elif isinstance(aliases, list):
                alternatives.extend(alias for alias in aliases if isinstance(alias, str))
            groups[str(canonical)] = list(dict.fromkeys(a.strip() for a in alternatives if a.strip()))
    else:
        groups = {str(name): [str(name)] for name in configured}

    # A token trie scans each description once instead of running hundreds of
    # regex searches. Regexes validate exact spelling and boundaries only for
    # literal alias candidates found by the trie.
    nodes = [{"next": {}, "fail": 0, "outputs": []}]
    validators = {}
    canonical_order = list(groups)
    for canonical, aliases in groups.items():
        for alias in sorted(set(aliases), key=len, reverse=True):
            if not alias:
                continue
            if canonical.casefold() == "lean" and alias.casefold() == "lean":
                continue  # Avoid tagging the common adjective "lean".
            alias_tokens = [token.group() for token in _TOKEN_RE.finditer(alias)]
            if not alias_tokens:
                continue
            node = 0
            for token in alias_tokens:
                key = token.casefold()
                child = nodes[node]["next"].get(key)
                if child is None:
                    child = len(nodes)
                    nodes[node]["next"][key] = child
                    nodes.append({"next": {}, "fail": 0, "outputs": []})
                node = child
            nodes[node]["outputs"].append((canonical, alias, len(alias_tokens)))

            # Allow flexible whitespace inside multi-word names while keeping
            # punctuation significant (Node.js, CI/CD, C++, C#, and .NET).
            body = re.escape(alias_tokens[0])
            for previous, token in zip(alias_tokens, alias_tokens[1:]):
                separator = r"\s+" if previous[-1].isalnum() and token[0].isalnum() else r"\s*"
                body += separator + re.escape(token)
            # These short labels are common words in prose when lower-case;
            # retain them only when the posting uses the canonical acronym.
            short_acronym = alias.casefold() in {"c", "r", "go", "safe", "ai", "ki", "ia", "ml", "solid"}
            if short_acronym:
                body = f"(?-i:{body})"
            left = r"(?<![\w])" if alias[0].isalnum() else ""
            if alias.casefold() == "c":
                right = r"(?![\w+#])"
            elif alias.casefold() == "r":
                # Avoid treating the common business abbreviation R&D as R.
                right = r"(?![\w&/])"
            else:
                right = r"(?![\w])"
            flags = 0 if short_acronym else re.IGNORECASE
            validators[(tuple(t.casefold() for t in alias_tokens), canonical, alias)] = re.compile(
                f"{left}{body}{right}", flags
            )

    # Failure links retain overlapping matches while keeping the scan linear
    # in the token count plus the number of literal candidates.
    queue = deque(nodes[0]["next"].values())
    while queue:
        parent = queue.popleft()
        for token, child in nodes[parent]["next"].items():
            queue.append(child)
            fallback = nodes[parent]["fail"]
            while fallback and token not in nodes[fallback]["next"]:
                fallback = nodes[fallback]["fail"]
            nodes[child]["fail"] = nodes[fallback]["next"].get(token, 0)
            nodes[child]["outputs"].extend(nodes[nodes[child]["fail"]]["outputs"])

    return nodes, validators, canonical_order


def extract_skills(text: str | None) -> list[str]:
    """Return canonical skills found in a title or description.

    Text is unescaped and stripped of HTML first, so ATS feeds that store
    escaped markup remain searchable. Aliases are boundary-aware and allow
    punctuation such as slashes, dots, plus signs, and hyphens.
    """
    if not text:
        return []
    visible = _plain_text(text)
    nodes, validators, canonical_order = _compiled_skill_pattern()
    found = set()
    state = 0
    tokens = list(_TOKEN_RE.finditer(visible))
    for index, token_match in enumerate(tokens):
        token = token_match.group().casefold()
        while state and token not in nodes[state]["next"]:
            state = nodes[state]["fail"]
        state = nodes[state]["next"].get(token, 0)
        for canonical, alias, token_count in nodes[state]["outputs"]:
            start = tokens[index - token_count + 1].start()
            end = token_match.end()
            alias_tokens = tuple(t.group().casefold() for t in _TOKEN_RE.finditer(alias))
            validator = validators[(alias_tokens, canonical, alias)]
            match = validator.match(visible, start)
            if match and match.end() == end:
                found.add(canonical)
    # When the optional spaCy extra is installed, use its NLP tokenizer and
    # PhraseMatcher as a second pass over the same curated skill aliases.
    spacy_matcher = _spacy_skill_matcher() if not found else None
    if spacy_matcher:
        nlp, matcher = spacy_matcher
        doc = nlp.make_doc(visible)
        found.update(nlp.vocab.strings[match_id] for match_id, _, _ in matcher(doc))
    # Keep taxonomy order stable for JSON and CSV exports.
    return [name for name in canonical_order if name in found]
