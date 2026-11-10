import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from packages.contracts.base import utc_now
from packages.contracts.profile import CandidateProfile
from packages.db.repositories.profile_repo import ProfileRepository
from packages.db.session import get_async_session
from services.api.services.extractor import ResumeExtractorService
from services.orchestrator.workflow import ProfileOnboardingWorkflow

router = APIRouter(prefix="/api/v1/profile", tags=["Profile Onboarding"])

# In-memory storage for test execution and fast lookups
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
    user_id: str = Form("usr_default_01"),
    session: Optional[AsyncSession] = Depends(get_async_session),
):
    """
    Ingest a resume (PDF, DOCX, or plain text), extract verifiable evidence, and initialize
    a LangGraph onboarding workflow paused at the human verification gate.
    Optionally persists structured profile and evidence into PostgreSQL / database repository.
    """
    extracted_text = ""
    if file:
        file_bytes = await file.read()
        try:
            extracted_text = ResumeExtractorService.extract_text_from_file(file_bytes, file.filename)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to extract text from {file.filename}: {str(e)}",
            ) from e
    elif raw_text:
        extracted_text = raw_text
    else:
        raise HTTPException(status_code=400, detail="Either 'file' or 'raw_text' must be provided.")

    if not extracted_text.strip():
        raise HTTPException(status_code=400, detail="Resume content is empty or unreadable.")

    # 1. Parse structured candidate profile with lightweight open source models / deterministic extractor
    profile = await ResumeExtractorService.parse_profile_async(extracted_text, user_id=user_id)
    profile_id = f"prof_{uuid.uuid4().hex[:10]}"
    profile.id = profile_id

    # 2. Persist to database repository if active session is available
    if session:
        try:
            repo = ProfileRepository(session)
            await repo.create_profile(
                profile_id=profile_id,
                user_id=user_id,
                full_name=profile.full_name,
                email=profile.email,
                phone=profile.phone,
                primary_location=profile.primary_location,
                total_years_experience=profile.total_years_experience,
                work_authorization=profile.work_authorization,
                notice_period_days=profile.notice_period_days,
                raw_resume_text=extracted_text,
                structured_data=profile.model_dump(),
            )
            # Store evidence references in database
            for skill in profile.skills:
                if skill.evidence:
                    await repo.add_evidence(
                        profile_id=profile_id,
                        field_name=f"skill.{skill.name}",
                        source_type=skill.evidence.source_type,
                        source_identifier=skill.evidence.source_identifier,
                        raw_snippet=skill.evidence.raw_snippet,
                        confidence_score=skill.evidence.confidence_score,
                        is_inferred=skill.evidence.is_inferred,
                        is_user_confirmed=skill.evidence.is_user_confirmed,
                    )
        except Exception:
            # Fall back to in-memory store cleanly if DB connection is unavailable in local testing
            pass

    _PROFILES_STORE[profile_id] = profile

    # 3. Initialize LangGraph workflow paused at human confirmation gate
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
        "audit_trail": [],
    }

    workflow.run_step(initial_state)

    return ProfileUploadResponse(
        workflow_id=workflow_id,
        profile_id=profile_id,
        message="Resume extracted successfully. Workflow is paused at human confirmation gate.",
        profile=profile,
    )


@router.get("/{profile_id}", response_model=CandidateProfile)
async def get_profile(
    profile_id: str,
    user_id: Optional[str] = None,
    session: Optional[AsyncSession] = Depends(get_async_session),
):
    """Retrieve structured candidate profile by ID."""
    if profile_id in _PROFILES_STORE:
        return _PROFILES_STORE[profile_id]

    if session and user_id:
        try:
            repo = ProfileRepository(session)
            db_profile = await repo.get_by_id_for_user(profile_id, user_id)
            if db_profile and db_profile.structured_data:
                return CandidateProfile(**db_profile.structured_data)
        except Exception:
            pass

    raise HTTPException(status_code=404, detail=f"Profile not found with ID {profile_id}")


@router.put("/{profile_id}", response_model=CandidateProfile)
async def update_profile(
    profile_id: str,
    updated_data: CandidateProfile,
    user_id: Optional[str] = None,
    session: Optional[AsyncSession] = Depends(get_async_session),
):
    """Allow user to edit and correct extracted profile attributes."""
    if profile_id not in _PROFILES_STORE:
        raise HTTPException(status_code=404, detail="Profile not found.")

    updated_data.id = profile_id
    _PROFILES_STORE[profile_id] = updated_data

    if session and user_id:
        try:
            repo = ProfileRepository(session)
            await repo.confirm_profile(
                profile_id=profile_id,
                user_id=user_id,
                updated_fields=updated_data.model_dump(),
            )
        except Exception:
            pass

    return updated_data


@router.post("/{profile_id}/confirm", response_model=CandidateProfile)
async def confirm_profile(
    profile_id: str,
    payload: ProfileConfirmRequest,
    user_id: Optional[str] = None,
    session: Optional[AsyncSession] = Depends(get_async_session),
):
    """
    Explicit user confirmation control.
    Transitions profile to verified and resumes paused LangGraph workflow.
    """
    profile = _PROFILES_STORE.get(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")

    if payload.confirmed_fields:
        for key, val in payload.confirmed_fields.items():
            if hasattr(profile, key):
                setattr(profile, key, val)

    profile.is_profile_confirmed = True
    profile.confirmed_at = utc_now().isoformat()
    _PROFILES_STORE[profile_id] = profile

    if session and (user_id or profile.user_id):
        try:
            repo = ProfileRepository(session)
            await repo.confirm_profile(
                profile_id=profile_id,
                user_id=user_id or profile.user_id,
                updated_fields=payload.confirmed_fields,
            )
        except Exception:
            pass

    return profile
