# Week 3 — Tailored Documents, Email Drafts, and Interview Research
## Detailed 6-Phase Implementation Breakdown

**Overall Goal of Week 3**: A shortlisted role produces an application package and preparation workspace. Grounded, explainable, zero-hallucination document tailoring, non-bypassable human review gates, structured email drafts, allowlisted web research, and interactive interview preparation.

---

### [x] Phase 1: Resume Tailoring & Visible Diff Analysis Engine (COMPLETED)
- **Goal**: Generate targeted resume variants tailored to shortlisted job listings strictly grounded in confirmed profile facts, with line-by-line diff summaries.
- **Scope**:
  - `TailoredResume`, `ResumeDiffAnalysis`, `ResumeSectionDiff`, `DiffChangeType` contracts with section diffs, emphasized skills, omitted/other skills, and evidence citations.
  - Zero-fabrication enforcement: every tailored bullet links to confirmed profile work experience; missing job requirements are flagged in `unsupported_claim_warnings` and never hallucinated.
  - `ResumeTailoringService` featuring hybrid Hugging Face generation with deterministic offline fallback and weighted highlight re-ranking.
  - `ApplicationPackageRepository` for database persistence with strict multi-tenant user isolation.
  - REST endpoints under `/api/v1/documents` (`/tailor-resume`, `/compare-resume`, `/packages/{id}`, `/packages/by-job/{id}`, `/packages/{id}/approve`).
  - Typed frontend API client methods in `apps/web/src/lib/api.ts`.
  - Comprehensive unit test suite (`tests/unit/test_resume_tailoring.py`) and user isolation verification (`test_cross_account_package_isolation`).

---

### [x] Phase 2: Fact-Grounded Cover Letter & Application Question Drafter (COMPLETED)
- **Goal**: Produce targeted cover letters and answer common application questions with explicit unsupported-claim warnings and Policy Reviewer quality gates.
- **Scope**:
  - `CoverLetter`, `CoverLetterParagraph`, `ApplicationQuestionAnswer`, and `ApplicationQuestionSet` schemas with paragraph-level provenance linking.
  - `CoverLetterAndQuestionService` with zero-fabrication enforcement: missing candidate skills are excluded and flagged rather than hallucinated.
  - `PolicyReviewerService` (Agent Role 9): audits documents and packages for unsupported claims, phantom employers, unconfirmed degrees, privacy leaks (SSN, credit card, tokens), and suspicious job scam indicators.
  - Question answering engine: provides verified answers for authorization, notice period, compensation, and tech stack; sets `requires_user_input=True` when evidence is missing.
  - REST endpoints: `POST /api/v1/documents/generate-cover-letter`, `POST /api/v1/documents/draft-answers`, `POST /api/v1/documents/review-package`.
  - Frontend TypeScript contracts and `documentsApi` wrappers in `apps/web/src/lib/api.ts`.
  - Exhaustive unit test suite (`tests/unit/test_cover_letter_and_questions.py`) passing 8/8 tests.

---

### [x] Phase 3: Role-Specific Email Generation System (Recruiter, Referral, Follow-Up, Thank-You) (COMPLETED)
- **Goal**: Generate role-specific, high-conversion email drafts for networking and application lifecycle management with strict safety invariants.
- **Scope**:
  - `EmailDraft`, `EmailTone`, `EmailType`, and `EmailVariantItem` contracts supporting 4 core categories:
    1. Recruiter outreach / Hiring manager note (cold/warm)
    2. Referral request (alumni/colleague/connection)
    3. Application follow-up (post-submission status & timeline check)
    4. Post-interview thank-you note (with contextual problem discussion)
  - Strict safety rule: **Never sends automatically**. All drafts are editable and stored in draft status.
  - Recipient assumption & missing recipient validation: alerts user if recipient name is missing and inserts clear placeholder.
  - Personalization evidence linking to confirmed profile facts (`personalization_evidence`).
  - 3 structured tone variants generated per request: `professional`, `conversational`, `executive`.
  - `EmailDraftRepository` with full CRUD and multi-tenant isolation.
  - REST endpoints under `/api/v1/emails`: `POST /generate`, `GET /drafts`, `GET /drafts/{id}`, `PATCH /drafts/{id}`, `DELETE /drafts/{id}`.
  - Frontend TypeScript contracts and `emailsApi` wrapper in `apps/web/src/lib/api.ts`.
  - Exhaustive test suite (`tests/unit/test_email_writer.py`) passing 8/8 tests and user isolation check (`test_cross_account_email_draft_isolation`).

---

### [x] Phase 4: Allowlisted Web Research Tool & Source Citation Cards (COMPLETED)
- **Goal**: Perform grounded research on prospective companies, role tech stacks, and team culture from reputable sources only.
- **Scope**:
  - `WebResearchTool` with strict domain allowlist (official corporate engineering blogs, SEC/EDGAR filings, GitHub, Wikipedia, TechCrunch, Wired, Greenhouse, Lever, and verified enterprise domains).
  - Explicit `DISALLOWED_DOMAINS` blocklist rejecting untrusted origins (4chan, pastebin, scam sites, Tor proxies).
  - Source capture retaining: `source_url`, `source_title`, `source_domain`, `retrieved_at`, `content_excerpt`, SHA-256 `content_hash`, and `source_category`.
  - Deterministic company knowledge base for CloudScale Data Technologies, Synthetix Labs, Google, Meta with verified sources and excerpts.
  - Dynamic fallback for unknown companies synthesizing allowlisted canonical sources.
  - `ResearchSummary` contract segregating `company_specific_sources` (tech stack, culture, milestones) from `general_advice_sources` (STAR method, system design theory).
  - `ResearchSourceRepository` with full CRUD: `save_source` (upsert by company+url), `get_source`, `list_sources` (filterable, paginated), `report_source`, `delete_source`.
  - Enriched DB model `ResearchSourceModel` with `content_hash`, `source_category`, `is_reported`, `report_reason`.
  - REST API under `/api/v1/research`: `POST /company`, `GET /sources`, `GET /sources/{id}`, `POST /sources/{id}/report`, `DELETE /sources/{id}`, `POST /validate-url`.
  - `SourceCitationCards.tsx` frontend component with allowlist badge, company-intel vs. general-prep tabs, SHA-256 hash tooltip, inline Report workflow, and Remove action.
  - TypeScript contracts `ResearchSource`, `ResearchSummary`, `ValidateUrlResponse` and `researchApi` wrappers in `apps/web/src/lib/api.ts`.
  - Comprehensive unit test suite (`tests/unit/test_web_research.py`) — 6/6 tests passed:
    1. `test_domain_allowlist_enforcement` — 13 allowlisted URLs accepted, 10 disallowed/unverified rejected.
    2. `test_validate_url_method` — URL category classification (sec_filing, github, engineering_blog, disallowed).
    3. `test_cryptographic_content_hash` — SHA-256 determinism and tamper-evidence.
    4. `test_research_company_intelligence_segregation` — partition verification, hash presence, allowlist compliance.
    5. `test_research_source_repository_crud` — full CRUD with upsert, report, filtered listing, delete, and 404 confirmation.
    6. `test_research_rest_api_endpoints` — full REST API surface via TestClient with DB session override.

---

### [ ] Phase 5: Interview Preparation Plan & Text-Based Mock Interview Engine
- **Goal**: Produce role- and seniority-tailored interview preparation guides and interactive mock interviews with scoring rubrics.
- **Scope**:
  - `InterviewPlan` generator covering technical, behavioral (STAR method), and domain-specific rounds.
  - Interactive mock interview question evaluator with transparent scoring rubric (1–5 scale across Clarity, Relevance, Depth, Evidence).
  - Feedback generator highlighting candidate strengths, identified gaps, and actionable suggestions (without false hiring guarantees).

---

### [ ] Phase 6: Application Package LangGraph Workflow & Web Dashboard Workspace
- **Goal**: End-to-end orchestration uniting shortlisted roles into full application packages with human approval gate and dashboard view.
- **Scope**:
  - LangGraph `ApplicationPreparationWorkflow` with durable checkpoints and `interrupt_before=["awaiting_package_approval"]`.
  - REST endpoints under `/api/v1/packages` for generating, reviewing, editing, and approving packages.
  - Integration with `apps/web/src/components/ApplicationPackagesView.tsx`: interactive workspace for resume diffs, cover letter review, email templates, research cards, and mock interview practice.
