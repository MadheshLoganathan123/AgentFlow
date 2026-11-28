import uuid
from typing import List, Optional

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.base import utc_now
from packages.db.models import ResearchSourceModel


class ResearchSourceRepository:
    """
    Repository for ResearchSourceModel.
    Persists web research sources, citations, and allowlisted intelligence.
    Enforces auditability, tamper detection via content hashing, and user-initiated source reporting.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_source(
        self,
        company_name: str,
        title: str,
        url: str,
        source_name: str,
        excerpt: str,
        job_id: Optional[str] = None,
        is_company_specific: bool = True,
        content_hash: Optional[str] = None,
        source_category: str = "engineering_blog",
        is_reported: bool = False,
        report_reason: Optional[str] = None,
        source_id: Optional[str] = None,
    ) -> ResearchSourceModel:
        """
        Create or update a research source record.
        """
        if source_id:
            existing = await self.get_source(source_id)
            if existing:
                existing.company_name = company_name
                existing.title = title
                existing.url = url
                existing.source_name = source_name
                existing.excerpt = excerpt
                existing.job_id = job_id
                existing.is_company_specific = is_company_specific
                existing.content_hash = content_hash
                existing.source_category = source_category
                existing.is_reported = is_reported
                existing.report_reason = report_reason
                existing.updated_at = utc_now()
                await self.session.flush()
                return existing

        # Check for duplicate by (company_name, url)
        stmt = select(ResearchSourceModel).where(
            ResearchSourceModel.company_name == company_name,
            ResearchSourceModel.url == url,
        )
        result = await self.session.execute(stmt)
        existing = result.scalars().first()

        if existing:
            existing.title = title
            existing.source_name = source_name
            existing.excerpt = excerpt
            existing.job_id = job_id or existing.job_id
            existing.is_company_specific = is_company_specific
            existing.content_hash = content_hash or existing.content_hash
            existing.source_category = source_category
            existing.is_reported = is_reported
            existing.report_reason = report_reason
            existing.updated_at = utc_now()
            await self.session.flush()
            return existing

        new_source = ResearchSourceModel(
            id=str(uuid.uuid4()),
            job_id=job_id,
            company_name=company_name,
            title=title,
            url=url,
            source_name=source_name,
            excerpt=excerpt,
            is_company_specific=is_company_specific,
            content_hash=content_hash,
            source_category=source_category,
            is_reported=is_reported,
            report_reason=report_reason,
            retrieved_at=utc_now(),
        )
        self.session.add(new_source)
        await self.session.flush()
        return new_source

    async def get_source(self, source_id: str) -> Optional[ResearchSourceModel]:
        """Retrieve a specific source by its ID."""
        stmt = select(ResearchSourceModel).where(ResearchSourceModel.id == source_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_sources(
        self,
        company_name: Optional[str] = None,
        job_id: Optional[str] = None,
        include_reported: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ResearchSourceModel]:
        """List sources matching filters ordered by most recently retrieved."""
        stmt = select(ResearchSourceModel)
        if company_name:
            stmt = stmt.where(ResearchSourceModel.company_name.ilike(f"%{company_name}%"))
        if job_id:
            stmt = stmt.where(ResearchSourceModel.job_id == job_id)
        if not include_reported:
            stmt = stmt.where(ResearchSourceModel.is_reported.is_(False))

        stmt = stmt.order_by(desc(ResearchSourceModel.retrieved_at)).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def report_source(self, source_id: str, reason: str) -> Optional[ResearchSourceModel]:
        """Flag a source as reported by user with an explanatory reason."""
        source = await self.get_source(source_id)
        if not source:
            return None
        source.is_reported = True
        source.report_reason = reason
        source.updated_at = utc_now()
        await self.session.flush()
        return source

    async def delete_source(self, source_id: str) -> bool:
        """Remove a source from the database permanently."""
        stmt = delete(ResearchSourceModel).where(ResearchSourceModel.id == source_id)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return bool(result.rowcount > 0)
