from datetime import UTC, datetime

from app.collectors.base import BaseCollector
from app.normalization.normalize import clean_html
from app.schemas.job import NormalizedJob


class LeverCollector(BaseCollector):
    source = "lever"

    async def fetch(self, config):
        host = "api.eu.lever.co" if config.get("region_code") == "eu" else "api.lever.co"
        out = []
        limit = min(int(config.get("page_size", 100)), 100)
        pages = min(int(config.get("max_pages", 1)), 20)
        for page in range(pages):
            rows = await self.request_json(
                f"https://{host}/v0/postings/{config['ats_identifier']}",
                params={"mode": "json", "skip": page * limit, "limit": limit},
            )
            if not isinstance(rows, list):
                raise ValueError("Lever response must be a JSON array")
            out.extend(rows)
            if len(rows) < limit:
                break
        return out[: int(config.get("max_jobs", 1000))]

    def normalize(self, raw, config):
        categories = raw.get("categories") or {}
        sections = "\n".join(x.get("content", "") for x in raw.get("descriptionSections", []))
        description_html = raw.get("description") or sections or None
        created = raw.get("createdAt")
        posted_at = (
            datetime.fromtimestamp(created / 1000, UTC)
            if isinstance(created, (int, float))
            else created
        )
        return NormalizedJob(
            source=self.source,
            source_job_id=str(raw.get("id") or raw.get("hostedUrl")),
            company_name=config["name"],
            title=raw.get("text") or "",
            description=clean_html(description_html),
            description_html=description_html,
            location=(raw.get("categories") or {}).get("location") or (raw.get("workplaceType")),
            department=categories.get("team"),
            employment_type=categories.get("commitment"),
            remote_type=(raw.get("workplaceType") or "unknown").lower(),
            posted_at=posted_at,
            apply_url=raw.get("applyUrl") or raw.get("hostedUrl"),
            source_url=raw.get("hostedUrl"),
            source_metadata={"categories": categories} if categories else None,
        )
