from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from packages.contracts.base import VersionedBaseModel, utc_now


class SourceCitation(BaseModel):
    id: Optional[str] = None
    title: str
    url: str
    source_name: str
    retrieval_date: datetime = Field(default_factory=utc_now)
    excerpt: str
    is_company_specific: bool = True
    content_hash: Optional[str] = None
    source_category: str = "engineering_blog"
    is_reported: bool = False
    report_reason: Optional[str] = None


class ResearchSource(VersionedBaseModel):
    """
    Research source curated by the Research and Interview Coach.
    Preserves source URL, retrieval timestamp, author/domain, and trustworthiness classification.
    """
    id: Optional[str] = None
    source_url: str
    source_title: str
    source_domain: str
    retrieved_at: datetime = Field(default_factory=utc_now)
    publication_date: Optional[str] = None
    is_reputable: bool = True
    is_company_specific: bool = True
    content_excerpt: str
    source_reliability_score: float = Field(default=1.0, ge=0.0, le=1.0)
    content_hash: Optional[str] = None
    source_category: str = "engineering_blog"
    is_reported: bool = False
    report_reason: Optional[str] = None


class ResearchSummary(VersionedBaseModel):
    """
    Comprehensive research summary for a target company and role.
    Enforces allowlist boundaries, separates company-specific intelligence
    from generic industry advice, and retains cryptographic content hashes.
    """
    company_name: str
    target_role: Optional[str] = None
    job_id: Optional[str] = None
    sources: List[ResearchSource] = Field(default_factory=list)
    company_specific_sources: List[ResearchSource] = Field(default_factory=list)
    general_advice_sources: List[ResearchSource] = Field(default_factory=list)
    tech_stack_observations: List[str] = Field(default_factory=list)
    culture_and_values: List[str] = Field(default_factory=list)
    recent_news_or_milestones: List[str] = Field(default_factory=list)
    interview_topics_suggested: List[str] = Field(default_factory=list)
    allowlist_status: str = "verified_allowlist_sources"
    warnings: List[str] = Field(default_factory=list)
    retrieved_at: datetime = Field(default_factory=utc_now)


class ReportSourceRequest(BaseModel):
    reason: str = Field(..., min_length=3, description="Reason for reporting source (stale, inaccurate, scam, broken)")


class ValidateUrlRequest(BaseModel):
    url: str = Field(..., description="Target URL to check against the allowlist")


class ValidateUrlResponse(BaseModel):
    url: str
    is_allowlisted: bool
    domain: str
    category: Optional[str] = None
    message: str


class CompanyResearchRequest(BaseModel):
    company_name: str = Field(..., min_length=1)
    role_title: Optional[str] = None
    job_id: Optional[str] = None
    force_refresh: bool = False


class InterviewQuestion(BaseModel):
    id: str
    category: str = Field(..., description="'behavioral', 'system_design', 'technical', 'company_specific'")
    question: str
    recommended_framing: str = Field(default="STAR", description="'STAR', 'CAR', 'technical_breakdown'")
    rubric_points: List[str] = Field(default_factory=list)


class QuestionSet(VersionedBaseModel):
    """
    Curated question set by role, seniority, and practice rubric.
    """
    id: Optional[str] = None
    role_title: str
    seniority: str
    estimated_time_minutes: int = 45
    questions: List[InterviewQuestion] = Field(default_factory=list)
    evaluation_rubric_summary: str = "Evaluated on clarity, impact metrics, technical correctness, and structure"


class PracticeFeedback(VersionedBaseModel):
    question_id: str
    answer_text: str
    strengths: List[str] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)
    rubric_score: float = Field(..., ge=0.0, le=100.0)
    coaching_tips: List[str] = Field(default_factory=list)


class InterviewPlan(VersionedBaseModel):
    """
    Role and company-specific interview preparation curriculum with source citations.
    """
    id: Optional[str] = None
    role_title: str
    company_name: str
    seniority: str
    company_research_summary: str
    citations: List[SourceCitation] = Field(default_factory=list)
    sources: List[ResearchSource] = Field(default_factory=list)
    question_sets: List[QuestionSet] = Field(default_factory=list)
    questions: List[InterviewQuestion] = Field(default_factory=list)
    feedback_history: List[PracticeFeedback] = Field(default_factory=list)
