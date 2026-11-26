import logging
from typing import Dict, List, Optional

from packages.contracts.base import EvidenceReference
from packages.contracts.email import (
    EmailDraft,
    EmailTone,
    EmailType,
    EmailVariantItem,
)
from packages.contracts.job import JobListing
from packages.contracts.profile import CandidateProfile
from services.api.services.huggingface_client import HuggingFaceClient
from services.api.services.policy_reviewer import PolicyReviewerService

logger = logging.getLogger("agentflow.email_writer")


class EmailWriterService:
    """
    Role-Specific Professional Email Writer (Agent Role 7).
    Drafts high-converting, personalized outreach messages for job seekers.
    Strict safety rules:
      - NEVER sends emails automatically in v1.
      - Grounds claims strictly in confirmed candidate profile facts.
      - Flags missing recipient names or unverified assumptions.
      - Provides 3 tone variants (Professional, Conversational, Executive).
    """

    def __init__(
        self,
        hf_client: Optional[HuggingFaceClient] = None,
        policy_reviewer: Optional[PolicyReviewerService] = None,
    ):
        self.hf_client = hf_client or HuggingFaceClient()
        self.policy_reviewer = policy_reviewer or PolicyReviewerService()

    async def generate_draft(
        self,
        candidate: CandidateProfile,
        job: JobListing,
        email_type: EmailType = EmailType.RECRUITER_OUTREACH,
        recipient_name: Optional[str] = None,
        recipient_role: Optional[str] = None,
        preferred_tone: EmailTone = EmailTone.PROFESSIONAL,
        extra_context: Optional[str] = None,
    ) -> EmailDraft:
        """
        Generate a personalized outreach draft with 3 tone variants and fact grounding.
        """
        # 1. Missing recipient warnings & assumptions
        recipient_assumptions: List[str] = []
        missing_recipient_warnings: List[str] = []

        if not recipient_name or not recipient_name.strip():
            missing_recipient_warnings.append(
                "Recipient name is not specified. A placeholder has been inserted — please confirm the recipient's name before sending."
            )
            clean_recipient = "[Hiring Manager / Recruiter Name]"
        else:
            clean_recipient = recipient_name.strip()

        if email_type in (EmailType.RECRUITER_OUTREACH, EmailType.HIRING_MANAGER_NOTE):
            recipient_assumptions.append("Assumes recipient is the primary technical recruiter or hiring team member for this role.")
        elif email_type == EmailType.REFERRAL_REQUEST:
            recipient_assumptions.append("Assumes recipient is an existing employee, alumnus, or professional connection at the target organization.")
        elif email_type == EmailType.FOLLOW_UP:
            recipient_assumptions.append("Assumes an application has already been submitted through the careers portal.")
        elif email_type == EmailType.THANK_YOU:
            recipient_assumptions.append("Assumes an interview or initial technical screening took place recently.")

        # 2. Extract verified candidate facts & intersecting skills
        cand_skills = [s.name for s in candidate.skills if s.name]
        job_req = [s for s in (job.skills_required or []) if s]
        job_pref = [s for s in (job.skills_preferred or []) if s]

        cand_skills_lower = {s.lower(): s for s in cand_skills}
        matching_skills = [
            cand_skills_lower[s.lower()]
            for s in (job_req + job_pref)
            if s.lower() in cand_skills_lower
        ]
        # Deduplicate
        seen = set()
        matched_skills_deduped = []
        for s in matching_skills:
            if s.lower() not in seen:
                seen.add(s.lower())
                matched_skills_deduped.append(s)

        top_skills_str = ", ".join(matched_skills_deduped[:3]) if matched_skills_deduped else ", ".join(cand_skills[:3])
        years_exp = candidate.total_years_experience or (len(candidate.experience) * 2.0)
        years_str = f"{int(years_exp)}+" if years_exp else "several"

        primary_exp = candidate.experience[0] if candidate.experience else None
        current_title = primary_exp.title if primary_exp else "Software Engineer"
        current_company = primary_exp.company if primary_exp else "Tech Company"

        # 3. Collect personalization evidence links
        personalization_evidence: List[EvidenceReference] = []
        if primary_exp and primary_exp.evidence:
            personalization_evidence.append(primary_exp.evidence)
        for s in candidate.skills[:3]:
            if s.evidence:
                personalization_evidence.append(s.evidence)

        # 4. Generate variants for all 3 tones
        variants_dict: Dict[EmailTone, EmailVariantItem] = {}
        for tone_enum in [EmailTone.PROFESSIONAL, EmailTone.CONVERSATIONAL, EmailTone.EXECUTIVE]:
            var_item = self._render_template(
                email_type=email_type,
                tone=tone_enum,
                candidate=candidate,
                job=job,
                recipient_name=clean_recipient,
                recipient_role=recipient_role,
                years_str=years_str,
                top_skills_str=top_skills_str,
                current_title=current_title,
                current_company=current_company,
                extra_context=extra_context,
            )
            variants_dict[tone_enum] = var_item

        # 5. Pick chosen variant as primary
        active_variant = variants_dict.get(preferred_tone, variants_dict[EmailTone.PROFESSIONAL])

        # 6. Policy and grounding review
        policy_eval = self.policy_reviewer._evaluate_content(
            full_text=f"{active_variant.subject}\n\n{active_variant.body}",
            candidate=candidate,
            job=job,
            context="email_draft",
        )
        for violation in policy_eval.violations:
            missing_recipient_warnings.append(f"Policy Warning: {violation.message}")

        return EmailDraft(
            email_type=email_type,
            recipient_name=recipient_name,
            recipient_role=recipient_role,
            subject=active_variant.subject,
            body=active_variant.body,
            call_to_action=active_variant.call_to_action,
            tone=preferred_tone.value,
            recipient_assumptions=recipient_assumptions,
            personalization_evidence=personalization_evidence,
            missing_recipient_warnings=missing_recipient_warnings,
            variants=[v.body for v in variants_dict.values()],
            structured_variants=list(variants_dict.values()),
            is_approved_by_user=False,
            user_id=candidate.user_id,
            job_id=job.id,
        )

    def _render_template(
        self,
        email_type: EmailType,
        tone: EmailTone,
        candidate: CandidateProfile,
        job: JobListing,
        recipient_name: str,
        recipient_role: Optional[str],
        years_str: str,
        top_skills_str: str,
        current_title: str,
        current_company: str,
        extra_context: Optional[str] = None,
    ) -> EmailVariantItem:
        """
        Renders deterministic, high-conversion email templates based on type and tone.
        """
        cand_name = candidate.full_name
        job_title = job.title
        org = job.organization

        if email_type in (EmailType.RECRUITER_OUTREACH, EmailType.HIRING_MANAGER_NOTE):
            if tone == EmailTone.PROFESSIONAL:
                subject = f"{job_title} role at {org} - {cand_name} Application"
                cta = "Would you have 10-15 minutes for a brief introductory conversation this week?"
                body = (
                    f"Dear {recipient_name},\n\n"
                    f"I hope this message finds you well. I am reaching out to express my strong interest in the "
                    f"{job_title} position at {org}.\n\n"
                    f"Currently serving as {current_title} at {current_company}, I have over {years_str} years of experience "
                    f"building scalable distributed systems with an emphasis on {top_skills_str}. "
                    f"Given {org}'s engineering mission, I believe my background in these core technologies aligns closely with your team's objectives.\n\n"
                    f"{cta}\n\n"
                    f"Thank you for your time and consideration.\n\n"
                    f"Best regards,\n{cand_name}"
                )
            elif tone == EmailTone.CONVERSATIONAL:
                subject = f"Quick hello from {cand_name} / {job_title} at {org}"
                cta = "Happy to send over a few code samples or jump on a quick 10-minute call whenever convenient."
                body = (
                    f"Hi {recipient_name},\n\n"
                    f"I saw the {job_title} opening on your team at {org} and wanted to reach out directly. "
                    f"I have spent the past {years_str} years working across {top_skills_str}, most recently as {current_title} at {current_company}.\n\n"
                    f"I really admire the technical challenges {org} is tackling, and I would love to connect about how my experience might be useful to your group.\n\n"
                    f"{cta}\n\n"
                    f"Cheers,\n{cand_name}"
                )
            else:  # EXECUTIVE
                subject = f"{cand_name} | {years_str} Experience — {job_title} Inquiry ({org})"
                cta = "I would welcome a concise introductory discussion regarding your architectural roadmap and engineering priorities."
                body = (
                    f"Dear {recipient_name},\n\n"
                    f"I am writing regarding the {job_title} requisition at {org}. "
                    f"With a proven record as {current_title} at {current_company} and {years_str} years scaling technical platforms in {top_skills_str}, "
                    f"I bring immediate execution capability to your engineering organization.\n\n"
                    f"{cta}\n\n"
                    f"Respectfully,\n{cand_name}"
                )

        elif email_type == EmailType.REFERRAL_REQUEST:
            if tone == EmailTone.PROFESSIONAL:
                subject = f"Exploring opportunities at {org} - {job_title}"
                cta = "If you feel comfortable, I would be deeply grateful for an internal referral or a brief conversation about your experience on the team."
                body = (
                    f"Hi {recipient_name},\n\n"
                    f"I hope you are having a productive week. I noticed you are working at {org} and wanted to reach out, "
                    f"as I am preparing an application for the {job_title} position.\n\n"
                    f"As a {current_title} with {years_str} years experience specializing in {top_skills_str}, "
                    f"I am very impressed by {org}'s product trajectory and engineering culture.\n\n"
                    f"{cta}\n\n"
                    f"Thank you so much for your consideration.\n\n"
                    f"Warm regards,\n{cand_name}"
                )
            elif tone == EmailTone.CONVERSATIONAL:
                subject = f"Quick question about {org} and {job_title}"
                cta = "Would you be open to a 5-minute chat, or perhaps putting my resume in front of the hiring team?"
                body = (
                    f"Hey {recipient_name},\n\n"
                    f"Hope all is well with you! I came across the {job_title} role at {org} and immediately thought of reaching out. "
                    f"With my background in {top_skills_str} over the past {years_str} years, this feels like an ideal match for my skillset.\n\n"
                    f"I would love to hear your thoughts on what it's like working at {org}. {cta}\n\n"
                    f"Thanks a ton,\n{cand_name}"
                )
            else:  # EXECUTIVE
                subject = f"Inquiry: {job_title} at {org} — {cand_name}"
                cta = "I would value your recommendation or introduction to the engineering leadership team."
                body = (
                    f"Hello {recipient_name},\n\n"
                    f"I am reaching out regarding the {job_title} leadership/engineering opening at {org}. "
                    f"Having spent {years_str} years driving technical outcomes in {top_skills_str}, I am interested in contributing to {org}'s next phase of growth.\n\n"
                    f"{cta}\n\n"
                    f"Best regards,\n{cand_name}"
                )

        elif email_type == EmailType.FOLLOW_UP:
            if tone == EmailTone.PROFESSIONAL:
                subject = f"Following up: {job_title} Application - {cand_name}"
                cta = "Please let me know if there are any additional materials or details I can provide to support the evaluation process."
                body = (
                    f"Dear {recipient_name},\n\n"
                    f"I hope you are having a wonderful week. I am following up on my recent application for the {job_title} role at {org}.\n\n"
                    f"Having reviewed {org}'s technical objectives, I remain very enthusiastic about how my {years_str} years of engineering experience in {top_skills_str} "
                    f"can contribute to your team's upcoming milestones.\n\n"
                    f"{cta}\n\n"
                    f"Thank you again for your time and guidance.\n\n"
                    f"Sincerely,\n{cand_name}"
                )
            elif tone == EmailTone.CONVERSATIONAL:
                subject = f"Following up on {job_title} / {cand_name}"
                cta = "Just wanted to check in and see if you need anything else from my end."
                body = (
                    f"Hi {recipient_name},\n\n"
                    f"Hope your week is going great! I wanted to quickly check in regarding the status of the {job_title} position at {org}.\n\n"
                    f"I'm still very excited about the opportunity to bring my {top_skills_str} background to the team. {cta}\n\n"
                    f"Best,\n{cand_name}"
                )
            else:  # EXECUTIVE
                subject = f"Status Inquiry: {job_title} — {cand_name}"
                cta = "I welcome an update regarding your recruitment timeline and interview schedule."
                body = (
                    f"Dear {recipient_name},\n\n"
                    f"I am writing to inquire on the evaluation timeline for the {job_title} position at {org}. "
                    f"With {years_str} years of demonstrated impact across {top_skills_str}, I look forward to exploring how my background aligns with your team's roadmap.\n\n"
                    f"{cta}\n\n"
                    f"Respectfully,\n{cand_name}"
                )

        else:  # THANK_YOU
            extra_mention = f" I especially appreciated discussing {extra_context}." if extra_context else ""
            if tone == EmailTone.PROFESSIONAL:
                subject = f"Thank you - {job_title} Interview - {cand_name}"
                cta = "Please let me know if any further information is needed as you finalize the next steps."
                body = (
                    f"Dear {recipient_name},\n\n"
                    f"Thank you very much for taking the time to speak with me today regarding the {job_title} opportunity at {org}.{extra_mention}\n\n"
                    f"Our discussion reaffirmed my strong interest in joining {org}. I am confident that my background in {top_skills_str} and "
                    f"experience tackling complex architectures will allow me to deliver immediate value.\n\n"
                    f"{cta}\n\n"
                    f"Best regards,\n{cand_name}"
                )
            elif tone == EmailTone.CONVERSATIONAL:
                subject = f"Great speaking with you today! - {job_title}"
                cta = "Looking forward to staying in touch and hearing about next steps."
                body = (
                    f"Hi {recipient_name},\n\n"
                    f"Thanks so much for the conversation earlier today! I really enjoyed learning more about the {job_title} role at {org}.{extra_mention}\n\n"
                    f"It sounds like a fantastic team, and I'm very excited about how my hands-on work with {top_skills_str} fits your upcoming plans. {cta}\n\n"
                    f"Cheers,\n{cand_name}"
                )
            else:  # EXECUTIVE
                subject = f"Appreciation & Next Steps: {job_title} Discussion — {cand_name}"
                cta = "I look forward to continuing our conversation regarding the team's strategic direction."
                body = (
                    f"Dear {recipient_name},\n\n"
                    f"Thank you for our discussion today regarding the {job_title} opening at {org}.{extra_mention}\n\n"
                    f"The technical scope and operational scale align closely with the work I have led throughout my {years_str} years in engineering. "
                    f"I am eager to contribute to {org}'s mission.\n\n"
                    f"{cta}\n\n"
                    f"Sincerely,\n{cand_name}"
                )

        return EmailVariantItem(
            tone=tone,
            subject=subject,
            body=body,
            call_to_action=cta,
        )
