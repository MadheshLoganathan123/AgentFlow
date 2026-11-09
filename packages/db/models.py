import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


from packages.db.base import Base, TimestampMixin, utc_now


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    profiles = relationship("CandidateProfileModel", back_populates="user", cascade="all, delete-orphan")
    workflows = relationship("WorkflowCheckpointModel", back_populates="user")
    audit_events = relationship("AuditEventModel", back_populates="user")


class CandidateProfileModel(Base, TimestampMixin):
    __tablename__ = "candidate_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    primary_location = Column(String(255), nullable=True)
    total_years_experience = Column(Float, nullable=True)
    work_authorization = Column(String(100), nullable=True)
    notice_period_days = Column(Integer, nullable=True)
    raw_resume_text = Column(Text, nullable=True)
    structured_data = Column(JSONB, nullable=False, default=dict)
    is_profile_confirmed = Column(Boolean, default=False, nullable=False)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="profiles")
    evidences = relationship("ProfileEvidenceModel", back_populates="profile", cascade="all, delete-orphan")


class ProfileEvidenceModel(Base, TimestampMixin):
    """
    Evidence grounding model. Distinguishes verified facts from inferences.
    """
    __tablename__ = "profile_evidence"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id = Column(String(36), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    field_name = Column(String(100), nullable=False)
    source_type = Column(String(50), nullable=False)  # resume_text, user_confirmed, external
    source_identifier = Column(String(255), nullable=False)
    raw_snippet = Column(Text, nullable=True)
    page_number = Column(Integer, nullable=True)
    confidence_score = Column(Float, default=1.0, nullable=False)
    is_inferred = Column(Boolean, default=False, nullable=False)
    is_user_confirmed = Column(Boolean, default=False, nullable=False)

    profile = relationship("CandidateProfileModel", back_populates="evidences")


class JobListingModel(Base, TimestampMixin):
    __tablename__ = "job_listings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False, index=True)
    organization = Column(String(255), nullable=False, index=True)
    location = Column(String(255), nullable=False)
    work_mode = Column(String(50), default="unknown", nullable=False)
    seniority = Column(String(50), default="unspecified", nullable=False)
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    salary_currency = Column(String(10), default="USD", nullable=True)
    skills_required = Column(JSONB, default=list, nullable=False)
    description_text = Column(Text, nullable=False)
    destination_url = Column(Text, nullable=False)
    source_name = Column(String(100), nullable=False)
    source_url = Column(Text, nullable=False)
    content_hash = Column(String(64), unique=True, nullable=False, index=True)
    retrieved_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    posted_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)


class WorkflowCheckpointModel(Base, TimestampMixin):
    """
    Durable checkpointing table for LangGraph orchestrator workflows.
    Ensures workflows can pause for human approval and resume safely.
    """
    __tablename__ = "workflow_checkpoints"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id = Column(String(255), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    current_stage = Column(String(100), nullable=False)
    state_payload = Column(JSONB, nullable=False, default=dict)
    is_paused = Column(Boolean, default=False, nullable=False)
    pause_reason = Column(String(255), nullable=True)
    checkpoint_version = Column(Integer, default=1, nullable=False)

    user = relationship("User", back_populates="workflows")


class ApprovalModel(Base, TimestampMixin):
    """
    Human approval gate records. An application or consequential step cannot proceed without this.
    """
    __tablename__ = "approvals"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id = Column(String(255), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    approval_type = Column(String(50), nullable=False)  # profile_facts, shortlist, application
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    target_payload = Column(JSONB, nullable=False, default=dict)
    destination_domain = Column(String(255), nullable=True)
    is_resolved = Column(Boolean, default=False, nullable=False)
    approved = Column(Boolean, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    user_feedback = Column(Text, nullable=True)


class AuditEventModel(Base, TimestampMixin):
    """
    Append-only audit trail for all agent, user, and safety events.
    """
    __tablename__ = "audit_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_id = Column(String(255), nullable=True, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    actor = Column(String(50), nullable=False)  # user, agent, system
    details = Column(JSONB, nullable=False, default=dict)

    user = relationship("User", back_populates="audit_events")
