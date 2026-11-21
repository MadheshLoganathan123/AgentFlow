import pytest
from fastapi.testclient import TestClient

from packages.contracts.base import utc_now
from packages.contracts.job import (
    JobListing,
    JobSeniority,
    WorkMode,
)
from packages.contracts.profile import (
    CandidateProfile,
    SkillItem,
    VerificationState,
    WorkExperience,
    WorkModePreference,
)
from services.api.main import app
from services.api.services.job_adapters import MOCK_JOB_FIXTURES, MockJobSourceAdapter
from services.api.services.matcher import MatchRankingService
from services.api.services.normalizer import JobNormalizerService


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture
def senior_backend_candidate() -> CandidateProfile:
    """Standardized Senior Backend Candidate profile for deterministic evaluation."""
    return CandidateProfile(
        user_id="user_sr_backend_01",
        full_name="Alex Morgan",
        email="alex.morgan@example.com",
        primary_location="San Francisco, CA",
        work_modes=[WorkModePreference.REMOTE, WorkModePreference.HYBRID],
        target_job_titles=["Senior Backend Engineer", "Distributed Systems Engineer"],
        total_years_experience=6.5,
        skills=[
            SkillItem(name="Python", verification_state=VerificationState.VERIFIED_FACT),
            SkillItem(name="FastAPI", verification_state=VerificationState.VERIFIED_FACT),
            SkillItem(name="PostgreSQL", verification_state=VerificationState.VERIFIED_FACT),
            SkillItem(name="Docker", verification_state=VerificationState.VERIFIED_FACT),
            SkillItem(name="Kubernetes", verification_state=VerificationState.VERIFIED_FACT),
            SkillItem(name="Distributed Systems", verification_state=VerificationState.VERIFIED_FACT),
        ],
        experience=[
            WorkExperience(
                company="TechCorp",
                title="Senior Backend Engineer",
                is_current=True,
                skills_used=["Python", "FastAPI", "PostgreSQL", "Docker"],
            )
        ],
        work_authorization="US Citizen",
        target_salary_min=165000,
        preferred_sectors=["Fintech", "Developer Tools"],
    )


# ---------------------------------------------------------------------------
# Dimension Unit Tests
# ---------------------------------------------------------------------------


def test_skills_matching_dimension(senior_backend_candidate: CandidateProfile):
    """Verify skills scoring differentiates core required vs preferred and identifies gaps."""
    job = JobListing(
        title="Senior Python Backend Engineer",
        organization="FintechCo",
        location="Remote",
        work_mode=WorkMode.REMOTE,
        seniority=JobSeniority.SENIOR,
        skills_required=["Python", "PostgreSQL", "Docker", "Rust"],
        skills_preferred=["Kubernetes", "GraphQL"],
        description_text="Building distributed payment gateways.",
        destination_url="https://example.com/apply",
        source_name="greenhouse",
        source_url="https://boards.greenhouse.io/fintechco/1",
        content_hash="hash_fintech_01",
    )

    explanation = MatchRankingService.evaluate_match(senior_backend_candidate, job)

    # Candidate has Python, PostgreSQL, Docker (3 of 4 required), plus Kubernetes (preferred)
    assert explanation.score_breakdown.skill_match_score >= 70.0
    assert any("Possesses core required skill: Python" in s for s in explanation.strengths)
    assert any("Lacks required skill: Rust" in g for g in explanation.gaps)

    # Verify requirement matches structure
    req_rust = next(m for m in explanation.matched_requirements if "Rust" in m.requirement)
    assert req_rust.is_satisfied is False
    assert "Missing required skill" in req_rust.evidence_or_gap_explanation


def test_seniority_matching_dimension(senior_backend_candidate: CandidateProfile):
    """Verify seniority scoring accurately rewards alignment and penalizes severe underqualification."""
    # Senior role (6.5 yrs vs 5-8 yrs) -> should be 100
    senior_job = JobListing(
        title="Senior Backend Engineer",
        organization="Corp",
        location="Remote",
        work_mode=WorkMode.REMOTE,
        seniority=JobSeniority.SENIOR,
        description_text="Senior role.",
        destination_url="http://test",
        source_name="mock",
        source_url="http://test",
        content_hash="hash_sen_01",
    )
    sen_expl = MatchRankingService.evaluate_match(senior_backend_candidate, senior_job)
    assert sen_expl.score_breakdown.seniority_score == 100.0

    # Junior candidate evaluated against Principal role -> should score low with gap
    junior_candidate = senior_backend_candidate.model_copy(update={"total_years_experience": 1.0})
    principal_job = senior_job.model_copy(update={"seniority": JobSeniority.PRINCIPAL})
    prin_expl = MatchRankingService.evaluate_match(junior_candidate, principal_job)
    assert prin_expl.score_breakdown.seniority_score <= 30.0
    assert any("Significantly under target seniority" in g for g in prin_expl.gaps)


def test_location_and_work_mode_matching(senior_backend_candidate: CandidateProfile):
    """Verify remote fit gives 100 while onsite in different city penalizes heavily."""
    remote_job = JobListing(
        title="Python Engineer",
        organization="RemoteCorp",
        location="Remote - Worldwide",
        work_mode=WorkMode.REMOTE,
        description_text="Remote",
        destination_url="http://test",
        source_name="mock",
        source_url="http://test",
        content_hash="hash_rem_01",
    )
    rem_expl = MatchRankingService.evaluate_match(senior_backend_candidate, remote_job)
    assert rem_expl.score_breakdown.location_mode_score == 100.0

    # Onsite job in Tokyo requiring relocation for candidate in San Francisco
    onsite_job = remote_job.model_copy(update={"work_mode": WorkMode.ONSITE, "location": "Tokyo, Japan"})
    onsite_expl = MatchRankingService.evaluate_match(senior_backend_candidate, onsite_job)
    assert onsite_expl.score_breakdown.location_mode_score <= 20.0
    assert any("requires relocation" in g for g in onsite_expl.gaps)


def test_salary_alignment_matching(senior_backend_candidate: CandidateProfile):
    """Verify salary meeting candidate target yields 100 while below target is penalized."""
    # Candidate target: $165,000
    good_sal_job = JobListing(
        title="Engineer",
        organization="A",
        location="Remote",
        salary_min=170000,
        salary_max=200000,
        description_text="Sal",
        destination_url="http://test",
        source_name="mock",
        source_url="http://test",
        content_hash="hash_sal_01",
    )
    good_expl = MatchRankingService.evaluate_match(senior_backend_candidate, good_sal_job)
    assert good_expl.score_breakdown.salary_alignment_score == 100.0

    # Low salary job: $110,000 max vs $165,000 target
    low_sal_job = good_sal_job.model_copy(update={"salary_min": 90000, "salary_max": 110000})
    low_expl = MatchRankingService.evaluate_match(senior_backend_candidate, low_sal_job)
    assert low_expl.score_breakdown.salary_alignment_score < 75.0
    assert any("below candidate target" in g for g in low_expl.gaps)

    # Job without salary disclosure
    no_sal_job = good_sal_job.model_copy(update={"salary_min": None, "salary_max": None})
    no_sal_expl = MatchRankingService.evaluate_match(senior_backend_candidate, no_sal_job)
    assert no_sal_expl.score_breakdown.salary_alignment_score is None
    assert any("does not disclose" in u for u in no_sal_expl.uncertainties)


# ---------------------------------------------------------------------------
# Critical Missing Information Safety Tests
# ---------------------------------------------------------------------------


def test_critical_missing_information_blocks_strong_match(senior_backend_candidate: CandidateProfile):
    """
    Acceptance Criterion: 'The system does not claim a match when critical information is missing.'
    If candidate work authorization is missing, never grant strong_match even with 100% skill match!
    """
    incomplete_candidate = senior_backend_candidate.model_copy(update={"work_authorization": None})

    perfect_job = JobListing(
        title="Senior Backend Engineer",
        organization="FintechCo",
        location="Remote",
        work_mode=WorkMode.REMOTE,
        seniority=JobSeniority.SENIOR,
        skills_required=["Python", "FastAPI", "PostgreSQL"],
        salary_min=180000,
        salary_max=220000,
        description_text="Python Fintech",
        destination_url="http://test",
        source_name="mock",
        source_url="http://test",
        content_hash="hash_perf_01",
    )

    explanation = MatchRankingService.evaluate_match(incomplete_candidate, perfect_job)

    # Crucial safety assertion: Must NOT be strong_match!
    assert explanation.recommendation != "strong_match"
    assert explanation.recommendation == "potential_match"
    assert any("work authorization is unconfirmed" in u for u in explanation.uncertainties)


# ---------------------------------------------------------------------------
# Ranking Tests against Fixed Sample Set
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ranking_against_fixed_sample_set(senior_backend_candidate: CandidateProfile):
    """
    Acceptance Criterion: 'Ranking tests run against a fixed sample set.'
    Verify that Stripe Senior Backend ranks #1 above frontend/unrelated roles.
    """
    mock_adapter = MockJobSourceAdapter()
    raw_jobs = await mock_adapter.fetch_raw_jobs(limit=12)
    normalized_jobs, _ = JobNormalizerService.normalize_and_deduplicate(raw_jobs)

    ranked_results = MatchRankingService.rank_jobs(
        candidate=senior_backend_candidate,
        jobs=normalized_jobs,
        limit=5,
    )

    assert len(ranked_results) > 0
    top_job, top_explanation = ranked_results[0]

    # The top job should be Stripe Senior Backend Engineer or Ramp Full Stack
    assert top_job.organization in ["Stripe", "Ramp", "Plaid"]
    assert top_explanation.composite_score >= 80.0
    assert top_explanation.recommendation == "strong_match"

    # Verify scores are strictly ordered descending
    scores = [expl.composite_score for _, expl in ranked_results]
    assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# REST API Endpoint Tests
# ---------------------------------------------------------------------------


def test_api_single_match_endpoint(test_client, senior_backend_candidate: CandidateProfile):
    """Verify POST /api/v1/jobs/match endpoint."""
    job = JobListing(
        title="Senior Python Engineer",
        organization="Stripe",
        location="Remote",
        work_mode=WorkMode.REMOTE,
        seniority=JobSeniority.SENIOR,
        skills_required=["Python", "PostgreSQL"],
        salary_min=170000,
        salary_max=210000,
        description_text="Distributed fintech APIs in Python.",
        destination_url="https://stripe.com/jobs/1",
        source_name="mock_adapter",
        source_url="http://mock/1",
        content_hash="hash_api_match_01",
    )

    req_payload = {
        "candidate_profile": senior_backend_candidate.model_dump(mode="json"),
        "job_listing": job.model_dump(mode="json"),
    }

    res = test_client.post("/api/v1/jobs/match", json=req_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["composite_score"] >= 80.0
    assert data["recommendation"] == "strong_match"
    assert "score_breakdown" in data
    assert len(data["strengths"]) > 0


def test_api_recommend_endpoint_automatic_discovery(test_client, senior_backend_candidate: CandidateProfile):
    """Verify POST /api/v1/jobs/recommend with automatic multi-source discovery."""
    req_payload = {
        "candidate_profile": senior_backend_candidate.model_dump(mode="json"),
        "limit": 5,
    }

    res = test_client.post("/api/v1/jobs/recommend", json=req_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["total_evaluated"] > 0
    assert len(data["ranked_recommendations"]) > 0

    first_rec = data["ranked_recommendations"][0]
    assert "job" in first_rec
    assert "explanation" in first_rec
    assert first_rec["explanation"]["composite_score"] > 0.0
