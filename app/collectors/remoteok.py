from app.collectors.base import BaseCollector
from app.schemas.job import NormalizedJob


class RemoteOKCollector(BaseCollector):
    source = "remoteok"

    async def fetch(self, config):
        data = await self.request_json("https://remoteok.com/api")
        if not isinstance(data, list):
            return []
        # First entry is legal disclaimer/metadata
        jobs = [item for item in data if isinstance(item, dict) and item.get("id")]
        max_jobs = int(config.get("max_jobs", 100))
        return jobs[:max_jobs]

    def normalize(self, raw, config):
        url = raw.get("apply_url") or raw.get("url")
        salary_min = float(raw.get("salary_min")) if raw.get("salary_min") else None
        salary_max = float(raw.get("salary_max")) if raw.get("salary_max") else None

        return NormalizedJob(
            source=self.source,
            source_job_id=str(raw.get("id") or ""),
            company_name=raw.get("company") or "Unknown",
            title=raw.get("position") or "",
            description=raw.get("description"),
            description_html=raw.get("description"),
            location=raw.get("location") or "Remote",
            remote_type="remote",
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency="USD" if (salary_min or salary_max) else None,
            salary_period="yearly" if (salary_min or salary_max) else None,
            posted_at=raw.get("date"),
            apply_url=url,
            source_url=raw.get("url") or url,
            skills=raw.get("tags") or [],
            source_metadata={
                key: raw[key]
                for key in ("tags", "epoch", "slug")
                if raw.get(key) is not None
            },
        )
