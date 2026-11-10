from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import User


class UserRepository:
    """Repository handling User persistence and lookups."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, email: str, full_name: str, user_id: Optional[str] = None) -> User:
        user = User(email=email, full_name=full_name)
        if user_id:
            user.id = user_id
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def get_by_id(self, user_id: str) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        stmt = select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

