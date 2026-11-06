# Stage 2 Network Preflight

Checked: 2026-11-06
Preflight order: try Arbeitnow first, then require Greenhouse; if Arbeitnow is unavailable, continue with Greenhouse only. Teamtailor discovery is optional and runs only from a successful Arbeitnow sample. The report records proxy variable names only, never proxy values or the project contact. Each source host received at most one preflight HTTP GET with a 10-second timeout and redirects disabled. Teamtailor candidates were derived only from Arbeitnow job/apply URLs; each candidate was tried once with at least one second between requests to the same host.

Proxy settings detected: none

| Source | Host | DNS | Resolved addresses | TCP | TLS | HTTP status | Classification |
|---|---|---|---|---|---|---:|---|
| arbeitnow | `www.arbeitnow.com` | OK | `2606:4700:20::ac43:47fb,2606:4700:20::681a:820,2606:4700:20::681a:920,104.26.9.32,172.67.71.251,104.26.8.32` | OK | OK | 200 | HTTP_OK |
| greenhouse | `boards-api.greenhouse.io` | OK | `64:ff9b::3a4:c371,64:ff9b::3a4:c310,64:ff9b::3a4:c312,64:ff9b::3a4:c31b,3.164.195.16,3.164.195.113,3.164.195.18,3.164.195.27` | OK | OK | 200 | HTTP_OK |

arbeitnow: available
teamtailor: no verified feed found in the Arbeitnow sample
