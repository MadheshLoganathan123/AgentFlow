import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from packages.contracts.application import (
    ApplicationPackage,
    ApplicationQuestionSet,
    CoverLetter,
    TailoredDocument,
)
from packages.contracts.base import EvidenceReference
from packages.contracts.job import JobListing
from packages.contracts.policy import PolicyCheckType, PolicySeverity
from packages.contracts.profile import (
    CandidateProfile,
    Education,
    SkillItem,
    VerificationState,
    WorkExperience,
)
from packages.db.base import Base
from services.api.main import app
from services.api.services.cover_letter_service import CoverLetterAndQuestionService
from services.api.services.policy_reviewer import PolicyReviewerService


@pytest.fixture
def sample_candidate() -> CandidateProfile:
    return CandidateProfile(
        user_id="usr_cl_1",
        full_name="Sarah Connor",
        email="sarah.connor@cyberdyne.org",
        phone="+1-555-867-5309",
        primary_location="San Francisco, CA",
        total_years_experience=6.0,
        work_authorization="US Citizen",
        notice_period_days=14,
        target_salary_min=160000,
        target_salary_max=190000,
        skills=[
            SkillItem(name="Python", category="technical", years_experience=6.0, verification_state=VerificationState.VERIFIED_FACT),
            SkillItem(name="FastAPI", category="technical", years_experience=4.0, verification_state=VerificationState.VERIFIED_FACT),
            SkillItem(name="Docker", category="technical", years_experience=5.0, verification_state=VerificationState.VERIFIED_FACT),
            SkillItem(name="PostgreSQL", category="technical", years_experience=4.0, verification_state=VerificationState.VERIFIED_FACT),
            SkillItem(name="Rust", category="technical", verification_state=VerificationState.UNCONFIRMED),
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
                    "Scaled Docker container orchestration across 50 nodes.",
                ],
                skills_used=["Python", "FastAPI", "Docker"],
                evidence=EvidenceReference(
                    source_type="resume_text",
                    source_identifier="resume_page_1",
                    raw_snippet="Staff Backend Engineer at SkyNet Resistance (2021 - Present)",
                ),
            ),
            WorkExperience(
                company="Cyberdyne Systems",
                title="Software Engineer",
                location="Sunnyvale, CA",
                start_date="2018-06",
                end_date="2020-12",
                is_current=False,
                highlights=[
                    "Developed neural network pipeline microservices in Python.",
                ],
                skills_used=["Python", "PostgreSQL"],
                evidence=EvidenceReference(
                    source_type="resume_text",
                    source_identifier="resume_page_2",
                    raw_snippet="Software Engineer at Cyberdyne Systems (2018 - 2020)",
                ),
            ),
        ],
        education=[
            Education(
                institution="UC Berkeley",
                degree="B.S. Computer Science",
                field_of_study="Computer Science",
                graduation_year=2018,
                evidence=EvidenceReference(
                    source_type="resume_text",
                    source_identifier="resume_page_2",
                    raw_snippet="B.S. Computer Science, UC Berkeley, 2018",
                ),
            )
        ],
        raw_resume_text="Sarah Connor\nStaff Backend Engineer with 6 years experience in Python, FastAPI, Docker, and PostgreSQL.",
    )


@pytest.fixture
def sample_job() -> JobListing:
    return JobListing(
        id="job_cl_88",
        source_id="src_mock_1",
        source_name="mock",
        source_url="https://jobs.example.com/backend-eng",
        destination_url="https://jobs.example.com/backend-eng",
        title="Senior Backend Engineer",
        organization="CloudScale Systems",
        location="San Francisco, CA",
        work_mode="hybrid",
        seniority="senior",
        skills_required=["Python", "FastAPI", "Kubernetes"],
        skills_preferred=["Docker", "PostgreSQL"],
        description_text="CloudScale Systems is looking for a Senior Backend Engineer to scale our distributed cloud platform.",
        content_hash="hash_cl_cloudscale_88",
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
async def test_generate_cover_letter_grounding_and_structure(
    sample_candidate: CandidateProfile, sample_job: JobListing
):
    """Test full cover letter generation lifecycle with structured paragraphs and evidence links."""
    service = CoverLetterAndQuestionService()
    cover_letter = await service.generate_cover_letter(candidate=sample_candidate, job=sample_job)

    assert isinstance(cover_letter, CoverLetter)
    assert cover_letter.job_id == sample_job.id
    assert cover_letter.job_title == sample_job.title
    assert cover_letter.organization == sample_job.organization
    assert cover_letter.candidate_name == sample_candidate.full_name
    assert cover_letter.is_grounded is True
    assert cover_letter.quality_score >= 80.0

    # Verify structured paragraphs
    paragraph_types = [p.paragraph_type for p in cover_letter.paragraphs]
    assert "opening" in paragraph_types
    assert "core_competency" in paragraph_types
    assert "closing" in paragraph_types

    # Full text checks
    assert "CloudScale Systems" in cover_letter.full_text
    assert "Senior Backend Engineer" in cover_letter.full_text
    assert "Sarah Connor" in cover_letter.full_text
    assert "SkyNet Resistance" in cover_letter.full_text

    # Evidence links present
    assert len(cover_letter.evidence_links) >= 1


@pytest.mark.asyncio
async def test_cover_letter_zero_hallucination_and_no_phantom_claims(
    sample_candidate: CandidateProfile, sample_job: JobListing
):
    """Verify cover letter never fabricates employers, degrees, or unevidenced skills."""
    service = CoverLetterAndQuestionService()
    cover_letter = await service.generate_cover_letter(candidate=sample_candidate, job=sample_job)

    # Job requires "Kubernetes", candidate lacks it
    # System should omit Kubernetes claim from letter and warn user
    assert "Kubernetes" not in cover_letter.full_text
    has_k8s_warning = any("Kubernetes" in w for w in cover_letter.unsupported_claim_warnings)
    assert has_k8s_warning, "Expected unsupported claim warning for unconfirmed Kubernetes skill"


@pytest.mark.asyncio
async def test_draft_application_answers_standard_questions(
    sample_candidate: CandidateProfile, sample_job: JobListing
):
    """Test drafting answers for standard application questions using verified candidate facts."""
    service = CoverLetterAndQuestionService()
    q_set = await service.draft_application_answers(candidate=sample_candidate, job=sample_job)

    assert isinstance(q_set, ApplicationQuestionSet)
    assert q_set.total_questions >= 5

    # Check work authorization answer
    auth_ans = next((a for a in q_set.answers if "authorization" in a.question.lower()), None)
    assert auth_ans is not None
    assert auth_ans.requires_user_input is False
    assert "US Citizen" in auth_ans.answer

    # Check notice period answer
    notice_ans = next((a for a in q_set.answers if "notice period" in a.question.lower()), None)
    assert notice_ans is not None
    assert notice_ans.requires_user_input is False
    assert "14 days" in notice_ans.answer

    # Check salary answer
    salary_ans = next((a for a in q_set.answers if "salary" in a.question.lower()), None)
    assert salary_ans is not None
    assert salary_ans.requires_user_input is False
    assert "160,000" in salary_ans.answer


@pytest.mark.asyncio
async def test_draft_application_answers_missing_evidence_flags(
    sample_candidate: CandidateProfile, sample_job: JobListing
):
    """Verify questions asking for unconfirmed skills or details are flagged for user input rather than hallucinated."""
    service = CoverLetterAndQuestionService()
    custom_questions = [
        "Describe your experience with Kubernetes.",
        "What is your security clearance level?",
    ]
    q_set = await service.draft_application_answers(
        candidate=sample_candidate,
        job=sample_job,
        custom_questions=custom_questions,
    )

    # Kubernetes question: candidate does not have it!
    k8s_ans = q_set.answers[0]
    assert k8s_ans.requires_user_input is True
    assert k8s_ans.missing_evidence_reason is not None
    assert "[Candidate Input Required" in k8s_ans.answer
    assert len(k8s_ans.unsupported_claim_warnings) >= 1

    # Security clearance: candidate does not have it!
    clearance_ans = q_set.answers[1]
    assert clearance_ans.requires_user_input is True
    assert "[Candidate Input Required" in clearance_ans.answer


def test_policy_reviewer_detects_unsupported_claims(sample_candidate: CandidateProfile, sample_job: JobListing):
    """Test PolicyReviewerService flags ungrounded degrees and exaggerated durations."""
    reviewer = PolicyReviewerService()

    # 1. Hallucinated Ph.D. claim
    fake_text = "I completed my Ph.D. in Artificial Intelligence at MIT and led deep learning research."
    res = reviewer._evaluate_content(
        full_text=fake_text,
        candidate=sample_candidate,
        job=sample_job,
        context="test_evaluation",
    )
    assert res.is_safe_to_proceed is False
    assert any(v.severity == PolicySeverity.BLOCKER for v in res.violations)
    assert any("Ph.D" in v.message for v in res.violations)

    # 2. Exaggerated years (15 years claimed vs 6 confirmed)
    exag_text = "With over 18 years of software engineering experience leading cloud platforms..."
    res_exag = reviewer._evaluate_content(
        full_text=exag_text,
        candidate=sample_candidate,
        job=sample_job,
        context="test_exaggeration",
    )
    assert any("exceeds confirmed profile duration" in v.message for v in res_exag.violations)


def test_policy_reviewer_detects_privacy_leaks(sample_candidate: CandidateProfile, sample_job: JobListing):
    """Test PolicyReviewerService flags and redacts sensitive PII or token patterns."""
    reviewer = PolicyReviewerService()

    text_with_pii = (
        "My SSN is 000-12-3456 and my Hugging Face token is hf_abcdef1234567890abcdef1234567890."
    )
    res = reviewer._evaluate_content(
        full_text=text_with_pii,
        candidate=sample_candidate,
        job=sample_job,
        context="test_privacy",
    )
    assert len(res.redactions) >= 2
    redaction_types = {r.redaction_type for r in res.redactions}
    assert "ssn" in redaction_types
    assert "token" in redaction_types


def test_policy_reviewer_detects_suspicious_job_listing(sample_candidate: CandidateProfile):
    """Test PolicyReviewerService detects scam indicators in job postings."""
    reviewer = PolicyReviewerService()

    suspicious_job = JobListing(
        id="job_scam_01",
        source_id="src_mock_1",
        source_name="mock",
        source_url="https://scam.example.com",
        destination_url="https://scam.example.com",
        title="Work from Home Data Entry",
        organization="Apex Global",
        location="Remote",
        work_mode="remote",
        seniority="entry",
        skills_required=["Typing"],
        description_text="Must pay $150 equipment fee via wire transfer before interview.",
        content_hash="hash_scam_01",
        is_active=True,
    )

    package = ApplicationPackage(
        id="pkg_test_scam",
        user_id=sample_candidate.user_id,
        job_id=suspicious_job.id,
        tailored_resume=TailoredDocument(
            document_type="resume",
            title="Resume",
            content_text="Regular resume text",
        ),
    )

    res = reviewer.review_full_package(package=package, candidate=sample_candidate, job=suspicious_job)
    assert res.is_safe_to_proceed is False
    assert any(v.check_type == PolicyCheckType.SUSPICIOUS_LISTING for v in res.violations)


@pytest.mark.asyncio
async def test_cover_letter_and_answers_api_endpoints(
    sample_candidate: CandidateProfile, sample_job: JobListing
):
    """Test FastAPI REST endpoints for generating cover letter and drafting answers."""
    client = TestClient(app)

    # 1. POST /api/v1/documents/generate-cover-letter
    cl_req = {
        "user_id": sample_candidate.user_id,
        "candidate_profile": sample_candidate.model_dump(mode="json"),
        "job_listing": sample_job.model_dump(mode="json"),
    }
    cl_resp = client.post("/api/v1/documents/generate-cover-letter", json=cl_req)
    assert cl_resp.status_code == 200, cl_resp.text
    cl_data = cl_resp.json()
    assert cl_data["job_title"] == sample_job.title
    assert cl_data["is_grounded"] is True
    assert len(cl_data["paragraphs"]) >= 3

    # 2. POST /api/v1/documents/draft-answers
    ans_req = {
        "user_id": sample_candidate.user_id,
        "candidate_profile": sample_candidate.model_dump(mode="json"),
        "job_listing": sample_job.model_dump(mode="json"),
        "custom_questions": ["What is your work authorization?", "Do you know Kubernetes?"],
    }
    ans_resp = client.post("/api/v1/documents/draft-answers", json=ans_req)
    assert ans_resp.status_code == 200, ans_resp.text
    ans_data = ans_resp.json()
    assert ans_data["total_questions"] == 2
    assert ans_data["requires_user_input_count"] >= 1  # Kubernetes requires user input!
