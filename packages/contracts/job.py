from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from packages.contracts.base import VersionedBaseModel, utc_now


class JobSourceType(str, Enum):
    API = "api"
    FEED = "feed"
    CRAWLER = "crawler"
    MOCK = "mock"


class JobSeniority(str, Enum):
    ENTRY = "entry"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    STAFF = "staff"
    PRINCIPAL = "principal"
    DIRECTOR = "director"
    EXECUTIVE = "executive"
    UNSPECIFIED = "unspecified"


class WorkMode(str, Enum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


class RawJobPayload(BaseModel):
    """
    Standardized payload received directly from an ingestion source/adapter
    prior to semantic normalization and deduplication.
    """
    source_name: str
    source_job_id: str
    source_url: str
    title: str
    organization: str
    location_raw: Optional[str] = None
    description_raw: str
    description_html: Optional[str] = None
    salary_raw: Optional[str] = None
    work_mode_raw: Optional[str] = None
    seniority_raw: Optional[str] = None
    destination_url: str
    retrieved_at: datetime = Field(default_factory=utc_now)
    posted_at: Optional[datetime] = None
    extra_metadata: Dict[str, Any] = Field(default_factory=dict)


class JobListing(VersionedBaseModel):
    """
    Normalized Job Listing retrieved from an approved adapter or source.
    Retains full source auditability and tamper-evident content hash.
    """
    id: Optional[str] = None
    title: str
    organization: str
    location: str
    work_mode: WorkMode = WorkMode.UNKNOWN
    seniority: JobSeniority = JobSeniority.UNSPECIFIED
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = "USD"
    skills_required: List[str] = Field(default_factory=list)
    skills_preferred: List[str] = Field(default_factory=list)
    description_text: str
    description_html: Optional[str] = None
    application_method: str = Field(default="url", description="'url', 'email', 'adapter'")
    destination_url: str

    # Source Provenance & Audit
    source_name: str = Field(..., description="e.g. 'greenhouse', 'lever', 'mock_adapter'")
    source_url: str
    content_hash: str = Field(..., description="SHA-256 hash of normalized job description to prevent tampering")
    retrieved_at: datetime = Field(default_factory=utc_now)
    posted_at: Optional[datetime] = None
    is_active: bool = True

    # Cross-Source Deduplication & Linking
    duplicate_of_id: Optional[str] = Field(None, description="Pointer to canonical listing ID if secondary duplicate")
    alternate_sources: List[Dict[str, Any]] = Field(default_factory=list, description="Cross-source linked postings for the same role")
    extra_metadata: Dict[str, Any] = Field(default_factory=dict)


class NormalizationSummary(BaseModel):
    """Telemetry and outcome summary of job normalization and deduplication run."""
    total_raw: int
    total_unique: int
    duplicates_detected: int
    cross_source_links: int
    processed_at: datetime = Field(default_factory=utc_now)

