import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from packages.db.base import Base, TimestampMixin, utc_now
from packages.db.types import SafeVector


def generate_uuid() -> str:
    return str(uuid.uuid4())


# 1. users
class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    profiles = relationship("CandidateProfileModel", back_populates="user", cascade="all, delete-orphan")
    preferences = relationship("PreferenceModel", back_populates="user", cascade="all, delete-orphan")
    matches = relationship("JobMatchModel", back_populates="user", cascade="all, delete-orphan")
    saved_jobs = relationship("SavedJobModel", back_populates="user", cascade="all, delete-orphan")
    application_packages = relationship("ApplicationPackageModel", back_populates="user", cascade="all, delete-orphan")
    applications = relationship("ApplicationModel", back_populates="user", cascade="all, delete-orphan")
    email_drafts = relationship("EmailDraftModel", back_populates="user", cascade="all, delete-orphan")
    interview_plans = relationship("InterviewPlanModel", back_populates="user", cascade="all, delete-orphan")
    mock_interviews = relationship("MockInterviewModel", back_populates="user", cascade="all, delete-orphan")
    workflows = relationship("WorkflowCheckpointModel", back_populates="user", cascade="all, delete-orphan")
    approvals = relationship("ApprovalModel", back_populates="user", cascade="all, delete-orphan")
    audit_events = relationship("AuditEventModel", back_populates="user", cascade="all, delete-orphan")
    model_usages = relationship("ModelUsageModel", back_populates="user", cascade="all, delete-orphan")


# 2. candidate_profiles
class CandidateProfileModel(Base, TimestampMixin):
    __tablename__ = "candidate_profiles"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    primary_location = Column(String(255), nullable=True)
    total_years_experience = Column(Float, nullable=True)
    work_authorization = Column(String(100), nullable=True)
    notice_period_days = Column(Integer, nullable=True)
    raw_resume_text = Column(Text, nullable=True)
    structured_data = Column(JSON, nullable=False, default=dict)
    embedding = Column(SafeVector(dim=1536), nullable=True)
    is_profile_confirmed = Column(Boolean, default=False, nullable=False)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="profiles")
    evidences = relationship("ProfileEvidenceModel", back_populates="profile", cascade="all, delete-orphan")
    matches = relationship("JobMatchModel", back_populates="profile", cascade="all, delete-orphan")


# 3. profile_evidence (Grounding facts vs inferences)
class ProfileEvidenceModel(Base, TimestampMixin):
    __tablename__ = "profile_evidence"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    profile_id = Column(String(36), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    field_name = Column(String(100), nullable=False)
    source_type = Column(String(50), nullable=False)  # resume_text, user_confirmed, external
    source_identifier = Column(String(255), nullable=False)
    raw_snippet = Column(Text, nullable=True)
    page_number = Column(Integer, nullable=True)
    confidence_score = Column(Float, default=1.0, nullable=False)
    is_inferred = Column(Boolean, default=False, nullable=False)  # Never treat unconfirmed inference as verified
    is_user_confirmed = Column(Boolean, default=False, nullable=False)

    profile = relationship("CandidateProfileModel", back_populates="evidences")


# 4. preferences
class PreferenceModel(Base, TimestampMixin):
    __tablename__ = "preferences"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    target_job_titles = Column(JSON, default=list, nullable=False)
    work_modes = Column(JSON, default=list, nullable=False)  # remote, hybrid, onsite
    preferred_locations = Column(JSON, default=list, nullable=False)
    target_salary_min = Column(Integer, nullable=True)
    target_salary_max = Column(Integer, nullable=True)
    salary_currency = Column(String(10), default="USD", nullable=False)
    preferred_sectors = Column(JSON, default=list, nullable=False)
    preferred_organizations = Column(JSON, default=list, nullable=False)
    excluded_organizations = Column(JSON, default=list, nullable=False)
    max_commute_minutes = Column(Integer, nullable=True)

    user = relationship("User", back_populates="preferences")


# 5. job_sources
class JobSourceModel(Base, TimestampMixin):
    __tablename__ = "job_sources"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), unique=True, nullable=False)
    adapter_type = Column(String(50), nullable=False)  # api, feed, crawler, mock
    base_url = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    rate_limit_per_minute = Column(Integer, default=60, nullable=False)
    last_scraped_at = Column(DateTime(timezone=True), nullable=True)
    settings = Column(JSON, default=dict, nullable=False)

    listings = relationship("JobListingModel", back_populates="source")


# 6. job_listings
class JobListingModel(Base, TimestampMixin):
    __tablename__ = "job_listings"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    source_id = Column(String(36), ForeignKey("job_sources.id", ondelete="SET NULL"), nullable=True, index=True)
    source_name = Column(String(100), nullable=False)
    source_url = Column(Text, nullable=False)
    title = Column(String(255), nullable=False, index=True)
    organization = Column(String(255), nullable=False, index=True)
    location = Column(String(255), nullable=False)
    work_mode = Column(String(50), default="unknown", nullable=False)
    seniority = Column(String(50), default="unspecified", nullable=False)
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    salary_currency = Column(String(10), default="USD", nullable=True)
    skills_required = Column(JSON, default=list, nullable=False)
    skills_preferred = Column(JSON, default=list, nullable=False)
    description_text = Column(Text, nullable=False)
    description_html = Column(Text, nullable=True)
    destination_url = Column(Text, nullable=False)
    application_method = Column(String(50), default="url", nullable=False)
    content_hash = Column(String(64), unique=True, nullable=False, index=True)
    embedding = Column(SafeVector(dim=1536), nullable=True)
    retrieved_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    posted_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    source = relationship("JobSourceModel", back_populates="listings")
    matches = relationship("JobMatchModel", back_populates="job", cascade="all, delete-orphan")
    saved_records = relationship("SavedJobModel", back_populates="job", cascade="all, delete-orphan")
    applications = relationship("ApplicationModel", back_populates="job", cascade="all, delete-orphan")
    research_sources = relationship("ResearchSourceModel", back_populates="job")


# 7. job_matches
class JobMatchModel(Base, TimestampMixin):
    __tablename__ = "job_matches"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    profile_id = Column(String(36), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(String(36), ForeignKey("job_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    composite_score = Column(Float, nullable=False)
    score_breakdown = Column(JSON, default=dict, nullable=False)
    strengths = Column(JSON, default=list, nullable=False)
    gaps = Column(JSON, default=list, nullable=False)
    uncertainties = Column(JSON, default=list, nullable=False)
    matched_requirements = Column(JSON, default=list, nullable=False)
    recommendation = Column(String(50), nullable=False)  # strong_match, potential_match, gap_heavy, not_recommended

    user = relationship("User", back_populates="matches")
    profile = relationship("CandidateProfileModel", back_populates="matches")
    job = relationship("JobListingModel", back_populates="matches")


# 8. saved_jobs
class SavedJobModel(Base, TimestampMixin):
    __tablename__ = "saved_jobs"
    __table_args__ = (UniqueConstraint("user_id", "job_id", name="uq_user_job_saved"),)

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(String(36), ForeignKey("job_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(50), default="shortlisted", nullable=False)  # shortlisted, saved, dismissed, unsuitable
    user_notes = Column(Text, nullable=True)

    user = relationship("User", back_populates="saved_jobs")
    job = relationship("JobListingModel", back_populates="saved_records")


# 9. application_packages
class ApplicationPackageModel(Base, TimestampMixin):
    __tablename__ = "application_packages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(String(36), ForeignKey("job_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    tailored_resume = Column(JSON, nullable=False)  # title, content, changed_sections, evidence_links
    cover_letter = Column(JSON, nullable=True)
    form_answers = Column(JSON, default=dict, nullable=False)
    unsupported_claim_warnings = Column(JSON, default=list, nullable=False)
    is_user_approved = Column(Boolean, default=False, nullable=False)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="application_packages")
    applications = relationship("ApplicationModel", back_populates="package")


# 10. applications
class ApplicationModel(Base, TimestampMixin):
    __tablename__ = "applications"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(String(36), ForeignKey("job_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    package_id = Column(String(36), ForeignKey("application_packages.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(50), default="draft", nullable=False)  # draft, ready_for_review, user_confirmed, submitted, handoff_required, failed, withdrawn
    destination_domain = Column(String(255), nullable=False)
    destination_url = Column(Text, nullable=False)
    idempotency_key = Column(String(128), unique=True, nullable=False, index=True)
    user_confirmed_at = Column(DateTime(timezone=True), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    submitted_payload = Column(JSON, default=dict, nullable=False)
    failure_reason = Column(Text, nullable=True)
    handoff_url = Column(Text, nullable=True)
    handoff_instructions = Column(Text, nullable=True)

    user = relationship("User", back_populates="applications")
    job = relationship("JobListingModel", back_populates="applications")
    package = relationship("ApplicationPackageModel", back_populates="applications")
    events = relationship("ApplicationEventModel", back_populates="application", cascade="all, delete-orphan")


# 11. application_events
class ApplicationEventModel(Base, TimestampMixin):
    __tablename__ = "application_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    application_id = Column(String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    from_status = Column(String(50), nullable=True)
    to_status = Column(String(50), nullable=True)
    details = Column(JSON, default=dict, nullable=False)

    application = relationship("ApplicationModel", back_populates="events")


# 12. email_drafts
class EmailDraftModel(Base, TimestampMixin):
    __tablename__ = "email_drafts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(String(36), ForeignKey("job_listings.id", ondelete="SET NULL"), nullable=True, index=True)
    email_type = Column(String(50), nullable=False)  # recruiter_outreach, referral_request, hiring_manager_note, thank_you, follow_up
    recipient_name = Column(String(255), nullable=True)
    recipient_role = Column(String(255), nullable=True)
    subject = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    call_to_action = Column(Text, nullable=False)
    tone = Column(String(50), default="professional", nullable=False)
    recipient_assumptions = Column(JSON, default=list, nullable=False)
    personalization_evidence = Column(JSON, default=list, nullable=False)
    missing_recipient_warnings = Column(JSON, default=list, nullable=False)
    variants = Column(JSON, default=list, nullable=False)
    is_approved_by_user = Column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="email_drafts")


# 13. research_sources
class ResearchSourceModel(Base, TimestampMixin):
    __tablename__ = "research_sources"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    job_id = Column(String(36), ForeignKey("job_listings.id", ondelete="SET NULL"), nullable=True, index=True)
    company_name = Column(String(255), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    url = Column(Text, nullable=False)
    source_name = Column(String(100), nullable=False)
    retrieved_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    excerpt = Column(Text, nullable=False)
    is_company_specific = Column(Boolean, default=True, nullable=False)

    job = relationship("JobListingModel", back_populates="research_sources")


# 14. interview_plans
class InterviewPlanModel(Base, TimestampMixin):
    __tablename__ = "interview_plans"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(String(36), ForeignKey("job_listings.id", ondelete="SET NULL"), nullable=True, index=True)
    role_title = Column(String(255), nullable=False)
    company_name = Column(String(255), nullable=False)
    seniority = Column(String(50), nullable=False)
    company_research_summary = Column(Text, nullable=False)
    curriculum = Column(JSON, default=dict, nullable=False)

    user = relationship("User", back_populates="interview_plans")
    mock_interviews = relationship("MockInterviewModel", back_populates="plan", cascade="all, delete-orphan")


# 15. mock_interviews
class MockInterviewModel(Base, TimestampMixin):
    __tablename__ = "mock_interviews"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    plan_id = Column(String(36), ForeignKey("interview_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    question_text = Column(Text, nullable=False)
    category = Column(String(50), nullable=False)  # behavioral, technical, system_design
    recommended_framing = Column(String(50), default="STAR", nullable=False)
    rubric = Column(JSON, default=dict, nullable=False)
    user_answer = Column(Text, nullable=True)
    rubric_score = Column(Float, nullable=True)
    feedback = Column(JSON, default=dict, nullable=False)

    plan = relationship("InterviewPlanModel", back_populates="mock_interviews")
    user = relationship("User", back_populates="mock_interviews")


# 16. agent_runs
class AgentRunModel(Base, TimestampMixin):
    __tablename__ = "agent_runs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    workflow_id = Column(String(255), nullable=False, index=True)
    agent_name = Column(String(100), nullable=False, index=True)
    model_name = Column(String(100), nullable=False)
    prompt_version = Column(String(50), nullable=False)
    model_version = Column(String(50), nullable=False)
    input_hash = Column(String(64), nullable=True)
    output_payload = Column(JSON, default=dict, nullable=False)
    tool_calls = Column(JSON, default=list, nullable=False)
    tokens_used = Column(Integer, default=0, nullable=False)
    duration_ms = Column(Integer, default=0, nullable=False)
    status = Column(String(50), default="success", nullable=False)


# 17. workflow_checkpoints
class WorkflowCheckpointModel(Base, TimestampMixin):
    __tablename__ = "workflow_checkpoints"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    workflow_id = Column(String(255), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    current_stage = Column(String(100), nullable=False)
    state_payload = Column(JSON, default=dict, nullable=False)
    is_paused = Column(Boolean, default=False, nullable=False)
    pause_reason = Column(String(255), nullable=True)
    checkpoint_version = Column(Integer, default=1, nullable=False)

    user = relationship("User", back_populates="workflows")


# 18. approvals
class ApprovalModel(Base, TimestampMixin):
    __tablename__ = "approvals"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    workflow_id = Column(String(255), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    approval_type = Column(String(50), nullable=False)  # profile_facts, shortlist_job, tailored_document, application_submission
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    target_payload = Column(JSON, default=dict, nullable=False)
    destination_domain = Column(String(255), nullable=True)
    is_resolved = Column(Boolean, default=False, nullable=False)
    approved = Column(Boolean, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    user_feedback = Column(Text, nullable=True)

    user = relationship("User", back_populates="approvals")


# 19. audit_events
class AuditEventModel(Base, TimestampMixin):
    __tablename__ = "audit_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_id = Column(String(255), nullable=True, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    actor = Column(String(50), nullable=False)  # user, agent, system
    details = Column(JSON, default=dict, nullable=False)
    ip_address = Column(String(50), nullable=True)

    user = relationship("User", back_populates="audit_events")


# 20. model_usage
class ModelUsageModel(Base, TimestampMixin):
    __tablename__ = "model_usage"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_name = Column(String(100), nullable=False)
    model_name = Column(String(100), nullable=False)
    prompt_tokens = Column(Integer, default=0, nullable=False)
    completion_tokens = Column(Integer, default=0, nullable=False)
    total_tokens = Column(Integer, default=0, nullable=False)
    latency_ms = Column(Integer, default=0, nullable=False)
    estimated_cost_usd = Column(Float, default=0.0, nullable=False)

    user = relationship("User", back_populates="model_usages")
