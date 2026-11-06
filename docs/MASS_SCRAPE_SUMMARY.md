# Mass Scrape Summary

Run date: 2026-11-06

## Work completed

- Ran the Europe pilot and three additional regional pilots: Africa (UN M49 002), USA only (country code US, M49 Americas 019), and Asia (UN M49 142).
- Used the public Arbeitnow API and approved Greenhouse board feeds. Arbeitnow and Greenhouse passed the final preflight. Teamtailor discovery found no verified feed in the Arbeitnow sample, so it was skipped.
- Kept each region bounded at 500 source records per source and 1,000 unique canonical keys. The USA Greenhouse source reached its 500-record cap.
- Added **1,766 posting rows** to `techjobs_v2`, representing **1,575 distinct canonical jobs**. The row count includes cross-source observations; canonical IDs identify deduplicated jobs.
- Exported all database postings to `data/exports/global_jobs.csv` (1,766 rows, about 14 MB). It includes job title, company, description, location, source, classification, skills, and timestamps.
- Created separate regional reports: `STAGE_3_AFRICA_PILOT_REPORT.md`, `STAGE_3_USA_PILOT_REPORT.md`, and `STAGE_3_ASIA_PILOT_REPORT.md`.

| Region | Posting rows | Arbeitnow | Greenhouse |
|---|---:|---:|---:|
| Europe | 974 | 497 | 477 |
| Africa | 1 | 0 | 1 |
| USA | 501 | 1 | 500 |
| Asia | 290 | 2 | 288 |
| **Total** | **1,766** | **500** | **1,266** |

## Improvements for future coverage

1. **Add more approved sources and board leads.** The current run used a narrow source set and the Greenhouse boards already in the database. Discover and verify more official ATS boards and regional public feeds, then record the evidence and terms decision before enabling them.
2. **Expand Africa coverage.** Only one Africa posting was found, from Greenhouse; Arbeitnow returned none in its sample. Add reputable Africa-focused feeds and more Africa-serving employer boards, subject to source review.
3. **Increase USA coverage.** Greenhouse reached the 500-record cap, so raise the cap in a staged run and add more verified boards or permitted sources.
4. **Restore offline translation.** OPUS-MT models/runtime were unavailable during these runs. Cache and validate the supported models so English title fields can be populated for non-English jobs.
5. **Measure classification and geography quality.** Human labels are still needed for the title review samples. Review ambiguous roles, unknown locations, and region assignment before broadening the classifier.
6. **Improve deduplication and refresh behavior.** The database has 1,766 source observations and 1,575 canonical jobs. Review cross-source matches, and add incremental refresh/closure handling so repeated runs update existing jobs without losing source attribution.
7. **Make long runs resumable.** Persist per-page and per-board checkpoints and resume after transient failures, avoiding a full regional rescan after interruption.

## Limits of this run

- This is a bounded sample, not exhaustive coverage of each region.
- No verified Teamtailor feed was found from the Arbeitnow sample.
- OPUS-MT translations were unavailable, so affected English title fields remain pending while original titles are retained.
- Accuracy against human labels remains unmeasured.
