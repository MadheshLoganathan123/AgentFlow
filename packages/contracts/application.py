from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from packages.contracts.base import EvidenceReference, VersionedBaseModel, utc_now


class ApplicationStatus(str, Enum):
    DRAFT = "draft"
    READY_FOR_REVIEW = "ready_for_review"
    USER_CONFIRMED = "user_confirmed"
    SUBMITTED = "submitted"
    HANDOFF_REQUIRED = "handoff_required"
    FAILED = "failed"
    WITHDRAWN = "withdrawn"


class TailoredDocument(BaseModel):
    document_type: str = Field(..., description="'resume', 'cover_letter', 'answers'")
    title: str
    content_text: str
    content_pdf_url: Optional[str] = None
    changed_sections: List[str] = Field(default_factory=list)
    evidence_links: List[EvidenceReference] = Field(default_factory=list)
    unsupported_claim_warnings: List[str] = Field(default_factory=list)


class ApplicationPackage(VersionedBaseModel):
    """
    Generated application package grounded strictly in confirmed profile facts.
    """
    id: Optional[str] = None
    job_id: str
    user_id: str
    tailored_resume: TailoredDocument
    cover_letter: Optional[TailoredDocument] = None
    form_answers: Dict[str, str] = Field(default_factory=dict)
    unsupported_claim_warnings: List[str] = Field(default_factory=list)
    is_user_approved: bool = False
    approved_at: Optional[datetime] = None


class ReadinessBlocker(BaseModel):
    field_or_rule: str
    message: str
    severity: str = Field(default="blocker", description="'blocker' or 'warning'")


class ApplicationReadiness(VersionedBaseModel):
    """
    Validation check preventing unsafe or incomplete application submissions.
    """
    is_ready_for_submission: bool
    destination_domain: str
    blockers: List[ReadinessBlocker] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    confirmation_summary: str
    required_user_actions: List[str] = Field(default_factory=list)


class ApplicationResult(VersionedBaseModel):
    """
    Authoritative record of submission or external handoff.
    """
    id: Optional[str] = None
    application_id: str
    status: ApplicationStatus
    destination: str
    idempotency_key: str
    submitted_fields: Dict[str, Any] = Field(default_factory=dict)
    submitted_artifacts: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=utc_now)
    failure_reason: Optional[str] = None
    handoff_url: Optional[str] = None
    handoff_instructions: Optional[str] = None

