# Week 1 — Foundation, Profile, and Product Skeleton
## Detailed 6-Phase Implementation Breakdown

**Overall Goal of Week 1**: A user can create a profile, upload a resume, review extracted data with separated facts/inferences, and see the core dashboard with human approval gates.

---

### [x] Phase 1: Project Architecture, Monorepo Foundation & Open Source Stack (COMPLETED)
- **Scope**:
  - Establish monorepo structure: `apps/web`, `services/api`, `services/orchestrator`, `packages/contracts`, `packages/db`, `tests`, `docs`.
  - Configure root package definitions (`pyproject.toml`, root `package.json`, `.env.example`, `.env`, `.gitignore`).
  - Containerization setup (`docker-compose.yml`) specifying PostgreSQL 16 with `pgvector`, backend API, and web dashboard.
  - Setup GitHub Actions CI workflow for linting, type checks, unit/integration testing, and Docker builds.
  - Base FastAPI application, health endpoints, LangGraph skeleton checkpointer, and Next.js frontend skeleton.
  - Initial end-to-end unit and integration test suite passing.

---

### [x] Phase 2: PostgreSQL Schema & Relational Models (COMPLETED)
- **Scope**:
  - Authoritative relational tables in SQLAlchemy 2.0 covering all 20 required entities: `users`, `candidate_profiles`, `profile_evidence`, `preferences`, `job_sources`, `job_listings`, `job_matches`, `saved_jobs`, `application_packages`, `applications`, `application_events`, `email_drafts`, `research_sources`, `interview_plans`, `mock_interviews`, `agent_runs`, `workflow_checkpoints`, `approvals`, `audit_events`, `model_usage`.
  - pgvector embedding schema integration (`SafeVector` with dimension 1536) for semantic retrieval.
  - Alembic migration environment (`alembic.ini`, `env.py`, `001_initial_schema.py`) with PostgreSQL vector extension initialization and downgrade rollback support.
  - Complete repository layer (`UserRepository`, `ProfileRepository`, `CheckpointRepository`, `AuditEventRepository`, `JobRepository`) enforcing user-data isolation at the query layer.
  - Cross-account isolation and anti-tampering test suite passing.

---

### [ ] Phase 3: Typed Agent & Domain Contracts
- **Scope**:
  - Complete Pydantic v2 schemas across all agents in `packages/contracts`:
    - `CandidateProfile`, `WorkExperience`, `Education`, `SkillItem`, `ProfileEvidence`.
    - `JobListing`, `MatchExplanation`, `ScoreBreakdown`.
    - `ApplicationPackage`, `ApplicationReadiness`, `ApplicationResult`.
    - `EmailDraft`, `InterviewPlan`.
  - Contract validation suite enforcing schema versioning, prompt versions, model identifiers, and evidence grounding.

---

### [ ] Phase 4: LangGraph Workflow Skeleton & Checkpointing
- **Scope**:
  - LangGraph `StateGraph` definition for the Profile Onboarding and Verification lifecycle.
  - Durable checkpoint persistence using PostgreSQL and fallback checkpointer.
  - Non-bypassable human approval pause gate (`awaiting_profile_confirmation`).
  - Resume-from-checkpoint execution without state loss or memory corruption.

---

### [ ] Phase 5: Backend API & Resume Extraction Pipeline
- **Scope**:
  - Resume file upload endpoint supporting PDF and plain text.
  - Open-source PDF text extraction using `pypdf` / `pdfplumber`.
  - Profile Analyst agent execution isolating verified resume facts from unconfirmed inferences.
  - Missing field detection generating targeted candidate questions.
  - REST endpoints for profile inspection, updating, and confirmation.

---

### [ ] Phase 6: Web Dashboard & Profile Onboarding UI
- **Scope**:
  - Next.js 14 App Router dashboard with responsive Tailwind CSS layout.
  - Resume upload component with drag-and-drop file selector and text fallback.
  - Profile review card visibly separating verified facts from missing/inferred information.
  - Explicit confirmation control to approve facts and resume the workflow.
  - End-of-week demo validation: `Resume upload -> Profile review -> Profile confirmation`.

