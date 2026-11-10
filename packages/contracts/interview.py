from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from packages.contracts.base import VersionedBaseModel, utc_now


class SourceCitation(BaseModel):
    title: str
    url: str
    source_name: str
    retrieval_date: datetime = Field(default_factory=utc_now)
    excerpt: str
    is_company_specific: bool = True


class ResearchSource(VersionedBaseModel):
    """
    Research source curated by the Research and Interview Coach.
    Preserves source URL, retrieval timestamp, author/domain, and trustworthiness classification.
    """
    source_url: str
    source_title: str
    source_domain: str
    retrieved_at: datetime = Field(default_factory=utc_now)
    publication_date: Optional[str] = None
    is_reputable: bool = True
    is_company_specific: bool = True
    content_excerpt: str
    source_reliability_score: float = Field(default=1.0, ge=0.0, le=1.0)


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


