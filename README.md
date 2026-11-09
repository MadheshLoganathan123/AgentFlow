# AgentFlow — Multi-Agent Job-Seeker Copilot

AgentFlow is a collaborative multi-agent job-search copilot for employees and job seekers. It understands a user's profile, discovers suitable roles across sectors and organizations, explains the match, prepares grounded application materials, drafts professional outreach emails, finds trustworthy mock-interview resources, and supports a user-authorized application flow.

## Core Architectural Principles
1. **One Workflow Authority**: LangGraph owns the workflow state machine and stage transitions.
2. **Human Approval Gates**: Consequential actions (profile confirmation, shortlisting, application submission) require explicit user action.
3. **Evidence Grounding**: Verified facts from resumes or authoritative sources are strictly isolated from model inferences. The system never treats an unconfirmed inference as a verified fact.
4. **Open Source Stack**: 100% open-source technologies (FastAPI, LangGraph, PostgreSQL + pgvector, Next.js, Docker).

---

## Repository Structure

```
AgentFlow/
|-- .github/workflows/ci.yml       # CI pipeline (lint, test, build)
|-- docker-compose.yml             # Postgres + pgvector, API, and Web containers
|-- pyproject.toml                 # Root Python project configuration
|-- package.json                   # Root npm workspace configuration
|-- requirements.txt               # Production Python dependencies
|-- requirements-dev.txt           # Testing & linting dependencies
|-- .env.example                   # Template environment variables
|-- apps/
|   `-- web/                       # Next.js 14 React Dashboard (App Router, Tailwind CSS)
|-- services/
|   |-- api/                       # FastAPI REST API service
|   `-- orchestrator/              # LangGraph workflow authority & checkpointer
|-- packages/
|   |-- contracts/                 # Shared typed Pydantic models & agent contracts
|   `-- db/                        # SQLAlchemy 2.0 models, pgvector & session management
|-- tests/
|   |-- unit/                      # Unit tests (contracts, extractor, orchestrator)
|   `-- integration/               # Integration tests (API endpoints, health checks)
`-- docs/                          # Architecture specs, week breakdown, setup guides
```

---

## 5-Week Implementation Roadmap

- **Week 1: Foundation, Profile, and Product Skeleton**
  - **[x] Phase 1**: Project Architecture, Monorepo Foundation & Open Source Stack
  - **[ ] Phase 2**: PostgreSQL Database Schema & Relational Models
  - **[ ] Phase 3**: Typed Agent & Domain Contracts
  - **[ ] Phase 4**: LangGraph Workflow Skeleton & Checkpointing
  - **[ ] Phase 5**: Backend API & Resume Extraction Pipeline
  - **[ ] Phase 6**: Web Dashboard & Profile Onboarding UI
- **Week 2**: Job Ingestion, Matching, and Explainable Recommendations
- **Week 3**: Tailored Documents, Email Drafts, and Interview Research
- **Week 4**: One-Click Assisted Application and End-to-End Workflow
- **Week 5**: Security, Evaluation, Usability, and Release

---

## Getting Started

Refer to [docs/LOCAL_DEVELOPMENT.md](file:///docs/LOCAL_DEVELOPMENT.md) for step-by-step setup instructions.

```bash
# 1. Setup Environment
cp .env.example .env

# 2. Run Database via Docker
docker compose up postgres -d

# 3. Run Backend API Tests
pytest
```

