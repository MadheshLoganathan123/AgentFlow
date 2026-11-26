import pytest
from fastapi.testclient import TestClient

from packages.contracts.base import utc_now
from packages.contracts.job import (
    JobSeniority,
    RawJobPayload,
    WorkMode,
)
from services.api.main import app
from services.api.services.normalizer import JobNormalizerService


@pytest.fixture
def test_client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Organization & Title Normalization Tests
# ---------------------------------------------------------------------------


def test_normalize_organization():
    """Verify stripping of corporate suffixes, board hyphens, and legal entities."""
    assert JobNormalizerService.normalize_organization("Stripe, Inc.") == "Stripe"
    assert JobNormalizerService.normalize_organization("Datadog LLC") == "Datadog"
    assert JobNormalizerService.normalize_organization("Vercel - Developer Tools") == "Vercel"
    assert JobNormalizerService.normalize_organization("Flatiron Health, Corp.") == "Flatiron Health"
    assert JobNormalizerService.normalize_organization("OpenAI, Ltd.") == "OpenAI"
    assert JobNormalizerService.normalize_organization("Plaid Technologies") == "Plaid"
    assert JobNormalizerService.normalize_organization("") == "Confidential"


def test_normalize_title():
    """Verify stripping of requisition codes, brackets, and standardizing abbreviations."""
    assert JobNormalizerService.normalize_title("Sr. Backend Engineer") == "Senior Backend Engineer"
    assert JobNormalizerService.normalize_title("Jr. Web Dev (Remote)") == "Junior Web Developer"
    assert JobNormalizerService.normalize_title("Lead Platform Eng [Req #8892]") == "Lead Platform Engineer"
    assert JobNormalizerService.normalize_title("Staff Software Engineer (m/f/d)") == "Staff Software Engineer"
    assert JobNormalizerService.normalize_title("Eng Mgr - Core Platform") == "Engineer Manager - Core Platform"


# ---------------------------------------------------------------------------
# Work Mode & Seniority Inference Tests
# ---------------------------------------------------------------------------


def test_infer_work_mode():
    """Verify accurate inference across remote, hybrid, and onsite."""
    assert JobNormalizerService.infer_work_mode("100% remote developer role", "Worldwide") == WorkMode.REMOTE
    assert JobNormalizerService.infer_work_mode("Hybrid position 2 days in office", "New York, NY") == WorkMode.HYBRID
    assert JobNormalizerService.infer_work_mode("On-site role, relocation required", "Austin, TX") == WorkMode.ONSITE
    assert JobNormalizerService.infer_work_mode("Role details below", "Unknown") == WorkMode.UNKNOWN
    # Explicit override takes precedence
    assert JobNormalizerService.infer_work_mode("Flexible work", work_mode_raw="remote") == WorkMode.REMOTE


def test_infer_seniority():
    """Verify seniority classification from titles and experience statements."""
    assert JobNormalizerService.infer_seniority("Senior Backend Developer", "") == JobSeniority.SENIOR
    assert JobNormalizerService.infer_seniority("Staff Platform Engineer", "") == JobSeniority.STAFF
    assert JobNormalizerService.infer_seniority("Principal Systems Architect", "") == JobSeniority.PRINCIPAL
    assert JobNormalizerService.infer_seniority("Lead DevOps Engineer", "") == JobSeniority.LEAD
    assert JobNormalizerService.infer_seniority("Junior Frontend Developer", "") == JobSeniority.ENTRY
    assert JobNormalizerService.infer_seniority("VP of Engineering", "") == JobSeniority.EXECUTIVE
    # Infer from years of experience in description
    assert (
        JobNormalizerService.infer_seniority(
            "Software Engineer",
            "Must have at least 6 years of experience in distributed systems.",
        )
        == JobSeniority.SENIOR
    )


# ---------------------------------------------------------------------------
# Salary & Skills Extraction Tests
# ---------------------------------------------------------------------------


def test_extract_salary():
    """Verify parsing of salary bounds and currency detection."""
    # Format $175,000 - $215,000 USD
    min_sal, max_sal, curr = JobNormalizerService.extract_salary("$175,000 - $215,000 USD", "")
    assert min_sal == 175000
    assert max_sal == 215000
    assert curr == "USD"

    # Format $140k - $180k
    min_sal, max_sal, curr = JobNormalizerService.extract_salary("$140k - $180k", "")
    assert min_sal == 140000
    assert max_sal == 180000
    assert curr == "USD"

    # Currency detection
    min_sal, max_sal, curr = JobNormalizerService.extract_salary("£90,000 - £120,000", "")
    assert min_sal == 90000
    assert max_sal == 120000
    assert curr == "GBP"

    # From description scan when raw is missing
    desc = "We offer a competitive compensation range of $160k - $200k with equity."
    min_sal, max_sal, curr = JobNormalizerService.extract_salary(None, desc)
    assert min_sal == 160000
    assert max_sal == 200000


def test_extract_skills():
    """Verify technical skills extraction and separation into required and preferred."""
    description = (
        "We are looking for a Senior Engineer with deep knowledge of Python, PostgreSQL, and Docker. "
        "Experience with FastAPI and Kubernetes is essential. "
        "Nice to have: PyTorch, GraphQL, and Terraform."
    )
    req, pref = JobNormalizerService.extract_skills(description, extra_tags=["Redis"])

    assert "Python" in req
    assert "PostgreSQL" in req
    assert "Docker" in req
    assert "FastAPI" in req
    assert "Kubernetes" in req
    assert "Redis" in req  # from extra_tags

    assert "PyTorch" in pref
    assert "Terraform" in pref
    assert "GraphQL" in pref


# ---------------------------------------------------------------------------
# Content Hashing & Tamper-Evidence Tests
# ---------------------------------------------------------------------------


def test_compute_content_hash_deterministic():
    """Verify SHA-256 content hash is deterministic and tamper-evident."""
    hash1 = JobNormalizerService.compute_content_hash("Stripe", "Senior Backend Engineer", "Build payment APIs in Python.")
    hash2 = JobNormalizerService.compute_content_hash("Stripe", "Senior Backend Engineer", "Build payment APIs in Python.")
    assert hash1 == hash2
    assert len(hash1) == 64  # standard SHA-256 hex string

    # Tampering with one word alters the hash completely
    hash3 = JobNormalizerService.compute_content_hash("Stripe", "Senior Backend Engineer", "Build payment APIs in Java.")
    assert hash1 != hash3


# ---------------------------------------------------------------------------
# Cross-Source Deduplication & Multi-Source Linking Tests
# ---------------------------------------------------------------------------


def test_cross_source_deduplication_and_linking():
    """
    Verify that when the same job is retrieved from two sources (e.g. Greenhouse & RemoteOK):
    1. It produces 1 canonical unique JobListing.
    2. The duplicate source is attached to canonical.alternate_sources.
    3. The deduplication metrics accurately report the link.
    """
    now = utc_now()

    # Posting 1: from Greenhouse
    raw1 = RawJobPayload(
        source_name="greenhouse",
        source_job_id="gh_stripe_101",
        source_url="https://boards-api.greenhouse.io/v1/boards/stripe/jobs/101",
        title="Senior Backend Engineer - Core",
        organization="Stripe, Inc.",
        location_raw="Remote - US",
        description_raw="Build core infrastructure with Python and PostgreSQL. Remote friendly.",
        destination_url="https://stripe.com/jobs/101",
        retrieved_at=now,
    )

    # Posting 2: same role reposted on RemoteOK
    raw2 = RawJobPayload(
        source_name="remoteok",
        source_job_id="rok_992211",
        source_url="https://remoteok.com/remote-jobs/992211",
        title="Senior Backend Engineer",
        organization="Stripe",
        location_raw="Worldwide (Remote)",
        description_raw="Stripe is seeking a Senior Backend Engineer to build core infrastructure in Python.",
        destination_url="https://stripe.com/apply/992211",
        retrieved_at=now,
    )

    # Posting 3: distinct role at Datadog
    raw3 = RawJobPayload(
        source_name="greenhouse",
        source_job_id="gh_datadog_202",
        source_url="https://boards-api.greenhouse.io/v1/boards/datadog/jobs/202",
        title="Staff Platform Engineer",
        organization="Datadog",
        location_raw="New York, NY",
        description_raw="Kubernetes and Go telemetry pipelines at scale.",
        destination_url="https://datadog.com/jobs/202",
        retrieved_at=now,
    )

    unique_jobs, summary = JobNormalizerService.normalize_and_deduplicate([raw1, raw2, raw3])

    # Should consolidate raw1 and raw2 into 1 job, plus raw3 -> 2 unique jobs total
    assert len(unique_jobs) == 2
    assert summary.total_raw == 3
    assert summary.total_unique == 2
    assert summary.duplicates_detected == 1
    assert summary.cross_source_links == 1

    # Find the Stripe canonical job
    stripe_job = next(j for j in unique_jobs if j.organization == "Stripe")
    assert len(stripe_job.alternate_sources) == 1
    alt = stripe_job.alternate_sources[0]
    assert alt["source_name"] == "remoteok"
    assert alt["source_url"] == "https://remoteok.com/remote-jobs/992211"


# ---------------------------------------------------------------------------
# REST API Endpoint Tests
# ---------------------------------------------------------------------------


def test_api_normalize_endpoint(test_client):
    """Verify POST /api/v1/jobs/normalize endpoint."""
    raw_payloads = [
        {
            "source_name": "mock_adapter",
            "source_job_id": "test_001",
            "source_url": "http://mock/1",
            "title": "Sr. Python Dev [Remote]",
            "organization": "Acme Corp",
            "location_raw": "Remote",
            "description_raw": "FastAPI, PostgreSQL, and Docker microservices with $150k-$180k salary.",
            "destination_url": "http://mock/apply/1",
        }
    ]

    res = test_client.post("/api/v1/jobs/normalize", json=raw_payloads)
    assert res.status_code == 200
    data = res.json()
    assert data["summary"]["total_unique"] == 1
    job = data["jobs"][0]
    assert job["organization"] == "Acme"
    assert job["title"] == "Senior Python Developer"
    assert job["work_mode"] == "remote"
    assert job["seniority"] == "senior"
    assert job["salary_min"] == 150000
    assert job["salary_max"] == 180000
    assert "Python" in job["skills_required"]
    assert len(job["content_hash"]) == 64


def test_api_discover_endpoint(test_client):
    """Verify POST /api/v1/jobs/discover end-to-end ingestion and normalization."""
    req = {
        "query": "Kubernetes",
        "sources": ["mock_adapter"],
        "limit_per_source": 5,
    }

    res = test_client.post("/api/v1/jobs/discover", json=req)
    assert res.status_code == 200
    data = res.json()
    assert data["summary"]["total_unique"] > 0
    for job in data["jobs"]:
        assert job["source_name"] == "mock_adapter"
        assert len(job["content_hash"]) == 64
        assert job["work_mode"] in ["remote", "hybrid", "onsite", "unknown"]
