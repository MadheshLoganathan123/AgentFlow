from services.orchestrator.checkpointer import MemoryCheckpointer
from services.orchestrator.workflow import ProfileOnboardingWorkflow


def test_orchestrator_pause_and_resume():
    checkpointer = MemoryCheckpointer()
    workflow = ProfileOnboardingWorkflow(checkpointer=checkpointer)

    initial_state = {
        "workflow_id": "wf_test_1001",
        "user_id": "usr_test_1001",
        "current_stage": "profile_ingestion",
        "verified_facts": [{"skill": "Python"}],
        "inferred_facts": ["Deduced Seniority: Senior"],
        "is_paused": False,
        "audit_trail": []
    }

    # Step 1: Execute step -> should pause for human approval
    result_state = workflow.run_step(initial_state)

    assert result_state["is_paused"] is True
    assert result_state["current_stage"] == "awaiting_profile_confirmation"
    assert result_state["pending_approval"] is not None
    assert result_state["pending_approval"]["is_resolved"] is False

    # Checkpoint should be durably saved
    saved_state = checkpointer.load_checkpoint("wf_test_1001")
    assert saved_state is not None
    assert saved_state["is_paused"] is True

    # Step 2: Resume with human approval
    confirmed_profile = {
        "full_name": "Test Candidate",
        "skills": ["Python"],
        "is_profile_confirmed": True
    }
    resumed_state = workflow.resume_with_approval(
        "wf_test_1001",
        confirmed_profile=confirmed_profile,
        user_feedback="Verified by candidate"
    )

    assert resumed_state["is_paused"] is False
    assert resumed_state["current_stage"] == "profile_confirmed"
    assert resumed_state["pending_approval"]["is_resolved"] is True
    assert resumed_state["pending_approval"]["approved"] is True

