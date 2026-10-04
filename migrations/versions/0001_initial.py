"""Initial source-agnostic jobs schema."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(80), unique=True, nullable=False),
        sa.Column("attribution", sa.Text),
    )
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("country", sa.String(2)),
        sa.Column("region", sa.String(40)),
        sa.Column("website", sa.String(2048)),
        sa.Column("careers_url", sa.String(2048)),
        sa.Column("ats", sa.String(40)),
        sa.Column("ats_identifier", sa.String(255)),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("name", "ats", "ats_identifier", name="uq_company_ats_identifier"),
    )
    op.create_table(
        "locations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("location_raw", sa.Text),
        sa.Column("city", sa.String(255)),
        sa.Column("region", sa.String(255)),
        sa.Column("country", sa.String(255)),
        sa.Column("country_code", sa.String(2)),
        sa.Column("remote_type", sa.String(20)),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source_id", sa.Integer, sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("source_job_id", sa.String(512), nullable=False),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id")),
        sa.Column("location_id", sa.Integer, sa.ForeignKey("locations.id")),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("normalized_title", sa.String(512)),
        sa.Column("description", sa.Text),
        sa.Column("description_html", sa.Text),
        sa.Column("location", sa.Text),
        sa.Column("remote_type", sa.String(20)),
        sa.Column("employment_type", sa.String(80)),
        sa.Column("seniority", sa.String(80)),
        sa.Column("department", sa.String(255)),
        sa.Column("salary_min", sa.Float),
        sa.Column("salary_max", sa.Float),
        sa.Column("salary_currency", sa.String(8)),
        sa.Column("salary_period", sa.String(40)),
        sa.Column("salary_raw", sa.Text),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("apply_url", sa.String(2048)),
        sa.Column("source_url", sa.String(2048)),
        sa.Column("primary_category", sa.String(120)),
        sa.Column(
            "secondary_categories",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("source_metadata", postgresql.JSONB),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("missing_runs", sa.Integer, nullable=False, server_default="0"),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("raw_data_path", sa.String(2048)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_id", "source_job_id", name="uq_job_source_identity"),
    )
    op.create_index("ix_jobs_country", "jobs", ["location_id"])
    op.create_index("ix_jobs_content_hash", "jobs", ["content_hash"])
    op.create_table(
        "job_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "job_id", sa.Integer, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("title", sa.String(512)),
        sa.Column("description_hash", sa.String(64)),
        sa.Column("salary_min", sa.Float),
        sa.Column("salary_max", sa.Float),
        sa.Column("salary_currency", sa.String(8)),
        sa.Column("location", sa.Text),
        sa.Column("remote_type", sa.String(20)),
        sa.Column("status", sa.String(20)),
        sa.Column("content_hash", sa.String(64), nullable=False),
    )
    op.create_table(
        "skills",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(120), unique=True, nullable=False),
    )
    op.create_table(
        "job_skills",
        sa.Column(
            "job_id", sa.Integer, sa.ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column(
            "skill_id", sa.Integer, sa.ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True
        ),
    )
    op.create_table(
        "scrape_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("source", sa.String(80)),
        sa.Column("connector", sa.String(80)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("companies_attempted", sa.Integer, nullable=False, server_default="0"),
        sa.Column("companies_succeeded", sa.Integer, nullable=False, server_default="0"),
        sa.Column("companies_failed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("jobs_found", sa.Integer, nullable=False, server_default="0"),
        sa.Column("jobs_inserted", sa.Integer, nullable=False, server_default="0"),
        sa.Column("jobs_updated", sa.Integer, nullable=False, server_default="0"),
        sa.Column("jobs_closed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("duration", sa.Float),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_summary", sa.Text),
    )
    op.create_table(
        "scrape_errors",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("source", sa.String(80)),
        sa.Column("company", sa.String(255)),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "duplicate_candidates",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "job_a_id", sa.Integer, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "job_b_id", sa.Integer, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("job_a_id", "job_b_id"),
    )


def downgrade():
    for table in (
        "duplicate_candidates",
        "scrape_errors",
        "scrape_runs",
        "job_skills",
        "skills",
        "job_history",
        "jobs",
        "locations",
        "companies",
        "sources",
    ):
        op.drop_table(table)
