from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def now():
    return datetime.now(UTC)


JSON_DOCUMENT = JSON().with_variant(JSONB, "postgresql")


class Base(DeclarativeBase):
    pass


job_skills = Table(
    "job_skills",
    Base.metadata,
    Column("job_id", ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True),
    Column("skill_id", ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
)


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    attribution: Mapped[str | None] = mapped_column(Text)
    jobs: Mapped[list["Job"]] = relationship(back_populates="source")


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (
        UniqueConstraint("name", "ats", "ats_identifier", name="uq_company_ats_identifier"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(2))
    region: Mapped[str | None] = mapped_column(String(40))
    website: Mapped[str | None] = mapped_column(String(2048))
    careers_url: Mapped[str | None] = mapped_column(String(2048))
    ats: Mapped[str | None] = mapped_column(String(40))
    ats_identifier: Mapped[str | None] = mapped_column(String(255))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Location(Base):
    __tablename__ = "locations"
    id: Mapped[int] = mapped_column(primary_key=True)
    location_raw: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(255))
    region: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(255))
    country_code: Mapped[str | None] = mapped_column(String(2))
    remote_type: Mapped[str] = mapped_column(String(20), default="unknown")


class Skill(Base):
    __tablename__ = "skills"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    jobs: Mapped[list["Job"]] = relationship(secondary=job_skills, back_populates="skills")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("source_id", "source_job_id", name="uq_job_source_identity"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    source_job_id: Mapped[str] = mapped_column(String(512))
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"))
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    company_name: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(512))
    normalized_title: Mapped[str | None] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)
    description_html: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    remote_type: Mapped[str] = mapped_column(String(20), default="unknown")
    employment_type: Mapped[str | None] = mapped_column(String(80))
    seniority: Mapped[str | None] = mapped_column(String(80))
    department: Mapped[str | None] = mapped_column(String(255))
    salary_min: Mapped[float | None] = mapped_column(Float)
    salary_max: Mapped[float | None] = mapped_column(Float)
    salary_currency: Mapped[str | None] = mapped_column(String(8))
    salary_period: Mapped[str | None] = mapped_column(String(40))
    salary_raw: Mapped[str | None] = mapped_column(Text)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    apply_url: Mapped[str | None] = mapped_column(String(2048))
    source_url: Mapped[str | None] = mapped_column(String(2048))
    primary_category: Mapped[str | None] = mapped_column(String(120))
    secondary_categories: Mapped[list] = mapped_column(JSON_DOCUMENT, default=list)
    source_metadata: Mapped[dict | list | None] = mapped_column(JSON_DOCUMENT)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    missing_runs: Mapped[int] = mapped_column(Integer, default=0)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="open")
    content_hash: Mapped[str] = mapped_column(String(64))
    raw_data_path: Mapped[str | None] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    source: Mapped[Source] = relationship(back_populates="jobs")
    company: Mapped[Company | None] = relationship()
    location_record: Mapped[Location | None] = relationship()
    skills: Mapped[list[Skill]] = relationship(secondary=job_skills, back_populates="jobs")


class JobHistory(Base):
    __tablename__ = "job_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    title: Mapped[str | None] = mapped_column(String(512))
    description_hash: Mapped[str | None] = mapped_column(String(64))
    salary_min: Mapped[float | None] = mapped_column(Float)
    salary_max: Mapped[float | None] = mapped_column(Float)
    salary_currency: Mapped[str | None] = mapped_column(String(8))
    location: Mapped[str | None] = mapped_column(Text)
    remote_type: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str | None] = mapped_column(String(20))
    content_hash: Mapped[str] = mapped_column(String(64))


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36))
    source: Mapped[str | None] = mapped_column(String(80))
    connector: Mapped[str | None] = mapped_column(String(80))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    companies_attempted: Mapped[int] = mapped_column(default=0)
    companies_succeeded: Mapped[int] = mapped_column(default=0)
    companies_failed: Mapped[int] = mapped_column(default=0)
    jobs_found: Mapped[int] = mapped_column(default=0)
    jobs_inserted: Mapped[int] = mapped_column(default=0)
    jobs_updated: Mapped[int] = mapped_column(default=0)
    jobs_closed: Mapped[int] = mapped_column(default=0)
    duration: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20))
    error_summary: Mapped[str | None] = mapped_column(Text)


class ScrapeError(Base):
    __tablename__ = "scrape_errors"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36))
    source: Mapped[str | None] = mapped_column(String(80))
    company: Mapped[str | None] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DuplicateCandidate(Base):
    __tablename__ = "duplicate_candidates"
    __table_args__ = (UniqueConstraint("job_a_id", "job_b_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    job_a_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    job_b_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    score: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
