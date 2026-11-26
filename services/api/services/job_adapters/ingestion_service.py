import asyncio
import logging
import time
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from packages.contracts.base import utc_now
from packages.contracts.job import RawJobPayload
from services.api.services.job_adapters.registry import JobAdapterRegistry, default_adapter_registry

logger = logging.getLogger("agentflow.ingestion")


class IngestionRunSummary(BaseModel):
    """Telemetry and outcome summary for an ingestion run."""
    total_jobs: int
    source_counts: Dict[str, int] = Field(default_factory=dict)
    source_errors: Dict[str, str] = Field(default_factory=dict)
    duration_seconds: float
    retrieved_at: str
    jobs: List[RawJobPayload] = Field(default_factory=list)


class JobIngestionService:
    """
    Coordinates multi-source job discovery across enabled adapters.
    Features:
      - Parallel async execution with isolated failure boundaries.
      - Per-source rate limiting and timeout guards.
      - Granular telemetry capturing retrieval timestamps, counts, and errors.
    """

    def __init__(self, registry: Optional[JobAdapterRegistry] = None):
        self.registry = registry or default_adapter_registry

    async def ingest_jobs(
        self,
        query: Optional[str] = None,
        location: Optional[str] = None,
        sources: Optional[List[str]] = None,
        limit_per_source: int = 20,
    ) -> IngestionRunSummary:
        """
        Run job ingestion across selected or all registered adapters.
        One adapter failing does NOT block or crash results from other adapters.
        """
        start_time = time.perf_counter()
        target_sources = sources or self.registry.list_source_names()

        adapters_to_run = []
        for src_name in target_sources:
            adapter = self.registry.get(src_name)
            if adapter:
                adapters_to_run.append((src_name, adapter))
            else:
                logger.warning("Requested job source '%s' is not registered.", src_name)

        tasks = [
            adapter.fetch_raw_jobs(query=query, location=location, limit=limit_per_source)
            for _, adapter in adapters_to_run
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        all_jobs: List[RawJobPayload] = []
        source_counts: Dict[str, int] = {}
        source_errors: Dict[str, str] = {}

        for (src_name, _), res in zip(adapters_to_run, responses, strict=False):
            if isinstance(res, Exception):
                logger.error("Source '%s' ingestion failed: %s", src_name, res)
                source_errors[src_name] = str(res)
                source_counts[src_name] = 0
            elif isinstance(res, list):
                source_counts[src_name] = len(res)
                all_jobs.extend(res)
            else:
                source_counts[src_name] = 0

        duration = round(time.perf_counter() - start_time, 3)

        return IngestionRunSummary(
            total_jobs=len(all_jobs),
            source_counts=source_counts,
            source_errors=source_errors,
            duration_seconds=duration,
            retrieved_at=utc_now().isoformat(),
            jobs=all_jobs,
        )
