import re
from typing import List, Optional, Set, Tuple

from packages.contracts.job import JobListing
from packages.contracts.match import MatchExplanation
from packages.contracts.profile import CandidateProfile
from packages.db.models import JobListingModel
from packages.db.repositories.job_repo import JobRepository
from services.api.services.matcher import MatchRankingService


class JobRetrievalService:
    """
    Hybrid Search and Retrieval Engine for AgentFlow.
    Combines:
      1. Relational multi-facet database filtering (organization, work mode, seniority, salary bounds).
      2. Lexical / TF-IDF relevance scoring across profile skills, target titles, and job descriptions.
      3. Explainable multi-dimensional match evaluation and ranking.
    """

    def __init__(self, job_repo: JobRepository):
        self.job_repo = job_repo

    async def hybrid_search_and_rank(
        self,
        candidate: CandidateProfile,
        user_id: str,
        query: Optional[str] = None,
        organization: Optional[str] = None,
        location: Optional[str] = None,
        work_mode: Optional[str] = None,
        seniority: Optional[str] = None,
        min_salary: Optional[int] = None,
        max_salary: Optional[int] = None,
        persist_matches: bool = True,
        limit: int = 20,
    ) -> List[Tuple[JobListing, MatchExplanation]]:
        """
        Executes hybrid search:
          1. Multi-facet database retrieval.
          2. Lexical keyword / skill matching.
          3. Multi-dimensional match evaluation.
          4. Persisting match results in PostgreSQL for auditability.
        """
        # Fetch candidate jobs matching relational criteria
        db_jobs = await self.job_repo.search_jobs(
            query=query,
            organization=organization,
            location=location,
            work_mode=work_mode,
            seniority=seniority,
            min_salary=min_salary,
            max_salary=max_salary,
            limit=limit * 3,  # Over-fetch for re-ranking
        )

        if not db_jobs:
            return []

        # Convert DB models to typed contracts
        job_contracts: List[JobListing] = [self._model_to_contract(j) for j in db_jobs]

        # Evaluate matches and rank
        ranked_results = MatchRankingService.rank_jobs(
            candidate=candidate,
            jobs=job_contracts,
            limit=limit,
        )

        # Optionally persist match evaluations into database
        if persist_matches:
            for job, expl in ranked_results:
                if job.id:
                    await self.job_repo.save_match(
                        user_id=user_id,
                        profile_id=candidate.id or f"prof_{user_id}",
                        job_id=job.id,
                        composite_score=expl.composite_score,
                        score_breakdown=expl.score_breakdown.model_dump(),
                        strengths=expl.strengths,
                        gaps=expl.gaps,
                        uncertainties=expl.uncertainties,
                        matched_requirements=[m.model_dump() for m in expl.matched_requirements],
                        recommendation=expl.recommendation,
                    )

        return ranked_results

    @staticmethod
    def _model_to_contract(model: JobListingModel) -> JobListing:
        """Map SQLAlchemy JobListingModel to authoritative JobListing Pydantic contract."""
        return JobListing(
            id=model.id,
            title=model.title,
            organization=model.organization,
            location=model.location,
            work_mode=model.work_mode,
            seniority=model.seniority,
            salary_min=model.salary_min,
            salary_max=model.salary_max,
            salary_currency=model.salary_currency or "USD",
            skills_required=list(model.skills_required or []),
            skills_preferred=list(model.skills_preferred or []),
            description_text=model.description_text,
            description_html=model.description_html,
            application_method=model.application_method or "url",
            destination_url=model.destination_url,
            source_name=model.source_name,
            source_url=model.source_url,
            content_hash=model.content_hash,
            retrieved_at=model.retrieved_at,
            posted_at=model.posted_at,
            is_active=model.is_active,
            duplicate_of_id=getattr(model, "duplicate_of_id", None),
            alternate_sources=list(getattr(model, "alternate_sources", []) or []),
        )

    @classmethod
    def compute_lexical_overlap_score(
        cls,
        candidate_terms: Set[str],
        job_text: str,
    ) -> float:
        """
        Compute normalized term overlap ratio (0-100) between candidate skills/terms and job description.
        """
        if not candidate_terms:
            return 50.0

        job_tokens = set(re.findall(r"\w+", job_text.lower()))
        if not job_tokens:
            return 0.0

        matches = candidate_terms & job_tokens
        return round((len(matches) / len(candidate_terms)) * 100.0, 1)
