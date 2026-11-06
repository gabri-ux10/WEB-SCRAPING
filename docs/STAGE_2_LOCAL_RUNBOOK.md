# Stage 2 Local Runbook

## Required `.env` key names

- `DATABASE_URL`
- `CSJOBS_CONTACT_EMAIL`

Teamtailor is optional. The preflight samples Arbeitnow, then checks Greenhouse, then derives up to five Teamtailor feeds only from job/apply URLs in that Arbeitnow response. It accepts a feed only when its RSS channel title matches the Arbeitnow company name, and then merges the two Teamtailor keys into `.env` and records the board in `ats_boards` when the database is available. If no match is found, it runs without Teamtailor. Do not copy `.env.example` over an existing `.env`; merge or edit only individual keys. The `DATABASE_URL` value is never displayed.

## PowerShell sequence

1. The workspace setting has been restored by `scripts/restore_database_url_from_compose.ps1`. That helper refuses to overwrite an existing key and does not display the URL. If the Compose-based local setting is not the one you intend, edit only `DATABASE_URL` in the existing file and preserve the contact line:

   ```powershell
   Set-Location 'C:\Users\GABRIEL\WEB-SCRAPING'
   notepad .env
   ```

2. Check the v2 database counts:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   python -m app.v2.db_check
   ```

If the checker says `AUTHENTICATION_FAILED`, enter the actual password for the configured PostgreSQL role through the hidden prompt in `scripts/set_postgres_password.ps1`. This updates only the `DATABASE_URL` key and does not alter PostgreSQL data. Then rerun `python -m app.v2.db_check`.

3. Run the local pilot wrapper. It loads `.env` into child processes, tries Arbeitnow first, requires the Greenhouse preflight, performs optional Teamtailor discovery only when the Arbeitnow sample is available, applies the isolated v2 schema update to `techjobs_v2`, and runs Africa, USA-only, and Asia pilots in sequence. If Arbeitnow is unreachable, the wrapper continues with Greenhouse only. Each region is capped at 500 source records per source and 1,000 unique canonical postings. The pilot reports are written to `docs/` and a `[STAGE3_SUMMARY]` line is printed.

   ```powershell
   .\scripts\run_stage2_pilot.ps1
   ```

The wrapper already runs the preflight; do not separately run it immediately before the wrapper, since that repeats source requests. For diagnostics only, the command is `python -m app.v2.preflight`. It never prints the contact value. The regional exports are `data/exports/stage3_africa_pilot.csv`, `stage3_usa_pilot.csv`, and `stage3_asia_pilot.csv`.
