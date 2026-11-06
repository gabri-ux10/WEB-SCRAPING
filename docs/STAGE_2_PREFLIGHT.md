# Stage 2 Europe Pilot Preflight

Checked: 2026-11-06
Each request followed a fresh check of `source_terms_decisions_v2.csv`; exactly one request was attempted per source until the first non-200/transport failure. Responses were discarded and not stored. Timeout: 10 seconds. User-Agent used the dedicated project contact from the ignored `.env`; its address is intentionally not recorded here.

| Source | Request endpoint | Terms checked | Decision | Evidence URL | HTTP status | Result |
|---|---|---|---|---|---:|---|
| arbeitnow | `https://www.arbeitnow.com/api/job-board-api?page=1` | 2026-11-06 | public_feed_policy | https://www.arbeitnow.com/blog/job-board-api | no response | error:ConnectError |
