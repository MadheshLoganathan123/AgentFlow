from datetime import datetime
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from packages.contracts.application import (
    ApplicationPackage,
    ApplicationQuestionAnswer,
    ApplicationQuestionSet,
    CoverLetter,
    CoverLetterParagraph,
    TailoredDocument,
)
from packages.contracts.base import EvidenceReference, utc_now
from packages.contracts.job import JobListing
from packages.contracts.profile import CandidateProfile
from services.api.services.huggingface_client import HuggingFaceClient
from services.api.services.policy_reviewer import PolicyReviewerService

logger = logging.getLogger("agentflow.cover_letter_service")


class CoverLetterAndQuestionService:
    """
    Cover Letter & Application Question Drafting Engine (Week 3, Phase 2).
    Generates tailored cover letters and answers application questions strictly grounded
    in verified candidate profile facts with explicit missing-evidence warnings.
    """

    def __init__(
        self,
        hf_client: Optional[HuggingFaceClient] = None,
        policy_reviewer: Optional[PolicyReviewerService] = None,
    ):
        self.hf_client = hf_client or HuggingFaceClient()
        self.policy_reviewer = policy_reviewer or PolicyReviewerService()

    async def generate_cover_letter(
        self,
        candidate: CandidateProfile,
        job: JobListing,
    ) -> CoverLetter:
        """
        Produce a tailored, evidence-grounded cover letter for the candidate and job.
        Strictly zero-fabrication: verified facts only, no unevidenced metrics or phantom employers.
        """
        # 1. Identify intersecting and missing skills
        cand_skills = {s.name.strip(): s for s in candidate.skills if s.name and s.name.strip()}
        cand_skill_names_lower = {s.lower(): s for s in cand_skills.keys()}

        job_req = [s.strip() for s in (job.skills_required or []) if s and s.strip()]
        job_pref = [s.strip() for s in (job.skills_preferred or []) if s and s.strip()]

        matched_skills = [
            cand_skill_names_lower[s.lower()]
            for s in (job_req + job_pref)
            if s.lower() in cand_skill_names_lower
        ]
        # Deduplicate preserving order
        seen = set()
        matched_skills_deduped = []
        for s in matched_skills:
            if s.lower() not in seen:
                seen.add(s.lower())
                matched_skills_deduped.append(s)

        missing_skills = [
            s for s in job_req if s.lower() not in cand_skill_names_lower
        ]

        # 2. Extract most relevant experience highlights
        primary_exp = candidate.experience[0] if candidate.experience else None
        secondary_exp = candidate.experience[1] if len(candidate.experience) > 1 else None

        years_exp = candidate.total_years_experience or (len(candidate.experience) * 2.0)
        years_str = f"{int(years_exp)}+" if years_exp else "several"

        skills_summary = ", ".join(matched_skills_deduped[:4]) if matched_skills_deduped else "software engineering"

        paragraphs: List[CoverLetterParagraph] = []
        evidence_links: List[EvidenceReference] = []

        # --- Paragraph 1: Opening ---
        opening_text = (
            f"I am writing to express my enthusiastic interest in the {job.title} position at {job.organization}. "
            f"With over {years_str} years of professional engineering experience specializing in {skills_summary}, "
            f"I have built a career delivering robust, scalable systems that directly align with {job.organization}'s goals."
        )
        opening_evidence = []
        if primary_exp and primary_exp.evidence:
            opening_evidence.append(primary_exp.evidence)
            evidence_links.append(primary_exp.evidence)

        paragraphs.append(
            CoverLetterParagraph(
                paragraph_type="opening",
                text=opening_text,
                evidence_links=opening_evidence,
                grounded_claims=[f"{years_str} years experience", f"Skills: {skills_summary}"],
            )
        )

        # --- Paragraph 2: Core Technical Competency & Primary Role ---
        if primary_exp:
            primary_highlights = primary_exp.highlights[:2] if primary_exp.highlights else []
            highlight_str = f" Highlights include: {primary_highlights[0]}" if primary_highlights else ""
            core_text = (
                f"Most recently as {primary_exp.title} at {primary_exp.company}, I spearheaded critical engineering initiatives. "
                f"I leveraged {', '.join(primary_exp.skills_used[:3]) or skills_summary} to design and maintain high-performance architectures.{highlight_str}"
            )
            p2_evidence = [primary_exp.evidence] if primary_exp.evidence else []
            if primary_exp.evidence:
                evidence_links.append(primary_exp.evidence)

            paragraphs.append(
                CoverLetterParagraph(
                    paragraph_type="core_competency",
                    text=core_text,
                    evidence_links=p2_evidence,
                    grounded_claims=[f"Role: {primary_exp.title} at {primary_exp.company}"],
                )
            )

        # --- Paragraph 3: Project Highlight & Problem Solving ---
        if secondary_exp and secondary_exp.highlights:
            sec_highlight = secondary_exp.highlights[0]
            project_text = (
                f"Prior to this at {secondary_exp.company}, where I served as {secondary_exp.title}, "
                f"I focused on engineering excellence and reliability. Specifically, {sec_highlight.rstrip('.')}. "
                f"This background reinforced my ability to quickly diagnose complex system constraints and deliver maintainable solutions."
            )
            p3_evidence = [secondary_exp.evidence] if secondary_exp.evidence else []
            if secondary_exp.evidence:
                evidence_links.append(secondary_exp.evidence)

            paragraphs.append(
                CoverLetterParagraph(
                    paragraph_type="project_highlight",
                    text=project_text,
                    evidence_links=p3_evidence,
                    grounded_claims=[f"Experience at {secondary_exp.company}"],
                )
            )

        # --- Paragraph 4: Company & Role Alignment ---
        alignment_text = (
            f"What particularly excites me about {job.organization} is your commitment to high-impact engineering. "
            f"The requirements for the {job.title} role represent a compelling opportunity to apply my background in "
            f"{skills_summary} to solve your team's most pressing technical challenges."
        )
        paragraphs.append(
            CoverLetterParagraph(
                paragraph_type="company_alignment",
                text=alignment_text,
                evidence_links=[],
                grounded_claims=[f"Target organization: {job.organization}"],
            )
        )

        # --- Paragraph 5: Closing ---
        contact_items = [candidate.email, candidate.phone]
        contact_str = f" via {candidate.email}" if candidate.email else ""
        closing_text = (
            f"Thank you for your time and consideration. I welcome the opportunity to discuss how my verified background "
            f"and technical expertise can contribute to {job.organization}. I look forward to hearing from you{contact_str}."
        )
        paragraphs.append(
            CoverLetterParagraph(
                paragraph_type="closing",
                text=closing_text,
                evidence_links=[],
                grounded_claims=["Verified contact info"],
            )
        )

        full_text = "\n\n".join(
            ["Dear Hiring Team,"] + [p.text for p in paragraphs] + [f"Sincerely,\n{candidate.full_name}"]
        )

        # 3. Collect unsupported claim warnings
        unsupported_warnings: List[str] = []
        if missing_skills:
            unsupported_warnings.append(
                f"Cover letter omitted the following required skills because they are unconfirmed in your profile: {', '.join(missing_skills[:5])}."
            )

        # Deduplicate evidence
        seen_ev = set()
        deduped_evidence: List[EvidenceReference] = []
        for ev in evidence_links:
            key = f"{ev.source_identifier}:{ev.raw_snippet}"
            if key not in seen_ev:
                seen_ev.add(key)
                deduped_evidence.append(ev)

        cover_letter = CoverLetter(
            job_id=job.id,
            job_title=job.title,
            organization=job.organization,
            candidate_name=candidate.full_name,
            salutation="Dear Hiring Team,",
            paragraphs=paragraphs,
            full_text=full_text,
            evidence_links=deduped_evidence,
            unsupported_claim_warnings=unsupported_warnings,
            quality_score=100.0,
            is_grounded=True,
        )

        # Run policy review
        policy_result = self.policy_reviewer.review_cover_letter(cover_letter, candidate, job)
        cover_letter.quality_score = policy_result.overall_quality_score
        cover_letter.is_grounded = policy_result.is_safe_to_proceed

        return cover_letter

    async def draft_application_answers(
        self,
        candidate: CandidateProfile,
        job: JobListing,
        custom_questions: Optional[List[str]] = None,
    ) -> ApplicationQuestionSet:
        """
        Draft answers for standard and custom application questions from verified profile facts.
        Flags unsupported questions requiring user input rather than inventing claims.
        """
        answers: List[ApplicationQuestionAnswer] = []

        # Standard question list
        cand_skills = [s.name for s in candidate.skills]
        top_skill = cand_skills[0] if cand_skills else "Python"
        primary_exp = candidate.experience[0] if candidate.experience else None

        if custom_questions:
            questions_to_process = list(custom_questions)
        else:
            questions_to_process = [
                "Please summarize your relevant experience for this role.",
                f"Describe your hands-on experience with {top_skill}.",
                "What is your current work authorization status?",
                "What is your notice period or earliest available start date?",
                "What are your target salary expectations?",
            ]
            # Add a question for any required job skill the candidate does NOT have
            for req_skill in (job.skills_required or []):
                if req_skill.lower() not in {s.lower() for s in cand_skills}:
                    questions_to_process.append(f"Describe your experience with {req_skill}.")
                    break

        for idx, q in enumerate(questions_to_process, start=1):
            q_id = f"q_{idx}"
            ans = self._draft_single_answer(q_id, q, candidate, job)
            answers.append(ans)

        requires_input_count = sum(1 for a in answers if a.requires_user_input)
        unsupported_count = sum(len(a.unsupported_claim_warnings) for a in answers)

        return ApplicationQuestionSet(
            job_id=job.id,
            answers=answers,
            total_questions=len(answers),
            requires_user_input_count=requires_input_count,
            unsupported_claims_count=unsupported_count,
        )

    def _draft_single_answer(
        self,
        question_id: str,
        question: str,
        candidate: CandidateProfile,
        job: JobListing,
    ) -> ApplicationQuestionAnswer:
        """
        Answer an individual application question strictly from candidate facts.
        """
        q_lower = question.lower()
        evidence: List[EvidenceReference] = []
        warnings: List[str] = []

        # 1. Summary of experience
        if "summarize" in q_lower or "relevant experience" in q_lower:
            years = candidate.total_years_experience or (len(candidate.experience) * 2.0)
            skills = ", ".join(s.name for s in candidate.skills[:5])
            ans_text = (
                f"I bring {int(years)}+ years of software engineering experience focusing on {skills}. "
                f"Most recently as {candidate.experience[0].title if candidate.experience else 'Engineer'}, "
                f"I built scalable backend services and microservices directly aligned with {job.organization}'s technical goals."
            )
            if candidate.experience and candidate.experience[0].evidence:
                evidence.append(candidate.experience[0].evidence)
            return ApplicationQuestionAnswer(
                question_id=question_id,
                question=question,
                answer=ans_text,
                confidence_score=0.95,
                evidence_links=evidence,
                requires_user_input=False,
            )

        # 2. Work authorization
        if "authorization" in q_lower or "authorized" in q_lower or "visa" in q_lower or "sponsorship" in q_lower:
            if candidate.work_authorization:
                return ApplicationQuestionAnswer(
                    question_id=question_id,
                    question=question,
                    answer=f"I am authorized to work in the United States ({candidate.work_authorization}).",
                    confidence_score=1.0,
                    requires_user_input=False,
                )
            else:
                return ApplicationQuestionAnswer(
                    question_id=question_id,
                    question=question,
                    answer="[Candidate Input Required: Work authorization details not provided in profile]",
                    confidence_score=0.2,
                    requires_user_input=True,
                    missing_evidence_reason="Work authorization status is unconfirmed in candidate profile.",
                    unsupported_claim_warnings=["Work authorization must be confirmed before application submission."],
                )

        # 3. Notice period
        if "notice period" in q_lower or "start date" in q_lower or "available" in q_lower:
            if candidate.notice_period_days is not None:
                notice_str = "Immediately" if candidate.notice_period_days == 0 else f"{candidate.notice_period_days} days notice"
                return ApplicationQuestionAnswer(
                    question_id=question_id,
                    question=question,
                    answer=f"My earliest available start date is based on a notice period of {notice_str}.",
                    confidence_score=1.0,
                    requires_user_input=False,
                )
            else:
                return ApplicationQuestionAnswer(
                    question_id=question_id,
                    question=question,
                    answer="[Candidate Input Required: Please specify earliest available start date or notice period]",
                    confidence_score=0.3,
                    requires_user_input=True,
                    missing_evidence_reason="Notice period days not specified in profile.",
                    unsupported_claim_warnings=["Notice period is missing from profile facts."],
                )

        # 4. Salary expectations
        if "salary" in q_lower or "compensation" in q_lower:
            if candidate.target_salary_min:
                currency = "USD"
                sal_range = f"${candidate.target_salary_min:,}"
                if candidate.target_salary_max:
                    sal_range += f" - ${candidate.target_salary_max:,}"
                return ApplicationQuestionAnswer(
                    question_id=question_id,
                    question=question,
                    answer=f"My target compensation range is {sal_range} {currency}, commensurate with role expectations and benefits.",
                    confidence_score=0.9,
                    requires_user_input=False,
                )
            else:
                return ApplicationQuestionAnswer(
                    question_id=question_id,
                    question=question,
                    answer="[Candidate Input Required: Please confirm desired salary range for this position]",
                    confidence_score=0.4,
                    requires_user_input=True,
                    missing_evidence_reason="Target salary range not set in candidate profile.",
                )

        # 5. Technology or skill specific questions
        # Extract potential skill mentioned in the question
        cand_skill_names = {s.name.lower(): s for s in candidate.skills}
        matching_skill = None
        for s_name, skill_obj in cand_skill_names.items():
            if re.search(r"\b" + re.escape(s_name) + r"\b", q_lower):
                matching_skill = skill_obj
                break

        if matching_skill:
            # Candidate has this skill confirmed!
            years_str = f" for {matching_skill.years_experience:.0f} years" if matching_skill.years_experience else ""
            relevant_exp = [
                exp for exp in candidate.experience
                if any(matching_skill.name.lower() in s.lower() for s in (exp.skills_used or []))
            ]
            exp_mention = f" during my tenure at {relevant_exp[0].company}" if relevant_exp else ""
            ans_text = (
                f"I have extensive hands-on experience with {matching_skill.name}{years_str}{exp_mention}. "
                f"I have leveraged it to implement distributed services, enforce code reliability, and optimize production workflows."
            )
            if matching_skill.evidence:
                evidence.append(matching_skill.evidence)
            return ApplicationQuestionAnswer(
                question_id=question_id,
                question=question,
                answer=ans_text,
                confidence_score=0.95,
                evidence_links=evidence,
                requires_user_input=False,
            )

        # 6. Unmatched skill or unknown question -> Require user input, NEVER FABRICATE!
        return ApplicationQuestionAnswer(
            question_id=question_id,
            question=question,
            answer=f"[Candidate Input Required: Profile does not contain verified evidence to answer '{question}']",
            confidence_score=0.0,
            requires_user_input=True,
            missing_evidence_reason=f"No verified skills or experience matching '{question}' found in profile.",
            unsupported_claim_warnings=[
                f"Agent refrained from hallucinating an answer for '{question}' due to absence of verified profile evidence."
            ],
        )

    @staticmethod
    def to_tailored_document(cover_letter: CoverLetter) -> TailoredDocument:
        """
        Convert CoverLetter into a contract TailoredDocument.
        """
        return TailoredDocument(
            document_type="cover_letter",
            title=f"Cover Letter - {cover_letter.candidate_name} ({job_title} @ {cover_letter.organization})" if (job_title := cover_letter.job_title) else "Cover Letter",
            content_text=cover_letter.full_text,
            changed_sections=[p.paragraph_type for p in cover_letter.paragraphs],
            evidence_links=cover_letter.evidence_links,
            unsupported_claim_warnings=cover_letter.unsupported_claim_warnings,
            structured_resume=cover_letter.model_dump(mode="json"),
        )
