from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from packages.contracts.base import VersionedBaseModel, utc_now


class WorkflowStage(str, Enum):
    PROFILE_INGESTION = "profile_ingestion"
    PROFILE_VALIDATION = "profile_validation"
    JOB_DISCOVERY = "job_discovery"
    JOB_NORMALIZATION = "job_normalization"
    MATCH_SCORING = "match_scoring"
    SHORTLIST_APPROVAL = "shortlist_approval"
    DOCUMENT_TAILORING = "document_tailoring"
    APPLICATION_READINESS = "application_readiness"
    USER_CONFIRMATION = "user_confirmation"
    APPLICATION_SUBMISSION = "application_submission"
    COMPLETED = "completed"
    PAUSED = "paused"
    FAILED = "failed"


class ApprovalType(str, Enum):
    PROFILE_FACTS = "profile_facts"
    SHORTLIST_JOB = "shortlist_job"
    TAILORED_DOCUMENT = "tailored_document"
    APPLICATION_SUBMISSION = "application_submission"


class ApprovalRequest(BaseModel):
    id: str
    workflow_id: str
    user_id: str
    approval_type: ApprovalType
    title: str
    description: str
    target_payload: Dict[str, Any] = Field(default_factory=dict)
    destination_domain: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    is_resolved: bool = False
    approved: Optional[bool] = None
    resolved_at: Optional[datetime] = None
    user_feedback: Optional[str] = None


class AuditEvent(BaseModel):
    id: str
    timestamp: datetime = Field(default_factory=utc_now)
    event_type: str
    user_id: str
    workflow_id: Optional[str] = None
    actor: str = Field(default="system", description="'user', 'agent', 'system'")
    details: Dict[str, Any] = Field(default_factory=dict)


class WorkflowState(VersionedBaseModel):
    """
    LangGraph orchestration state.
    Provides pause, resume, and durable checkpoint capability.
    """
    workflow_id: str
    user_id: str
    current_stage: WorkflowStage = WorkflowStage.PROFILE_INGESTION
    is_paused: bool = False
    pause_reason: Optional[str] = None
    pending_approval: Optional[ApprovalRequest] = None
    candidate_id: Optional[str] = None
    selected_job_ids: List[str] = Field(default_factory=list)
    state_data: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    retry_count: int = 0

