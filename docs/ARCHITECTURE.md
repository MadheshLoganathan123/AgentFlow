# AgentFlow — Architecture & Technical Design

## 1. Core Principle: One Workflow Authority

AgentFlow implements **one workflow authority**. **LangGraph** owns the job-search workflow state and stage transitions. The **FastAPI** API layer handles authentication, persistence, and REST/SSE requests. Browser/application adapters, web research tools, and email integrations are controlled tools called by workflow nodes; **they never independently decide whether an application is submitted or mutates external services**.

```
+-------------------------------------------------------+
|                 React / Next.js Web UI                |
|       (Dashboard, Onboarding, Review & Gates)         |
+---------------------------+---------------------------+
                            | REST / SSE
                            v
+-------------------------------------------------------+
|                 FastAPI Backend Service               |
|      (Authentication, REST endpoints, File Ingest)    |
+---------------------------+---------------------------+
                            |
           +----------------+----------------+
           |                                 |
           v                                 v
+-----------------------+       +-----------------------+
| PostgreSQL + pgvector |       | LangGraph Orchestrator|
| (Authoritative state) |       | (StateGraph Authority)|
+-----------------------+       +-----------+-----------+
                                            |
         +----------------------------------+----------------------------------+
         |                                  |                                  |
         v                                  v                                  v
+-------------------+              +-------------------+              +-------------------+
| Profile Analyst   |              |  Match & Ranking  |              | Document Agent    |
| (Fact Extraction) |              |  (Scoring & Gaps) |              | (Evidence-Grounded|
+-------------------+              +-------------------+              +-------------------+
```

## 2. Open Source Tech Stack

AgentFlow is built 100% on open-source technologies:
- **Backend & Orchestration**: Python 3.11+, FastAPI, Pydantic v2, LangGraph, LangChain-Core
- **Database & Persistence**: PostgreSQL 16 with `pgvector` for vector similarity search and SQLAlchemy 2.0 (asyncpg) for relational data
- **Document Ingestion**: `pypdf`, `pdfplumber` for local, zero-leak text extraction
- **Frontend Dashboard**: Next.js 14 (App Router), React 18, Tailwind CSS, Lucide React
- **Containerization & CI**: Docker, Docker Compose, GitHub Actions

## 3. Human Approval Gates & Safety Architecture

AgentFlow strictly enforces the following non-bypassable constraints:
1. **Separation of Facts from Inferences**: Resume facts extracted with verbatim evidence citations are distinguished from model inferences. The system never treats an unconfirmed inference as a verified fact.
2. **Consequential Action Gates**: Consequential actions (confirming profile facts, shortlisting jobs, approving tailored resumes/cover letters, and submitting applications) require an explicit user confirmation control in the UI.
3. **No Unattended Automation**: AgentFlow never performs unattended mass applications or bypasses CAPTCHAs, bot controls, or login challenges. Unsupported or protected sites fall back to a manual handoff package.
4. **Idempotent Execution**: Application submissions are guarded by an idempotency key tied to `(user_id, job_id, approved_package_hash)`.

