import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from packages.db.base import Base
from packages.db.repositories import (
    CheckpointRepository,
    JobRepository,
    ProfileRepository,
    UserRepository,
)


@pytest_asyncio.fixture
async def async_test_session():
    """Create an isolated in-memory SQLite database session."""
    from sqlalchemy.pool import StaticPool

    # StaticPool ensures all connections share the same in-memory DB instance,
    # so schema created in one connection is visible to subsequent connections.
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


@pytest.mark.asyncio
async def test_cross_account_profile_isolation(async_test_session: AsyncSession):
    """Verify that User A cannot read, access, or confirm User B's candidate profile."""
    user_repo = UserRepository(async_test_session)
    profile_repo = ProfileRepository(async_test_session)

    # Create two distinct users
    user_alice = await user_repo.create(email="alice@company.com", full_name="Alice Candidate")
    user_bob = await user_repo.create(email="bob@company.com", full_name="Bob Candidate")

    # Create profile belonging to Alice
    alice_profile = await profile_repo.create_profile(
        user_id=user_alice.id,
        full_name="Alice Candidate",
        raw_resume_text="Confidential resume of Alice with proprietary project data."
    )

    # 1. Alice queries her own profile -> Success
    alice_view = await profile_repo.get_by_id_for_user(profile_id=alice_profile.id, user_id=user_alice.id)
    assert alice_view is not None
    assert alice_view.id == alice_profile.id

    # 2. Bob attempts to access Alice's profile -> Blocked / Returns None
    bob_view = await profile_repo.get_by_id_for_user(profile_id=alice_profile.id, user_id=user_bob.id)
    assert bob_view is None, "Cross-account profile leakage detected! Bob was able to retrieve Alice's profile."

    # 3. Bob attempts to confirm or mutate Alice's profile -> Blocked / Returns None
    bob_confirm = await profile_repo.confirm_profile(
        profile_id=alice_profile.id,
        user_id=user_bob.id,
        updated_fields={"full_name": "Tampered By Bob"}
    )
    assert bob_confirm is None, "Cross-account unauthorized mutation! Bob was able to confirm Alice's profile."

    # Verify Alice's profile was not tampered with
    alice_check = await profile_repo.get_by_id_for_user(profile_id=alice_profile.id, user_id=user_alice.id)
    assert alice_check.full_name == "Alice Candidate"
    assert not alice_check.is_profile_confirmed


@pytest.mark.asyncio
async def test_cross_account_workflow_checkpoint_isolation(async_test_session: AsyncSession):
    """Verify that User A cannot view User B's paused LangGraph workflow checkpoints."""
    user_repo = UserRepository(async_test_session)
    checkpoint_repo = CheckpointRepository(async_test_session)

    user_alice = await user_repo.create(email="alice2@example.com", full_name="Alice 2")
    user_bob = await user_repo.create(email="bob2@example.com", full_name="Bob 2")

    # Alice has a paused workflow checkpoint
    await checkpoint_repo.save_checkpoint(
        workflow_id="wf_secret_alice",
        user_id=user_alice.id,
        current_stage="awaiting_profile_confirmation",
        state_payload={"confidential_notes": "Alice's career goals"},
        is_paused=True
    )

    # Bob queries Alice's workflow_id -> Returns None
    bob_checkpoint = await checkpoint_repo.get_latest_checkpoint(
        workflow_id="wf_secret_alice",
        user_id=user_bob.id
    )
    assert bob_checkpoint is None, "Cross-account checkpoint leakage! Bob accessed Alice's workflow state."


@pytest.mark.asyncio
async def test_cross_account_saved_jobs_isolation(async_test_session: AsyncSession):
    """Verify that User A's saved and shortlisted jobs cannot be viewed or modified by User B."""
    user_repo = UserRepository(async_test_session)
    job_repo = JobRepository(async_test_session)

    user_alice = await user_repo.create(email="alice_jobs@example.com", full_name="Alice Jobs")
    user_bob = await user_repo.create(email="bob_jobs@example.com", full_name="Bob Jobs")

    job = await job_repo.upsert_job(
        title="Principal AI Architect",
        organization="OpenAI",
        location="San Francisco, CA",
        source_name="greenhouse",
        source_url="https://openai.com/careers/1",
        destination_url="https://openai.com/careers/1",
        content_hash="hash_openai_arch_01",
        description_text="Architect frontier model infrastructure",
    )

    # Alice shortlists the job
    await job_repo.save_or_shortlist_job(
        user_id=user_alice.id,
        job_id=job.id,
        status="shortlisted",
        notes="Alice's top target role",
    )

    # Bob's query for saved jobs must be empty
    bob_saved = await job_repo.list_saved_jobs(user_id=user_bob.id)
    assert len(bob_saved) == 0, "Cross-user saved job leakage! Bob sees Alice's saved jobs."

    # Bob cannot fetch Alice's saved job directly
    bob_fetch = await job_repo.get_saved_job(user_id=user_bob.id, job_id=job.id)
    assert bob_fetch is None, "Bob was able to fetch Alice's saved job entry."

    # Bob attempting to delete Alice's saved job fails
    bob_delete = await job_repo.remove_saved_job(user_id=user_bob.id, job_id=job.id)
    assert bob_delete is False, "Bob was able to delete Alice's saved job record."

    # Alice's saved record remains intact
    alice_saved = await job_repo.get_saved_job(user_id=user_alice.id, job_id=job.id)
    assert alice_saved is not None
    assert alice_saved.status == "shortlisted"
    assert alice_saved.user_notes == "Alice's top target role"


@pytest.mark.asyncio
async def test_cross_account_job_matches_isolation(async_test_session: AsyncSession):
    """Verify that User A's explainable match evaluations are isolated from User B."""
    user_repo = UserRepository(async_test_session)
    job_repo = JobRepository(async_test_session)

    user_alice = await user_repo.create(email="alice_match@example.com", full_name="Alice Match")
    user_bob = await user_repo.create(email="bob_match@example.com", full_name="Bob Match")

    job = await job_repo.upsert_job(
        title="Distinguished Engineer",
        organization="Google",
        location="Mountain View, CA",
        source_name="greenhouse",
        source_url="https://google.com/careers/2",
        destination_url="https://google.com/careers/2",
        content_hash="hash_google_dist_02",
        description_text="Lead company-wide technical strategy",
    )

    await job_repo.save_match(
        user_id=user_alice.id,
        profile_id="prof_alice",
        job_id=job.id,
        composite_score=94.5,
        score_breakdown={"skills_match": 95.0, "seniority": 90.0},
        strengths=["Top-tier industry background"],
        gaps=[],
        uncertainties=[],
        matched_requirements=[{"skill": "Distributed Systems", "status": "verified"}],
        recommendation="strong_match",
    )

    # Bob querying matches sees nothing
    bob_matches = await job_repo.list_matches_for_user(user_id=user_bob.id)
    assert len(bob_matches) == 0, "Bob accessed Alice's match records!"

    bob_match_record = await job_repo.get_match(user_id=user_bob.id, job_id=job.id)
    assert bob_match_record is None, "Bob retrieved Alice's match evaluation."


