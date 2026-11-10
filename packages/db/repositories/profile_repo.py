from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from packages.db.base import utc_now
from packages.db.models import CandidateProfileModel, ProfileEvidenceModel


class ProfileRepository:
    """
    Repository for CandidateProfile and ProfileEvidence.
    Strictly enforces user-data isolation at the query layer.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_profile(
        self,
        user_id: str,
        full_name: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        primary_location: Optional[str] = None,
        total_years_experience: Optional[float] = None,
        work_authorization: Optional[str] = None,
        notice_period_days: Optional[int] = None,
        raw_resume_text: Optional[str] = None,
        structured_data: Optional[Dict[str, Any]] = None,
        embedding: Optional[List[float]] = None,
        profile_id: Optional[str] = None,
    ) -> CandidateProfileModel:
        profile = CandidateProfileModel(
            user_id=user_id,
            full_name=full_name,
            email=email,
            phone=phone,
            primary_location=primary_location,
            total_years_experience=total_years_experience,
            work_authorization=work_authorization,
            notice_period_days=notice_period_days,
            raw_resume_text=raw_resume_text,
            structured_data=structured_data or {},
            embedding=embedding,
            is_profile_confirmed=False
        )
        if profile_id:
            profile.id = profile_id

        self.session.add(profile)
        await self.session.commit()
        await self.session.refresh(profile)
        return profile

    async def add_evidence(
        self,
        profile_id: str,
        field_name: str,
        source_type: str,
        source_identifier: str,
        raw_snippet: Optional[str] = None,
        page_number: Optional[int] = None,
        confidence_score: float = 1.0,
        is_inferred: bool = False,
        is_user_confirmed: bool = False,
    ) -> ProfileEvidenceModel:
        evidence = ProfileEvidenceModel(
            profile_id=profile_id,
            field_name=field_name,
            source_type=source_type,
            source_identifier=source_identifier,
            raw_snippet=raw_snippet,
            page_number=page_number,
            confidence_score=confidence_score,
            is_inferred=is_inferred,
            is_user_confirmed=is_user_confirmed
        )
        self.session.add(evidence)
        await self.session.commit()
        await self.session.refresh(evidence)
        return evidence

    async def get_by_id_for_user(self, profile_id: str, user_id: str) -> Optional[CandidateProfileModel]:
        """User-data isolation: queries by profile_id AND user_id."""
        stmt = (
            select(CandidateProfileModel)
            .options(selectinload(CandidateProfileModel.evidences))
            .where(
                CandidateProfileModel.id == profile_id,
                CandidateProfileModel.user_id == user_id
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_profile_for_user(self, user_id: str) -> Optional[CandidateProfileModel]:
        stmt = (
            select(CandidateProfileModel)
            .options(selectinload(CandidateProfileModel.evidences))
            .where(CandidateProfileModel.user_id == user_id)
            .order_by(CandidateProfileModel.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def confirm_profile(
        self,
        profile_id: str,
        user_id: str,
        updated_fields: Optional[Dict[str, Any]] = None
    ) -> Optional[CandidateProfileModel]:
        """
        Human approval gate: sets profile as confirmed and marks all associated
        evidence as user-confirmed.
        """
        profile = await self.get_by_id_for_user(profile_id, user_id)
        if not profile:
            return None

        if updated_fields:
            for k, v in updated_fields.items():
                if hasattr(profile, k):
                    setattr(profile, k, v)

        profile.is_profile_confirmed = True
        profile.confirmed_at = utc_now()

        # Mark all evidence as user_confirmed
        for ev in profile.evidences:
            ev.is_user_confirmed = True

        await self.session.commit()
        await self.session.refresh(profile)
        return profile

