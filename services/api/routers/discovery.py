"""
Phase 5 — Week 2: Job Discovery & Matching Workflow REST API
=============================================================
Exposes the LangGraph JobDiscoveryAndMatchingWorkflow via HTTP endpoints:

POST /api/v1/discovery/start
    Kick off a new job discovery + match scoring workflow run.
    Returns immediately when the workflow pauses at the shortlist gate.

GET  /api/v1/discovery/{workflow_id}/status
    Retrieve current workflow state (stage, is_paused, ranked matches count).

GET  /api/v1/discovery/{workflow_id}/matches
    Fetch the ranked match list for a paused workflow ready for user review.

POST /api/v1/discovery/{workflow_id}/approve-shortlist
    Resume the workflow with the user's shortlist / dismiss decisions.

GET  /api/v1/discovery/{workflow_id}/shortlisted
    Return only the shortlisted job IDs and their match explanations.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from services.orchestrator.checkpointer import MemoryCheckpointer
from services.orchestrator.job_discovery_workflow import (
    JobDiscoveryAndMatchingWorkflow,
)

router = APIRouter(prefix="/api/v1/discovery", tags=["Job Discovery Workflow"])

# In-process store: workflow_id → workflow instance (dev; prod uses DB-backed checkpointer)
_WORKFLOW_STORE: Dict[str, JobDiscoveryAndMatchingWorkflow] = {}

# Shared in-memory checkpointer across all workflow instances in this process
_SHARED_CHECKPOINTER = MemoryCheckpointer()


def _get_or_create_workflow(workflow_id: str) -> JobDiscoveryAndMatchingWorkflow:
    if workflow_id not in _WORKFLOW_STORE:
        _WORKFLOW_STORE[workflow_id] = JobDiscoveryAndMatchingWorkflow(
            checkpointer=_SHARED_CHECKPOINTER,
        )
    return _WORKFLOW_STORE[workflow_id]


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class DiscoveryStartRequest(BaseModel):
    workflow_id: Optional[str] = Field(None, description="Custom workflow ID; auto-generated if omitted")
    user_id: str = Field(..., description="Owning user ID")
    profile_id: Optional[str] = Field(None, description="Candidate profile ID for match scoring")
    # Candidate profile snapshot (must be provided for match scoring)
    extracted_profile: Optional[Dict[str, Any]] = Field(
        None,
        description="Serialised CandidateProfile dict. Required for match scoring.",
    )
    # Pre-seeded job payloads (optional; triggers live ingestion if absent)
    raw_job_payloads: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Pre-normalized/raw job payload dicts. If omitted, live adapters are queried.",
    )
    # Discovery filter parameters
    discovery_query: Optional[str] = None
    discovery_location: Optional[str] = None
    discovery_work_mode: Optional[str] = None
    discovery_seniority: Optional[str] = None
    discovery_min_salary: Optional[int] = None
    discovery_max_salary: Optional[int] = None
    discovery_limit: int = Field(15, ge=1, le=50)


class MatchSummaryItem(BaseModel):
    job_id: Optional[str]
    title: str
    organization: str
    location: str
    work_mode: str
    seniority: str
    composite_score: float
    recommendation: str
    strengths: List[str]
    gaps: List[str]


class DiscoveryStatusResponse(BaseModel):
    workflow_id: str
    user_id: str
    current_stage: str
    is_paused: bool
    pause_reason: Optional[str]
    total_raw_jobs: int
    total_normalized_jobs: int
    total_ranked_matches: int
    shortlist_approved: bool
    errors: List[str]


class ShortlistApprovalRequest(BaseModel):
    shortlisted_job_ids: List[str] = Field(..., description="Job IDs the user wants to shortlist")
    dismissed_job_ids: List[str] = Field(default_factory=list, description="Job IDs the user dismisses")
    user_feedback: Optional[str] = Field(None, description="Optional free-text feedback from user")


class ShortlistConfirmedResponse(BaseModel):
    workflow_id: str
    current_stage: str
    is_paused: bool
    shortlist_approved: bool
    shortlisted_job_ids: List[str]
    dismissed_job_ids: List[str]
    audit_trail_length: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/start", response_model=DiscoveryStatusResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_discovery_workflow(payload: DiscoveryStartRequest):
    """
    Launch a new Job Discovery & Matching workflow.
    Runs: job_discovery → normalization → match scoring → pauses at shortlist gate.
    Returns the workflow ID and status when paused.
    """
    import uuid as _uuid
    workflow_id = payload.workflow_id or str(_uuid.uuid4())

    wf = _get_or_create_workflow(workflow_id)

    initial_state = {
        "workflow_id": workflow_id,
        "user_id": payload.user_id,
        "profile_id": payload.profile_id,
        "extracted_profile": payload.extracted_profile or {},
        "raw_job_payloads": payload.raw_job_payloads or [],
        "discovery_query": payload.discovery_query,
        "discovery_location": payload.discovery_location,
        "discovery_work_mode": payload.discovery_work_mode,
        "discovery_seniority": payload.discovery_seniority,
        "discovery_min_salary": payload.discovery_min_salary,
        "discovery_max_salary": payload.discovery_max_salary,
        "discovery_limit": payload.discovery_limit,
        "current_stage": "job_discovery",
        "is_paused": False,
        "audit_trail": [],
        "errors": [],
        "ranked_matches": [],
        "normalized_jobs": [],
        "shortlisted_job_ids": [],
        "dismissed_job_ids": [],
        "shortlist_approved": False,
    }

    try:
        result_state = wf.start(initial_state)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Workflow start failed: {exc!s}",
        )

    return DiscoveryStatusResponse(
        workflow_id=workflow_id,
        user_id=result_state.get("user_id", payload.user_id),
        current_stage=result_state.get("current_stage", "awaiting_shortlist_approval"),
        is_paused=result_state.get("is_paused", True),
        pause_reason=result_state.get("pause_reason"),
        total_raw_jobs=len(result_state.get("raw_job_payloads") or []),
        total_normalized_jobs=len(result_state.get("normalized_jobs") or []),
        total_ranked_matches=len(result_state.get("ranked_matches") or []),
        shortlist_approved=result_state.get("shortlist_approved", False),
        errors=result_state.get("errors") or [],
    )


@router.get("/{workflow_id}/status", response_model=DiscoveryStatusResponse)
async def get_workflow_status(workflow_id: str):
    """
    Retrieve the current stage, pause status, and progress counts for a workflow.
    """
    wf = _get_or_create_workflow(workflow_id)
    state = wf.load_state(workflow_id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow '{workflow_id}' not found",
        )
    return DiscoveryStatusResponse(
        workflow_id=workflow_id,
        user_id=state.get("user_id", "unknown"),
        current_stage=state.get("current_stage", "unknown"),
        is_paused=state.get("is_paused", False),
        pause_reason=state.get("pause_reason"),
        total_raw_jobs=len(state.get("raw_job_payloads") or []),
        total_normalized_jobs=len(state.get("normalized_jobs") or []),
        total_ranked_matches=len(state.get("ranked_matches") or []),
        shortlist_approved=state.get("shortlist_approved", False),
        errors=state.get("errors") or [],
    )


@router.get("/{workflow_id}/matches", response_model=List[MatchSummaryItem])
async def get_ranked_matches(workflow_id: str):
    """
    Retrieve the ranked match list for user review at the shortlist gate.
    Returns job summaries sorted by composite score descending.
    """
    wf = _get_or_create_workflow(workflow_id)
    ranked_matches = wf.get_ranked_matches(workflow_id)

    if ranked_matches is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow '{workflow_id}' not found or has no matches yet",
        )

    result = []
    for item in ranked_matches:
        job = item.get("job", {})
        expl = item.get("explanation", {})
        result.append(
            MatchSummaryItem(
                job_id=job.get("id"),
                title=job.get("title", ""),
                organization=job.get("organization", ""),
                location=job.get("location", ""),
                work_mode=job.get("work_mode", ""),
                seniority=job.get("seniority", ""),
                composite_score=expl.get("composite_score", 0.0),
                recommendation=expl.get("recommendation", ""),
                strengths=expl.get("strengths", []),
                gaps=expl.get("gaps", []),
            )
        )
    return result


@router.post(
    "/{workflow_id}/approve-shortlist",
    response_model=ShortlistConfirmedResponse,
    status_code=status.HTTP_200_OK,
)
async def approve_shortlist(workflow_id: str, payload: ShortlistApprovalRequest):
    """
    Resume a paused workflow with the user's shortlist approval decision.
    Marks selected jobs as 'shortlisted' and dismissed jobs as 'dismissed'.
    Advances the workflow to 'shortlist_confirmed'.
    """
    wf = _get_or_create_workflow(workflow_id)
    state = wf.load_state(workflow_id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow '{workflow_id}' not found",
        )
    if not state.get("is_paused"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Workflow '{workflow_id}' is not currently paused at the shortlist gate",
        )

    try:
        final_state = wf.resume_with_shortlist(
            workflow_id=workflow_id,
            shortlisted_job_ids=payload.shortlisted_job_ids,
            dismissed_job_ids=payload.dismissed_job_ids,
            user_feedback=payload.user_feedback,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Shortlist approval failed: {exc!s}",
        )

    return ShortlistConfirmedResponse(
        workflow_id=workflow_id,
        current_stage=final_state.get("current_stage", "shortlist_confirmed"),
        is_paused=final_state.get("is_paused", False),
        shortlist_approved=final_state.get("shortlist_approved", True),
        shortlisted_job_ids=final_state.get("shortlisted_job_ids") or [],
        dismissed_job_ids=final_state.get("dismissed_job_ids") or [],
        audit_trail_length=len(final_state.get("audit_trail") or []),
    )


@router.get("/{workflow_id}/shortlisted", response_model=List[MatchSummaryItem])
async def get_shortlisted_matches(workflow_id: str):
    """
    Return only the shortlisted jobs (confirmed by user) with their match explanations.
    """
    wf = _get_or_create_workflow(workflow_id)
    state = wf.load_state(workflow_id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow '{workflow_id}' not found",
        )

    shortlisted_ids = set(state.get("shortlisted_job_ids") or [])
    ranked_matches = state.get("ranked_matches") or []

    result = []
    for item in ranked_matches:
        job = item.get("job", {})
        expl = item.get("explanation", {})
        job_id = job.get("id") or expl.get("job_id")
        if job_id and job_id in shortlisted_ids:
            result.append(
                MatchSummaryItem(
                    job_id=job_id,
                    title=job.get("title", ""),
                    organization=job.get("organization", ""),
                    location=job.get("location", ""),
                    work_mode=job.get("work_mode", ""),
                    seniority=job.get("seniority", ""),
                    composite_score=expl.get("composite_score", 0.0),
                    recommendation=expl.get("recommendation", ""),
                    strengths=expl.get("strengths", []),
                    gaps=expl.get("gaps", []),
                )
            )

    return sorted(result, key=lambda x: x.composite_score, reverse=True)
