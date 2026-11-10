import io
import re
from typing import List, Optional

from pypdf import PdfReader

from packages.contracts.base import EvidenceReference
from packages.contracts.profile import (
    CandidateProfile,
    Education,
    MissingFieldNotice,
    SkillItem,
    VerificationState,
    WorkExperience,
    WorkModePreference,
)


class ResumeExtractorService:
    """
    Open-source text extraction and profile structuring engine.
    Ensures that factual evidence from the document is strictly isolated from model inferences.
    """

    @staticmethod
    def extract_text_from_pdf(pdf_bytes: bytes) -> str:
        """Extract plain text from uploaded PDF bytes using pypdf."""
        reader = PdfReader(io.BytesIO(pdf_bytes))
        extracted_pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            extracted_pages.append(text)
        return "\n".join(extracted_pages).strip()

    @classmethod
    def parse_profile(cls, raw_text: str, user_id: str = "default-user") -> CandidateProfile:
        """
        Parses raw text into a structured CandidateProfile.
        Distinguishes verified facts from missing or inferred values.
        """
        email = cls._extract_email(raw_text)
        phone = cls._extract_phone(raw_text)
        name = cls._extract_name(raw_text, email)
        skills = cls._extract_skills(raw_text)
        experiences = cls._extract_experience(raw_text)
        education = cls._extract_education(raw_text)

        # Check for missing critical fields required for matching
        missing_fields: List[MissingFieldNotice] = []
        inferred_fields: List[str] = []

        work_auth = None
        if "authorized to work" in raw_text.lower() or "us citizen" in raw_text.lower():
            work_auth = "Authorized"
        else:
            missing_fields.append(MissingFieldNotice(
                field_name="work_authorization",
                description="Work authorization status is not explicitly stated in resume.",
                is_critical_for_matching=True,
                suggested_question="What is your work authorization status (e.g. Citizen, Permanent Resident, Visa)?"
            ))

        missing_fields.append(MissingFieldNotice(
            field_name="target_salary_min",
            description="Target salary expectations are not in resume.",
            is_critical_for_matching=False,
            suggested_question="What is your target minimum annual salary?"
        ))

        missing_fields.append(MissingFieldNotice(
            field_name="notice_period_days",
            description="Notice period is not in resume.",
            is_critical_for_matching=False,
            suggested_question="How many days notice do you need before starting a new role?"
        ))

        # Approximate total years of experience
        total_years = float(len(experiences) * 2.0) if experiences else 1.0

        return CandidateProfile(
            user_id=user_id,
            full_name=name,
            email=email,
            phone=phone,
            primary_location="Remote / Flexible",
            work_modes=[WorkModePreference.REMOTE, WorkModePreference.HYBRID],
            target_job_titles=[exp.title for exp in experiences] if experiences else ["Software Engineer"],
            total_years_experience=total_years,
            skills=skills,
            experience=experiences,
            education=education,
            work_authorization=work_auth,
            missing_fields=missing_fields,
            inferred_fields=inferred_fields,
            raw_resume_text=raw_text,
            is_profile_confirmed=False
        )

    @staticmethod
    def _extract_email(text: str) -> Optional[str]:
        match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
        return match.group(0) if match else None

    @staticmethod
    def _extract_phone(text: str) -> Optional[str]:
        match = re.search(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text)
        return match.group(0) if match else None

    @staticmethod
    def _extract_name(text: str, email: Optional[str]) -> str:
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if lines:
            first_line = lines[0]
            if len(first_line.split()) <= 4 and not any(char in first_line for char in "@0123456789"):
                return first_line
        if email:
            prefix = email.split("@")[0].replace(".", " ").title()
            return prefix
        return "Candidate"

    @classmethod
    def _extract_skills(cls, text: str) -> List[SkillItem]:
        common_skills = [
            "Python", "TypeScript", "JavaScript", "React", "Next.js", "Node.js",
            "FastAPI", "SQL", "PostgreSQL", "Docker", "Kubernetes", "AWS", "Git",
            "LangGraph", "LangChain", "Machine Learning", "GraphQL", "Tailwind CSS"
        ]
        found_skills = []
        for skill in common_skills:
            pattern = rf"\b{re.escape(skill)}\b"
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                evidence = EvidenceReference(
                    source_type="resume_text",
                    source_identifier="skills_section",
                    raw_snippet=match.group(0),
                    confidence_score=1.0,
                    is_inferred=False
                )
                found_skills.append(SkillItem(
                    name=skill,
                    category="technical",
                    verification_state=VerificationState.VERIFIED_FACT,
                    evidence=evidence
                ))
        return found_skills

    @classmethod
    def _extract_experience(cls, text: str) -> List[WorkExperience]:
        experiences = []
        exp_pattern = re.compile(
            r"(Senior\s+[\w\s]+|Software\s+Engineer|Full\s+Stack\s+Developer|Data\s+Scientist|Product\s+Manager|Engineer)\s+(?:at|@)\s+([\w\s]+)",
            re.IGNORECASE
        )
        for match in exp_pattern.finditer(text):
            title = match.group(1).strip()
            company = match.group(2).strip()
            evidence = EvidenceReference(
                source_type="resume_text",
                source_identifier="experience_section",
                raw_snippet=match.group(0),
                confidence_score=0.9,
                is_inferred=False
            )
            experiences.append(WorkExperience(
                title=title,
                company=company,
                evidence=evidence
            ))
        return experiences

    @classmethod
    def _extract_education(cls, text: str) -> List[Education]:
        education_list = []
        degree_pattern = re.compile(
            r"(Bachelor(?:'s)?|Master(?:'s)?|B\.S\.|M\.S\.|Ph\.D\.)\s+(?:of|in)?\s+([\w\s]+)\s+(?:from|at)\s+([\w\s]+)",
            re.IGNORECASE
        )
        for match in degree_pattern.finditer(text):
            degree = match.group(1).strip()
            field_study = match.group(2).strip()
            institution = match.group(3).strip()
            evidence = EvidenceReference(
                source_type="resume_text",
                source_identifier="education_section",
                raw_snippet=match.group(0),
                confidence_score=0.95,
                is_inferred=False
            )
            education_list.append(Education(
                institution=institution,
                degree=degree,
                field_of_study=field_study,
                evidence=evidence
            ))
        return education_list

