import json
from typing import Any, List, Optional

from sqlalchemy import JSON, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB

try:
    from pgvector.sqlalchemy import Vector as PgVector
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False


class SafeVector(TypeDecorator):
    """
    SQLAlchemy TypeDecorator providing vector embedding storage.
    Uses pgvector.sqlalchemy.Vector on PostgreSQL, and falls back to JSON
    on SQLite / non-vector dialects for deterministic tests and portability.
    """
    impl = JSON
    cache_ok = True

    def __init__(self, dim: int = 1536, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dim = dim

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql" and PGVECTOR_AVAILABLE:
            return dialect.type_descriptor(PgVector(self.dim))
        elif dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        else:
            return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: Optional[List[float]], dialect) -> Any:
        if value is None:
            return None
        if dialect.name == "postgresql" and PGVECTOR_AVAILABLE:
            return value
        return value

    def process_result_value(self, value: Any, dialect) -> Optional[List[float]]:
        if value is None:
            return None
        if isinstance(value, list):
            return [float(x) for x in value]
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return [float(x) for x in parsed]
            except Exception:
                return None
        return list(value)

