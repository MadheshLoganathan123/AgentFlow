/**
 * AgentFlow API client — typed wrappers for all Phase 5/6 backend endpoints.
 * Uses the Next.js public env var NEXT_PUBLIC_API_URL (default: http://localhost:8000).
 */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options?.headers ?? {}) },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${options?.method ?? "GET"} ${path} → ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ─── Type contracts (mirror backend Pydantic models) ─────────────────────────

export interface ScoreBreakdown {
  skill_match_score: number;
  seniority_score: number;
  location_mode_score: number;
  salary_alignment_score: number | null;
  work_authorization_score: number;
  recency_score: number;
  industry_preference_score: number;
  composite_score: number;
}

export interface MatchExplanation {
  candidate_id: string;
  job_id: string;
  composite_score: number;
  score_breakdown: ScoreBreakdown;
  strengths: string[];
  gaps: string[];
  uncertainties: string[];
  matched_requirements: Array<{ skill: string; status: string }>;
  recommendation: "strong_match" | "potential_match" | "gap_heavy" | "not_recommended";
}

export interface JobListing {
  id?: string;
  title: string;
  organization: string;
  location: string;
  work_mode: string;
  seniority: string;
  salary_min?: number;
  salary_max?: number;
  salary_currency?: string;
  skills_required: string[];
  skills_preferred: string[];
  description_text: string;
  destination_url: string;
  source_name: string;
  content_hash: string;
  posted_at?: string;
  retrieved_at?: string;
  is_active: boolean;
}

export interface RankedMatch {
  job: JobListing;
  explanation: MatchExplanation;
}

export interface DiscoveryStatusResponse {
  workflow_id: string;
  user_id: string;
  current_stage: string;
  is_paused: boolean;
  pause_reason?: string;
  total_raw_jobs: number;
  total_normalized_jobs: number;
  total_ranked_matches: number;
  shortlist_approved: boolean;
  errors: string[];
}

export interface MatchSummaryItem {
  job_id?: string;
  title: string;
  organization: string;
  location: string;
  work_mode: string;
  seniority: string;
  composite_score: number;
  recommendation: string;
  strengths: string[];
  gaps: string[];
}

export interface ShortlistConfirmedResponse {
  workflow_id: string;
  current_stage: string;
  is_paused: boolean;
  shortlist_approved: boolean;
  shortlisted_job_ids: string[];
  dismissed_job_ids: string[];
  audit_trail_length: number;
}

export interface SavedJobResponse {
  id: string;
  user_id: string;
  job_id: string;
  status: string;
  user_notes?: string;
  created_at?: string;
  updated_at?: string;
}

// ─── Discovery Workflow API ───────────────────────────────────────────────────

export const discoveryApi = {
  start: (body: {
    workflow_id?: string;
    user_id: string;
    extracted_profile?: Record<string, unknown>;
    raw_job_payloads?: unknown[];
    discovery_query?: string;
    discovery_location?: string;
    discovery_work_mode?: string;
    discovery_seniority?: string;
    discovery_min_salary?: number;
    discovery_max_salary?: number;
    discovery_limit?: number;
  }) =>
    request<DiscoveryStatusResponse>("/api/v1/discovery/start", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  status: (workflowId: string) =>
    request<DiscoveryStatusResponse>(`/api/v1/discovery/${workflowId}/status`),

  matches: (workflowId: string) =>
    request<MatchSummaryItem[]>(`/api/v1/discovery/${workflowId}/matches`),

  approveShortlist: (
    workflowId: string,
    body: {
      shortlisted_job_ids: string[];
      dismissed_job_ids: string[];
      user_feedback?: string;
    }
  ) =>
    request<ShortlistConfirmedResponse>(
      `/api/v1/discovery/${workflowId}/approve-shortlist`,
      { method: "POST", body: JSON.stringify(body) }
    ),

  shortlisted: (workflowId: string) =>
    request<MatchSummaryItem[]>(`/api/v1/discovery/${workflowId}/shortlisted`),
};

// ─── Jobs Search API ──────────────────────────────────────────────────────────

export const jobsApi = {
  search: (params: {
    query?: string;
    organization?: string;
    work_mode?: string;
    seniority?: string;
    min_salary?: number;
    max_salary?: number;
    limit?: number;
    offset?: number;
  }) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
    });
    return request<JobListing[]>(`/api/v1/jobs/search?${qs.toString()}`);
  },

  action: (
    jobId: string,
    body: { user_id: string; status: string; notes?: string }
  ) =>
    request<SavedJobResponse>(`/api/v1/jobs/${jobId}/action`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  saved: (userId: string, status?: string) => {
    const qs = new URLSearchParams({ user_id: userId });
    if (status) qs.set("status", status);
    return request<SavedJobResponse[]>(`/api/v1/jobs/saved?${qs.toString()}`);
  },

  removeSaved: (jobId: string, userId: string) =>
    request<{ message: string }>(`/api/v1/jobs/${jobId}/saved?user_id=${userId}`, {
      method: "DELETE",
    }),
};

// ─── Documents & Tailoring API (Week 3, Phase 1) ────────────────────────────

export type DiffChangeType = "unchanged" | "added" | "removed" | "modified" | "reordered";

export interface ResumeSectionDiff {
  section_name: string;
  change_type: DiffChangeType;
  original_text?: string | null;
  tailored_text?: string | null;
  explanation: string;
  evidence_links?: Array<{ source_type: string; source_identifier: string; raw_snippet: string }>;
}

export interface ResumeDiffAnalysis {
  base_word_count: number;
  tailored_word_count: number;
  emphasized_skills: string[];
  deprioritized_skills: string[];
  section_diffs: ResumeSectionDiff[];
  unsupported_claims: string[];
  change_summary: string;
}

export interface TailoredResume {
  job_id: string;
  job_title: string;
  organization: string;
  candidate_name: string;
  professional_summary: string;
  emphasized_skills: string[];
  other_skills: string[];
  experience_entries: Array<{
    company: string;
    title: string;
    location?: string;
    start_date?: string;
    end_date?: string;
    is_current: boolean;
    highlights: string[];
    skills_used?: string[];
  }>;
  education_entries: Array<{
    institution: string;
    degree: string;
    field_of_study?: string;
    graduation_year?: number;
  }>;
  full_markdown_text: string;
  diff_analysis: ResumeDiffAnalysis;
  changed_sections: string[];
  evidence_links: Array<{ source_type: string; source_identifier: string; raw_snippet: string }>;
  unsupported_claim_warnings: string[];
  is_grounded: boolean;
}

export interface TailorResumeResponse {
  tailored_resume: TailoredResume;
  package_id?: string | null;
  package?: any;
  message: string;
}

// ─── Cover Letter & Application Answers Contracts (Week 3, Phase 2) ──────────

export interface CoverLetterParagraph {
  paragraph_type: string;
  text: string;
  evidence_links?: Array<{ source_type: string; source_identifier: string; raw_snippet: string }>;
  grounded_claims: string[];
  unsupported_claims: string[];
}

export interface CoverLetter {
  job_id: string;
  job_title: string;
  organization: string;
  candidate_name: string;
  salutation: string;
  paragraphs: CoverLetterParagraph[];
  full_text: string;
  evidence_links: Array<{ source_type: string; source_identifier: string; raw_snippet: string }>;
  unsupported_claim_warnings: string[];
  quality_score: number;
  is_grounded: boolean;
}

export interface ApplicationQuestionAnswer {
  question_id: string;
  question: string;
  answer: string;
  confidence_score: number;
  evidence_links: Array<{ source_type: string; source_identifier: string; raw_snippet: string }>;
  requires_user_input: boolean;
  missing_evidence_reason?: string | null;
  unsupported_claim_warnings: string[];
}

export interface ApplicationQuestionSet {
  job_id: string;
  answers: ApplicationQuestionAnswer[];
  total_questions: number;
  requires_user_input_count: number;
  unsupported_claims_count: number;
}

export interface PolicyViolation {
  check_type: string;
  severity: "info" | "warning" | "blocker";
  message: string;
  offending_field_or_text?: string | null;
  remediation_hint?: string | null;
}

export interface PolicyReviewResult {
  is_safe_to_proceed: boolean;
  overall_quality_score: number;
  violations: PolicyViolation[];
  requires_human_approval: boolean;
  approval_gate_reason?: string | null;
  redactions: Array<{ field_name: string; redaction_type: string; redacted_preview: string }>;
  audit_metadata: Record<string, any>;
}

export const documentsApi = {
  tailorResume: (body: {
    user_id: string;
    job_id?: string;
    candidate_profile?: any;
    job_listing?: any;
    save_to_package?: boolean;
  }) =>
    request<TailorResumeResponse>("/api/v1/documents/tailor-resume", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  compareResume: (body: { candidate_profile: any; job_listing: any }) =>
    request<ResumeDiffAnalysis>("/api/v1/documents/compare-resume", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  generateCoverLetter: (body: {
    user_id: string;
    job_id?: string;
    candidate_profile?: any;
    job_listing?: any;
    package_id?: string;
  }) =>
    request<CoverLetter>("/api/v1/documents/generate-cover-letter", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  draftAnswers: (body: {
    user_id: string;
    job_id?: string;
    candidate_profile?: any;
    job_listing?: any;
    custom_questions?: string[];
    package_id?: string;
  }) =>
    request<ApplicationQuestionSet>("/api/v1/documents/draft-answers", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  reviewPackage: (body: { user_id: string; package_id: string }) =>
    request<PolicyReviewResult>("/api/v1/documents/review-package", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getPackage: (packageId: string, userId: string) =>
    request<any>(`/api/v1/documents/packages/${packageId}?user_id=${userId}`),

  getPackageByJob: (jobId: string, userId: string) =>
    request<any>(`/api/v1/documents/packages/by-job/${jobId}?user_id=${userId}`),

  approvePackage: (packageId: string, userId: string, isApproved: boolean = true) =>
    request<{ id: string; user_id: string; is_user_approved: boolean; message: string }>(
      `/api/v1/documents/packages/${packageId}/approve`,
      {
        method: "POST",
        body: JSON.stringify({ user_id: userId, is_approved: isApproved }),
      }
    ),
};

// ─── Professional Email Drafting Contracts (Week 3, Phase 3) ─────────────────

export type EmailType =
  | "recruiter_outreach"
  | "referral_request"
  | "hiring_manager_note"
  | "thank_you"
  | "follow_up";

export type EmailTone = "professional" | "conversational" | "executive";

export interface EmailVariantItem {
  tone: EmailTone;
  subject: string;
  body: string;
  call_to_action: string;
}

export interface EmailDraft {
  id?: string;
  user_id?: string;
  job_id?: string;
  email_type: EmailType;
  recipient_name?: string | null;
  recipient_role?: string | null;
  subject: string;
  body: string;
  call_to_action: string;
  tone: string;
  recipient_assumptions: string[];
  personalization_evidence: Array<{ source_type: string; source_identifier: string; raw_snippet: string }>;
  missing_recipient_warnings: string[];
  variants: string[];
  structured_variants?: EmailVariantItem[];
  is_approved_by_user: boolean;
}

export const emailsApi = {
  generate: (body: {
    user_id: string;
    job_id?: string;
    email_type?: EmailType;
    recipient_name?: string;
    recipient_role?: string;
    tone?: EmailTone;
    extra_context?: string;
    candidate_profile?: any;
    job_listing?: any;
    save_to_drafts?: boolean;
  }) =>
    request<EmailDraft>("/api/v1/emails/generate", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  listDrafts: (userId: string, jobId?: string, emailType?: string) => {
    const qs = new URLSearchParams({ user_id: userId });
    if (jobId) qs.set("job_id", jobId);
    if (emailType) qs.set("email_type", emailType);
    return request<EmailDraft[]>(`/api/v1/emails/drafts?${qs.toString()}`);
  },

  getDraft: (draftId: string, userId: string) =>
    request<EmailDraft>(`/api/v1/emails/drafts/${draftId}?user_id=${userId}`),

  updateDraft: (
    draftId: string,
    body: {
      user_id: string;
      subject?: string;
      body?: string;
      call_to_action?: string;
      tone?: string;
      is_approved_by_user?: boolean;
    }
  ) =>
    request<EmailDraft>(`/api/v1/emails/drafts/${draftId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  deleteDraft: (draftId: string, userId: string) =>
    request<{ message: string; id: string }>(
      `/api/v1/emails/drafts/${draftId}?user_id=${userId}`,
      { method: "DELETE" }
    ),
};
