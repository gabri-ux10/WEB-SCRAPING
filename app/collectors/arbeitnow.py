from datetime import UTC, datetime
from app.collectors.base import BaseCollector
from app.schemas.job import NormalizedJob


class ArbeitnowCollector(BaseCollector):
    source = "arbeitnow"

    async def fetch(self, config):
        out = []
        page = 1
        next_url = None
        seen_pages = set()
        while True:
            data = await self.request_json_or_none(
                next_url or "https://www.arbeitnow.com/api/job-board-api",
                params=None if next_url else {"page": page},
            )
            if data is None:
                break
            items = data.get("data", [])
            if not items:
                self.exhausted = True
                break
            out.extend(items)
            next_value = data.get("links", {}).get("next")
            if not next_value:
                self.exhausted = True
                break
            if isinstance(next_value, str):
                if next_value in seen_pages:
                    self.exhausted = True
                    break
                seen_pages.add(next_value)
                next_url = next_value
            else:
                page += 1
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
