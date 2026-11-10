from datetime import datetime, timezone

from sqlalchemy import Column, DateTime
from sqlalchemy.orm import DeclarativeBase


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy entities."""
    pass


class TimestampMixin:
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

