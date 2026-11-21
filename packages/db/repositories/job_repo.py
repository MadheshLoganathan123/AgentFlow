from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, delete, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import JobListingModel, JobMatchModel, SavedJobModel


class JobRepository:
    """
    Repository for storing, indexing, and querying normalized job listings,
    explainable match evaluations, and user shortlist actions.
    Enforces deduplication using content_hash and strict user data isolation.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_job(
        self,
        title: str,
        organization: str,
        location: str,
        source_name: str,
        source_url: str,
        destination_url: str,
        content_hash: str,
        description_text: str,
        work_mode: str = "unknown",
        seniority: str = "unspecified",
        salary_min: Optional[int] = None,
        salary_max: Optional[int] = None,
        salary_currency: Optional[str] = "USD",
        skills_required: Optional[List[str]] = None,
        skills_preferred: Optional[List[str]] = None,
        description_html: Optional[str] = None,
        application_method: str = "url",
        embedding: Optional[List[float]] = None,
        duplicate_of_id: Optional[str] = None,
        alternate_sources: Optional[List[dict]] = None,
        posted_at: Optional[datetime] = None,
    ) -> JobListingModel:
        """
        Idempotently insert or update a job listing using content_hash.
        Merges new source provenance when an identical job is re-encountered.
        """
        stmt = select(JobListingModel).where(JobListingModel.content_hash == content_hash)
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()

        if existing:
            # Merge any new alternate source into existing record
            if alternate_sources and hasattr(existing, "alternate_sources"):
                current_alts = list(existing.alternate_sources or [])
                changed = False
                for alt in alternate_sources:
                    if alt not in current_alts:
                        current_alts.append(alt)
                        changed = True
                if changed:
                    existing.alternate_sources = current_alts
                    await self.session.commit()
                    await self.session.refresh(existing)
            return existing

        job = JobListingModel(
            title=title,
            organization=organization,
            location=location,
            source_name=source_name,
            source_url=source_url,
            destination_url=destination_url,
            content_hash=content_hash,
            description_text=description_text,
            description_html=description_html,
            work_mode=work_mode,
            seniority=seniority,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=salary_currency or "USD",
            skills_required=skills_required or [],
            skills_preferred=skills_preferred or [],
            application_method=application_method,
            embedding=embedding,
            is_active=True,
            duplicate_of_id=duplicate_of_id,
            alternate_sources=alternate_sources or [],
            posted_at=posted_at,
        )
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def get_by_id(self, job_id: str) -> Optional[JobListingModel]:
        """Retrieve a single job listing by ID."""
        stmt = select(JobListingModel).where(JobListingModel.id == job_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_content_hash(self, content_hash: str) -> Optional[JobListingModel]:
        """Retrieve a single job listing by content_hash."""
        stmt = select(JobListingModel).where(JobListingModel.content_hash == content_hash)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def search_jobs(
        self,
        query: Optional[str] = None,
        organization: Optional[str] = None,
        title: Optional[str] = None,
        location: Optional[str] = None,
        work_mode: Optional[str] = None,
        seniority: Optional[str] = None,
        min_salary: Optional[int] = None,
        max_salary: Optional[int] = None,
        posted_after: Optional[datetime] = None,
        is_active: bool = True,
        limit: int = 20,
        offset: int = 0,
    ) -> List[JobListingModel]:
        """
        Execute multi-facet search with filters across organization, title,
        location, work mode, seniority, salary bounds, and posting recency.
        """
        conditions = [JobListingModel.is_active == is_active]

        if query:
            q_norm = f"%{query.strip().lower()}%"
            conditions.append(
                or_(
                    JobListingModel.title.ilike(q_norm),
                    JobListingModel.organization.ilike(q_norm),
                    JobListingModel.description_text.ilike(q_norm),
                )
            )

        if organization:
            conditions.append(JobListingModel.organization.ilike(f"%{organization.strip()}%"))

        if title:
            conditions.append(JobListingModel.title.ilike(f"%{title.strip()}%"))

        if location:
            conditions.append(JobListingModel.location.ilike(f"%{location.strip()}%"))

        if work_mode and work_mode.lower() != "any":
            conditions.append(JobListingModel.work_mode == work_mode.lower().strip())

        if seniority and seniority.lower() != "unspecified":
            conditions.append(JobListingModel.seniority == seniority.lower().strip())

        if min_salary is not None:
            # Job salary_max must be at least min_salary, or salary_min >= min_salary
            conditions.append(
                or_(
                    JobListingModel.salary_max >= min_salary,
                    JobListingModel.salary_min >= min_salary,
                )
            )

        if max_salary is not None:
            # Job salary_min must be within max_salary
            conditions.append(
                or_(
                    JobListingModel.salary_min <= max_salary,
                    JobListingModel.salary_max <= max_salary,
                )
            )

        if posted_after:
            conditions.append(
                or_(
                    JobListingModel.posted_at >= posted_after,
                    and_(
                        JobListingModel.posted_at.is_(None),
                        JobListingModel.retrieved_at >= posted_after,
                    ),
                )
            )

        stmt = (
            select(JobListingModel)
            .where(and_(*conditions))
            .order_by(desc(JobListingModel.retrieved_at))
            .limit(limit)
            .offset(offset)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # -------------------------------------------------------------------------
    # Match Evaluation Persistence
    # -------------------------------------------------------------------------

    async def save_match(
        self,
        user_id: str,
        profile_id: str,
        job_id: str,
        composite_score: float,
        score_breakdown: Dict[str, Any],
        strengths: List[str],
        gaps: List[str],
        uncertainties: List[str],
        matched_requirements: List[Dict[str, Any]],
        recommendation: str,
    ) -> JobMatchModel:
        """
        Persist or update an explainable match evaluation in the database.
        Enforces user_id isolation.
        """
        stmt = select(JobMatchModel).where(
            and_(
                JobMatchModel.user_id == user_id,
                JobMatchModel.job_id == job_id,
            )
        )
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()

        if existing:
            existing.profile_id = profile_id
            existing.composite_score = composite_score
            existing.score_breakdown = score_breakdown
            existing.strengths = strengths
            existing.gaps = gaps
            existing.uncertainties = uncertainties
            existing.matched_requirements = matched_requirements
            existing.recommendation = recommendation
            await self.session.commit()
            await self.session.refresh(existing)
            return existing

        match = JobMatchModel(
            user_id=user_id,
            profile_id=profile_id,
            job_id=job_id,
            composite_score=composite_score,
            score_breakdown=score_breakdown,
            strengths=strengths,
            gaps=gaps,
            uncertainties=uncertainties,
            matched_requirements=matched_requirements,
            recommendation=recommendation,
        )
        self.session.add(match)
        await self.session.commit()
        await self.session.refresh(match)
        return match

    async def get_match(self, user_id: str, job_id: str) -> Optional[JobMatchModel]:
        """Retrieve match evaluation for a user and job."""
        stmt = select(JobMatchModel).where(
            and_(
                JobMatchModel.user_id == user_id,
                JobMatchModel.job_id == job_id,
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_matches_for_user(
        self,
        user_id: str,
        profile_id: Optional[str] = None,
        min_score: Optional[float] = None,
        limit: int = 50,
    ) -> List[JobMatchModel]:
        """List match evaluations for a user, sorted by composite score descending."""
        conditions = [JobMatchModel.user_id == user_id]
        if profile_id:
            conditions.append(JobMatchModel.profile_id == profile_id)
        if min_score is not None:
            conditions.append(JobMatchModel.composite_score >= min_score)

        stmt = (
            select(JobMatchModel)
            .where(and_(*conditions))
            .order_by(desc(JobMatchModel.composite_score))
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # -------------------------------------------------------------------------
    # Saved / Shortlist Actions Persistence
    # -------------------------------------------------------------------------

    async def save_or_shortlist_job(
        self,
        user_id: str,
        job_id: str,
        status: str = "shortlisted",
        notes: Optional[str] = None,
    ) -> SavedJobModel:
        """
        Record user decision on a job ('shortlisted', 'saved', 'dismissed', 'unsuitable').
        Idempotently updates existing record if user changes their mind.
        """
        stmt = select(SavedJobModel).where(
            and_(
                SavedJobModel.user_id == user_id,
                SavedJobModel.job_id == job_id,
            )
        )
        res = await self.session.execute(stmt)
        record = res.scalar_one_or_none()

        if record:
            record.status = status
            if notes is not None:
                record.user_notes = notes
        else:
            record = SavedJobModel(
                user_id=user_id,
                job_id=job_id,
                status=status,
                user_notes=notes,
            )
            self.session.add(record)

        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def get_saved_job(self, user_id: str, job_id: str) -> Optional[SavedJobModel]:
        """Fetch a specific saved job record for a user."""
        stmt = select(SavedJobModel).where(
            and_(
                SavedJobModel.user_id == user_id,
                SavedJobModel.job_id == job_id,
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_saved_jobs(
        self,
        user_id: str,
        status: Optional[str] = None,
    ) -> List[SavedJobModel]:
        """List all saved/shortlisted jobs for a user, optionally filtered by status."""
        conditions = [SavedJobModel.user_id == user_id]
        if status:
            conditions.append(SavedJobModel.status == status)

        stmt = select(SavedJobModel).where(and_(*conditions)).order_by(desc(SavedJobModel.updated_at))
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def remove_saved_job(self, user_id: str, job_id: str) -> bool:
        """Remove a saved job record for a user."""
        stmt = delete(SavedJobModel).where(
            and_(
                SavedJobModel.user_id == user_id,
                SavedJobModel.job_id == job_id,
            )
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.rowcount > 0
