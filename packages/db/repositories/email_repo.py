from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.base import utc_now
from packages.db.models import EmailDraftModel


class EmailDraftRepository:
    """
    Repository for EmailDraftModel.
    Persists role-specific email drafts (recruiter outreach, referral requests, follow-ups, thank-you notes).
    Strictly enforces user-data isolation at the database query layer.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_draft(
        self,
        user_id: str,
        email_type: str,
        subject: str,
        body: str,
        call_to_action: str,
        job_id: Optional[str] = None,
        recipient_name: Optional[str] = None,
        recipient_role: Optional[str] = None,
        tone: str = "professional",
        recipient_assumptions: Optional[List[str]] = None,
        personalization_evidence: Optional[List[Dict[str, Any]]] = None,
        missing_recipient_warnings: Optional[List[str]] = None,
        variants: Optional[List[str]] = None,
        is_approved_by_user: bool = False,
        draft_id: Optional[str] = None,
    ) -> EmailDraftModel:
        """
        Create a new email draft or update an existing draft by ID.
        """
        if draft_id:
            existing = await self.get_draft(user_id=user_id, draft_id=draft_id)
            if existing:
                existing.email_type = email_type
                existing.subject = subject
                existing.body = body
                existing.call_to_action = call_to_action
                existing.job_id = job_id
                existing.recipient_name = recipient_name
                existing.recipient_role = recipient_role
                existing.tone = tone
                existing.recipient_assumptions = recipient_assumptions or []
                existing.personalization_evidence = personalization_evidence or []
                existing.missing_recipient_warnings = missing_recipient_warnings or []
                existing.variants = variants or []
                existing.is_approved_by_user = is_approved_by_user
                existing.updated_at = utc_now()
                await self.session.flush()
                return existing

        new_draft = EmailDraftModel(
            id=draft_id or str(uuid.uuid4()),
            user_id=user_id,
            job_id=job_id,
            email_type=email_type,
            recipient_name=recipient_name,
            recipient_role=recipient_role,
            subject=subject,
            body=body,
            call_to_action=call_to_action,
            tone=tone,
            recipient_assumptions=recipient_assumptions or [],
            personalization_evidence=personalization_evidence or [],
            missing_recipient_warnings=missing_recipient_warnings or [],
            variants=variants or [],
            is_approved_by_user=is_approved_by_user,
        )
        self.session.add(new_draft)
        await self.session.flush()
        return new_draft

    async def get_draft(self, user_id: str, draft_id: str) -> Optional[EmailDraftModel]:
        """
        Retrieve a specific email draft by ID, strictly enforcing user isolation.
        """
        stmt = select(EmailDraftModel).where(
            EmailDraftModel.id == draft_id,
            EmailDraftModel.user_id == user_id,
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_drafts_for_user(
        self,
        user_id: str,
        job_id: Optional[str] = None,
        email_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[EmailDraftModel]:
        """
        List all email drafts for a user with optional job_id and email_type filtering.
        """
        stmt = select(EmailDraftModel).where(EmailDraftModel.user_id == user_id)
        if job_id:
            stmt = stmt.where(EmailDraftModel.job_id == job_id)
        if email_type:
            stmt = stmt.where(EmailDraftModel.email_type == email_type)

        stmt = stmt.order_by(desc(EmailDraftModel.updated_at)).limit(limit).offset(offset)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def update_draft_content(
        self,
        user_id: str,
        draft_id: str,
        subject: Optional[str] = None,
        body: Optional[str] = None,
        call_to_action: Optional[str] = None,
        tone: Optional[str] = None,
        is_approved_by_user: Optional[bool] = None,
    ) -> Optional[EmailDraftModel]:
        """
        Update user-editable fields of an email draft.
        """
        draft = await self.get_draft(user_id=user_id, draft_id=draft_id)
        if not draft:
            return None

        if subject is not None:
            draft.subject = subject
        if body is not None:
            draft.body = body
        if call_to_action is not None:
            draft.call_to_action = call_to_action
        if tone is not None:
            draft.tone = tone
        if is_approved_by_user is not None:
            draft.is_approved_by_user = is_approved_by_user

        draft.updated_at = utc_now()
        await self.session.flush()
        return draft

    async def delete_draft(self, user_id: str, draft_id: str) -> bool:
        """
        Delete an email draft, enforcing user isolation.
        """
        stmt = delete(EmailDraftModel).where(
            EmailDraftModel.id == draft_id,
            EmailDraftModel.user_id == user_id,
        )
        res = await self.session.execute(stmt)
        await self.session.flush()
        return res.rowcount > 0
