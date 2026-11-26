import hashlib
import logging
import re
import uuid
from typing import Dict, List, Optional, Set, Tuple

from packages.contracts.base import utc_now
from packages.contracts.job import (
    JobListing,
    JobSeniority,
    NormalizationSummary,
    RawJobPayload,
    WorkMode,
)

logger = logging.getLogger("agentflow.normalizer")

# Technical skills taxonomy categorized for precision extraction
SKILLS_TAXONOMY: Dict[str, List[str]] = {
    "languages": [
        "Python", "TypeScript", "JavaScript", "Go", "Rust", "Java", "C++", "C#",
        "Ruby", "Swift", "Kotlin", "PHP", "Scala", "SQL", "Bash", "R",
    ],
    "web_frameworks": [
        "React", "Next.js", "FastAPI", "Django", "Flask", "Node.js", "Express",
        "Angular", "Vue", "Spring", "Rails", "Tailwind CSS", "GraphQL", "REST", "gRPC",
    ],
    "cloud_devops": [
        "AWS", "GCP", "Azure", "Docker", "Kubernetes", "Terraform", "CI/CD",
        "Linux", "Helm", "Ansible", "GitHub Actions", "Prometheus", "Grafana",
    ],
    "data_storage": [
        "PostgreSQL", "MySQL", "Redis", "MongoDB", "Elasticsearch", "Snowflake",
        "DynamoDB", "Cassandra", "Kafka", "pgvector", "SQLite",
    ],
    "ai_ml": [
        "PyTorch", "TensorFlow", "Scikit-Learn", "Ray", "Pandas", "NumPy",
        "Apache Spark", "Hugging Face", "LLMs", "NLP", "LangChain", "LangGraph",
    ],
    "architecture": [
        "Distributed Systems", "Microservices", "System Design", "Event-Driven",
        "High-Throughput", "Observability", "Zero Trust",
    ],
}

ALL_KNOWN_SKILLS: List[str] = [
    skill for group in SKILLS_TAXONOMY.values() for skill in group
]

# Patterns for corporate legal entity suffixes
CORP_SUFFIX_PATTERN = re.compile(
    r"\b(inc\.?|llc|ltd\.?|corp\.?|corporation|technologies|tech|solutions|co\.?|group|holdings|gmbh|pty|s\.a\.)\b",
    re.IGNORECASE,
)

# Patterns for title annotations and requisition tags
TITLE_NOISE_PATTERN = re.compile(
    r"(\((?:req|id|job id|req id|ref|requisition)[\s#:]*[\w-]+\)|\[[^\]]*\]|\((?:remote|hybrid|onsite|worldwide|anywhere|m/f/d|m/w/d|full[\s-]?time|part[\s-]?time)\))",
    re.IGNORECASE,
)


class JobNormalizerService:
    """
    Job Normalization and Cross-Source Deduplication Engine.
    Responsibilities:
      - Title & Organization normalization to canonical forms.
      - Automated rule-based inference of Work Mode, Seniority, Salary bounds, and Skills.
      - SHA-256 tamper-evident content hashing.
      - Cross-source deduplication and multi-source linking.
    """

    @classmethod
    def normalize_organization(cls, org_raw: str) -> str:
        """Strip corporate legal suffixes, company board tags, and trailing punctuation."""
        if not org_raw:
            return "Confidential"

        cleaned = org_raw.strip()
        # Remove board artifacts like "company-inc" or "company - NY"
        cleaned = re.split(r"[-–—|/]", cleaned)[0].strip()
        # Remove corporate entity suffixes
        cleaned = CORP_SUFFIX_PATTERN.sub("", cleaned).strip()
        # Remove trailing commas, periods
        cleaned = re.sub(r"[,.\s]+$", "", cleaned).strip()

        return cleaned if cleaned else org_raw.strip()

    @classmethod
    def normalize_title(cls, title_raw: str) -> str:
        """Strip requisition codes, locations in parens, and normalize standard abbreviations."""
        if not title_raw:
            return "Software Engineer"

        cleaned = TITLE_NOISE_PATTERN.sub("", title_raw).strip()
        # Normalize common abbreviations
        cleaned = re.sub(r"\bSr\.?\s+", "Senior ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bJr\.?\s+", "Junior ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bDev\b", "Developer", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bEng\b", "Engineer", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bMgr\b", "Manager", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        return cleaned if cleaned else title_raw.strip()

    @classmethod
    def infer_work_mode(
        cls,
        text: str,
        location_raw: Optional[str] = None,
        work_mode_raw: Optional[str] = None,
    ) -> WorkMode:
        """Accurately infer remote, hybrid, or onsite work mode from text and metadata."""
        if work_mode_raw:
            w_lower = work_mode_raw.lower().strip()
            if "remote" in w_lower:
                return WorkMode.REMOTE
            elif "hybrid" in w_lower:
                return WorkMode.HYBRID
            elif "onsite" in w_lower or "on-site" in w_lower:
                return WorkMode.ONSITE

        searchable = f"{location_raw or ''} {text[:1000]}".lower()

        # Hybrid detection
        if any(h in searchable for h in ["hybrid", "flexible working", "days remote", "in-office / remote"]):
            return WorkMode.HYBRID

        # Remote detection
        if any(r in searchable for r in ["remote", "worldwide", "anywhere", "work from home", "wfh", "100% remote", "virtual"]):
            return WorkMode.REMOTE

        # Onsite detection
        if any(o in searchable for o in ["onsite", "on-site", "in-person", "office-based", "in office"]):
            return WorkMode.ONSITE

        return WorkMode.UNKNOWN

    @classmethod
    def infer_seniority(
        cls,
        title: str,
        description: str,
        seniority_raw: Optional[str] = None,
    ) -> JobSeniority:
        """Infer seniority level from title keywords and experience requirements."""
        if seniority_raw:
            s_raw = seniority_raw.lower().strip()
            for enum_val in JobSeniority:
                if enum_val.value == s_raw:
                    return enum_val

        t_lower = title.lower()

        if any(k in t_lower for k in ["executive", "chief", "cto", "cio", "cpo", "vice president", "vp", "head of"]):
            return JobSeniority.EXECUTIVE
        if "director" in t_lower:
            return JobSeniority.DIRECTOR
        if any(k in t_lower for k in ["principal", "distinguished", "fellow"]):
            return JobSeniority.PRINCIPAL
        if "staff" in t_lower:
            return JobSeniority.STAFF
        if any(k in t_lower for k in ["lead", "tech lead", "team lead", "architect"]):
            return JobSeniority.LEAD
        if any(k in t_lower for k in ["senior", "sr", " iii", " iv", "level 5", "level 6", "l5", "l6"]):
            return JobSeniority.SENIOR
        if any(k in t_lower for k in ["junior", "jr", "entry", "associate", "graduate", "intern", "apprentice"]):
            return JobSeniority.ENTRY
        if any(k in t_lower for k in ["mid", "intermediate", " ii", "level 3", "level 4", "l3", "l4"]):
            return JobSeniority.MID

        # Infer from years mentioned in requirements
        exp_match = re.search(r"(\d+)\+?\s*years?\s+(?:of\s+)?experience", description[:2500], re.IGNORECASE)
        if exp_match:
            try:
                years = int(exp_match.group(1))
                if years >= 8:
                    return JobSeniority.STAFF
                elif years >= 5:
                    return JobSeniority.SENIOR
                elif years >= 2:
                    return JobSeniority.MID
                else:
                    return JobSeniority.ENTRY
            except ValueError:
                pass

        return JobSeniority.UNSPECIFIED

    @classmethod
    def extract_salary(
        cls,
        salary_raw: Optional[str],
        description: str,
    ) -> Tuple[Optional[int], Optional[int], str]:
        """
        Extract numerical salary bounds (min, max) and currency.
        Handles $140k-$180k, $150,000 - $200,000 USD, £80,000, €90k, etc.
        """
        target_text = salary_raw if salary_raw else description[:2500]

        currency = "USD"
        if "£" in target_text or "GBP" in target_text:
            currency = "GBP"
        elif "€" in target_text or "EUR" in target_text:
            currency = "EUR"
        elif "CAD" in target_text:
            currency = "CAD"

        # Pattern 1: $150,000 - $200,000 or $150k - $200k
        range_match = re.search(
            r"[\$£€]?\s*(\d{2,3}(?:,\d{3})*|\d{2,3})\s*(k)?\s*(?:-|to|–|—)\s*[\$£€]?\s*(\d{2,3}(?:,\d{3})*|\d{2,3})\s*(k)?",
            target_text,
            re.IGNORECASE,
        )
        if range_match:
            min_str, min_k, max_str, max_k = range_match.groups()
            sal_min = int(min_str.replace(",", ""))
            sal_max = int(max_str.replace(",", ""))
            if min_k or sal_min < 1000:
                sal_min *= 1000
            if max_k or sal_max < 1000:
                sal_max *= 1000
            return sal_min, sal_max, currency

        # Pattern 2: Single figure (e.g. "From $140,000" or "$150k")
        single_match = re.search(
            r"[\$£€]\s*(\d{2,3}(?:,\d{3})*|\d{2,3})\s*(k)?",
            target_text,
            re.IGNORECASE,
        )
        if single_match:
            val_str, is_k = single_match.groups()
            val = int(val_str.replace(",", ""))
            if is_k or val < 1000:
                val *= 1000
            return val, val, currency

        return None, None, currency

    @classmethod
    def extract_skills(
        cls,
        text: str,
        extra_tags: Optional[List[str]] = None,
    ) -> Tuple[List[str], List[str]]:
        """
        Extract required and preferred technical skills using taxonomy matching.
        Differentiates between core requirements and nice-to-have qualifications.
        """
        req_skills: Set[str] = set()
        pref_skills: Set[str] = set()

        # Add explicit tags if provided
        if extra_tags:
            for tag in extra_tags:
                tag.strip().title()
                for skill in ALL_KNOWN_SKILLS:
                    if skill.lower() == tag.lower():
                        req_skills.add(skill)

        # Split into requirements and preferred sections if present
        pref_split = re.split(r"(preferred qualifications|nice to have|bonus points|preferred skills|plus:)", text, flags=re.IGNORECASE)
        req_text = pref_split[0]
        pref_text = pref_split[1] + pref_split[2] if len(pref_split) > 2 else ""

        for skill in ALL_KNOWN_SKILLS:
            # Word boundary regex to avoid false positives (e.g., "Go" in "Good")
            pattern = rf"(?<!\w){re.escape(skill)}(?!\w)"
            if re.search(pattern, req_text, re.IGNORECASE):
                req_skills.add(skill)
            elif pref_text and re.search(pattern, pref_text, re.IGNORECASE):
                pref_skills.add(skill)

        return sorted(req_skills), sorted(pref_skills - req_skills)

    @classmethod
    def compute_content_hash(cls, organization: str, title: str, description_text: str) -> str:
        """
        Compute deterministic SHA-256 content hash of normalized job attributes.
        Provides tamper-evidence and idempotent deduplication identity.
        """
        norm_org = organization.lower().strip()
        norm_title = title.lower().strip()
        norm_desc = re.sub(r"\s+", " ", description_text.lower().strip())
        canonical_repr = f"{norm_org}|{norm_title}|{norm_desc[:2000]}"
        return hashlib.sha256(canonical_repr.encode("utf-8")).hexdigest()

    @classmethod
    def normalize_payload(cls, raw: RawJobPayload) -> JobListing:
        """Transform a raw adapter payload into a fully normalized, typed JobListing contract."""
        norm_org = cls.normalize_organization(raw.organization)
        norm_title = cls.normalize_title(raw.title)
        clean_desc = re.sub(r"\s+", " ", raw.description_raw).strip()

        work_mode = cls.infer_work_mode(
            text=clean_desc,
            location_raw=raw.location_raw,
            work_mode_raw=raw.work_mode_raw,
        )

        seniority = cls.infer_seniority(
            title=norm_title,
            description=clean_desc,
            seniority_raw=raw.seniority_raw,
        )

        sal_min, sal_max, currency = cls.extract_salary(
            salary_raw=raw.salary_raw,
            description=clean_desc,
        )

        extra_tags = raw.extra_metadata.get("tags") if raw.extra_metadata else None
        skills_req, skills_pref = cls.extract_skills(f"{norm_title}\n{clean_desc}", extra_tags=extra_tags)

        content_hash = cls.compute_content_hash(
            organization=norm_org,
            title=norm_title,
            description_text=clean_desc,
        )

        location = raw.location_raw.strip() if raw.location_raw else "Remote / Flexible"

        return JobListing(
            id=f"job_{uuid.uuid4().hex[:10]}",
            title=norm_title,
            organization=norm_org,
            location=location,
            work_mode=work_mode,
            seniority=seniority,
            salary_min=sal_min,
            salary_max=sal_max,
            salary_currency=currency,
            skills_required=skills_req,
            skills_preferred=skills_pref,
            description_text=clean_desc,
            description_html=raw.description_html,
            application_method="url",
            destination_url=raw.destination_url,
            source_name=raw.source_name,
            source_url=raw.source_url,
            content_hash=content_hash,
            retrieved_at=raw.retrieved_at or utc_now(),
            posted_at=raw.posted_at,
            is_active=True,
            alternate_sources=[],
            extra_metadata=dict(raw.extra_metadata or {}),
        )

    @classmethod
    def deduplicate_and_link(
        cls,
        listings: List[JobListing],
    ) -> Tuple[List[JobListing], int, int]:
        """
        Cross-source deduplication and linking algorithm.
        Identifies exact content hash duplicates AND cross-source multi-postings:
          - Same normalized organization
          - High title token similarity (> 70%)
          - Compatible location or both remote
        Consolidates duplicates by attaching alternate sources to the canonical listing.
        Returns: (unique_canonical_listings, duplicates_detected_count, cross_source_links_count)
        """
        canonical_map: Dict[str, JobListing] = {}
        unique_listings: List[JobListing] = []
        duplicates_count = 0
        cross_source_links = 0

        for listing in listings:
            # 1. Exact Content Hash Match
            if listing.content_hash in canonical_map:
                canonical = canonical_map[listing.content_hash]
                duplicates_count += 1
                cls._link_alternate_source(canonical, listing)
                cross_source_links += 1
                continue

            # 2. Cross-Source Semantic Fuzzy Match
            matched_canonical = None
            for existing in unique_listings:
                if cls._is_cross_source_duplicate(existing, listing):
                    matched_canonical = existing
                    break

            if matched_canonical:
                duplicates_count += 1
                cls._link_alternate_source(matched_canonical, listing)
                cross_source_links += 1
            else:
                canonical_map[listing.content_hash] = listing
                unique_listings.append(listing)

        return unique_listings, duplicates_count, cross_source_links

    @classmethod
    def _is_cross_source_duplicate(cls, job_a: JobListing, job_b: JobListing) -> bool:
        """Check if two listings from potentially different sources represent the same job."""
        # 1. Organizations must match
        if job_a.organization.lower() != job_b.organization.lower():
            return False

        # 2. Location compatibility (if both remote or same location)
        both_remote = (job_a.work_mode == WorkMode.REMOTE and job_b.work_mode == WorkMode.REMOTE)
        same_loc = (job_a.location.lower() in job_b.location.lower() or job_b.location.lower() in job_a.location.lower())
        if not (both_remote or same_loc):
            return False

        # 3. Title token Jaccard similarity
        tokens_a = set(re.findall(r"\w+", job_a.title.lower()))
        tokens_b = set(re.findall(r"\w+", job_b.title.lower()))
        if not tokens_a or not tokens_b:
            return False

        intersection = len(tokens_a & tokens_b)
        union = len(tokens_a | tokens_b)
        jaccard = intersection / union if union > 0 else 0.0

        return jaccard >= 0.70 or tokens_a.issubset(tokens_b) or tokens_b.issubset(tokens_a)

    @classmethod
    def _link_alternate_source(cls, canonical: JobListing, duplicate: JobListing) -> None:
        """Record the duplicate source information on the canonical record."""
        source_entry = {
            "source_name": duplicate.source_name,
            "source_url": duplicate.source_url,
            "destination_url": duplicate.destination_url,
            "retrieved_at": duplicate.retrieved_at.isoformat(),
        }
        # Prevent appending identical source multiple times
        if not any(
            s.get("source_url") == duplicate.source_url and s.get("source_name") == duplicate.source_name
            for s in canonical.alternate_sources
        ):
            canonical.alternate_sources.append(source_entry)

    @classmethod
    def normalize_and_deduplicate(
        cls,
        raw_payloads: List[RawJobPayload],
    ) -> Tuple[List[JobListing], NormalizationSummary]:
        """
        End-to-end normalization pipeline:
          RawJobPayload[] -> Normalize -> Deduplicate & Link -> JobListing[] + Telemetry
        """
        normalized_initial = [cls.normalize_payload(raw) for raw in raw_payloads]
        unique_jobs, dup_count, cross_links = cls.deduplicate_and_link(normalized_initial)

        summary = NormalizationSummary(
            total_raw=len(raw_payloads),
            total_unique=len(unique_jobs),
            duplicates_detected=dup_count,
            cross_source_links=cross_links,
            processed_at=utc_now(),
        )

        return unique_jobs, summary
