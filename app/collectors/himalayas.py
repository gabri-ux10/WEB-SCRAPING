from datetime import UTC, datetime

from app.collectors.base import BaseCollector
from app.schemas.job import NormalizedJob


class HimalayasCollector(BaseCollector):
    """Public cursor-paginated feed for global remote jobs."""

    source = "himalayas"

    async def fetch(self, config):
        jobs = []
        cursor = None
        seen_cursors = set()
        limit = max(1, min(int(config.get("page_size", 20)), 20))
        seen_ids = set()
        while True:
            params = {"limit": limit}
            if cursor:
                params["cursor"] = cursor
            data = await self.request_json_or_none("https://himalayas.app/jobs/api", params=params)
            if data is None:
                break
            rows = data.get("jobs", [])
            if not rows:
                self.exhausted = True
                break
            before = len(seen_ids)
            for job in rows:
                identity = str(job.get("guid") or job.get("applicationLink") or "")
                if identity and identity not in seen_ids:
                    seen_ids.add(identity)
                    jobs.append(job)
            if len(seen_ids) == before:
                self.exhausted = True
                break
            next_cursor = data.get("nextCursor")
            if not next_cursor or next_cursor in seen_cursors:
                self.exhausted = True
                break
            seen_cursors.add(next_cursor)
            cursor = next_cursor

        return jobs

    def normalize(self, raw, config):
        raw_locations = raw.get("locationRestrictions") or []
        locations = [
            item.get("name") if isinstance(item, dict) else str(item)
            for item in raw_locations
        ]
        posted_at = raw.get("pubDate")
        if isinstance(posted_at, (int, float)):
            posted_at = datetime.fromtimestamp(posted_at / 1000, UTC)
        seniority = raw.get("seniority") or []
        seniority = ", ".join(seniority) if isinstance(seniority, list) else str(seniority)

        url = raw.get("applicationLink")
        categories = raw.get("categories") or []
        return NormalizedJob(
            source=self.source,
            source_job_id=str(raw.get("guid") or url or ""),
            company_name=raw.get("companyName") or "Unknown",
            title=raw.get("title") or "",
            description=raw.get("description") or raw.get("excerpt"),
            description_html=raw.get("description"),
            location=", ".join(filter(None, locations)) or "Worldwide",
            remote_type="remote",
            employment_type=raw.get("employmentType"),
            seniority=seniority or None,
            salary_min=raw.get("minSalary"),
            salary_max=raw.get("maxSalary"),
            salary_currency=raw.get("currency"),
            salary_period=raw.get("salaryPeriod"),
            posted_at=posted_at,
            apply_url=url,
            source_url=url,
            skills=categories,
            source_metadata={
                key: raw[key]
                for key in ("companySlug", "categories", "parentCategories", "timezoneRestrictions")
                if raw.get(key) is not None
            },
        )
