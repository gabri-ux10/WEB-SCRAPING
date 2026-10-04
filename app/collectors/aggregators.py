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
        max_pages = min(int(config.get("max_pages", 2)), 20)
        for country in config.get("countries", []):
            for query in config.get("keywords", []):
                for page in range(1, max_pages + 1):
                    data = await self.request_json(
                        f"https://api.adzuna.com/v1/api/jobs/{country.lower()}/search/{page}",
                        params={
                            "app_id": settings.adzuna_app_id,
                            "app_key": settings.adzuna_app_key,
                            "results_per_page": int(config.get("results_per_page", 20)),
                            "what": query,
                            "content-type": "application/json",
                        },
                    )
                    out += [{**j, "_country": country} for j in data.get("results", [])]
                    if not data.get("results"):
                        break
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
        max_pages = min(int(config.get("max_pages", 1)), 20)
        for keyword in config.get("keywords", ["Information Technology"]):
            for page in range(1, max_pages + 1):
                data = await self.request_json(
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
                rows = data.get("SearchResult", {}).get("SearchResultItems", [])
                out += rows
                if not rows:
                    break
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
        budget = max(0, min(int(config.get("max_requests_per_run", 5)), 5))
        requests = 0
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
                if requests >= budget:
                    break
                requests += 1
                payload = await self.request_json_post(
                    f"https://{domain}/api/{api_key}",
                    json_body={"keywords": keyword, "location": country, "page": "1"},
                )
                out += payload.get("jobs", [])
            if requests >= budget:
                break
        return out[: int(config.get("max_jobs", 100))]

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
