from typing import Any, Dict, List, Optional, TypedDict


class AgentFlowWorkflowState(TypedDict, total=False):
    """
    Type-safe workflow state schema shared across LangGraph nodes.
    Supports durable serialization and resume-after-pause execution.
    Used by both ProfileOnboardingWorkflow and JobDiscoveryAndMatchingWorkflow.
    """
    workflow_id: str
    user_id: str
    profile_id: Optional[str]
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
    # ── Phase 5: Job Discovery & Matching ──────────────────────────────────────
    # Ingestion parameters set by caller
    discovery_query: Optional[str]
    discovery_location: Optional[str]
    discovery_work_mode: Optional[str]
    discovery_seniority: Optional[str]
    discovery_min_salary: Optional[int]
    discovery_max_salary: Optional[int]
    discovery_limit: int
    # Raw ingested payloads (list[dict] serialisable representations)
    raw_job_payloads: List[Dict[str, Any]]
    # Normalized + deduplicated canonical job listings (dict reps)
    normalized_jobs: List[Dict[str, Any]]
    normalization_summary: Optional[Dict[str, Any]]
    # Match evaluations: list of {job: dict, explanation: dict}
    ranked_matches: List[Dict[str, Any]]
    # Shortlist approval gate
    shortlisted_job_ids: List[str]
    dismissed_job_ids: List[str]
    shortlist_approved: bool

