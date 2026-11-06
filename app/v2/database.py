from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

SCHEMA = "csjobs"


class V2Base(DeclarativeBase):
    pass


class Source(V2Base):
    __tablename__ = "sources"
    __table_args__ = {"schema": SCHEMA}
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    regions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    access: Mapped[str | None] = mapped_column(Text)
    auth: Mapped[str | None] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text)
    limits_and_terms: Mapped[str | None] = mapped_column(Text)
    enable_from_stage: Mapped[str | None] = mapped_column(String(40))
    priority: Mapped[int | None] = mapped_column(Integer)
    terms_decision: Mapped[str] = mapped_column(String(64), nullable=False, default="not_reviewed")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Category(V2Base):
    __tablename__ = "categories"
    __table_args__ = {"schema": SCHEMA}
    id: Mapped[str] = mapped_column(String(12), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tier: Mapped[str] = mapped_column(String(32), nullable=False)


class SubDomain(V2Base):
    __tablename__ = "sub_domains"
    __table_args__ = {"schema": SCHEMA}
    id: Mapped[str] = mapped_column(String(12), primary_key=True)
    category_id: Mapped[str] = mapped_column(ForeignKey(f"{SCHEMA}.categories.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    roadmap: Mapped[str | None] = mapped_column(String(255))
    roadmap_node_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tier: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_roles: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    title_aliases: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    title_aliases_i18n: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class ClassificationFallback(V2Base):
    __tablename__ = "classification_fallbacks"
    __table_args__ = {"schema": SCHEMA}
    id: Mapped[str] = mapped_column(String(12), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    sub_domain: Mapped[str] = mapped_column(String(64), nullable=False)
    use_when: Mapped[str] = mapped_column(Text, nullable=False)


class Company(V2Base):
    __tablename__ = "companies"
    __table_args__ = (UniqueConstraint("normalized_key", name="uq_v2_company_normalized_key"), {"schema": SCHEMA})
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    display_name: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_key: Mapped[str] = mapped_column(String(512), nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(2))
    website: Mapped[str | None] = mapped_column(Text)


class ATSBoard(V2Base):
    __tablename__ = "ats_boards"
    __table_args__ = (UniqueConstraint("source_id", "identifier", name="uq_v2_ats_board"), {"schema": SCHEMA})
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey(f"{SCHEMA}.companies.id"))
    source_id: Mapped[str] = mapped_column(ForeignKey(f"{SCHEMA}.sources.id"), nullable=False)
    identifier: Mapped[str] = mapped_column(String(512), nullable=False)
    discovered_from: Mapped[str | None] = mapped_column(Text)
    verified_name_match: Mapped[bool | None] = mapped_column(Boolean)
    last_status: Mapped[str | None] = mapped_column(String(64))


class Skill(V2Base):
    __tablename__ = "skills"
    __table_args__ = {"schema": SCHEMA}
    slug: Mapped[str] = mapped_column(String(255), primary_key=True)
    label: Mapped[str] = mapped_column(String(512), nullable=False)
    n_roadmaps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    roadmaps: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    subdomain_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    n_subdomains: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ScrapeRun(V2Base):
    __tablename__ = "scrape_runs"
    __table_args__ = {"schema": SCHEMA}
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    region_m49: Mapped[str | None] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sources_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    postings_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    postings_new: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)


class Posting(V2Base):
    __tablename__ = "postings"
    __table_args__ = (
        UniqueConstraint("source_id", "source_job_id", name="uq_v2_source_posting_identity"),
        {"schema": SCHEMA},
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    canonical_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey(f"{SCHEMA}.sources.id"), nullable=False)
    source_job_id: Mapped[str] = mapped_column(String(512), nullable=False)
    company_id: Mapped[int | None] = mapped_column(ForeignKey(f"{SCHEMA}.companies.id"))
    raw_title: Mapped[str] = mapped_column(Text, nullable=False)
    clean_title: Mapped[str] = mapped_column(Text, nullable=False)
    clean_title_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    title_language: Mapped[str] = mapped_column(String(8), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    description_language: Mapped[str | None] = mapped_column(String(8))
    language_confidence: Mapped[float | None] = mapped_column(Float)
    translation_method: Mapped[str] = mapped_column(String(32), nullable=False)
    description_raw: Mapped[str | None] = mapped_column(Text)
    source_charset: Mapped[str | None] = mapped_column(String(80))
    source_url: Mapped[str | None] = mapped_column(Text)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    country_code: Mapped[str | None] = mapped_column(String(2), index=True)
    region_m49: Mapped[str | None] = mapped_column(String(3), index=True)
    city: Mapped[str | None] = mapped_column(String(255))
    location_raw: Mapped[str | None] = mapped_column(Text)
    is_remote: Mapped[bool | None] = mapped_column(Boolean)
    is_hybrid: Mapped[bool | None] = mapped_column(Boolean)
    employment_type: Mapped[str | None] = mapped_column(String(100))
    normalized_role: Mapped[str] = mapped_column(Text, nullable=False)
    seniority: Mapped[str] = mapped_column(String(64), nullable=False)
    domain_specialization: Mapped[str | None] = mapped_column(String(255))
    category_id: Mapped[str] = mapped_column(String(12), nullable=False)
    sub_domain_id: Mapped[str | None] = mapped_column(String(12))
    is_tech_role: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tier: Mapped[str | None] = mapped_column(String(32))
    role_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_flag: Mapped[str] = mapped_column(String(16), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(48))
    salary_min: Mapped[float | None] = mapped_column(Float)
    salary_max: Mapped[float | None] = mapped_column(Float)
    salary_currency: Mapped[str | None] = mapped_column(String(8))
    raw_payload: Mapped[dict | list | None] = mapped_column(JSONB)
    scrape_run_id: Mapped[str | None] = mapped_column(ForeignKey(f"{SCHEMA}.scrape_runs.id"))
    classifier_version: Mapped[str] = mapped_column(String(32), nullable=False)
    taxonomy_version: Mapped[str] = mapped_column(String(32), nullable=False)


class RawPayload(V2Base):
    __tablename__ = "raw_payloads"
    __table_args__ = {"schema": SCHEMA}
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(ForeignKey(f"{SCHEMA}.sources.id"), nullable=False)
    source_job_id: Mapped[str | None] = mapped_column(String(512))
    raw_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    source_charset: Mapped[str | None] = mapped_column(String(80))
    content_type: Mapped[str | None] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))


class QuarantinedRecord(V2Base):
    __tablename__ = "quarantined_records"
    __table_args__ = {"schema": SCHEMA}
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(ForeignKey(f"{SCHEMA}.sources.id"), nullable=False)
    source_job_id: Mapped[str | None] = mapped_column(String(512))
    raw_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    source_charset: Mapped[str | None] = mapped_column(String(80))
    content_type: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(String(128), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))


class PostingSkill(V2Base):
    __tablename__ = "posting_skills"
    __table_args__ = (UniqueConstraint("posting_id", "skill_slug", "origin", name="uq_v2_posting_skill_origin"), {"schema": SCHEMA})
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    posting_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.postings.id", ondelete="CASCADE"), nullable=False)
    skill_slug: Mapped[str] = mapped_column(ForeignKey(f"{SCHEMA}.skills.slug"), nullable=False)
    origin: Mapped[str] = mapped_column(String(32), nullable=False)


class ClassificationReview(V2Base):
    __tablename__ = "classification_review"
    __table_args__ = (UniqueConstraint("posting_id", name="uq_v2_classification_review_posting"), {"schema": SCHEMA})
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    posting_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.postings.id", ondelete="CASCADE"), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(48), nullable=False)
    owner_decision: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))


class SourceEvidence(V2Base):
    __tablename__ = "source_evidence"
    __table_args__ = (UniqueConstraint("source_id", "evidence_url", name="uq_v2_source_evidence_url"), {"schema": SCHEMA})
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(ForeignKey(f"{SCHEMA}.sources.id"), nullable=False)
    evidence_url: Mapped[str] = mapped_column(Text, nullable=False)
    checked_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    decision: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)


class TranslationCache(V2Base):
    __tablename__ = "translation_cache"
    __table_args__ = (UniqueConstraint("title_hash", "target_language", name="uq_v2_translation_key"), {"schema": SCHEMA})
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_title: Mapped[str] = mapped_column(Text, nullable=False)
    target_language: Mapped[str] = mapped_column(String(8), nullable=False)
    translated_title: Mapped[str] = mapped_column(Text, nullable=False)
    translation_method: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
