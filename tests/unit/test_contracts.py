from datetime import timezone

import pytest
from pydantic import ValidationError

from packages.contracts.agent import (
    AgentRole,
    AgentRunRecord,
    AgentRunStatus,
    TokenUsage,
    ToolCallRecord,
)
from packages.contracts.application import (
    ApplicationPackage,
    ApplicationReadiness,
    ApplicationResult,
    ApplicationStatus,
    ReadinessBlocker,
    TailoredDocument,
)
from packages.contracts.base import EvidenceReference, VersionedBaseModel
from packages.contracts.email import EmailDraft, EmailType
from packages.contracts.interview import (
    InterviewPlan,
    InterviewQuestion,
    PracticeFeedback,
    QuestionSet,
    ResearchSource,
    SourceCitation,
)
from packages.contracts.job import JobListing, JobSeniority, WorkMode
from packages.contracts.match import MatchExplanation, RequirementMatch, ScoreBreakdown
from packages.contracts.policy import (
    PolicyCheckType,
    PolicyReviewResult,
    PolicySeverity,
    PolicyViolation,
    PrivacyRedaction,
)
from packages.contracts.profile import (
    CandidateProfile,
    Education,
    MissingFieldNotice,
    SkillItem,
    VerificationState,
    WorkExperience,
    WorkModePreference,
)


def test_base_contract_versioning():
    """Ensure all models inherit versioning, open-source model provenance, and UTC timestamps."""
    model = VersionedBaseModel(model_version="llama3.2:1b", prompt_version="v1.2.0")
    assert model.schema_version == "1.0.0"
    assert model.model_version == "llama3.2:1b"
    assert model.prompt_version == "v1.2.0"
    assert model.created_at is not None
    assert model.created_at.tzinfo == timezone.utc


def test_evidence_grounding_flag():
    """Ensure the system distinguishes verified resume facts from inferred or unconfirmed facts."""
    fact_evidence = EvidenceReference(
        source_type="resume_text",
        source_identifier="experience_section",
        raw_snippet="5 years Python experience at Stripe",
        confidence_score=1.0,
        is_inferred=False,
        is_user_confirmed=True,
    )
    assert not fact_evidence.is_inferred
    assert fact_evidence.is_user_confirmed
    assert fact_evidence.confidence_score == 1.0

    inferred_evidence = EvidenceReference(
        source_type="llm_inference",
        source_identifier="deduced_seniority",
        confidence_score=0.75,
        is_inferred=True,
        is_user_confirmed=False,
    )
    assert inferred_evidence.is_inferred
    assert not inferred_evidence.is_user_confirmed


def test_candidate_profile_contract():
    """Test 1. Profile Analyst contract output: structured profile with evidence & missing fields."""
    profile = CandidateProfile(
        user_id="usr_123",
        full_name="Alice Developer",
        email="alice@example.com",
        primary_location="San Francisco, CA",
        work_modes=[WorkModePreference.REMOTE, WorkModePreference.HYBRID],
        target_job_titles=["Staff Platform Engineer"],
        skills=[
            SkillItem(
                name="Python",
                category="programming",
                years_experience=6.0,
                verification_state=VerificationState.VERIFIED_FACT,
                evidence=EvidenceReference(
                    source_type="resume_text",
                    source_identifier="skills",
                    raw_snippet="Python (6 yrs)",
                ),
            )
        ],
        experience=[
            WorkExperience(
                company="OpenTech",
                title="Lead Backend Engineer",
                is_current=True,
                highlights=["Architected high-throughput message bus"],
            )
        ],
        education=[
            Education(
                institution="UC Berkeley",
                degree="B.S. Computer Science",
                graduation_year=2018,
            )
        ],
        missing_fields=[
            MissingFieldNotice(
                field_name="work_authorization",
                description="Work authorization status is required for accurate matching.",
                is_critical_for_matching=True,
                suggested_question="Are you authorized to work in the United States?",
            )
        ],
        inferred_fields=["seniority: staff"],
    )

    assert profile.user_id == "usr_123"
    assert profile.full_name == "Alice Developer"
    assert len(profile.skills) == 1
    assert profile.skills[0].verification_state == VerificationState.VERIFIED_FACT
    assert len(profile.missing_fields) == 1
    assert profile.missing_fields[0].is_critical_for_matching is True
    assert not profile.is_profile_confirmed


def test_job_listing_contract():
    """Test 2. Job Discovery Agent contract output: normalized fields with tamper-evident hash."""
    job = JobListing(
        title="Senior Distributed Systems Engineer",
        organization="CloudScale Corp",
        location="Remote - US",
        work_mode=WorkMode.REMOTE,
        seniority=JobSeniority.SENIOR,
        salary_min=180000,
        salary_max=220000,
        salary_currency="USD",
        skills_required=["Python", "PostgreSQL", "FastAPI"],
        description_text="Building resilient cloud systems with Python and LangGraph...",
        destination_url="https://cloudscale.example/jobs/42",
        source_name="greenhouse",
        source_url="https://boards.greenhouse.io/cloudscale/42",
        content_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    assert job.title == "Senior Distributed Systems Engineer"
    assert job.work_mode == WorkMode.REMOTE
    assert job.seniority == JobSeniority.SENIOR
    assert job.salary_min == 180000
    assert len(job.skills_required) == 3
    assert job.content_hash is not None


def test_match_and_ranking_contract():
    """Test 3. Match and Ranking Agent contract output: explainable multidimensional score."""
    match = MatchExplanation(
        candidate_id="cand_101",
        job_id="job_202",
        composite_score=87.5,
        score_breakdown=ScoreBreakdown(
            skill_match_score=92.0,
            seniority_score=90.0,
            location_mode_score=100.0,
            salary_alignment_score=85.0,
            work_authorization_score=100.0,
            recency_score=75.0,
            composite_score=87.5,
        ),
        strengths=["Strong overlap in Python and distributed systems", "Location matches remote preference"],
        gaps=["No prior Go experience mentioned in verified facts"],
        uncertainties=["Job post does not specify exact equity package"],
        matched_requirements=[
            RequirementMatch(
                requirement="5+ years Python experience",
                is_satisfied=True,
                evidence_or_gap_explanation="Candidate verified 6 years of Python experience",
                candidate_skill_or_exp="Python",
            ),
            RequirementMatch(
                requirement="Experience with Kubernetes",
                is_satisfied=False,
                evidence_or_gap_explanation="Not listed in candidate verified profile",
            ),
        ],
        recommendation="strong_match",
    )

    assert match.composite_score == 87.5
    assert match.score_breakdown.skill_match_score == 92.0
    assert len(match.strengths) == 2
    assert len(match.gaps) == 1
    assert match.matched_requirements[0].is_satisfied is True
    assert match.matched_requirements[1].is_satisfied is False
    assert match.recommendation == "strong_match"


def test_resume_and_document_contract():
    """Test 4. Resume and Document Agent contract output: tailored materials grounded in facts."""
    package = ApplicationPackage(
        job_id="job_202",
        user_id="usr_123",
        tailored_resume=TailoredDocument(
            document_type="resume",
            title="Alice Developer - Tailored for CloudScale",
            content_text="Experienced engineer focusing on high-throughput backend systems...",
            changed_sections=["Professional Summary", "Highlighted Python Projects"],
            evidence_links=[
                EvidenceReference(
                    source_type="resume_text",
                    source_identifier="original_resume",
                    raw_snippet="Lead Backend Engineer at OpenTech",
                    confidence_score=1.0,
                )
            ],
            unsupported_claim_warnings=[],
        ),
        cover_letter=TailoredDocument(
            document_type="cover_letter",
            title="Cover Letter - CloudScale",
            content_text="Dear Hiring Team, I am writing to express my interest...",
        ),
        form_answers={
            "years_of_experience": "6",
            "primary_language": "Python",
        },
        unsupported_claim_warnings=[],
        is_user_approved=False,
    )

    assert package.job_id == "job_202"
    assert len(package.tailored_resume.changed_sections) == 2
    assert not package.is_user_approved
    assert package.cover_letter is not None


def test_application_readiness_contract():
    """Test 5. Application Readiness Agent contract output: blocks submission when blockers exist."""
    readiness = ApplicationReadiness(
        is_ready_for_submission=False,
        destination_domain="boards.greenhouse.io",
        blockers=[
            ReadinessBlocker(
                field_or_rule="work_authorization",
                message="Work authorization status is unconfirmed.",
                severity="blocker",
            )
        ],
        warnings=["Salary expectation exceeds posted band"],
        confirmation_summary="1 critical blocker prevents submission.",
        required_user_actions=["Confirm work authorization in profile"],
    )

    assert not readiness.is_ready_for_submission
    assert len(readiness.blockers) == 1
    assert readiness.blockers[0].severity == "blocker"
    assert readiness.destination_domain == "boards.greenhouse.io"


def test_application_agent_result_and_safety():
    """Test 6. Application Agent contract output: idempotency key and safe handoff fallback."""
    result = ApplicationResult(
        application_id="app_555",
        status=ApplicationStatus.HANDOFF_REQUIRED,
        destination="https://jobs.apple.com/en-us/details/12345",
        idempotency_key="usr_123:job_apple_12345:pkg_999",
        handoff_url="https://jobs.apple.com/en-us/details/12345",
        handoff_instructions="This job requires custom SSO credentials. AgentFlow prepared your resume and cover letter for manual paste.",
        failure_reason="Site requires CAPTCHA or authenticated internal portal",
    )

    assert result.status == ApplicationStatus.HANDOFF_REQUIRED
    assert result.idempotency_key == "usr_123:job_apple_12345:pkg_999"
    assert result.handoff_url is not None


def test_email_writer_contract():
    """Test 7. Email Writer contract output: role-specific email with tone and personalization."""
    draft = EmailDraft(
        email_type=EmailType.RECRUITER_OUTREACH,
        recipient_name="Sam Recruiter",
        recipient_role="Technical Talent Partner at CloudScale",
        subject="Senior Distributed Systems Engineer - Alice Developer",
        body="Hi Sam, I noticed the Senior Distributed Systems Engineer role at CloudScale...",
        call_to_action="Would you be open to a 10-minute introductory conversation this week?",
        tone="professional",
        recipient_assumptions=["Recipient handles engineering hiring at CloudScale"],
        personalization_evidence=[
            EvidenceReference(
                source_type="job_description",
                source_identifier="requirements",
                raw_snippet="Looking for distributed systems background",
            )
        ],
        variants=["Alternative shorter 3-sentence note"],
        is_approved_by_user=False,
    )

    assert draft.email_type == EmailType.RECRUITER_OUTREACH
    assert draft.tone == "professional"
    assert not draft.is_approved_by_user
    assert len(draft.variants) == 1


def test_research_and_interview_coach_contract():
    """Test 8. Research & Interview Coach contract output: citations, questions, and rubric scoring."""
    plan = InterviewPlan(
        role_title="Senior Platform Engineer",
        company_name="CloudScale Corp",
        seniority="Senior",
        company_research_summary="CloudScale provides managed distributed data stores.",
        citations=[
            SourceCitation(
                title="CloudScale Engineering Architecture Blog",
                url="https://cloudscale.example/blog/arch",
                source_name="Company Blog",
                excerpt="Our services rely on raft consensus for state management.",
                is_company_specific=True,
            )
        ],
        sources=[
            ResearchSource(
                source_url="https://cloudscale.example/blog/arch",
                source_title="CloudScale Engineering Architecture",
                source_domain="cloudscale.example",
                content_excerpt="Our services rely on raft consensus...",
                is_reputable=True,
            )
        ],
        question_sets=[
            QuestionSet(
                role_title="Senior Platform Engineer",
                seniority="Senior",
                estimated_time_minutes=30,
                questions=[
                    InterviewQuestion(
                        id="q_01",
                        category="system_design",
                        question="Design an idempotent distributed job scheduler.",
                        recommended_framing="technical_breakdown",
                        rubric_points=["Addresses dead-letter queues", "Handles split-brain scenarios"],
                    )
                ],
            )
        ],
        questions=[
            InterviewQuestion(
                id="q_01",
                category="system_design",
                question="Design an idempotent distributed job scheduler.",
            )
        ],
        feedback_history=[
            PracticeFeedback(
                question_id="q_01",
                answer_text="I would use Redis with leasing and postgres for persistence.",
                strengths=["Good separation of locking from durable store"],
                gaps=["Did not mention heartbeat recovery timeouts"],
                rubric_score=82.0,
                coaching_tips=["Remember to detail failure modes in distributed locks"],
            )
        ],
    )

    assert plan.role_title == "Senior Platform Engineer"
    assert len(plan.citations) == 1
    assert plan.citations[0].is_company_specific is True
    assert len(plan.sources) == 1
    assert len(plan.question_sets) == 1
    assert plan.feedback_history[0].rubric_score == 82.0


def test_policy_and_quality_reviewer_contract():
    """Test 9. Policy & Quality Reviewer contract output: privacy scrub, unverified claims, approval gate."""
    review = PolicyReviewResult(
        is_safe_to_proceed=False,
        overall_quality_score=72.0,
        violations=[
            PolicyViolation(
                check_type=PolicyCheckType.UNSUPPORTED_CLAIM,
                severity=PolicySeverity.BLOCKER,
                message="Resume claims Kubernetes certification not found in verified evidence.",
                offending_field_or_text="Certified Kubernetes Administrator (CKA)",
                remediation_hint="Upload certification proof or remove claim before continuing.",
            ),
            PolicyViolation(
                check_type=PolicyCheckType.PRIVACY,
                severity=PolicySeverity.WARNING,
                message="Social security number detected in resume text; redacted automatically.",
                offending_field_or_text="SSN: XXX-XX-XXXX",
            ),
        ],
        requires_human_approval=True,
        approval_gate_reason="Contains unverified certification claim requiring candidate confirmation.",
        redactions=[
            PrivacyRedaction(
                field_name="raw_resume_text",
                redaction_type="ssn",
                redacted_preview="[REDACTED_SSN]",
            )
        ],
    )

    assert not review.is_safe_to_proceed
    assert review.overall_quality_score == 72.0
    assert len(review.violations) == 2
    assert review.requires_human_approval is True
    assert len(review.redactions) == 1


def test_agent_execution_metadata_and_run_record():
    """Test Agent execution record with open source model provenance, tool telemetry, and latency."""
    record = AgentRunRecord(
        agent_role=AgentRole.PROFILE_ANALYST,
        workflow_id="wf_profile_001",
        user_id="usr_123",
        status=AgentRunStatus.SUCCESS,
        model_name="llama3.2:1b",
        prompt_version="v1.0.0",
        inputs_payload={"resume_bytes_len": 4096},
        outputs_payload={"parsed_skills_count": 8},
        tool_calls=[
            ToolCallRecord(
                tool_name="pdf_text_extractor",
                arguments={"file_format": "pdf"},
                output_summary="Extracted 420 words across 1 page",
                execution_time_ms=45.2,
                is_success=True,
            )
        ],
        token_usage=TokenUsage(prompt_tokens=450, completion_tokens=180, total_tokens=630),
        latency_ms=850.5,
        user_approval_state="approved",
    )

    assert record.agent_role == AgentRole.PROFILE_ANALYST
    assert record.model_name == "llama3.2:1b"
    assert record.status == AgentRunStatus.SUCCESS
    assert len(record.tool_calls) == 1
    assert record.tool_calls[0].is_success is True
    assert record.token_usage.total_tokens == 630
    assert record.user_approval_state == "approved"


def test_score_breakdown_bounds_validation():
    """Ensure score components enforce numeric bounds [0.0, 100.0]."""
    with pytest.raises(ValidationError):
        ScoreBreakdown(
            skill_match_score=150.0,  # Invalid: > 100
            seniority_score=80.0,
            location_mode_score=90.0,
            work_authorization_score=100.0,
            recency_score=80.0,
            composite_score=100.0,
        )
