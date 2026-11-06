# Stage 1 Report — v2 Dataset Foundation

**Date:** 6 November 2026
**Status:** Stage 1 complete; M49 and company/ATS lead conditions are satisfied; Stage 2 is approved within the user-defined pilot scope.
**Collection:** No job postings were requested, written, or merged from legacy data.

## Implemented and verified

- Copied the provided v2 specification, taxonomy, skill vocabulary, and source registry into `docs/` and `data/reference/`; hashes matched the supplied files.
- Created and seeded the isolated UTF8 `techjobs_v2` database and `csjobs` schema. Current counts: 7 categories, 43 sub-domains, 8,493 skill vocabulary rows, 62 sources, 19 source evidence rows, 5,810 company leads, and 71 ATS board leads. There are **0 postings, 0 raw payloads, and 0 posting-skill links**. All sources remain disabled.
- Implemented byte-first charset selection, raw-byte retention, Unicode NFC/control cleanup, mojibake repair logging, language cues, title cleaning, seniority parsing, taxonomy alias matching, conservative skills fallback, title translation cache/LLM validation hooks, cross-language canonicalization, and deduplication helpers.
- Generated a golden set of 300 unique legacy titles. Its expected labels come from the project's own deterministic unique-longest-taxonomy-alias rules; they are **unverified machine expectations, not ground truth**. A separate stratified 100-title hand-label CSV covers expected categories C1-C7, Non-Tech, and Unclassified over detected English, German, French, Spanish, Portuguese, Italian, Dutch, Japanese, and Chinese title strata. Legacy data was used only for title/company/ATS leads; no legacy posting rows were written to v2.
- Added U+FFFD title rejection so corrupted text is quarantined instead of stored. The loaded taxonomy currently has no aliases containing U+FFFD; the source files remain byte-for-byte unchanged.
- Downloaded the official UN M49 table using a plain project User-Agent. `un_m49_countries.csv` contains 248 ISO alpha-2 mappings; region lookup returns Europe `150` for Germany, Americas `019` for the USA, Africa `002` for Kenya, and Asia `142` for Japan. M49 groupings are stored as published, including edge cases.
- Official access/terms checks are recorded in `docs/STAGE_1_SOURCE_VERIFICATION.md` and `data/reference/source_terms_decisions_v2.csv`. Lead reconciliation is in `docs/STAGE_1_COMPANY_LEAD_RECONCILIATION.md`: no Personio boards were found, so the approved pilot is Arbeitnow + Teamtailor RSS + Greenhouse, with source caps below.

## Test result

`pytest tests/v2 -q --tb=short`: **49 passed**, including M49 lookups for Europe, USA (M49 Americas), Africa, and Asia.

## Open gates

1. **Terms decisions:** Adzuna, Jooble, Careerjet, Reed, Remotive, France Travail, and EURES remain blocked as specified in the authoritative terms ledger. The initializer now takes current eligibility from `source_terms_decisions_v2.csv`, not the historical registry status, and leaves every source disabled.
2. **Translation:** The pilot will use local Helsinki-NLP OPUS-MT models; model installation and spot checks are part of Stage 2. Classification will run rules-only with no LLM fallback.

## Requested decision

`source_terms_decisions_v2.csv` is authoritative over the original source registry for eligibility. The accepted taxonomy decisions are `include_extensions=true`, keep C5 adjacent, and use UN M49 groupings as published. Stage 2 is approved: Arbeitnow + Teamtailor RSS + Greenhouse, about 400 per source and about 1,000 total.
