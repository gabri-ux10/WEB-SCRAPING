from app.collectors.base import BaseCollector
from app.schemas.job import NormalizedJob


class JobicyCollector(BaseCollector):
    source = "jobicy"

    async def fetch(self, config):
        out = []
        cursor = None
        for _ in range(min(int(config.get("max_pages", 2)), 20)):
            params = {"count": min(int(config.get("count", 100)), 200)}
            for k in ("geo", "industry", "tag"):
                if config.get(k):
                    params[k] = config[k]
            if cursor:
                params["cursor"] = cursor
            data = await self.request_json("https://jobicy.com/api/v2/remote-jobs", params=params)
            out.extend(data.get("jobs", []))
            cursor = data.get("nextCursor")
            if not cursor:
                break
        return out

    def normalize(self, raw, config):
        url = raw.get("url")
        return NormalizedJob(
            source=self.source,
            source_job_id=str(raw.get("id") or ""),
            company_name=raw.get("companyName") or "Unknown",
            title=raw.get("jobTitle") or "",
            description=raw.get("jobExcerpt"),
            description_html=raw.get("jobDescription"),
            location=raw.get("jobGeo"),
            remote_type="remote",
            employment_type=", ".join(raw.get("jobType", [])) or None,
            seniority=raw.get("jobLevel"),
            salary_min=raw.get("salaryMin"),
            salary_max=raw.get("salaryMax"),
            salary_currency=raw.get("salaryCurrency"),
            salary_period=raw.get("salaryPeriod"),
            posted_at=raw.get("pubDate"),
            apply_url=url,
            source_url=url,
            source_metadata={
                key: raw[key]
                for key in ("jobIndustry", "jobGeo", "jobLevel")
                if raw.get(key) is not None
            },
        )
