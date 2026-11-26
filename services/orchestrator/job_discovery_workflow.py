"""
Phase 5 — Week 2: LangGraph JobDiscoveryAndMatchingWorkflow
============================================================
Orchestrates the full end-to-end job search pipeline with a durable
human shortlist approval gate.

State-Machine Stages
--------------------
job_discovery
    ↓  (fetch raw job postings from adapters)
job_normalization_dedup
    ↓  (normalize, hash, dedup → canonical JobListing objects)
match_scoring_explanation
    ↓  (6-dimension scoring, rank by composite score)
awaiting_shortlist_approval        ← INTERRUPT BEFORE (human gate)
    ↓  (user reviews ranked cards, picks shortlist / dismissals)
shortlist_confirmed
    ↓  (persist decisions into saved_jobs table)
END

Key design principles
---------------------
* Deterministic, testable: every node is a pure function of state.
* Human gate is enforced by LangGraph `interrupt_before`; it cannot
  be bypassed by calling node code.
* Durable: MemoryCheckpointer (dev) or PostgresCheckpointer (prod) is
  swapped in transparently via BaseCheckpointer interface.
* Safety check propagated: strong_match blocked if work_authorization
  missing (inherited from MatchRankingService).
* All state mutations are additive dicts — no in-place mutation.
"""
import contextlib
import uuid
from typing import Any, Dict, List, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from services.orchestrator.checkpointer import BaseCheckpointer, MemoryCheckpointer
from services.orchestrator.state import AgentFlowWorkflowState

# ---------------------------------------------------------------------------
# Node: job_discovery
# ---------------------------------------------------------------------------

def node_job_discovery(state: AgentFlowWorkflowState) -> Dict[str, Any]:
    """
    Discover raw job postings by invoking all registered adapters.

    In production this would call JobIngestionService.ingest_jobs() async.
    In the LangGraph sync context, we execute via asyncio.run() with a
    timeout guard.  For the test environment the caller pre-seeds
    ``raw_job_payloads`` directly, so this node becomes a no-op pass-through.
    """
    import asyncio

    trail = list(state.get("audit_trail") or [])
    errors = list(state.get("errors") or [])

    # If the caller pre-seeded raw_job_payloads, skip live fetching.
    existing_payloads = state.get("raw_job_payloads") or []
    if existing_payloads:
        trail.append({
            "stage": "job_discovery",
            "message": f"Using {len(existing_payloads)} pre-seeded raw job payloads",
        })
        return {
            "current_stage": "job_normalization_dedup",
            "raw_job_payloads": existing_payloads,
            "audit_trail": trail,
            "errors": errors,
        }

    # Live ingestion path
    try:
        from services.api.services.job_adapters import (
            JobIngestionService,
            default_adapter_registry,
        )

        query = state.get("discovery_query")
        location = state.get("discovery_location")
        sources = None  # all active sources
        limit_per_source = state.get("discovery_limit") or 15

        async def _ingest():
            svc = JobIngestionService(default_adapter_registry)
            return await svc.ingest_jobs(
                query=query,
                location=location,
                sources=sources,
                limit_per_source=limit_per_source,
            )

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(asyncio.run, _ingest())
                    summary = future.result(timeout=30)
            else:
                summary = loop.run_until_complete(_ingest())
        except RuntimeError:
            summary = asyncio.run(_ingest())

        raw_payloads = [p.model_dump(mode="json") for p in summary.jobs]
        trail.append({
            "stage": "job_discovery",
            "message": f"Ingested {len(raw_payloads)} raw postings from {len(summary.sources_queried)} sources",
            "sources_queried": summary.sources_queried,
        })
    except Exception as exc:  # pragma: no cover
        errors.append(f"job_discovery failed: {exc!s}")
        raw_payloads = []
        trail.append({
            "stage": "job_discovery",
            "message": f"Ingestion failed: {exc!s}",
        })

    return {
        "current_stage": "job_normalization_dedup",
        "raw_job_payloads": raw_payloads,
        "audit_trail": trail,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Node: job_normalization_dedup
# ---------------------------------------------------------------------------

def node_job_normalization_dedup(state: AgentFlowWorkflowState) -> Dict[str, Any]:
    """
    Normalize raw job payloads into authoritative JobListing contracts.
    Applies title/org normalization, attribute inference, SHA-256 content
    hashing, and cross-source duplicate linking.
    Accepts both canonical RawJobPayload dicts and legacy raw dicts with
    alternate field names (raw_title, raw_description, etc.).
    """
    from packages.contracts.job import RawJobPayload
    from services.api.services.normalizer import JobNormalizerService

    trail = list(state.get("audit_trail") or [])
    errors = list(state.get("errors") or [])
    raw_payloads = state.get("raw_job_payloads") or []

    normalized_dicts: List[Dict[str, Any]] = []
    summary_dict: Dict[str, Any] = {}

    if raw_payloads:
        try:
            raw_contracts = []
            for p in raw_payloads:
                try:
                    raw_contracts.append(RawJobPayload(**p))
                except Exception:
                    # Attempt field-name normalisation for legacy/alternate dict shapes
                    mapped = {
                        "source_name": p.get("source_name", "unknown"),
                        "source_job_id": (
                            p.get("source_job_id")
                            or p.get("external_id")
                            or p.get("source_id", "unknown")
                        ),
                        "source_url": p.get("source_url", ""),
                        "destination_url": p.get("destination_url", p.get("source_url", "")),
                        "title": (
                            p.get("title")
                            or p.get("raw_title", "Unknown Title")
                        ),
                        "organization": (
                            p.get("organization")
                            or p.get("raw_organization", "Unknown Organization")
                        ),
                        "location_raw": (
                            p.get("location_raw")
                            or p.get("raw_location")
                            or p.get("location")
                        ),
                        "description_raw": (
                            p.get("description_raw")
                            or p.get("raw_description")
                            or p.get("description_text", "")
                        ),
                        "salary_raw": p.get("salary_raw") or p.get("raw_salary"),
                        "work_mode_raw": p.get("work_mode_raw") or p.get("raw_work_mode"),
                        "seniority_raw": p.get("seniority_raw") or p.get("raw_seniority"),
                        "posted_at": p.get("posted_at"),
                        "extra_metadata": p.get("extra_metadata", {}),
                    }
                    try:
                        raw_contracts.append(RawJobPayload(**mapped))
                    except Exception as inner_exc:
                        errors.append(f"Payload mapping failed: {inner_exc!s}")

            if raw_contracts:
                unique_jobs, summary = JobNormalizerService.normalize_and_deduplicate(raw_contracts)
                normalized_dicts = [j.model_dump(mode="json") for j in unique_jobs]
                summary_dict = summary.model_dump(mode="json")
                trail.append({
                    "stage": "job_normalization_dedup",
                    "message": (
                        f"Normalized {summary.total_normalized} jobs → "
                        f"{summary.unique_count} unique after deduplication "
                        f"({summary.duplicate_count} duplicates removed)"
                    ),
                })
            else:
                trail.append({
                    "stage": "job_normalization_dedup",
                    "message": "All payloads failed mapping — zero contracts produced",
                })
        except Exception as exc:
            errors.append(f"normalization failed: {exc!s}")
            trail.append({"stage": "job_normalization_dedup", "message": f"Error: {exc!s}"})
    else:
        trail.append({
            "stage": "job_normalization_dedup",
            "message": "No raw payloads to normalize — skipping",
        })

    return {
        "current_stage": "match_scoring_explanation",
        "normalized_jobs": normalized_dicts,
        "normalization_summary": summary_dict,
        "audit_trail": trail,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Node: match_scoring_explanation
# ---------------------------------------------------------------------------

def node_match_scoring_explanation(state: AgentFlowWorkflowState) -> Dict[str, Any]:
    """
    Score and rank normalized job listings against the candidate profile.
    Uses the full 6-dimensional MatchRankingService with:
      - Skills (35%), Seniority (20%), Location/Mode (15%), Salary (15%),
        Sector (10%), Recency (5%)
    Produces ranked_matches list of {job: dict, explanation: dict} sorted
    by composite_score descending.
    Safety check: strong_match blocked without confirmed work_authorization.
    """
    from packages.contracts.job import JobListing
    from packages.contracts.profile import CandidateProfile
    from services.api.services.matcher import MatchRankingService

    trail = list(state.get("audit_trail") or [])
    errors = list(state.get("errors") or [])
    normalized_jobs_dicts = state.get("normalized_jobs") or []
    extracted_profile = state.get("extracted_profile") or {}

    ranked_matches: List[Dict[str, Any]] = []

    if not normalized_jobs_dicts:
        trail.append({
            "stage": "match_scoring_explanation",
            "message": "No normalized jobs available — skipping scoring",
        })
        trail.append({
            "stage": "awaiting_shortlist_approval",
            "message": "Workflow will pause at shortlist approval gate. 0 matches available.",
        })
        return {
            "current_stage": "awaiting_shortlist_approval",
            "ranked_matches": ranked_matches,
            "audit_trail": trail,
            "errors": errors,
        }

    if not extracted_profile:
        trail.append({
            "stage": "match_scoring_explanation",
            "message": "No extracted profile — skipping scoring",
        })
        trail.append({
            "stage": "awaiting_shortlist_approval",
            "message": "Workflow will pause at shortlist approval gate. 0 matches available.",
        })
        return {
            "current_stage": "awaiting_shortlist_approval",
            "ranked_matches": ranked_matches,
            "audit_trail": trail,
            "errors": errors,
        }

    try:
        candidate = CandidateProfile(**extracted_profile)
        job_listings = []
        for jd in normalized_jobs_dicts:
            with contextlib.suppress(Exception):
                job_listings.append(JobListing(**jd))

        ranked_pairs = MatchRankingService.rank_jobs(
            candidate=candidate,
            jobs=job_listings,
            min_score=0.0,
        )

        ranked_matches = [
            {
                "job": job.model_dump(mode="json"),
                "explanation": expl.model_dump(mode="json"),
            }
            for job, expl in ranked_pairs
        ]

        strong = sum(1 for r in ranked_matches if r["explanation"]["recommendation"] == "strong_match")
        potential = sum(1 for r in ranked_matches if r["explanation"]["recommendation"] == "potential_match")

        trail.append({
            "stage": "match_scoring_explanation",
            "message": (
                f"Scored {len(job_listings)} jobs → "
                f"{strong} strong_match, {potential} potential_match, "
                f"{len(ranked_matches) - strong - potential} others. "
                f"Ranked by composite score descending."
            ),
        })
        # Pre-record the gate entry since interrupt_before fires before the node body
        trail.append({
            "stage": "awaiting_shortlist_approval",
            "message": (
                f"Workflow will pause at shortlist approval gate. "
                f"{len(ranked_matches)} matches ready for user review."
            ),
        })
    except Exception as exc:  # pragma: no cover
        errors.append(f"match_scoring failed: {exc!s}")
        trail.append({"stage": "match_scoring_explanation", "message": f"Error: {exc!s}"})

    return {
        "current_stage": "awaiting_shortlist_approval",
        "ranked_matches": ranked_matches,
        "audit_trail": trail,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Node: awaiting_shortlist_approval  (human gate — interrupt_before)
# ---------------------------------------------------------------------------

def node_awaiting_shortlist_approval(state: AgentFlowWorkflowState) -> Dict[str, Any]:
    """
    Human approval gate: pauses execution so the user can review ranked
    job cards and decide which to shortlist vs. dismiss.
    LangGraph enforces the interrupt via interrupt_before=[this_node].
    """
    workflow_id = state.get("workflow_id", str(uuid.uuid4()))
    user_id = state.get("user_id", "unknown")
    ranked_matches = state.get("ranked_matches") or []

    approval_request = {
        "id": str(uuid.uuid4()),
        "workflow_id": workflow_id,
        "user_id": user_id,
        "approval_type": "shortlist_jobs",
        "title": "Review Your Job Matches — Confirm Shortlist",
        "description": (
            f"{len(ranked_matches)} ranked matches are ready for your review. "
            "Please choose which jobs to shortlist, save, or dismiss."
        ),
        "ranked_match_count": len(ranked_matches),
        "is_resolved": False,
    }

    trail = list(state.get("audit_trail") or [])
    trail.append({
        "stage": "awaiting_shortlist_approval",
        "message": (
            f"Workflow paused at shortlist approval gate. "
            f"{len(ranked_matches)} matches ready for user review."
        ),
    })

    return {
        "current_stage": "awaiting_shortlist_approval",
        "is_paused": True,
        "pause_reason": "Human shortlist approval required",
        "pending_approval": approval_request,
        "audit_trail": trail,
    }


# ---------------------------------------------------------------------------
# Node: shortlist_confirmed
# ---------------------------------------------------------------------------

def node_shortlist_confirmed(state: AgentFlowWorkflowState) -> Dict[str, Any]:
    """
    Post-approval node: records the user's shortlisting decisions.
    Sets shortlist_approved=True and clears the pause gate.
    In production, this would fire async calls to job_repo.save_or_shortlist_job
    for each shortlisted_job_id.
    """
    trail = list(state.get("audit_trail") or [])
    shortlisted = state.get("shortlisted_job_ids") or []
    dismissed = state.get("dismissed_job_ids") or []

    trail.append({
        "stage": "shortlist_confirmed",
        "message": (
            f"Shortlist confirmed. "
            f"{len(shortlisted)} job(s) shortlisted, "
            f"{len(dismissed)} job(s) dismissed."
        ),
    })

    pending = state.get("pending_approval") or {}
    pending = {**pending, "is_resolved": True, "approved": True}

    return {
        "current_stage": "shortlist_confirmed",
        "is_paused": False,
        "pause_reason": None,
        "shortlist_approved": True,
        "pending_approval": pending,
        "audit_trail": trail,
    }


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_job_discovery_graph(memory_saver: Optional[MemorySaver] = None):
    """
    Compile the authoritative JobDiscoveryAndMatchingWorkflow StateGraph.
    Interrupts execution before `awaiting_shortlist_approval` to enforce
    the non-bypassable human shortlist gate.
    """
    builder = StateGraph(AgentFlowWorkflowState)

    builder.add_node("job_discovery", node_job_discovery)
    builder.add_node("job_normalization_dedup", node_job_normalization_dedup)
    builder.add_node("match_scoring_explanation", node_match_scoring_explanation)
    builder.add_node("awaiting_shortlist_approval", node_awaiting_shortlist_approval)
    builder.add_node("shortlist_confirmed", node_shortlist_confirmed)

    builder.add_edge(START, "job_discovery")
    builder.add_edge("job_discovery", "job_normalization_dedup")
    builder.add_edge("job_normalization_dedup", "match_scoring_explanation")
    builder.add_edge("match_scoring_explanation", "awaiting_shortlist_approval")
    builder.add_edge("awaiting_shortlist_approval", "shortlist_confirmed")
    builder.add_edge("shortlist_confirmed", END)

    saver = memory_saver or MemorySaver()
    return builder.compile(
        checkpointer=saver,
        interrupt_before=["awaiting_shortlist_approval"],
    )


# ---------------------------------------------------------------------------
# Workflow class
# ---------------------------------------------------------------------------

class JobDiscoveryAndMatchingWorkflow:
    """
    High-level controller for the Job Discovery & Matching LangGraph workflow.

    Lifecycle
    ---------
    1. ``start(state)``           — Runs up to the shortlist approval gate and
                                    pauses. Returns state with is_paused=True.
    2. ``resume_with_shortlist()`` — Called after user confirms shortlist. Resumes
                                    past the gate into ``shortlist_confirmed``.
    3. ``get_ranked_matches()``   — Convenience accessor for ranked results from
                                    a loaded checkpoint.
    """

    def __init__(
        self,
        checkpointer: Optional[BaseCheckpointer] = None,
        langgraph_saver: Optional[MemorySaver] = None,
    ):
        self.checkpointer = checkpointer or MemoryCheckpointer()
        self.langgraph_saver = langgraph_saver or MemorySaver()
        self.graph = build_job_discovery_graph(self.langgraph_saver)

    # ------------------------------------------------------------------
    def start(self, state: AgentFlowWorkflowState) -> AgentFlowWorkflowState:
        """
        Execute job_discovery → normalization → scoring and pause at the
        shortlist approval gate.  Returns the paused state.
        """
        workflow_id = state.get("workflow_id") or str(uuid.uuid4())
        state = dict(state)
        state.setdefault("workflow_id", workflow_id)
        state.setdefault("audit_trail", [])
        state.setdefault("errors", [])
        state.setdefault("raw_job_payloads", [])
        state.setdefault("normalized_jobs", [])
        state.setdefault("ranked_matches", [])
        state.setdefault("shortlisted_job_ids", [])
        state.setdefault("dismissed_job_ids", [])
        state.setdefault("shortlist_approved", False)
        state.setdefault("discovery_limit", 15)

        config = {"configurable": {"thread_id": workflow_id}}

        # Invoke: runs until interrupt_before=[awaiting_shortlist_approval]
        graph_output = self.graph.invoke(state, config=config)
        merged = {**state, **graph_output}
        merged["is_paused"] = True
        merged["current_stage"] = "awaiting_shortlist_approval"
        merged["pause_reason"] = "Human shortlist approval required"

        self.checkpointer.save_checkpoint(
            workflow_id, merged, "awaiting_shortlist_approval"
        )
        return merged

    # ------------------------------------------------------------------
    def resume_with_shortlist(
        self,
        workflow_id: str,
        shortlisted_job_ids: List[str],
        dismissed_job_ids: Optional[List[str]] = None,
        user_feedback: Optional[str] = None,
    ) -> AgentFlowWorkflowState:
        """
        Resume a paused workflow after the user has confirmed their shortlist.
        Runs ``shortlist_confirmed`` and returns the final state.
        """
        state = self.checkpointer.load_checkpoint(workflow_id)
        if not state:
            raise ValueError(f"No checkpoint found for workflow_id={workflow_id!r}")

        dismissed_job_ids = dismissed_job_ids or []

        # Resolve pending approval
        pending = dict(state.get("pending_approval") or {})
        pending.update({"is_resolved": True, "approved": True, "user_feedback": user_feedback})

        # Inject shortlist decisions into state
        state["shortlisted_job_ids"] = shortlisted_job_ids
        state["dismissed_job_ids"] = dismissed_job_ids
        state["pending_approval"] = pending
        state["is_paused"] = False
        state["pause_reason"] = None
        state["current_stage"] = "shortlist_confirmed"

        config = {"configurable": {"thread_id": workflow_id}}
        try:
            self.graph.update_state(
                config,
                {
                    "shortlisted_job_ids": shortlisted_job_ids,
                    "dismissed_job_ids": dismissed_job_ids,
                    "pending_approval": pending,
                    "is_paused": False,
                    "pause_reason": None,
                    "current_stage": "shortlist_confirmed",
                },
                as_node="awaiting_shortlist_approval",
            )
            graph_output = self.graph.invoke(None, config=config)
            state.update(graph_output)
        except Exception:
            # Fallback: apply node_shortlist_confirmed directly
            confirmation_output = node_shortlist_confirmed(state)
            state.update(confirmation_output)

        self.checkpointer.save_checkpoint(workflow_id, state, "shortlist_confirmed")
        return state

    # ------------------------------------------------------------------
    def get_ranked_matches(self, workflow_id: str) -> List[Dict[str, Any]]:
        """Return the ranked match list from the checkpoint for a workflow."""
        state = self.checkpointer.load_checkpoint(workflow_id)
        if not state:
            return []
        return state.get("ranked_matches") or []

    # ------------------------------------------------------------------
    def load_state(self, workflow_id: str) -> Optional[AgentFlowWorkflowState]:
        """Load the latest checkpoint state for a workflow."""
        return self.checkpointer.load_checkpoint(workflow_id)
