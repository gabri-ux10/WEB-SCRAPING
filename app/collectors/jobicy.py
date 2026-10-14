from app.collectors.base import BaseCollector
from app.schemas.job import NormalizedJob


class JobicyCollector(BaseCollector):
    source = "jobicy"

    async def fetch(self, config):
        out = []
        cursor = None
        seen_cursors = set()
        while True:
            params = {"count": min(int(config.get("count", 100)), 200)}
            for k in ("geo", "industry", "tag"):
                if config.get(k):
                    params[k] = config[k]
            if cursor:
                params["cursor"] = cursor
            data = await self.request_json_or_none("https://jobicy.com/api/v2/remote-jobs", params=params)
            if data is None:
                break
            jobs = data.get("jobs", [])
            if not jobs:
                self.exhausted = True
                break
            out.extend(jobs)
            cursor = data.get("nextCursor")
            if not cursor or cursor in seen_cursors:
                self.exhausted = True
                break
            seen_cursors.add(cursor)
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
