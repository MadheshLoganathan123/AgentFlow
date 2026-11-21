from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from packages.contracts.base import utc_now
from packages.contracts.job import JobSourceType, RawJobPayload
from services.api.services.job_adapters.base import BaseJobSourceAdapter

MOCK_JOB_FIXTURES: List[Dict[str, Any]] = [
    {
        "id": "mock_stripe_001",
        "title": "Senior Backend Engineer - Core Infrastructure",
        "organization": "Stripe",
        "location": "San Francisco, CA (Remote Friendly)",
        "work_mode": "remote",
        "seniority": "senior",
        "salary_raw": "$175,000 - $215,000 USD",
        "description": (
            "Stripe is looking for a Senior Backend Engineer to design scalable financial services infrastructure. "
            "You will build high-throughput microservices using Python, FastAPI, and PostgreSQL with pgvector. "
            "Requires 5+ years of software engineering experience, deep familiarity with distributed systems, "
            "Docker, and asynchronous programming in Linux environments."
        ),
        "destination_url": "https://stripe.com/jobs/senior-backend-infra",
        "posted_days_ago": 2,
        "sector": "Fintech",
    },
    {
        "id": "mock_datadog_002",
        "title": "Staff Platform Engineer - Kubernetes & Observability",
        "organization": "Datadog",
        "location": "New York, NY",
        "work_mode": "hybrid",
        "seniority": "staff",
        "salary_raw": "$195,000 - $245,000 USD",
        "description": (
            "Join Datadog as a Staff Platform Engineer driving Kubernetes cluster reliability and real-time observability. "
            "Key responsibilities include architecting multi-region Go services, optimizing telemetry pipelines, "
            "and scaling distributed traces. Requires 8+ years experience, expert knowledge of Go, Kubernetes, "
            "Terraform, and large-scale cloud operations on AWS."
        ),
        "destination_url": "https://careers.datadoghq.com/detail/staff-platform-engineer",
        "posted_days_ago": 4,
        "sector": "Developer Tools",
    },
    {
        "id": "mock_vercel_003",
        "title": "Frontend Engineer - Developer Experience",
        "organization": "Vercel",
        "location": "Remote - Worldwide",
        "work_mode": "remote",
        "seniority": "mid",
        "salary_raw": "$140,000 - $175,000 USD",
        "description": (
            "Vercel is seeking a Frontend Engineer passionate about crafting world-class developer experiences. "
            "You will develop interactive dashboards and preview tooling using Next.js 14, React, TypeScript, and Tailwind CSS. "
            "Requires 3+ years experience with modern React, client-side performance profiling, and accessible web UI."
        ),
        "destination_url": "https://vercel.com/careers/frontend-dev-experience",
        "posted_days_ago": 1,
        "sector": "Developer Tools",
    },
    {
        "id": "mock_flatiron_004",
        "title": "Senior Data Scientist - Oncology Analytics",
        "organization": "Flatiron Health",
        "location": "Boston, MA",
        "work_mode": "hybrid",
        "seniority": "senior",
        "salary_raw": "$160,000 - $200,000 USD",
        "description": (
            "Flatiron Health needs a Senior Data Scientist to analyze real-world clinical cancer research data. "
            "You will build predictive models, run causal inference, and collaborate with clinical researchers. "
            "Requirements: Python, pandas, scikit-learn, SQL, and 4+ years applying statistical models to health data."
        ),
        "destination_url": "https://flatiron.com/careers/senior-data-scientist",
        "posted_days_ago": 6,
        "sector": "HealthTech",
    },
    {
        "id": "mock_ramp_005",
        "title": "Full Stack Engineer - Cards & Spend Management",
        "organization": "Ramp",
        "location": "New York, NY",
        "work_mode": "onsite",
        "seniority": "mid",
        "salary_raw": "$150,000 - $190,000 USD",
        "description": (
            "Ramp is the next-generation financial automation platform. We are looking for a Full Stack Engineer "
            "to build card issuance and expense workflows. Tech stack: Python, FastAPI, React, TypeScript, and PostgreSQL. "
            "Requires 3+ years of end-to-end web engineering experience."
        ),
        "destination_url": "https://ramp.com/careers/fullstack-cards",
        "posted_days_ago": 3,
        "sector": "Fintech",
    },
    {
        "id": "mock_anthropic_006",
        "title": "AI Research & Alignment Engineer",
        "organization": "Anthropic",
        "location": "San Francisco, CA",
        "work_mode": "hybrid",
        "seniority": "senior",
        "salary_raw": "$220,000 - $280,000 USD",
        "description": (
            "Anthropic is building reliable, beneficial AI systems. We are seeking an AI Alignment Engineer "
            "to evaluate foundation model reasoning and safety properties. Requires strong Python, PyTorch, "
            "experience with LLM fine-tuning, automated evaluations, and distributed training clusters."
        ),
        "destination_url": "https://anthropic.com/careers/alignment-engineer",
        "posted_days_ago": 1,
        "sector": "AI / ML",
    },
    {
        "id": "mock_shopify_007",
        "title": "Lead Cloud Infrastructure Architect",
        "organization": "Shopify",
        "location": "Remote - Canada / US",
        "work_mode": "remote",
        "seniority": "lead",
        "salary_raw": "$185,000 - $230,000 USD",
        "description": (
            "Lead cloud architecture for millions of merchants during peak flash sales. "
            "Experience with Kubernetes, multi-region failover, Terraform, Go, and high-concurrency systems. "
            "Requires 7+ years in infrastructure architecture and reliability engineering."
        ),
        "destination_url": "https://shopify.com/careers/lead-cloud-architect",
        "posted_days_ago": 5,
        "sector": "E-Commerce",
    },
    {
        "id": "mock_openai_008",
        "title": "Systems Software Engineer - GPU Infrastructure",
        "organization": "OpenAI",
        "location": "San Francisco, CA",
        "work_mode": "onsite",
        "seniority": "senior",
        "salary_raw": "$230,000 - $310,000 USD",
        "description": (
            "Design the compute runtime powering cutting-edge AI breakthroughs. "
            "Expertise in Rust, C++, CUDA, low-latency networking, and distributed memory management. "
            "Minimum 5 years of systems programming experience."
        ),
        "destination_url": "https://openai.com/careers/systems-engineer-gpu",
        "posted_days_ago": 7,
        "sector": "AI / ML",
    },
    {
        "id": "mock_plaid_009",
        "title": "Senior DevOps & Security Automation Engineer",
        "organization": "Plaid",
        "location": "Remote - US",
        "work_mode": "remote",
        "seniority": "senior",
        "salary_raw": "$165,000 - $205,000 USD",
        "description": (
            "Plaid connects financial accounts safely. We are hiring a Senior DevOps Engineer to automate "
            "compliance, security scanning, container deployments, and CI/CD pipelines. "
            "Requires Python, Bash, AWS IAM, Docker, and SOC2 compliance automation."
        ),
        "destination_url": "https://plaid.com/careers/senior-devops-security",
        "posted_days_ago": 2,
        "sector": "Fintech",
    },
    {
        "id": "mock_figma_010",
        "title": "Product Engineer - Collaboration Systems",
        "organization": "Figma",
        "location": "San Francisco, CA",
        "work_mode": "hybrid",
        "seniority": "mid",
        "salary_raw": "$160,000 - $195,000 USD",
        "description": (
            "Figma enables teams to design together in real-time. Looking for a Product Engineer to build multiplayer "
            "canvas interactions. Requires strong TypeScript, WebGL/Canvas rendering, React, and operational transform algorithms."
        ),
        "destination_url": "https://figma.com/careers/product-engineer-collaboration",
        "posted_days_ago": 3,
        "sector": "Developer Tools",
    },
    {
        "id": "mock_scale_011",
        "title": "Machine Learning Infrastructure Engineer",
        "organization": "Scale AI",
        "location": "Remote - US",
        "work_mode": "remote",
        "seniority": "senior",
        "salary_raw": "$175,000 - $225,000 USD",
        "description": (
            "Build large-scale data ingestion and model training pipelines. "
            "Must have experience with Python, Ray, Apache Spark, Kubernetes, and PostgreSQL. "
            "4+ years building high-throughput ML pipelines."
        ),
        "destination_url": "https://scale.com/careers/ml-infra-engineer",
        "posted_days_ago": 8,
        "sector": "AI / ML",
    },
    {
        "id": "mock_github_012",
        "title": "Software Engineer II - Actions & Automation",
        "organization": "GitHub",
        "location": "Remote - Worldwide",
        "work_mode": "remote",
        "seniority": "mid",
        "salary_raw": "$135,000 - $170,000 USD",
        "description": (
            "Help build the engine powering GitHub Actions CI/CD workflows worldwide. "
            "We build in Ruby, Go, and TypeScript with Azure and Docker. "
            "Requires 2+ years backend engineering and familiarity with developer tooling."
        ),
        "destination_url": "https://github.com/careers/software-engineer-actions",
        "posted_days_ago": 4,
        "sector": "Developer Tools",
    },
]


class MockJobSourceAdapter(BaseJobSourceAdapter):
    """
    Deterministic mock adapter providing realistic multi-sector synthetic jobs.
    Essential for reproducible testing, evaluation benchmarks, and offline local development.
    """

    source_id = "src_mock_01"
    source_name = "mock_adapter"
    source_type = JobSourceType.MOCK
    rate_limit_per_minute = 1000
    base_url = "internal://mock-job-feed"

    def __init__(self, fixtures: Optional[List[Dict[str, Any]]] = None):
        self._fixtures = fixtures or MOCK_JOB_FIXTURES

    async def is_available(self) -> bool:
        """Mock adapter is always available in-memory."""
        return True

    async def fetch_raw_jobs(
        self,
        query: Optional[str] = None,
        location: Optional[str] = None,
        limit: int = 20,
    ) -> List[RawJobPayload]:
        """
        Return filtered synthetic jobs according to search terms.
        Preserves complete source provenance and UTC retrieval timestamps.
        """
        results: List[RawJobPayload] = []
        now = utc_now()
        query_norm = (query or "").lower().strip()
        loc_norm = (location or "").lower().strip()

        for item in self._fixtures:
            # Query match check
            if query_norm:
                searchable = f"{item['title']} {item['organization']} {item['description']} {item.get('sector', '')}".lower()
                if query_norm not in searchable:
                    continue

            # Location match check
            if loc_norm:
                loc_text = f"{item['location']} {item['work_mode']}".lower()
                if loc_norm not in loc_text:
                    continue

            posted_date = now - timedelta(days=item.get("posted_days_ago", 3))

            raw_payload = RawJobPayload(
                source_name=self.source_name,
                source_job_id=item["id"],
                source_url=f"internal://mock/{item['id']}",
                title=item["title"],
                organization=item["organization"],
                location_raw=item["location"],
                description_raw=item["description"],
                description_html=f"<p>{item['description']}</p>",
                salary_raw=item.get("salary_raw"),
                work_mode_raw=item.get("work_mode"),
                seniority_raw=item.get("seniority"),
                destination_url=item["destination_url"],
                retrieved_at=now,
                posted_at=posted_date,
                extra_metadata={
                    "sector": item.get("sector", "Technology"),
                    "mock": True,
                },
            )
            results.append(raw_payload)

            if len(results) >= limit:
                break

        return results
