from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from packages.contracts.job import JobListing, NormalizationSummary, RawJobPayload
from packages.contracts.match import MatchExplanation
from packages.contracts.profile import CandidateProfile
from packages.db.repositories.job_repo import JobRepository
from packages.db.session import get_async_session
from services.api.services.job_adapters import (
    IngestionRunSummary,
    JobAdapterRegistry,
    JobIngestionService,
    default_adapter_registry,
)
from services.api.services.matcher import MatchRankingService
from services.api.services.normalizer import JobNormalizerService
from services.api.services.retrieval import JobRetrievalService

router = APIRouter(prefix="/api/v1/jobs", tags=["Job Ingestion & Discovery"])

_ingestion_service = JobIngestionService(default_adapter_registry)


class JobSourceInfo(BaseModel):
    source_name: str
    source_id: str
    source_type: str
    rate_limit_per_minute: int
    base_url: str
    is_available: bool


class JobIngestRequest(BaseModel):
    query: Optional[str] = Field(None, description="Keywords to match in job title or description")
    location: Optional[str] = Field(None, description="Location or work mode filter (e.g. 'remote', 'New York')")
    sources: Optional[List[str]] = Field(None, description="Specific sources to query. Defaults to all active sources")
    limit_per_source: int = Field(15, ge=1, le=50, description="Max jobs to fetch per source")


class JobDiscoveryResponse(BaseModel):
    """Normalized and deduplicated job discovery outcome."""
    summary: NormalizationSummary
    jobs: List[JobListing]


@router.get("/sources", response_model=List[JobSourceInfo])
async def list_sources():
    """List all registered job source adapters and their operational availability."""
    sources_info = []
    for adapter in default_adapter_registry.list_adapters():
        available = await adapter.is_available()
        sources_info.append(
            JobSourceInfo(
                source_name=adapter.source_name,
                source_id=adapter.source_id,
                source_type=adapter.source_type.value,
                rate_limit_per_minute=adapter.rate_limit_per_minute,
                base_url=adapter.base_url,
                is_available=available,
            )
        )
    return sources_info


@router.post("/ingest", response_model=IngestionRunSummary, status_code=status.HTTP_200_OK)
async def ingest_jobs(payload: JobIngestRequest):
    """
    Execute raw job ingestion across registered adapters with isolated error handling.
    Returns standardized raw job payloads with complete source metadata and retrieval telemetry.
    """
    summary = await _ingestion_service.ingest_jobs(
        query=payload.query,
        location=payload.location,
        sources=payload.sources,
        limit_per_source=payload.limit_per_source,
    )
    return summary


@router.post("/normalize", response_model=JobDiscoveryResponse, status_code=status.HTTP_200_OK)
async def normalize_jobs(raw_jobs: List[RawJobPayload]):
    """
    Normalize raw job payloads into canonical JobListing contracts.
    Executes content hashing, title/org normalization, attribute inference,
    and cross-source duplicate linking.
    """
    unique_jobs, summary = JobNormalizerService.normalize_and_deduplicate(raw_jobs)
    return JobDiscoveryResponse(summary=summary, jobs=unique_jobs)


@router.post("/discover", response_model=JobDiscoveryResponse, status_code=status.HTTP_200_OK)
async def discover_jobs(payload: JobIngestRequest):
    """
    End-to-end job discovery:
    1. Ingests raw postings from all requested/active adapters.
    2. Normalizes titles, organizations, locations, work modes, seniorities, and skills.
    3. Computes tamper-evident SHA-256 content hashes.
    4. Deduplicates and cross-links multi-source postings.
    """
    ingestion_summary = await _ingestion_service.ingest_jobs(
        query=payload.query,
        location=payload.location,
        sources=payload.sources,
        limit_per_source=payload.limit_per_source,
    )
    unique_jobs, norm_summary = JobNormalizerService.normalize_and_deduplicate(ingestion_summary.jobs)
    return JobDiscoveryResponse(summary=norm_summary, jobs=unique_jobs)


class JobMatchRequest(BaseModel):
    candidate_profile: CandidateProfile
    job_listing: JobListing
    custom_weights: Optional[Dict[str, float]] = None


class RankedJobRecommendation(BaseModel):
    job: JobListing
    explanation: MatchExplanation


class JobRecommendationRequest(BaseModel):
    candidate_profile: CandidateProfile
    jobs: Optional[List[JobListing]] = None
    query: Optional[str] = None
    location: Optional[str] = None
    min_score: float = 0.0
    limit: int = 15


class JobRecommendationResponse(BaseModel):
    total_evaluated: int
    ranked_recommendations: List[RankedJobRecommendation]


@router.post("/match", response_model=MatchExplanation, status_code=status.HTTP_200_OK)
async def evaluate_single_match(payload: JobMatchRequest):
    """
    Evaluate candidate profile against a single job listing.
    Returns transparent score breakdown across 6 dimensions, matched requirements,
    strengths, gaps, and recommendation.
    """
    explanation = MatchRankingService.evaluate_match(
        candidate=payload.candidate_profile,
        job=payload.job_listing,
        custom_weights=payload.custom_weights,
    )
    return explanation


@router.post("/recommend", response_model=JobRecommendationResponse, status_code=status.HTTP_200_OK)
async def recommend_jobs(payload: JobRecommendationRequest):
    """
    Rank job opportunities for a candidate profile.
    If jobs are not explicitly provided, automatically queries registered sources,
    normalizes the listings, and ranks them by multi-dimensional fit.
    """
    jobs_to_rank = payload.jobs
    if not jobs_to_rank:
        query = payload.query or (payload.candidate_profile.target_job_titles[0] if payload.candidate_profile.target_job_titles else None)
        ingest_summary = await _ingestion_service.ingest_jobs(
            query=query,
            location=payload.location,
            limit_per_source=15,
        )
        jobs_to_rank, _ = JobNormalizerService.normalize_and_deduplicate(ingest_summary.jobs)

    ranked_pairs = MatchRankingService.rank_jobs(
        candidate=payload.candidate_profile,
        jobs=jobs_to_rank,
        min_score=payload.min_score,
        limit=payload.limit,
    )

    recommendations = [
        RankedJobRecommendation(job=job, explanation=explanation)
        for job, explanation in ranked_pairs
    ]

    return JobRecommendationResponse(
        total_evaluated=len(jobs_to_rank),
        ranked_recommendations=recommendations,
    )


# =============================================================================
# Phase 4: Job Persistence, Multi-Facet Search & Shortlist Actions
# =============================================================================


class JobPersistRequest(BaseModel):
    jobs: List[JobListing]


class JobPersistResponse(BaseModel):
    persisted_count: int
    job_ids: List[str]


class JobActionRequest(BaseModel):
    user_id: str
    status: str = Field(..., description="Action status: 'shortlisted', 'saved', 'dismissed', 'unsuitable'")
    notes: Optional[str] = None


class SavedJobResponse(BaseModel):
    id: str
    user_id: str
    job_id: str
    status: str
    user_notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class HybridSearchRequest(BaseModel):
    candidate_profile: CandidateProfile
    user_id: str
    query: Optional[str] = None
    organization: Optional[str] = None
    location: Optional[str] = None
    work_mode: Optional[str] = None
    seniority: Optional[str] = None
    min_salary: Optional[int] = None
    max_salary: Optional[int] = None
    persist_matches: bool = True
    limit: int = 20


@router.post("/persist", response_model=JobPersistResponse, status_code=status.HTTP_200_OK)
async def persist_jobs(
    payload: JobPersistRequest,
    session: Optional[AsyncSession] = Depends(get_async_session),
):
    """
    Persist normalized jobs into PostgreSQL database with content-hash deduplication
    and cross-source provenance tracking.
    """
    if not session:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database session is not available",
        )
    repo = JobRepository(session)
    persisted_ids = []
    for job in payload.jobs:
        record = await repo.upsert_job(
            title=job.title,
            organization=job.organization,
            location=job.location,
            source_name=job.source_name,
            source_url=job.source_url,
            destination_url=job.destination_url,
            content_hash=job.content_hash,
            description_text=job.description_text,
            description_html=job.description_html,
            work_mode=job.work_mode,
            seniority=job.seniority,
            salary_min=job.salary_min,
            salary_max=job.salary_max,
            salary_currency=job.salary_currency,
            skills_required=job.skills_required,
            skills_preferred=job.skills_preferred,
            application_method=job.application_method,
            duplicate_of_id=job.duplicate_of_id,
            alternate_sources=job.alternate_sources,
            posted_at=job.posted_at,
        )
        persisted_ids.append(record.id)

    return JobPersistResponse(persisted_count=len(persisted_ids), job_ids=persisted_ids)


@router.get("/search", response_model=List[JobListing], status_code=status.HTTP_200_OK)
async def search_jobs(
    query: Optional[str] = Query(None, description="Free-text keywords matching title, org, or description"),
    organization: Optional[str] = Query(None, description="Filter by company / organization name"),
    title: Optional[str] = Query(None, description="Filter by job title"),
    location: Optional[str] = Query(None, description="Filter by location (e.g. 'San Francisco', 'Remote')"),
    work_mode: Optional[str] = Query(None, description="Filter by work mode: 'remote', 'hybrid', 'onsite'"),
    seniority: Optional[str] = Query(None, description="Filter by seniority level: 'entry', 'mid', 'senior', 'lead', 'executive'"),
    min_salary: Optional[int] = Query(None, description="Minimum salary threshold"),
    max_salary: Optional[int] = Query(None, description="Maximum salary ceiling"),
    posted_after: Optional[datetime] = Query(None, description="Filter postings retrieved or posted after ISO timestamp"),
    is_active: bool = Query(True, description="Filter active jobs"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Optional[AsyncSession] = Depends(get_async_session),
):
    """
    Multi-facet query search across persisted database job listings with relational filters.
    """
    if not session:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database session is not available",
        )
    repo = JobRepository(session)
    models = await repo.search_jobs(
        query=query,
        organization=organization,
        title=title,
        location=location,
        work_mode=work_mode,
        seniority=seniority,
        min_salary=min_salary,
        max_salary=max_salary,
        posted_after=posted_after,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    return [JobRetrievalService._model_to_contract(m) for m in models]


@router.get("/saved", response_model=List[SavedJobResponse], status_code=status.HTTP_200_OK)
async def list_saved_jobs(
    user_id: str = Query(..., description="Target user ID for isolated saved job listing"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status: 'shortlisted', 'saved', 'dismissed', 'unsuitable'"),
    session: Optional[AsyncSession] = Depends(get_async_session),
):
    """
    List all saved and shortlisted jobs for an isolated user.
    """
    if not session:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database session is not available",
        )
    repo = JobRepository(session)
    records = await repo.list_saved_jobs(user_id=user_id, status=status_filter)
    return [
        SavedJobResponse(
            id=r.id,
            user_id=r.user_id,
            job_id=r.job_id,
            status=r.status,
            user_notes=r.user_notes,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in records
    ]


@router.get("/{job_id}", response_model=JobListing, status_code=status.HTTP_200_OK)
async def get_job_by_id(
    job_id: str,
    session: Optional[AsyncSession] = Depends(get_async_session),
):
    """
    Retrieve a specific job listing by its canonical ID.
    """
    if not session:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database session is not available",
        )
    repo = JobRepository(session)
    model = await repo.get_by_id(job_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job listing '{job_id}' not found",
        )
    return JobRetrievalService._model_to_contract(model)


@router.post("/{job_id}/action", response_model=SavedJobResponse, status_code=status.HTTP_200_OK)
async def record_job_action(
    job_id: str,
    payload: JobActionRequest,
    session: Optional[AsyncSession] = Depends(get_async_session),
):
    """
    Record user shortlist decision or preference update on a job listing
    ('shortlisted', 'saved', 'dismissed', 'unsuitable').
    """
    valid_statuses = {"shortlisted", "saved", "dismissed", "unsuitable"}
    if payload.status.lower() not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status '{payload.status}'. Must be one of: {sorted(valid_statuses)}",
        )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database session is not available",
        )
    repo = JobRepository(session)
    record = await repo.save_or_shortlist_job(
        user_id=payload.user_id,
        job_id=job_id,
        status=payload.status.lower(),
        notes=payload.notes,
    )
    return SavedJobResponse(
        id=record.id,
        user_id=record.user_id,
        job_id=record.job_id,
        status=record.status,
        user_notes=record.user_notes,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.delete("/{job_id}/saved", status_code=status.HTTP_200_OK)
async def remove_saved_job(
    job_id: str,
    user_id: str = Query(..., description="User ID owning the saved job"),
    session: Optional[AsyncSession] = Depends(get_async_session),
):
    """
    Remove a saved/shortlisted job record for a user.
    """
    if not session:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database session is not available",
        )
    repo = JobRepository(session)
    deleted = await repo.remove_saved_job(user_id=user_id, job_id=job_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved job record not found for this user",
        )
    return {"message": "Job removed from saved list", "job_id": job_id, "user_id": user_id}


@router.post("/search-and-rank", response_model=JobRecommendationResponse, status_code=status.HTTP_200_OK)
async def search_and_rank_jobs(
    payload: HybridSearchRequest,
    session: Optional[AsyncSession] = Depends(get_async_session),
):
    """
    Hybrid search and multi-dimensional ranking:
    1. Queries database with relational multi-facet filters.
    2. Ranks candidate jobs using explainable match engine.
    3. Persists match evaluations into PostgreSQL `job_matches` for auditability.
    """
    if not session:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database session is not available",
        )
    repo = JobRepository(session)
    retrieval_service = JobRetrievalService(repo)

    ranked_pairs = await retrieval_service.hybrid_search_and_rank(
        candidate=payload.candidate_profile,
        user_id=payload.user_id,
        query=payload.query,
        organization=payload.organization,
        location=payload.location,
        work_mode=payload.work_mode,
        seniority=payload.seniority,
        min_salary=payload.min_salary,
        max_salary=payload.max_salary,
        persist_matches=payload.persist_matches,
        limit=payload.limit,
    )

    recommendations = [
        RankedJobRecommendation(job=job, explanation=explanation)
        for job, explanation in ranked_pairs
    ]

    return JobRecommendationResponse(
        total_evaluated=len(recommendations),
        ranked_recommendations=recommendations,
    )
