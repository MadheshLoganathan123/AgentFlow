from typing import Any, Dict, List, Optional, TypedDict
from packages.contracts.profile import CandidateProfile
from packages.contracts.workflow import ApprovalRequest, AuditEvent, WorkflowStage


class AgentFlowWorkflowState(TypedDict, total=False):
    """
    Type-safe workflow state schema shared across LangGraph nodes.
    Supports durable serialization and resume-after-pause execution.
    """
    workflow_id: str
    user_id: str
    current_stage: str
    is_paused: bool
    pause_reason: Optional[str]
    raw_resume_bytes: Optional[bytes]
    raw_resume_text: Optional[str]
    extracted_profile: Optional[Dict[str, Any]]
    verified_facts: List[Dict[str, Any]]
    inferred_facts: List[Dict[str, Any]]
    missing_fields: List[Dict[str, Any]]
    pending_approval: Optional[Dict[str, Any]]
    selected_jobs: List[Dict[str, Any]]
    audit_trail: List[Dict[str, Any]]
    errors: List[str]
    retry_count: int

