from typing import Dict, List, Optional

from services.api.services.job_adapters.base import BaseJobSourceAdapter
from services.api.services.job_adapters.greenhouse_adapter import GreenhouseJobSourceAdapter
from services.api.services.job_adapters.mock_adapter import MockJobSourceAdapter
from services.api.services.job_adapters.remoteok_adapter import RemoteOKJobSourceAdapter


class JobAdapterRegistry:
    """
    Central registry for job source adapters.
    Manages adapter instances and provides lookup by name or source type.
    """

    def __init__(self):
        self._adapters: Dict[str, BaseJobSourceAdapter] = {}
        self._register_default_adapters()

    def _register_default_adapters(self) -> None:
        """Register the standard default adapters (Mock, Greenhouse, RemoteOK)."""
        mock = MockJobSourceAdapter()
        greenhouse = GreenhouseJobSourceAdapter()
        remoteok = RemoteOKJobSourceAdapter()

        self.register(mock)
        self.register(greenhouse)
        self.register(remoteok)

    def register(self, adapter: BaseJobSourceAdapter) -> None:
        """Register an adapter under its unique source_name."""
        self._adapters[adapter.source_name] = adapter

    def get(self, source_name: str) -> Optional[BaseJobSourceAdapter]:
        """Retrieve an adapter by source_name."""
        return self._adapters.get(source_name)

    def list_adapters(self) -> List[BaseJobSourceAdapter]:
        """List all registered adapters."""
        return list(self._adapters.values())

    def list_source_names(self) -> List[str]:
        """Return the names of all registered sources."""
        return list(self._adapters.keys())


# Global default registry instance
default_adapter_registry = JobAdapterRegistry()
