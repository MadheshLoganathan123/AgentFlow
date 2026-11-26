import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from packages.contracts.base import EvidenceReference
from packages.contracts.email import (
    EmailDraft,
    EmailTone,
    EmailType,
)
from packages.contracts.job import JobListing
from packages.contracts.profile import (
    CandidateProfile,
    Education,
    SkillItem,
    VerificationState,
    WorkExperience,
)
from packages.db.base import Base
from packages.db.repositories.email_repo import EmailDraftRepository
from packages.db.repositories.job_repo import JobRepository
from packages.db.repositories.user_repo import UserRepository
from services.api.main import app
from services.api.services.email_writer import EmailWriterService


@pytest.fixture
def sample_candidate() -> CandidateProfile:
    return CandidateProfile(
        user_id="usr_mail_1",
        full_name="Sarah Connor",
        email="sarah.connor@cyberdyne.org",
        phone="+1-555-867-5309",
        primary_location="San Francisco, CA",
        total_years_experience=6.0,
        work_authorization="US Citizen",
        skills=[
            SkillItem(name="Python", category="technical", verification_state=VerificationState.VERIFIED_FACT),
            SkillItem(name="FastAPI", category="technical", verification_state=VerificationState.VERIFIED_FACT),
            SkillItem(name="Docker", category="technical", verification_state=VerificationState.VERIFIED_FACT),
            SkillItem(name="PostgreSQL", category="technical", verification_state=VerificationState.VERIFIED_FACT),
        ],
        experience=[
            WorkExperience(
                company="SkyNet Resistance",
                title="Staff Backend Engineer",
                location="San Francisco, CA",
                start_date="2021-01",
                end_date="Present",
                is_current=True,
                highlights=[
                    "Engineered real-time telemetry streaming in Python and FastAPI.",
                ],
                skills_used=["Python", "FastAPI"],
                evidence=EvidenceReference(
                    source_type="resume_text",
                    source_identifier="resume_page_1",
                    raw_snippet="Staff Backend Engineer at SkyNet Resistance",
                ),
            )
        ],
        education=[
            Education(
                institution="UC Berkeley",
                degree="B.S. Computer Science",
                graduation_year=2018,
            )
        ],
    )


@pytest.fixture
def sample_job() -> JobListing:
    return JobListing(
        id="job_mail_77",
        source_id="src_mock_1",
        source_name="mock",
        source_url="https://jobs.example.com/lead-backend",
        destination_url="https://jobs.example.com/lead-backend",
        title="Lead Backend Architect",
        organization="CloudScale Systems",
        location="San Francisco, CA",
        work_mode="hybrid",
        seniority="lead",
        skills_required=["Python", "FastAPI", "Kubernetes"],
        skills_preferred=["Docker", "PostgreSQL"],
        description_text="CloudScale Systems is looking for a Lead Backend Architect experienced in Python and FastAPI.",
        content_hash="hash_mail_cloudscale_77",
        is_active=True,
    )


@pytest_asyncio.fixture
async def async_test_session():
    """In-memory SQLite async database session."""
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
async def test_generate_recruiter_outreach(
    sample_candidate: CandidateProfile, sample_job: JobListing
):
    """Test recruiter outreach email generation across all 3 tone variants."""
    service = EmailWriterService()
    draft = await service.generate_draft(
        candidate=sample_candidate,
        job=sample_job,
        email_type=EmailType.RECRUITER_OUTREACH,
        recipient_name="Alice Smith",
        recipient_role="Lead Technical Recruiter",
        preferred_tone=EmailTone.PROFESSIONAL,
    )

    assert isinstance(draft, EmailDraft)
    assert draft.email_type == EmailType.RECRUITER_OUTREACH
    assert draft.recipient_name == "Alice Smith"
    assert "CloudScale Systems" in draft.subject
    assert "Lead Backend Architect" in draft.subject
    assert "Dear Alice Smith" in draft.body
    assert "SkyNet Resistance" in draft.body
    assert "Staff Backend Engineer" in draft.body
    assert "Would you have 10-15 minutes" in draft.call_to_action
    assert len(draft.structured_variants) == 3

    # Check tone variants exist
    tones = [v.tone for v in draft.structured_variants]
    assert EmailTone.PROFESSIONAL in tones
    assert EmailTone.CONVERSATIONAL in tones
    assert EmailTone.EXECUTIVE in tones


@pytest.mark.asyncio
async def test_generate_referral_request(
    sample_candidate: CandidateProfile, sample_job: JobListing
):
    """Test referral request email generation."""
    service = EmailWriterService()
    draft = await service.generate_draft(
        candidate=sample_candidate,
        job=sample_job,
        email_type=EmailType.REFERRAL_REQUEST,
        recipient_name="Bob Alum",
        preferred_tone=EmailTone.CONVERSATIONAL,
    )

    assert draft.email_type == EmailType.REFERRAL_REQUEST
    assert "referral" in draft.call_to_action.lower() or "chat" in draft.call_to_action.lower()
    assert "CloudScale Systems" in draft.body
    assert "Lead Backend Architect" in draft.body
    assert "Hey Bob Alum" in draft.body or "Hi Bob Alum" in draft.body


@pytest.mark.asyncio
async def test_generate_follow_up(
    sample_candidate: CandidateProfile, sample_job: JobListing
):
    """Test post-application follow-up email draft."""
    service = EmailWriterService()
    draft = await service.generate_draft(
        candidate=sample_candidate,
        job=sample_job,
        email_type=EmailType.FOLLOW_UP,
        recipient_name="Clara Talent",
        preferred_tone=EmailTone.EXECUTIVE,
    )

    assert draft.email_type == EmailType.FOLLOW_UP
    assert "timeline" in draft.call_to_action.lower() or "update" in draft.call_to_action.lower() or "materials" in draft.call_to_action.lower()
    assert "Lead Backend Architect" in draft.subject


@pytest.mark.asyncio
async def test_generate_thank_you_note(
    sample_candidate: CandidateProfile, sample_job: JobListing
):
    """Test post-interview thank-you note referencing discussion context."""
    service = EmailWriterService()
    draft = await service.generate_draft(
        candidate=sample_candidate,
        job=sample_job,
        email_type=EmailType.THANK_YOU,
        recipient_name="David VP Engineering",
        extra_context="the distributed telemetry pipeline migration",
        preferred_tone=EmailTone.PROFESSIONAL,
    )

    assert draft.email_type == EmailType.THANK_YOU
    assert "distributed telemetry pipeline migration" in draft.body
    assert "next steps" in draft.call_to_action.lower()
    assert "Thank you" in draft.subject


@pytest.mark.asyncio
async def test_missing_recipient_warnings(
    sample_candidate: CandidateProfile, sample_job: JobListing
):
    """Verify missing recipient name triggers clear warning and safe placeholder."""
    service = EmailWriterService()
    draft = await service.generate_draft(
        candidate=sample_candidate,
        job=sample_job,
        email_type=EmailType.RECRUITER_OUTREACH,
        recipient_name=None,  # Missing recipient name!
    )

    assert len(draft.missing_recipient_warnings) >= 1
    assert any("Recipient name is not specified" in w for w in draft.missing_recipient_warnings)
    assert "[Hiring Manager / Recruiter Name]" in draft.body


@pytest.mark.asyncio
async def test_zero_hallucination_and_fact_grounding(
    sample_candidate: CandidateProfile, sample_job: JobListing
):
    """Verify email body cites only confirmed skills and links evidence."""
    service = EmailWriterService()
    draft = await service.generate_draft(
        candidate=sample_candidate,
        job=sample_job,
        email_type=EmailType.RECRUITER_OUTREACH,
        recipient_name="Recruiter",
    )

    # Job requires "Kubernetes", which candidate does NOT have in profile
    # The email should cite Python and FastAPI, but NOT claim Kubernetes
    assert "Kubernetes" not in draft.body
    assert len(draft.personalization_evidence) >= 1


@pytest.mark.asyncio
async def test_email_draft_repository_crud(async_test_session: AsyncSession):
    """Test EmailDraftRepository save, retrieve, update, list, and delete."""
    user_repo = UserRepository(async_test_session)
    job_repo = JobRepository(async_test_session)
    email_repo = EmailDraftRepository(async_test_session)

    user = await user_repo.create(email="writer_test@example.com", full_name="Writer User")
    job = await job_repo.upsert_job(
        title="Staff Data Engineer",
        organization="Snowflake",
        location="Remote",
        source_name="mock",
        source_url="https://snowflake.com/jobs/1",
        destination_url="https://snowflake.com/jobs/1",
        content_hash="hash_snow_01",
        description_text="Scale cloud data warehouse",
    )

    # 1. Save draft
    draft = await email_repo.save_draft(
        user_id=user.id,
        job_id=job.id,
        email_type="recruiter_outreach",
        subject="Staff Data Engineer Inquiry",
        body="Dear Team, I am writing to apply...",
        call_to_action="Would you be open to an introductory call?",
        tone="professional",
    )
    assert draft.id is not None
    assert draft.is_approved_by_user is False

    # 2. Retrieve draft
    fetched = await email_repo.get_draft(user_id=user.id, draft_id=draft.id)
    assert fetched is not None
    assert fetched.subject == "Staff Data Engineer Inquiry"

    # 3. Update draft
    updated = await email_repo.update_draft_content(
        user_id=user.id,
        draft_id=draft.id,
        subject="Updated Subject Line",
        is_approved_by_user=True,
    )
    assert updated is not None
    assert updated.subject == "Updated Subject Line"
    assert updated.is_approved_by_user is True

    # 4. List drafts
    drafts = await email_repo.list_drafts_for_user(user_id=user.id)
    assert len(drafts) == 1

    # 5. Delete draft
    deleted = await email_repo.delete_draft(user_id=user.id, draft_id=draft.id)
    assert deleted is True

    rem = await email_repo.get_draft(user_id=user.id, draft_id=draft.id)
    assert rem is None


def test_email_api_endpoints(sample_candidate: CandidateProfile, sample_job: JobListing):
    """Test FastAPI REST endpoints in services/api/routers/emails.py."""
    client = TestClient(app)

    # 1. POST /api/v1/emails/generate
    gen_req = {
        "user_id": sample_candidate.user_id,
        "email_type": "recruiter_outreach",
        "recipient_name": "Jane Recruiter",
        "candidate_profile": sample_candidate.model_dump(mode="json"),
        "job_listing": sample_job.model_dump(mode="json"),
        "save_to_drafts": False,
    }
    resp = client.post("/api/v1/emails/generate", json=gen_req)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["email_type"] == "recruiter_outreach"
    assert "CloudScale Systems" in data["subject"]
    assert "Jane Recruiter" in data["body"]
    assert len(data["structured_variants"]) == 3
