# Global CS Job Scraping: Final Specification (v2)

Version 2, prepared 5 November 2026 for a coding agent (Codex). It replaces the first specification: the data is re-scraped from scratch for Europe, then the USA, Africa and Asia, using verified sources only, one stage at a time, with every posting classified against a fixed taxonomy built from roadmap.sh.

## 1. Why this is a redo

The project is a final year project on the tech job market and skills demand (Data Science + AI). The first scrape ran without a role list, a skills list, a geographic plan or a source check. The result is too messy to build on, especially the German postings.

The redo starts from scratch. The old PostgreSQL tables and exports stay untouched as an archive called `legacy_v1`. They are used only as leads (section 5.3) and are never merged into the new tables.

| Dataset (first scrape, 5 Nov 2026) | Tech | Non-Tech | Tech with populated skills |
|---|---:|---:|---:|
| PostgreSQL | 18,449 | 12,569 | 100% |
| CSV and JSON exports | 15,004 | 11,144 | 100% |

The file `scraped_companies.docx` lists 5,875 company names with their posting counts, which sum to 31,018 postings. What it shows:

- About 44% of the names carry German legal suffixes (GmbH, AG, KG and similar), and 56% of companies have exactly one posting.
- The largest companies are US career-page employers (Databricks 1,440, Stripe 1,356, OpenAI 900, Cloudflare 824, Anthropic 648).
- Names are noisy: the same company appears under variants (for example `1KOMMA5°`, `1KOMMA5˚`, `1Komma5Grad`) and some entries are junk identifiers.
- Africa and Asia are barely represented.

### What the redo fixes

1. Roles were labelled tech or non-tech by company. They are now classified per posting against a fixed taxonomy.
2. There was no skills reference. The roadmap.sh skills vocabulary is now the reference.
3. The mix was skewed to US big tech and German small companies. Coverage is now planned by region.
4. Duplicates and company-name variants were not handled.
5. Source, country and dates were not recorded per posting.
6. Sources were not checked. Only verified sources are used now.
7. There was no coverage measure or stopping rule.

## 2. Decisions already made

- **Fresh start:** scrape again from zero. Do not reuse old postings as data.
- **Geography:** Europe as a whole continent first (not Germany only), then the USA, then Africa, then Asia. Give every posting a country (ISO 3166 alpha-2) and a region (UN M49 scheme). Europe means the M49 region Europe, which includes the UK, Switzerland, Norway and Iceland.
- **Verified sources only:** a source is scraped only when it has a documented API or public feed (section 5). No unverified HTML scraping.
- **Taxonomy:** categories and sub-domains come from the roadmap.sh roles (section 4). Anything that does not fit goes to **Non-Tech** or **Unclassified**, and the owner decides about it later.
- **Excluded:** LinkedIn, Indeed and Glassdoor.
- **Time:** a baseline run now, then weekly runs until 5 Nov 2027. Live sites cannot be scraped backwards in time.
- **Stopping rule:** coverage targets per region and category, not exhaustion.
- **Step by step:** work in stages (section 6) and stop for the owner's approval after each one.

## 3. Reference files

Place these in `data/reference/`. The version 1 files (`cs_job_taxonomy.json`, `scrape_sources.csv`, `skills_vocabulary.csv`) are obsolete: ignore them.

| File | Contents |
|---|---|
| `cs_job_taxonomy_v2.json` | 7 categories and 43 sub-domains with tier, roadmap.sh source, title aliases and starter aliases in German, French, Spanish, Portuguese, Italian and Dutch; the Non-Tech and Unclassified fallbacks; the classification rules. |
| `skills_vocabulary_v2.csv` | 8,493 skill and topic terms from 97 roadmap.sh roadmaps. 3,488 are linked to at least one sub-domain through the `subdomain_ids` column. |
| `scrape_sources_v2.csv` | 62 sources with verification status, access method, evidence, limits and the stage that enables them: 18 VERIFIED, 9 RECHECK, 27 DISABLED_UNVERIFIED, 8 EXCLUDED. |
| `scraped_companies.docx` | The old company directory (read-only evidence of what the first run covered). |

## 4. Taxonomy (built from roadmap.sh)

Every posting gets one category and one sub-domain from this list, or one of two fallbacks. A star marks an extension sub-domain that roadmap.sh does not have but that is common in real job postings.

| Category | Tier | Sub-domains |
|---|---|---|
| C1 Software Development | core | Frontend Developer; Backend Developer; Full Stack Developer; Android Developer; iOS Developer; Cross-platform Mobile Developer; Game Developer; Server-side Game Developer; Blockchain Developer; Software Architect; QA / Test Engineer; Forward Deployed Engineer; AR/VR Developer*; ERP / CRM Developer*; Systems / Low-level Engineer*; Mainframe / Legacy Developer* |
| C2 Data & AI | core | Data Analyst; BI Analyst; Data Engineer; Data Scientist; Machine Learning Engineer; MLOps Engineer; AI Engineer; Inference Engineer |
| C3 Cloud, DevOps & Infrastructure | core | DevOps Engineer; Cloud Engineer / Architect; Network Engineer; Database Administrator; Site Reliability Engineer*; Systems Administrator* |
| C4 Cybersecurity | core | Cyber Security Specialist; DevSecOps Engineer; AI Red Teamer; SOC Analyst*; Penetration Tester* |
| C5 Product, Design & Management | adjacent | Product Manager; UX / Product Designer; Engineering Manager; Developer Relations; Technical Writer |
| C6 IT Operations & Support | core | IT Support / Help Desk* |
| C7 Embedded, Hardware & Robotics | core | Embedded / Firmware Engineer*; Robotics Software Engineer* |
| Non-Tech | n/a | Clearly outside computer science and IT (sales, HR, legal, creative, retail, healthcare, finance, operations, SEO) |
| Unclassified | n/a | Ambiguous, unparseable or low-confidence titles |

Rules:

- **Fixed vocabulary.** Never invent a category, sub-domain or normalized role. A title that does not fit goes to Non-Tech or Unclassified with a reason code, and the owner decides later.
- **Tech flag.** `is_tech_role` is true for every row in C1 to C7 and false for Non-Tech and Unclassified. There are no other exceptions.
- **Tier and source.** Keep `tier` (core or adjacent) and the sub-domain's `source` (roadmap or extension) on each row so analyses can be restricted to core roadmap.sh roles.
- **Extension toggle.** Config `include_extensions` defaults to true. When false, rows that match an extension sub-domain go to Unclassified with reason code `extension_disabled`.
- **Known weakness.** roadmap.sh describes learning paths, not job titles. The aliases are a first draft that must be checked against real postings, and the vocabulary contains generic words such as introduction or testing that must be pruned against real posting text (section 7).

## 5. Sources and verification

### 5.1 Verification gate

Every source in `scrape_sources_v2.csv` has a status. Only the stage and status rules below allow a request to be made.

| Status | Meaning | What Codex may do |
|---|---|---|
| VERIFIED | Vendor or official documentation found and a live test succeeded in October 2026 | Scrape from its enable stage |
| RECHECK | Believed official but not re-verified | First find the official documentation and terms, save the evidence (URL, date, decision) in the `sources` table, then use it only if allowed |
| DISABLED_UNVERIFIED | HTML-only board with no documented API or permission found | Do not scrape. Codex may write a robots.txt and terms report so the owner can decide per source |
| EXCLUDED | LinkedIn, Indeed, Glassdoor and undocumented ATS endpoints | Never, unless the owner approves a specific source |

### 5.2 Verified sources

| Group | Sources | Notes |
|---|---|---|
| Career-page systems (public, no key) | Greenhouse, Lever (EU host api.eu.lever.co), Ashby, SmartRecruiters, Workable, Recruitee, Personio, Teamtailor RSS, Pinpoint, Gem, Polymer | One call returns one company's published jobs. No endpoint lists the companies, so board identifiers must be discovered (5.3). Personio feeds work only when the employer activated them. |
| Aggregator and government APIs (key or registration) | Adzuna, Jooble, Careerjet, Reed (UK), USAJOBS (US federal only), Arbeitnow (no key) | Adzuna covers gb, de, fr, nl, at, be, ch, es, it, pl, us, ca, za, in, sg and more (confirm list). Arbeitnow is mostly built from the same career-page systems, so expect heavy overlap. |
| Remote | Remotive | Tiny public feed (about 17 jobs in September 2026), at most 4 fetches a day, attribution required. Low value. |

RECHECK sources: Remote OK, We Work Remotely, Himalayas, Hacker News Who is hiring, France Travail, EURES, MyCareersFuture (Singapore), The Muse, ReliefWeb.

The full list with endpoints, evidence and limits is in `scrape_sources_v2.csv`.

### 5.3 Using the old data as leads

The company directory has names and counts only. To find where each company posts:

1. Mine the `legacy_v1` database for job URLs and source fields. URLs such as boards.greenhouse.io/acme or jobs.lever.co/acme reveal the system and the board identifier directly.
2. For companies without a usable URL, try the identifier a company would most likely use only as a fallback, and accept a hit only when the company name returned by the feed matches. Throttle these probes and log hits and misses in an `ats_boards` table.
3. Discover new boards from public lists of companies on the same systems, and from company career URLs found through verified aggregators.
4. Find out which old source produced the German postings (check legacy URLs) and report it, so the same mistake is not repeated.

### 5.4 Limits and gaps

- Aggregator APIs (Adzuna, Jooble, Careerjet) are built to display search results. Read each one's terms and record whether storing results for academic research is allowed. If unclear, mark the source needs_owner_decision and do not store its results yet.
- Reported free-tier limits (confirm each before planning): Adzuna about 25 calls per minute and 250 per day; Jooble about 500 requests on a free key; Remotive 4 fetches a day.
- Official APIs cover Africa and Asia thinly: Adzuna (South Africa, India, Singapore), Jooble and Careerjet (check which locales), plus employers on the career-page systems above. The main local boards (BrighterMonday, Jobberman, Careers24, MyJobMag, Naukri, JobStreet and others) have no documented API that was found, so they are disabled. If Africa or Asia cannot reach the coverage targets, report the gap and let the owner choose: ask boards for permission, or approve a specific board after a robots.txt and terms report.

## 6. Stages

Work one stage at a time. At the end of each stage write a short report and stop until the owner approves the next stage.

1. **Stage 0, plan (no scraping).** Inspect the repo, database and scrapers. Reuse what works. Write a short plan with assumptions and list the API keys needed.
2. **Stage 1, foundation (no job scraping).** Create the new schema. Load the taxonomy, vocabulary and source registry. Build the classifier (section 8) with unit tests and a golden set of at least 300 real titles taken from the legacy archive. Mine legacy leads (5.3). Run the verification gate for the Europe sources.
3. **Stage 2, Europe pilot.** Enable at most 3 VERIFIED sources of different types (for example one career-page system, Adzuna for a few European countries, and Arbeitnow). Cap at about 1,000 postings and run the full pipeline. Report: duplicate rate, classification accuracy on 200 sampled rows, the share and top 50 titles of Non-Tech and Unclassified, error log, and a check of German data quality.
4. **Stage 3, Europe full.** Enable the remaining Europe-suitable VERIFIED sources (career-page discovery across the systems above, Adzuna European countries, Reed, Arbeitnow, Teamtailor). Run until the coverage targets or saturation (section 11).
5. **Stage 4, USA.** Career-page systems for US employers, Adzuna (us, ca), USAJOBS, then any RECHECK source that passes the gate.
6. **Stage 5, Africa.** Adzuna (za), Jooble and Careerjet where locales exist, African employers on the career-page systems, ReliefWeb if verified, remote sources. Report the coverage gap.
7. **Stage 6, Asia.** Adzuna (in, sg), Jooble and Careerjet where locales exist, Asian employers on the career-page systems (SmartRecruiters has many), MyCareersFuture if verified. Report the coverage gap.
8. **Stage 7, schedule.** Weekly runs until 5 Nov 2027, weekly coverage report, closed-posting detection.

Oceania, Latin America and the Middle East are out of scope. Keep their postings if a verified source returns them, but do not chase them, and report the counts.

## 7. Per-posting pipeline

For every posting, in this order: fetch, store the raw payload, normalise, deduplicate, extract skills, classify (section 8), write. Classification runs inline while scraping.

- **Company names:** repair encoding damage, lowercase, strip punctuation, symbols and diacritics, and collapse legal suffixes (GmbH, AG, SE, KG, UG, Inc, Ltd, LLC, PLC, Pty, SA, SAS, BV, NV, AB, AS, Oy) into a normalised key. Keep the display name. Merge variants such as `1KOMMA5°` and `1Komma5Grad`. Flag names that look like identifiers (long digit or hex strings).
- **Location:** parse country (ISO 3166 alpha-2), region (UN M49), city, and remote or hybrid flags. For remote postings keep the countries the job allows when the source says so.
- **Dates:** store `posted_at` as the source gives it, plus our own `first_seen` and `last_seen`.
- **Duplicates:** the same job from several sources is one posting. Dedupe key: normalised company + normalised title + country + posted month, with a fuzzy fallback on the first 300 characters of the description. Keep every (source, source_job_id) row linked to one canonical posting. Where two sources give the same URL, treat them as one.
- **Raw payload:** store the original JSON, XML or HTML for every posting so results can be reproduced.
- **Skills extraction:** load `skills_vocabulary_v2.csv` and build matching terms from the label plus a hand-made synonym map (js = javascript, k8s = kubernetes, postgres = postgresql, node = node.js, golang = go, ml = machine learning, gcp = google cloud). Match whole words, case-insensitive, over title and description. Ambiguous names (Go, R, C, Swift, Rust, Spring, Express, Flutter) count only in a technical context. After the first full run, move terms found in fewer than 20 postings or in more than 60% of postings to a review list. Output `skills_vocabulary_pruned.csv` and the discard list. Also keep any skills the source supplies, labelled by origin.

### 7.1 Encoding and language

**Encoding (done at capture, before any cleaning)**

- Work with bytes first. Decode raw response bytes to text using, in order: the charset in the Content-Type header, the XML declaration or HTML meta charset, then charset detection (charset-normalizer). JSON is UTF-8 by specification. Older Asian sites may use Shift_JIS, EUC-JP, GBK or Big5, so never assume UTF-8 blindly.
- Beware the Python requests library: for text responses with no charset it falls back to ISO-8859-1, which creates mojibake. Set the encoding explicitly from the rules above. Pass bytes, not decoded text, to XML and HTML parsers (Personio and Teamtailor feeds declare their own encoding).
- Keep the raw bytes (or raw file) and the detected charset in `source_charset`, so a wrong decode can be redone without scraping again.
- Normalise decoded text to Unicode NFC. Remove NUL characters (PostgreSQL cannot store them), other control characters and zero-width characters, and turn non-breaking spaces into normal spaces.
- Encode as UTF-8 everywhere on save: PostgreSQL database encoding UTF8 (check `SHOW server_encoding`), text files opened with encoding utf-8, CSV exports written as utf-8-sig so Excel shows accents correctly, and JSON written with ensure_ascii false.
- Safety net: some sources store text that is already corrupted (for example Ã¤ instead of ä). Decoding correctly cannot fix that, so the mojibake repair in 8.2 stays, and the pipeline logs how often it changes a title.

**Language (the data must be readable in English)**

- Never overwrite the original. Keep the original text and add English fields.
- Detect the language per posting (`title_language`, `description_language`, `language_confidence`) from the description and the source's country or locale. Short titles alone are unreliable.
- Classification uses the multilingual aliases (8.9), so `category`, `sub_domain` and `normalized_role` are already English.
- Add `clean_title_en`: the original when the title is already English, otherwise an English translation of the title only, made by the LLM, cached by unique title, with `translation_method` recorded. If translation fails or looks wrong, fall back to the seniority plus the English `normalized_role`.
- Do not translate descriptions in the pipeline. Skills extraction runs on the original text with the English vocabulary. If English descriptions are ever needed for text analysis, translate a sample later.
- Deduplicate across languages with an English key: company + `normalized_role` + city.
- Add `clean_title_en`, `title_language` and `translation_method` to the output in 8.10.
- Checks: a test fixture of at least 50 titles with accents, umlauts, CJK characters and mojibake; zero replacement characters (U+FFFD) in stored titles; 100 translated titles spot-checked per language at each stage.

## 8. Title cleaning and classification

### 8.1 When it runs

- Inline during scraping, after skills extraction and before the database write.
- `raw_title` is never changed. Store the classifier output next to it.
- Store `classifier_version` and `taxonomy_version` on every row. Provide a re-classify job that reprocesses stored rows when rules or taxonomy change. Never fix rows by hand.

### 8.2 Cleaning (`clean_title`)

1. Encoding is fixed at capture (section 7.1), so this step is only a safety net: repair any remaining mojibake (for example with the `ftfy` library), normalise to NFC, collapse whitespace.
2. Strip European gender and diversity markers: `(m/w/d)`, `(m/f/d)`, `(w/m/d)`, `m|w|d`, `(m/w/đ)`, `(m/w/i)`, `(f/m/x)`, and `:in`, `*in` suffixes (`Applikationsmanager:in` becomes `Applikationsmanager`).
3. Strip regional employment-status tags such as `【正社員】` and `[中途]`, and similar bracketed Japanese, Chinese and Korean tags.
4. Strip work-mode and location suffixes: `(Remote)`, `[Hybrid]`, `(Berlin / Germany)`, `- Remote`, `| Nairobi`.
5. Keep core role words and domain specialisations (`Staff Software Engineer, Web3` keeps Web3).
6. Leave seniority words in `clean_title`. Extract them separately (8.3).

### 8.3 Seniority (`seniority`)

- Extract only what is stated. Allowed values: `Intern / Werkstudent / Praktikum`, `Junior`, `Mid-Level`, `Senior`, `Staff`, `Principal`, `Lead`, `Head / Director`, or a Roman numeral level (`II`, `III`).
- If nothing is stated, use `Mid/Unspecified`. Never infer seniority and never alter the core title to fit a level.
- Recognise equivalents in other languages (Werkstudent, Praktikant, Berufseinsteiger, Stagiaire, Pasante and similar).

### 8.4 Assigning category and sub-domain

1. Match `clean_title` against each sub-domain's `title_aliases` and `title_aliases_i18n` (case-insensitive, whole words, hyphens normalised). The longest alias wins. If two sub-domains tie, use the skills fallback (8.7).
2. Take the category of the winning sub-domain.
3. With no title match, use the skills fallback.
4. If still undecided: **Non-Tech** when the role is clearly outside CS and IT (nurse, driver, accountant, sales representative, recruiter, lawyer), otherwise **Unclassified**.
5. Generic titles are not guessed: `Software Engineer` maps to Full Stack Developer; `Engineer`, `Consultant`, `Analyst` or `Fachinformatiker` alone go to Unclassified unless the skills decide.

### 8.5 Role normalisation (`normalized_role`, `domain_specialization`)

- Use the sub-domain's `normalized_roles` value (for Full Stack Developer, `Software Engineer` for generic software engineer titles, otherwise `Full Stack Developer`).
- A secondary domain suffix goes to `domain_specialization`: `Staff Software Engineer, Web3` gives `normalized_role = Software Engineer` and `domain_specialization = Web3`. No suffix gives null.
- For Non-Tech and Unclassified rows, `normalized_role` is the cleaned core title as written.

### 8.6 Tech flag (`is_tech_role`)

- True when the category is C1 to C7. False for Non-Tech and Unclassified. No other exceptions.

### 8.7 Skills fallback

- Use skills only when the title is ambiguous: a tie, a generic title, or no match.
- Count extracted skills per sub-domain using `subdomain_ids` in the vocabulary. Choose a sub-domain only if it has at least 3 matching skills and at least twice as many as the next one. Otherwise Unclassified (reason code `conflicting_skills` or `ambiguous_title`).
- Hardware or mechanical skills (CAD, SolidWorks, PLC and similar) with no CS skills go to Non-Tech.
- Skills never override a clear title match and never create a new category.

### 8.8 Confidence and review queue

- `HIGH` (0.85 or more): one clear alias match, no conflicting skills.
- `MEDIUM` (0.70 to 0.84): partial match or a skills-assisted decision.
- `LOW` (below 0.70): category Unclassified, reason code `low_confidence`.
- Every Non-Tech and Unclassified row needs a `reason_code` from: `no_title_match`, `ambiguous_title`, `conflicting_skills`, `low_confidence`, `clearly_non_cs`, `unparseable_text`, `extension_disabled`, `non_english_unmatched`.
- Write these rows to a `classification_review` table. The weekly report lists the 50 most frequent unmatched titles with counts, so the owner can decide whether to extend the taxonomy. Taxonomy changes are versioned and trigger the re-classify job.

### 8.9 Languages

Europe is multilingual, so titles will not all be English. The taxonomy has starter aliases in German, French, Spanish, Portuguese, Italian and Dutch. Extend them from real samples, keep each alias tagged with its language, and keep the lists in the taxonomy file rather than in code. A title with no match in any language goes to the LLM fallback (8.11), then to Unclassified with reason code `non_english_unmatched` if still unsure.

### 8.10 Output

Each posting gets these fields:

```json
{
  "raw_title": "string",
  "clean_title": "string",
  "clean_title_en": "English version, same as clean_title when already English",
  "title_language": "ISO 639-1 code",
  "translation_method": "original_english | llm | fallback_role",
  "normalized_role": "string",
  "seniority": "string",
  "domain_specialization": "string or null",
  "category": "string",
  "sub_domain": "string",
  "is_tech_role": true,
  "confidence_flag": "HIGH | MEDIUM | LOW",
  "category_id": "C1",
  "sub_domain_id": "S02",
  "tier": "core | adjacent | null",
  "role_confidence": 0.92,
  "reason_code": "null for taxonomy rows, required for Non-Tech and Unclassified",
  "classifier_version": "string",
  "taxonomy_version": "2.0"
}
```

### 8.11 Implementation

1. **Rules first:** the cleaning, seniority and alias matching above, then the skills fallback. This should settle most postings cheaply and the same way every time.
2. **LLM fallback second:** send only ambiguous or unmatched titles to an LLM using the prompt in Appendix A. Validate the JSON against 8.10, reject any value outside the taxonomy, retry once, and cache results by a hash of title plus skills.
3. **Check it:** build a golden test set of at least 300 real titles covering English, German, French and Asian formats, encoding damage, gender markers, seniority words and ambiguous roles. Add unit tests for every cleaning rule. Review 200 sampled rows per stage and report accuracy per category and the failing patterns.

## 9. Data schema (starting point)

Keep these concepts and adjust names to the existing database.

- `sources(id, name, type, region_scope, access_method, verification_status, evidence_url, terms_decision, checked_on, notes)`
- `companies(id, display_name, normalised_key, country, website, ats_type, ats_identifier)`
- `ats_boards(id, company_id, ats_type, identifier, discovered_from, verified_name_match, last_status)`
- `postings(id, canonical_id, source_id, source_job_id, company_id, raw_title, clean_title, clean_title_en, title_language, translation_method, description, description_language, source_charset, url, posted_at, first_seen, last_seen, closed_at, country, region, city, is_remote, employment_type, seniority, normalized_role, domain_specialization, category_id, sub_domain_id, is_tech_role, tier, role_confidence, confidence_flag, reason_code, salary_min, salary_max, salary_currency, raw_payload, scrape_run_id, classifier_version, taxonomy_version)`
- `categories`, `sub_domains` loaded from `cs_job_taxonomy_v2.json`; `skills` loaded from the vocabulary
- `posting_skills(posting_id, skill_id, origin)` where origin is extracted or source
- `classification_review(posting_id, reason_code, created_at, owner_decision)`
- `scrape_runs(id, started_at, finished_at, source_id, stage, postings_seen, postings_new, errors)`

Salary fields are optional and stored only when the source publishes them. Respect flags such as compensation_visible=false.

## 10. Collection rules

1. Use only sources whose status allows it (section 5.1). Read each source's documentation and terms and record the decision.
2. Rate limit politely: at most one request per second per host, or the documented limit if slower. Back off on 429 and 5xx errors and retry with delays.
3. Send an honest User-Agent naming the project with a contact email. USAJOBS requires the registered email in the User-Agent.
4. Cache responses so a rerun does not download unchanged data.
5. Keep API keys in environment variables. List which sources need a key in the README (Adzuna app id and key, Jooble, Careerjet partner id, Reed, USAJOBS).
6. Keep required attribution (Remotive, Remote OK) and skip any listing flagged as not public, such as Ashby records with isListed false.
7. Do not collect recruiter or applicant personal data and do not store contact emails or phone numbers from postings.
8. Never bypass logins, CAPTCHAs or bot protection. If a source blocks access, mark it blocked and move on.
9. Log per source: requests, successes, failures, blocked responses.

## 11. Coverage, time window and stopping rule

- **Time window:** baseline run now, then weekly runs until 5 Nov 2027. Live sites show a posting for roughly 30 to 60 days, so history cannot be scraped backwards. Treat any later historical data as a separate, labelled source.
- **Closing postings:** mark a posting closed only after it is missing from two consecutive complete, successful snapshots. A failed or partial run never closes jobs.
- **Coverage targets:** count de-duplicated postings per region and category (C1 to C4 first). Default target: at least 300 per cell, as a rule of thumb for stable skill percentages. Make it a config value.
- **Saturation:** when a newly added source brings fewer than 10% new postings to a cell, stop adding sources for that cell.
- **Balance:** cap large cells (for example US big tech) by sampling so one region does not dominate. Spend effort on the thinnest cells.
- **Weekly report:** cells below and above target, new versus repeat postings, yield per source, and the Non-Tech and Unclassified review list.

## 12. Acceptance criteria

- Every posting has source, country, region, `first_seen`, `last_seen`, category, sub-domain (or Non-Tech or Unclassified), `is_tech_role`, confidence and, where needed, a reason code.
- Only sources with status VERIFIED, or RECHECK sources that passed the gate with evidence saved, were used.
- Duplicate rate under 2% in a random sample of 500 postings.
- Classification accuracy of at least 85% on 200 sampled core-category rows, reported per category with the failing patterns.
- A company-name merge report and a pruned skills vocabulary with its discard list.
- A coverage report by region and category with targets, gaps and a plain statement of which regions fall short and why.
- The German postings in the Stage 2 pilot are clean: no encoding damage, no gender markers or location suffixes left in `clean_title`.
- A README describing every adapter, the config, the keys, the stages and how to re-run classification.

## 13. Open questions for Codex to flag instead of guessing

- Which old source produced the German postings.
- Which API keys the owner already has.
- Where the weekly schedule will run (local machine, server or cloud).
- Keep the extension sub-domains and C5 in the final analysis, or send them to Unclassified with `include_extensions` false.
- Edge countries under M49: Russia, Belarus, Turkey, Cyprus, Georgia, Armenia, Azerbaijan, Kazakhstan.
- Whether Adzuna, Jooble and Careerjet terms allow storing results for academic research.
- If verified sources cannot reach the targets for Africa or Asia: ask boards for permission, approve a specific board after a terms report, or accept the gap.

## Appendix A. LLM fallback prompt

Fill the placeholders per posting. Build `{taxonomy_list}` at run time from `cs_job_taxonomy_v2.json` (one line per category with its id, name and its sub-domains with ids). Return only the JSON object.

```
You classify one scraped job posting into a fixed computer science job taxonomy.

TAXONOMY (the only allowed values):
{taxonomy_list}
Fallbacks: Non-Tech (clearly outside CS and IT) and Unclassified (ambiguous, unparseable or low confidence).

INSTRUCTIONS
1. clean_title: repair encoding damage; strip European gender markers such as (m/w/d), (m/f/d), m|w|d, (m/w/i) and :in suffixes; strip Asian employment tags such as 【正社員】 and [中途]; strip work-mode and location suffixes such as (Remote), [Hybrid], (Berlin / Germany). Keep core role words and specialisations.
2. seniority: only what is stated: Intern / Werkstudent / Praktikum, Junior, Mid-Level, Senior, Staff, Principal, Lead, Head / Director, or a Roman numeral such as II or III. Otherwise Mid/Unspecified. Never infer it.
3. category and sub_domain: choose exactly one sub-domain from the taxonomy and use its category. If none fits, use Non-Tech when clearly outside CS and IT, otherwise Unclassified. Never invent categories or sub-domains.
4. normalized_role: the sub-domain's normalized role. A secondary suffix such as Web3 goes to domain_specialization (else null). For Non-Tech and Unclassified use the cleaned core title.
5. is_tech_role: true when the category is C1 to C7, false for Non-Tech and Unclassified.
6. Skills: use them only when the title is ambiguous, to choose between existing sub-domains. Never override a clear title.
7. confidence_flag: HIGH at 0.85 or more, MEDIUM at 0.70 to 0.84, LOW below 0.70. LOW means Unclassified.
8. reason_code: required for Non-Tech and Unclassified, one of no_title_match, ambiguous_title, conflicting_skills, low_confidence, clearly_non_cs, unparseable_text, non_english_unmatched. Otherwise null.

INPUT
Raw Title: {raw_title}
Skills: {skills}

OUTPUT: only a JSON object with raw_title, clean_title, normalized_role, seniority, domain_specialization, category, sub_domain, category_id, sub_domain_id, is_tech_role, confidence_flag, reason_code.
```
