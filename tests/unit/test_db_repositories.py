import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from packages.db.base import Base
from packages.db.repositories import (
    AuditEventRepository,
    CheckpointRepository,
    JobRepository,
    ProfileRepository,
    UserRepository,
)


@pytest.fixture
async def async_test_session():
    """Create an isolated in-memory SQLite database session for repository testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_user_repository_crud(async_test_session: AsyncSession):
    user_repo = UserRepository(async_test_session)
    user = await user_repo.create(email="sarah.connor@example.com", full_name="Sarah Connor")

    assert user.id is not None
    assert user.email == "sarah.connor@example.com"

    fetched = await user_repo.get_by_email("sarah.connor@example.com")
    assert fetched is not None
    assert fetched.id == user.id


@pytest.mark.asyncio
async def test_profile_repository_with_evidence_and_confirmation(async_test_session: AsyncSession):
    user_repo = UserRepository(async_test_session)
    profile_repo = ProfileRepository(async_test_session)

    user = await user_repo.create(email="dev@example.com", full_name="Jane Dev")

    # 1. Create candidate profile (unconfirmed initially)
    profile = await profile_repo.create_profile(
        user_id=user.id,
        full_name="Jane Dev",
        email="dev@example.com",
        primary_location="Remote",
        total_years_experience=6.0,
        raw_resume_text="Senior Python Engineer with 6 years experience at ACME"
    )
    assert not profile.is_profile_confirmed
    assert profile.confirmed_at is None

    # 2. Add factual evidence vs inferred evidence
    fact_ev = await profile_repo.add_evidence(
        profile_id=profile.id,
        field_name="skills.Python",
        source_type="resume_text",
        source_identifier="skills_section",
        raw_snippet="Python 6 years",
        confidence_score=1.0,
        is_inferred=False
    )
    assert not fact_ev.is_inferred
    assert not fact_ev.is_user_confirmed

    inferred_ev = await profile_repo.add_evidence(
        profile_id=profile.id,
        field_name="seniority",
        source_type="llm_inference",
        source_identifier="experience_length",
        raw_snippet="Inferred Senior from 6 years",
        confidence_score=0.8,
        is_inferred=True
    )
    assert inferred_ev.is_inferred

    # 3. Confirm profile via Human Approval Gate
    confirmed_profile = await profile_repo.confirm_profile(
        profile_id=profile.id,
        user_id=user.id,
        updated_fields={"work_authorization": "Authorized"}
    )
    assert confirmed_profile.is_profile_confirmed
    assert confirmed_profile.confirmed_at is not None
    assert confirmed_profile.work_authorization == "Authorized"


@pytest.mark.asyncio
async def test_checkpoint_repository_versioning(async_test_session: AsyncSession):
    user_repo = UserRepository(async_test_session)
    checkpoint_repo = CheckpointRepository(async_test_session)

    user = await user_repo.create(email="flow@example.com", full_name="Flow User")

    # Save version 1
    cp1 = await checkpoint_repo.save_checkpoint(
        workflow_id="wf_101",
        user_id=user.id,
        current_stage="profile_ingestion",
        state_payload={"step": 1},
        is_paused=False
    )
    assert cp1.checkpoint_version == 1

    # Save version 2 (paused at human gate)
    cp2 = await checkpoint_repo.save_checkpoint(
        workflow_id="wf_101",
        user_id=user.id,
        current_stage="awaiting_profile_confirmation",
        state_payload={"step": 2, "pending": True},
        is_paused=True,
        pause_reason="Awaiting user confirmation of profile facts"
    )
    assert cp2.checkpoint_version == 2
    assert cp2.is_paused is True

    # Retrieve latest checkpoint
    latest = await checkpoint_repo.get_latest_checkpoint(workflow_id="wf_101", user_id=user.id)
    assert latest.checkpoint_version == 2
    assert latest.current_stage == "awaiting_profile_confirmation"
    assert latest.is_paused is True


@pytest.mark.asyncio
async def test_job_repository_deduplication(async_test_session: AsyncSession):
    job_repo = JobRepository(async_test_session)

    # Ingest first job
    job1 = await job_repo.upsert_job(
        title="Lead Platform Engineer",
        organization="OpenCorp",
        location="San Francisco, CA",
        source_name="greenhouse",
        source_url="https://boards.greenhouse.io/opencorp/123",
        destination_url="https://opencorp.example/jobs/123",
        content_hash="hash_abc_123_unique",
        description_text="Lead platform engineer working with Python & Docker."
    )
    assert job1.id is not None

    # Ingest same job again with identical content_hash -> should deduplicate
    job2 = await job_repo.upsert_job(
        title="Lead Platform Engineer",
        organization="OpenCorp",
        location="San Francisco, CA",
        source_name="lever",
        source_url="https://jobs.lever.co/opencorp/123",
        destination_url="https://opencorp.example/jobs/123",
        content_hash="hash_abc_123_unique",
        description_text="Lead platform engineer working with Python & Docker."
    )
    assert job1.id == job2.id

