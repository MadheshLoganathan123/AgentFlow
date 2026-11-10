from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import Field

from packages.contracts.base import VersionedBaseModel, utc_now


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

