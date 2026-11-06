"""Gate the Stage 2 pilot and discover an optional Teamtailor feed from Arbeitnow."""

from __future__ import annotations

import asyncio
import csv
import json
import os
import re
import socket
import ssl
import time
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.v2.database import ATSBoard, Company
from app.v2.envfile import load_selected_env
from app.v2.normalization import normalize_company_name

ROOT = Path(__file__).resolve().parents[2]
TERMS = ROOT / "data/reference/source_terms_decisions_v2.csv"
REPORT = ROOT / "docs/STAGE_2_NETWORK_PREFLIGHT.md"
LEGACY_EXPORT = ROOT / "job_postings_full.json"
TIMEOUT = 10.0
PROBE_TIMEOUT = 5.0
ARBEITNOW_URL = "https://www.arbeitnow.com/api/job-board-api?page=1"
PROXY_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")
USER_AGENT_PREFIX = "csjobs-research/2.0 (+mailto:"
TEAMTAILOR_NO_MATCH = "teamtailor: no verified feed found in the Arbeitnow sample"


def greenhouse_board() -> str | None:
    if not LEGACY_EXPORT.exists():
        return None
    pattern = re.compile(rb"https?://(?:job-boards|boards)\.greenhouse\.io/([A-Za-z0-9_.-]+)/(?:jobs|job/)")
    with LEGACY_EXPORT.open("rb") as stream:
        carry = b""
        while block := stream.read(1024 * 1024):
            match = pattern.search(carry + block)
            if match:
                return match.group(1).decode("ascii")
            carry = (carry + block)[-512:]
    return None


def terms_allowed(source_id: str) -> bool:
    with TERMS.open(encoding="utf-8-sig", newline="") as stream:
        rows = {row["source_id"]: row for row in csv.DictReader(stream)}
    row = rows.get(source_id)
    return bool(row and row["verification_status"] == "VERIFIED" and row["terms_decision"] == "public_feed_policy")


def network_probe(host: str) -> dict[str, str]:
    result = {"dns": "NOT_RUN", "dns_addresses": "", "tcp": "NOT_RUN", "tls": "NOT_RUN"}
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        result["dns_addresses"] = ",".join(dict.fromkeys(item[4][0] for item in addresses))
        result["dns"] = "OK"
    except OSError as exc:
        result["dns"] = f"FAILED:{type(exc).__name__}"
        return result
    try:
        raw_socket = socket.create_connection((host, 443), timeout=PROBE_TIMEOUT)
    except OSError as exc:
        result["tcp"] = f"FAILED:{type(exc).__name__}"
        return result
    result["tcp"] = "OK"
    try:
        context = ssl.create_default_context()
        with context.wrap_socket(raw_socket, server_hostname=host):
            result["tls"] = "OK"
    except (ssl.SSLError, OSError) as exc:
        result["tls"] = f"FAILED:{type(exc).__name__}"
    finally:
        raw_socket.close()
    return result


def _candidate_feeds(jobs: list[dict]) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()
    for job in jobs:
        company = str(job.get("company_name") or "").strip()
        if not company:
            continue
        for field in ("url", "apply_url", "applyUrl", "application_url"):
            value = job.get(field)
            if not isinstance(value, str):
                continue
            parsed = urlparse(value.strip())
            host = (parsed.hostname or "").lower().rstrip(".")
            suffix = ".teamtailor.com"
            if parsed.scheme not in {"http", "https"} or not host.endswith(suffix):
                continue
            company_subdomain = host[: -len(suffix)]
            if not company_subdomain or "." in company_subdomain:
                continue
            feed_url = f"https://{company_subdomain}{suffix}/jobs.rss"
            if feed_url not in seen:
                seen.add(feed_url)
                candidates.append({"url": feed_url, "host": f"{company_subdomain}{suffix}", "company": company, "discovered_from": value.strip()})
                if len(candidates) == 5:
                    return candidates
    return candidates


def _rss_channel_title(content: bytes) -> str | None:
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return None
    if root.tag.rsplit("}", 1)[-1].lower() != "rss":
        return None
    channel = next((child for child in root if child.tag.rsplit("}", 1)[-1].lower() == "channel"), None)
    if channel is None:
        return None
    title = next((child for child in channel if child.tag.rsplit("}", 1)[-1].lower() == "title"), None)
    value = (title.text or "").strip() if title is not None else ""
    return value or None


def _merge_env_keys(path: Path, updates: dict[str, str]) -> None:
    """Replace only named keys and preserve all other .env contents and line endings."""
    raw = path.read_text(encoding="utf-8") if path.exists() else ""
    newline = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.splitlines()
    remaining = dict(updates)
    output: list[str] = []
    for line in lines:
        stripped = line.strip()
        candidate = stripped[7:].lstrip() if stripped.startswith("export ") else stripped
        key, separator, _ = candidate.partition("=")
        key = key.strip()
        if separator and key in remaining:
            output.append(f"{key}={remaining.pop(key)}")
        else:
            output.append(line)
    output.extend(f"{key}={value}" for key, value in remaining.items())
    path.write_text(newline.join(output) + (newline if raw.endswith(("\n", "\r")) or not raw else ""), encoding="utf-8")


async def _record_teamtailor_board(company_name: str, identifier: str, discovered_from: str) -> str:
    config = load_selected_env(ROOT / ".env", {"DATABASE_URL"})
    database_url = config.get("DATABASE_URL", "")
    if not database_url or "<" in database_url or ">" in database_url:
        return "database unavailable; ATS board record skipped"
    url = make_url(database_url).set(database="techjobs_v2")
    engine = create_async_engine(url, pool_pre_ping=True, connect_args={"timeout": 10})
    try:
        Session = async_sessionmaker(engine, expire_on_commit=False)
        async with Session() as session, session.begin():
            normalized = normalize_company_name(company_name)
            company = (await session.execute(select(Company).where(Company.normalized_key == normalized))).scalar_one_or_none()
            if company is None:
                company = Company(display_name=company_name, normalized_key=normalized)
                session.add(company)
                await session.flush()
            board = (await session.execute(select(ATSBoard).where(ATSBoard.source_id == "teamtailor", ATSBoard.identifier == identifier))).scalar_one_or_none()
            if board is None:
                board = ATSBoard(source_id="teamtailor", identifier=identifier)
                session.add(board)
            board.company_id = company.id
            board.discovered_from = discovered_from
            board.verified_name_match = True
            board.last_status = "200"
        return "recorded in ats_boards"
    except Exception as exc:  # optional lead recording must not block the required-source pilot
        return f"database record skipped ({type(exc).__name__})"
    finally:
        await engine.dispose()


def main() -> None:
    config = load_selected_env(ROOT / ".env", {"CSJOBS_CONTACT_EMAIL", "DATABASE_URL", *PROXY_KEYS})
    contact = config.get("CSJOBS_CONTACT_EMAIL")
    if not contact or "<<" in contact or "PASTE" in contact.upper() or "your-project-contact" in contact.lower() or "example.org" in contact.lower():
        raise SystemExit("Preflight configuration error: CSJOBS_CONTACT_EMAIL is missing or a placeholder.")
    user_agent = f"{USER_AGENT_PREFIX}{contact})"
    proxy_detected = [key for key in PROXY_KEYS if config.get(key) or os.environ.get(key)]
    rows: list[dict[str, str]] = []

    # Try Arbeitnow first. If it is unavailable, continue to the already-approved
    # Greenhouse source; Teamtailor discovery then remains unavailable as well.
    host = "www.arbeitnow.com"
    arbeitnow_jobs: list[dict] = []
    status: int | None = None
    outcome = ""
    if not terms_allowed("arbeitnow"):
        diag = {"dns": "NOT_RUN", "dns_addresses": "", "tcp": "NOT_RUN", "tls": "NOT_RUN"}
        outcome = "TERMS_BLOCKED_NO_REQUEST"
    else:
        diag = network_probe(host)
        if not any(diag[key] != "OK" for key in ("dns", "tcp", "tls")):
            try:
                response = httpx.get(ARBEITNOW_URL, timeout=TIMEOUT, headers={"User-Agent": user_agent}, follow_redirects=False)
                status = response.status_code
                if 200 <= status < 300:
                    payload = response.json()
                    arbeitnow_jobs = payload.get("data", []) if isinstance(payload, dict) else []
                    outcome = "HTTP_OK" if isinstance(arbeitnow_jobs, list) else "INVALID_API_RESPONSE"
                else:
                    outcome = "HTTP_STATUS_FAILURE"
            except (httpx.HTTPError, ValueError) as exc:
                outcome = f"HTTP_TRANSPORT_FAILURE:{type(exc).__name__}"
        else:
            outcome = "DIRECT_NETWORK_PROBE_FAILED"
    arbeitnow_ok = diag["dns"] == diag["tcp"] == diag["tls"] == "OK" and outcome == "HTTP_OK"
    rows.append({"source": "arbeitnow", "host": host, **diag, "http_status": str(status) if status is not None else "none", "classification": outcome})

    # Required gate 2: Greenhouse. Do not begin optional discovery if this gate fails.
    if not terms_allowed("greenhouse"):
        _write_report(rows, proxy_detected, TEAMTAILOR_NO_MATCH)
        raise SystemExit("Preflight failed at stage: greenhouse (terms blocked).")
    board = greenhouse_board()
    greenhouse_url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true" if board else "https://boards-api.greenhouse.io/"
    host = "boards-api.greenhouse.io"
    diag = network_probe(host)
    status = None
    outcome = ""
    if not any(diag[key] != "OK" for key in ("dns", "tcp", "tls")) and board:
        try:
            response = httpx.get(greenhouse_url, timeout=TIMEOUT, headers={"User-Agent": user_agent}, follow_redirects=False)
            status = response.status_code
            outcome = "HTTP_OK" if 200 <= status < 300 else "HTTP_STATUS_FAILURE"
        except httpx.HTTPError as exc:
            outcome = f"HTTP_TRANSPORT_FAILURE:{type(exc).__name__}"
    elif not board:
        outcome = "NO_GREENHOUSE_BOARD_IDENTIFIER"
    else:
        outcome = "DIRECT_NETWORK_PROBE_FAILED"
    greenhouse_ok = diag["dns"] == diag["tcp"] == diag["tls"] == "OK" and outcome == "HTTP_OK"
    rows.append({"source": "greenhouse", "host": host, **diag, "http_status": str(status) if status is not None else "none", "classification": outcome})
    if not greenhouse_ok:
        _write_report(rows, proxy_detected, f"arbeitnow: {'available' if arbeitnow_ok else 'unavailable; Greenhouse-only fallback not started'}\n{TEAMTAILOR_NO_MATCH}")
        for row in rows:
            print(f"{row['source']}: DNS={row['dns']}({row['dns_addresses'] or 'n/a'}) TCP={row['tcp']} TLS={row['tls']} HTTP={row['http_status']} result={row['classification']}")
        print(f"Preflight failed at stage: greenhouse. Report: {REPORT.relative_to(ROOT).as_posix()}")
        raise SystemExit(1)

    # Optional gate 3: derive at most five feeds only from URLs and company names in that response.
    candidates = _candidate_feeds(arbeitnow_jobs) if arbeitnow_ok else []
    accepted: dict[str, str] | None = None
    last_request_by_host: dict[str, float] = {}
    for candidate in candidates:
        elapsed = time.monotonic() - last_request_by_host.get(candidate["host"], 0.0)
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        last_request_by_host[candidate["host"]] = time.monotonic()
        diag = network_probe(candidate["host"])
        candidate_status: int | None = None
        classification = "DIRECT_NETWORK_PROBE_FAILED"
        feed_title = None
        if diag["dns"] == diag["tcp"] == diag["tls"] == "OK":
            try:
                feed_response = httpx.get(candidate["url"], timeout=TIMEOUT, headers={"User-Agent": user_agent}, follow_redirects=False)
                candidate_status = feed_response.status_code
                feed_title = _rss_channel_title(feed_response.content) if 200 <= candidate_status < 300 else None
                if feed_title:
                    classification = "VALID_RSS_NAME_MATCH" if normalize_company_name(feed_title) == normalize_company_name(candidate["company"]) else "VALID_RSS_NAME_MISMATCH"
                else:
                    classification = "INVALID_RSS_OR_HTTP_FAILURE"
            except httpx.HTTPError as exc:
                classification = f"HTTP_TRANSPORT_FAILURE:{type(exc).__name__}"
        rows.append({"source": "teamtailor", "host": candidate["host"], **diag, "http_status": str(candidate_status) if candidate_status is not None else "none", "classification": classification})
        if classification == "VALID_RSS_NAME_MATCH":
            accepted = {**candidate, "feed_title": feed_title or ""}
            break
        if feed_title:
            # The first structurally valid RSS feed ends discovery even when
            # its company name fails the required match.
            break

    if accepted:
        _merge_env_keys(ROOT / ".env", {
            "CSJOBS_TEAMTAILOR_FEED_URL": accepted["url"],
            "CSJOBS_TEAMTAILOR_COMPANY_NAME": accepted["company"],
        })
        db_status = asyncio.run(_record_teamtailor_board(accepted["company"], urlparse(accepted["url"]).hostname.split(".", 1)[0], accepted["discovered_from"]))
        teamtailor_status = f"teamtailor: verified {accepted['url']} (feed title matched Arbeitnow company; {db_status})"
    else:
        teamtailor_status = TEAMTAILOR_NO_MATCH

    arbeitnow_status = "arbeitnow: available" if arbeitnow_ok else "arbeitnow: unavailable; proceeding with Greenhouse only"
    _write_report(rows, proxy_detected, f"{arbeitnow_status}\n{teamtailor_status}")
    for row in rows:
        print(f"{row['source']}: DNS={row['dns']}({row['dns_addresses'] or 'n/a'}) TCP={row['tcp']} TLS={row['tls']} HTTP={row['http_status']} result={row['classification']}")
    print(f"[ARBEITNOW_GATE] {'PASS' if arbeitnow_ok else 'SKIP'}")
    print(arbeitnow_status)
    print(f"{teamtailor_status}")
    print(f"Preflight report: {REPORT.relative_to(ROOT).as_posix()}; proxy settings detected: {', '.join(proxy_detected) if proxy_detected else 'none'}")


def _write_report(rows: list[dict[str, str]], proxy_detected: list[str], teamtailor_status: str) -> None:
    report = [
        "# Stage 2 Network Preflight", "", f"Checked: {date.today().isoformat()}",
        "Preflight order: try Arbeitnow first, then require Greenhouse; if Arbeitnow is unavailable, continue with Greenhouse only. Teamtailor discovery is optional and runs only from a successful Arbeitnow sample. The report records proxy variable names only, never proxy values or the project contact. Each source host received at most one preflight HTTP GET with a 10-second timeout and redirects disabled. Teamtailor candidates were derived only from Arbeitnow job/apply URLs; each candidate was tried once with at least one second between requests to the same host.",
        "", "Proxy settings detected: " + (", ".join(proxy_detected) if proxy_detected else "none"), "",
        "| Source | Host | DNS | Resolved addresses | TCP | TLS | HTTP status | Classification |", "|---|---|---|---|---|---|---:|---|",
    ]
    report.extend(f"| {row['source']} | `{row['host']}` | {row['dns']} | `{row['dns_addresses'] or 'n/a'}` | {row['tcp']} | {row['tls']} | {row['http_status']} | {row['classification']} |" for row in rows)
    report += ["", teamtailor_status]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
