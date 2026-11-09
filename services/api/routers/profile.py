import uuid
from typing import Any, Dict, Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from packages.contracts.base import utc_now
from packages.contracts.profile import CandidateProfile, VerificationState
from services.api.services.extractor import ResumeExtractorService
from services.orchestrator.workflow import ProfileOnboardingWorkflow

router = APIRouter(prefix="/api/v1/profile", tags=["Profile Onboarding"])

# In-memory storage for Phase 1 demonstration and quick execution
_PROFILES_STORE: Dict[str, CandidateProfile] = {}
_WORKFLOWS_STORE: Dict[str, ProfileOnboardingWorkflow] = {}


class ProfileUploadResponse(BaseModel):
    workflow_id: str
    profile_id: str
    message: str
    profile: CandidateProfile


class ProfileConfirmRequest(BaseModel):
    user_feedback: Optional[str] = None
    confirmed_fields: Optional[Dict[str, Any]] = None


@router.post("/upload-resume", response_model=ProfileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: Optional[UploadFile] = File(None),
    raw_text: Optional[str] = Form(None),
    user_id: str = Form("usr_default_01")
):
    """
    Ingest a resume (PDF or plain text), extract verifiable evidence, and initialize
    a LangGraph onboarding workflow paused at the human verification gate.
    """
    extracted_text = ""
    if file:
        file_bytes = await file.read()
        if file.filename.lower().endswith(".pdf"):
            try:
                extracted_text = ResumeExtractorService.extract_text_from_pdf(file_bytes)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to extract PDF text: {str(e)}")
        else:
            extracted_text = file_bytes.decode("utf-8", errors="ignore")
    elif raw_text:
        extracted_text = raw_text
    else:
        raise HTTPException(status_code=400, detail="Either 'file' or 'raw_text' must be provided.")

    if not extracted_text.strip():
        raise HTTPException(status_code=400, detail="Resume content is empty.")

    # 1. Parse structured candidate profile
    profile = ResumeExtractorService.parse_profile(extracted_text, user_id=user_id)
    profile_id = f"prof_{uuid.uuid4().hex[:10]}"
    profile.id = profile_id
    _PROFILES_STORE[profile_id] = profile

    # 2. Initialize LangGraph workflow
    workflow_id = f"wf_{uuid.uuid4().hex[:10]}"
    workflow = ProfileOnboardingWorkflow()
    _WORKFLOWS_STORE[workflow_id] = workflow

    initial_state = {
        "workflow_id": workflow_id,
        "user_id": user_id,
        "current_stage": "profile_ingestion",
        "raw_resume_text": extracted_text,
        "extracted_profile": profile.model_dump(),
        "verified_facts": [skill.model_dump() for skill in profile.skills],
        "inferred_facts": profile.inferred_fields,
        "missing_fields": [m.model_dump() for m in profile.missing_fields],
        "audit_trail": []
    }

    # Run step 1: will pause at human approval gate
    workflow.run_step(initial_state)

    return ProfileUploadResponse(
        workflow_id=workflow_id,
        profile_id=profile_id,
        message="Resume extracted successfully. Workflow is paused at human confirmation gate.",
        profile=profile
    )


@router.get("/{profile_id}", response_model=CandidateProfile)
async def get_profile(profile_id: str):
    """Retrieve structured candidate profile by ID."""
    profile = _PROFILES_STORE.get(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile not found with ID {profile_id}")
    return profile


@router.put("/{profile_id}", response_model=CandidateProfile)
async def update_profile(profile_id: str, updated_data: CandidateProfile):
    """Allow user to edit and correct extracted profile attributes."""
    if profile_id not in _PROFILES_STORE:
        raise HTTPException(status_code=404, detail="Profile not found.")
    updated_data.id = profile_id
    _PROFILES_STORE[profile_id] = updated_data
    return updated_data


@router.post("/{profile_id}/confirm", response_model=CandidateProfile)
async def confirm_profile(profile_id: str, payload: ProfileConfirmRequest):
    """
    Explicit user confirmation control.
    Transitions profile to verified and resumes paused LangGraph workflow.
    """
    profile = _PROFILES_STORE.get(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")

    if payload.confirmed_fields:
        # Merge confirmed fields
        for key, val in payload.confirmed_fields.items():
            if hasattr(profile, key):
                setattr(profile, key, val)

    profile.is_profile_confirmed = True
    profile.confirmed_at = utc_now().isoformat()
    _PROFILES_STORE[profile_id] = profile

    return profile

