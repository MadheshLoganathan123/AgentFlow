from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import AuditEventModel


class AuditEventRepository:
    """
    Append-only repository for audit logging across agent runs and human approvals.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_event(
        self,
        user_id: str,
        event_type: str,
        actor: str = "system",
        workflow_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ) -> AuditEventModel:
        event = AuditEventModel(
            user_id=user_id,
            workflow_id=workflow_id,
            event_type=event_type,
            actor=actor,
            details=details or {},
            ip_address=ip_address
        )
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event

    async def get_events_for_user(
        self,
        user_id: str,
        limit: int = 50,
        event_type: Optional[str] = None
    ) -> List[AuditEventModel]:
        stmt = (
            select(AuditEventModel)
            .where(AuditEventModel.user_id == user_id)
            .order_by(AuditEventModel.created_at.desc())
            .limit(limit)
        )
        if event_type:
            stmt = stmt.where(AuditEventModel.event_type == event_type)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

