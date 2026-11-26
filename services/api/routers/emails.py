import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from packages.contracts.email import (
    EmailDraft,
    EmailTone,
    EmailType,
)
from packages.contracts.job import JobListing
from packages.contracts.profile import CandidateProfile
from packages.db.models import EmailDraftModel
from packages.db.repositories.email_repo import EmailDraftRepository
from packages.db.repositories.job_repo import JobRepository
from packages.db.repositories.profile_repo import ProfileRepository
from packages.db.session import get_async_session
from services.api.services.email_writer import EmailWriterService

logger = logging.getLogger("agentflow.emails")

router = APIRouter(prefix="/api/v1/emails", tags=["Professional Email Drafting"])

_email_service = EmailWriterService()


class GenerateEmailRequest(BaseModel):
    user_id: str
    job_id: Optional[str] = None
    email_type: EmailType = EmailType.RECRUITER_OUTREACH
    recipient_name: Optional[str] = None
    recipient_role: Optional[str] = None
    tone: EmailTone = EmailTone.PROFESSIONAL
    extra_context: Optional[str] = None
    candidate_profile: Optional[CandidateProfile] = None
    job_listing: Optional[JobListing] = None
    save_to_drafts: bool = True


class UpdateEmailDraftRequest(BaseModel):
    user_id: str
    subject: Optional[str] = None
    body: Optional[str] = None
    call_to_action: Optional[str] = None
    tone: Optional[str] = None
    is_approved_by_user: Optional[bool] = None


def _model_to_contract(model: EmailDraftModel) -> EmailDraft:
    return EmailDraft(
        id=model.id,
        user_id=model.user_id,
        job_id=model.job_id,
        email_type=EmailType(model.email_type),
        recipient_name=model.recipient_name,
        recipient_role=model.recipient_role,
        subject=model.subject,
        body=model.body,
        call_to_action=model.call_to_action,
        tone=model.tone,
        recipient_assumptions=list(model.recipient_assumptions or []),
        personalization_evidence=list(model.personalization_evidence or []),
        missing_recipient_warnings=list(model.missing_recipient_warnings or []),
        variants=list(model.variants or []),
        is_approved_by_user=bool(model.is_approved_by_user),
    )


@router.post(
    "/generate",
    response_model=EmailDraft,
    status_code=status.HTTP_200_OK,
    summary="Generate personalized outreach email draft with 3 tone variants",
)
async def generate_email_endpoint(
    req: GenerateEmailRequest,
    session: AsyncSession = Depends(get_async_session),
) -> EmailDraft:
    """
    Produce a grounded, professional email draft (recruiter outreach, referral, follow-up, or thank-you).
    Strictly follows safety guidelines: never sends automatically, flags missing recipients, and includes tone variants.
    """
    candidate = req.candidate_profile
    job = req.job_listing

    # Load candidate profile from DB if not passed directly
    if candidate is None:
        profile_repo = ProfileRepository(session)
        profile_model = await profile_repo.get_profile_by_user_id(req.user_id)
        if not profile_model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Candidate profile not found for user {req.user_id}",
            )
        data = dict(profile_model.structured_data or {})
        data["id"] = profile_model.id
        data["user_id"] = profile_model.user_id
        data["full_name"] = profile_model.full_name
        data["email"] = profile_model.email
        data["phone"] = profile_model.phone
        data["primary_location"] = profile_model.primary_location
        data["total_years_experience"] = profile_model.total_years_experience
        data["work_authorization"] = profile_model.work_authorization
        data["notice_period_days"] = profile_model.notice_period_days
        data["raw_resume_text"] = profile_model.raw_resume_text
        candidate = CandidateProfile(**data)

    # Load job listing from DB if not passed directly
    if job is None:
        if not req.job_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either job_listing or job_id must be provided",
            )
        job_repo = JobRepository(session)
        job_model = await job_repo.get_job_by_id(req.job_id)
        if not job_model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job listing {req.job_id} not found",
            )
        job = job_repo._to_contract(job_model)

    draft = await _email_service.generate_draft(
        candidate=candidate,
        job=job,
        email_type=req.email_type,
        recipient_name=req.recipient_name,
        recipient_role=req.recipient_role,
        preferred_tone=req.tone,
        extra_context=req.extra_context,
    )

    if req.save_to_drafts:
        email_repo = EmailDraftRepository(session)
        evidence_dicts = [ev.model_dump(mode="json") for ev in draft.personalization_evidence]
        saved_model = await email_repo.save_draft(
            user_id=req.user_id,
            job_id=job.id,
            email_type=draft.email_type.value,
            subject=draft.subject,
            body=draft.body,
            call_to_action=draft.call_to_action,
            recipient_name=draft.recipient_name,
            recipient_role=draft.recipient_role,
            tone=draft.tone,
            recipient_assumptions=draft.recipient_assumptions,
            personalization_evidence=evidence_dicts,
            missing_recipient_warnings=draft.missing_recipient_warnings,
            variants=draft.variants,
            is_approved_by_user=False,
        )
        await session.commit()
        draft.id = saved_model.id

    return draft


@router.get(
    "/drafts",
    response_model=List[EmailDraft],
    summary="List saved email drafts for user with optional filters",
)
async def list_drafts_endpoint(
    user_id: str = Query(..., description="ID of the authenticated user"),
    job_id: Optional[str] = Query(None, description="Filter by job ID"),
    email_type: Optional[str] = Query(None, description="Filter by email type"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_async_session),
) -> List[EmailDraft]:
    """
    List outreach email drafts created by the user, strictly enforcing multi-tenant isolation.
    """
    email_repo = EmailDraftRepository(session)
    models = await email_repo.list_drafts_for_user(
        user_id=user_id,
        job_id=job_id,
        email_type=email_type,
        limit=limit,
        offset=offset,
    )
    return [_model_to_contract(m) for m in models]


@router.get(
    "/drafts/{draft_id}",
    response_model=EmailDraft,
    summary="Retrieve single email draft by ID with user isolation",
)
async def get_draft_endpoint(
    draft_id: str,
    user_id: str = Query(..., description="ID of the authenticated user"),
    session: AsyncSession = Depends(get_async_session),
) -> EmailDraft:
    """
    Retrieve single draft by ID, verifying user ownership.
    """
    email_repo = EmailDraftRepository(session)
    model = await email_repo.get_draft(user_id=user_id, draft_id=draft_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Email draft {draft_id} not found or access denied",
        )
    return _model_to_contract(model)


@router.patch(
    "/drafts/{draft_id}",
    response_model=EmailDraft,
    summary="Update or approve email draft",
)
async def update_draft_endpoint(
    draft_id: str,
    req: UpdateEmailDraftRequest,
    session: AsyncSession = Depends(get_async_session),
) -> EmailDraft:
    """
    Edit draft subject, body, or call to action, or record human approval.
    """
    email_repo = EmailDraftRepository(session)
    updated = await email_repo.update_draft_content(
        user_id=req.user_id,
        draft_id=draft_id,
        subject=req.subject,
        body=req.body,
        call_to_action=req.call_to_action,
        tone=req.tone,
        is_approved_by_user=req.is_approved_by_user,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Email draft {draft_id} not found or access denied",
        )
    await session.commit()
    return _model_to_contract(updated)


@router.delete(
    "/drafts/{draft_id}",
    response_model=Dict[str, Any],
    summary="Delete email draft with user isolation",
)
async def delete_draft_endpoint(
    draft_id: str,
    user_id: str = Query(..., description="ID of the authenticated user"),
    session: AsyncSession = Depends(get_async_session),
) -> Dict[str, Any]:
    """
    Delete an email draft scoped strictly to the authenticated user.
    """
    email_repo = EmailDraftRepository(session)
    deleted = await email_repo.delete_draft(user_id=user_id, draft_id=draft_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Email draft {draft_id} not found or access denied",
        )
    await session.commit()
    return {"message": "Email draft deleted successfully", "id": draft_id}
