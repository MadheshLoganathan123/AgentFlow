import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.base import utc_now
from packages.db.models import ApplicationPackageModel


class ApplicationPackageRepository:
    """
    Repository for ApplicationPackageModel.
    Provides persistence and retrieval for tailored resumes, cover letters, and application materials.
    Strictly enforces user-data isolation at the database query layer.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_package(
        self,
        user_id: str,
        job_id: str,
        tailored_resume: Dict[str, Any],
        cover_letter: Optional[Dict[str, Any]] = None,
        form_answers: Optional[Dict[str, str]] = None,
        unsupported_claim_warnings: Optional[List[str]] = None,
        package_id: Optional[str] = None,
    ) -> ApplicationPackageModel:
        """
        Create or update an application package for a given user and job.
        Ensures idempotency per user and job.
        """
        # Check if a package already exists for this user and job
        existing_stmt = select(ApplicationPackageModel).where(
            ApplicationPackageModel.user_id == user_id,
            ApplicationPackageModel.job_id == job_id,
        )
        result = await self.session.execute(existing_stmt)
        package = result.scalar_one_or_none()

        if package:
            package.tailored_resume = tailored_resume
            if cover_letter is not None:
                package.cover_letter = cover_letter
            if form_answers is not None:
                package.form_answers = form_answers
            if unsupported_claim_warnings is not None:
                package.unsupported_claim_warnings = unsupported_claim_warnings
            package.updated_at = utc_now()
        else:
            package = ApplicationPackageModel(
                id=package_id or str(uuid.uuid4()),
                user_id=user_id,
                job_id=job_id,
                tailored_resume=tailored_resume,
                cover_letter=cover_letter,
                form_answers=form_answers or {},
                unsupported_claim_warnings=unsupported_claim_warnings or [],
                is_user_approved=False,
                approved_at=None,
            )
            self.session.add(package)

        await self.session.flush()
        return package

    async def get_package(self, user_id: str, package_id: str) -> Optional[ApplicationPackageModel]:
        """
        Retrieve an application package by ID, strictly scoped to the user.
        """
        stmt = select(ApplicationPackageModel).where(
            ApplicationPackageModel.id == package_id,
            ApplicationPackageModel.user_id == user_id,
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_package_by_job(self, user_id: str, job_id: str) -> Optional[ApplicationPackageModel]:
        """
        Retrieve an application package by job ID, strictly scoped to the user.
        """
        stmt = select(ApplicationPackageModel).where(
            ApplicationPackageModel.job_id == job_id,
            ApplicationPackageModel.user_id == user_id,
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_packages_for_user(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> List[ApplicationPackageModel]:
        """
        List all application packages for a user, ordered by most recently updated.
        """
        stmt = (
            select(ApplicationPackageModel)
            .where(ApplicationPackageModel.user_id == user_id)
            .order_by(desc(ApplicationPackageModel.updated_at))
            .limit(limit)
            .offset(offset)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def update_approval(
        self, user_id: str, package_id: str, is_user_approved: bool
    ) -> Optional[ApplicationPackageModel]:
        """
        Update the human approval status of a package, verifying user isolation.
        """
        package = await self.get_package(user_id=user_id, package_id=package_id)
        if not package:
            return None

        package.is_user_approved = is_user_approved
        package.approved_at = utc_now() if is_user_approved else None
        package.updated_at = utc_now()
        await self.session.flush()
        return package

    async def delete_package(self, user_id: str, package_id: str) -> bool:
        """
        Delete a package, verifying user isolation.
        """
        stmt = delete(ApplicationPackageModel).where(
            ApplicationPackageModel.id == package_id,
            ApplicationPackageModel.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0
