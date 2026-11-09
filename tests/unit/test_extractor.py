from services.api.services.extractor import ResumeExtractorService
from packages.contracts.profile import VerificationState

SAMPLE_RESUME_TEXT = """
Jane Doe
Email: jane.doe@example.com
Phone: (555) 123-4567

Professional Summary:
Passionate Software Engineer at CloudCorp with extensive expertise in building scalable systems.

Experience:
Senior Software Engineer at CloudCorp
- Architected distributed microservices in Python and FastAPI.
- Built interactive dashboards using Next.js, React, and TypeScript.
- Managed PostgreSQL database instances with pgvector for semantic search.

Education:
Bachelor of Science from Stanford University
"""


def test_resume_text_extraction_and_parsing():
    profile = ResumeExtractorService.parse_profile(SAMPLE_RESUME_TEXT, user_id="test_user_001")

    assert profile.full_name == "Jane Doe"
    assert profile.email == "jane.doe@example.com"
    assert profile.phone == "(555) 123-4567"

    # Verify skills extraction
    skill_names = [s.name for s in profile.skills]
    assert "Python" in skill_names
    assert "FastAPI" in skill_names
    assert "React" in skill_names
    assert "PostgreSQL" in skill_names

    # Check evidence grounding
    for skill in profile.skills:
        assert skill.verification_state == VerificationState.VERIFIED_FACT
        assert skill.evidence is not None
        assert skill.evidence.raw_snippet is not None

    # Check missing fields separation
    missing_field_names = [m.field_name for m in profile.missing_fields]
    assert "work_authorization" in missing_field_names
    assert not profile.is_profile_confirmed

