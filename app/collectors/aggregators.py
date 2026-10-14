import os

from app.collectors.base import BaseCollector
from app.config import settings
from app.schemas.job import NormalizedJob


class AdzunaCollector(BaseCollector):
    source = "adzuna"

    async def fetch(self, config):
        if not settings.adzuna_app_id or not settings.adzuna_app_key:
            return []
        out = []
        for country in config.get("countries", []):
            for query in config.get("keywords", []):
                page = 1
                seen = set()
                while True:
                    data = await self.request_json_or_none(
                        f"https://api.adzuna.com/v1/api/jobs/{country.lower()}/search/{page}",
                        params={
                            "app_id": settings.adzuna_app_id,
                            "app_key": settings.adzuna_app_key,
                            "results_per_page": int(config.get("results_per_page", 20)),
                            "what": query,
                            "content-type": "application/json",
                        },
                    )
                    if data is None:
                        break
                    rows = data.get("results", [])
                    if not rows:
                        self.exhausted = True
                        break
                    before = len(seen)
                    for row in rows:
                        identity = str(row.get("id") or row.get("redirect_url") or "")
                        if identity and identity not in seen:
                            seen.add(identity)
                            out.append({**row, "_country": country})
                    if len(seen) == before:
                        self.exhausted = True
                        break
                    page += 1
        return out

    def normalize(self, raw, config):
        company = (raw.get("company") or {}).get("display_name") or "Unknown"
        loc = (raw.get("location") or {}).get("display_name")
        return NormalizedJob(
            source=self.source,
            source_job_id=str(raw.get("id") or ""),
            company_name=company,
            title=raw.get("title") or "",
            description=raw.get("description"),
            location=loc,
            country_code=raw.get("_country"),
            salary_min=raw.get("salary_min"),
            salary_max=raw.get("salary_max"),
            salary_currency=config.get("currency"),
            employment_type=raw.get("contract_type"),
            posted_at=raw.get("created"),
            apply_url=raw.get("redirect_url"),
            source_url=raw.get("redirect_url"),
        )


class USAJobsCollector(BaseCollector):
    source = "usajobs"

    async def fetch(self, config):
        if not settings.usajobs_api_key or not settings.usajobs_email:
            return []
        out = []
        for keyword in config.get("keywords", ["Information Technology"]):
            page = 1
            while True:
                data = await self.request_json_or_none(
                    "https://data.usajobs.gov/api/Search",
                    params={
                        "Keyword": keyword,
                        "ResultsPerPage": config.get("results_per_page", 25),
                        "Page": page,
                    },
                    headers={
                        "Authorization-Key": settings.usajobs_api_key,
                        "User-Agent": settings.usajobs_email,
                    },
                )
                if data is None:
                    break
                rows = data.get("SearchResult", {}).get("SearchResultItems", [])
                out += rows
                if not rows:
                    self.exhausted = True
                    break
                count = data.get("SearchResult", {}).get("SearchResultCountAll")
                pages = data.get("SearchResult", {}).get("UserArea", {}).get("NumberOfPages")
                if pages and page >= int(pages):
                    self.exhausted = True
                    break
                if count and page * int(config.get("results_per_page", 25)) >= min(int(count), 10000):
                    # USAJOBS documents a 10,000-result search ceiling.
                    self.exhausted = True
                    break
                page += 1
        return out

    def normalize(self, raw, config):
        item = raw.get("MatchedObjectDescriptor", {})
        locs = item.get("PositionLocation", [])
        loc = locs[0].get("LocationName") if locs else None
        return NormalizedJob(
            source=self.source,
            source_job_id=str(item.get("PositionID") or item.get("PositionURI") or ""),
            company_name=item.get("OrganizationName") or "U.S. Government",
            title=item.get("PositionTitle") or "",
            description=item.get("UserArea", {}).get("Details", {}).get("JobSummary"),
            location=loc,
            employment_type=", ".join(
                item.get("PositionSchedule", [])
                and [p.get("Name", "") for p in item.get("PositionSchedule", [])]
                or []
            )
            or None,
            posted_at=item.get("PublicationStartDate"),
            apply_url=item.get("ApplyURI", [None])[0],
            source_url=item.get("PositionURI"),
        )


class JoobleCollector(BaseCollector):
    source = "jooble"

    async def fetch(self, config):
        out = []
        markets = config.get("markets") or [
            {
                "location": country,
                "domain": config.get("api_domain", "jooble.org"),
                "key_env": "JOOBLE_API_KEY",
            }
            for country in config.get("countries", [])
        ]
        for market in markets:
            country = market.get("location")
            domain = market.get("domain", "jooble.org")
            api_key = os.getenv(market.get("key_env", "JOOBLE_API_KEY")) or settings.jooble_api_key
            if not country or not api_key:
                continue
            for keyword in config.get("keywords", []):
                page = 1
                seen = set()
                while True:
                    payload = await self.request_json_post_or_none(
                        f"https://{domain}/api/{api_key}",
                        json_body={"keywords": keyword, "location": country, "page": str(page)},
                    )
                    if payload is None:
                        break
                    rows = payload.get("jobs", [])
                    if not rows:
                        self.exhausted = True
                        break
                    before = len(seen)
                    for row in rows:
                        identity = str(row.get("id") or row.get("link") or "")
                        if identity and identity not in seen:
                            seen.add(identity)
                            out.append(row)
                    if len(seen) == before:
                        self.exhausted = True
                        break
                    total = payload.get("totalCount")
                    page_size = int(config.get("results_per_page", 20))
                    if total is not None and page * page_size >= int(total):
                        self.exhausted = True
                        break
                    page += 1
        return out

    def normalize(self, raw, config):
        return NormalizedJob(
            source=self.source,
            source_job_id=str(raw.get("id") or raw.get("link") or ""),
            company_name=raw.get("company") or "Unknown",
            title=raw.get("title") or "",
            description=raw.get("snippet"),
            location=raw.get("location"),
            salary_raw=raw.get("salary"),
            posted_at=raw.get("updated"),
            apply_url=raw.get("link"),
            source_url=raw.get("link"),
        )
