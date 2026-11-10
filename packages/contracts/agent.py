from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from packages.contracts.base import VersionedBaseModel, utc_now


class AgentRole(str, Enum):
    PROFILE_ANALYST = "profile_analyst"
    JOB_DISCOVERY = "job_discovery"
    MATCH_AND_RANKING = "match_and_ranking"
    RESUME_AND_DOCUMENT = "resume_and_document"
    APPLICATION_READINESS = "application_readiness"
    APPLICATION = "application"
    EMAIL_WRITER = "email_writer"
    RESEARCH_INTERVIEW_COACH = "research_interview_coach"
    POLICY_QUALITY_REVIEWER = "policy_quality_reviewer"


class AgentRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PAUSED_FOR_APPROVAL = "paused_for_approval"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ToolCallRecord(BaseModel):
    """
    Audit record for any external tool invoked by an agent node.
    """
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    output_summary: Optional[str] = None
    execution_time_ms: Optional[float] = None
    is_success: bool = True
    error_message: Optional[str] = None


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class AgentExecutionMetadata(BaseModel):
    """
    Standard metadata captured per agent run execution.
    """
    model_name: str = Field(default="llama3.2:1b", description="Local open source model identifier")
    model_version: Optional[str] = None
    prompt_version: str = Field(default="v1.0.0")
    tool_calls: List[ToolCallRecord] = Field(default_factory=list)
    tokens_used: Optional[TokenUsage] = None
    duration_ms: Optional[float] = None
    user_approval_state: Optional[str] = None
    timestamp: datetime = Field(default_factory=utc_now)

    model_config = {
        "protected_namespaces": ()
    }


class AgentRunRecord(VersionedBaseModel):
    """
    Authoritative audit record of a single agent invocation.
    Captures model provenance, prompt version, tool telemetry, and approval state.
    """
    id: Optional[str] = None
    agent_role: AgentRole
    workflow_id: Optional[str] = None
    user_id: str
    status: AgentRunStatus = AgentRunStatus.PENDING

    # Provenance (Open source local models default)
    model_name: str = Field(default="llama3.2:1b", description="e.g. 'llama3.2:1b', 'all-minilm'")
    prompt_version: str = Field(default="v1.0.0")

    # Inputs & Outputs
    inputs_payload: Dict[str, Any] = Field(default_factory=dict)
    outputs_payload: Dict[str, Any] = Field(default_factory=dict)

    # Telemetry & Audit
    tool_calls: List[ToolCallRecord] = Field(default_factory=list)
    token_usage: Optional[TokenUsage] = None
    latency_ms: Optional[float] = None
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = None

    # Safety & Human Gate
    user_approval_state: Optional[str] = Field(
        None,
        description="'pending', 'approved', 'rejected', 'not_required'"
    )
    error_message: Optional[str] = None
