import uuid
from typing import Any, Dict, Optional
from services.orchestrator.checkpointer import BaseCheckpointer, default_checkpointer
from services.orchestrator.state import AgentFlowWorkflowState


class ProfileOnboardingWorkflow:
    """
    Core Week 1 LangGraph workflow skeleton for Profile Onboarding and Verification.
    Manages stage transitions, pause gates for human review, and durable recovery.
    """

    def __init__(self, checkpointer: Optional[BaseCheckpointer] = None):
        self.checkpointer = checkpointer or default_checkpointer

    def run_step(self, state: AgentFlowWorkflowState) -> AgentFlowWorkflowState:
        """
        Execute the next logical workflow step according to the authoritative state machine.
        """
        stage = state.get("current_stage", "profile_ingestion")

        if stage == "profile_ingestion":
            return self._step_ingest(state)
        elif stage == "profile_validation":
            return self._step_validate(state)
        elif stage == "awaiting_profile_confirmation":
            # Workflow is paused waiting for user action
            state["is_paused"] = True
            state["pause_reason"] = "Human approval required to confirm parsed profile facts"
            self.checkpointer.save_checkpoint(state["workflow_id"], state, stage)
            return state
        elif stage == "profile_confirmed":
            return self._step_profile_confirmed(state)
        else:
            return state

    def _step_ingest(self, state: AgentFlowWorkflowState) -> AgentFlowWorkflowState:
        """Process input resume text or file."""
        state["current_stage"] = "profile_validation"
        if not state.get("verified_facts"):
            state["verified_facts"] = []
        if not state.get("inferred_facts"):
            state["inferred_facts"] = []

        # Audit event
        state.setdefault("audit_trail", []).append({
            "stage": "profile_ingestion",
            "message": "Resume text received for parsing and fact extraction"
        })
        self.checkpointer.save_checkpoint(state["workflow_id"], state, "profile_validation")
        return self._step_validate(state)

    def _step_validate(self, state: AgentFlowWorkflowState) -> AgentFlowWorkflowState:
        """
        Validate parsed facts vs inferred facts.
        Pause and emit an approval request so unconfirmed inferences are NEVER treated as verified.
        """
        workflow_id = state["workflow_id"]
        user_id = state["user_id"]

        approval_request = {
            "id": str(uuid.uuid4()),
            "workflow_id": workflow_id,
            "user_id": user_id,
            "approval_type": "profile_facts",
            "title": "Review Extracted Profile Facts",
            "description": "Please review extracted facts and confirm inferred or missing information.",
            "is_resolved": False
        }

        state["pending_approval"] = approval_request
        state["current_stage"] = "awaiting_profile_confirmation"
        state["is_paused"] = True
        state["pause_reason"] = "Awaiting user confirmation of candidate profile facts"

        state.setdefault("audit_trail", []).append({
            "stage": "awaiting_profile_confirmation",
            "message": "Workflow paused at human approval gate for profile review"
        })

        self.checkpointer.save_checkpoint(workflow_id, state, "awaiting_profile_confirmation")
        return state

    def resume_with_approval(
        self,
        workflow_id: str,
        confirmed_profile: Dict[str, Any],
        user_feedback: Optional[str] = None
    ) -> AgentFlowWorkflowState:
        """
        Resume a paused workflow after explicit user confirmation.
        """
        state = self.checkpointer.load_checkpoint(workflow_id)
        if not state:
            raise ValueError(f"Workflow checkpoint not found for ID: {workflow_id}")

        if not state.get("is_paused"):
            return state

        # Resolve approval
        if state.get("pending_approval"):
            state["pending_approval"]["is_resolved"] = True
            state["pending_approval"]["approved"] = True
            state["pending_approval"]["user_feedback"] = user_feedback

        state["extracted_profile"] = confirmed_profile
        state["is_paused"] = False
        state["pause_reason"] = None
        state["current_stage"] = "profile_confirmed"

        state.setdefault("audit_trail", []).append({
            "stage": "profile_confirmed",
            "message": "User confirmed profile facts. Profile marked verified."
        })

        self.checkpointer.save_checkpoint(workflow_id, state, "profile_confirmed")
        return state

    def _step_profile_confirmed(self, state: AgentFlowWorkflowState) -> AgentFlowWorkflowState:
        state["current_stage"] = "ready_for_job_discovery"
        self.checkpointer.save_checkpoint(state["workflow_id"], state, "ready_for_job_discovery")
        return state

