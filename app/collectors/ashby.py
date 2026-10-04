from app.collectors.base import BaseCollector
from app.schemas.job import NormalizedJob


class AshbyCollector(BaseCollector):
    source = "ashby"

    async def fetch(self, config):
        data = await self.request_json(
            f"https://api.ashbyhq.com/posting-api/job-board/{config['ats_identifier']}",
            params={"includeCompensation": "true"},
        )
        return [j for j in data.get("jobs", []) if j.get("isListed", True)]

    def normalize(self, raw, config):
        address = (raw.get("address") or {}).get("postalAddress") or {}
        comp = raw.get("compensation") or {}
        salary = next(
            (
                row
                for row in comp.get("summaryComponents", [])
                if row.get("compensationType") == "Salary"
            ),
            {},
        )
        return NormalizedJob(
            source=self.source,
            source_job_id=str(raw.get("id") or raw.get("jobUrl")),
            company_name=config["name"],
            title=raw.get("title") or "",
            description=raw.get("descriptionPlain"),
            description_html=raw.get("descriptionHtml"),
            location=raw.get("location"),
            city=address.get("addressLocality"),
            region=address.get("addressRegion"),
            country=address.get("addressCountry"),
            remote_type=(
                raw.get("workplaceType") or ("remote" if raw.get("isRemote") else "unknown")
            ).lower(),
            employment_type=raw.get("employmentType"),
            department=raw.get("department"),
            posted_at=raw.get("publishedAt"),
            apply_url=raw.get("applyUrl"),
            source_url=raw.get("jobUrl"),
            salary_raw=comp.get("scrapeableCompensationSalarySummary"),
            salary_min=salary.get("minValue"),
            salary_max=salary.get("maxValue"),
            salary_currency=salary.get("currencyCode"),
            salary_period=salary.get("interval"),
            source_metadata={
                key: raw[key] for key in ("secondaryLocations", "team") if raw.get(key) is not None
            }
            or None,
        )
