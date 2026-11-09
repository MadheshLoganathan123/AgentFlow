from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from packages.contracts.base import EvidenceReference, VersionedBaseModel


class EmailType(str, Enum):
    RECRUITER_OUTREACH = "recruiter_outreach"
    REFERRAL_REQUEST = "referral_request"
    HIRING_MANAGER_NOTE = "hiring_manager_note"
    THANK_YOU = "thank_you"
    FOLLOW_UP = "follow_up"


class EmailDraft(VersionedBaseModel):
    """
    Drafted outreach email grounded in candidate profile and job context.
    Never sent automatically in v1.
    """
    id: Optional[str] = None
    email_type: EmailType
    recipient_name: Optional[str] = None
    recipient_role: Optional[str] = None
    subject: str
    body: str
    call_to_action: str
    tone: str = "professional"
    recipient_assumptions: List[str] = Field(default_factory=list)
    personalization_evidence: List[EvidenceReference] = Field(default_factory=list)
    missing_recipient_warnings: List[str] = Field(default_factory=list)
    variants: List[str] = Field(default_factory=list)
    is_approved_by_user: bool = False

