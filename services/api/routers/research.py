import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from packages.contracts.interview import (
    CompanyResearchRequest,
    ReportSourceRequest,
    ResearchSource,
    ResearchSummary,
    ValidateUrlRequest,
    ValidateUrlResponse,
)
from packages.db.models import ResearchSourceModel
from packages.db.repositories.research_repo import ResearchSourceRepository
from packages.db.session import get_async_session
from services.api.services.web_research import WebResearchTool

logger = logging.getLogger("agentflow.research")

router = APIRouter(prefix="/api/v1/research", tags=["Allowlisted Web Research & Citations"])


def _model_to_source(m: ResearchSourceModel) -> ResearchSource:
    return ResearchSource(
        id=m.id,
        source_url=m.url,
        source_title=m.title,
        source_domain=m.source_name,
        retrieved_at=m.retrieved_at,
        is_reputable=True,
        is_company_specific=m.is_company_specific,
        content_excerpt=m.excerpt,
        content_hash=m.content_hash,
        source_category=m.source_category or "engineering_blog",
        is_reported=m.is_reported,
        report_reason=m.report_reason,
    )


@router.post(
    "/company",
    response_model=ResearchSummary,
    status_code=status.HTTP_200_OK,
    summary="Conduct allowlisted web research on a target company and role",
)
async def research_company(
    request: CompanyResearchRequest,
    session: AsyncSession = Depends(get_async_session),
) -> ResearchSummary:
    """
    Executes grounded research on a target company and optional role title.
    Enforces the reputable domain allowlist (official corporate sites, SEC filings,
    GitHub, verified engineering blogs, Wikipedia, and tech press).
    Stores discovered source citations in the repository with SHA-256 content hashes.
    """
    try:
        repo = ResearchSourceRepository(session)
        tool = WebResearchTool(repository=repo)
        summary = await tool.research_company(
            company_name=request.company_name,
            role_title=request.role_title,
            job_id=request.job_id,
        )
        return summary
    except Exception as exc:
        logger.error(f"Error researching company {request.company_name}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to conduct company research: {str(exc)}",
        ) from exc


@router.get(
    "/sources",
    response_model=List[ResearchSource],
    summary="List saved research source citations",
)
async def list_sources(
    company_name: Optional[str] = Query(None, description="Filter by company name"),
    job_id: Optional[str] = Query(None, description="Filter by job ID"),
    include_reported: bool = Query(True, description="Include reported sources"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_async_session),
) -> List[ResearchSource]:
    """Retrieve persisted research sources and citations with pagination and optional filters."""
    repo = ResearchSourceRepository(session)
    models = await repo.list_sources(
        company_name=company_name,
        job_id=job_id,
        include_reported=include_reported,
        limit=limit,
        offset=offset,
    )
    return [_model_to_source(m) for m in models]


@router.get(
    "/sources/{source_id}",
    response_model=ResearchSource,
    summary="Get single research source citation by ID",
)
async def get_source(
    source_id: str,
    session: AsyncSession = Depends(get_async_session),
) -> ResearchSource:
    """Fetch details and provenance of an individual source citation card."""
    repo = ResearchSourceRepository(session)
    m = await repo.get_source(source_id)
    if not m:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research source '{source_id}' not found.",
        )
    return _model_to_source(m)


@router.post(
    "/sources/{source_id}/report",
    response_model=ResearchSource,
    summary="Report an inaccurate, stale, or problematic source citation",
)
async def report_source(
    source_id: str,
    request: ReportSourceRequest,
    session: AsyncSession = Depends(get_async_session),
) -> ResearchSource:
    """Flag a source as reported with candidate reasoning."""
    repo = ResearchSourceRepository(session)
    updated = await repo.report_source(source_id=source_id, reason=request.reason)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research source '{source_id}' not found.",
        )
    return _model_to_source(updated)


@router.delete(
    "/sources/{source_id}",
    summary="Remove a source citation card from the repository",
)
async def delete_source(
    source_id: str,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Permanently delete a research source citation."""
    repo = ResearchSourceRepository(session)
    deleted = await repo.delete_source(source_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research source '{source_id}' not found.",
        )
    return {"message": "Source citation successfully removed", "id": source_id}


@router.post(
    "/validate-url",
    response_model=ValidateUrlResponse,
    summary="Check whether a URL conforms to the domain allowlist",
)
async def validate_url(
    request: ValidateUrlRequest,
) -> ValidateUrlResponse:
    """Validate whether an external target URL is permitted by allowlist policy."""
    return WebResearchTool.validate_url(request.url)
