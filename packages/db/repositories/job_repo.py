from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from packages.db.models import JobListingModel, SavedJobModel


class JobRepository:
    """
    Repository for storing and querying normalized job listings.
    Enforces deduplication using content_hash.
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
        skills_required: Optional[List[str]] = None,
        skills_preferred: Optional[List[str]] = None,
        embedding: Optional[List[float]] = None
    ) -> JobListingModel:
        # Check for existing job by content_hash to deduplicate
        stmt = select(JobListingModel).where(JobListingModel.content_hash == content_hash)
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()

        if existing:
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
            work_mode=work_mode,
            seniority=seniority,
            salary_min=salary_min,
            salary_max=salary_max,
            skills_required=skills_required or [],
            skills_preferred=skills_preferred or [],
            embedding=embedding,
            is_active=True
        )
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def get_by_content_hash(self, content_hash: str) -> Optional[JobListingModel]:
        stmt = select(JobListingModel).where(JobListingModel.content_hash == content_hash)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def save_or_shortlist_job(
        self,
        user_id: str,
        job_id: str,
        status: str = "shortlisted",
        notes: Optional[str] = None
    ) -> SavedJobModel:
        stmt = select(SavedJobModel).where(
            SavedJobModel.user_id == user_id,
            SavedJobModel.job_id == job_id
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
                user_notes=notes
            )
            self.session.add(record)

        await self.session.commit()
        await self.session.refresh(record)
        return record

