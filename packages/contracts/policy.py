from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from packages.contracts.base import VersionedBaseModel


class PolicyCheckType(str, Enum):
    PRIVACY = "privacy"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    DUPLICATE_APPLICATION = "duplicate_application"
    SUSPICIOUS_LISTING = "suspicious_listing"
    UNSAFE_INSTRUCTION = "unsafe_instruction"
    SOURCE_QUALITY = "source_quality"
    APPROVAL_GATE_REQUIRED = "approval_gate_required"


class PolicySeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"


class PolicyViolation(BaseModel):
    """
    Specific violation or issue flagged during policy evaluation.
    """
    check_type: PolicyCheckType
    severity: PolicySeverity
    message: str
    offending_field_or_text: Optional[str] = None
    remediation_hint: Optional[str] = None


class PrivacyRedaction(BaseModel):
    """
    Tracks fields or PII scrubbed/redacted from inputs or logs.
    """
    field_name: str
    redaction_type: str = Field(..., description="'email', 'phone', 'ssn', 'address', 'token'")
    redacted_preview: str = "[REDACTED]"


class PolicyReviewResult(VersionedBaseModel):
    """
    Authoritative quality gate result from the Policy and Quality Reviewer Agent.
    Enforces that ungrounded claims, privacy violations, or suspicious jobs require
    either remediation or explicit human approval.
    """
    is_safe_to_proceed: bool = Field(
        ...,
        description="True if no blocker violations exist and safety constraints are satisfied"
    )
    overall_quality_score: float = Field(
        default=100.0,
        ge=0.0,
        le=100.0,
        description="Composite score 0-100 indicating confidence, grounding, and policy conformance"
    )
    violations: List[PolicyViolation] = Field(
        default_factory=list,
        description="List of detected policy violations or warnings"
    )
    requires_human_approval: bool = Field(
        default=False,
        description="True if an explicit human confirmation gate is mandatory"
    )
    approval_gate_reason: Optional[str] = Field(
        None,
        description="Reason why human approval was triggered"
    )
    redactions: List[PrivacyRedaction] = Field(
        default_factory=list,
        description="PII or secrets redacted before logging/retention"
    )
    audit_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Audit attributes for tracking reviewer agent run"
    )

