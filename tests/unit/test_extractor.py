import io
import zipfile

import pytest

from packages.contracts.profile import VerificationState
from services.api.services.extractor import ResumeExtractorService

SAMPLE_RESUME_TEXT = """
Jane Doe
Email: jane.doe@example.com
Phone: (555) 123-4567
Location: San Francisco, CA

Professional Summary:
Passionate Software Engineer at CloudCorp with 6 years of experience building scalable systems.
Preference: Remote or Hybrid work modes.

Experience:
Senior Software Engineer at CloudCorp - 2021 to Present
- Architected distributed microservices in Python and FastAPI.
- Built interactive dashboards using Next.js, React, and TypeScript.
- Managed PostgreSQL database instances with pgvector for semantic search.

Backend Engineer at StartupHub - 2018 to 2021
- Developed REST APIs and background workers with Docker and Git.

Education:
Bachelor of Science in Computer Science from Stanford University - 2018
"""

RESUME_WITH_WORK_AUTH = """
John Smith
Email: john.smith@example.com
Phone: (555) 987-6543
Work Authorization: US Citizen

Experience:
Lead DevOps Engineer at OpenCorp
- Kubernetes, Docker, AWS, and Python automation.
"""


def test_resume_text_extraction_and_parsing():
    """Verify that facts from raw resume text are extracted and grounded with evidence."""
    profile = ResumeExtractorService.parse_profile(SAMPLE_RESUME_TEXT, user_id="test_user_001")

    assert profile.full_name == "Jane Doe"
    assert profile.email == "jane.doe@example.com"
    assert profile.phone == "(555) 123-4567"
    assert "San Francisco" in profile.primary_location
    assert profile.total_years_experience == 6.0

    # Verify skills extraction
    skill_names = [s.name for s in profile.skills]
    assert "Python" in skill_names
    assert "FastAPI" in skill_names
    assert "React" in skill_names
    assert "PostgreSQL" in skill_names
    assert "Docker" in skill_names

    # Check evidence grounding
    for skill in profile.skills:
        assert skill.verification_state == VerificationState.VERIFIED_FACT
        assert skill.evidence is not None
        assert skill.evidence.raw_snippet is not None
        assert not skill.evidence.is_inferred

    # Check work experience extraction
    assert len(profile.experience) >= 2
    assert any(exp.company == "CloudCorp" for exp in profile.experience)
    assert any(exp.title == "Senior Software Engineer" for exp in profile.experience)

    # Check education extraction
    assert len(profile.education) >= 1
    assert "Stanford University" in profile.education[0].institution

    # Check missing critical fields separation
    missing_field_names = [m.field_name for m in profile.missing_fields]
    assert "work_authorization" in missing_field_names
    assert not profile.is_profile_confirmed


def test_extract_text_from_txt():
    """Verify plain text decoding across UTF-8 encodings."""
    content = "Hello World! Software Engineer with Python skills."
    txt_bytes = content.encode("utf-8")
    extracted = ResumeExtractorService.extract_text_from_txt(txt_bytes)
    assert extracted == content


def test_extract_text_from_docx():
    """Verify DOCX text extraction using synthetic in-memory ZIP package without external libraries."""
    docx_buffer = io.BytesIO()
    xml_content = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
        <w:body>
            <w:p><w:r><w:t>Alex Morgan</w:t></w:r></w:p>
            <w:p><w:r><w:t>Email: alex@example.com</w:t></w:r></w:p>
            <w:p><w:r><w:t>Senior Backend Developer at FinTechInc</w:t></w:r></w:p>
            <w:p><w:r><w:t>Skills: Python, Go, Docker, PostgreSQL</w:t></w:r></w:p>
        </w:body>
    </w:document>
    """.strip()

    with zipfile.ZipFile(docx_buffer, "w") as zf:
        zf.writestr("word/document.xml", xml_content)

    docx_bytes = docx_buffer.getvalue()
    extracted = ResumeExtractorService.extract_text_from_docx(docx_bytes)

    assert "Alex Morgan" in extracted
    assert "alex@example.com" in extracted
    assert "Python, Go, Docker, PostgreSQL" in extracted


def test_extract_text_from_file_dispatch():
    """Test unified dispatcher based on file extensions."""
    txt_data = b"Plain text resume data"
    assert ResumeExtractorService.extract_text_from_file(txt_data, "resume.txt") == "Plain text resume data"
    assert ResumeExtractorService.extract_text_from_file(txt_data, "resume.md") == "Plain text resume data"


def test_explicit_work_authorization_detection():
    """Verify that when work authorization is stated, it is recorded and not in missing fields."""
    profile = ResumeExtractorService.parse_profile(RESUME_WITH_WORK_AUTH, user_id="user_auth_01")

    assert profile.work_authorization == "US Citizen"
    missing_fields = [m.field_name for m in profile.missing_fields]
    assert "work_authorization" not in missing_fields


def test_evidence_grounding_integrity():
    """Ensure the system distinguishes verified facts from model inferences and never invents claims."""
    profile = ResumeExtractorService.parse_profile(SAMPLE_RESUME_TEXT, user_id="user_eval_01")

    # Every verified skill must have a valid raw_snippet from the resume
    for skill in profile.skills:
        assert skill.evidence.raw_snippet.lower() in SAMPLE_RESUME_TEXT.lower()
        assert not skill.evidence.is_inferred

    # If seniority or experience years were estimated, it must be recorded in inferred_fields
    assert len(profile.inferred_fields) > 0 or profile.total_years_experience == 6.0


@pytest.mark.asyncio
async def test_parse_profile_async_pure_local():
    """Ensure async parsing operates 100% locally with zero external model daemons."""
    profile = await ResumeExtractorService.parse_profile_async(
        SAMPLE_RESUME_TEXT,
        user_id="usr_async_01",
    )
    assert profile.user_id == "usr_async_01"
    assert profile.model_version == "deterministic_extractor:v1"
    assert profile.full_name == "Jane Doe"
    assert len(profile.skills) >= 4


@pytest.mark.asyncio
async def test_parse_profile_async_with_inferred_fields():
    """Test async parsing with estimated or inferred fields when years not explicit in text."""
    resume_without_explicit_years = """
    Sarah Connor
    Email: sarah.connor@sky.net
    Location: Los Angeles, CA

    Experience:
    AI Systems Architect at Cyberdyne Systems
    - Led research on autonomous reinforcement learning algorithms.
    """

    profile = await ResumeExtractorService.parse_profile_async(
        resume_without_explicit_years,
        user_id="usr_sarah_01",
        extra_fields={"total_years_experience": 8.0, "full_name": "Dr. Sarah Connor"},
    )

    assert profile.user_id == "usr_sarah_01"
    assert profile.model_version == "deterministic_extractor:v1"
    assert profile.full_name == "Dr. Sarah Connor"
    assert profile.total_years_experience == 8.0
    assert any("total_years_experience: 8.0 (inferred)" in inf for inf in profile.inferred_fields)
