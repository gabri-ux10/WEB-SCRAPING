from app.collectors.base import BaseCollector
from app.schemas.job import NormalizedJob


class GreenhouseCollector(BaseCollector):
    source = "greenhouse"

    async def fetch(self, config):
        board = config["ats_identifier"]
        data = await self.request_json(
            f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs", params={"content": "true"}
        )
        return data.get("jobs", [])

    def normalize(self, raw, config):
        loc = (raw.get("location") or {}).get("name")
        return NormalizedJob(
            source=self.source,
            source_job_id=str(raw["id"]),
            company_name=config["name"],
            title=raw.get("title") or "",
            description=raw.get("content"),
            description_html=raw.get("content"),
            location=loc,
            department=", ".join(d.get("name", "") for d in raw.get("departments", [])) or None,
            posted_at=raw.get("updated_at"),
            apply_url=raw.get("absolute_url"),
            source_url=raw.get("absolute_url"),
            source_metadata={
                key: raw[key] for key in ("metadata", "offices") if raw.get(key) is not None
            }
            or None,
        )
