# Stage 3 Africa Pilot Report

Run date: 2026-11-06
Sources: Arbeitnow public API and Greenhouse public Job Board API; Teamtailor public RSS was optional and discovered from the Arbeitnow sample.
Scope: Africa only (UN M49 region 002), maximum 500 source records per feed and 1,000 unique canonical postings overall. Requests used a 10-second timeout and per-host rate limiting of no more than one request per second.
Classification: rules-only; no LLM fallback. Extensions enabled; C5 remains adjacent. M49 groupings are used as published.
Translation: Helsinki-NLP OPUS-MT models were unavailable locally during this run; original titles were preserved and English title fields remain pending where translation was unavailable.

## Collection

arbeitnow: included
teamtailor: no verified feed found in the Arbeitnow sample
- Source records selected: **1**
- Canonical English-key unique postings: **1**
- Arbeitnow: **0**
- Teamtailor RSS: **0**
- Greenhouse: **1**
- Arbeitnow keys also present in ATS feeds: **0**
- U+FFFD title quarantine records: **0**
- HTTP failed URLs after retries: **0**

## Per-language title accuracy

Accuracy against human labels is **pending**: the accompanying 100-title manual sheet has blank reviewer fields and the 300-row golden set is explicitly unverified. The rule-only baseline below is coverage by detected title language, not accuracy:

- en: 1 titles; accuracy pending hand labels

## German text cleanliness

- German-title postings: **0**
- German titles containing U+FFFD in stored rows: **0**
- German descriptions containing U+FFFD: **0**
- German descriptions with common mojibake markers: **0**

## Top 50 Non-Tech titles


## Top 50 Unclassified titles

- Commercial Account Executive  (1)

Exports: `data/exports/stage3_africa_pilot.csv` and `data/exports/stage3_africa_pilot.json`.
Local MT title translations available for hand spot-check: **0** (`data/exports/stage3_africa_pilot_title_translation_review.csv`). The 100-title classification sheet provides manual expected-label fields.
