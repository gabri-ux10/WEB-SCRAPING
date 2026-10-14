from app.collectors.base import BaseCollector
from app.schemas.job import NormalizedJob


class RemotiveCollector(BaseCollector):
    """Single-request public feed; the provider advises fetching no more than 4x/day."""

    source = "remotive"

    TECH_CATEGORIES = (
        "software",
        "devops",
        "data science",
        "sysadmin",
        "product",
        "qa",
        "quality assurance",
        "engineering",
        "design",
    )

    async def fetch(self, config):
        data = await self.request_json("https://remotive.com/api/remote-jobs")
        jobs = data.get("jobs", [])
        # The feed spans several industries. Keep technology and adjacent product roles.
        jobs = [
            job
            for job in jobs
            if any(
                category in str(job.get("category", "")).lower()
                for category in self.TECH_CATEGORIES
            )
        ]
        self.exhausted = True
        return jobs

    def normalize(self, raw, config):
        url = raw.get("url")
        category = raw.get("category")
        tags = raw.get("tags") or []
        skills = tags if isinstance(tags, list) else [str(tags)]
        if category and category not in skills:
            skills.append(category)

        return NormalizedJob(
            source=self.source,
            source_job_id=str(raw.get("id") or url or ""),
            company_name=raw.get("company_name") or "Unknown",
            title=raw.get("title") or "",
            description=raw.get("description"),
            description_html=raw.get("description"),
            location=raw.get("candidate_required_location") or "Remote",
            remote_type="remote",
            employment_type=raw.get("job_type"),
            posted_at=raw.get("publication_date"),
            apply_url=url,
            source_url=url,
            skills=skills,
            source_metadata={
                key: raw[key]
                for key in ("category", "tags", "job_type")
                if raw.get(key) is not None
            },
        )
