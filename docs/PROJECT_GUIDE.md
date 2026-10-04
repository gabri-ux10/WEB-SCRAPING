# TechJobs Aggregator: Project and Deployment Guide

TechJobs Aggregator collects public technology job postings, normalizes and classifies them, stores them in PostgreSQL, and exposes read-only search and export interfaces. This guide explains the project layout, local setup, common operations, and a practical single-server deployment.

## What the service does

The ingestion pipeline is:

```text
Fetch public listings → save raw response → normalize → validate → classify
→ extract skills → find duplicates → upsert jobs → record history
```

Each source connector is isolated in `app/collectors/`. The scraping service coordinates collection and records run and error details. SQLAlchemy defines the schema, Alembic applies schema migrations, and FastAPI serves read-only endpoints. Raw response snapshots are saved under `data/raw/` before normalization; exports are written under `data/exports/`.

### Project layout

| Path | Purpose |
|---|---|
| `app/api/` | FastAPI app and read-only HTTP routes |
| `app/collectors/` | Greenhouse, Lever, Ashby, and optional aggregator connectors |
| `app/classification/` | Job category and skill extraction rules |
| `app/database/` | SQLAlchemy models and async database sessions |
| `app/deduplication/` | Cross-source duplicate candidate scoring |
| `app/normalization/` | Title, location, salary, and posting normalization |
| `app/persistence/` | Job insert/update and history persistence |
| `app/services/scraping.py` | Collection orchestration, exports, and persistence workflow |
| `config/` | Company boards, sources, regions, search terms, and classification rules |
| `migrations/` | Alembic schema revisions |
| `tests/` | Unit and API tests |
| `Dockerfile`, `docker-compose.yml` | API container and local PostgreSQL development stack |

### Sources

Greenhouse, Lever, and Ashby connectors use public company job board endpoints. Adzuna, USAJOBS, Jooble, and Jobicy are optional sources; API credentials are needed for some of them. Which sources are enabled is controlled by `config/sources.yml`. Company board identifiers are maintained in `config/companies.yml`. The checked-in company entries are disabled placeholders; verify a company's public board identifier before enabling it.

Only public postings are requested. Do not bypass authentication, CAPTCHAs, access restrictions, or provider bot protections. Review each source's terms and quotas before enabling it.

## Requirements

- Python 3.12 or newer
- Docker Engine/Desktop with Docker Compose v2 for the bundled PostgreSQL and API containers
- Git, if cloning the repository

The examples below use PowerShell on Windows. Commands also work in a POSIX shell after adjusting virtual environment activation and file-copy syntax.

## Local development setup

From the repository root:

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
docker compose up -d db
alembic upgrade head
```

The default `DATABASE_URL` in `.env` connects the host Python process to PostgreSQL at `localhost:5432`. The Compose database publishes that port on host loopback only. Apply migrations after the database is healthy and before scraping or serving requests.

Start a scrape from the host environment:

```powershell
python -m app.cli scrape
```

Start the API in a separate terminal:

```powershell
docker compose up -d app
```

The API is available at `http://localhost:8000`; interactive API documentation is at `http://localhost:8000/docs`. The app container connects to the Compose database by the internal hostname `db`. The Compose app's database URL is set in `docker-compose.yml`; the host CLI uses `.env`.

Stop the services with `docker compose down`. This preserves the PostgreSQL named volume. To also remove the database volume and all stored data, use `docker compose down -v`.

## Configuration

Settings are read from environment variables and `.env` (see `app/config.py`). Keep `.env` out of version control; `.gitignore` already excludes it. Do not put production credentials into YAML configuration files or commit them.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Async SQLAlchemy/PostgreSQL connection string |
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | Adzuna API credentials |
| `USAJOBS_API_KEY`, `USAJOBS_EMAIL` | USAJOBS API key and contact email |
| `JOOBLE_API_KEY` | Jooble API key |
| `REQUEST_TIMEOUT` | HTTP request timeout in seconds (default `30`) |
| `MAX_RETRIES` | Retry limit for transient provider/network errors (default `3`) |
| `LOG_LEVEL` | Logging level (default `INFO`) |

Missing credentials skip the corresponding optional connector. Source-specific enablement, request caps, and regional settings are held in `config/sources.yml` and `config/regions.yml`.

## Common operations

### Scrape jobs

```powershell
python -m app.cli scrape
python -m app.cli scrape --source greenhouse
python -m app.cli scrape --country KE
python -m app.cli scrape --region africa
python -m app.cli scrape --company "My Startup"
python -m app.cli scrape --dry-run --max-pages 1 --max-jobs 50
```

Use `--dry-run` and small page/job limits when validating a connector. A scrape can partially succeed; inspect the CLI summary and the `scrape_runs` / `scrape_errors` records. A failed or malformed company feed does not advance missing-posting observations.

### Export and inspect

```powershell
python -m app.cli export --format csv
python -m app.cli export --format json
python -m app.cli export --format jsonl --output data/exports/review.jsonl
python -m app.cli jobs
python -m app.cli health
```

The default export paths are `data/exports/jobs.csv`, `jobs.json`, and `jobs.jsonl`. Raw snapshots and exports are local filesystem artifacts; arrange backup or durable storage for them if they must survive host replacement.

### API endpoints

| Method and path | Description |
|---|---|
| `GET /health` | Process liveness check |
| `GET /jobs` | Search and filter jobs (supports pagination) |
| `GET /jobs/{id}` | Fetch one job |
| `GET /companies` | List companies |
| `GET /companies/{id}` | Fetch a company |
| `GET /sources` | List sources |
| `GET /stats` | Summary statistics |

Example:

```text
GET /jobs?country=KE&category=Software%20Engineering&remote_type=remote
GET /jobs?q=python&skill=Python&limit=25&offset=0
```

Job filters include `q`, `country`, `region`, `city`, `remote_type`, `employment_type`, `category`, `skill`, `company`, `source`, `posted_after`, `posted_before`, and `salary_min`. API docs at `/docs` show the response schemas and accepted parameters.

### Add or update a company

Edit `config/companies.yml`. Verify the provider and exact public board identifier from the company's official careers page and provider endpoint. Keep the entry disabled until verification:

```yaml
- name: My Startup
  country: KE
  region: kenya
  website: https://example.com
  careers_url: https://example.com/careers
  ats: ashby
  ats_identifier: verified-public-board-name
  enabled: false
```

Then test the connector with a limited dry run before enabling the company for regular collection.

## Deploying to a single Linux server

The included Compose file is a development starting point. It uses a default PostgreSQL password and publishes the API on port 8000, so do not expose it directly to the public internet. For production, use a maintained Linux host, restrict inbound traffic, terminate HTTPS at a reverse proxy such as Caddy or Nginx, and use a strong database credential or managed PostgreSQL.

### Prepare the host

Install Docker Engine and the Compose plugin, then clone the repository on the server. Configure the domain's DNS to point at the server and permit inbound HTTPS (TCP 443). Keep SSH access restricted to trusted administrators.

Before starting production services, update `docker-compose.yml` or create a production Compose override to:

1. Replace the hard-coded PostgreSQL password with a strong secret provided outside version control, and use the same credential in the app's database URL.
2. Bind the API port to loopback (for example `127.0.0.1:8000:8000`) so only a host reverse proxy can reach it.
3. Keep the PostgreSQL port bound to loopback or remove its host port mapping when it is not needed from the host.
4. Configure a persistent volume for PostgreSQL and a backup plan. Preserve `data/raw` and `data/exports` separately if those artifacts are required.

Do not publish the production `.env` or secrets in source control, shell history, build logs, or support tickets. For a managed PostgreSQL database, remove the Compose app's hard-coded `DATABASE_URL` override and provide the managed connection string through your deployment secret manager.

### Deploy the API

With the production environment and Compose settings configured, start the database and apply migrations from the checked-out repository using Python 3.12 and the configured `DATABASE_URL`:

```bash
docker compose up -d db
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install .
alembic upgrade head
```

Then build and start the API container:

```bash
docker compose up -d --build app
docker compose ps
docker compose logs --tail=100 app
```

The `Dockerfile` runs Uvicorn on port 8000. Configure the reverse proxy to forward HTTPS requests to `127.0.0.1:8000`; enable automatic certificate renewal and redirect HTTP to HTTPS. Confirm `/health` locally and through the domain after deployment. Do not expose `/docs` publicly unless that is appropriate for your service.

### Schedule collection

The API container does not run collection automatically. Run the CLI from a host-side Python environment on a schedule (cron/systemd timer), using the same database URL and source credentials as the API. Example cron entry for every six hours:

```cron
0 */6 * * * cd /srv/techjobs-aggregator && .venv/bin/python -m app.cli scrape >> /var/log/techjobs-scrape.log 2>&1
```

Set restrictive permissions on the environment file and log directory. Watch task exit status, logs, and `scrape_errors`; review provider quotas before increasing frequency.

### Updating and backing up

Before an update, take a PostgreSQL backup and preserve any raw snapshot data needed for audit or reprocessing. Pull the intended revision, install updated Python dependencies if needed, apply migrations, and rebuild the API image:

```bash
git pull --ff-only
.venv/bin/python -m pip install .
.venv/bin/alembic upgrade head
docker compose up -d --build app
```

Use `pg_dump` for PostgreSQL backups and regularly test restoring a backup. Docker named volumes are persistent across container replacement, but they are not a backup. Keep a rollback plan for the application revision and database schema changes.

## Database and data behavior

The schema includes `sources`, `companies`, `locations`, `jobs`, `job_history`, `skills`, `job_skills`, `scrape_runs`, `scrape_errors`, and `duplicate_candidates`. `(source_id, source_job_id)` is unique. Meaningful updates preserve prior state in history. Cross-source matches are stored as candidates and are not merged automatically. Jobs missing from a fully successful company feed accrue missing observations and are closed after the configured threshold.

Apply schema updates with `alembic upgrade head`. Review Alembic autogeneration output before creating or applying a new migration. The app does not automatically migrate the database during startup.

## Quality checks and troubleshooting

Run the project checks from the activated virtual environment:

```powershell
pytest
ruff check app tests
```

| Symptom | Check |
|---|---|
| Database connection error | Run `docker compose ps`; verify PostgreSQL is healthy and the process uses the correct host (`localhost` from the host, `db` from Compose). |
| `python -m app.cli health` fails | Confirm `.env` and `DATABASE_URL`, then run `alembic upgrade head`. |
| Company returns 404 | Recheck the public ATS board token/site name against the official careers page. |
| Optional source is skipped | Set its required credentials and enable it in `config/sources.yml`. |
| No jobs are returned | Check company entries are enabled and verified, source enablement, country/region filters, and scrape errors. |
| API container cannot connect to PostgreSQL | Confirm both services are on the Compose network and that the app container uses hostname `db`, not `localhost`. |

## Current operational limits

- Company configuration contains disabled placeholders until board identifiers are verified.
- Geographic coverage depends on configured public boards and optional API access.
- Duplicate matches across sources are suggestions only; there is no automatic merge workflow.
- Raw snapshots and exports are local files, not automatically uploaded to object storage.
- The API currently has no authentication or rate limiting; place it behind a suitable access-control layer before exposing sensitive or high-volume deployments.
- Salary currencies are not converted, and provider APIs may return abbreviated descriptions or impose changing quotas.
