import hashlib

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from packages.contracts.interview import (
    ResearchSummary,
    ValidateUrlResponse,
)
from packages.db.base import Base
from packages.db.repositories.research_repo import ResearchSourceRepository
from packages.db.session import get_async_session
from services.api.main import app
from services.api.services.web_research import WebResearchTool


@pytest_asyncio.fixture
async def async_test_session():
    """In-memory SQLite async database session."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def client_with_session(async_test_session: AsyncSession):
    """Test client configured with async DB session dependency override."""
    async def override_session():
        yield async_test_session

    app.dependency_overrides[get_async_session] = override_session
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_domain_allowlist_enforcement():
    """Verify that only reputable sources are allowlisted and untrusted origins are strictly rejected."""
    # 1. Allowlisted reputable domains
    reputable_urls = [
        "https://engineering.cloudscale.io/distributed-ingestion-architecture",
        "https://cloudscale.io/careers/values-and-culture",
        "https://www.sec.gov/edgar/browse/?CIK=0001326801",
        "https://github.com/cloudscale/pipeline-orchestrator",
        "https://en.wikipedia.org/wiki/Distributed_data_store",
        "https://engineering.fb.com/ai-infrastructure",
        "https://blog.cloudflare.com/how-we-built-it",
        "https://cloud.google.com/blog/topics/developers-practitioners",
        "https://techcrunch.com/2026/synthetix-labs-funding",
        "https://wired.com/story/future-of-ai-agents",
        "https://news.ycombinator.com/item?id=123456",
        "https://lever.co/company-job",
        "https://jobs.greenhouse.io/synthetix/lead-architect",
    ]
    for url in reputable_urls:
        assert WebResearchTool.is_domain_allowlisted(url) is True, f"Expected allowlisted: {url}"

    # 2. Untrusted / Disallowed origins
    banned_urls = [
        "https://4chan.org/biz/thread/12345",
        "https://pastebin.com/raw/leaked-data",
        "https://free-resume-scam.net/free-templates",
        "https://unknown-shady-board.xyz/forum/view",
        "http://scam-jobs.biz/apply-now",
        "https://piratebay.org/torrent/123",
    ]
    for url in banned_urls:
        assert WebResearchTool.is_domain_allowlisted(url) is False, f"Expected rejected: {url}"

    # 3. Arbitrary non-allowlisted / unverified external sites
    unverified_urls = [
        "https://random-unverified-blog.org/my-thoughts",
        "https://bob-home-page.info/tips",
        "not-a-valid-url",
        "ftp://files.example.com/readme",
    ]
    for url in unverified_urls:
        assert WebResearchTool.is_domain_allowlisted(url) is False, f"Expected rejected: {url}"


def test_validate_url_method():
    """Test URL inspection and category classification."""
    # Allowlisted URL
    res = WebResearchTool.validate_url("https://www.sec.gov/edgar/searchedgar/companysearch")
    assert isinstance(res, ValidateUrlResponse)
    assert res.is_allowlisted is True
    assert res.category == "sec_filing"
    assert "verified and allowlisted" in res.message

    # GitHub repository
    res_gh = WebResearchTool.validate_url("https://github.com/fastapi/fastapi")
    assert res_gh.is_allowlisted is True
    assert res_gh.category == "github"

    # Disallowed untrusted origin
    res_banned = WebResearchTool.validate_url("https://pastebin.com/xyz123")
    assert res_banned.is_allowlisted is False
    assert res_banned.category == "disallowed_untrusted"
    assert "flagged as untrusted" in res_banned.message

    # Invalid URL
    res_inv = WebResearchTool.validate_url("")
    assert res_inv.is_allowlisted is False


def test_cryptographic_content_hash():
    """Verify SHA-256 cryptographic hashing for content tamper-evidence."""
    excerpt = "Our streaming ingestion pipeline processes 50,000 events/second using asynchronous Python workers."
    expected_hash = hashlib.sha256(excerpt.strip().encode("utf-8")).hexdigest()

    computed_hash = WebResearchTool.calculate_content_hash(excerpt)
    assert computed_hash == expected_hash
    assert len(computed_hash) == 64

    # Tamper test
    tampered_excerpt = excerpt + " Tampered addition."
    tampered_hash = WebResearchTool.calculate_content_hash(tampered_excerpt)
    assert tampered_hash != computed_hash


@pytest.mark.asyncio
async def test_research_company_intelligence_segregation():
    """
    Verify that research separates company-specific intelligence (tech stack, culture)
    from generic industry/interview advice, retaining SHA-256 hashes on all sources.
    """
    tool = WebResearchTool()
    summary = await tool.research_company(
        company_name="CloudScale Data Technologies",
        role_title="Senior Backend Engineer",
        job_id="job_cs_99",
    )

    assert isinstance(summary, ResearchSummary)
    assert summary.company_name == "CloudScale Data Technologies"
    assert summary.target_role == "Senior Backend Engineer"
    assert summary.job_id == "job_cs_99"
    assert len(summary.sources) > 0
    assert len(summary.company_specific_sources) > 0
    assert len(summary.general_advice_sources) > 0

    # Ensure complete partition
    assert len(summary.company_specific_sources) + len(summary.general_advice_sources) == len(summary.sources)

    # Check company-specific sources properties
    for src in summary.company_specific_sources:
        assert src.is_company_specific is True
        assert src.content_hash is not None
        assert len(src.content_hash) == 64
        assert src.is_reputable is True
        assert WebResearchTool.is_domain_allowlisted(src.source_url) is True

    # Check general advice sources properties
    for src in summary.general_advice_sources:
        assert src.is_company_specific is False
        assert src.content_hash is not None
        assert WebResearchTool.is_domain_allowlisted(src.source_url) is True

    # Check tech stack and culture observations
    assert any("Python" in item for item in summary.tech_stack_observations)
    assert any("Kafka" in item or "PostgreSQL" in item for item in summary.tech_stack_observations)
    assert len(summary.culture_and_values) > 0
    assert len(summary.interview_topics_suggested) > 0


@pytest.mark.asyncio
async def test_research_source_repository_crud(async_test_session: AsyncSession):
    """Test full CRUD operations on ResearchSourceRepository."""
    repo = ResearchSourceRepository(async_test_session)

    # 1. Save new source
    source1 = await repo.save_source(
        company_name="Synthetix Labs",
        title="Synthetix Labs AI Platform Engineering",
        url="https://blog.synthetixlabs.ai/agent-state-machines",
        source_name="blog.synthetixlabs.ai",
        excerpt="Structuring durable LLM agents with deterministic checkpoints.",
        job_id="job_syn_10",
        is_company_specific=True,
        content_hash="abc123hash456",
        source_category="engineering_blog",
    )
    assert source1.id is not None
    assert source1.company_name == "Synthetix Labs"
    assert source1.is_reported is False
    assert source1.content_hash == "abc123hash456"

    # 2. Get source by ID
    fetched = await repo.get_source(source1.id)
    assert fetched is not None
    assert fetched.title == "Synthetix Labs AI Platform Engineering"

    # 3. Duplicate save updates existing
    updated = await repo.save_source(
        company_name="Synthetix Labs",
        title="Synthetix Labs AI Platform Engineering - Updated",
        url="https://blog.synthetixlabs.ai/agent-state-machines",
        source_name="blog.synthetixlabs.ai",
        excerpt="Updated excerpt for durability.",
        job_id="job_syn_10",
        is_company_specific=True,
        content_hash="def456updatedhash",
        source_category="engineering_blog",
    )
    assert updated.id == source1.id
    assert updated.title == "Synthetix Labs AI Platform Engineering - Updated"
    assert updated.content_hash == "def456updatedhash"

    # 4. Save second source for listing
    await repo.save_source(
        company_name="Synthetix Labs",
        title="STAR Method Guide",
        url="https://en.wikipedia.org/wiki/Situation,_task,_action_and_result",
        source_name="wikipedia.org",
        excerpt="STAR framework overview.",
        job_id="job_syn_10",
        is_company_specific=False,
        content_hash="hash_star_789",
        source_category="general_advice",
    )

    sources = await repo.list_sources(company_name="Synthetix")
    assert len(sources) == 2

    # 5. Report source
    reported = await repo.report_source(source1.id, "Stale engineering post; version upgraded.")
    assert reported is not None
    assert reported.is_reported is True
    assert reported.report_reason == "Stale engineering post; version upgraded."

    # Filter with include_reported=False
    active_sources = await repo.list_sources(company_name="Synthetix", include_reported=False)
    assert len(active_sources) == 1
    assert active_sources[0].is_reported is False

    # 6. Delete source
    deleted = await repo.delete_source(source1.id)
    assert deleted is True

    rem = await repo.get_source(source1.id)
    assert rem is None


def test_research_rest_api_endpoints(client_with_session: TestClient):
    """Test FastAPI REST endpoints in services/api/routers/research.py."""
    client = client_with_session

    # 1. POST /api/v1/research/validate-url
    val_resp = client.post(
        "/api/v1/research/validate-url",
        json={"url": "https://engineering.fb.com/ai-infrastructure"},
    )
    assert val_resp.status_code == 200, val_resp.text
    val_data = val_resp.json()
    assert val_data["is_allowlisted"] is True
    assert val_data["category"] == "engineering_blog"

    # 2. POST /api/v1/research/company
    comp_resp = client.post(
        "/api/v1/research/company",
        json={
            "company_name": "Synthetix Labs",
            "role_title": "Lead AI Application Architect",
            "job_id": "job_syn_42",
        },
    )
    assert comp_resp.status_code == 200, comp_resp.text
    summary_data = comp_resp.json()
    assert summary_data["company_name"] == "Synthetix Labs"
    assert len(summary_data["sources"]) > 0
    assert len(summary_data["company_specific_sources"]) > 0
    assert len(summary_data["general_advice_sources"]) > 0

    first_source_id = summary_data["sources"][0].get("id")

    # 3. GET /api/v1/research/sources
    list_resp = client.get("/api/v1/research/sources?company_name=Synthetix")
    assert list_resp.status_code == 200, list_resp.text
    list_data = list_resp.json()
    assert len(list_data) >= 1

    if first_source_id:
        # 4. GET /api/v1/research/sources/{source_id}
        get_resp = client.get(f"/api/v1/research/sources/{first_source_id}")
        assert get_resp.status_code == 200, get_resp.text
        assert get_resp.json()["id"] == first_source_id

        # 5. POST /api/v1/research/sources/{source_id}/report
        rep_resp = client.post(
            f"/api/v1/research/sources/{first_source_id}/report",
            json={"reason": "Contains outdated framework reference."},
        )
        assert rep_resp.status_code == 200, rep_resp.text
        assert rep_resp.json()["is_reported"] is True
        assert rep_resp.json()["report_reason"] == "Contains outdated framework reference."

        # 6. DELETE /api/v1/research/sources/{source_id}
        del_resp = client.delete(f"/api/v1/research/sources/{first_source_id}")
        assert del_resp.status_code == 200, del_resp.text
        assert del_resp.json()["id"] == first_source_id

        # Verify 404 after deletion
        get_404 = client.get(f"/api/v1/research/sources/{first_source_id}")
        assert get_404.status_code == 404
