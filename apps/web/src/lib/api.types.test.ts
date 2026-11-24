/**
 * Phase 6 — TypeScript type-safety checks for the API client lib.
 * These are compile-time-only tests (no runtime dependencies needed).
 * Run as part of `tsc --noEmit` via `npm run build`.
 */

// Verify all exported types are well-formed at import time
import type {
  DiscoveryStatusResponse,
  JobListing,
  MatchExplanation,
  MatchSummaryItem,
  RankedMatch,
  SavedJobResponse,
  ScoreBreakdown,
  ShortlistConfirmedResponse,
} from "@/lib/api";

// ─── Type assertion helpers ───────────────────────────────────────────────────

function assertType<T>(_: T): void {}

// ScoreBreakdown all numeric fields
const sb: ScoreBreakdown = {
  skill_match_score: 95.0,
  seniority_score: 88.0,
  location_mode_score: 90.0,
  salary_alignment_score: null,
  work_authorization_score: 100.0,
  recency_score: 80.0,
  industry_preference_score: 75.0,
  composite_score: 88.3,
};
assertType<ScoreBreakdown>(sb);

// MatchExplanation with all recommendation variants
const explanations: MatchExplanation[] = [
  {
    candidate_id: "cand_01",
    job_id: "job_01",
    composite_score: 92.0,
    score_breakdown: sb,
    strengths: ["Python expertise verified"],
    gaps: [],
    uncertainties: [],
    matched_requirements: [{ skill: "Python", status: "verified" }],
    recommendation: "strong_match",
  },
  {
    candidate_id: "cand_02",
    job_id: "job_02",
    composite_score: 68.0,
    score_breakdown: { ...sb, composite_score: 68.0 },
    strengths: [],
    gaps: ["Missing Kubernetes"],
    uncertainties: ["Work authorization unconfirmed"],
    matched_requirements: [],
    recommendation: "potential_match",
  },
];
assertType<MatchExplanation[]>(explanations);

// JobListing
const job: JobListing = {
  id: "job_uuid_01",
  title: "Senior Backend Engineer",
  organization: "StreamScale",
  location: "San Francisco, CA",
  work_mode: "remote",
  seniority: "senior",
  salary_min: 160000,
  salary_max: 210000,
  salary_currency: "USD",
  skills_required: ["Python", "FastAPI"],
  skills_preferred: ["Kubernetes"],
  description_text: "Build scalable microservices.",
  destination_url: "https://streamscale.io/careers/1",
  source_name: "greenhouse",
  content_hash: "abc123sha256",
  is_active: true,
};
assertType<JobListing>(job);

// RankedMatch
const rm: RankedMatch = { job, explanation: explanations[0] };
assertType<RankedMatch>(rm);

// DiscoveryStatusResponse
const statusRes: DiscoveryStatusResponse = {
  workflow_id: "wf_01",
  user_id: "usr_01",
  current_stage: "awaiting_shortlist_approval",
  is_paused: true,
  pause_reason: "Human shortlist approval required",
  total_raw_jobs: 20,
  total_normalized_jobs: 18,
  total_ranked_matches: 15,
  shortlist_approved: false,
  errors: [],
};
assertType<DiscoveryStatusResponse>(statusRes);

// MatchSummaryItem
const matchItem: MatchSummaryItem = {
  job_id: "job_01",
  title: "Senior Backend Engineer",
  organization: "StreamScale",
  location: "Remote",
  work_mode: "remote",
  seniority: "senior",
  composite_score: 92.0,
  recommendation: "strong_match",
  strengths: ["Python expertise"],
  gaps: [],
};
assertType<MatchSummaryItem>(matchItem);

// ShortlistConfirmedResponse
const confirmedRes: ShortlistConfirmedResponse = {
  workflow_id: "wf_01",
  current_stage: "shortlist_confirmed",
  is_paused: false,
  shortlist_approved: true,
  shortlisted_job_ids: ["job_01", "job_03"],
  dismissed_job_ids: ["job_02"],
  audit_trail_length: 6,
};
assertType<ShortlistConfirmedResponse>(confirmedRes);

// SavedJobResponse
const savedRes: SavedJobResponse = {
  id: "saved_uuid_01",
  user_id: "usr_01",
  job_id: "job_01",
  status: "shortlisted",
  user_notes: "Top priority role",
  created_at: "2026-11-21T10:00:00Z",
  updated_at: "2026-11-21T10:05:00Z",
};
assertType<SavedJobResponse>(savedRes);

export {};
