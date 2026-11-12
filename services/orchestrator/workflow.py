import uuid
from typing import Any, Dict, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from services.orchestrator.checkpointer import (
    BaseCheckpointer,
    default_checkpointer,
)
from services.orchestrator.state import AgentFlowWorkflowState


def node_profile_ingest(state: AgentFlowWorkflowState) -> Dict[str, Any]:
    """Process incoming raw resume text or file bytes and prepare validation payload."""
    trail = list(state.get("audit_trail") or [])
    trail.append({
        "stage": "profile_ingestion",
        "message": "Resume text received for parsing and fact extraction",
    })
    return {
        "current_stage": "profile_validation",
        "verified_facts": list(state.get("verified_facts") or []),
        "inferred_facts": list(state.get("inferred_facts") or []),
        "missing_fields": list(state.get("missing_fields") or []),
        "audit_trail": trail,
    }


def node_profile_validate(state: AgentFlowWorkflowState) -> Dict[str, Any]:
    """
    Validate parsed facts vs inferred facts.
    Emits an approval request and pauses at the human approval gate.
    """
    workflow_id = state.get("workflow_id", str(uuid.uuid4()))
    user_id = state.get("user_id", "default_user")

    approval_request = {
        "id": str(uuid.uuid4()),
        "workflow_id": workflow_id,
        "user_id": user_id,
        "approval_type": "profile_facts",
        "title": "Review Extracted Profile Facts",
        "description": "Please review extracted facts and confirm inferred or missing information.",
        "is_resolved": False,
    }

    trail = list(state.get("audit_trail") or [])
    trail.append({
        "stage": "awaiting_profile_confirmation",
        "message": "Workflow paused at human approval gate for profile review",
    })

    return {
        "current_stage": "awaiting_profile_confirmation",
        "is_paused": True,
        "pause_reason": "Human approval required to confirm parsed profile facts",
        "pending_approval": approval_request,
        "audit_trail": trail,
    }


def node_awaiting_confirmation(state: AgentFlowWorkflowState) -> Dict[str, Any]:
    """Node representing the paused approval gate."""
    return {
        "is_paused": True,
        "current_stage": "awaiting_profile_confirmation",
        "pause_reason": "Awaiting user confirmation of candidate profile facts",
    }


def node_profile_confirmed(state: AgentFlowWorkflowState) -> Dict[str, Any]:
    """Post-confirmation transition marking profile verified."""
    trail = list(state.get("audit_trail") or [])
    trail.append({
        "stage": "profile_confirmed",
        "message": "User confirmed profile facts. Profile marked verified.",
    })
    return {
        "current_stage": "profile_confirmed",
        "is_paused": False,
        "pause_reason": None,
        "audit_trail": trail,
    }


def build_profile_onboarding_graph(memory_saver: Optional[MemorySaver] = None):
    """
    Constructs and compiles the authoritative LangGraph StateGraph for profile onboarding.
    Enforces interrupt_before on the human confirmation gate ('awaiting_confirmation').
    """
    builder = StateGraph(AgentFlowWorkflowState)

    builder.add_node("profile_ingest", node_profile_ingest)
    builder.add_node("profile_validate", node_profile_validate)
    builder.add_node("awaiting_confirmation", node_awaiting_confirmation)
    builder.add_node("profile_confirmed", node_profile_confirmed)

    builder.add_edge(START, "profile_ingest")
    builder.add_edge("profile_ingest", "profile_validate")
    builder.add_edge("profile_validate", "awaiting_confirmation")
    builder.add_edge("awaiting_confirmation", "profile_confirmed")
    builder.add_edge("profile_confirmed", END)

    saver = memory_saver or MemorySaver()
    compiled_graph = builder.compile(
        checkpointer=saver,
        interrupt_before=["awaiting_confirmation"],
    )
    return compiled_graph


class ProfileOnboardingWorkflow:
    """
    Core LangGraph workflow authority for Profile Onboarding and Verification.
    Coordinates LangGraph StateGraph compilation, durable checkpointing,
    human approval pause gate ('awaiting_profile_confirmation'), and resume execution.
    """

    def __init__(
        self,
        checkpointer: Optional[BaseCheckpointer] = None,
        langgraph_saver: Optional[MemorySaver] = None,
    ):
        self.checkpointer = checkpointer or default_checkpointer
        self.langgraph_saver = langgraph_saver or MemorySaver()
        self.graph = build_profile_onboarding_graph(self.langgraph_saver)

    def run_step(self, state: AgentFlowWorkflowState) -> AgentFlowWorkflowState:
        """
        Execute the next logical workflow step according to the authoritative state machine.
        Invokes the LangGraph StateGraph compiled with non-bypassable interrupt_before.
        """
        workflow_id = state.get("workflow_id") or str(uuid.uuid4())
        state["workflow_id"] = workflow_id
        config = {"configurable": {"thread_id": workflow_id}}

        stage = state.get("current_stage", "profile_ingestion")

        if stage in ("profile_ingestion", "profile_validation"):
            graph_output = self.graph.invoke(dict(state), config=config)
            merged_state = {**state, **graph_output}
            merged_state["is_paused"] = True
            merged_state["current_stage"] = "awaiting_profile_confirmation"
            merged_state["pause_reason"] = "Human approval required to confirm parsed profile facts"
            self.checkpointer.save_checkpoint(workflow_id, merged_state, "awaiting_profile_confirmation")
            return merged_state

        elif stage == "awaiting_profile_confirmation":
            state["is_paused"] = True
            state["pause_reason"] = "Human approval required to confirm parsed profile facts"
            self.checkpointer.save_checkpoint(workflow_id, state, stage)
            return state

        elif stage == "profile_confirmed":
            return self._step_profile_confirmed(state)

        else:
            return state

    def resume_with_approval(
        self,
        workflow_id: str,
        confirmed_profile: Dict[str, Any],
        user_feedback: Optional[str] = None,
    ) -> AgentFlowWorkflowState:
        """
        Resume a paused workflow after explicit user confirmation.
        Updates state in LangGraph checkpointer and resumes past the pause gate.
        """
        state = self.checkpointer.load_checkpoint(workflow_id)
        if not state:
            raise ValueError(f"Workflow checkpoint not found for ID: {workflow_id}")

        if not state.get("is_paused"):
            return state

        # Resolve approval
        pending_approval = state.get("pending_approval") or {}
        pending_approval["is_resolved"] = True
        pending_approval["approved"] = True
        pending_approval["user_feedback"] = user_feedback
        state["pending_approval"] = pending_approval

        state["extracted_profile"] = confirmed_profile
        state["is_paused"] = False
        state["pause_reason"] = None
        state["current_stage"] = "profile_confirmed"

        audit_trail = list(state.get("audit_trail") or [])
        audit_trail.append({
            "stage": "profile_confirmed",
            "message": "User confirmed profile facts. Profile marked verified.",
        })
        state["audit_trail"] = audit_trail

        config = {"configurable": {"thread_id": workflow_id}}
        try:
            self.graph.update_state(
                config,
                {
                    "extracted_profile": confirmed_profile,
                    "is_paused": False,
                    "pause_reason": None,
                    "pending_approval": pending_approval,
                    "current_stage": "profile_confirmed",
                    "audit_trail": audit_trail,
                },
                as_node="awaiting_confirmation",
            )
            graph_output = self.graph.invoke(None, config=config)
            state.update(graph_output)
        except Exception:
            state["current_stage"] = "profile_confirmed"

        self.checkpointer.save_checkpoint(workflow_id, state, "profile_confirmed")
        return state

    def _step_profile_confirmed(self, state: AgentFlowWorkflowState) -> AgentFlowWorkflowState:
        state["current_stage"] = "ready_for_job_discovery"
        state["is_paused"] = False
        state["pause_reason"] = None
        self.checkpointer.save_checkpoint(state["workflow_id"], state, "ready_for_job_discovery")
        return state
