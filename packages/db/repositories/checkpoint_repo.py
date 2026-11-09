from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from packages.db.models import WorkflowCheckpointModel


class CheckpointRepository:
    """
    Durable checkpoint repository for LangGraph workflow state persistence.
    Supports user isolation and resume-from-pause execution.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_checkpoint(
        self,
        workflow_id: str,
        user_id: str,
        current_stage: str,
        state_payload: Dict[str, Any],
        is_paused: bool = False,
        pause_reason: Optional[str] = None
    ) -> WorkflowCheckpointModel:
        # Check existing version
        stmt = (
            select(WorkflowCheckpointModel)
            .where(
                WorkflowCheckpointModel.workflow_id == workflow_id,
                WorkflowCheckpointModel.user_id == user_id
            )
            .order_by(WorkflowCheckpointModel.checkpoint_version.desc())
        )
        res = await self.session.execute(stmt)
        latest = res.scalars().first()
        next_ver = (latest.checkpoint_version + 1) if latest else 1

        checkpoint = WorkflowCheckpointModel(
            workflow_id=workflow_id,
            user_id=user_id,
            current_stage=current_stage,
            state_payload=state_payload,
            is_paused=is_paused,
            pause_reason=pause_reason,
            checkpoint_version=next_ver
        )
        self.session.add(checkpoint)
        await self.session.commit()
        await self.session.refresh(checkpoint)
        return checkpoint

    async def get_latest_checkpoint(self, workflow_id: str, user_id: str) -> Optional[WorkflowCheckpointModel]:
        stmt = (
            select(WorkflowCheckpointModel)
            .where(
                WorkflowCheckpointModel.workflow_id == workflow_id,
                WorkflowCheckpointModel.user_id == user_id
            )
            .order_by(WorkflowCheckpointModel.checkpoint_version.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_checkpoints(self, workflow_id: str, user_id: str) -> List[WorkflowCheckpointModel]:
        stmt = (
            select(WorkflowCheckpointModel)
            .where(
                WorkflowCheckpointModel.workflow_id == workflow_id,
                WorkflowCheckpointModel.user_id == user_id
            )
            .order_by(WorkflowCheckpointModel.checkpoint_version.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

