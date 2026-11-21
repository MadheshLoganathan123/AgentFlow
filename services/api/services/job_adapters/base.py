from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from packages.contracts.job import JobSourceType, RawJobPayload


class BaseJobSourceAdapter(ABC):
    """
    Abstract base class for all job source adapters.
    Ensures consistent metadata preservation, error isolation, and standardized raw output.
    """

    source_id: str
    source_name: str
    source_type: JobSourceType
    rate_limit_per_minute: int = 60
    base_url: str

    @abstractmethod
    async def fetch_raw_jobs(
        self,
        query: Optional[str] = None,
        location: Optional[str] = None,
        limit: int = 20,
    ) -> List[RawJobPayload]:
        """
        Fetch raw job postings from the external source or mock fixture.
        Returns a list of standardized RawJobPayload objects.
        """
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the source endpoint or feed is accessible."""
        pass
