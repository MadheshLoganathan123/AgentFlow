"use client";

import React, { useState, useCallback } from "react";
import {
  Search,
  Filter,
  Zap,
  MapPin,
  Building,
  DollarSign,
  Clock,
  CheckCircle,
  AlertCircle,
  Sparkles,
  Bookmark,
  ThumbsDown,
  ExternalLink,
  Briefcase,
  Loader2,
  ChevronDown,
  ChevronUp,
  TrendingUp,
  Shield,
  Star,
  X,
  ListChecks,
  RefreshCw,
  SlidersHorizontal,
} from "lucide-react";
import { discoveryApi, MatchSummaryItem } from "@/lib/api";

// ─── Types ────────────────────────────────────────────────────────────────────

type WorkflowPhase =
  | "idle"
  | "launching"
  | "paused_at_gate"
  | "confirming"
  | "confirmed";

interface FilterState {
  query: string;
  workMode: string;
  seniority: string;
  minSalary: string;
  maxSalary: string;
}

const WORK_MODES = ["all", "remote", "hybrid", "onsite"];
const SENIORITIES = ["all", "entry", "mid", "senior", "lead", "principal"];

const RECOMMENDATION_META: Record<
  string,
  { label: string; color: string; bg: string; border: string; icon: React.FC<{ className?: string }> }
> = {
  strong_match: {
    label: "Strong Match",
    color: "text-accent-emerald",
    bg: "bg-accent-emerald/10",
    border: "border-accent-emerald/30",
    icon: Star,
  },
  potential_match: {
    label: "Potential Match",
    color: "text-accent-primary",
    bg: "bg-accent-primary/10",
    border: "border-accent-primary/30",
    icon: TrendingUp,
  },
  gap_heavy: {
    label: "Gap Heavy",
    color: "text-accent-amber",
    bg: "bg-accent-amber/10",
    border: "border-accent-amber/30",
    icon: AlertCircle,
  },
  not_recommended: {
    label: "Not Recommended",
    color: "text-content-muted",
    bg: "bg-app-cardSecondary",
    border: "border-border-subtle",
    icon: Shield,
  },
};

// ─── Score Bar Component ──────────────────────────────────────────────────────

const ScoreBar: React.FC<{ label: string; value: number; color: string }> = ({
  label,
  value,
  color,
}) => (
  <div className="space-y-1">
    <div className="flex justify-between text-[11px]">
      <span className="text-content-muted">{label}</span>
      <span className={`font-bold font-mono ${color}`}>{Math.round(value)}%</span>
    </div>
    <div className="h-1.5 bg-app-cardSecondary rounded-full overflow-hidden">
      <div
        className={`h-full rounded-full transition-all duration-700 ${color.replace("text-", "bg-")}`}
        style={{ width: `${Math.min(100, value)}%` }}
      />
    </div>
  </div>
);

// ─── Match Card Component ─────────────────────────────────────────────────────

const MatchCard: React.FC<{
  match: MatchSummaryItem;
  isShortlisted: boolean;
  isDismissed: boolean;
  onShortlist: () => void;
  onDismiss: () => void;
}> = ({ match, isShortlisted, isDismissed, onShortlist, onDismiss }) => {
  const [expanded, setExpanded] = useState(false);
  const meta = RECOMMENDATION_META[match.recommendation] ?? RECOMMENDATION_META.gap_heavy;
  const Icon = meta.icon;

  const scoreColor =
    match.composite_score >= 80
      ? "text-accent-emerald"
      : match.composite_score >= 65
      ? "text-accent-primary"
      : match.composite_score >= 45
      ? "text-accent-amber"
      : "text-content-muted";

  if (isDismissed) return null;

  return (
    <div
      className={`bg-app-card rounded-xl border p-5 shadow-dark-sm space-y-4 transition-all duration-200 ${
        isShortlisted
          ? "border-accent-emerald/40 shadow-[0_0_0_1px_rgba(16,185,129,0.15)]"
          : "border-border-default hover:border-border-active/40"
      }`}
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          {/* Match badge + recommendation pill */}
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <span
              className={`inline-flex items-center gap-1 text-xs font-bold px-2.5 py-0.5 rounded-full border ${meta.bg} ${meta.color} ${meta.border}`}
            >
              <Icon className="w-3 h-3" />
              {meta.label}
            </span>
            <span
              className={`text-sm font-black font-mono ${scoreColor}`}
            >
              {Math.round(match.composite_score)}%
            </span>
            {isShortlisted && (
              <span className="text-[10px] font-semibold text-accent-emerald bg-accent-emerald/10 border border-accent-emerald/30 px-2 py-0.5 rounded-full flex items-center gap-1">
                <Bookmark className="w-2.5 h-2.5" />
                Shortlisted
              </span>
            )}
          </div>

          <h3 className="text-base font-bold text-content-primary leading-tight truncate">
            {match.title}
          </h3>

          <div className="flex flex-wrap items-center gap-3 text-xs text-content-secondary mt-1.5">
            <span className="flex items-center gap-1">
              <Building className="w-3.5 h-3.5 text-content-muted" />
              {match.organization}
            </span>
            <span className="flex items-center gap-1">
              <MapPin className="w-3.5 h-3.5 text-content-muted" />
              {match.location}
            </span>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-app-cardSecondary border border-border-subtle text-[11px] capitalize">
              {match.work_mode}
            </span>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-app-cardSecondary border border-border-subtle text-[11px] capitalize">
              {match.seniority}
            </span>
          </div>
        </div>

        {/* Composite score ring */}
        <div className="flex-shrink-0 flex flex-col items-center justify-center w-16 h-16 rounded-full border-2 border-border-subtle bg-app-cardSecondary">
          <span className={`text-lg font-black font-mono leading-none ${scoreColor}`}>
            {Math.round(match.composite_score)}
          </span>
          <span className="text-[9px] text-content-muted uppercase tracking-wide">score</span>
        </div>
      </div>

      {/* Strengths + Gaps */}
      {(match.strengths.length > 0 || match.gaps.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-3 border-t border-border-subtle text-xs">
          {match.strengths.length > 0 && (
            <div>
              <p className="text-[10px] font-bold uppercase text-content-muted mb-1.5 flex items-center gap-1">
                <CheckCircle className="w-3 h-3 text-accent-emerald" />
                Strengths
              </p>
              <ul className="space-y-1">
                {match.strengths.slice(0, 3).map((s, i) => (
                  <li key={i} className="text-[11px] text-content-secondary flex items-start gap-1.5">
                    <span className="text-accent-emerald mt-0.5">✓</span>
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {match.gaps.length > 0 && (
            <div>
              <p className="text-[10px] font-bold uppercase text-content-muted mb-1.5 flex items-center gap-1">
                <AlertCircle className="w-3 h-3 text-accent-amber" />
                Gaps
              </p>
              <ul className="space-y-1">
                {match.gaps.slice(0, 3).map((g, i) => (
                  <li key={i} className="text-[11px] text-content-secondary flex items-start gap-1.5">
                    <span className="text-accent-amber mt-0.5">△</span>
                    {g}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Expandable score breakdown */}
      <button
        onClick={() => setExpanded((p) => !p)}
        className="w-full flex items-center justify-between text-[11px] text-content-muted hover:text-content-primary transition pt-1 border-t border-border-subtle"
      >
        <span className="flex items-center gap-1">
          <SlidersHorizontal className="w-3 h-3" />
          Score breakdown
        </span>
        {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
      </button>

      {expanded && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2 pt-1 pb-1">
          <ScoreBar label="Skills Match" value={match.composite_score} color={scoreColor} />
          <ScoreBar
            label="Recommendation"
            value={
              match.recommendation === "strong_match"
                ? 95
                : match.recommendation === "potential_match"
                ? 72
                : match.recommendation === "gap_heavy"
                ? 48
                : 20
            }
            color={scoreColor}
          />
        </div>
      )}

      {/* Action buttons */}
      <div className="flex items-center justify-between pt-1">
        <span className="text-[10px] text-content-muted flex items-center gap-1">
          <Sparkles className="w-3 h-3 text-accent-purple" />
          AI-grounded match evaluation
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={onDismiss}
            className="p-2 rounded-lg bg-app-cardSecondary hover:bg-app-panel text-content-muted hover:text-accent-rose border border-border-subtle transition"
            title="Dismiss"
          >
            <ThumbsDown className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={onShortlist}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition border ${
              isShortlisted
                ? "bg-accent-emerald/20 text-accent-emerald border-accent-emerald/40 hover:bg-accent-emerald/30"
                : "bg-accent-primary hover:bg-blue-600 text-white border-transparent shadow-dark-sm"
            }`}
          >
            <Bookmark className="w-3.5 h-3.5" />
            {isShortlisted ? "Shortlisted ✓" : "Shortlist"}
          </button>
        </div>
      </div>
    </div>
  );
};

// ─── Discovery Launcher Panel ─────────────────────────────────────────────────

const DiscoveryLauncher: React.FC<{
  onLaunch: (filters: FilterState) => void;
  isLoading: boolean;
}> = ({ onLaunch, isLoading }) => {
  const [filters, setFilters] = useState<FilterState>({
    query: "",
    workMode: "all",
    seniority: "all",
    minSalary: "",
    maxSalary: "",
  });

  const set = (k: keyof FilterState, v: string) =>
    setFilters((p) => ({ ...p, [k]: v }));

  return (
    <div className="bg-app-card rounded-xl border border-border-default p-4 shadow-dark-sm space-y-4">
      {/* Title row */}
      <div className="flex items-center gap-2">
        <Zap className="w-4 h-4 text-accent-primary" />
        <h3 className="text-sm font-bold text-content-primary">
          Discover & Rank Jobs
        </h3>
        <span className="ml-auto text-[10px] text-content-muted border border-border-subtle rounded-full px-2 py-0.5">
          Powered by LangGraph
        </span>
      </div>

      {/* Filters row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Search */}
        <div className="sm:col-span-2 relative">
          <Search className="w-3.5 h-3.5 text-content-muted absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={filters.query}
            onChange={(e) => set("query", e.target.value)}
            placeholder="Role, skill, or company keyword…"
            className="w-full text-xs pl-9 pr-3 py-2 bg-app-cardSecondary border border-border-default rounded-lg text-content-primary placeholder:text-content-muted focus:outline-none focus:border-border-active focus:ring-1 focus:ring-accent-primary"
          />
        </div>

        {/* Work mode */}
        <select
          value={filters.workMode}
          onChange={(e) => set("workMode", e.target.value)}
          className="text-xs px-3 py-2 bg-app-cardSecondary border border-border-default rounded-lg text-content-primary focus:outline-none focus:border-border-active capitalize"
        >
          {WORK_MODES.map((m) => (
            <option key={m} value={m} className="bg-app-card">
              {m === "all" ? "Any Work Mode" : m.charAt(0).toUpperCase() + m.slice(1)}
            </option>
          ))}
        </select>

        {/* Seniority */}
        <select
          value={filters.seniority}
          onChange={(e) => set("seniority", e.target.value)}
          className="text-xs px-3 py-2 bg-app-cardSecondary border border-border-default rounded-lg text-content-primary focus:outline-none focus:border-border-active capitalize"
        >
          {SENIORITIES.map((s) => (
            <option key={s} value={s} className="bg-app-card">
              {s === "all" ? "Any Seniority" : s.charAt(0).toUpperCase() + s.slice(1)}
            </option>
          ))}
        </select>
      </div>

      {/* Salary range + Launch button */}
      <div className="flex flex-col sm:flex-row items-center gap-3">
        <div className="flex items-center gap-2 flex-1">
          <DollarSign className="w-3.5 h-3.5 text-content-muted flex-shrink-0" />
          <input
            type="number"
            value={filters.minSalary}
            onChange={(e) => set("minSalary", e.target.value)}
            placeholder="Min salary"
            className="w-full text-xs px-3 py-2 bg-app-cardSecondary border border-border-default rounded-lg text-content-primary placeholder:text-content-muted focus:outline-none focus:border-border-active"
          />
          <span className="text-content-muted text-xs">–</span>
          <input
            type="number"
            value={filters.maxSalary}
            onChange={(e) => set("maxSalary", e.target.value)}
            placeholder="Max salary"
            className="w-full text-xs px-3 py-2 bg-app-cardSecondary border border-border-default rounded-lg text-content-primary placeholder:text-content-muted focus:outline-none focus:border-border-active"
          />
        </div>

        <button
          onClick={() => onLaunch(filters)}
          disabled={isLoading}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent-primary hover:bg-blue-600 disabled:opacity-60 text-white text-xs font-semibold transition shadow-dark-sm whitespace-nowrap"
        >
          {isLoading ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Zap className="w-3.5 h-3.5" />
          )}
          {isLoading ? "Discovering…" : "Run Discovery"}
        </button>
      </div>
    </div>
  );
};

// ─── Shortlist Confirm Banner ─────────────────────────────────────────────────

const ShortlistConfirmBanner: React.FC<{
  shortlistedCount: number;
  dismissedCount: number;
  onConfirm: () => void;
  onReset: () => void;
  isConfirming: boolean;
  isConfirmed: boolean;
}> = ({
  shortlistedCount,
  dismissedCount,
  onConfirm,
  onReset,
  isConfirming,
  isConfirmed,
}) => {
  if (isConfirmed) {
    return (
      <div className="bg-accent-emerald/10 border border-accent-emerald/30 rounded-xl p-4 flex items-center gap-3">
        <CheckCircle className="w-5 h-5 text-accent-emerald flex-shrink-0" />
        <div>
          <p className="text-sm font-semibold text-accent-emerald">
            Shortlist Confirmed ✓
          </p>
          <p className="text-xs text-content-secondary mt-0.5">
            {shortlistedCount} job{shortlistedCount !== 1 ? "s" : ""} shortlisted and
            saved to your profile. The workflow has been marked complete.
          </p>
        </div>
        <button
          onClick={onReset}
          className="ml-auto p-1.5 rounded-lg hover:bg-app-panel text-content-muted hover:text-content-primary transition"
          title="Start new discovery"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>
    );
  }

  return (
    <div className="bg-app-card border border-accent-primary/30 rounded-xl p-4 flex flex-col sm:flex-row items-center gap-4 shadow-dark-sm">
      <div className="flex items-center gap-3 flex-1">
        <ListChecks className="w-5 h-5 text-accent-primary flex-shrink-0" />
        <div>
          <p className="text-sm font-semibold text-content-primary">
            Review Ready — Confirm Your Shortlist
          </p>
          <p className="text-xs text-content-secondary mt-0.5">
            <span className="text-accent-emerald font-semibold">{shortlistedCount}</span> shortlisted ·{" "}
            <span className="text-accent-amber font-semibold">{dismissedCount}</span> dismissed
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={onReset}
          className="px-3 py-1.5 rounded-lg text-xs font-medium text-content-secondary border border-border-subtle hover:border-border-active transition"
        >
          Reset
        </button>
        <button
          onClick={onConfirm}
          disabled={isConfirming || shortlistedCount === 0}
          className="flex items-center gap-2 px-4 py-1.5 rounded-lg bg-accent-emerald hover:bg-emerald-500 disabled:opacity-60 text-white text-xs font-semibold transition shadow-dark-sm"
        >
          {isConfirming ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <CheckCircle className="w-3.5 h-3.5" />
          )}
          Confirm Shortlist
        </button>
      </div>
    </div>
  );
};

// ─── Main JobMatchesView ──────────────────────────────────────────────────────

export const JobMatchesView: React.FC = () => {
  const [phase, setPhase] = useState<WorkflowPhase>("idle");
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [matches, setMatches] = useState<MatchSummaryItem[]>([]);
  const [shortlisted, setShortlisted] = useState<Record<string, boolean>>({});
  const [dismissed, setDismissed] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);
  const [statusMsg, setStatusMsg] = useState<string>("");

  // Client-side filter state (applied on top of backend matches)
  const [localFilter, setLocalFilter] = useState("");

  const handleLaunch = useCallback(async (filters: FilterState) => {
    setPhase("launching");
    setError(null);
    setMatches([]);
    setShortlisted({});
    setDismissed({});
    setStatusMsg("Launching job discovery workflow…");

    try {
      const wfId = `wf_ui_${Date.now()}`;
      setWorkflowId(wfId);

      setStatusMsg("Ingesting and normalizing job postings…");
      const statusRes = await discoveryApi.start({
        workflow_id: wfId,
        user_id: "usr_dashboard_01",
        discovery_query: filters.query || undefined,
        discovery_work_mode: filters.workMode !== "all" ? filters.workMode : undefined,
        discovery_seniority: filters.seniority !== "all" ? filters.seniority : undefined,
        discovery_min_salary: filters.minSalary ? parseInt(filters.minSalary) : undefined,
        discovery_max_salary: filters.maxSalary ? parseInt(filters.maxSalary) : undefined,
        discovery_limit: 20,
      });

      setStatusMsg(`Scoring ${statusRes.total_normalized_jobs} jobs…`);

      const matchList = await discoveryApi.matches(wfId);
      setMatches(matchList);
      setPhase("paused_at_gate");
      setStatusMsg(
        `${matchList.length} ranked matches ready for review — select your shortlist`
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      setPhase("idle");
      setStatusMsg("");
    }
  }, []);

  const toggleShortlist = useCallback((jobId: string) => {
    setShortlisted((p) => ({ ...p, [jobId]: !p[jobId] }));
  }, []);

  const toggleDismiss = useCallback((jobId: string) => {
    setDismissed((p) => ({ ...p, [jobId]: !p[jobId] }));
    // Auto-unshortlist if dismissed
    setShortlisted((p) => ({ ...p, [jobId]: false }));
  }, []);

  const handleConfirmShortlist = useCallback(async () => {
    if (!workflowId) return;
    setPhase("confirming");
    setError(null);

    const shortlistedIds = Object.entries(shortlisted)
      .filter(([, v]) => v)
      .map(([k]) => k);
    const dismissedIds = Object.entries(dismissed)
      .filter(([, v]) => v)
      .map(([k]) => k);

    try {
      await discoveryApi.approveShortlist(workflowId, {
        shortlisted_job_ids: shortlistedIds,
        dismissed_job_ids: dismissedIds,
        user_feedback: "Confirmed via AgentFlow dashboard",
      });
      setPhase("confirmed");
      setStatusMsg("Shortlist confirmed and saved to your profile.");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      setPhase("paused_at_gate");
    }
  }, [workflowId, shortlisted, dismissed]);

  const handleReset = () => {
    setPhase("idle");
    setWorkflowId(null);
    setMatches([]);
    setShortlisted({});
    setDismissed({});
    setError(null);
    setStatusMsg("");
    setLocalFilter("");
  };

  const shortlistedCount = Object.values(shortlisted).filter(Boolean).length;
  const dismissedCount = Object.values(dismissed).filter(Boolean).length;

  const displayedMatches = matches.filter((m) => {
    if (!localFilter) return true;
    const q = localFilter.toLowerCase();
    return (
      m.title.toLowerCase().includes(q) ||
      m.organization.toLowerCase().includes(q) ||
      m.location.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-5">
      {/* Discovery launcher */}
      <DiscoveryLauncher
        onLaunch={handleLaunch}
        isLoading={phase === "launching"}
      />

      {/* Error state */}
      {error && (
        <div className="bg-accent-rose/10 border border-accent-rose/30 rounded-xl p-3 flex items-start gap-2">
          <AlertCircle className="w-4 h-4 text-accent-rose flex-shrink-0 mt-0.5" />
          <div className="flex-1 text-xs text-content-secondary">
            <span className="font-semibold text-accent-rose">Error: </span>
            {error}
            <span className="text-content-muted ml-1">
              (Ensure the AgentFlow API is running on port 8000)
            </span>
          </div>
          <button onClick={() => setError(null)}>
            <X className="w-3.5 h-3.5 text-content-muted hover:text-content-primary" />
          </button>
        </div>
      )}

      {/* Status message */}
      {statusMsg && phase === "launching" && (
        <div className="flex items-center gap-2 text-xs text-content-secondary bg-app-card border border-border-subtle rounded-lg px-4 py-3">
          <Loader2 className="w-3.5 h-3.5 text-accent-primary animate-spin" />
          {statusMsg}
        </div>
      )}

      {/* Shortlist confirm banner */}
      {(phase === "paused_at_gate" || phase === "confirming" || phase === "confirmed") && (
        <ShortlistConfirmBanner
          shortlistedCount={shortlistedCount}
          dismissedCount={dismissedCount}
          onConfirm={handleConfirmShortlist}
          onReset={handleReset}
          isConfirming={phase === "confirming"}
          isConfirmed={phase === "confirmed"}
        />
      )}

      {/* Results header + local filter */}
      {matches.length > 0 && (
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm">
            <span className="font-semibold text-content-primary">
              {matches.length} Ranked Matches
            </span>
            {shortlistedCount > 0 && (
              <span className="text-xs text-accent-emerald bg-accent-emerald/10 border border-accent-emerald/20 px-2 py-0.5 rounded-full">
                {shortlistedCount} shortlisted
              </span>
            )}
          </div>
          <div className="relative w-full sm:w-72">
            <Filter className="w-3.5 h-3.5 text-content-muted absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={localFilter}
              onChange={(e) => setLocalFilter(e.target.value)}
              placeholder="Filter results…"
              className="w-full text-xs pl-9 pr-3 py-2 bg-app-card border border-border-default rounded-lg text-content-primary placeholder:text-content-muted focus:outline-none focus:border-border-active"
            />
          </div>
        </div>
      )}

      {/* Match cards */}
      <div className="space-y-4">
        {displayedMatches.map((match) => {
          const id = match.job_id ?? match.title;
          return (
            <MatchCard
              key={id}
              match={match}
              isShortlisted={!!shortlisted[id]}
              isDismissed={!!dismissed[id]}
              onShortlist={() => toggleShortlist(id)}
              onDismiss={() => toggleDismiss(id)}
            />
          );
        })}

        {/* Empty state — before launch */}
        {phase === "idle" && matches.length === 0 && !error && (
          <div className="p-12 text-center bg-app-card rounded-xl border border-dashed border-border-default text-content-muted space-y-3">
            <Briefcase className="w-10 h-10 mx-auto text-content-muted/50" />
            <p className="text-sm font-semibold text-content-primary">
              No Matches Yet
            </p>
            <p className="text-xs max-w-sm mx-auto leading-relaxed">
              Configure your discovery filters above and click{" "}
              <span className="text-accent-primary font-semibold">Run Discovery</span> to
              launch the LangGraph workflow. Jobs will be ingested, normalized, and
              scored against your profile automatically.
            </p>
            <div className="pt-2 flex items-center justify-center gap-2 text-[11px] text-content-muted">
              <Sparkles className="w-3.5 h-3.5 text-accent-purple" />
              <span>AI-grounded, evidence-backed match evaluation</span>
            </div>
          </div>
        )}

        {/* Empty after filter */}
        {phase !== "idle" && matches.length > 0 && displayedMatches.length === 0 && (
          <div className="p-8 text-center bg-app-card rounded-xl border border-border-default text-content-muted space-y-2">
            <p className="text-sm font-semibold text-content-primary">No results match your filter</p>
            <p className="text-xs">Try clearing the filter or running a new discovery.</p>
            <button
              onClick={() => setLocalFilter("")}
              className="mt-2 text-xs text-accent-primary hover:underline"
            >
              Clear filter
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
