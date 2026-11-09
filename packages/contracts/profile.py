from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from packages.contracts.base import EvidenceReference, VersionedBaseModel, utc_now


class WorkModePreference(str, Enum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    ANY = "any"


class VerificationState(str, Enum):
    VERIFIED_FACT = "verified_fact"
    INFERRED = "inferred"
    USER_CONFIRMED = "user_confirmed"
    USER_EDITED = "user_edited"
    UNCONFIRMED = "unconfirmed"


class SkillItem(BaseModel):
    name: str
    category: Optional[str] = "technical"
    years_experience: Optional[float] = None
    verification_state: VerificationState = VerificationState.UNCONFIRMED
    evidence: Optional[EvidenceReference] = None


class WorkExperience(BaseModel):
    company: str
    title: str
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None  # None or "Present"
    is_current: bool = False
    highlights: List[str] = Field(default_factory=list)
    skills_used: List[str] = Field(default_factory=list)
    evidence: Optional[EvidenceReference] = None


class Education(BaseModel):
    institution: str
    degree: str
    field_of_study: Optional[str] = None
    graduation_year: Optional[int] = None
    evidence: Optional[EvidenceReference] = None


class MissingFieldNotice(BaseModel):
    field_name: str
    description: str
    is_critical_for_matching: bool = True
    suggested_question: str


class CandidateProfile(VersionedBaseModel):
    """
    Structured profile representing the candidate.
    Distinguishes verified resume facts from inferred or missing information.
    """
    id: Optional[str] = None
    user_id: str
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    primary_location: Optional[str] = None
    work_modes: List[WorkModePreference] = Field(default_factory=lambda: [WorkModePreference.REMOTE])
    target_job_titles: List[str] = Field(default_factory=list)
    total_years_experience: Optional[float] = None
    skills: List[SkillItem] = Field(default_factory=list)
    experience: List[WorkExperience] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    work_authorization: Optional[str] = None
    notice_period_days: Optional[int] = None
    target_salary_min: Optional[int] = None
    target_salary_max: Optional[int] = None
    preferred_sectors: List[str] = Field(default_factory=list)
    preferred_organizations: List[str] = Field(default_factory=list)

    # Verification and provenance audit
    is_profile_confirmed: bool = False
    confirmed_at: Optional[str] = None
    missing_fields: List[MissingFieldNotice] = Field(default_factory=list)
    inferred_fields: List[str] = Field(default_factory=list)
    raw_resume_text: Optional[str] = None

