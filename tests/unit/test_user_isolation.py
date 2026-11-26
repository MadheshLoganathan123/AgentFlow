import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from packages.db.base import Base
from packages.db.repositories import (
    ApplicationPackageRepository,
    CheckpointRepository,
    EmailDraftRepository,
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


@pytest.mark.asyncio
async def test_cross_account_package_isolation(async_test_session: AsyncSession):
    """Verify that User A's tailored application packages are completely isolated from User B."""
    user_repo = UserRepository(async_test_session)
    job_repo = JobRepository(async_test_session)
    package_repo = ApplicationPackageRepository(async_test_session)

    user_alice = await user_repo.create(email="alice_pkg@example.com", full_name="Alice Tailoring")
    user_bob = await user_repo.create(email="bob_pkg@example.com", full_name="Bob Tailoring")

    job = await job_repo.upsert_job(
        title="Senior Site Reliability Engineer",
        organization="Meta",
        location="Remote",
        source_name="mock",
        source_url="https://meta.com/careers/sre",
        destination_url="https://meta.com/careers/sre",
        content_hash="hash_meta_sre_01",
        description_text="Scale global infrastructure",
    )

    pkg = await package_repo.save_package(
        user_id=user_alice.id,
        job_id=job.id,
        tailored_resume={
            "document_type": "resume",
            "title": "Alice - SRE Resume",
            "content_text": "Alice's proprietary infrastructure experience",
        },
        unsupported_claim_warnings=["Missing Kubernetes verification"],
    )

    # 1. Alice can retrieve her package
    alice_pkg = await package_repo.get_package(user_id=user_alice.id, package_id=pkg.id)
    assert alice_pkg is not None
    assert alice_pkg.id == pkg.id

    alice_by_job = await package_repo.get_package_by_job(user_id=user_alice.id, job_id=job.id)
    assert alice_by_job is not None

    alice_list = await package_repo.list_packages_for_user(user_id=user_alice.id)
    assert len(alice_list) == 1

    # 2. Bob cannot retrieve Alice's package by ID or job ID
    bob_pkg = await package_repo.get_package(user_id=user_bob.id, package_id=pkg.id)
    assert bob_pkg is None, "Bob accessed Alice's package by ID!"

    bob_by_job = await package_repo.get_package_by_job(user_id=user_bob.id, job_id=job.id)
    assert bob_by_job is None, "Bob accessed Alice's package by job ID!"

    bob_list = await package_repo.list_packages_for_user(user_id=user_bob.id)
    assert len(bob_list) == 0, "Bob listed Alice's application packages!"

    # 3. Bob cannot approve or delete Alice's package
    bob_approve = await package_repo.update_approval(user_id=user_bob.id, package_id=pkg.id, is_user_approved=True)
    assert bob_approve is None, "Bob updated approval on Alice's package!"

    bob_delete = await package_repo.delete_package(user_id=user_bob.id, package_id=pkg.id)
    assert bob_delete is False, "Bob deleted Alice's package!"


@pytest.mark.asyncio
async def test_cross_account_email_draft_isolation(async_test_session: AsyncSession):
    """Verify that User A's generated email drafts are strictly isolated from User B."""
    user_repo = UserRepository(async_test_session)
    job_repo = JobRepository(async_test_session)
    email_repo = EmailDraftRepository(async_test_session)

    user_alice = await user_repo.create(email="alice_email@example.com", full_name="Alice Mail")
    user_bob = await user_repo.create(email="bob_email@example.com", full_name="Bob Mail")

    job = await job_repo.upsert_job(
        title="Principal AI Engineer",
        organization="Anthropic",
        location="San Francisco, CA",
        source_name="mock",
        source_url="https://anthropic.com/jobs/1",
        destination_url="https://anthropic.com/jobs/1",
        content_hash="hash_anthropic_ai_01",
        description_text="Lead LLM safety research and deployment",
    )

    draft = await email_repo.save_draft(
        user_id=user_alice.id,
        job_id=job.id,
        email_type="recruiter_outreach",
        subject="AI Research Inquiry - Alice",
        body="Dear Recruiter, this is confidential outreach from Alice.",
        call_to_action="Would you be open to an introductory conversation?",
        tone="professional",
    )

    # 1. Alice can view and list her email drafts
    alice_draft = await email_repo.get_draft(user_id=user_alice.id, draft_id=draft.id)
    assert alice_draft is not None
    assert alice_draft.id == draft.id

    alice_list = await email_repo.list_drafts_for_user(user_id=user_alice.id)
    assert len(alice_list) == 1

    # 2. Bob cannot view or list Alice's draft
    bob_draft = await email_repo.get_draft(user_id=user_bob.id, draft_id=draft.id)
    assert bob_draft is None, "Bob accessed Alice's private email draft!"

    bob_list = await email_repo.list_drafts_for_user(user_id=user_bob.id)
    assert len(bob_list) == 0, "Bob listed Alice's email drafts!"

    # 3. Bob cannot update or delete Alice's draft
    bob_update = await email_repo.update_draft_content(
        user_id=user_bob.id,
        draft_id=draft.id,
        subject="Hacked by Bob",
    )
    assert bob_update is None, "Bob updated Alice's draft!"

    bob_delete = await email_repo.delete_draft(user_id=user_bob.id, draft_id=draft.id)
    assert bob_delete is False, "Bob deleted Alice's draft!"




