# Stage 2 Europe Pilot Report

Run date: 2026-11-06
Sources: Arbeitnow public API and Greenhouse public Job Board API; Teamtailor public RSS was optional and discovered from the Arbeitnow sample.
Scope: Europe only (UN M49 region 150), maximum 500 source records per feed and 1,000 unique canonical postings overall. Requests used a 10-second timeout and per-host rate limiting of no more than one request per second.
Classification: rules-only; no LLM fallback. Extensions enabled; C5 remains adjacent. M49 groupings are used as published.
Translation: Helsinki-NLP OPUS-MT models were unavailable locally during this run; original titles were preserved and English title fields remain pending where translation was unavailable.

## Collection

teamtailor: no verified feed found in the Arbeitnow sample
- Source records selected: **977**
- Canonical English-key unique postings: **901**
- Arbeitnow: **500**
- Teamtailor RSS: **0**
- Greenhouse: **477**
- Arbeitnow keys also present in ATS feeds: **1**
- U+FFFD title quarantine records: **0**
- HTTP failed URLs after retries: **0**

## Per-language title accuracy

Accuracy against human labels is **pending**: the accompanying 100-title manual sheet has blank reviewer fields and the 300-row golden set is explicitly unverified. The rule-only baseline below is coverage by detected title language, not accuracy:

- de: 269 titles; accuracy pending hand labels
- en: 393 titles; accuracy pending hand labels
- es: 25 titles; accuracy pending hand labels
- fr: 239 titles; accuracy pending hand labels
- it: 36 titles; accuracy pending hand labels
- nl: 14 titles; accuracy pending hand labels
- pt: 1 titles; accuracy pending hand labels

## German text cleanliness

- German-title postings: **269**
- German titles containing U+FFFD in stored rows: **0**
- German descriptions containing U+FFFD: **0**
- German descriptions with common mojibake markers: **0**

## Top 50 Non-Tech titles

- Global Operations Associate (5)
- Sales Development Representative (5)
- Strategy & Operations Director (2)
- People Operations Working Student (m/f/d) (2)
- Senior Recruiter (2)
- Regional Operations Director-Based in Munich/Berlin (2)
- Sales Engineer - UK (2)
- Senior Sales Engineer - UK (2)
- Accounting and Finance Manager | Paris (1)
- Senior Accountant | Paris (1)
- GTM Recruiter, EMEA (1)
- Chargé de projet Marketing & communication F/H (1)
- Stagiaire Marketing & Communication (H/F) (1)
- Senior Sales Engineer, France (1)
- Werkstudent:in Finance & Accounting (m/f/d) (1)
- Senior Field Operations Manager (1)
- Senior Consultant - Digital Commerce (Retail & CPG) | DACH (1)
- Area Manager Operations (m/w/d) (1)
- Legal Engineer Manager, Germany (1)
- Legal Engineer Manager, Product Specialist, Germany (1)
- Legal Engineer (Transactional or In-house) (1)
- Group Financial Accountant (1)
- Product Marketing Manager, AI Governance (EMEA) (1)
- Field Marketing Lead (1)
- Principal, Global Campaign Operations (1)
- Head of Product Management & Transformation (Risk, Finance & Compliance) (1)
- Head of Investment Fund Operations (1)
- Chief Physician / Head of Urology (1)
- Senior Sales Advisor - Geneva (1)
- Lead Commercial Sales (1)
- Senior HR Project Manager (1)
- Senior Associate, GTM Marketing (1)
- Influencer Marketing Manager (m/f/d) (1)
- Consultant Finance and Digitalization (w/m/d) - Fintech SaaS Scale-Up (1)
- Regional Sales Director-Eastern Europe (1)
- Senior Legal Counsel (1)
- Freelance Campaign Manager, Influencer Marketing, CPG (Europe) - Second European Language Essential (1)
- Partner Sales Director (1)
- CDI - Sales / Account Executive (Paris/ IDF) (1)
- Sales Manager, Startups | New Business UK&I (1)
- Sales Director - ServiceNow (1)
- Operations Tooling Engineer (1)
- Lead Banking Operations - Debt Collection (1)
- Director, Engineering IT Operations (1)
- Founding EMEA Marketing Lead (1)
- Regional Operations Director (1)
- Account Executive – Accountant Channel (1)
- Growth Operations Apprentice (1)
- Prudential Reporting & Banking Accountant H/F (1)
- B2B Marketing Manager, DACH (1)

## Top 50 Unclassified titles

- Account Executive, Enterprise (5)
- Senior National Account Manager (4)
- Ingénieur confirmé géotechnique F/H (3)
- Senior Business Development Director (f/m/d) (3)
- Strategic Account Executive (3)
- Applied AI Architect, Partnerships (3)
- Manager, Forward Deployed Engineering (3)
- Technical Deployment Lead (3)
- Senior Product Engineer (3)
- Staff Product Engineer, AI (3)
- Mechanical Engineer, Jigs & Tools (2)
- Mechanical Engineer, Automation Projects (2)
- Compliance Director (2)
- Head of Compliance (2)
- General Manager (2)
- CEO - Doit Lithuania (2)
- French Speaking Fitbit Customer Support Specialist - Work In Sofia, Bulgaria (2)
- French Speaking Partner Technical Solutions Consultant - Work In Sofia, Bulgaria (2)
- Key Account Manager 🇫🇷 (2)
- Client Data & Analytics Lead (f/m/d) (2)
- Senior Account Manager (2)
- Customer Success Manager (2)
- (Senior) Full Stack Engineer (m/f/x) - Based in Germany (2)
- Mid-Market Account Executive - France (2)
- (Senior) React Native Engineer (m/f/x) - Based in Germany (2)
- Applied AI Architect, Industries  (2)
- Enterprise Account Executive, Public Sector (2)
- DACH Senior Solution Engineer (f/m/d) (2)
- Mid Market Account Executive - DACH (f/m/d) (2)
- Mid Market Account Executive - France (f/m/d) (2)
- Senior Solution Engineer - France (f/m/d) (2)
- Account Executive, MidMarket (2)
- Account Executive, MidMarket - German Speaking (2)
- Account Executive, Senior MidMarket (French) (2)
- Business Development Representative (2)
- Senior Customer Education Manager, Live Programs (2)
- Senior Customer Success Manager (2)
- Senior Machine Learning Scientist  (2)
- Solutions Architect (2)
- Client Enablement & Coaching Lead (f/m/d) - Danish & German speaking (1)
- Senior Embedded (ARM) Engineer - Quantum Computing (m/w/d) (1)
- Mobile Quality Engineer (1)
- Partnerships Manager (South East) (1)
- Partnerships Manager (North West) (1)
- Partnerships Manager (Midlands) (1)
- Partnerships Manager (London) (1)
- Talent Lead at AIOS- Remote, $100-200k inc equity (1)
- Head of Applied Research (1)
- English Language Instructor (1)
- Technology Transformation - Senior (1)

Exports: `data/exports/stage2_europe_pilot.csv` and `data/exports/stage2_europe_pilot.json`.
Local MT title translations available for hand spot-check: **0** (`data/exports/stage2_title_translation_review.csv`). The 100-title classification sheet provides manual expected-label fields.
