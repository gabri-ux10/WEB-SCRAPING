# Stage 3 Asia Pilot Report

Run date: 2026-11-06
Sources: Arbeitnow public API and Greenhouse public Job Board API; Teamtailor public RSS was optional and discovered from the Arbeitnow sample.
Scope: Asia only (UN M49 region 142), maximum 500 source records per feed and 1,000 unique canonical postings overall. Requests used a 10-second timeout and per-host rate limiting of no more than one request per second.
Classification: rules-only; no LLM fallback. Extensions enabled; C5 remains adjacent. M49 groupings are used as published.
Translation: Helsinki-NLP OPUS-MT models were unavailable locally during this run; original titles were preserved and English title fields remain pending where translation was unavailable.

## Collection

arbeitnow: included
teamtailor: no verified feed found in the Arbeitnow sample
- Source records selected: **290**
- Canonical English-key unique postings: **262**
- Arbeitnow: **2**
- Teamtailor RSS: **0**
- Greenhouse: **288**
- Arbeitnow keys also present in ATS feeds: **0**
- U+FFFD title quarantine records: **0**
- HTTP failed URLs after retries: **0**

## Per-language title accuracy

Accuracy against human labels is **pending**: the accompanying 100-title manual sheet has blank reviewer fields and the 300-row golden set is explicitly unverified. The rule-only baseline below is coverage by detected title language, not accuracy:

- en: 284 titles; accuracy pending hand labels
- ja: 2 titles; accuracy pending hand labels
- zh: 4 titles; accuracy pending hand labels

## German text cleanliness

- German-title postings: **0**
- German titles containing U+FFFD in stored rows: **0**
- German descriptions containing U+FFFD: **0**
- German descriptions with common mojibake markers: **0**

## Top 50 Non-Tech titles

- Ocean Operations Associate (3)
- Senior Ocean Operations Associate (2)
- Senior Account Executive - Enterprise Sales (Japan)(担当領域:小売・卸売業(中間流通業)・不動産・運輸) (2)
- Senior Contract Solutions Lawyer, APAC (1)
- Enterprise Account Executive - Retail / CPG / Trading (1)
- Recruiter, Go-To-Market (GTM)  (1)
- Recruiter, GTM - Singapore (1)
- Reseller Operations Manager, Japan & Korea (1)
- Partner Sales Manager Singapore (South East Asia) (1)
- Senior Sales Manager, Digital Native, Japan (Based in Tokyo) (1)
- Account Manager - Retail (1)
- Marketing Executive, CRM and Ops, UAE (1)
- Marketing Executive, Merchant Marketing, KW (1)
- Marketing Executive, Value & Promotions (1)
- Senior Security Operations Centre Specialist (1)
- Product Marketing Manager - Figma Weave (Tel Aviv, Israel)  (1)
- Air and Ocean Operations Associate (1)
- Assistant Manager, Ocean Operations (Chennai) (1)
- Assistant Manager, Ocean Operations (Gurugram) (1)
- Marketing Manager APAC (1)
- Sales Manager (1)
- Sales Manager (Chinese Speaking)  (1)
- Sales Manager, Mumbai  (1)
- Sales Manager, New Delhi (1)
- Contract Talent Acquisition Sourcer, Sales (APJ) (1)
- Manager, Sales Recruiting (APJ) (1)
- Recruiter, Sales (APJ) (1)
- Senior Ecosystems Sales Manager: Scale, India (1)
- Senior Manager, Total Rewards Operations (1)
- Account Executive - Enterprise Sales (Japan)(担当領域:インターネットメディア) (1)
- Account Executive - Mid-Enterprise Sales (1)
- Lead Accountant - Order to Cash (1)
- Sales Development Representative (1)
- Senior Account Executive, Enterprise Sales(Acquisition) (1)
- Senior Account Executive - Enterprise Sales (Japan)(担当領域:デジタルプラットフォーマー) (1)
- Senior Account Executive - Enterprise Sales (Japan) (担当領域:大手SIer & 配信メディア) (1)
- Senior Account Executive - Enterprise Sales (Japan)(担当領域:製造・金融業界) (1)
- Senior Cloud Partner Sales Manager (AWS & Microsoft Azure) (1)
- Senior Legal Counsel (1)
- Senior Manager, Partner Sales  (1)
- Senior Partner Sales Manager (1)
- Senior Revenue Operations Manager - GTM Systems and Automation (1)
- Senior Revenue Operations Manager- Order To Cash (1)
- Manager, Revenue Operations Analytics / Revops (Hybrid- Bangalore) (1)
- Senior Machine Learning Operations Engineer (1)
- Sr. Manager, Strategy and Business Operations (1)
- New Market GTM - Digital Marketing Manager (1)
- Recruiter - APJ (1)
- Onboarding Operations Specialist 1 (1)
- Phone Numbers Operations Specialist 2 (1)

## Top 50 Unclassified titles

- Applied AI Architect (3)
- Regional Research Economist, Economic Research (3)
- Manager, Account Management (2)
- Technical Program Manager (2)
- Senior Solutions Architect  (2)
- Senior Technical Success Manager (2)
- Technical Success Manager (2)
- Phone Number specialist 1 (2)
- Strategic Account Executive (2)
- Senior Paralegal, Contracts (1)
- Account Executive - Public Sector (ASEAN) (1)
- APAC Recruiting Coordinator (1)
- APAC Tax Lead (1)
- Applied AI Architect ( Global Customers) (1)
- Applied AI Architect, Partnerships (1)
- Applied AI Architects, Partner  (1)
- Compute Country Lead, Japan (1)
- Customer Success (1)
- Customer Success Manager (1)
- Director of Payroll, APAC (1)
- Enterprise Account Executive, Digital Native Business  (1)
- Enterprise Account Executive, Industries - BFSI (1)
- Enterprise Account Executive - Industries Generalist (ASEAN) (1)
- Enterprise Account Executive - Manufacturing Industries, Taiwan (1)
- Enterprise Account Executive, System Integrators (1)
- Head of ASEAN, Applied AI (1)
- Head of Partnerships, Japan (1)
- International Accounting, APAC (1)
- IT Support Engineer (1)
- Manager, Account Executive (1)
- Manager, Applied AI Architect (1)
- Partner Account Manager, Systems Integrators (1)
- Product Support Specialist (1)
- Account Executive, Enterprise (1)
- Account Executive, Scale (Thailand and Vietnam market) (1)
- Senior Employer Brand & Employee Experience Specialist (1)
- Deal Desk Manager, APAC (1)
- Commercial Project Manager (1)
- Corporate Account Manager - Deliveroo for Work (1)
- Corporate Commercial Manager, Abu Dhabi (1)
- Emiratisation Talent Pool (1)
- Junior Designer - Kuwaiti National Only (1)
- Key Account Manager - Restaurants (1)
- Mid Market Account Manager (1)
- People Services Advisor (1)
- Rider Engagement Associate - UAE National  (1)
- Service Desk Specialist (1)
- SMB Account Manager - Dubai (1)
- Account Executive, Enterprise (Bengaluru, India) (1)
- Account Executive, Enterprise, Mandarin Speaking (Singapore) (1)

Exports: `data/exports/stage3_asia_pilot.csv` and `data/exports/stage3_asia_pilot.json`.
Local MT title translations available for hand spot-check: **0** (`data/exports/stage3_asia_pilot_title_translation_review.csv`). The 100-title classification sheet provides manual expected-label fields.
