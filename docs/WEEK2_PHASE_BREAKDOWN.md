# Week 2 — Job Ingestion, Matching, and Explainable Recommendations
## Detailed 6-Phase Implementation Breakdown

**Overall Goal of Week 2**: A user can search or receive a useful shortlist of jobs with reasons, clear match explanations, grounded source citations, and human shortlist decisions.

---

### [x] Phase 1: Multi-Source Job Ingestion Adapters & Raw Ingestion Pipeline (CURRENT)
- **Goal**: Establish an extensible, resilient adapter architecture to ingest job postings from real and mock sources with full source metadata and auditability.
- **Scope**:
  - `BaseJobSourceAdapter` abstract base class defining standard contracts:
    - Unique `source_id`, `source_name`, `adapter_type`, and rate limiting parameters.
    - Async `fetch_raw_jobs(query, limit)` and `fetch_job_details(job_id)`.
    - Health/connectivity checks (`is_available`).
  - **Deterministic Mock Adapter** (`MockJobSourceAdapter`):
    - Curated, realistic synthetic dataset covering 5+ industry sectors (Fintech, HealthTech, AI/Developer Tools, Cloud Platforms, E-Commerce).
    - Diverse seniority levels (Entry, Mid, Senior, Lead, Staff, Principal).
    - Diverse work modes (Remote, Hybrid, Onsite) and competitive salary ranges.
    - Deterministic responses for repeatable testing and offline local development.
  - **Greenhouse Public ATS Adapter** (`GreenhouseJobSourceAdapter`):
    - Ingests public job listings via Greenhouse board endpoints (`https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs`).
    - Handles pagination, department/office tagging, and HTML content decoding.
  - **RemoteOK Adapter** (`RemoteOKJobSourceAdapter`):
    - Ingests live remote developer jobs with tag/skill extraction and ISO date parsing.
  - **Adapter Registry** (`JobAdapterRegistry`):
    - Central registry to discover, configure, and dynamically invoke adapters by name or source type.
  - **Job Ingestion Service** (`JobIngestionService`):
    - Orchestrates concurrent ingestion across enabled sources with bounded retries, timeouts, and error isolation.
  - Unit and integration tests verifying all adapters, error handling, rate limits, and source metadata capture.

---

### [x] Phase 2: Job Normalization, Cross-Source Deduplication & Content Hashing (COMPLETED)
- **Goal**: Clean raw payloads into authoritative `JobListing` contracts, compute tamper-evident content hashes, and deduplicate identical roles across sources.
- **Scope**:
  - Title and organization string normalizers stripping legal suffixes and requisition noise.
  - Automated extraction/inference of work modes (`remote`, `hybrid`, `onsite`), seniority levels, numerical salary bounds, and categorized skill taxonomy requirements.
  - Deterministic SHA-256 content hashing to ensure idempotent storage, reproducible identity, and tamper detection.
  - Cross-source deduplication algorithm identifying multi-posted roles across Greenhouse, RemoteOK, and mock feeds, consolidating them into canonical records with linked `alternate_sources`.
  - REST endpoints `POST /api/v1/jobs/normalize` and `POST /api/v1/jobs/discover` with full `NormalizationSummary` telemetry.
  - Full test suite passing with 60/60 tests and 100% clean Next.js build.

---

### [x] Phase 3: Explainable Multi-Dimensional Match & Ranking Engine (COMPLETED)
- **Goal**: Score candidates against jobs across 6 explicit dimensions and generate structured, transparent explanations.
- **Scope**:
  - Multi-dimensional scoring: Skills (35%), Seniority (20%), Work Mode/Location (15%), Salary (15%), Sector (10%), Recency (5%).
  - Transparent `ScoreBreakdown` providing granular score inspection for every evaluated dimension without opaque scores.
  - Detailed `MatchExplanation` generator detailing strengths, gaps, missing criteria, matched requirements, and uncertainty metrics.
  - Safety check: strictly blocks claiming `strong_match` when critical candidate requirements (e.g. work authorization) are unconfirmed or missing.
  - REST endpoints `POST /api/v1/jobs/match` (single match breakdown) and `POST /api/v1/jobs/recommend` (ranked multi-job recommendations).
  - Ranking tests verified against fixed sample sets and full test suite passing with 68/68 tests.

---

### [x] Phase 4: Database Persistence, Search Filters & Hybrid Retrieval (COMPLETED)
- **Goal**: Store normalized jobs and match results in PostgreSQL and provide multi-facet search, hybrid ranking, and user shortlist actions.
- **Scope**:
  - Enhanced `JobRepository` with multi-facet query filtering: organization, title, location, work mode, seniority, salary bounds, posting date, and pagination.
  - Idempotent upsert logic with `content_hash` deduplication and automated multi-source provenance linking (`alternate_sources`).
  - Explainable match evaluations persistence in `job_matches` table with full 6-dimensional breakdown, strengths, gaps, uncertainties, and matched requirements.
  - User shortlist and decision actions (`shortlisted`, `saved`, `dismissed`, `unsuitable`) in `saved_jobs` table with strict user data isolation.
  - Hybrid search and retrieval engine (`JobRetrievalService`) integrating relational filtering, lexical token overlap, and explainable multi-dimensional ranking.
  - Complete REST API endpoints:
    - `POST /api/v1/jobs/persist`: Bulk persist normalized job listings.
    - `GET /api/v1/jobs/search`: Multi-facet query search with parameter validation.
    - `GET /api/v1/jobs/{job_id}`: Single job lookup by canonical ID.
    - `POST /api/v1/jobs/{job_id}/action`: Record user decision (`shortlisted`, `saved`, `dismissed`, `unsuitable`).
    - `GET /api/v1/jobs/saved`: List user saved/shortlisted jobs with status filtering.
    - `DELETE /api/v1/jobs/{job_id}/saved`: Remove saved job decision.
    - `POST /api/v1/jobs/search-and-rank`: End-to-end hybrid search, ranking, and match persistence.
  - 4 comprehensive audit tiers passed: 73 unit tests (100% pass), multi-tenant user isolation, idempotent deduplication, and Next.js production build.

---

### [x] Phase 5: LangGraph Discovery & Matching Workflow with Shortlist Approval Gate (COMPLETED)
- **Goal**: Orchestrate the full end-to-end job search pipeline in LangGraph with a durable, non-bypassable human shortlist approval gate.
- **State Machine**:
  - `job_discovery` → `job_normalization_dedup` → `match_scoring_explanation` → `awaiting_shortlist_approval` *(interrupt_before gate)* → `shortlist_confirmed` → `END`
- **Scope**:
  - `JobDiscoveryAndMatchingWorkflow` LangGraph StateGraph in [`services/orchestrator/job_discovery_workflow.py`](services/orchestrator/job_discovery_workflow.py):
    - **`node_job_discovery`**: Invokes all registered adapters (or accepts pre-seeded payloads). Concurrent live fetching via `JobIngestionService` with asyncio fallback guard.
    - **`node_job_normalization_dedup`**: Normalizes raw payloads into canonical `JobListing` contracts via `JobNormalizerService`. Accepts both canonical and alternate field-name schemas. SHA-256 content hashing and cross-source deduplication applied.
    - **`node_match_scoring_explanation`**: Scores all normalized jobs against candidate profile using `MatchRankingService` (6 dimensions: Skills 35%, Seniority 20%, Location/Mode 15%, Salary 15%, Sector 10%, Recency 5%). Produces ranked list sorted by composite score descending with full explanations.
    - **`node_awaiting_shortlist_approval`**: Human approval gate — enforced by LangGraph `interrupt_before`. Cannot be bypassed. Emits structured `ApprovalRequest` with ranked count.
    - **`node_shortlist_confirmed`**: Records shortlisted and dismissed job IDs, marks approval resolved, clears pause state.
  - `AgentFlowWorkflowState` extended with Phase 5 fields: discovery parameters, raw/normalized payloads, ranked matches, shortlist/dismiss decisions.
  - Resilient payload mapping in normalization node handles both canonical and alternate raw field schemas.
  - `JobDiscoveryAndMatchingWorkflow` class with `start()`, `resume_with_shortlist()`, `get_ranked_matches()`, and `load_state()` controller methods.
  - Durable checkpointing via `MemoryCheckpointer` (dev) with `BaseCheckpointer` interface for PostgreSQL swap-in.
  - REST API endpoints in [`services/api/routers/discovery.py`](services/api/routers/discovery.py):
    - `POST /api/v1/discovery/start`: Kick off workflow; runs to gate; returns 202 when paused.
    - `GET /api/v1/discovery/{workflow_id}/status`: Current stage, pause state, progress counts.
    - `GET /api/v1/discovery/{workflow_id}/matches`: Ranked match summaries sorted by score for user review.
    - `POST /api/v1/discovery/{workflow_id}/approve-shortlist`: Resume with user shortlist decision (409 if not paused).
    - `GET /api/v1/discovery/{workflow_id}/shortlisted`: Return only user-confirmed shortlisted jobs.
  - 4 audit tiers all passed: **94 / 94 unit tests (100%)**, workflow regression (22/22), LangGraph interrupt gate enforcement, Next.js production build.

---

### [x] Phase 6: Web Dashboard Integration — Discovery, Match Explanations & Shortlist UI (COMPLETED)
- **Goal**: Deliver a fully wired, production-quality user experience for discovering jobs, reviewing explainable match cards, and confirming a shortlist via the LangGraph approval gate.
- **Scope**:
  - **Typed API client** [`apps/web/src/lib/api.ts`](apps/web/src/lib/api.ts):
    - Full TypeScript contracts mirroring all backend Pydantic models: `ScoreBreakdown`, `MatchExplanation`, `JobListing`, `RankedMatch`, `DiscoveryStatusResponse`, `MatchSummaryItem`, `ShortlistConfirmedResponse`, `SavedJobResponse`.
    - `discoveryApi`: `start`, `status`, `matches`, `approveShortlist`, `shortlisted` wrappers.
    - `jobsApi`: `search`, `action`, `saved`, `removeSaved` wrappers.
    - Configurable via `NEXT_PUBLIC_API_URL` environment variable.
  - **Rebuilt `JobMatchesView`** [`apps/web/src/components/JobMatchesView.tsx`](apps/web/src/components/JobMatchesView.tsx):
    - **`DiscoveryLauncher`** panel: live filter controls for keyword query, work mode, seniority, min/max salary — calls `POST /api/v1/discovery/start`.
    - **`MatchCard`** component: composite score ring, recommendation badge (Strong Match / Potential Match / Gap Heavy / Not Recommended), strengths list, gaps list, expandable per-dimension score bars, shortlist / dismiss action buttons.
    - **`ShortlistConfirmBanner`**: LangGraph approval gate UI — shows shortlisted/dismissed counts, `Confirm Shortlist` button (calls `POST /api/v1/discovery/{id}/approve-shortlist`), `409 Conflict` guard prevents double-confirmation.
    - Client-side `localFilter` text box for instant result filtering on top of backend matches.
    - Workflow state machine: `idle → launching → paused_at_gate → confirming → confirmed`.
    - Full error boundary with inline error display and API-not-running hint.
  - **TypeScript type audit file** [`apps/web/src/lib/api.types.test.ts`](apps/web/src/lib/api.types.test.ts): compile-time assertions for all 8 exported contract types.
  - 3 audit tiers passed: **Next.js production build ✓** (19.4 kB bundle, 4 static pages), **TypeScript `--noEmit` strict check ✓** (zero errors), **94 / 94 backend tests ✓** (no regressions).
