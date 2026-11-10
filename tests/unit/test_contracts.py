from packages.contracts.application import ApplicationReadiness, ReadinessBlocker
from packages.contracts.base import EvidenceReference, VersionedBaseModel
from packages.contracts.job import JobListing, JobSeniority, WorkMode
from packages.contracts.profile import CandidateProfile, SkillItem, VerificationState


def test_base_contract_versioning():
    model = VersionedBaseModel(model_version="gpt-4o", prompt_version="v1.2")
    assert model.schema_version == "1.0.0"
    assert model.model_version == "gpt-4o"
    assert model.prompt_version == "v1.2"
    assert model.created_at is not None


def test_evidence_grounding_flag():
    fact_evidence = EvidenceReference(
        source_type="resume_text",
        source_identifier="experience_section",
        raw_snippet="5 years Python experience at Stripe",
        confidence_score=1.0,
        is_inferred=False
    )
    assert not fact_evidence.is_inferred
    assert fact_evidence.confidence_score == 1.0

    inferred_evidence = EvidenceReference(
        source_type="llm_inference",
        source_identifier="deduced_seniority",
        confidence_score=0.75,
        is_inferred=True
    )
    assert inferred_evidence.is_inferred


def test_candidate_profile_contract():
    profile = CandidateProfile(
        user_id="usr_123",
        full_name="Alice Developer",
        target_job_titles=["Senior Backend Engineer"],
        skills=[
            SkillItem(
                name="Python",
                verification_state=VerificationState.VERIFIED_FACT
            )
        ]
    )
    assert profile.user_id == "usr_123"
    assert profile.full_name == "Alice Developer"
    assert len(profile.skills) == 1
    assert profile.skills[0].verification_state == VerificationState.VERIFIED_FACT


def test_job_listing_contract():
    job = JobListing(
        title="Full Stack Engineer",
        organization="TechCorp",
        location="Remote",
        work_mode=WorkMode.REMOTE,
        senority=JobSeniority.SENIOR,
        description_text="Looking for a Python/Next.js engineer...",
        destination_url="https://techcorp.example/jobs/1",
        source_name="greenhouse",
        source_url="https://boards.greenhouse.io/techcorp/jobs/1",
        content_hash="a1b2c3d4e5f6g7h8"
    )
    assert job.title == "Full Stack Engineer"
    assert job.source_name == "greenhouse"
    assert job.content_hash == "a1b2c3d4e5f6g7h8"


def test_application_readiness_blockers():
    readiness = ApplicationReadiness(
        is_ready_for_submission=False,
        destination_domain="boards.greenhouse.io",
        blockers=[
            ReadinessBlocker(
                field_or_rule="work_authorization",
                message="Work authorization status is unconfirmed.",
                severity="blocker"
            )
        ],
        confirmation_summary="1 critical blocker prevents submission."
    )
    assert not readiness.is_ready_for_submission
    assert len(readiness.blockers) == 1

