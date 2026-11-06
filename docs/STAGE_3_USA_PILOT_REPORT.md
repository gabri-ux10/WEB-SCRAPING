# Stage 3 USA Pilot Report

Run date: 2026-11-06
Sources: Arbeitnow public API and Greenhouse public Job Board API; Teamtailor public RSS was optional and discovered from the Arbeitnow sample.
Scope: USA only (UN M49 region 019, country US only), maximum 500 source records per feed and 1,000 unique canonical postings overall. Requests used a 10-second timeout and per-host rate limiting of no more than one request per second.
Classification: rules-only; no LLM fallback. Extensions enabled; C5 remains adjacent. M49 groupings are used as published.
Translation: Helsinki-NLP OPUS-MT models were unavailable locally during this run; original titles were preserved and English title fields remain pending where translation was unavailable.

## Collection

arbeitnow: included
teamtailor: no verified feed found in the Arbeitnow sample
- Source records selected: **501**
- Canonical English-key unique postings: **416**
- Arbeitnow: **1**
- Teamtailor RSS: **0**
- Greenhouse: **500**
- Arbeitnow keys also present in ATS feeds: **0**
- U+FFFD title quarantine records: **0**
- HTTP failed URLs after retries: **0**

## Per-language title accuracy

Accuracy against human labels is **pending**: the accompanying 100-title manual sheet has blank reviewer fields and the 300-row golden set is explicitly unverified. The rule-only baseline below is coverage by detected title language, not accuracy:

- en: 501 titles; accuracy pending hand labels

## German text cleanliness

- German-title postings: **0**
- German titles containing U+FFFD in stored rows: **0**
- German descriptions containing U+FFFD: **0**
- German descriptions with common mojibake markers: **0**

## Top 50 Non-Tech titles

- Lifecycle Marketing Manager (2)
- Global Operations Associate (2)
- Capacity Deployment Lead - Data Center Operations (1)
- Content Marketing Manager, SEO & AI Search (1)
- Director, Lifecycle Marketing Operations (1)
- Director of Growth and Acquisition Marketing (1)
- Incident Operations Manager (1)
- Manager, Corporate Finance (1)
- Senior Associate, Strategic Finance (1)
- Senior Associate, Strategic Finance (Growth) (1)
- Senior Operations Manager, Partner Management (1)
- Sr. CRM Operations Manager (1)
- Sr. Growth Product Marketing Manager, Chime Enterprise (1)
- Sr. Instructional Designer, Learning Operations (1)
- Sr. Product Marketing Manager, Lending (1)
- Manager, Enterprise Sales (1)
- Manager, Recruiting - Sales (1)
- Manager, SMB Sales (1)
- Inbound Sales Development Representative (1)
- Inbound Sales Development Representative - New Grad (1)
- Mid-market Sales Manager  (1)
- Operations Associate - Join Our Talent Community (1)
- Operations Solutions Manager (1)
- Operations Specialist - Join Our Talent Community  (1)
- Sales Development Manager (1)
- Sales Development Representative (1)
- Sales Development Representative - New Grad (1)
- Sales Leader (1)
- Senior Financial Analyst, North America Sales & Operations Finance (1)
- Director, Global People Operations & Compliance (1)
- Ecosystem Operations Specialist (1)
- Lead Legal Counsel, Corporate (1)
- Manager, Sales Recruiting (AMER) (1)
- Principal Executive Recruiter (1)
- Principal Product Marketing Manager, Competitive (1)
- Recruiter, R&D (1)
- Recruiter,  Sales (AMER) (1)
- Regional Sales Director, Financial Services - NYC  (1)
- Regional Sales Director, National Security Group (1)
- Senior Ecosystem Operations Manager (1)
- Senior Solutions Architect Operations Manager  (1)
- Staff Professional Services Operations Manager (1)
- Staff Regional Marketing Manager, West (1)
- Tech Operations Specialist (1)
- Future Sales Openings: Account Executive, US |Remote|  (1)
- Manager, Sales Development | United States | Remote (1)
- Marketing Analytics Director  | United States | Remote (1)
- Regional Marketing Associate | East or Central US | Remote (1)
- Regional Sales Director, Commercial, Growth | West| Remote (1)
- Sales Operations Manager | United States | Remote (1)

## Top 50 Unclassified titles

- Enterprise Account Executive (8)
- Enterprise Account Executive  (4)
- Mid Market Account Executive (4)
- Business Control Manager (3)
- Customs Specialist (3)
- Manager, Ocean Freight (3)
- Social Media & Content Manager (3)
- Account Executive  (2)
- Customs Associate (2)
- Manager, Ocean Procurement (2)
- Senior IT Systems Engineer  (2)
- Senior Systems Engineer (Identity and Access) (2)
- Solutions Consultant (2)
- Account Executive- Public Sector (2)
- Growth Program Manager (2)
- Senior Solution Consultant (2)
- Senior SysOps Engineer (2)
- Anthropic Fellows Program, AI Safety & Security (1)
- Anthropic Fellows Program, ML Systems & Reinforcement Learning (1)
- Anthropic Fellows Program, The Anthropic Institute (Economics & Policy) (1)
- Community Engagement Manager, Data Centers (Indiana & Kentucky) (1)
- Community Engagement Manager, Data Centers (Louisiana) (1)
- Community Engagement Manager, Data Centers (Montana & Utah) (1)
- Community Engagement Manager, Data Centers (New York) (1)
- Community Engagement Manager, Data Centers (Texas) (1)
- Community Engagement Manager, Data Centers (Virginia & West Virginia) (1)
- Cyber Evaluations Engineer (1)
- Data Center Architect, CSA (1)
- Data Center Electrical Engineer – Design (1)
- Data Center Mechanical Engineer (1)
- Data Center Power Generation and Microgrids Engineer (1)
- Field Engineer, Data Center Design and Engineering (1)
- Incident Response Manager - Product & Engineering (1)
- Reporting and Controls Lead, Data Center Capacity Delivery (1)
- State and Local Affairs Lead, Midwest  (1)
- State and Local Affairs Lead, West (1)
- Supply Chain Delivery Manager, Data Center Power & Cooling OFE (1)
- Transaction Manager (1)
- Commercial Counsel (1)
- Director, Corporate Strategy (1)
- Director of Communications & Content, Chime Enterprise (1)
- Lead Analyst, Financial Crimes (1)
- Manager, Corporate Communications (1)
- Manager, Product Security (1)
- Program Manager, OMX SOTO (1)
- Senior Associate, Compliance Advisory (1)
- Senior Compensation Partner (1)
- Senior Director, Product and Brand Communications (1)
- Senior Litigation Paralegal (1)
- Senior Manager, Financial Reporting (1)

Exports: `data/exports/stage3_usa_pilot.csv` and `data/exports/stage3_usa_pilot.json`.
Local MT title translations available for hand spot-check: **0** (`data/exports/stage3_usa_pilot_title_translation_review.csv`). The 100-title classification sheet provides manual expected-label fields.
