"""001_initial_schema: create authoritative relational tables and pgvector support

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-11-09 22:15:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Attempt to enable vector and uuid-ossp extensions on PostgreSQL
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")

    # 1. users
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email")
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # 2. candidate_profiles
    op.create_table(
        "candidate_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("primary_location", sa.String(length=255), nullable=True),
        sa.Column("total_years_experience", sa.Float(), nullable=True),
        sa.Column("work_authorization", sa.String(length=100), nullable=True),
        sa.Column("notice_period_days", sa.Integer(), nullable=True),
        sa.Column("raw_resume_text", sa.Text(), nullable=True),
        sa.Column("structured_data", sa.JSON(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("is_profile_confirmed", sa.Boolean(), nullable=False, default=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_candidate_profiles_user_id", "candidate_profiles", ["user_id"])

    # 3. profile_evidence
    op.create_table(
        "profile_evidence",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("field_name", sa.String(length=100), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_identifier", sa.String(length=255), nullable=False),
        sa.Column("raw_snippet", sa.Text(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False, default=1.0),
        sa.Column("is_inferred", sa.Boolean(), nullable=False, default=False),
        sa.Column("is_user_confirmed", sa.Boolean(), nullable=False, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["candidate_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_profile_evidence_profile_id", "profile_evidence", ["profile_id"])

    # 4. preferences
    op.create_table(
        "preferences",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("target_job_titles", sa.JSON(), nullable=False),
        sa.Column("work_modes", sa.JSON(), nullable=False),
        sa.Column("preferred_locations", sa.JSON(), nullable=False),
        sa.Column("target_salary_min", sa.Integer(), nullable=True),
        sa.Column("target_salary_max", sa.Integer(), nullable=True),
        sa.Column("salary_currency", sa.String(length=10), nullable=False, default="USD"),
        sa.Column("preferred_sectors", sa.JSON(), nullable=False),
        sa.Column("preferred_organizations", sa.JSON(), nullable=False),
        sa.Column("excluded_organizations", sa.JSON(), nullable=False),
        sa.Column("max_commute_minutes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_preferences_user_id", "preferences", ["user_id"])

    # 5. job_sources
    op.create_table(
        "job_sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("adapter_type", sa.String(length=50), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=False, default=60),
        sa.Column("last_scraped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name")
    )

    # 6. job_listings
    op.create_table(
        "job_listings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=True),
        sa.Column("source_name", sa.String(length=100), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("organization", sa.String(length=255), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("work_mode", sa.String(length=50), nullable=False, default="unknown"),
        sa.Column("seniority", sa.String(length=50), nullable=False, default="unspecified"),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("salary_currency", sa.String(length=10), nullable=True, default="USD"),
        sa.Column("skills_required", sa.JSON(), nullable=False),
        sa.Column("skills_preferred", sa.JSON(), nullable=False),
        sa.Column("description_text", sa.Text(), nullable=False),
        sa.Column("description_html", sa.Text(), nullable=True),
        sa.Column("destination_url", sa.Text(), nullable=False),
        sa.Column("application_method", sa.String(length=50), nullable=False, default="url"),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["job_sources.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_hash")
    )
    op.create_index("ix_job_listings_content_hash", "job_listings", ["content_hash"])
    op.create_index("ix_job_listings_title", "job_listings", ["title"])
    op.create_index("ix_job_listings_organization", "job_listings", ["organization"])

    # 7. job_matches
    op.create_table(
        "job_matches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("composite_score", sa.Float(), nullable=False),
        sa.Column("score_breakdown", sa.JSON(), nullable=False),
        sa.Column("strengths", sa.JSON(), nullable=False),
        sa.Column("gaps", sa.JSON(), nullable=False),
        sa.Column("uncertainties", sa.JSON(), nullable=False),
        sa.Column("matched_requirements", sa.JSON(), nullable=False),
        sa.Column("recommendation", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["candidate_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["job_listings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_job_matches_user_id", "job_matches", ["user_id"])
    op.create_index("ix_job_matches_profile_id", "job_matches", ["profile_id"])
    op.create_index("ix_job_matches_job_id", "job_matches", ["job_id"])

    # 8. saved_jobs
    op.create_table(
        "saved_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, default="shortlisted"),
        sa.Column("user_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["job_listings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "job_id", name="uq_user_job_saved")
    )
    op.create_index("ix_saved_jobs_user_id", "saved_jobs", ["user_id"])

    # 9. application_packages
    op.create_table(
        "application_packages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("tailored_resume", sa.JSON(), nullable=False),
        sa.Column("cover_letter", sa.JSON(), nullable=True),
        sa.Column("form_answers", sa.JSON(), nullable=False),
        sa.Column("unsupported_claim_warnings", sa.JSON(), nullable=False),
        sa.Column("is_user_approved", sa.Boolean(), nullable=False, default=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["job_listings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_application_packages_user_id", "application_packages", ["user_id"])

    # 10. applications
    op.create_table(
        "applications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("package_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, default="draft"),
        sa.Column("destination_domain", sa.String(length=255), nullable=False),
        sa.Column("destination_url", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("user_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_payload", sa.JSON(), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("handoff_url", sa.Text(), nullable=True),
        sa.Column("handoff_instructions", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["job_listings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["package_id"], ["application_packages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key")
    )
    op.create_index("ix_applications_user_id", "applications", ["user_id"])
    op.create_index("ix_applications_idempotency_key", "applications", ["idempotency_key"])

    # 11. application_events
    op.create_table(
        "application_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("from_status", sa.String(length=50), nullable=True),
        sa.Column("to_status", sa.String(length=50), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_application_events_application_id", "application_events", ["application_id"])

    # 12. email_drafts
    op.create_table(
        "email_drafts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=True),
        sa.Column("email_type", sa.String(length=50), nullable=False),
        sa.Column("recipient_name", sa.String(length=255), nullable=True),
        sa.Column("recipient_role", sa.String(length=255), nullable=True),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("call_to_action", sa.Text(), nullable=False),
        sa.Column("tone", sa.String(length=50), nullable=False, default="professional"),
        sa.Column("recipient_assumptions", sa.JSON(), nullable=False),
        sa.Column("personalization_evidence", sa.JSON(), nullable=False),
        sa.Column("missing_recipient_warnings", sa.JSON(), nullable=False),
        sa.Column("variants", sa.JSON(), nullable=False),
        sa.Column("is_approved_by_user", sa.Boolean(), nullable=False, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["job_listings.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_email_drafts_user_id", "email_drafts", ["user_id"])

    # 13. research_sources
    op.create_table(
        "research_sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=True),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("source_name", sa.String(length=100), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("is_company_specific", sa.Boolean(), nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["job_listings.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_research_sources_company_name", "research_sources", ["company_name"])

    # 14. interview_plans
    op.create_table(
        "interview_plans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=True),
        sa.Column("role_title", sa.String(length=255), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("seniority", sa.String(length=50), nullable=False),
        sa.Column("company_research_summary", sa.Text(), nullable=False),
        sa.Column("curriculum", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["job_listings.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_interview_plans_user_id", "interview_plans", ["user_id"])

    # 15. mock_interviews
    op.create_table(
        "mock_interviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("recommended_framing", sa.String(length=50), nullable=False, default="STAR"),
        sa.Column("rubric", sa.JSON(), nullable=False),
        sa.Column("user_answer", sa.Text(), nullable=True),
        sa.Column("rubric_score", sa.Float(), nullable=True),
        sa.Column("feedback", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["interview_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_mock_interviews_plan_id", "mock_interviews", ["plan_id"])
    op.create_index("ix_mock_interviews_user_id", "mock_interviews", ["user_id"])

    # 16. agent_runs
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workflow_id", sa.String(length=255), nullable=False),
        sa.Column("agent_name", sa.String(length=100), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("prompt_version", sa.String(length=50), nullable=False),
        sa.Column("model_version", sa.String(length=50), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column("output_payload", sa.JSON(), nullable=False),
        sa.Column("tool_calls", sa.JSON(), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=False, default=0),
        sa.Column("duration_ms", sa.Integer(), nullable=False, default=0),
        sa.Column("status", sa.String(length=50), nullable=False, default="success"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_agent_runs_workflow_id", "agent_runs", ["workflow_id"])
    op.create_index("ix_agent_runs_agent_name", "agent_runs", ["agent_name"])

    # 17. workflow_checkpoints
    op.create_table(
        "workflow_checkpoints",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workflow_id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("current_stage", sa.String(length=100), nullable=False),
        sa.Column("state_payload", sa.JSON(), nullable=False),
        sa.Column("is_paused", sa.Boolean(), nullable=False, default=False),
        sa.Column("pause_reason", sa.String(length=255), nullable=True),
        sa.Column("checkpoint_version", sa.Integer(), nullable=False, default=1),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_workflow_checkpoints_workflow_id", "workflow_checkpoints", ["workflow_id"])
    op.create_index("ix_workflow_checkpoints_user_id", "workflow_checkpoints", ["user_id"])

    # 18. approvals
    op.create_table(
        "approvals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workflow_id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("approval_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("target_payload", sa.JSON(), nullable=False),
        sa.Column("destination_domain", sa.String(length=255), nullable=True),
        sa.Column("is_resolved", sa.Boolean(), nullable=False, default=False),
        sa.Column("approved", sa.Boolean(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_feedback", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_approvals_workflow_id", "approvals", ["workflow_id"])
    op.create_index("ix_approvals_user_id", "approvals", ["user_id"])

    # 19. audit_events
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("workflow_id", sa.String(length=255), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("actor", sa.String(length=50), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("ip_address", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_audit_events_user_id", "audit_events", ["user_id"])
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])

    # 20. model_usage
    op.create_table(
        "model_usage",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("agent_name", sa.String(length=100), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, default=0),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, default=0),
        sa.Column("total_tokens", sa.Integer(), nullable=False, default=0),
        sa.Column("latency_ms", sa.Integer(), nullable=False, default=0),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=False, default=0.0),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_model_usage_user_id", "model_usage", ["user_id"])


def downgrade() -> None:
    op.drop_table("model_usage")
    op.drop_table("audit_events")
    op.drop_table("approvals")
    op.drop_table("workflow_checkpoints")
    op.drop_table("agent_runs")
    op.drop_table("mock_interviews")
    op.drop_table("interview_plans")
    op.drop_table("research_sources")
    op.drop_table("email_drafts")
    op.drop_table("application_events")
    op.drop_table("applications")
    op.drop_table("application_packages")
    op.drop_table("saved_jobs")
    op.drop_table("job_matches")
    op.drop_table("job_listings")
    op.drop_table("job_sources")
    op.drop_table("preferences")
    op.drop_table("profile_evidence")
    op.drop_table("candidate_profiles")
    op.drop_table("users")

