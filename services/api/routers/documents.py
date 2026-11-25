from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from packages.contracts.application import (
    ApplicationPackage,
    ApplicationQuestionAnswer,
    ApplicationQuestionSet,
    CoverLetter,
    ResumeDiffAnalysis,
    TailoredDocument,
    TailoredResume,
)
from packages.contracts.job import JobListing
from packages.contracts.policy import PolicyReviewResult
from packages.contracts.profile import CandidateProfile
from packages.db.repositories.job_repo import JobRepository
from packages.db.repositories.package_repo import ApplicationPackageRepository
from packages.db.repositories.profile_repo import ProfileRepository
from packages.db.session import get_async_session
from services.api.services.cover_letter_service import CoverLetterAndQuestionService
from services.api.services.policy_reviewer import PolicyReviewerService
from services.api.services.tailoring import ResumeTailoringService

logger = logging.getLogger("agentflow.documents")

router = APIRouter(prefix="/api/v1/documents", tags=["Application Documents & Tailoring"])

_tailoring_service = ResumeTailoringService()
_cover_letter_service = CoverLetterAndQuestionService()
_policy_reviewer = PolicyReviewerService()


class TailorResumeRequest(BaseModel):
    user_id: str
    job_id: Optional[str] = None
    candidate_profile: Optional[CandidateProfile] = None
    job_listing: Optional[JobListing] = None
    save_to_package: bool = True


class TailorResumeResponse(BaseModel):
    tailored_resume: TailoredResume
    package_id: Optional[str] = None
    package: Optional[ApplicationPackage] = None
    message: str = "Resume tailored successfully"


class CompareResumeRequest(BaseModel):
    candidate_profile: CandidateProfile
    job_listing: JobListing


class ApprovePackageRequest(BaseModel):
    user_id: str
    is_approved: bool = True


@router.post(
    "/tailor-resume",
    response_model=TailorResumeResponse,
    status_code=status.HTTP_200_OK,
    summary="Tailor resume variant for target job with diff analysis",
)
async def tailor_resume_endpoint(
    req: TailorResumeRequest,
    session: AsyncSession = Depends(get_async_session),
) -> TailorResumeResponse:
    """
    Generates a tailored resume variant matching the specified job listing.
    Enforces strict zero-fabrication: verified facts only, no phantom employers or metrics.
    Includes line-by-line diff analysis comparing original vs tailored sections.
    """
    candidate = req.candidate_profile
    job = req.job_listing

    # If candidate profile is not provided in body, load from DB
    if candidate is None:
        profile_repo = ProfileRepository(session)
        profile_model = await profile_repo.get_profile_by_user_id(req.user_id)
        if not profile_model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Candidate profile not found for user {req.user_id}",
            )
        # Reconstruct CandidateProfile from DB model
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

    # If job listing is not provided in body, load from DB
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

    # Execute resume tailoring
    tailored = await _tailoring_service.tailor_resume(candidate=candidate, job=job)

    # Persist package if requested
    package_id = None
    package_contract = None
    if req.save_to_package:
        package_repo = ApplicationPackageRepository(session)
        pkg_id = str(uuid.uuid4())
        doc_dict = _tailoring_service.to_tailored_document(tailored).model_dump(mode="json")

        saved_pkg = await package_repo.save_package(
            user_id=req.user_id,
            job_id=job.id,
            tailored_resume=doc_dict,
            unsupported_claim_warnings=tailored.unsupported_claim_warnings,
            package_id=pkg_id,
        )
        await session.commit()

        package_id = saved_pkg.id
        package_contract = _tailoring_service.to_application_package(
            user_id=req.user_id,
            tailored=tailored,
            package_id=saved_pkg.id,
        )

    return TailorResumeResponse(
        tailored_resume=tailored,
        package_id=package_id,
        package=package_contract,
    )


@router.post(
    "/compare-resume",
    response_model=ResumeDiffAnalysis,
    status_code=status.HTTP_200_OK,
    summary="Compute side-by-side diff between base resume and tailored variant",
)
async def compare_resume_endpoint(
    req: CompareResumeRequest,
) -> ResumeDiffAnalysis:
    """
    Computes diff analysis and changes between base candidate profile and job requirements.
    """
    tailored = await _tailoring_service.tailor_resume(candidate=req.candidate_profile, job=req.job_listing)
    return tailored.diff_analysis


@router.get(
    "/packages/{package_id}",
    response_model=Dict[str, Any],
    summary="Retrieve application package by ID with user isolation",
)
async def get_package_endpoint(
    package_id: str,
    user_id: str = Query(..., description="ID of the authenticated user"),
    session: AsyncSession = Depends(get_async_session),
) -> Dict[str, Any]:
    """
    Retrieve application package details with strict user data isolation.
    """
    package_repo = ApplicationPackageRepository(session)
    package = await package_repo.get_package(user_id=user_id, package_id=package_id)
    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application package {package_id} not found or access denied",
        )

    return {
        "id": package.id,
        "user_id": package.user_id,
        "job_id": package.job_id,
        "tailored_resume": package.tailored_resume,
        "cover_letter": package.cover_letter,
        "form_answers": package.form_answers,
        "unsupported_claim_warnings": package.unsupported_claim_warnings,
        "is_user_approved": package.is_user_approved,
        "approved_at": package.approved_at.isoformat() if package.approved_at else None,
        "updated_at": package.updated_at.isoformat() if package.updated_at else None,
    }


@router.get(
    "/packages/by-job/{job_id}",
    response_model=Dict[str, Any],
    summary="Retrieve package by job ID with user isolation",
)
async def get_package_by_job_endpoint(
    job_id: str,
    user_id: str = Query(..., description="ID of the authenticated user"),
    session: AsyncSession = Depends(get_async_session),
) -> Dict[str, Any]:
    """
    Retrieve package for a specific job with user isolation.
    """
    package_repo = ApplicationPackageRepository(session)
    package = await package_repo.get_package_by_job(user_id=user_id, job_id=job_id)
    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application package for job {job_id} not found",
        )

    return {
        "id": package.id,
        "user_id": package.user_id,
        "job_id": package.job_id,
        "tailored_resume": package.tailored_resume,
        "cover_letter": package.cover_letter,
        "form_answers": package.form_answers,
        "unsupported_claim_warnings": package.unsupported_claim_warnings,
        "is_user_approved": package.is_user_approved,
        "approved_at": package.approved_at.isoformat() if package.approved_at else None,
        "updated_at": package.updated_at.isoformat() if package.updated_at else None,
    }


@router.post(
    "/packages/{package_id}/approve",
    response_model=Dict[str, Any],
    summary="User approval control for application package",
)
async def approve_package_endpoint(
    package_id: str,
    req: ApprovePackageRequest,
    session: AsyncSession = Depends(get_async_session),
) -> Dict[str, Any]:
    """
    Explicit human approval gate for tailored application materials.
    """
    package_repo = ApplicationPackageRepository(session)
    updated = await package_repo.update_approval(
        user_id=req.user_id,
        package_id=package_id,
        is_user_approved=req.is_approved,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application package {package_id} not found or access denied",
        )
    await session.commit()

    return {
        "id": updated.id,
        "user_id": updated.user_id,
        "is_user_approved": updated.is_user_approved,
        "approved_at": updated.approved_at.isoformat() if updated.approved_at else None,
        "message": "Package approval status updated successfully",
    }


# ─── Week 3 Phase 2: Cover Letter & Application Answers ─────────────────────

class GenerateCoverLetterRequest(BaseModel):
    user_id: str
    job_id: Optional[str] = None
    candidate_profile: Optional[CandidateProfile] = None
    job_listing: Optional[JobListing] = None
    package_id: Optional[str] = None


class DraftAnswersRequest(BaseModel):
    user_id: str
    job_id: Optional[str] = None
    candidate_profile: Optional[CandidateProfile] = None
    job_listing: Optional[JobListing] = None
    custom_questions: Optional[List[str]] = None
    package_id: Optional[str] = None


class ReviewPackageRequest(BaseModel):
    user_id: str
    package_id: str


@router.post(
    "/generate-cover-letter",
    response_model=CoverLetter,
    status_code=status.HTTP_200_OK,
    summary="Generate tailored, fact-grounded cover letter with evidence provenance",
)
async def generate_cover_letter_endpoint(
    req: GenerateCoverLetterRequest,
    session: AsyncSession = Depends(get_async_session),
) -> CoverLetter:
    """
    Produce a targeted cover letter strictly referencing confirmed profile facts.
    Evaluated with Policy and Quality Reviewer to enforce zero hallucination.
    """
    candidate = req.candidate_profile
    job = req.job_listing

    # Load from DB if not provided
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

    # Generate cover letter
    cover_letter = await _cover_letter_service.generate_cover_letter(candidate=candidate, job=job)

    # Persist in package if package_id or job_id provided
    package_repo = ApplicationPackageRepository(session)
    target_package_id = req.package_id
    if target_package_id:
        pkg = await package_repo.get_package(user_id=req.user_id, package_id=target_package_id)
        if pkg:
            pkg.cover_letter = cover_letter.model_dump(mode="json")
            # Merge warnings
            current_warnings = list(pkg.unsupported_claim_warnings or [])
            for w in cover_letter.unsupported_claim_warnings:
                if w not in current_warnings:
                    current_warnings.append(w)
            pkg.unsupported_claim_warnings = current_warnings
            await session.commit()
    elif req.job_id:
        pkg = await package_repo.get_package_by_job(user_id=req.user_id, job_id=req.job_id)
        if pkg:
            pkg.cover_letter = cover_letter.model_dump(mode="json")
            current_warnings = list(pkg.unsupported_claim_warnings or [])
            for w in cover_letter.unsupported_claim_warnings:
                if w not in current_warnings:
                    current_warnings.append(w)
            pkg.unsupported_claim_warnings = current_warnings
            await session.commit()

    return cover_letter


@router.post(
    "/draft-answers",
    response_model=ApplicationQuestionSet,
    status_code=status.HTTP_200_OK,
    summary="Draft answers for application questions with unsupported claim warnings",
)
async def draft_answers_endpoint(
    req: DraftAnswersRequest,
    session: AsyncSession = Depends(get_async_session),
) -> ApplicationQuestionSet:
    """
    Draft answers for application questions based solely on confirmed profile facts.
    Sets requires_user_input=True when facts are missing, rather than fabricating answers.
    """
    candidate = req.candidate_profile
    job = req.job_listing

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

    answers_set = await _cover_letter_service.draft_application_answers(
        candidate=candidate,
        job=job,
        custom_questions=req.custom_questions,
    )

    # Persist in package if package exists
    package_repo = ApplicationPackageRepository(session)
    answers_dict = {a.question: a.answer for a in answers_set.answers}

    target_pkg = None
    if req.package_id:
        target_pkg = await package_repo.get_package(user_id=req.user_id, package_id=req.package_id)
    elif req.job_id:
        target_pkg = await package_repo.get_package_by_job(user_id=req.user_id, job_id=req.job_id)

    if target_pkg:
        target_pkg.form_answers = answers_dict
        current_warnings = list(target_pkg.unsupported_claim_warnings or [])
        for ans in answers_set.answers:
            for w in ans.unsupported_claim_warnings:
                if w not in current_warnings:
                    current_warnings.append(w)
        target_pkg.unsupported_claim_warnings = current_warnings
        await session.commit()

    return answers_set


@router.post(
    "/review-package",
    response_model=PolicyReviewResult,
    status_code=status.HTTP_200_OK,
    summary="Comprehensive policy and quality review across package materials",
)
async def review_package_endpoint(
    req: ReviewPackageRequest,
    session: AsyncSession = Depends(get_async_session),
) -> PolicyReviewResult:
    """
    Evaluates entire package for unsupported claims, privacy leaks, and suspicious job signs.
    """
    package_repo = ApplicationPackageRepository(session)
    pkg = await package_repo.get_package(user_id=req.user_id, package_id=req.package_id)
    if not pkg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application package {req.package_id} not found or access denied",
        )

    # Retrieve candidate profile and job listing
    profile_repo = ProfileRepository(session)
    profile_model = await profile_repo.get_profile_by_user_id(req.user_id)
    if not profile_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate profile not found for user {req.user_id}",
        )
    p_data = dict(profile_model.structured_data or {})
    p_data["id"] = profile_model.id
    p_data["user_id"] = profile_model.user_id
    p_data["full_name"] = profile_model.full_name
    candidate = CandidateProfile(**p_data)

    job_repo = JobRepository(session)
    job_model = await job_repo.get_job_by_id(pkg.job_id)
    if not job_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Associated job listing {pkg.job_id} not found",
        )
    job = job_repo._to_contract(job_model)

    resume_dict = dict(pkg.tailored_resume) if isinstance(pkg.tailored_resume, dict) else {}
    cover_letter_dict = dict(pkg.cover_letter) if isinstance(pkg.cover_letter, dict) else None

    pkg_contract = ApplicationPackage(
        id=str(pkg.id),
        user_id=str(pkg.user_id),
        job_id=str(pkg.job_id),
        tailored_resume=TailoredDocument.model_validate(resume_dict),
        cover_letter=TailoredDocument.model_validate(cover_letter_dict) if cover_letter_dict else None,
        form_answers=dict(pkg.form_answers or {}),
        unsupported_claim_warnings=list(pkg.unsupported_claim_warnings or []),
        is_user_approved=bool(pkg.is_user_approved),
        approved_at=pkg.approved_at,
    )

    review_result = _policy_reviewer.review_full_package(
        package=pkg_contract,
        candidate=candidate,
        job=job,
    )
    return review_result
