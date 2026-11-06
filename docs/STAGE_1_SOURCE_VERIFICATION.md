# Stage 1 Europe Source Verification

Checked 6 November 2026 against official documentation and source terms where available. No job listing endpoints were requested and no job records were stored. This is an access and terms gate, not legal advice. The v2 request ceiling remains one request per host per second.

## Verified source registry entries

| Source | Official evidence | Result and terms decision |
|---|---|---|
| Greenhouse | [Job Board API](https://docs.greenhouse.io/job-board.html) | Public GET endpoints require no authentication and expose published jobs for company career pages. Eligible under the user’s public-API rule; no bulk request made. |
| Lever | [Postings API](https://github.com/lever/postings-api) | Official docs provide published postings, pagination, and global/EU hosts. Use `api.eu.lever.co` for EU-hosted boards. Eligible under the user’s public-API rule. |
| Ashby | [Public Job Posting API](https://developers.ashbyhq.com/docs/public-job-posting-api) | Official board endpoint returns published jobs. Respect `isListed=false` and retain listed-only behavior. Eligible under the user’s public-API rule. |
| SmartRecruiters | [Posting API](https://developers.smartrecruiters.com/docs/posting-api), [authentication](https://developers.smartrecruiters.com/docs/authentication) | Official Posting API exposes published postings. The platform also supports credentials that can expose internal postings; v2 must not use credentials and must request only public endpoints. |
| Workable | [Careers API guide](https://help.workable.com/hc/en-us/articles/115012771647-Using-the-Workable-API-to-create-a-careers-page), [API documentation](https://help.workable.com/hc/en-us/articles/115013356548-Workable-API-Documentation) | Official docs describe displaying published jobs on employer career pages and a public endpoint. Do not use authenticated candidate or private ATS endpoints. |
| Recruitee | [Published offers endpoint](https://docs.recruitee.com/reference/offers) | Official endpoint returns published jobs. The separate Careers Site API requires an employer token; use only the documented public offers endpoint. |
| Personio | [XML job feed](https://support.personio.de/hc/en-us/articles/207576365-Integrate-jobs-from-Personio-into-your-website-via-XML) | Official feed is enabled per employer and intended for career-page integration. Use only activated public feeds; English is requested with `language=en`. |
| Teamtailor RSS | [RSS feed guide](https://support.teamtailor.com/en/articles/11171756-rss-feed-how-to-guide) | Official docs say feed contents are public and document pagination. Eligible as a public feed; attribute/link to the source listing. |
| Pinpoint | [Postings JSON endpoint](https://developers.pinpointhq.com/docs/jobs-json-endpoint) | Official `postings.json` is the current public careers feed; it replaces deprecated `jobs.json`. Eligible under the user’s public-feed rule. |
| Gem | [Job Board API](https://help.gem.com/databases/gem-help-center/the-job-board-api) | Official endpoint returns currently open job posts and is intended for custom job boards. Eligible under the user’s public-API rule. |
| Polymer | [Public API](https://developer.polymer.co/) | Official docs distinguish unauthenticated public job listings from authenticated hiring data; public API is rate-limited and intended for job-board integrations. Use public endpoints only. |
| Arbeitnow | [Job Board API](https://www.arbeitnow.com/blog/job-board-api) | Official page documents a free, no-key job-search API covering jobs aggregated from multiple ATS platforms. Eligible as a public API; expect duplicates and preserve original listing URLs. |
| Remotive | [Public API and terms](https://remotive.com/remote-jobs/api), [API help](https://support.remotive.com/en/article/list-remote-jobs-public-api-105pww2/) | API access allows further sharing with source attribution and prohibits submission to third-party job sites. Long-term research-dataset storage is not expressly addressed; set `terms_decision=needs_owner_decision` before persistence. Respect the registry’s request cap. |

## Storage blocked pending permission or clearer terms

| Source | Official evidence | Decision |
|---|---|---|
| Adzuna | [API terms](https://developer.adzuna.com/docs/terms_of_service) | Academic research is listed as a permitted use, but organizational/academic use is limited to a 14-day validation trial; ongoing research in original or aggregated form requires written consent. Do not persist results without written permission covering this longitudinal study. |
| Jooble | [REST API documentation](https://help.jooble.org/en/support/solutions/articles/60001448238), [API portal](https://jooble.org/api/about), [terms](https://jooble.org/info/terms) | API is described for displaying search results on a website; the public-site terms prohibit automated crawlers and copying. No clear academic bulk-storage grant was found. Do not persist without written permission/API terms confirming it. Each country requires its own key; the current official help page states a 500-request lifetime free quota. |
| Careerjet | [Partner API](https://www.careerjet.com/partners/api/), [partner program](https://www.careerjet.com/partners/) | API is for publisher websites displaying Careerjet results; requests require user IP, user-agent and referrer. No academic dataset-retention grant was found. Do not persist without written permission. |
| Reed | [Registry-listed Jobseeker API](https://www.reed.co.uk/developers/jobseeker) | Current official search did not verify a usable public job-search API contract and terms for research storage. Treat as unavailable until Reed confirms the endpoint, key eligibility, and storage rights. |

## RECHECK sources with Europe relevance

| Source | Official evidence | Decision |
|---|---|---|
| France Travail | [Official API data-service record](https://www.data.gouv.fr/dataservices/api-offres-demploi), [legal conditions](https://www.francetravail.fr/informations/informations-legales-et-conditio/conditions-generales-dutilisatio.html) | API access is currently withdrawn while France Travail reviews distribution and reuse rules. Access is restricted and its listing says no reuse licence is specified. Do not request job data or store results until the official service reopens and grants access. |
| EURES | [EURES job-vacancy terms](https://europa.eu/eures/portal/jv-se/home?lang=en) | Automated extraction is limited to EURES partner organizations recognized by a national coordination office; screen-scraping is prohibited. This project has no documented partner status. Do not use. |

## Gate status

- Official public endpoint/feed documentation confirmed for Greenhouse, Lever, Ashby, SmartRecruiters, Workable, Recruitee, Personio, Teamtailor RSS, Pinpoint, Gem, Polymer and Arbeitnow.
- Public API documentation was confirmed for Remotive, but storage beyond attributed display remains unresolved.
- Adzuna, Jooble, Careerjet and Reed remain blocked from database writes pending the decisions above.
- France Travail and EURES are not available to this project under their current access/terms.
- No endpoint live tests were run in Stage 1 because the stage prohibits job scraping. The registry’s October 2026 `VERIFIED` status remains historical evidence, not a new live test.
- Proposed Stage 2 pilot remains Greenhouse + Teamtailor RSS + Arbeitnow, capped at about 1,000 Europe postings, subject to the Stage 2 approval gate.
