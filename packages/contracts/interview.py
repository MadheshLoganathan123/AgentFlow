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


class InterviewQuestion(BaseModel):
    id: str
    category: str = Field(..., description="'behavioral', 'system_design', 'technical', 'company_specific'")
    question: str
    recommended_framing: str = Field(default="STAR", description="'STAR', 'CAR', 'technical_breakdown'")
    rubric_points: List[str] = Field(default_factory=list)


class PracticeFeedback(BaseModel):
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
    questions: List[InterviewQuestion] = Field(default_factory=list)
    feedback_history: List[PracticeFeedback] = Field(default_factory=list)

