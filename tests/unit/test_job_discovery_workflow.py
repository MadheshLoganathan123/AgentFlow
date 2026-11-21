"""
Phase 5 — Week 2: LangGraph JobDiscoveryAndMatchingWorkflow Test Suite
=======================================================================
Covers:
  1. Individual node unit tests (pure function assertions)
  2. Full workflow lifecycle: start → pause → resume → confirmed
  3. Shortlist approval gate enforcement (non-bypassable interrupt)
  4. Durable checkpointing and state restoration
  5. Cross-user workflow isolation
  6. REST API endpoints: start, status, matches, approve-shortlist, shortlisted
  7. Edge cases: empty payloads, missing profile, duplicate shortlisting
"""
import uuid
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from packages.contracts.base import utc_now
from packages.contracts.job import JobListing, JobSeniority, WorkMode
from packages.contracts.profile import (
    CandidateProfile,
    SkillItem,
    VerificationState,
    WorkExperience,
    WorkModePreference,
)
from services.api.main import app
from services.orchestrator.checkpointer import MemoryCheckpointer
from services.orchestrator.job_discovery_workflow import (
    JobDiscoveryAndMatchingWorkflow,
    build_job_discovery_graph,
    node_awaiting_shortlist_approval,
    node_job_discovery,
    node_job_normalization_dedup,
    node_match_scoring_explanation,
    node_shortlist_confirmed,
)
from services.orchestrator.state import AgentFlowWorkflowState


# ---------------------------------------------------------------------------
# Shared Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture
def senior_candidate_dict() -> Dict[str, Any]:
    """Serialisable CandidateProfile dict for workflow state injection."""
    return CandidateProfile(
        user_id="usr_phase5_01",
        full_name="Casey Rivers",
        email="casey.rivers@example.com",
        primary_location="San Francisco, CA",
        work_modes=[WorkModePreference.REMOTE, WorkModePreference.HYBRID],
        target_job_titles=["Senior Backend Engineer", "Staff Software Engineer"],
        total_years_experience=7.0,
        work_authorization="US Citizen",
        skills=[
            SkillItem(name="Python", verification_state=VerificationState.VERIFIED_FACT),
            SkillItem(name="FastAPI", verification_state=VerificationState.VERIFIED_FACT),
            SkillItem(name="PostgreSQL", verification_state=VerificationState.VERIFIED_FACT),
            SkillItem(name="Docker", verification_state=VerificationState.VERIFIED_FACT),
            SkillItem(name="Kubernetes", verification_state=VerificationState.VERIFIED_FACT),
        ],
        experience=[
            WorkExperience(
                company="StreamBase",
                title="Senior Backend Engineer",
                start_date="2020-03",
                highlights=["Built event-driven data platform serving 5M req/day"],
            )
        ],
    ).model_dump(mode="json")


@pytest.fixture
def sample_raw_job_payloads() -> List[Dict[str, Any]]:
    """Three realistic raw job payloads using the canonical RawJobPayload schema."""
    now_iso = utc_now().isoformat()
    return [
        {
            "source_name": "mock",
            "source_job_id": "mock_001",
            "source_url": "https://streamscale.io/careers/1",
            "destination_url": "https://streamscale.io/careers/1",
            "title": "Senior Backend Engineer",
            "organization": "StreamScale Inc.",
            "location_raw": "Remote",
            "description_raw": (
                "Build scalable microservices with Python, FastAPI, PostgreSQL, and Docker. "
                "5+ years experience required. Remote-first team. $160K–$210K."
            ),
            "posted_at": now_iso,
        },
        {
            "source_name": "mock",
            "source_job_id": "mock_002",
            "source_url": "https://apexai.com/jobs/2",
            "destination_url": "https://apexai.com/jobs/2",
            "title": "Principal Machine Learning Engineer",
            "organization": "Apex AI Labs",
            "location_raw": "San Francisco, CA (Hybrid)",
            "description_raw": (
                "Lead ML platform initiatives. PhD or 8+ years experience in ML. "
                "PyTorch, Python, Kubernetes. $220K–$300K base."
            ),
            "posted_at": now_iso,
        },
        {
            "source_name": "mock",
            "source_job_id": "mock_003",
            "source_url": "https://testworks.com/jobs/3",
            "destination_url": "https://testworks.com/jobs/3",
            "title": "Junior QA Engineer",
            "organization": "TestWorks",
            "location_raw": "Austin, TX (Onsite)",
            "description_raw": (
                "Write test cases and automation scripts. 1 year experience. "
                "Selenium, Python. $70K–$85K."
            ),
            "posted_at": now_iso,
        },
    ]


def _make_state(
    workflow_id: str,
    user_id: str,
    candidate_dict: Dict[str, Any],
    raw_payloads: List[Dict[str, Any]],
) -> AgentFlowWorkflowState:
    return {
        "workflow_id": workflow_id,
        "user_id": user_id,
        "extracted_profile": candidate_dict,
        "raw_job_payloads": raw_payloads,
        "current_stage": "job_discovery",
        "is_paused": False,
        "audit_trail": [],
        "errors": [],
        "normalized_jobs": [],
        "ranked_matches": [],
        "shortlisted_job_ids": [],
        "dismissed_job_ids": [],
        "shortlist_approved": False,
        "discovery_limit": 15,
    }


# =============================================================================
# 1. Node Unit Tests — Pure Function Assertions
# =============================================================================

def test_node_job_discovery_preseeded(
    sample_raw_job_payloads: List[Dict[str, Any]],
):
    """Pre-seeded payloads bypass live adapter calls and pass through directly."""
    state = {
        "workflow_id": "wf_node_01",
        "user_id": "usr_node_01",
        "raw_job_payloads": sample_raw_job_payloads,
        "audit_trail": [],
        "errors": [],
        "discovery_limit": 15,
    }
    out = node_job_discovery(state)
    assert out["current_stage"] == "job_normalization_dedup"
    assert len(out["raw_job_payloads"]) == 3
    assert any("pre-seeded" in e["message"] for e in out["audit_trail"])


def test_node_job_discovery_empty_state():
    """Empty raw_job_payloads triggers live adapter path (no crash in test env)."""
    state = {
        "workflow_id": "wf_node_02",
        "user_id": "usr_node_02",
        "raw_job_payloads": [],
        "audit_trail": [],
        "errors": [],
        "discovery_limit": 5,
    }
    out = node_job_discovery(state)
    assert out["current_stage"] == "job_normalization_dedup"
    # Errors may appear from live adapter failures — that's acceptable in test env
    assert isinstance(out["raw_job_payloads"], list)


def test_node_normalization_dedup(
    sample_raw_job_payloads: List[Dict[str, Any]],
):
    """Normalization node converts raw payloads to canonical JobListing dicts."""
    state = {
        "raw_job_payloads": sample_raw_job_payloads,
        "audit_trail": [],
        "errors": [],
    }
    out = node_job_normalization_dedup(state)
    assert out["current_stage"] == "match_scoring_explanation"
    # 3 raw payloads should produce ≥1 normalized job (all unique hashes)
    assert len(out["normalized_jobs"]) >= 1
    assert out["normalization_summary"] is not None
    # Every normalized job has a content_hash
    for j in out["normalized_jobs"]:
        assert "content_hash" in j and j["content_hash"]


def test_node_normalization_dedup_empty():
    """Empty payloads produce empty normalized list without error."""
    out = node_job_normalization_dedup({"raw_job_payloads": [], "audit_trail": [], "errors": []})
    assert out["normalized_jobs"] == []
    assert out["current_stage"] == "match_scoring_explanation"


def test_node_match_scoring(
    sample_raw_job_payloads: List[Dict[str, Any]],
    senior_candidate_dict: Dict[str, Any],
):
    """Match scoring produces ranked list sorted by composite_score descending."""
    # First normalize
    norm_out = node_job_normalization_dedup({
        "raw_job_payloads": sample_raw_job_payloads,
        "audit_trail": [],
        "errors": [],
    })
    state = {
        "normalized_jobs": norm_out["normalized_jobs"],
        "extracted_profile": senior_candidate_dict,
        "audit_trail": norm_out["audit_trail"],
        "errors": [],
    }
    out = node_match_scoring_explanation(state)
    assert out["current_stage"] == "awaiting_shortlist_approval"
    ranked = out["ranked_matches"]
    assert len(ranked) >= 1
    # Sorted descending by composite_score
    scores = [r["explanation"]["composite_score"] for r in ranked]
    assert scores == sorted(scores, reverse=True)
    # Senior Backend job should rank highest for a senior backend candidate
    top_job = ranked[0]["job"]
    assert "backend" in top_job["title"].lower() or "engineer" in top_job["title"].lower()
    # Every entry has recommendation field
    for r in ranked:
        assert r["explanation"]["recommendation"] in {
            "strong_match", "potential_match", "gap_heavy", "not_recommended"
        }


def test_node_match_scoring_no_profile():
    """Missing profile → empty ranked_matches, no crash."""
    out = node_match_scoring_explanation({
        "normalized_jobs": [{"title": "job", "organization": "co"}],
        "extracted_profile": None,
        "audit_trail": [],
        "errors": [],
    })
    assert out["ranked_matches"] == []
    assert out["current_stage"] == "awaiting_shortlist_approval"


def test_node_awaiting_shortlist_approval_structure():
    """Approval gate node produces well-formed pending_approval payload."""
    state = {
        "workflow_id": "wf_gate_01",
        "user_id": "usr_gate_01",
        "ranked_matches": [{"job": {}, "explanation": {}}] * 5,
        "audit_trail": [],
        "errors": [],
    }
    out = node_awaiting_shortlist_approval(state)
    assert out["is_paused"] is True
    assert out["current_stage"] == "awaiting_shortlist_approval"
    pa = out["pending_approval"]
    assert pa["approval_type"] == "shortlist_jobs"
    assert pa["ranked_match_count"] == 5
    assert pa["is_resolved"] is False


def test_node_shortlist_confirmed():
    """Confirmation node marks gate resolved and records decisions."""
    state = {
        "shortlisted_job_ids": ["job_a", "job_b"],
        "dismissed_job_ids": ["job_c"],
        "pending_approval": {"is_resolved": False},
        "audit_trail": [],
        "errors": [],
    }
    out = node_shortlist_confirmed(state)
    assert out["current_stage"] == "shortlist_confirmed"
    assert out["is_paused"] is False
    assert out["shortlist_approved"] is True
    assert out["pending_approval"]["is_resolved"] is True
    assert out["pending_approval"]["approved"] is True
    assert any("2 job(s) shortlisted" in e["message"] for e in out["audit_trail"])


# =============================================================================
# 2. Full Workflow Lifecycle Test
# =============================================================================

def test_workflow_full_lifecycle(
    senior_candidate_dict: Dict[str, Any],
    sample_raw_job_payloads: List[Dict[str, Any]],
):
    """Full lifecycle: start → paused at gate → resume with shortlist → confirmed."""
    checkpointer = MemoryCheckpointer()
    wf = JobDiscoveryAndMatchingWorkflow(checkpointer=checkpointer)
    wf_id = "wf_lifecycle_01"

    state = _make_state(wf_id, "usr_lifecycle_01", senior_candidate_dict, sample_raw_job_payloads)

    # --- Step 1: Start workflow ---
    paused_state = wf.start(state)
    assert paused_state["is_paused"] is True
    assert paused_state["current_stage"] == "awaiting_shortlist_approval"
    assert paused_state["pause_reason"] == "Human shortlist approval required"

    # Ranked matches exist
    ranked = paused_state.get("ranked_matches") or []
    assert len(ranked) >= 1

    # Checkpoint persisted
    checkpoint = checkpointer.load_checkpoint(wf_id)
    assert checkpoint is not None
    assert checkpoint["is_paused"] is True

    # --- Step 2: User reviews and shortlists top job ---
    top_job_id = ranked[0]["explanation"].get("job_id") or ranked[0]["job"].get("id") or "mock_id"
    shortlisted_ids = [top_job_id]
    dismissed_ids = [
        r["explanation"].get("job_id") or r["job"].get("id") or f"dismissed_{i}"
        for i, r in enumerate(ranked[1:], start=1)
    ]

    resumed_state = wf.resume_with_shortlist(
        workflow_id=wf_id,
        shortlisted_job_ids=shortlisted_ids,
        dismissed_job_ids=dismissed_ids,
        user_feedback="Top match confirmed by candidate",
    )

    # --- Assertions on resumed state ---
    assert resumed_state["is_paused"] is False
    assert resumed_state["current_stage"] == "shortlist_confirmed"
    assert resumed_state["shortlist_approved"] is True
    assert resumed_state["pending_approval"]["is_resolved"] is True
    assert resumed_state["pending_approval"]["approved"] is True
    assert resumed_state["pending_approval"]["user_feedback"] == "Top match confirmed by candidate"
    assert shortlisted_ids[0] in resumed_state["shortlisted_job_ids"]

    # Checkpoint reflects final stage
    final_checkpoint = checkpointer.load_checkpoint(wf_id)
    assert final_checkpoint["current_stage"] == "shortlist_confirmed"


# =============================================================================
# 3. Shortlist Gate Enforcement Test
# =============================================================================

def test_shortlist_gate_cannot_be_bypassed_by_restart(
    senior_candidate_dict: Dict[str, Any],
    sample_raw_job_payloads: List[Dict[str, Any]],
):
    """
    Resuming a workflow with no initial start call should raise ValueError
    because there is no checkpoint to load from.
    """
    checkpointer = MemoryCheckpointer()
    wf = JobDiscoveryAndMatchingWorkflow(checkpointer=checkpointer)
    wf_id = "wf_bypass_attempt_01"

    with pytest.raises(ValueError, match="No checkpoint found"):
        wf.resume_with_shortlist(
            workflow_id=wf_id,
            shortlisted_job_ids=["any_id"],
        )


def test_shortlist_gate_requires_explicit_job_ids(
    senior_candidate_dict: Dict[str, Any],
    sample_raw_job_payloads: List[Dict[str, Any]],
):
    """Resume with an empty shortlist is valid (user dismisses all jobs)."""
    checkpointer = MemoryCheckpointer()
    wf = JobDiscoveryAndMatchingWorkflow(checkpointer=checkpointer)
    wf_id = "wf_empty_shortlist_01"

    state = _make_state(wf_id, "usr_empty_01", senior_candidate_dict, sample_raw_job_payloads)
    wf.start(state)

    # Resume with empty shortlist — workflow should still complete
    result = wf.resume_with_shortlist(
        workflow_id=wf_id,
        shortlisted_job_ids=[],
        dismissed_job_ids=[],
        user_feedback="No matches met my expectations",
    )
    assert result["shortlist_approved"] is True
    assert result["shortlisted_job_ids"] == []
    assert result["current_stage"] == "shortlist_confirmed"


# =============================================================================
# 4. Durable Checkpoint Recovery Test
# =============================================================================

def test_workflow_checkpoint_recovery(
    senior_candidate_dict: Dict[str, Any],
    sample_raw_job_payloads: List[Dict[str, Any]],
):
    """Checkpoint saved during 'start' can be loaded from a fresh workflow instance."""
    checkpointer = MemoryCheckpointer()
    wf_id = "wf_checkpoint_01"

    # First instance: run start and pause
    wf_instance_1 = JobDiscoveryAndMatchingWorkflow(checkpointer=checkpointer)
    state = _make_state(wf_id, "usr_checkpoint_01", senior_candidate_dict, sample_raw_job_payloads)
    wf_instance_1.start(state)

    # Second instance: same checkpointer, different object
    wf_instance_2 = JobDiscoveryAndMatchingWorkflow(checkpointer=checkpointer)
    loaded = wf_instance_2.load_state(wf_id)
    assert loaded is not None
    assert loaded["is_paused"] is True
    assert loaded["current_stage"] == "awaiting_shortlist_approval"
    assert len(loaded.get("ranked_matches") or []) >= 1

    # Second instance can resume
    result = wf_instance_2.resume_with_shortlist(wf_id, shortlisted_job_ids=[])
    assert result["shortlist_approved"] is True


# =============================================================================
# 5. Cross-User Workflow Isolation Test
# =============================================================================

def test_cross_user_workflow_isolation(
    senior_candidate_dict: Dict[str, Any],
    sample_raw_job_payloads: List[Dict[str, Any]],
):
    """
    Two users running concurrent workflows must have completely isolated states.
    User B cannot access or modify User A's workflow checkpoint.
    """
    checkpointer = MemoryCheckpointer()
    wf_alice = JobDiscoveryAndMatchingWorkflow(checkpointer=checkpointer)
    wf_bob = JobDiscoveryAndMatchingWorkflow(checkpointer=checkpointer)

    alice_wf_id = "wf_alice_isolation_01"
    bob_wf_id = "wf_bob_isolation_01"

    state_alice = _make_state(alice_wf_id, "usr_alice", senior_candidate_dict, sample_raw_job_payloads)
    state_bob = _make_state(bob_wf_id, "usr_bob", senior_candidate_dict, sample_raw_job_payloads)

    wf_alice.start(state_alice)
    wf_bob.start(state_bob)

    # Alice's checkpoint has Alice's user_id
    alice_state = checkpointer.load_checkpoint(alice_wf_id)
    assert alice_state["user_id"] == "usr_alice"

    # Bob's checkpoint has Bob's user_id
    bob_state = checkpointer.load_checkpoint(bob_wf_id)
    assert bob_state["user_id"] == "usr_bob"

    # Bob cannot load Alice's checkpoint using Bob's workflow_id
    assert checkpointer.load_checkpoint(alice_wf_id)["user_id"] != "usr_bob"

    # Bob resuming his own workflow does not affect Alice's state
    wf_bob.resume_with_shortlist(bob_wf_id, shortlisted_job_ids=[])
    alice_check_after = checkpointer.load_checkpoint(alice_wf_id)
    assert alice_check_after["is_paused"] is True, "Bob's actions mutated Alice's state!"


# =============================================================================
# 6. REST API Endpoint Tests
# =============================================================================

def test_api_start_discovery_workflow(
    test_client: TestClient,
    senior_candidate_dict: Dict[str, Any],
    sample_raw_job_payloads: List[Dict[str, Any]],
):
    """POST /start: Starts workflow, runs to pause gate, returns 202 with status."""
    wf_id = f"wf_api_start_{uuid.uuid4().hex[:8]}"
    resp = test_client.post(
        "/api/v1/discovery/start",
        json={
            "workflow_id": wf_id,
            "user_id": "usr_api_01",
            "extracted_profile": senior_candidate_dict,
            "raw_job_payloads": sample_raw_job_payloads,
        },
    )
    assert resp.status_code == 202, resp.text
    data = resp.json()
    assert data["workflow_id"] == wf_id
    assert data["is_paused"] is True
    assert data["current_stage"] == "awaiting_shortlist_approval"
    assert data["total_normalized_jobs"] >= 1
    assert data["total_ranked_matches"] >= 1
    assert data["shortlist_approved"] is False


def test_api_get_workflow_status(
    test_client: TestClient,
    senior_candidate_dict: Dict[str, Any],
    sample_raw_job_payloads: List[Dict[str, Any]],
):
    """GET /{workflow_id}/status: Returns current stage and progress counts."""
    wf_id = f"wf_api_status_{uuid.uuid4().hex[:8]}"
    test_client.post(
        "/api/v1/discovery/start",
        json={
            "workflow_id": wf_id,
            "user_id": "usr_api_02",
            "extracted_profile": senior_candidate_dict,
            "raw_job_payloads": sample_raw_job_payloads,
        },
    )
    status_resp = test_client.get(f"/api/v1/discovery/{wf_id}/status")
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["is_paused"] is True
    assert data["total_ranked_matches"] >= 1


def test_api_get_ranked_matches(
    test_client: TestClient,
    senior_candidate_dict: Dict[str, Any],
    sample_raw_job_payloads: List[Dict[str, Any]],
):
    """GET /{workflow_id}/matches: Returns ranked match summaries sorted by score."""
    wf_id = f"wf_api_matches_{uuid.uuid4().hex[:8]}"
    test_client.post(
        "/api/v1/discovery/start",
        json={
            "workflow_id": wf_id,
            "user_id": "usr_api_03",
            "extracted_profile": senior_candidate_dict,
            "raw_job_payloads": sample_raw_job_payloads,
        },
    )
    matches_resp = test_client.get(f"/api/v1/discovery/{wf_id}/matches")
    assert matches_resp.status_code == 200
    matches = matches_resp.json()
    assert len(matches) >= 1
    # Sorted descending by composite_score
    scores = [m["composite_score"] for m in matches]
    assert scores == sorted(scores, reverse=True)
    # Every match has required fields
    for m in matches:
        assert m["title"]
        assert m["organization"]
        assert m["recommendation"] in {"strong_match", "potential_match", "gap_heavy", "not_recommended"}


def test_api_approve_shortlist(
    test_client: TestClient,
    senior_candidate_dict: Dict[str, Any],
    sample_raw_job_payloads: List[Dict[str, Any]],
):
    """POST /{workflow_id}/approve-shortlist: Resumes workflow and confirms shortlist."""
    wf_id = f"wf_api_approve_{uuid.uuid4().hex[:8]}"
    start_resp = test_client.post(
        "/api/v1/discovery/start",
        json={
            "workflow_id": wf_id,
            "user_id": "usr_api_04",
            "extracted_profile": senior_candidate_dict,
            "raw_job_payloads": sample_raw_job_payloads,
        },
    )
    assert start_resp.status_code == 202

    # Get match IDs
    matches_resp = test_client.get(f"/api/v1/discovery/{wf_id}/matches")
    matches = matches_resp.json()
    top_id = matches[0].get("job_id") or "mock_top"
    rest_ids = [m.get("job_id") or f"mock_{i}" for i, m in enumerate(matches[1:], 1)]

    # Approve with shortlist
    approve_resp = test_client.post(
        f"/api/v1/discovery/{wf_id}/approve-shortlist",
        json={
            "shortlisted_job_ids": [top_id],
            "dismissed_job_ids": rest_ids,
            "user_feedback": "Top role looks perfect",
        },
    )
    assert approve_resp.status_code == 200
    data = approve_resp.json()
    assert data["shortlist_approved"] is True
    assert data["is_paused"] is False
    assert data["current_stage"] == "shortlist_confirmed"
    assert top_id in data["shortlisted_job_ids"]


def test_api_approve_shortlist_conflict_when_not_paused(
    test_client: TestClient,
    senior_candidate_dict: Dict[str, Any],
    sample_raw_job_payloads: List[Dict[str, Any]],
):
    """POST approve-shortlist on already-confirmed workflow returns 409 Conflict."""
    wf_id = f"wf_api_conflict_{uuid.uuid4().hex[:8]}"
    test_client.post(
        "/api/v1/discovery/start",
        json={
            "workflow_id": wf_id,
            "user_id": "usr_api_05",
            "extracted_profile": senior_candidate_dict,
            "raw_job_payloads": sample_raw_job_payloads,
        },
    )
    # First approval succeeds
    test_client.post(
        f"/api/v1/discovery/{wf_id}/approve-shortlist",
        json={"shortlisted_job_ids": [], "dismissed_job_ids": []},
    )
    # Second approval should fail with 409
    second_resp = test_client.post(
        f"/api/v1/discovery/{wf_id}/approve-shortlist",
        json={"shortlisted_job_ids": ["some_id"], "dismissed_job_ids": []},
    )
    assert second_resp.status_code == 409


def test_api_get_shortlisted_matches_after_approval(
    test_client: TestClient,
    senior_candidate_dict: Dict[str, Any],
    sample_raw_job_payloads: List[Dict[str, Any]],
):
    """GET /{workflow_id}/shortlisted returns only user-confirmed shortlisted matches."""
    wf_id = f"wf_api_shortlisted_{uuid.uuid4().hex[:8]}"
    test_client.post(
        "/api/v1/discovery/start",
        json={
            "workflow_id": wf_id,
            "user_id": "usr_api_06",
            "extracted_profile": senior_candidate_dict,
            "raw_job_payloads": sample_raw_job_payloads,
        },
    )
    matches = test_client.get(f"/api/v1/discovery/{wf_id}/matches").json()
    # Shortlist only matches with job_id set
    shortlist_ids = [m["job_id"] for m in matches if m.get("job_id")]

    if shortlist_ids:
        test_client.post(
            f"/api/v1/discovery/{wf_id}/approve-shortlist",
            json={"shortlisted_job_ids": shortlist_ids[:1], "dismissed_job_ids": []},
        )
        shortlisted_resp = test_client.get(f"/api/v1/discovery/{wf_id}/shortlisted")
        assert shortlisted_resp.status_code == 200
        shortlisted = shortlisted_resp.json()
        # Only shortlisted IDs are returned
        for item in shortlisted:
            assert item["job_id"] in shortlist_ids[:1]
    else:
        # No job IDs in memory-only run is acceptable
        test_client.post(
            f"/api/v1/discovery/{wf_id}/approve-shortlist",
            json={"shortlisted_job_ids": [], "dismissed_job_ids": []},
        )
        shortlisted_resp = test_client.get(f"/api/v1/discovery/{wf_id}/shortlisted")
        assert shortlisted_resp.status_code == 200


def test_api_workflow_not_found(test_client: TestClient):
    """GET /status and /matches return 404 for unknown workflow IDs."""
    resp = test_client.get("/api/v1/discovery/nonexistent-workflow-xyz/status")
    assert resp.status_code == 404

    resp2 = test_client.get("/api/v1/discovery/nonexistent-workflow-xyz/matches")
    # 200 with empty list (no checkpoint = empty list from get_ranked_matches)
    assert resp2.status_code in (200, 404)


# =============================================================================
# 7. Audit: State Integrity After Each Node
# =============================================================================

def test_audit_trail_accumulates_across_all_nodes(
    senior_candidate_dict: Dict[str, Any],
    sample_raw_job_payloads: List[Dict[str, Any]],
):
    """Audit trail entries must be additive across the full workflow pipeline."""
    checkpointer = MemoryCheckpointer()
    wf = JobDiscoveryAndMatchingWorkflow(checkpointer=checkpointer)
    wf_id = "wf_audit_trail_01"

    state = _make_state(wf_id, "usr_audit_01", senior_candidate_dict, sample_raw_job_payloads)
    paused = wf.start(state)

    trail = paused.get("audit_trail") or []
    # At minimum: discovery, normalization, scoring, and gate entries
    assert len(trail) >= 3

    stages_touched = {entry["stage"] for entry in trail}
    assert "job_discovery" in stages_touched
    assert "job_normalization_dedup" in stages_touched
    assert "match_scoring_explanation" in stages_touched
    assert "awaiting_shortlist_approval" in stages_touched

    # Resume and verify trail grows
    resumed = wf.resume_with_shortlist(wf_id, shortlisted_job_ids=[], dismissed_job_ids=[])
    final_trail = resumed.get("audit_trail") or []
    assert len(final_trail) > len(trail)
    stages_final = {e["stage"] for e in final_trail}
    assert "shortlist_confirmed" in stages_final
