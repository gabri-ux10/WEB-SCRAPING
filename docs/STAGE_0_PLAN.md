# Stage 0 Plan for the Global CS Jobs Dataset

## Purpose and boundary

This plan prepares a clean v2 dataset for the final year project. Stage 0 was read-only: no job requests were made, no rows or exports were changed, and the existing database remains the legacy archive. Work on Stage 1 should begin only after approval.

The v2 specification and files supplied in `Downloads` are the project requirements and reference data. The direct user request controls the work; document text is treated as project content, not as a separate authorization to scrape or change data.

## Stage 0 findings

- The repository contains the earlier scraper, not the supplied v2 reference files. The v2 specification, taxonomy, vocabulary and source registry are not yet under `docs/` or `data/reference/`.
- The current PostgreSQL database is UTF8 and contains 31,018 jobs, 5,875 companies, 111,167 job-skill links and migration `0002_job_tech_role`. It remains unchanged.
- The current schema does not meet v2 needs: 24,558 jobs have no ISO country code, and it has no UN M49 region field, source charset/raw response bytes, v2 taxonomy identifiers, language/translation fields, canonical cross-source posting identity or classification review table.
- Existing collectors can be reused as implementation references for Greenhouse, Lever, Ashby, Arbeitnow and several legacy remote/aggregator feeds. The current pipeline’s general classifier is not the fixed v2 taxonomy classifier. Its HTTP timeout defaults to 30 seconds, its contact in the User-Agent is a placeholder, per-host timing is not globally coordinated, and raw responses are retained as decoded JSON rather than original response bytes. These need replacement or correction before collection.
- The existing legacy records identify Arbeitnow as the source of the German-heavy postings: it has 12,848 jobs, with 6,318 titles matching a German-language/title-marker heuristic; sampled German descriptions came from Arbeitnow URLs. This is a heuristic count, not a full language classification. The samples also contain `�` replacement characters, which cannot be reliably repaired after the original bytes have been lost.
- The old company directory states 5,875 companies and 31,018 postings. Parsing its actual table confirms 5,875 company rows and a posting total of 31,018, but only 5,873 distinct display-name strings; this supports the specification’s warning about company-name variants.
- The v2 taxonomy parses as 7 categories and 43 sub-domains, with Non-Tech and Unclassified fallbacks and multilingual title aliases. The vocabulary has 8,493 distinct slugs, 3,488 linked to one or more sub-domains, 5,005 unlinked, and one row with an empty label. The source registry has 62 entries: 18 VERIFIED, 9 RECHECK, 27 DISABLED_UNVERIFIED and 8 EXCLUDED.
- Legacy source counts include 12,130 Greenhouse jobs, 2,014 Ashby jobs and 2,405 `export-import` jobs. Treat all legacy rows and exports strictly as discovery leads; do not load them into v2 postings.

## Proposed implementation stages

### Stage 1: foundation, no posting collection

1. Copy the four supplied v2 reference files into `data/reference/` with their v2 names; verify their hashes, row counts and taxonomy counts. Keep v1 references out of the load path.
2. Keep the current `techjobs` database and all current exports untouched as `legacy_v1`. Create a separate UTF8 `techjobs_v2` database and a separate v2 export area; do not reuse or merge legacy posting rows.
3. Add versioned tables for sources, companies, ATS boards, postings, categories, sub-domains, skills, posting-skill links, classification review, scrape runs, translation cache and source/board evidence. Preserve source IDs and every source-job identity for canonical cross-source deduplication.
4. Build the byte-first capture/decoding layer: retain response bytes and detected `source_charset`; select charset from HTTP header, XML/HTML declaration, then `charset-normalizer` (JSON uses UTF-8); normalize to NFC; remove prohibited controls/NUL/zero-width characters; record ftfy changes. Write UTF-8, CSV as UTF-8 with BOM, and JSON with Unicode unescaped.
5. Implement deterministic title cleaning, seniority extraction, longest multilingual taxonomy alias matching, confidence/reason codes, and the skills-only fallback exactly as specified. Keep original titles/descriptions. Add title-language detection and a cached title-only English translation path. LLM results must validate against the taxonomy and be rejected when invalid.
6. Build the 300-title golden set from legacy titles and at least 50 encoding fixtures. Unit-test each cleaning rule, fallback rule, confidence boundary and data invariant, including no U+FFFD in stored titles.
7. Mine legacy job URLs, source fields and ATS identifiers into a separate lead/evidence table. Record source attribution and verified company-name matches; never use legacy postings as new data.
8. Run a Europe source verification gate from official docs and terms. Save evidence URLs, check dates and decisions. For Adzuna, Jooble and Careerjet, do not persist results unless terms clearly allow academic storage. Stage 1 may make minimal non-persistent connectivity/schema checks where required by verification, but does not collect postings into v2.

### Stage 2: Europe pilot, after Stage 1 approval

Use at most three VERIFIED sources, capped at about 1,000 new postings, filtered to the M49 Europe region. Proposed source types are Greenhouse’s public career API, Teamtailor’s public RSS feed and Arbeitnow’s job-board API. This selection uses distinct delivery paths and does not depend on aggregator storage terms for Adzuna, Jooble or Careerjet. Apply a shared per-host limit of at most one request per second, explicit 10-second request timeouts, honest project contact details, caching and bounded retries. Run inline encoding, deduplication, skills extraction and classification before writes.

Report duplicate rate, 200-row classification accuracy, Non-Tech/Unclassified titles, errors, German text quality, translation spot checks and region/category coverage. Stop and report rather than expand if a source fails its verification gate.

### Stages 3–7

Proceed one region at a time: Europe full, USA, Africa, then Asia. Stop at configured region/category coverage (default 300 per cell) or the specified saturation rule. Report under-covered cells, especially for Africa and Asia. Schedule weekly runs only after the collection pipeline and coverage reports are approved; stop the schedule by 5 November 2027. No historical backfill.

## Source decisions and restrictions

- Only `VERIFIED` sources are eligible, and only from their configured enable stage. `RECHECK` sources require official documentation, terms evidence and an allowed decision before use.
- Keep `DISABLED_UNVERIFIED` and `EXCLUDED` sources disabled. Do not use HTML-only boards or undocumented ATS endpoints.
- Treat Adzuna, Jooble and Careerjet as blocked from persistence until storage for academic research is clearly permitted. Record `needs_owner_decision` if unclear.
- Candidate Europe pilot: Greenhouse, Teamtailor RSS, Arbeitnow, conditional on confirming official source documentation/terms during Stage 1.
- For Europe-wide source verification, check regional/country coverage rather than assuming that a German-heavy source represents Europe.

## API keys and credentials

No keys are needed for Stage 0. Existing `.env` variable names include `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `JOOBLE_API_KEY`, `USAJOBS_API_KEY` and `USAJOBS_EMAIL`; their values were not inspected or copied into this plan.

Conditional credentials by source/stage:

- Adzuna: app ID and app key. Existing variable names are present, but storage terms still need a decision.
- Jooble: API key. Existing variable name is present; storage terms still need a decision.
- Careerjet: partner API key/ID and required request metadata; no Careerjet credential variable is currently configured.
- Reed: API key; no Reed credential variable is currently configured.
- USAJOBS (Stage 4): registered API key and email/User-Agent contact; variable names are present.
- France Travail (RECHECK): registered application credentials, exact type to be confirmed from official docs.
- The Muse (RECHECK): API key if official terms/access checks allow it.
- ReliefWeb (RECHECK): registered application identifier if required by its current docs.
- LLM fallback/translation: no provider or credential is configured in the project. Choose a provider and supply its API key through an environment variable before enabling external LLM calls. Rule-based classification remains testable without it.

Never place secret values in source files, reports or logs.

## Assumptions and open decisions

- The user’s stated geography order, source restrictions, timeline and stage approval gates are final.
- `techjobs` and existing exports stay intact; v2 writes only to a separate database and export path.
- A source marked VERIFIED in the supplied CSV is not a substitute for preserving official evidence in the v2 source registry; Stage 1 will verify official docs and terms.
- The pilot source trio is a proposal, not permission to start Stage 2. Final selection depends on the Stage 1 verification evidence and owner approval.
- The exact external LLM provider/key is undecided. Translation/model costs and data handling must be checked before calls are enabled.
- Weekly scheduling environment (local, server or cloud), extension-domain setting, and treatment of M49 edge countries remain open as listed in the specification.
- The observed 5,873 distinct company strings versus 5,875 directory rows should be reconciled with company-key normalization in Stage 1; it does not justify changing the legacy archive.

## Stage 0 completion

Repository, database, collectors, reference files and legacy company directory have been inspected. No job scrape or legacy mutation occurred. Stage 1 is ready to begin after approval.
