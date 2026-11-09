import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from datetime import datetime, timezone


class BaseCheckpointer(ABC):
    """Abstract interface for storing and resuming LangGraph workflow checkpoints."""

    @abstractmethod
    def save_checkpoint(self, workflow_id: str, state: Dict[str, Any], stage: str) -> None:
        """Persist state checkpoint for a workflow."""
        pass

    @abstractmethod
    def load_checkpoint(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the latest checkpoint for a workflow."""
        pass


class MemoryCheckpointer(BaseCheckpointer):
    """In-memory checkpointer suitable for development and tests."""

    def __init__(self):
        self._checkpoints: Dict[str, Dict[str, Any]] = {}

    def save_checkpoint(self, workflow_id: str, state: Dict[str, Any], stage: str) -> None:
        self._checkpoints[workflow_id] = {
            "workflow_id": workflow_id,
            "stage": stage,
            "state": state,
            "saved_at": datetime.now(timezone.utc).isoformat()
        }

    def load_checkpoint(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        record = self._checkpoints.get(workflow_id)
        if record:
            return record["state"]
        return None

    def clear(self) -> None:
        self._checkpoints.clear()


# Default singleton checkpointer for Phase 1
default_checkpointer = MemoryCheckpointer()

