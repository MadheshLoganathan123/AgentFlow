from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from packages.contracts.job import JobSourceType, RawJobPayload
from services.api.main import app
from services.api.services.job_adapters import (
    BaseJobSourceAdapter,
    GreenhouseJobSourceAdapter,
    JobAdapterRegistry,
    JobIngestionService,
    MockJobSourceAdapter,
    RemoteOKJobSourceAdapter,
)


@pytest.fixture
def test_client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Mock Adapter Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mock_adapter_fetches_default_jobs():
    """Verify MockJobSourceAdapter returns synthetic job fixtures with complete metadata."""
    adapter = MockJobSourceAdapter()
    assert await adapter.is_available() is True
    assert adapter.source_type == JobSourceType.MOCK

    jobs = await adapter.fetch_raw_jobs(limit=10)
    assert len(jobs) == 10

    sample = jobs[0]
    assert isinstance(sample, RawJobPayload)
    assert sample.source_name == "mock_adapter"
    assert sample.title
    assert sample.organization
    assert sample.description_raw
    assert sample.destination_url.startswith("http")
    assert sample.posted_at is not None
    assert sample.retrieved_at is not None


@pytest.mark.asyncio
async def test_mock_adapter_query_and_location_filtering():
    """Verify keyword filtering on title, description, and sector."""
    adapter = MockJobSourceAdapter()

    # Search by Python
    python_jobs = await adapter.fetch_raw_jobs(query="Python", limit=20)
    assert len(python_jobs) > 0
    for j in python_jobs:
        searchable = f"{j.title} {j.description_raw} {j.organization}".lower()
        assert "python" in searchable

    # Search by remote location
    remote_jobs = await adapter.fetch_raw_jobs(location="remote", limit=20)
    assert len(remote_jobs) > 0
    for j in remote_jobs:
        assert "remote" in f"{j.location_raw} {j.work_mode_raw}".lower()


# ---------------------------------------------------------------------------
# Greenhouse Adapter Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_greenhouse_adapter_parsing_and_html_stripping():
    """Verify GreenhouseJobSourceAdapter converts board JSON and cleans HTML content."""
    adapter = GreenhouseJobSourceAdapter(boards=["testcorp"])

    fake_board_data = {
        "jobs": [
            {
                "id": 12345,
                "title": "Principal Systems Engineer",
                "location": {"name": "Austin, TX"},
                "updated_at": "2026-11-10T12:00:00Z",
                "content": "<p>We are seeking a <strong>Principal Systems Engineer</strong>.<br>Must know Linux &amp; C++.</p>",
                "absolute_url": "https://boards.greenhouse.io/testcorp/jobs/12345",
                "departments": [{"name": "Infrastructure"}],
                "offices": [{"name": "Austin HQ"}],
            }
        ]
    }

    mock_resp = httpx.Response(200, json=fake_board_data, request=httpx.Request("GET", "http://test"))

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        jobs = await adapter.fetch_raw_jobs(limit=10)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.source_name == "greenhouse"
    assert job.source_job_id == "gh_testcorp_12345"
    assert job.title == "Principal Systems Engineer"
    assert job.location_raw == "Austin, TX"
    assert "Principal Systems Engineer" in job.description_raw
    assert "<strong>" not in job.description_raw  # HTML cleanly stripped
    assert "&amp;" not in job.description_raw  # HTML entities unescaped
    assert job.destination_url == "https://boards.greenhouse.io/testcorp/jobs/12345"
    assert job.extra_metadata["departments"] == ["Infrastructure"]


@pytest.mark.asyncio
async def test_greenhouse_adapter_timeout_handling():
    """Verify Greenhouse adapter catches timeouts gracefully without raising."""
    adapter = GreenhouseJobSourceAdapter(boards=["timeoutcorp"])

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=httpx.TimeoutException("Timeout")):
        jobs = await adapter.fetch_raw_jobs(limit=5)

    assert jobs == []


# ---------------------------------------------------------------------------
# RemoteOK Adapter Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remoteok_adapter_parsing():
    """Verify RemoteOK adapter skips legal disclaimer at index 0 and parses job payloads."""
    adapter = RemoteOKJobSourceAdapter()

    fake_feed = [
        {"legal": "Do not scrape without permission"},  # index 0 disclaimer
        {
            "id": 998877,
            "position": "Senior Python Developer",
            "company": "Acme Global",
            "location": "Worldwide",
            "tags": ["python", "django", "postgres"],
            "description": "<p>Remote role building APIs with Python and Django.</p>",
            "url": "https://remoteok.com/remote-jobs/998877",
            "apply_url": "https://acme.com/apply/998877",
            "salary_min": 130000,
            "salary_max": 160000,
            "date": "2026-11-12T08:00:00Z",
            "slug": "senior-python-developer-acme",
        },
    ]

    mock_resp = httpx.Response(200, json=fake_feed, request=httpx.Request("GET", "http://test"))

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        jobs = await adapter.fetch_raw_jobs(limit=10)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.source_name == "remoteok"
    assert job.source_job_id == "rok_998877"
    assert job.title == "Senior Python Developer"
    assert job.organization == "Acme Global"
    assert job.salary_raw == "$130,000 - $160,000 USD"
    assert job.work_mode_raw == "remote"
    assert "python" in job.extra_metadata["tags"]


# ---------------------------------------------------------------------------
# Registry & Ingestion Service Tests
# ---------------------------------------------------------------------------


def test_job_adapter_registry():
    """Verify adapter registration and retrieval."""
    registry = JobAdapterRegistry()
    assert "mock_adapter" in registry.list_source_names()
    assert "greenhouse" in registry.list_source_names()
    assert "remoteok" in registry.list_source_names()

    mock = registry.get("mock_adapter")
    assert mock is not None
    assert mock.source_name == "mock_adapter"


@pytest.mark.asyncio
async def test_ingestion_service_error_isolation():
    """Verify that an error in one source does not crash other sources."""
    registry = JobAdapterRegistry()

    # Create a failing adapter
    class FailingAdapter(BaseJobSourceAdapter):
        source_id = "src_fail"
        source_name = "failing_src"
        source_type = JobSourceType.API
        base_url = "http://error"

        async def is_available(self):
            return False

        async def fetch_raw_jobs(self, query=None, location=None, limit=20):
            raise RuntimeError("Upstream feed corrupted")

    registry.register(FailingAdapter())

    service = JobIngestionService(registry=registry)
    summary = await service.ingest_jobs(sources=["mock_adapter", "failing_src"], limit_per_source=5)

    assert summary.total_jobs > 0
    assert "failing_src" in summary.source_errors
    assert "Upstream feed corrupted" in summary.source_errors["failing_src"]
    assert summary.source_counts.get("mock_adapter") == 5
    assert summary.duration_seconds >= 0.0


# ---------------------------------------------------------------------------
# REST API Endpoint Tests
# ---------------------------------------------------------------------------


def test_api_list_sources(test_client):
    """Verify GET /api/v1/jobs/sources returns active adapters."""
    res = test_client.get("/api/v1/jobs/sources")
    assert res.status_code == 200
    data = res.json()
    source_names = [s["source_name"] for s in data]
    assert "mock_adapter" in source_names
    assert "greenhouse" in source_names
    assert "remoteok" in source_names


def test_api_ingest_endpoint(test_client):
    """Verify POST /api/v1/jobs/ingest invokes ingestion across mock source."""
    payload = {
        "query": "Backend",
        "sources": ["mock_adapter"],
        "limit_per_source": 5,
    }
    res = test_client.post("/api/v1/jobs/ingest", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["total_jobs"] > 0
    assert "mock_adapter" in data["source_counts"]
    assert len(data["jobs"]) == data["total_jobs"]
    for j in data["jobs"]:
        assert j["source_name"] == "mock_adapter"
        assert "backend" in f"{j['title']} {j['description_raw']}".lower()
