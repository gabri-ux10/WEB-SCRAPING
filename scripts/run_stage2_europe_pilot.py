"""Run the approved Europe pilot from Arbeitnow, Teamtailor RSS, and Greenhouse."""

from __future__ import annotations

import asyncio
import csv
import hashlib
import html
import json
import logging
import os
import random
import re
import time
import uuid
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse
from dataclasses import replace

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.v2.classification import Classification, classify, extract_skills
from app.v2.database import (
    ClassificationReview, Company, Posting, PostingSkill,
    QuarantinedRecord, RawPayload, ScrapeRun, Source, TranslationCache,
)
from app.v2.encoding import decode_response
from app.v2.geography import m49_region_for_country
from app.v2.language import detect_language
from app.v2.normalization import cross_language_dedup_key, normalize_company_name, normalize_role
from app.v2.taxonomy import REFERENCE_DIR, load_taxonomy, load_skills
from app.v2.translation import translate_title

LOG = logging.getLogger("stage2")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "exports"
TARGETS = {
    "150": ("Europe", "150", None),
    "002": ("Africa", "002", None),
    "USA": ("USA", "019", "US"),
    "142": ("Asia", "142", None),
}
TARGET_KEY = os.getenv("STAGE2_TARGET_REGION", "150").upper()
if TARGET_KEY not in TARGETS:
    raise RuntimeError("STAGE2_TARGET_REGION must be 150, 002, USA, or 142")
TARGET_LABEL, TARGET_REGION_M49, TARGET_COUNTRY_CODE = TARGETS[TARGET_KEY]
REPORT = ROOT / "docs" / f"STAGE_3_{TARGET_LABEL.upper()}_PILOT_REPORT.md"
UA_BASE = "csjobs-research/2.0 (+mailto:"
SOURCE_CAP = 500
TOTAL_UNIQUE_CAP = 1000
RATE_SECONDS = 1.0
MAX_RETRIES = 3
TIMEOUT = httpx.Timeout(10.0)
_UNAVAILABLE_TRANSLATION_LANGUAGES: set[str] = set()
LANG_HINT = {"DE": "de", "AT": "de", "CH": "de", "FR": "fr", "ES": "es", "PT": "pt", "IT": "it", "NL": "nl", "BE": "nl", "IE": "en", "GB": "en", "SE": "en", "NO": "en", "DK": "en", "FI": "en", "PL": "en"}
SOURCE_TERMS = {
    row["source_id"]: row
    for row in csv.DictReader((REFERENCE_DIR / "source_terms_decisions_v2.csv").open(encoding="utf-8-sig", newline=""))
}
M49_ROWS = list(csv.DictReader((REFERENCE_DIR / "un_m49_countries.csv").open(encoding="utf-8-sig", newline="")))
COUNTRY_BY_NAME = {normalize_role(row["country_or_area"]): row["iso_alpha2"] for row in M49_ROWS if row["iso_alpha2"]}
COUNTRY_BY_ALPHA3 = {row["iso_alpha3"].upper(): row["iso_alpha2"] for row in M49_ROWS if row["iso_alpha2"]}
COUNTRY_BY_ALPHA2 = {row["iso_alpha2"].upper(): row["iso_alpha2"] for row in M49_ROWS if row["iso_alpha2"]}
COUNTRY_ALIASES = {"uk": "GB", "britain": "GB", "england": "GB", "scotland": "GB", "wales": "GB", "usa": "US", "united states": "US", "u.s.a.": "US", "u.s.": "US", "czech republic": "CZ", "ivory coast": "CI", "uae": "AE"}
for alias, code in COUNTRY_ALIASES.items():
    COUNTRY_BY_NAME[normalize_role(alias)] = code


class HostLimiter:
    def __init__(self) -> None:
        self.locks: dict[str, asyncio.Lock] = {}
        self.last_request: dict[str, float] = {}

    async def wait(self, url: str) -> None:
        host = (urlparse(url).hostname or "").lower()
        lock = self.locks.setdefault(host, asyncio.Lock())
        async with lock:
            delay = RATE_SECONDS - (time.monotonic() - self.last_request.get(host, 0))
            if delay > 0:
                await asyncio.sleep(delay)
            self.last_request[host] = time.monotonic()


class PilotHTTP:
    def __init__(self, user_agent: str) -> None:
        self.client = httpx.AsyncClient(timeout=TIMEOUT, headers={"User-Agent": user_agent, "Accept": "application/json, application/rss+xml, application/xml;q=0.9, */*;q=0.8"}, follow_redirects=True)
        self.limiter = HostLimiter()
        self.requests = Counter()
        self.failures: list[str] = []

    async def get(self, url: str, params: dict | None = None) -> httpx.Response | None:
        request_url = str(httpx.URL(url, params=params)) if params else url
        host = (urlparse(request_url).hostname or "unknown").lower()
        for attempt in range(1, MAX_RETRIES + 1):
            await self.limiter.wait(request_url)
            self.requests[host] += 1
            try:
                response = await self.client.get(request_url)
                if response.status_code == 404:
                    return response
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt == MAX_RETRIES:
                        self.failures.append(f"{request_url}: HTTP {response.status_code} after {attempt} attempts")
                        return None
                    retry_after = response.headers.get("Retry-After")
                    backoff = float(retry_after) if retry_after and retry_after.isdigit() else (2 ** (attempt - 1) + random.random())
                    await asyncio.sleep(min(60.0, backoff))
                    continue
                response.raise_for_status()
                return response
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                if attempt == MAX_RETRIES:
                    self.failures.append(f"{request_url}: {type(exc).__name__} after {attempt} attempts")
                    return None
                await asyncio.sleep(min(20.0, 2 ** (attempt - 1) + random.random()))
        return None

    async def close(self) -> None:
        await self.client.aclose()


def _source_gate(source_id: str) -> None:
    row = SOURCE_TERMS.get(source_id)
    if not row or row["verification_status"] != "VERIFIED" or row["terms_decision"] != "public_feed_policy":
        raise RuntimeError(f"{source_id} is not verified/allowed by source_terms_decisions_v2.csv")


def _country(value) -> str | None:
    if isinstance(value, dict):
        value = value.get("code") or value.get("countryCode") or value.get("name") or value.get("country")
    if value is None:
        return None
    text_value = str(value).strip()
    upper = text_value.upper()
    if upper in COUNTRY_BY_ALPHA2:
        return COUNTRY_BY_ALPHA2[upper]
    if upper in COUNTRY_BY_ALPHA3:
        return COUNTRY_BY_ALPHA3[upper]
    normalized = normalize_role(text_value)
    if normalized in COUNTRY_BY_NAME:
        return COUNTRY_BY_NAME[normalized]
    # Match a full country name at a location boundary; do not infer from city names.
    for name, code in sorted(COUNTRY_BY_NAME.items(), key=lambda item: len(item[0]), reverse=True):
        if name and re.search(rf"(?<![a-z0-9]){re.escape(name)}(?![a-z0-9])", normalized):
            return code
    return None


def _location(raw, explicit_country=None) -> tuple[str, str | None]:
    city = ""
    if isinstance(raw, list) and raw:
        first = raw[0]
        if isinstance(first, dict):
            city = str(first.get("city") or first.get("name") or "")
            explicit_country = explicit_country or first.get("country_code") or first.get("countryCode") or first.get("country")
        else:
            city = str(first)
    elif isinstance(raw, dict):
        city = str(raw.get("city") or raw.get("name") or "")
        explicit_country = explicit_country or raw.get("country_code") or raw.get("countryCode") or raw.get("country")
    else:
        city = str(raw or "")
    country = _country(explicit_country) or _country(city)
    if "," in city:
        city = city.split(",", 1)[0].strip()
    return city.strip(), country


def _date(value) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) or str(value).isdigit():
        number = float(value)
        if number > 10_000_000_000:
            number /= 1000
        return datetime.fromtimestamp(number, UTC)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    except ValueError:
        try:
            parsed = parsedate_to_datetime(str(value))
            return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
        except (TypeError, ValueError):
            return None


def _work_modes(value) -> tuple[bool | None, bool | None]:
    if value is None:
        return None, None
    if isinstance(value, bool):
        return value, False
    mode = normalize_role(str(value))
    if mode in {"", "none", "onsite", "on site", "false", "no"}:
        return False, False
    if "hybrid" in mode:
        return False, True
    if mode in {"remote", "fully", "fully remote", "temporary", "temporarily remote", "yes", "true"}:
        return True, False
    return None, None


_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d ()./-]{7,}\d)(?!\w)")
_SENSITIVE_KEYS = re.compile(r"(?:e.?mail|phone|contact|recruiter|hiring.?manager|applicant)", re.I)


def _has_personal_contact(text: str) -> bool:
    return bool(_EMAIL.search(text) or _PHONE.search(text) or re.search(r"(?i)(?:contact|reach out to|questions to)\s*[:\-]?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}", text))


def _sanitize_text(text: str) -> str:
    text = _EMAIL.sub("[contact removed]", text)
    text = _PHONE.sub("[phone removed]", text)
    return re.sub(r"(?i)(?:contact|reach out to|questions to)\s*[:\-]?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}", "[contact removed]", text)


def _sanitize_object(value):
    if isinstance(value, dict):
        return {key: _sanitize_object(item) for key, item in value.items() if not _SENSITIVE_KEYS.search(str(key))}
    if isinstance(value, list):
        return [_sanitize_object(item) for item in value]
    if isinstance(value, str):
        return _sanitize_text(value)
    return value


def _json_array_record_bytes(raw_bytes: bytes, key: str) -> list[bytes]:
    """Extract original UTF-8 bytes for individual JSON array objects, not the full feed."""
    text_value = raw_bytes.decode("utf-8-sig", errors="strict")
    match = re.search(rf'"{re.escape(key)}"\s*:\s*\[', text_value)
    if not match:
        return []
    decoder = json.JSONDecoder()
    cursor = match.end()
    result = []
    while cursor < len(text_value):
        while cursor < len(text_value) and text_value[cursor] in " \r\n\t,":
            cursor += 1
        if cursor >= len(text_value) or text_value[cursor] == "]":
            break
        _value, end = decoder.raw_decode(text_value, cursor)
        result.append(text_value[cursor:end].encode("utf-8"))
        cursor = end
    return result


def _xml_item_bytes(raw_bytes: bytes) -> list[bytes]:
    return [match.group(0) for match in re.finditer(rb"<item\b[^>]*>.*?</item\s*>", raw_bytes, re.I | re.S)]


def _description(value) -> tuple[str, str]:
    raw = str(value or "")
    plain = html.unescape(BeautifulSoup(raw, "html.parser").get_text(" ", strip=True))
    plain = re.sub(r"\s+", " ", plain).strip()
    # Exclude direct recruiter contact details from stored text.
    return _sanitize_text(raw), _sanitize_text(plain)


def _repair_json_strings(value):
    """Repair text leaves after JSON parsing without modifying JSON syntax."""
    try:
        from ftfy import fix_text
    except ImportError:
        fix_text = lambda text: text
    if isinstance(value, str):
        return fix_text(value)
    if isinstance(value, list):
        return [_repair_json_strings(item) for item in value]
    if isinstance(value, dict):
        return {key: _repair_json_strings(item) for key, item in value.items()}
    return value


def _record(source_id: str, source_job_id, company: str, title: str, location, country, url: str, description, posted, raw: dict, page: bytes, charset: str, content_type: str, remote=None) -> dict:
    city, country_code = _location(location, country)
    is_remote, is_hybrid = _work_modes(remote)
    return {
        "source_id": source_id, "source_job_id": str(source_job_id or url), "company_name": company or "",
        "raw_title": str(title or ""), "location_raw": str(location or ""), "city": city,
        "country_code": country_code, "source_url": str(url or ""), "description_values": _description(description),
        "posted_at": _date(posted), "raw": _sanitize_object(raw), "source_record_bytes": page,
        "raw_record_persistable": not _has_personal_contact(page.decode(charset, errors="replace")),
        "source_charset": charset, "content_type": content_type, "is_remote": is_remote, "is_hybrid": is_hybrid,
    }


async def collect_arbeitnow(http: PilotHTTP) -> tuple[list[dict], list[dict]]:
    _source_gate("arbeitnow")
    records, raw_pages = [], []
    url = "https://www.arbeitnow.com/api/job-board-api"
    page = 1
    while len(records) < SOURCE_CAP:
        response = await http.get(url, params={"page": page})
        if response is None or response.status_code == 404:
            break
        decoded = decode_response(response.content, response.headers.get("content-type"))
        payload = _repair_json_strings(json.loads(decoded.text))
        data = payload.get("data", []) if isinstance(payload, dict) else []
        if not data:
            break
        raw_pages.append({"page": page, "bytes": decoded.raw_bytes, "charset": decoded.source_charset, "content_type": response.headers.get("content-type", "application/json"), "persistable": not _has_personal_contact(decoded.text)})
        raw_records = _json_array_record_bytes(decoded.raw_bytes, "data")
        for job_index, job in enumerate(data):
            location = job.get("location") or job.get("locations") or ""
            country = job.get("country_code") or job.get("country") or job.get("location_country")
            record_bytes = raw_records[job_index] if job_index < len(raw_records) else json.dumps(job, ensure_ascii=False).encode("utf-8")
            row = _record("arbeitnow", job.get("slug") or job.get("id"), job.get("company_name"), job.get("title"), location, country, job.get("url"), job.get("description"), job.get("created_at"), job, record_bytes, decoded.source_charset, response.headers.get("content-type", "application/json"), job.get("remote"))
            if _target_candidate(row):
                records.append(row)
                if len(records) >= SOURCE_CAP:
                    break
        LOG.info("[+] Arbeitnow page %d: %d %s records (%d/%d source cap)", page, len(records), TARGET_LABEL, len(records), SOURCE_CAP)
        next_url = None
        if isinstance(payload, dict):
            next_url = (payload.get("links") or {}).get("next") or (payload.get("meta") or {}).get("next_page_url")
        if next_url:
            url, page = next_url, page + 1
        else:
            page += 1
    return records, raw_pages


async def collect_teamtailor(http: PilotHTTP, feed_url: str, company_name: str) -> tuple[list[dict], list[dict]]:
    _source_gate("teamtailor")
    records, raw_pages, seen = [], [], set()
    base = feed_url
    offset = 0
    while len(records) < SOURCE_CAP:
        response = await http.get(base, params={"per_page": 100, "offset": offset})
        if response is None or response.status_code == 404 or not response.content:
            break
        decoded = decode_response(response.content, response.headers.get("content-type"), media_type="application/rss+xml")
        root = ET.fromstring(decoded.text)
        items = root.findall(".//item")
        if not items:
            break
        raw_pages.append({"page": offset, "bytes": decoded.raw_bytes, "charset": decoded.source_charset, "content_type": response.headers.get("content-type", "application/rss+xml"), "persistable": not _has_personal_contact(decoded.text)})
        new_count = 0
        item_bytes = _xml_item_bytes(decoded.raw_bytes)
        for item_index, item in enumerate(items):
            link = (item.findtext("link") or "").strip()
            guid = (item.findtext("guid") or link).strip()
            if not guid or guid in seen:
                continue
            seen.add(guid)
            ns = {"tt": "http://www.teamtailor.com"}
            country = item.findtext("tt:locations/tt:location/tt:country", namespaces=ns)
            location = item.findtext("tt:locations/tt:location/tt:name", namespaces=ns) or item.findtext("tt:locations/tt:location/tt:city", namespaces=ns) or ""
            description = item.findtext("description") or ""
            record_bytes = item_bytes[item_index] if item_index < len(item_bytes) else ET.tostring(item, encoding="utf-8")
            charset = decoded.source_charset if item_index < len(item_bytes) else "utf-8"
            row = _record("teamtailor", guid, company_name, item.findtext("title") or "", location, country, link, description, item.findtext("pubDate"), {"guid": guid, "title": item.findtext("title"), "link": link, "pubDate": item.findtext("pubDate"), "description": description, "location": location, "country": country}, record_bytes, charset, response.headers.get("content-type", "application/rss+xml"), item.findtext("remoteStatus"))
            if _target_candidate(row):
                records.append(row)
                new_count += 1
                if len(records) >= SOURCE_CAP:
                    break
        LOG.info("[+] Teamtailor offset %d: %d %s records (%d/%d source cap)", offset, len(records), TARGET_LABEL, len(records), SOURCE_CAP)
        if len(items) < 100 or new_count == 0:
            break
        offset += 100
    return records, raw_pages


async def collect_greenhouse(http: PilotHTTP, board_rows: list[tuple[str, str, int | None]]) -> tuple[list[dict], list[dict]]:
    _source_gate("greenhouse")
    records, raw_pages = [], []
    for index, (board, company, company_id) in enumerate(board_rows, 1):
        if len(records) >= SOURCE_CAP:
            break
        url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
        response = await http.get(url, params={"content": "true"})
        if response is None or response.status_code == 404:
            LOG.info("[+] Greenhouse board %s: unavailable", board)
            continue
        decoded = decode_response(response.content, response.headers.get("content-type"))
        try:
            payload = _repair_json_strings(json.loads(decoded.text))
        except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
            http.failures.append(f"Greenhouse board {board}: invalid JSON response ({type(exc).__name__})")
            LOG.warning("[+] Greenhouse board %s: skipped invalid JSON response (%s)", board, type(exc).__name__)
            continue
        if not isinstance(payload, dict) or not isinstance(payload.get("jobs", []), list):
            http.failures.append(f"Greenhouse board {board}: unexpected JSON shape")
            LOG.warning("[+] Greenhouse board %s: skipped unexpected JSON shape", board)
            continue
        jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
        raw_pages.append({"page": board, "bytes": decoded.raw_bytes, "charset": decoded.source_charset, "content_type": response.headers.get("content-type", "application/json"), "persistable": not _has_personal_contact(decoded.text)})
        raw_records = _json_array_record_bytes(decoded.raw_bytes, "jobs")
        for job_index, job in enumerate(jobs):
            location = (job.get("location") or {}).get("name") or ""
            record_bytes = raw_records[job_index] if job_index < len(raw_records) else json.dumps(job, ensure_ascii=False).encode("utf-8")
            row = _record("greenhouse", f"{board}:{job.get('id')}", company, job.get("title"), location, job.get("country_code"), job.get("absolute_url"), job.get("content"), None, job, record_bytes, decoded.source_charset, response.headers.get("content-type", "application/json"), job.get("remote"))
            if _target_candidate(row):
                records.append(row)
                if len(records) >= SOURCE_CAP:
                    break
        LOG.info("[+] Greenhouse board %s (%d/%d): %d %s records (%d/%d source cap)", board, index, len(board_rows), len(records), TARGET_LABEL, len(records), SOURCE_CAP)
    return records, raw_pages


def _local_translation_callback(cache: dict[tuple[str, str], str], pending: list[dict], language_hint: str | None = None):
    def translate(title: str) -> str | None:
        language, _ = detect_language(title, language_hint)
        language = language or language_hint or "und"
        if language == "en":
            return title
        key = (hashlib.sha256(title.encode("utf-8")).hexdigest(), language)
        if key in cache:
            return cache[key]
        if language in _UNAVAILABLE_TRANSLATION_LANGUAGES:
            return None
        try:
            result = translate_title(title, language)
        except (OSError, RuntimeError, ValueError) as exc:
            _UNAVAILABLE_TRANSLATION_LANGUAGES.add(language)
            LOG.warning("Local OPUS-MT unavailable for %s title (model %s): %s", language, language, type(exc).__name__)
            return None
        if result:
            cache[key] = result
            pending.append({"hash": key[0], "source_title": title, "language": language, "translation": result})
        return result
    return translate


def _target_candidate(row: dict) -> bool:
    country = row.get("country_code")
    if not country:
        return False
    if TARGET_COUNTRY_CODE:
        return country.upper() == TARGET_COUNTRY_CODE
    return m49_region_for_country(country) == TARGET_REGION_M49


async def persist_and_export(collected: dict[str, list[dict]], raw_pages: dict[str, list[dict]], boards: list[tuple[str, str, int | None]], http: PilotHTTP) -> dict:
    arbeitnow_enabled = os.getenv("STAGE2_ARBEITNOW_ENABLED", "1") == "1"
    active_sources = (["arbeitnow"] if arbeitnow_enabled else []) + ["greenhouse"] + (["teamtailor"] if collected.get("teamtailor") or os.getenv("STAGE2_TEAMTAILOR_VERIFIED") == "1" else [])
    for source_id in active_sources:
        _source_gate(source_id)
    database_url = make_url(settings.database_url).set(database="techjobs_v2").render_as_string(hide_password=False)
    engine = create_async_engine(database_url, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync: __import__("app.v2.database", fromlist=["V2Base"]).V2Base.metadata.create_all(sync))
    Session = async_sessionmaker(engine, expire_on_commit=False)
    skills_ref = load_skills()
    skills_by_slug = {term.slug for term in skills_ref}
    translations: dict[tuple[str, str], str] = {}
    translations_pending: list[dict] = []
    counters = Counter()
    languages = Counter()
    titles_nontech = Counter()
    titles_unclassified = Counter()
    german = Counter()
    quarantine_rows = []
    prepared = []

    async with Session() as session:
        cache_rows = (await session.execute(select(TranslationCache))).scalars().all()
        for item in cache_rows:
            translations[(item.title_hash, item.target_language)] = item.translated_title
        board_map = {identifier: (name, company_id) for identifier, name, company_id in boards}
        for source_id, jobs in collected.items():
            for row in jobs:
                if "\ufffd" in row["raw_title"]:
                    quarantine_rows.append(row)
                    counters[f"{source_id}_quarantined"] += 1
                    continue
                if not _target_candidate(row):
                    counters[f"{source_id}_missing_or_non_europe_location"] += 1
                    continue
                raw_desc, description = row["description_values"]
                country = row["country_code"]
                locale = LANG_HINT.get(country)
                skill_terms = extract_skills(description, skills_ref)
                labels = [term.label for term in skill_terms]
                translator_base = _local_translation_callback(translations, translations_pending, locale)
                translator = lambda title: translator_base(title)
                result: Classification = classify(
                    row["raw_title"], description, labels, source_language=locale,
                    include_extensions=True, translator=translator, llm_fallback=None,
                )
                title_language = result.title_language
                languages[title_language] += 1
                if title_language == "de":
                    german["count"] += 1
                    german["title_replacement"] += int("\ufffd" in row["raw_title"])
                    german["description_replacement"] += int("\ufffd" in description)
                    german["mojibake_pattern"] += int(bool(re.search(r"(?:Ã.|Â.|â€|\ufffd)", description)))
                if title_language != "en":
                    translated = translator(result.clean_title)
                    if translated:
                        result = replace(result, clean_title_en=translated, translation_method="opus_mt_local")
                    else:
                        result = replace(result, clean_title_en=None, translation_method="pending")
                if result.category_id == "N":
                    titles_nontech[row["raw_title"]] += 1
                if result.category_id == "U":
                    titles_unclassified[row["raw_title"]] += 1
                role_key = result.normalized_role if result.sub_domain_id else normalize_role(result.clean_title_en or result.clean_title)
                key = cross_language_dedup_key(row["company_name"], role_key, row["city"])
                canonical_id = str(uuid.uuid5(uuid.NAMESPACE_URL, key))
                company_id = board_map.get(row["source_job_id"].split(":", 1)[0], ("", None))[1] if source_id == "greenhouse" else None
                prepared.append({**row, "classification": result, "skills": skill_terms, "description": description, "description_raw": raw_desc, "canonical_key": key, "canonical_id": canonical_id, "company_id": company_id})

    # Unique canonical-key cap spans sources; duplicate source observations remain attributable.
    selected, canonical_keys = [], set()
    for source_id in ("arbeitnow", "teamtailor", "greenhouse"):
        source_count = 0
        for row in (item for item in prepared if item["source_id"] == source_id):
            is_new = row["canonical_key"] not in canonical_keys
            if is_new and len(canonical_keys) >= TOTAL_UNIQUE_CAP:
                continue
            canonical_keys.add(row["canonical_key"])
            if source_count < SOURCE_CAP:
                selected.append(row)
                source_count += 1

    async with Session() as session, session.begin():
        run_id = str(uuid.uuid4())
        stage_name = "stage2_europe_pilot" if TARGET_KEY == "150" else "stage3_global_pilot"
        run = ScrapeRun(id=run_id, stage=stage_name, region_m49=TARGET_REGION_M49, status="running", sources_seen=len(active_sources), postings_seen=len(selected), postings_new=0, errors=list(http.failures))
        session.add(run)
        sources = (await session.execute(select(Source).where(Source.id.in_(active_sources)))).scalars().all()
        for source in sources:
            source.enabled = True
        existing_ids = set()
        for item in selected:
            existing = (await session.execute(select(Posting.id).where(Posting.source_id == item["source_id"], Posting.source_job_id == item["source_job_id"]))).scalar_one_or_none()
            if existing:
                existing_ids.add((item["source_id"], item["source_job_id"]))
                continue
            company_id = item["company_id"]
            if company_id is None and item["company_name"]:
                company = (await session.execute(select(Company).where(Company.normalized_key == normalize_company_name(item["company_name"])))).scalar_one_or_none()
                if company is None:
                    company = Company(display_name=item["company_name"], normalized_key=normalize_company_name(item["company_name"]))
                    session.add(company)
                    await session.flush()
                company_id = company.id
            result = item["classification"]
            posting = Posting(
                canonical_id=item["canonical_id"], source_id=item["source_id"], source_job_id=item["source_job_id"], company_id=company_id,
                raw_title=item["raw_title"], clean_title=result.clean_title, clean_title_en=result.clean_title_en,
                title_language=result.title_language, description=item["description"], description_language=result.description_language,
                language_confidence=result.language_confidence, translation_method=result.translation_method,
                description_raw=item["description_raw"], source_charset=item["source_charset"], source_url=item["source_url"],
                posted_at=item["posted_at"], country_code=item["country_code"], region_m49=m49_region_for_country(item["country_code"]),
                city=item["city"], location_raw=item["location_raw"], is_remote=item["is_remote"], is_hybrid=item["is_hybrid"], normalized_role=result.normalized_role,
                seniority=result.seniority, domain_specialization=result.domain_specialization, category_id=result.category_id,
                sub_domain_id=result.sub_domain_id, is_tech_role=result.is_tech_role, tier=result.tier,
                role_confidence=result.role_confidence, confidence_flag=result.confidence_flag, reason_code=result.reason_code,
                raw_payload=item["raw"], scrape_run_id=run_id, classifier_version=result.classifier_version, taxonomy_version=result.taxonomy_version,
            )
            session.add(posting)
            await session.flush()
            for term in item["skills"]:
                if term.slug in skills_by_slug:
                    session.add(PostingSkill(posting_id=posting.id, skill_slug=term.slug, origin="vocabulary"))
            if result.category_id in {"N", "U"}:
                session.add(ClassificationReview(posting_id=posting.id, reason_code=result.reason_code or "manual_review_required"))
            counters[f"{item['source_id']}_stored"] += 1
            if item["raw_record_persistable"]:
                raw_bytes, raw_charset, raw_type = item["source_record_bytes"], item["source_charset"], item["content_type"]
            else:
                raw_bytes = json.dumps(item["raw"], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                raw_charset, raw_type = "utf-8", "application/vnd.cs-jobs.sanitized-source-record+json"
                counters["raw_payloads_redacted_for_contact"] += 1
            session.add(RawPayload(source_id=item["source_id"], source_job_id=item["source_job_id"], raw_bytes=raw_bytes, source_charset=raw_charset, content_type=raw_type, sha256=hashlib.sha256(raw_bytes).hexdigest()))
        run.status = "completed_with_errors" if http.failures else "completed"
        run.finished_at = datetime.now(UTC)
        run.postings_new = sum(counters[key] for key in ("arbeitnow_stored", "teamtailor_stored", "greenhouse_stored"))
        for row in quarantine_rows:
            if row["raw_record_persistable"]:
                safe_bytes, charset, content_type = row["source_record_bytes"], row["source_charset"], row["content_type"]
            else:
                safe_bytes = json.dumps(row["raw"], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                charset, content_type = "utf-8", "application/vnd.cs-jobs.sanitized-source-record+json"
            session.add(QuarantinedRecord(source_id=row["source_id"], source_job_id=row["source_job_id"], raw_bytes=safe_bytes, source_charset=charset, content_type=content_type, source_url=row["source_url"], reason="U+FFFD in raw title"))
        for item in translations_pending:
            exists = (await session.execute(select(TranslationCache.id).where(TranslationCache.title_hash == item["hash"], TranslationCache.target_language == item["language"]))).scalar_one_or_none()
            if exists is None:
                session.add(TranslationCache(title_hash=item["hash"], source_title=item["source_title"], target_language=item["language"], translated_title=item["translation"], translation_method="opus_mt_local", model=f"Helsinki-NLP/opus-mt-{item['language']}-en"))

    await engine.dispose()
    OUT.mkdir(parents=True, exist_ok=True)
    export_rows = []
    for item in selected:
        result = item["classification"]
        export_rows.append({
            "company_name": item["company_name"], "posted_at": item["posted_at"].isoformat() if item["posted_at"] else "",
            "job_title": item["raw_title"], "clean_title_en": result.clean_title_en, "title_language": result.title_language,
            "location": item["location_raw"], "country_code": item["country_code"], "region_m49": m49_region_for_country(item["country_code"]),
            "category_id": result.category_id, "category": result.category, "sub_domain_id": result.sub_domain_id or "",
            "sub_domain": result.sub_domain, "normalized_role": result.normalized_role, "is_tech_role": result.is_tech_role,
            "skills": [term.label for term in item["skills"]], "description": item["description"], "source_id": item["source_id"],
            "url": item["source_url"], "classification_confidence": result.confidence_flag, "reason_code": result.reason_code or "",
        })
    output_stem = f"stage2_europe_pilot" if TARGET_KEY == "150" else f"stage3_{TARGET_LABEL.lower()}_pilot"
    export_csv = OUT / f"{output_stem}.csv"
    export_json = OUT / f"{output_stem}.json"
    translation_review = OUT / f"{output_stem}_title_translation_review.csv"
    if export_rows:
        with export_csv.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(export_rows[0]))
            writer.writeheader()
            for row in export_rows:
                writer.writerow({key: "; ".join(value) if isinstance(value, list) else value for key, value in row.items()})
        export_json.write_text(json.dumps(export_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    translated_rows = [
        {"source_id": item["source_id"], "raw_title": item["raw_title"], "title_language": item["classification"].title_language,
         "opus_mt_title_en": item["classification"].clean_title_en, "manual_title_en": "", "reviewer_note": ""}
        for item in selected if item["classification"].translation_method == "opus_mt_local"
    ]
    with translation_review.open("w", encoding="utf-8-sig", newline="") as stream:
        fields = list(translated_rows[0]) if translated_rows else ["source_id", "raw_title", "title_language", "opus_mt_title_en", "manual_title_en", "reviewer_note"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(translated_rows)

    source_counts = Counter(item["source_id"] for item in selected)
    overlap = set(item["canonical_key"] for item in selected if item["source_id"] == "arbeitnow") & set(item["canonical_key"] for item in selected if item["source_id"] in {"greenhouse", "teamtailor"})
    by_lang = Counter(item["classification"].title_language for item in selected)
    nontech = Counter(item["raw_title"] for item in selected if item["classification"].category_id == "N")
    unclassified = Counter(item["raw_title"] for item in selected if item["classification"].category_id == "U")
    german_rows = [item for item in selected if item["classification"].title_language == "de"]
    teamtailor_status = os.getenv("STAGE2_TEAMTAILOR_STATUS", "teamtailor: no verified feed found in the Arbeitnow sample")
    arbeitnow_status = "arbeitnow: included" if os.getenv("STAGE2_ARBEITNOW_ENABLED", "1") == "1" else "arbeitnow: skipped after preflight failure; Greenhouse-only fallback used"
    source_description = (
        "Arbeitnow public API and Greenhouse public Job Board API"
        if os.getenv("STAGE2_ARBEITNOW_ENABLED", "1") == "1"
        else "Greenhouse public Job Board API only; Arbeitnow was unreachable at preflight"
    )
    report = [
        f"# Stage {'2 Europe' if TARGET_KEY == '150' else '3 ' + TARGET_LABEL} Pilot Report", "", f"Run date: {datetime.now(UTC).date().isoformat()}",
        f"Sources: {source_description}; Teamtailor public RSS was optional and discovered from the Arbeitnow sample.",
        f"Scope: {TARGET_LABEL} only (UN M49 region {TARGET_REGION_M49}" + (", country US only" if TARGET_COUNTRY_CODE else "") + "), maximum 500 source records per feed and 1,000 unique canonical postings overall. Requests used a 10-second timeout and per-host rate limiting of no more than one request per second.",
        "Classification: rules-only; no LLM fallback. Extensions enabled; C5 remains adjacent. M49 groupings are used as published.",
        "Translation: local Helsinki-NLP OPUS-MT models where cached; original titles remain preserved.", "",
        "## Collection", "", arbeitnow_status, teamtailor_status, f"- Source records selected: **{len(selected)}**", f"- Canonical English-key unique postings: **{len(canonical_keys):,}**", f"- Arbeitnow: **{source_counts['arbeitnow']}**", f"- Teamtailor RSS: **{source_counts['teamtailor']}**", f"- Greenhouse: **{source_counts['greenhouse']}**", f"- Arbeitnow keys also present in ATS feeds: **{len(overlap)}**", f"- U+FFFD title quarantine records: **{len(quarantine_rows)}**", f"- HTTP failed URLs after retries: **{len(http.failures)}**", "",
        "## Per-language title accuracy", "",
        "Accuracy against human labels is **pending**: the accompanying 100-title manual sheet has blank reviewer fields and the 300-row golden set is explicitly unverified. The rule-only baseline below is coverage by detected title language, not accuracy:", "",
    ]
    report.extend(f"- {lang}: {count} titles; accuracy pending hand labels" for lang, count in sorted(by_lang.items()))
    report += ["", "## German text cleanliness", "", f"- German-title postings: **{len(german_rows)}**", f"- German titles containing U+FFFD in stored rows: **{sum('�' in item['raw_title'] for item in german_rows)}**", f"- German descriptions containing U+FFFD: **{sum('�' in item['description'] for item in german_rows)}**", f"- German descriptions with common mojibake markers: **{sum(bool(re.search(r'(?:Ã.|Â.|â€|�)', item['description'])) for item in german_rows)}**", "", "## Top 50 Non-Tech titles", ""]
    report.extend(f"- {title} ({count})" for title, count in nontech.most_common(50))
    report += ["", "## Top 50 Unclassified titles", ""]
    report.extend(f"- {title} ({count})" for title, count in unclassified.most_common(50))
    report += ["", f"Exports: `{export_csv.relative_to(ROOT).as_posix()}` and `{export_json.relative_to(ROOT).as_posix()}`.", f"Local MT title translations available for hand spot-check: **{len(translated_rows)}** (`{translation_review.relative_to(ROOT).as_posix()}`). The 100-title classification sheet provides manual expected-label fields."]
    REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")
    LOG.info("[+] Pilot exports written: %d selected source records; %d unique keys", len(selected), len(canonical_keys))
    return {"selected": len(selected), "unique": len(canonical_keys), "source_counts": source_counts}


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    arbeitnow_enabled = os.getenv("STAGE2_ARBEITNOW_ENABLED", "1") == "1"
    for source_id in (("arbeitnow",) if arbeitnow_enabled else ()) + ("greenhouse",):
        _source_gate(source_id)
    contact = os.getenv("CSJOBS_CONTACT_EMAIL")
    if not contact:
        raise RuntimeError("Set CSJOBS_CONTACT_EMAIL to the dedicated project contact before job-feed requests")
    teamtailor_enabled = os.getenv("STAGE2_TEAMTAILOR_VERIFIED") == "1"
    teamtailor_url = os.getenv("CSJOBS_TEAMTAILOR_FEED_URL", "") if teamtailor_enabled else ""
    teamtailor_company = os.getenv("CSJOBS_TEAMTAILOR_COMPANY_NAME", "").strip() if teamtailor_enabled else ""
    teamtailor_host = (urlparse(teamtailor_url).hostname or "").lower()
    if teamtailor_enabled and (
        not teamtailor_host.endswith(".teamtailor.com")
        or urlparse(teamtailor_url).scheme != "https"
        or not urlparse(teamtailor_url).path.endswith("/jobs.rss")
        or "<" in teamtailor_url
        or not teamtailor_company
        or "<" in teamtailor_company
    ):
        raise RuntimeError("Configure a verified company-specific Teamtailor RSS URL and matching company name before the pilot")
    http = PilotHTTP(f"{UA_BASE}{contact})")
    try:
        if arbeitnow_enabled:
            arbeitnow, raw_a = await collect_arbeitnow(http)
        else:
            arbeitnow, raw_a = [], []
        if teamtailor_enabled:
            _source_gate("teamtailor")
            teamtailor, raw_t = await collect_teamtailor(http, teamtailor_url, teamtailor_company)
        else:
            teamtailor, raw_t = [], []
        database_url = make_url(settings.database_url).set(database="techjobs_v2").render_as_string(hide_password=False)
        engine = create_async_engine(database_url, pool_pre_ping=True)
        async with engine.connect() as conn:
            boards = (await conn.execute(text("""
                SELECT b.identifier, c.display_name, c.id FROM csjobs.ats_boards b
                LEFT JOIN csjobs.companies c ON c.id=b.company_id
                WHERE b.source_id='greenhouse' ORDER BY b.identifier
            """))).all()
        await engine.dispose()
        greenhouse, raw_g = await collect_greenhouse(http, [(r.identifier, r.display_name or r.identifier, r.id) for r in boards])
        LOG.info("[+] Fetched pages: Arbeitnow=%d Teamtailor=%d Greenhouse=%d", len(raw_a), len(raw_t), len(raw_g))
        result = await persist_and_export({"arbeitnow": arbeitnow, "teamtailor": teamtailor, "greenhouse": greenhouse}, {"arbeitnow": raw_a, "teamtailor": raw_t, "greenhouse": raw_g}, [(r.identifier, r.display_name or r.identifier, r.id) for r in boards], http)
        for failure in http.failures:
            LOG.error("[!] retry exhausted: %s", failure)
        print("[STAGE2_SUMMARY] " + json.dumps({"region": TARGET_LABEL, "region_m49": TARGET_REGION_M49, "country_filter": TARGET_COUNTRY_CODE, "result": result, "teamtailor": os.getenv("STAGE2_TEAMTAILOR_STATUS", "teamtailor: no verified feed found in the Arbeitnow sample"), "requests_by_host": http.requests, "failures": http.failures}, default=dict, ensure_ascii=False))
    finally:
        await http.close()


if __name__ == "__main__":
    asyncio.run(main())
