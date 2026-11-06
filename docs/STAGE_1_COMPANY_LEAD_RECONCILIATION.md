# Legacy Company Lead Reconciliation

Read-only comparison of the legacy DOCX directory, legacy posting company names, and the v2 normalized company leads. Company-name normalization is a lead grouping rule, not proof that two brands are the same legal entity.

## Counts

- DOCX directory rows: **5875**; stated legacy postings: **31,018**.
- Directory exact distinct display names: **5,873**; directory distinct normalized keys: **5,810**.
- Directory rows with empty normalized keys: **0**.
- Directory names matching the conservative placeholder screen: **0**. The screen flags only exact placeholders (Unknown, Confidential, Undisclosed, N/A, None, Not provided, Anonymous, Stealth, Various, Multiple companies); these are not automatically dropped.
- Directory normalization merge clusters: **62** clusters covering **125** distinct display names; the complete list is `data/reference/legacy_company_name_merges_v2.csv`.
- Legacy jobs table distinct nonblank company names: **5,873**; normalized company keys: **5,810**; blank names: **0**.
- Legacy normalized-key overlap with the directory: **5,810**; directory-only keys: **0**; legacy-only keys: **0**.
- Legacy names matching the conservative placeholder screen: **0**. The v2 miner excludes only names whose normalized key is empty; it does not silently discard placeholder-looking names.

## Why 5,810 leads versus 5,875 directory rows

The 5,810 v2 company rows were derived from distinct normalized names in the legacy jobs table, not copied one-for-one from the company directory. The directory is a report with 5,875 rows, including repeated display strings and variants collapsed by accent/punctuation/legal-suffix normalization. The jobs table has a different observed company-name set. Blank/punctuation-only names normalize to an empty key and are excluded; placeholder-looking names are retained pending review. No legacy job postings were copied.

## ATS board lead counts by system

- ashby: **29**
- greenhouse: **38**
- lever: **4**
- personio: **0**
- teamtailor: **0**
- Other systems: **0**
- Total: **71** distinct ATS board identifiers.

These are unverified URL-derived ATS board identifiers from legacy postings. They are discovery leads, not confirmed live boards. Since Personio has fewer than 10 leads, the conditional Stage 2 selection is Greenhouse.

## Merge and junk review limits

The merge CSV lists only directory strings that collapse to the same normalized key. This is a reproducible normalization report; actual company identity merges should be manually reviewed. The conservative junk screen is intentionally narrow and is reported separately so that a placeholder candidate is not silently removed.
