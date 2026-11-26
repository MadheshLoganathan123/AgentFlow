from datetime import timedelta
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from packages.contracts.base import utc_now
from packages.contracts.profile import (
    CandidateProfile,
    SkillItem,
    VerificationState,
    WorkExperience,
    WorkModePreference,
)
from packages.db.base import Base
from packages.db.repositories.job_repo import JobRepository
from packages.db.session import get_async_session
from services.api.main import app
from services.api.services.retrieval import JobRetrievalService


@pytest_asyncio.fixture
async def async_test_session() -> AsyncGenerator[AsyncSession, None]:
    """Create an isolated in-memory SQLite database session with static pool."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def client_with_session(async_test_session: AsyncSession):
    """Test client configured with async DB session dependency override."""
    async def override_session():
        yield async_test_session

    app.dependency_overrides[get_async_session] = override_session
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_candidate() -> CandidateProfile:
    return CandidateProfile(
        user_id="usr_audit_lead_01",
        full_name="Jordan Reed",
        email="jordan.reed@example.com",
        primary_location="San Francisco, CA",
        work_modes=[WorkModePreference.REMOTE, WorkModePreference.HYBRID],
        target_job_titles=["Staff Backend Engineer", "Senior Software Engineer"],
        total_years_experience=8.0,
        work_authorization="US Citizen / Green Card",
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
                company="Apex Scale",
                title="Senior Staff Engineer",
                start_date="2020-01",
                end_date=None,
                highlights=["Designed microservices handling 2M req/sec using FastAPI and Kafka"],
            )
        ],
    )


# =============================================================================
# 1. Repository Tests: Upsert & Deduplication Idempotency
# =============================================================================

@pytest.mark.asyncio
async def test_job_repo_upsert_and_deduplication(async_test_session: AsyncSession):
    repo = JobRepository(async_test_session)

    job1 = await repo.upsert_job(
        title="Senior Python Backend Engineer",
        organization="Stripe",
        location="San Francisco, CA",
        source_name="greenhouse",
        source_url="https://boards.greenhouse.io/stripe/jobs/101",
        destination_url="https://stripe.com/jobs/101",
        content_hash="hash_stripe_backend_001",
        description_text="Build scalable payment infrastructure with Python and PostgreSQL.",
        work_mode="remote",
        seniority="senior",
        salary_min=150000,
        salary_max=190000,
        skills_required=["Python", "PostgreSQL", "Distributed Systems"],
        alternate_sources=[{"source": "greenhouse", "url": "https://boards.greenhouse.io/stripe/jobs/101"}],
    )

    assert job1.id is not None
    assert job1.title == "Senior Python Backend Engineer"
    assert job1.content_hash == "hash_stripe_backend_001"
    assert len(job1.alternate_sources) == 1

    # Re-upserting same content hash should return existing record and merge alternate source
    job2 = await repo.upsert_job(
        title="Senior Python Backend Engineer",
        organization="Stripe",
        location="San Francisco, CA",
        source_name="remoteok",
        source_url="https://remoteok.com/j/101",
        destination_url="https://stripe.com/jobs/101",
        content_hash="hash_stripe_backend_001",
        description_text="Duplicate posting from remoteok",
        alternate_sources=[{"source": "remoteok", "url": "https://remoteok.com/j/101"}],
    )

    assert job2.id == job1.id
    assert len(job2.alternate_sources) == 2
    sources = [s["source"] for s in job2.alternate_sources]
    assert "greenhouse" in sources
    assert "remoteok" in sources


# =============================================================================
# 2. Repository Tests: Multi-Facet Search Filters
# =============================================================================

@pytest.mark.asyncio
async def test_job_repo_multi_facet_search(async_test_session: AsyncSession):
    repo = JobRepository(async_test_session)
    now = utc_now()

    # Seed 3 distinct jobs
    await repo.upsert_job(
        title="Staff Platform Engineer",
        organization="DataDog",
        location="New York, NY",
        source_name="greenhouse",
        source_url="https://datadog.com/jobs/1",
        destination_url="https://datadog.com/jobs/1",
        content_hash="hash_datadog_01",
        description_text="Kubernetes and Go telemetry pipelines",
        work_mode="hybrid",
        seniority="lead",
        salary_min=180000,
        salary_max=220000,
        posted_at=now - timedelta(days=1),
    )

    await repo.upsert_job(
        title="Junior Frontend Engineer",
        organization="Figma",
        location="Remote",
        source_name="remoteok",
        source_url="https://figma.com/jobs/2",
        destination_url="https://figma.com/jobs/2",
        content_hash="hash_figma_02",
        description_text="React and TypeScript canvas development",
        work_mode="remote",
        seniority="entry",
        salary_min=90000,
        salary_max=120000,
        posted_at=now - timedelta(days=5),
    )

    await repo.upsert_job(
        title="Senior Machine Learning Engineer",
        organization="Anthropic",
        location="San Francisco, CA",
        source_name="greenhouse",
        source_url="https://anthropic.com/jobs/3",
        destination_url="https://anthropic.com/jobs/3",
        content_hash="hash_anthropic_03",
        description_text="LLM alignment and Python PyTorch inference",
        work_mode="onsite",
        seniority="senior",
        salary_min=200000,
        salary_max=280000,
        posted_at=now - timedelta(days=10),
    )

    # 1. Search by organization
    results_org = await repo.search_jobs(organization="DataDog")
    assert len(results_org) == 1
    assert results_org[0].organization == "DataDog"

    # 2. Search by work mode
    results_remote = await repo.search_jobs(work_mode="remote")
    assert len(results_remote) == 1
    assert results_remote[0].organization == "Figma"

    # 3. Search by seniority
    results_lead = await repo.search_jobs(seniority="lead")
    assert len(results_lead) == 1
    assert results_lead[0].title == "Staff Platform Engineer"

    # 4. Search by salary minimum (>= 190000)
    results_high_pay = await repo.search_jobs(min_salary=190000)
    assert len(results_high_pay) == 2  # DataDog (max 220k >= 190k) and Anthropic (min 200k >= 190k)

    # 5. Search by recency (posted in last 3 days)
    results_recent = await repo.search_jobs(posted_after=now - timedelta(days=3))
    assert len(results_recent) == 1
    assert results_recent[0].organization == "DataDog"

    # 6. Search free text query matching description
    results_query = await repo.search_jobs(query="PyTorch")
    assert len(results_query) == 1
    assert results_query[0].organization == "Anthropic"


# =============================================================================
# 3. Repository Tests: Explainable Match Persistence & User Isolation
# =============================================================================

@pytest.mark.asyncio
async def test_job_repo_match_persistence_and_isolation(async_test_session: AsyncSession):
    repo = JobRepository(async_test_session)

    job = await repo.upsert_job(
        title="Staff Systems Architect",
        organization="CloudScale",
        location="Remote",
        source_name="greenhouse",
        source_url="https://cloudscale.io/j/1",
        destination_url="https://cloudscale.io/j/1",
        content_hash="hash_cloudscale_01",
        description_text="High performance distributed systems in Rust and Python",
    )

    # Save match for User A
    match_a = await repo.save_match(
        user_id="user_alpha",
        profile_id="profile_alpha_01",
        job_id=job.id,
        composite_score=88.5,
        score_breakdown={"skills_match": 90.0, "experience_level": 85.0},
        strengths=["Exceptional Python expertise"],
        gaps=["No previous Rust exposure"],
        uncertainties=[],
        matched_requirements=[{"skill": "Python", "status": "verified"}],
        recommendation="strong_match",
    )
    assert match_a.id is not None
    assert match_a.composite_score == 88.5

    # Save match for User B on the same job
    await repo.save_match(
        user_id="user_bravo",
        profile_id="profile_bravo_02",
        job_id=job.id,
        composite_score=52.0,
        score_breakdown={"skills_match": 50.0, "experience_level": 55.0},
        strengths=["Good general engineering"],
        gaps=["Missing 4 core requirements"],
        uncertainties=[],
        matched_requirements=[],
        recommendation="unsuitable",
    )

    # Verify strict user isolation
    matches_alpha = await repo.list_matches_for_user(user_id="user_alpha")
    matches_bravo = await repo.list_matches_for_user(user_id="user_bravo")

    assert len(matches_alpha) == 1
    assert matches_alpha[0].user_id == "user_alpha"
    assert matches_alpha[0].composite_score == 88.5

    assert len(matches_bravo) == 1
    assert matches_bravo[0].user_id == "user_bravo"
    assert matches_bravo[0].composite_score == 52.0

    # Idempotent match score update for User A
    updated_match_a = await repo.save_match(
        user_id="user_alpha",
        profile_id="profile_alpha_01",
        job_id=job.id,
        composite_score=92.0,
        score_breakdown={"skills_match": 95.0, "experience_level": 90.0},
        strengths=["Updated certifications verified"],
        gaps=[],
        uncertainties=[],
        matched_requirements=[{"skill": "Python", "status": "verified"}],
        recommendation="strong_match",
    )
    assert updated_match_a.id == match_a.id
    assert updated_match_a.composite_score == 92.0


# =============================================================================
# 4. Repository Tests: Shortlist Actions & User Isolation
# =============================================================================

@pytest.mark.asyncio
async def test_job_repo_shortlist_actions_and_isolation(async_test_session: AsyncSession):
    repo = JobRepository(async_test_session)

    job = await repo.upsert_job(
        title="Lead Cloud Engineer",
        organization="CloudFast",
        location="Austin, TX",
        source_name="greenhouse",
        source_url="https://cloudfast.io/j/2",
        destination_url="https://cloudfast.io/j/2",
        content_hash="hash_cloudfast_02",
        description_text="Lead AWS and Kubernetes cloud engineering team",
    )

    # User A shortlists the job
    saved_a = await repo.save_or_shortlist_job(
        user_id="user_alice",
        job_id=job.id,
        status="shortlisted",
        notes="High compensation and remote friendly",
    )
    assert saved_a.status == "shortlisted"
    assert saved_a.user_notes == "High compensation and remote friendly"

    # User B marks the exact same job as dismissed
    saved_b = await repo.save_or_shortlist_job(
        user_id="user_bob",
        job_id=job.id,
        status="dismissed",
        notes="Too much travel required",
    )
    assert saved_b.status == "dismissed"

    # User isolation check
    alice_saved = await repo.list_saved_jobs(user_id="user_alice")
    bob_saved = await repo.list_saved_jobs(user_id="user_bob")

    assert len(alice_saved) == 1
    assert alice_saved[0].status == "shortlisted"
    assert len(bob_saved) == 1
    assert bob_saved[0].status == "dismissed"

    # Status update: Alice changes from 'shortlisted' to 'saved'
    updated_alice = await repo.save_or_shortlist_job(
        user_id="user_alice",
        job_id=job.id,
        status="saved",
    )
    assert updated_alice.id == saved_a.id
    assert updated_alice.status == "saved"

    # Remove saved job
    removed = await repo.remove_saved_job(user_id="user_alice", job_id=job.id)
    assert removed is True
    assert await repo.get_saved_job(user_id="user_alice", job_id=job.id) is None
    # Bob's decision is undisturbed
    assert await repo.get_saved_job(user_id="user_bob", job_id=job.id) is not None


# =============================================================================
# 5. Service Tests: Hybrid Search & Retrieval Service
# =============================================================================

@pytest.mark.asyncio
async def test_job_retrieval_service_hybrid_search(
    async_test_session: AsyncSession,
    sample_candidate: CandidateProfile,
):
    repo = JobRepository(async_test_session)
    retrieval_service = JobRetrievalService(repo)

    # Populate 2 jobs in DB
    await repo.upsert_job(
        title="Senior Python Backend Engineer",
        organization="ScaleAI",
        location="San Francisco, CA",
        source_name="greenhouse",
        source_url="https://scale.com/jobs/1",
        destination_url="https://scale.com/jobs/1",
        content_hash="hash_scale_01",
        description_text="Develop high throughput data infrastructure using Python, FastAPI, and PostgreSQL.",
        work_mode="remote",
        seniority="senior",
        salary_min=160000,
        salary_max=210000,
        skills_required=["Python", "FastAPI", "PostgreSQL"],
    )

    await repo.upsert_job(
        title="Frontend React Specialist",
        organization="PixelArt",
        location="Remote",
        source_name="remoteok",
        source_url="https://pixelart.com/jobs/2",
        destination_url="https://pixelart.com/jobs/2",
        content_hash="hash_pixel_02",
        description_text="Build animated UIs with React, CSS, and Figma.",
        work_mode="remote",
        seniority="mid",
        salary_min=110000,
        salary_max=140000,
        skills_required=["React", "CSS", "TypeScript"],
    )

    # Hybrid search with seniority="senior" and query="Python"
    results = await retrieval_service.hybrid_search_and_rank(
        candidate=sample_candidate,
        user_id="usr_audit_lead_01",
        query="Python",
        seniority="senior",
        persist_matches=True,
    )

    assert len(results) == 1
    job, explanation = results[0]
    assert job.title == "Senior Python Backend Engineer"
    assert explanation.composite_score >= 80.0
    assert explanation.recommendation == "strong_match"

    # Verify match persistence in database
    persisted_match = await repo.get_match(user_id="usr_audit_lead_01", job_id=job.id)
    assert persisted_match is not None
    assert persisted_match.composite_score == explanation.composite_score


# =============================================================================
# 6. REST API Endpoint Tests
# =============================================================================

def test_api_job_persist_and_search_flow(client_with_session: TestClient):
    # 1. Bulk persist 2 normalized jobs
    job_payload_1 = {
        "title": "Principal Distributed Systems Engineer",
        "organization": "CockroachDB",
        "location": "Remote",
        "work_mode": "remote",
        "seniority": "lead",
        "salary_min": 210000,
        "salary_max": 260000,
        "salary_currency": "USD",
        "skills_required": ["Go", "Distributed Systems", "Kubernetes"],
        "skills_preferred": ["Python"],
        "description_text": "Architect next-generation resilient distributed transactional storage.",
        "application_method": "url",
        "destination_url": "https://cockroachlabs.com/careers/1",
        "source_name": "greenhouse",
        "source_url": "https://cockroachlabs.com/careers/1",
        "content_hash": "hash_crdb_01",
        "posted_at": utc_now().isoformat(),
        "alternate_sources": [],
    }

    job_payload_2 = {
        "title": "Junior QA Automation Engineer",
        "organization": "TestCo",
        "location": "Boston, MA",
        "work_mode": "onsite",
        "seniority": "entry",
        "salary_min": 75000,
        "salary_max": 90000,
        "salary_currency": "USD",
        "skills_required": ["Selenium", "Python"],
        "skills_preferred": [],
        "description_text": "Write end-to-end integration tests using Selenium.",
        "application_method": "url",
        "destination_url": "https://testco.com/careers/2",
        "source_name": "remoteok",
        "source_url": "https://testco.com/careers/2",
        "content_hash": "hash_testco_02",
        "posted_at": utc_now().isoformat(),
        "alternate_sources": [],
    }

    resp = client_with_session.post(
        "/api/v1/jobs/persist",
        json={"jobs": [job_payload_1, job_payload_2]},
    )
    assert resp.status_code == 200
    persist_data = resp.json()
    assert persist_data["persisted_count"] == 2
    job_id_1, job_id_2 = persist_data["job_ids"]

    # 2. Multi-facet search: work_mode=remote, seniority=lead
    search_resp = client_with_session.get(
        "/api/v1/jobs/search",
        params={"work_mode": "remote", "seniority": "lead"},
    )
    assert search_resp.status_code == 200
    search_results = search_resp.json()
    assert len(search_results) == 1
    assert search_results[0]["organization"] == "CockroachDB"

    # 3. Retrieve single job by ID
    get_job_resp = client_with_session.get(f"/api/v1/jobs/{job_id_1}")
    assert get_job_resp.status_code == 200
    assert get_job_resp.json()["id"] == job_id_1

    # 4. User Shortlist Action
    action_resp = client_with_session.post(
        f"/api/v1/jobs/{job_id_1}/action",
        json={"user_id": "usr_client_01", "status": "shortlisted", "notes": "Dream distributed systems role"},
    )
    assert action_resp.status_code == 200
    action_data = action_resp.json()
    assert action_data["status"] == "shortlisted"
    assert action_data["user_notes"] == "Dream distributed systems role"

    # 5. List saved jobs
    saved_resp = client_with_session.get("/api/v1/jobs/saved", params={"user_id": "usr_client_01"})
    assert saved_resp.status_code == 200
    saved_list = saved_resp.json()
    assert len(saved_list) == 1
    assert saved_list[0]["job_id"] == job_id_1

    # 6. Remove saved job
    delete_resp = client_with_session.delete(
        f"/api/v1/jobs/{job_id_1}/saved",
        params={"user_id": "usr_client_01"},
    )
    assert delete_resp.status_code == 200

    # Verify empty list
    saved_resp_after = client_with_session.get("/api/v1/jobs/saved", params={"user_id": "usr_client_01"})
    assert saved_resp_after.status_code == 200
    assert len(saved_resp_after.json()) == 0


def test_api_hybrid_search_and_rank(client_with_session: TestClient, sample_candidate: CandidateProfile):
    # 1. Seed job
    job_payload = {
        "title": "Senior Backend Infrastructure Engineer",
        "organization": "FastScale",
        "location": "San Francisco, CA",
        "work_mode": "remote",
        "seniority": "senior",
        "salary_min": 170000,
        "salary_max": 220000,
        "salary_currency": "USD",
        "skills_required": ["Python", "FastAPI", "PostgreSQL", "Docker"],
        "skills_preferred": ["Distributed Systems"],
        "description_text": "Design and operate distributed microservices with Python, FastAPI, and Docker.",
        "application_method": "url",
        "destination_url": "https://fastscale.io/careers/10",
        "source_name": "greenhouse",
        "source_url": "https://fastscale.io/careers/10",
        "content_hash": "hash_fastscale_10",
        "posted_at": utc_now().isoformat(),
        "alternate_sources": [],
    }

    persist_res = client_with_session.post("/api/v1/jobs/persist", json={"jobs": [job_payload]})
    assert persist_res.status_code == 200

    # 2. Call /api/v1/jobs/search-and-rank
    req_body = {
        "candidate_profile": sample_candidate.model_dump(mode="json"),
        "user_id": "usr_audit_lead_01",
        "work_mode": "remote",
        "seniority": "senior",
        "min_salary": 160000,
        "persist_matches": True,
    }

    rank_resp = client_with_session.post("/api/v1/jobs/search-and-rank", json=req_body)
    assert rank_resp.status_code == 200
    data = rank_resp.json()
    assert data["total_evaluated"] >= 1
    top_rec = data["ranked_recommendations"][0]
    assert top_rec["job"]["organization"] == "FastScale"
    assert top_rec["explanation"]["composite_score"] >= 80.0
