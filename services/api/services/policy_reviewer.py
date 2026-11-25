import logging
import re
from typing import Any, Dict, List, Optional, Set

from packages.contracts.application import (
    ApplicationPackage,
    ApplicationQuestionAnswer,
    CoverLetter,
    TailoredResume,
)
from packages.contracts.job import JobListing
from packages.contracts.policy import (
    PolicyCheckType,
    PolicyReviewResult,
    PolicySeverity,
    PolicyViolation,
    PrivacyRedaction,
)
from packages.contracts.profile import CandidateProfile

logger = logging.getLogger("agentflow.policy_reviewer")

# Common scam or suspicious indicators in job postings
SCAM_INDICATORS = [
    r"wire\s+transfer",
    r"western\s+union",
    r"crypto(?:currency)?\s+fee",
    r"pay\s+(?:upfront|before\s+interview)",
    r"check\s+deposit",
    r"send\s+gift\s+cards?",
    r"telegram\s+interview\s+only",
]

# Sensitive PII patterns
SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CREDIT_CARD_PATTERN = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")
TOKEN_PATTERN = re.compile(r"\b(?:hf_[A-Za-z0-9]{30,}|ghp_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{30,})\b")


class PolicyReviewerService:
    """
    Policy & Quality Reviewer (Agent Role 9).
    Enforces that ungrounded claims, privacy violations, or suspicious listings
    are flagged and require human remediation or confirmation.
    """

    def review_cover_letter(
        self,
        cover_letter: CoverLetter,
        candidate: CandidateProfile,
        job: Optional[JobListing] = None,
    ) -> PolicyReviewResult:
        """
        Evaluate a cover letter for unsupported claims, privacy breaches, and factual alignment.
        """
        return self._evaluate_content(
            full_text=cover_letter.full_text,
            candidate=candidate,
            job=job,
            context="cover_letter",
            existing_warnings=cover_letter.unsupported_claim_warnings,
        )

    def review_application_answers(
        self,
        answers: List[ApplicationQuestionAnswer],
        candidate: CandidateProfile,
        job: Optional[JobListing] = None,
    ) -> PolicyReviewResult:
        """
        Evaluate application form answers for missing evidence or unsupported claims.
        """
        violations: List[PolicyViolation] = []
        redactions: List[PrivacyRedaction] = []

        combined_text = " ".join(a.answer for a in answers)
        redactions.extend(self._check_privacy(combined_text))

        for ans in answers:
            if ans.requires_user_input:
                violations.append(
                    PolicyViolation(
                        check_type=PolicyCheckType.UNSUPPORTED_CLAIM,
                        severity=PolicySeverity.WARNING,
                        message=f"Question '{ans.question[:40]}...' requires user confirmation: {ans.missing_evidence_reason}",
                        offending_field_or_text=ans.question,
                        remediation_hint="Candidate must provide personal details or confirm answer before submission.",
                    )
                )
            for warning in ans.unsupported_claim_warnings:
                violations.append(
                    PolicyViolation(
                        check_type=PolicyCheckType.UNSUPPORTED_CLAIM,
                        severity=PolicySeverity.WARNING,
                        message=warning,
                        offending_field_or_text=ans.answer[:60],
                    )
                )

        score = max(0.0, 100.0 - (len(violations) * 12.0) - (len(redactions) * 20.0))
        blockers = [v for v in violations if v.severity == PolicySeverity.BLOCKER]
        has_redactions = len(redactions) > 0

        requires_human = bool(violations or has_redactions)
        reason = None
        if blockers:
            reason = f"Blocked by {len(blockers)} high-severity policy violation(s)."
        elif violations:
            reason = f"{len(violations)} application question(s) require candidate verification."

        return PolicyReviewResult(
            is_safe_to_proceed=len(blockers) == 0,
            overall_quality_score=round(score, 1),
            violations=violations,
            requires_human_approval=requires_human,
            approval_gate_reason=reason,
            redactions=redactions,
            audit_metadata={"context": "application_answers", "answer_count": len(answers)},
        )

    def review_full_package(
        self,
        package: ApplicationPackage,
        candidate: CandidateProfile,
        job: JobListing,
    ) -> PolicyReviewResult:
        """
        Audit complete application package (tailored resume, cover letter, answers).
        """
        violations: List[PolicyViolation] = []
        redactions: List[PrivacyRedaction] = []

        # 1. Check job listing for scam indicators
        if job.description_text:
            for pattern in SCAM_INDICATORS:
                if re.search(pattern, job.description_text, re.IGNORECASE):
                    violations.append(
                        PolicyViolation(
                            check_type=PolicyCheckType.SUSPICIOUS_LISTING,
                            severity=PolicySeverity.BLOCKER,
                            message=f"Suspicious job listing indicator detected: '{pattern}'",
                            offending_field_or_text=job.description_text[:100],
                            remediation_hint="Verify the employer's official careers site before proceeding.",
                        )
                    )

        # 2. Check resume text
        if package.tailored_resume:
            resume_eval = self._evaluate_content(
                full_text=package.tailored_resume.content_text,
                candidate=candidate,
                job=job,
                context="tailored_resume",
                existing_warnings=package.tailored_resume.unsupported_claim_warnings,
            )
            violations.extend(resume_eval.violations)
            redactions.extend(resume_eval.redactions)

        # 3. Check cover letter
        if package.cover_letter:
            cl_eval = self._evaluate_content(
                full_text=package.cover_letter.content_text,
                candidate=candidate,
                job=job,
                context="cover_letter",
                existing_warnings=package.cover_letter.unsupported_claim_warnings,
            )
            violations.extend(cl_eval.violations)
            redactions.extend(cl_eval.redactions)

        # 4. Consolidate package warnings
        for warning in package.unsupported_claim_warnings:
            violations.append(
                PolicyViolation(
                    check_type=PolicyCheckType.UNSUPPORTED_CLAIM,
                    severity=PolicySeverity.WARNING,
                    message=warning,
                )
            )

        blockers = [v for v in violations if v.severity == PolicySeverity.BLOCKER]
        score = max(0.0, 100.0 - (len(blockers) * 25.0) - (len(violations) * 8.0) - (len(redactions) * 15.0))

        requires_human = True  # Always requires human gate prior to application submission
        gate_reason = "Human approval required prior to application dispatch."
        if blockers:
            gate_reason = f"Application blocked: {len(blockers)} policy blocker(s) must be resolved."

        return PolicyReviewResult(
            is_safe_to_proceed=len(blockers) == 0,
            overall_quality_score=round(score, 1),
            violations=violations,
            requires_human_approval=requires_human,
            approval_gate_reason=gate_reason,
            redactions=redactions,
            audit_metadata={"job_id": job.id, "package_id": package.id},
        )

    def _evaluate_content(
        self,
        full_text: str,
        candidate: CandidateProfile,
        job: Optional[JobListing],
        context: str,
        existing_warnings: Optional[List[str]] = None,
    ) -> PolicyReviewResult:
        """
        Internal evaluator for text against confirmed candidate profile facts.
        """
        violations: List[PolicyViolation] = []
        redactions = self._check_privacy(full_text)

        # A. Check for phantom employers
        # Find capitalized phrases following "at ", "for ", "with " that are not the candidate's employers or the target company
        known_companies = {exp.company.lower() for exp in candidate.experience}
        if job:
            known_companies.add(job.organization.lower())
        for edu in candidate.education:
            known_companies.add(edu.institution.lower())

        # Check existing warnings
        for w in existing_warnings or []:
            violations.append(
                PolicyViolation(
                    check_type=PolicyCheckType.UNSUPPORTED_CLAIM,
                    severity=PolicySeverity.WARNING,
                    message=w,
                    remediation_hint="Confirm requirement in candidate profile or omit claim.",
                )
            )

        # B. Check for ungrounded degree claims
        known_degrees = " ".join(edu.degree.lower() for edu in candidate.education)
        if ("ph.d" in full_text.lower() or "doctorate" in full_text.lower()) and "ph.d" not in known_degrees and "doctorate" not in known_degrees:
            violations.append(
                PolicyViolation(
                    check_type=PolicyCheckType.UNSUPPORTED_CLAIM,
                    severity=PolicySeverity.BLOCKER,
                    message="Document references Ph.D./Doctorate credential not found in verified education history.",
                    offending_field_or_text="Ph.D. / Doctorate",
                    remediation_hint="Remove unverified advanced degree claim.",
                )
            )

        # C. Exaggerated years of experience
        cand_years = candidate.total_years_experience or (len(candidate.experience) * 2.0)
        years_matches = re.findall(r"\b(\d+)\+?\s+years?\b", full_text, re.IGNORECASE)
        for ym in years_matches:
            claimed_years = int(ym)
            if claimed_years > (cand_years + 3.0):
                violations.append(
                    PolicyViolation(
                        check_type=PolicyCheckType.UNSUPPORTED_CLAIM,
                        severity=PolicySeverity.WARNING,
                        message=f"Claimed experience ({claimed_years} years) significantly exceeds confirmed profile duration ({cand_years:.0f} years).",
                        offending_field_or_text=f"{claimed_years} years",
                        remediation_hint="Align stated years with verified experience timeline.",
                    )
                )

        blockers = [v for v in violations if v.severity == PolicySeverity.BLOCKER]
        score = max(0.0, 100.0 - (len(blockers) * 25.0) - (len(violations) * 10.0) - (len(redactions) * 15.0))

        return PolicyReviewResult(
            is_safe_to_proceed=len(blockers) == 0,
            overall_quality_score=round(score, 1),
            violations=violations,
            requires_human_approval=bool(violations or redactions),
            approval_gate_reason=f"{len(violations)} check(s) flagged during {context} evaluation." if violations else None,
            redactions=redactions,
            audit_metadata={"context": context},
        )

    def _check_privacy(self, text: str) -> List[PrivacyRedaction]:
        """
        Detect sensitive PII or credentials.
        """
        redactions: List[PrivacyRedaction] = []

        if SSN_PATTERN.search(text):
            redactions.append(
                PrivacyRedaction(
                    field_name="social_security_number",
                    redaction_type="ssn",
                    redacted_preview="[REDACTED-SSN]",
                )
            )

        if CREDIT_CARD_PATTERN.search(text):
            redactions.append(
                PrivacyRedaction(
                    field_name="credit_card_number",
                    redaction_type="credit_card",
                    redacted_preview="[REDACTED-CC]",
                )
            )

        if TOKEN_PATTERN.search(text):
            redactions.append(
                PrivacyRedaction(
                    field_name="auth_token",
                    redaction_type="token",
                    redacted_preview="[REDACTED-TOKEN]",
                )
            )

        return redactions
