from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return current UTC timestamp with timezone."""
    return datetime.now(timezone.utc)


class VersionedBaseModel(BaseModel):
    """
    Authoritative base model for all AgentFlow models and agent outputs.
    Guarantees schema versioning, prompt/model provenance, and timestamps.
    """
    schema_version: str = Field(default="1.0.0", description="SemVer version of the data contract")
    model_version: Optional[str] = Field(default=None, description="LLM/ML model used for extraction/generation")
    prompt_version: Optional[str] = Field(default=None, description="Version tag of the prompt used")
    created_at: datetime = Field(default_factory=utc_now, description="UTC creation timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Extensible execution and telemetry metadata")

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "protected_namespaces": ()
    }


class EvidenceReference(BaseModel):
    """
    Represents verifiable evidence extracted from resumes or authoritative sources.
    Crucial for distinguishing verified facts from model inferences.
    """
    source_type: str = Field(..., description="e.g., 'resume_text', 'user_input', 'external_url'")
    source_identifier: str = Field(..., description="File name, section name, URL, or form field ID")
    raw_snippet: Optional[str] = Field(None, description="Verbatim text extracted from source")
    page_number: Optional[int] = Field(None, description="Page number if extracted from a document")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction or verification confidence")
    is_inferred: bool = Field(default=False, description="True if inferred by LLM; False if verbatim from evidence")
    is_user_confirmed: bool = Field(default=False, description="Explicitly confirmed by user")
