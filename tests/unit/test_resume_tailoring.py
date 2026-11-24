from datetime import datetime, timezone
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from packages.contracts.application import (
    ApplicationPackage,
    DiffChangeType,
    ResumeDiffAnalysis,
    TailoredDocument,
    TailoredResume,
)
from packages.contracts.base import EvidenceReference
from packages.contracts.job import JobListing
from packages.contracts.profile import (
    CandidateProfile,
    Education,
    SkillItem,
    VerificationState,
    WorkExperience,
)
from packages.db.base import Base
from packages.db.repositories.job_repo import JobRepository
from packages.db.repositories.package_repo import ApplicationPackageRepository
from packages.db.repositories.profile_repo import ProfileRepository
from packages.db.repositories.user_repo import UserRepository
from services.api.main import app
from services.api.services.tailoring import ResumeTailoringService


@pytest.fixture
def sample_candidate() -> CandidateProfile:
    return CandidateProfile(
        user_id="usr_tailor_1",
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
            SkillItem(name="Rust", category="technical", verification_state=VerificationState.UNCONFIRMED),
            SkillItem(name="C++", category="technical", verification_state=VerificationState.VERIFIED_FACT),
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
                    "Engineered real-time telemetry streaming in Python and C++.",
                    "Scaled Docker container orchestration across 50 nodes.",
                    "Built secure REST APIs using FastAPI handling 50k req/sec.",
                ],
                skills_used=["Python", "FastAPI", "Docker", "C++"],
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
                    "Maintained automated unit testing and CI pipelines.",
                ],
                skills_used=["Python"],
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
        raw_resume_text="Sarah Connor\nStaff Backend Engineer with 6 years experience in Python, FastAPI, Docker, and C++.",
    )


@pytest.fixture
def sample_job() -> JobListing:
    return JobListing(
        id="job_tailor_99",
        source_id="src_mock_1",
        source_name="mock",
        source_url="https://jobs.example.com/fastapi-backend",
        destination_url="https://jobs.example.com/fastapi-backend",
        title="Senior FastAPI Backend Architect",
        organization="CloudScale Systems",
        location="San Francisco, CA",
        work_mode="hybrid",
        seniority="senior",
        skills_required=["FastAPI", "Python", "Kubernetes"],
        skills_preferred=["Docker", "Redis"],
        description_text="Seeking Senior FastAPI Backend Architect to build distributed microservices with FastAPI and Docker. Experience with Kubernetes is required.",
        content_hash="hash_tailor_cloudscale_01",
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
async def test_tailor_resume_grounding_and_structure(
    sample_candidate: CandidateProfile, sample_job: JobListing
):
    """Test full resume tailoring lifecycle with zero fabrication and valid contract."""
    service = ResumeTailoringService()
    tailored = await service.tailor_resume(candidate=sample_candidate, job=sample_job)

    assert isinstance(tailored, TailoredResume)
    assert tailored.job_id == sample_job.id
    assert tailored.candidate_name == sample_candidate.full_name
    assert tailored.job_title == sample_job.title
    assert tailored.organization == sample_job.organization
    assert tailored.is_grounded is True

    # Check that companies match verified profile
    companies = [exp["company"] for exp in tailored.experience_entries]
    assert companies == ["SkyNet Resistance", "Cyberdyne Systems"]

    # Check that education matches verified profile
    institutions = [edu["institution"] for edu in tailored.education_entries]
    assert institutions == ["UC Berkeley"]


@pytest.mark.asyncio
async def test_zero_hallucination_and_no_phantom_claims(
    sample_candidate: CandidateProfile, sample_job: JobListing
):
    """Verify system strictly preserves candidate facts and never invents employers or credentials."""
    service = ResumeTailoringService()
    tailored = await service.tailor_resume(candidate=sample_candidate, job=sample_job)

    # 1. No phantom companies
    known_companies = {exp.company for exp in sample_candidate.experience}
    for exp in tailored.experience_entries:
        assert exp["company"] in known_companies

    # 2. No phantom job titles
    known_titles = {exp.title for exp in sample_candidate.experience}
    for exp in tailored.experience_entries:
        assert exp["title"] in known_titles

    # 3. No phantom dates
    known_starts = {exp.start_date for exp in sample_candidate.experience}
    for exp in tailored.experience_entries:
        assert exp["start_date"] in known_starts

    # 4. Job requires "Kubernetes" which candidate does NOT have
    # Ensure Kubernetes is NOT listed in candidate's emphasized or other skills
    assert "Kubernetes" not in tailored.emphasized_skills
    assert "Kubernetes" not in tailored.other_skills

    # 5. Unsupported claim warning generated for missing Kubernetes
    has_k8s_warning = any("Kubernetes" in w for w in tailored.unsupported_claim_warnings)
    assert has_k8s_warning, "Expected unsupported claim warning for missing Kubernetes requirement"


@pytest.mark.asyncio
async def test_skill_prioritization_and_reordering(
    sample_candidate: CandidateProfile, sample_job: JobListing
):
    """Verify skills intersecting with the target role are elevated to emphasized_skills."""
    service = ResumeTailoringService()
    tailored = await service.tailor_resume(candidate=sample_candidate, job=sample_job)

    # Job requires FastAPI, Python and prefers Docker
    # Candidate has Python, FastAPI, Docker, C++, Rust
    assert "FastAPI" in tailored.emphasized_skills
    assert "Python" in tailored.emphasized_skills
    assert "Docker" in tailored.emphasized_skills

    # C++ was not required or mentioned in job description, so it should be in other_skills
    assert "C++" in tailored.other_skills


@pytest.mark.asyncio
async def test_experience_highlights_reordering(
    sample_candidate: CandidateProfile, sample_job: JobListing
):
    """Verify accomplishment bullets are re-ordered to prioritize job-matching keywords."""
    service = ResumeTailoringService()
    tailored = await service.tailor_resume(candidate=sample_candidate, job=sample_job)

    skynet_exp = next(e for e in tailored.experience_entries if e["company"] == "SkyNet Resistance")
    highlights = skynet_exp["highlights"]

    # The highlight mentioning FastAPI should be prioritized because job title has "FastAPI"
    # and job requires "FastAPI"
    assert "FastAPI" in highlights[0] or "Docker" in highlights[0]


@pytest.mark.asyncio
async def test_diff_analysis_computation(
    sample_candidate: CandidateProfile, sample_job: JobListing
):
    """Verify section-by-section diff analysis and change summary."""
    service = ResumeTailoringService()
    tailored = await service.tailor_resume(candidate=sample_candidate, job=sample_job)

    diff = tailored.diff_analysis
    assert isinstance(diff, ResumeDiffAnalysis)
    assert diff.tailored_word_count > 0
    assert len(diff.section_diffs) >= 4

    section_names = {sd.section_name for sd in diff.section_diffs}
    assert "Professional Summary" in section_names
    assert "Core Technical Skills" in section_names
    assert "Professional Experience" in section_names
    assert "Education" in section_names

    # Education must be UNCHANGED
    edu_diff = next(sd for sd in diff.section_diffs if sd.section_name == "Education")
    assert edu_diff.change_type == DiffChangeType.UNCHANGED

    # Summary must be MODIFIED or ADDED
    summary_diff = next(sd for sd in diff.section_diffs if sd.section_name == "Professional Summary")
    assert summary_diff.change_type in (DiffChangeType.MODIFIED, DiffChangeType.ADDED)
    assert "CloudScale Systems" in summary_diff.explanation or "Senior FastAPI Backend Architect" in summary_diff.explanation


@pytest.mark.asyncio
async def test_conversion_to_tailored_document_and_application_package(
    sample_candidate: CandidateProfile, sample_job: JobListing
):
    """Test converting TailoredResume into contract TailoredDocument and ApplicationPackage."""
    service = ResumeTailoringService()
    tailored = await service.tailor_resume(candidate=sample_candidate, job=sample_job)

    # 1. TailoredDocument
    doc = service.to_tailored_document(tailored)
    assert isinstance(doc, TailoredDocument)
    assert doc.document_type == "resume"
    assert "CloudScale Systems" in doc.title
    assert doc.diff_analysis is not None
    assert doc.structured_resume is not None

    # 2. ApplicationPackage
    package = service.to_application_package(user_id="usr_test_100", tailored=tailored)
    assert isinstance(package, ApplicationPackage)
    assert package.job_id == sample_job.id
    assert package.user_id == "usr_test_100"
    assert package.tailored_resume.document_type == "resume"
    assert package.is_user_approved is False


@pytest.mark.asyncio
async def test_application_package_repository(async_test_session: AsyncSession):
    """Test ApplicationPackageRepository CRUD operations with user isolation."""
    user_repo = UserRepository(async_test_session)
    job_repo = JobRepository(async_test_session)
    pkg_repo = ApplicationPackageRepository(async_test_session)

    user = await user_repo.create(email="tailor_test@example.com", full_name="Tailor Candidate")
    job = await job_repo.upsert_job(
        title="Infrastructure Lead",
        organization="DataWorks",
        location="Remote",
        source_name="mock",
        source_url="https://dataworks.com/jobs/1",
        destination_url="https://dataworks.com/jobs/1",
        content_hash="hash_dataworks_lead_01",
        description_text="Lead infrastructure engineering team",
    )

    # Save package
    pkg = await pkg_repo.save_package(
        user_id=user.id,
        job_id=job.id,
        tailored_resume={
            "document_type": "resume",
            "title": "Tailor Candidate - DataWorks",
            "content_text": "Experienced infrastructure engineer...",
        },
        unsupported_claim_warnings=["Missing Terraform verification"],
    )
    assert pkg.id is not None
    assert pkg.is_user_approved is False

    # Retrieve package
    retrieved = await pkg_repo.get_package(user_id=user.id, package_id=pkg.id)
    assert retrieved is not None
    assert retrieved.job_id == job.id

    # Retrieve by job
    by_job = await pkg_repo.get_package_by_job(user_id=user.id, job_id=job.id)
    assert by_job is not None
    assert by_job.id == pkg.id

    # Update approval
    approved = await pkg_repo.update_approval(user_id=user.id, package_id=pkg.id, is_user_approved=True)
    assert approved is not None
    assert approved.is_user_approved is True
    assert approved.approved_at is not None

    # Idempotent re-save
    pkg2 = await pkg_repo.save_package(
        user_id=user.id,
        job_id=job.id,
        tailored_resume={
            "document_type": "resume",
            "title": "Tailor Candidate - DataWorks v2",
            "content_text": "Updated infrastructure resume content...",
        },
    )
    assert pkg2.id == pkg.id
    assert pkg2.tailored_resume["title"] == "Tailor Candidate - DataWorks v2"


def test_documents_api_endpoints(sample_candidate: CandidateProfile, sample_job: JobListing):
    """Test FastAPI REST endpoints in services/api/routers/documents.py."""
    client = TestClient(app)

    # 1. POST /api/v1/documents/tailor-resume with direct payload
    req_body = {
        "user_id": "usr_direct_api",
        "candidate_profile": sample_candidate.model_dump(mode="json"),
        "job_listing": sample_job.model_dump(mode="json"),
        "save_to_package": False,
    }
    resp = client.post("/api/v1/documents/tailor-resume", json=req_body)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "tailored_resume" in data
    assert data["tailored_resume"]["job_title"] == sample_job.title
    assert data["tailored_resume"]["is_grounded"] is True
    assert "diff_analysis" in data["tailored_resume"]

    # 2. POST /api/v1/documents/compare-resume
    comp_body = {
        "candidate_profile": sample_candidate.model_dump(mode="json"),
        "job_listing": sample_job.model_dump(mode="json"),
    }
    comp_resp = client.post("/api/v1/documents/compare-resume", json=comp_body)
    assert comp_resp.status_code == 200
    comp_data = comp_resp.json()
    assert "section_diffs" in comp_data
    assert len(comp_data["section_diffs"]) >= 4
    assert comp_data["tailored_word_count"] > 0
