import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from packages.db.base import Base
from packages.db.repositories import (
    CheckpointRepository,
    ProfileRepository,
    UserRepository,
)


@pytest_asyncio.fixture
async def async_test_session():
    """Create an isolated in-memory SQLite database session."""
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

