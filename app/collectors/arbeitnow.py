from datetime import UTC, datetime
from app.collectors.base import BaseCollector
from app.schemas.job import NormalizedJob


class ArbeitnowCollector(BaseCollector):
    source = "arbeitnow"

    async def fetch(self, config):
        out = []
        max_pages = min(int(config.get("max_pages", 3)), 10)
        for page in range(1, max_pages + 1):
            data = await self.request_json(
                "https://www.arbeitnow.com/api/job-board-api", params={"page": page}
            )
            items = data.get("data", [])
            out.extend(items)
            if not data.get("links", {}).get("next"):
                break
        return out

    def normalize(self, raw, config):
        url = raw.get("url")
        created_ts = raw.get("created_at")
        posted_at = (
            datetime.fromtimestamp(created_ts, UTC)
            if isinstance(created_ts, (int, float))
            else None
        )
        is_remote = bool(raw.get("remote"))

        return NormalizedJob(
            source=self.source,
            source_job_id=str(raw.get("slug") or url),
            company_name=raw.get("company_name") or "Unknown",
            title=raw.get("title") or "",
            description=raw.get("description"),
            description_html=raw.get("description"),
            location=raw.get("location") or ("Remote" if is_remote else None),
            remote_type="remote" if is_remote else "onsite",
            employment_type=", ".join(raw.get("job_types", [])) or None,
            posted_at=posted_at,
            apply_url=url,
            source_url=url,
            skills=raw.get("tags") or [],
            source_metadata={
                key: raw[key]
                for key in ("tags", "job_types", "slug")
                if raw.get(key) is not None
            },
        )
