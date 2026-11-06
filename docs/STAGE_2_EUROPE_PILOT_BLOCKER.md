# Stage 2 Europe Pilot — Historical Execution Blocker

**Status:** Resolved on 2026-11-06. This note records the blockers before the successful Europe run; current totals and follow-up work are in `MASS_SCRAPE_SUMMARY.md`.

## Gates completed

- Official UN M49 mapping downloaded from the [UN Statistics Division M49 table](https://unstats.un.org/unsd/methodology/m49/overview), using the approved plain project User-Agent. The file contains 248 ISO alpha-2 mappings. Unit checks return Germany `150` (Europe), USA `019` (Americas per M49), Kenya `002` (Africa), and Japan `142` (Asia).
- Legacy company and board leads are reconciled in `STAGE_1_COMPANY_LEAD_RECONCILIATION.md`. Personio has 0 board leads, so Greenhouse is the third approved pilot source.
- `source_terms_decisions_v2.csv` overrides the historical registry status. Adzuna, Jooble, Careerjet, Reed, Remotive, France Travail, and EURES are explicitly blocked and remain disabled in PostgreSQL.
- The local rollback tag `stage1-v2` points to commit `2be4fd6`.
- The pilot runner applies Europe M49 filtering, one request per host per second, 10-second request timeouts, 400 source-record caps, a 1,000 canonical-key cap, contact redaction, quarantine for U+FFFD titles, rules-only classification, extensions enabled, and no LLM fallback.

## Blockers before any job request

1. **OPUS-MT model/runtime unavailable:** The project venv has no `transformers`, `sentencepiece`, or `torch`, and the Hugging Face cache contains no Helsinki-NLP OPUS-MT models. The HF CLI metadata check hung; an HTTPS metadata request to `huggingface.co` timed out during TLS handshake. I stopped the incomplete package install and did not use a mirror. The runner now preflights all eight language-to-English models locally before creating the HTTP client, so it cannot start scraping without them.
2. **Project contact not present in this execution shell:** `CSJOBS_CONTACT_EMAIL` was not set when checked. The pilot runner requires that dedicated project address for its User-Agent before it can make job-feed requests. It never reads `USAJOBS_EMAIL`. The M49 fetch used the expressly approved plain project User-Agent and did not use an email.

## Status at the time of the blocker

- `techjobs_v2.csjobs.postings`: **0**; the legacy archive remains untouched.
- Pilot request count: **0** for Arbeitnow, Teamtailor, and Greenhouse.
- Translation and classification accuracy: not measured. The 100-title review CSV has blank human-label fields, and its machine expectations are marked unverified. Per-language accuracy will be computed against returned hand labels.
- German cleanliness, Arbeitnow/ATS overlap, U+FFFD quarantine count, and top Non-Tech/Unclassified titles: not measurable until the pilot runs.

## Original resume condition

Make the public Helsinki-NLP model files available in the local Hugging Face cache for `opus-mt-de-en`, `opus-mt-fr-en`, `opus-mt-es-en`, `opus-mt-pt-en`, `opus-mt-it-en`, `opus-mt-nl-en`, `opus-mt-ja-en`, and `opus-mt-zh-en`, and set `CSJOBS_CONTACT_EMAIL` in the execution shell. Then rerun `scripts/run_stage2_europe_pilot.py`. The first action will be local model preflight; job requests begin only after all models pass.
