import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from packages.contracts.base import utc_now
from packages.contracts.job import JobListing, JobSeniority, WorkMode
from packages.contracts.match import (
    MatchExplanation,
    RequirementMatch,
    ScoreBreakdown,
)
from packages.contracts.profile import CandidateProfile, WorkModePreference

logger = logging.getLogger("agentflow.matcher")

DEFAULT_WEIGHTS: Dict[str, float] = {
    "skills": 0.35,
    "seniority": 0.20,
    "location_mode": 0.15,
    "salary": 0.15,
    "sector": 0.10,
    "recency": 0.05,
}

SENIORITY_YEARS_MAP: Dict[JobSeniority, Tuple[float, float]] = {
    JobSeniority.ENTRY: (0.0, 2.0),
    JobSeniority.MID: (2.0, 5.0),
    JobSeniority.SENIOR: (5.0, 8.0),
    JobSeniority.LEAD: (7.0, 10.0),
    JobSeniority.STAFF: (8.0, 12.0),
    JobSeniority.PRINCIPAL: (10.0, 25.0),
    JobSeniority.DIRECTOR: (10.0, 25.0),
    JobSeniority.EXECUTIVE: (12.0, 30.0),
    JobSeniority.UNSPECIFIED: (0.0, 40.0),
}


class MatchRankingService:
    """
    Explainable Multi-Dimensional Match & Ranking Engine.
    Evaluates candidate profiles against normalized job listings across 6 explicit dimensions:
      1. Technical Skills Match (35%)
      2. Seniority & Experience Alignment (20%)
      3. Location & Work Mode Fit (15%)
      4. Compensation & Salary Alignment (15%)
      5. Industry Sector Preference (10%)
      6. Posting Recency (5%)

    Guarantees:
      - 100% transparent score breakdowns (no opaque black-box numbers).
      - Explicit strengths, gaps, and uncertainties enumeration.
      - Safety check: NEVER claims strong_match when critical information is missing.
    """

    @classmethod
    def evaluate_match(
        cls,
        candidate: CandidateProfile,
        job: JobListing,
        custom_weights: Optional[Dict[str, float]] = None,
    ) -> MatchExplanation:
        """
        Evaluate candidate profile against a job listing and generate an explainable MatchExplanation.
        """
        weights = dict(custom_weights or DEFAULT_WEIGHTS)
        strengths: List[str] = []
        gaps: List[str] = []
        uncertainties: List[str] = []
        matched_requirements: List[RequirementMatch] = []

        # 1. Skills Matching
        skill_score, skill_matches, skill_strengths, skill_gaps = cls._score_skills(candidate, job)
        matched_requirements.extend(skill_matches)
        strengths.extend(skill_strengths)
        gaps.extend(skill_gaps)

        # 2. Seniority Matching
        seniority_score, sen_strengths, sen_gaps = cls._score_seniority(candidate, job)
        strengths.extend(sen_strengths)
        gaps.extend(sen_gaps)

        # 3. Location & Work Mode Matching
        loc_score, loc_strengths, loc_gaps = cls._score_location_and_mode(candidate, job)
        strengths.extend(loc_strengths)
        gaps.extend(loc_gaps)

        # 4. Salary Alignment
        salary_score, sal_strengths, sal_gaps, sal_uncertainties = cls._score_salary(candidate, job)
        strengths.extend(sal_strengths)
        gaps.extend(sal_gaps)
        uncertainties.extend(sal_uncertainties)

        # 5. Work Authorization Check
        work_auth_score, auth_strengths, auth_gaps, auth_uncertainties = cls._score_work_authorization(candidate, job)
        strengths.extend(auth_strengths)
        gaps.extend(auth_gaps)
        uncertainties.extend(auth_uncertainties)

        # 6. Sector / Industry Preference
        sector_score, sec_strengths, sec_gaps = cls._score_sector(candidate, job)
        strengths.extend(sec_strengths)
        gaps.extend(sec_gaps)

        # 7. Recency Score
        recency_score = cls._score_recency(job)

        # Dynamic weight normalization across available dimensions
        active_dimensions: Dict[str, Tuple[float, float]] = {
            "skills": (weights["skills"], skill_score),
            "seniority": (weights["seniority"], seniority_score),
            "location_mode": (weights["location_mode"], loc_score),
            "work_auth": (0.05, work_auth_score),
            "sector": (weights["sector"], sector_score),
            "recency": (weights["recency"], recency_score),
        }

        if salary_score is not None:
            active_dimensions["salary"] = (weights["salary"], salary_score)

        total_weight = sum(w for w, _ in active_dimensions.values())
        weighted_sum = sum(w * s for w, s in active_dimensions.values())
        composite = round(weighted_sum / total_weight, 1)

        # Critical Missing Information Safety Check
        has_critical_gap = (
            not candidate.work_authorization
            or (candidate.total_years_experience is None)
            or (loc_score <= 10.0)
            or (work_auth_score <= 20.0)
        )

        # Determine Recommendation
        if composite >= 80.0 and not has_critical_gap:
            recommendation = "strong_match"
        elif composite >= 65.0:
            recommendation = "potential_match"
        elif composite >= 45.0:
            recommendation = "gap_heavy"
        else:
            recommendation = "not_recommended"

        if not candidate.work_authorization:
            uncertainties.append("Candidate work authorization is unconfirmed; matching confidence reduced.")

        score_breakdown = ScoreBreakdown(
            skill_match_score=round(skill_score, 1),
            seniority_score=round(seniority_score, 1),
            location_mode_score=round(loc_score, 1),
            salary_alignment_score=round(salary_score, 1) if salary_score is not None else None,
            work_authorization_score=round(work_auth_score, 1),
            recency_score=round(recency_score, 1),
            industry_preference_score=round(sector_score, 1),
            composite_score=composite,
        )

        return MatchExplanation(
            candidate_id=candidate.id or candidate.user_id,
            job_id=job.id or job.content_hash,
            composite_score=composite,
            score_breakdown=score_breakdown,
            strengths=strengths,
            gaps=gaps,
            uncertainties=uncertainties,
            matched_requirements=matched_requirements,
            recommendation=recommendation,
            user_decision=None,
        )

    @classmethod
    def rank_jobs(
        cls,
        candidate: CandidateProfile,
        jobs: List[JobListing],
        min_score: float = 0.0,
        limit: int = 20,
    ) -> List[Tuple[JobListing, MatchExplanation]]:
        """
        Rank a list of job listings against a candidate profile, sorted by composite score descending.
        """
        evaluated: List[Tuple[JobListing, MatchExplanation]] = []
        for job in jobs:
            explanation = cls.evaluate_match(candidate, job)
            if explanation.composite_score >= min_score:
                evaluated.append((job, explanation))

        # Sort by composite score descending, then by recency descending
        evaluated.sort(
            key=lambda item: (item[1].composite_score, item[1].score_breakdown.recency_score),
            reverse=True,
        )
        return evaluated[:limit]

    # -------------------------------------------------------------------------
    # Dimension Scoring Helpers
    # -------------------------------------------------------------------------

    @classmethod
    def _score_skills(
        cls, candidate: CandidateProfile, job: JobListing
    ) -> Tuple[float, List[RequirementMatch], List[str], List[str]]:
        candidate_skills = {s.name.lower(): s for s in candidate.skills}
        req_skills = job.skills_required or []
        pref_skills = job.skills_preferred or []

        if not req_skills and not pref_skills:
            return 85.0, [], ["No specific technical skills strictly required"], []

        matches: List[RequirementMatch] = []
        strengths: List[str] = []
        gaps: List[str] = []

        satisfied_req = 0
        for skill in req_skills:
            s_lower = skill.lower()
            if s_lower in candidate_skills:
                satisfied_req += 1
                cand_item = candidate_skills[s_lower]
                matches.append(
                    RequirementMatch(
                        requirement=f"Required skill: {skill}",
                        is_satisfied=True,
                        evidence_or_gap_explanation=f"Candidate verified expertise in {skill}",
                        candidate_skill_or_exp=skill,
                    )
                )
                strengths.append(f"Possesses core required skill: {skill}")
            else:
                matches.append(
                    RequirementMatch(
                        requirement=f"Required skill: {skill}",
                        is_satisfied=False,
                        evidence_or_gap_explanation=f"Missing required skill: {skill}",
                        candidate_skill_or_exp=None,
                    )
                )
                gaps.append(f"Lacks required skill: {skill}")

        satisfied_pref = 0
        for skill in pref_skills:
            s_lower = skill.lower()
            if s_lower in candidate_skills:
                satisfied_pref += 1
                strengths.append(f"Possesses preferred skill: {skill}")

        # Core requirements carry double weight
        total_pts = (len(req_skills) * 2.0) + (len(pref_skills) * 1.0)
        earned_pts = (satisfied_req * 2.0) + (satisfied_pref * 1.0)
        score = (earned_pts / total_pts * 100.0) if total_pts > 0 else 85.0

        return max(0.0, min(100.0, score)), matches, strengths, gaps

    @classmethod
    def _score_seniority(
        cls, candidate: CandidateProfile, job: JobListing
    ) -> Tuple[float, List[str], List[str]]:
        cand_years = candidate.total_years_experience or 0.0
        job_sen = job.seniority or JobSeniority.UNSPECIFIED
        min_years, max_years = SENIORITY_YEARS_MAP.get(job_sen, (0.0, 40.0))

        if job_sen == JobSeniority.UNSPECIFIED:
            return 85.0, [], []

        if min_years <= cand_years <= max_years:
            return 100.0, [f"Experience level ({cand_years:.1f} yrs) aligns with {job_sen.value} seniority"], []

        # Underqualified case
        if cand_years < min_years:
            gap_years = min_years - cand_years
            if gap_years <= 1.5:
                return 75.0, [], [f"Slightly below target seniority ({cand_years:.1f} yrs vs {min_years:.0f}+ yrs required)"]
            elif gap_years <= 3.0:
                return 50.0, [], [f"Below target seniority ({cand_years:.1f} yrs vs {min_years:.0f}+ yrs required)"]
            else:
                return 25.0, [], [f"Significantly under target seniority ({cand_years:.1f} yrs vs {min_years:.0f}+ yrs)"]

        # Overqualified case
        if cand_years > max_years:
            return 90.0, [f"Candidate exceeds target seniority range ({cand_years:.1f} yrs vs {max_years:.0f} max)"], []

        return 80.0, [], []

    @classmethod
    def _score_location_and_mode(
        cls, candidate: CandidateProfile, job: JobListing
    ) -> Tuple[float, List[str], List[str]]:
        cand_modes = candidate.work_modes or [WorkModePreference.REMOTE]
        cand_loc = (candidate.primary_location or "").lower()
        job_loc = (job.location or "").lower()

        # Job is Remote
        if job.work_mode == WorkMode.REMOTE or "remote" in job_loc:
            if any(m in [WorkModePreference.REMOTE, WorkModePreference.ANY] for m in cand_modes):
                return 100.0, ["Matches candidate's preference for Remote work"], []
            return 80.0, ["Remote role available, but candidate preferred Onsite"], []

        # Job is Hybrid
        if job.work_mode == WorkMode.HYBRID or "hybrid" in job_loc:
            loc_match = any(token in job_loc for token in re.findall(r"\w+", cand_loc) if len(token) > 2)
            if any(m in [WorkModePreference.HYBRID, WorkModePreference.ANY] for m in cand_modes) and loc_match:
                return 100.0, ["Hybrid work mode and office location match candidate"], []
            elif loc_match:
                return 70.0, [], ["Role is Hybrid in candidate's city, but candidate preferred Remote only"]
            return 30.0, [], [f"Hybrid role requires in-person presence in {job.location}, mismatching {candidate.primary_location}"]

        # Job is Onsite
        if job.work_mode == WorkMode.ONSITE or "onsite" in job_loc or "on-site" in job_loc:
            loc_match = any(token in job_loc for token in re.findall(r"\w+", cand_loc) if len(token) > 2)
            if any(m in [WorkModePreference.ONSITE, WorkModePreference.ANY] for m in cand_modes) and loc_match:
                return 100.0, ["Onsite role in candidate's city"], []
            elif loc_match:
                return 50.0, [], ["Onsite role in candidate's city, but candidate preferred Remote work"]
            return 10.0, [], [f"Onsite role in {job.location} requires relocation from {candidate.primary_location}"]

        return 80.0, [], []

    @classmethod
    def _score_salary(
        cls, candidate: CandidateProfile, job: JobListing
    ) -> Tuple[Optional[float], List[str], List[str], List[str]]:
        target_min = candidate.target_salary_min
        job_max = job.salary_max
        job_min = job.salary_min

        if not target_min or not job_max:
            uncertainties = []
            if not job_max:
                uncertainties.append("Job posting does not disclose explicit salary compensation")
            return None, [], [], uncertainties

        if job_max >= target_min:
            strengths = [f"Salary range (${job_min or job_max:,} - ${job_max:,}) meets candidate target (${target_min:,})"]
            return 100.0, strengths, [], []

        # Under candidate target
        diff = target_min - job_max
        ratio = job_max / target_min
        score = max(10.0, round(ratio * 100.0, 1))
        gaps = [f"Job maximum salary (${job_max:,}) is below candidate target (${target_min:,}) by ${diff:,}"]
        return score, [], gaps, []

    @classmethod
    def _score_work_authorization(
        cls, candidate: CandidateProfile, job: JobListing
    ) -> Tuple[float, List[str], List[str], List[str]]:
        if not candidate.work_authorization:
            return 70.0, [], [], ["Candidate work authorization status is unspecified"]

        auth = candidate.work_authorization.lower()
        if "citizen" in auth or "permanent resident" in auth or "green card" in auth:
            return 100.0, ["Work authorization fully satisfied (Citizen/PR)"], [], []
        elif "authorized" in auth:
            return 90.0, ["Authorized to work"], [], []
        elif "sponsorship" in auth:
            # Check if job mentions sponsorship
            job_desc = job.description_text.lower()
            if "sponsor" in job_desc and "no sponsor" not in job_desc:
                return 90.0, ["Role offers or considers visa sponsorship"], [], []
            elif "no sponsor" in job_desc or "cannot sponsor" in job_desc:
                return 15.0, [], ["Job specifies no visa sponsorship, conflicting with candidate's status"], []
            return 60.0, [], [], ["Role does not specify whether visa sponsorship is supported"]

        return 75.0, [], [], []

    @classmethod
    def _score_sector(
        cls, candidate: CandidateProfile, job: JobListing
    ) -> Tuple[float, List[str], List[str]]:
        preferred = candidate.preferred_sectors or []
        if not preferred:
            return 85.0, [], []

        extra_meta = getattr(job, "extra_metadata", None) or {}
        job_sector = extra_meta.get("sector") if isinstance(extra_meta, dict) else None
        job_text = f"{job.title} {job.organization} {job.description_text} {job_sector or ''}".lower()

        for sec in preferred:
            if sec.lower() in job_text:
                return 100.0, [f"Matches preferred industry sector: {sec}"], []

        return 50.0, [], []

    @classmethod
    def _score_recency(cls, job: JobListing) -> float:
        posted = job.posted_at or job.retrieved_at or utc_now()
        now = utc_now()
        if posted.tzinfo is None:
            posted = posted.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (now - posted).total_seconds() / 86400.0)

        if age_days <= 3.0:
            return 100.0
        elif age_days <= 7.0:
            return 90.0
        elif age_days <= 14.0:
            return 75.0
        elif age_days <= 30.0:
            return 50.0
        return 25.0
