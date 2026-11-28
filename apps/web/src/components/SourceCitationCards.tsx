"use client";

import React, { useState } from "react";
import {
  ExternalLink,
  ShieldCheck,
  AlertTriangle,
  Trash2,
  Flag,
  Hash,
  Clock,
  Building,
  BookOpen,
  CheckCircle2,
} from "lucide-react";
import { ResearchSource } from "@/lib/api";

interface SourceCitationCardsProps {
  sources: ResearchSource[];
  companyName: string;
  onReportSource?: (sourceId: string, reason: string) => Promise<void>;
  onDeleteSource?: (sourceId: string) => Promise<void>;
}

export const SourceCitationCards: React.FC<SourceCitationCardsProps> = ({
  sources: initialSources,
  companyName,
  onReportSource,
  onDeleteSource,
}) => {
  const [sources, setSources] = useState<ResearchSource[]>(initialSources);
  const [activeTab, setActiveTab] = useState<"all" | "company" | "general">("all");
  const [reportingId, setReportingId] = useState<string | null>(null);
  const [reportReason, setReportReason] = useState("");
  const [isSubmittingReport, setIsSubmittingReport] = useState(false);

  const filteredSources = sources.filter((s) => {
    if (activeTab === "company") return s.is_company_specific;
    if (activeTab === "general") return !s.is_company_specific;
    return true;
  });

  const handleReport = async (sourceId: string) => {
    if (!reportReason.trim()) return;
    setIsSubmittingReport(true);
    try {
      if (onReportSource) {
        await onReportSource(sourceId, reportReason.trim());
      }
      setSources((prev) =>
        prev.map((s) =>
          s.id === sourceId
            ? { ...s, is_reported: true, report_reason: reportReason.trim() }
            : s
        )
      );
      setReportingId(null);
      setReportReason("");
    } finally {
      setIsSubmittingReport(false);
    }
  };

  const handleDelete = async (sourceId: string) => {
    if (onDeleteSource) {
      await onDeleteSource(sourceId);
    }
    setSources((prev) => prev.filter((s) => s.id !== sourceId));
  };

  const getCategoryBadgeClass = (category: string) => {
    switch (category) {
      case "sec_filing":
        return "bg-amber-500/10 text-amber-400 border-amber-500/30";
      case "engineering_blog":
        return "bg-cyan-500/10 text-cyan-400 border-cyan-500/30";
      case "careers_page":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
      case "github":
        return "bg-purple-500/10 text-purple-400 border-purple-500/30";
      case "tech_press":
        return "bg-blue-500/10 text-blue-400 border-blue-500/30";
      default:
        return "bg-zinc-500/10 text-zinc-400 border-zinc-500/30";
    }
  };

  return (
    <div className="space-y-4">
      {/* Header and Controls */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-4 bg-app-card rounded-xl border border-border-default">
        <div>
          <div className="flex items-center space-x-2">
            <ShieldCheck className="w-5 h-5 text-accent-emerald" />
            <h3 className="text-sm font-bold text-content-primary">
              Allowlisted Research Citations — {companyName}
            </h3>
          </div>
          <p className="text-xs text-content-secondary mt-1">
            Grounded from official engineering publications, SEC filings, GitHub, and verified press. Tamper-evident SHA-256 hashes.
          </p>
        </div>

        {/* Tab Filters */}
        <div className="flex items-center space-x-1.5 p-1 bg-zinc-900/60 rounded-lg border border-border-default text-xs">
          <button
            onClick={() => setActiveTab("all")}
            className={`px-2.5 py-1 rounded-md transition-colors ${
              activeTab === "all"
                ? "bg-accent-blue text-white font-medium"
                : "text-content-secondary hover:text-content-primary"
            }`}
          >
            All ({sources.length})
          </button>
          <button
            onClick={() => setActiveTab("company")}
            className={`px-2.5 py-1 rounded-md transition-colors ${
              activeTab === "company"
                ? "bg-accent-blue text-white font-medium"
                : "text-content-secondary hover:text-content-primary"
            }`}
          >
            Company ({sources.filter((s) => s.is_company_specific).length})
          </button>
          <button
            onClick={() => setActiveTab("general")}
            className={`px-2.5 py-1 rounded-md transition-colors ${
              activeTab === "general"
                ? "bg-accent-blue text-white font-medium"
                : "text-content-secondary hover:text-content-primary"
            }`}
          >
            General Advice ({sources.filter((s) => !s.is_company_specific).length})
          </button>
        </div>
      </div>

      {/* Citations Grid */}
      {filteredSources.length === 0 ? (
        <div className="p-8 text-center text-xs text-content-muted border border-dashed border-border-default rounded-xl">
          No sources match the selected filter.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredSources.map((source) => (
            <div
              key={source.id || source.source_url}
              className={`p-4 rounded-xl border flex flex-col justify-between transition-all ${
                source.is_reported
                  ? "bg-rose-950/10 border-rose-900/40 opacity-75"
                  : "bg-app-card border-border-default hover:border-zinc-700"
              }`}
            >
              <div>
                {/* Badges Bar */}
                <div className="flex items-center justify-between gap-2 mb-2.5 flex-wrap">
                  <div className="flex items-center space-x-2">
                    <span
                      className={`text-[10px] uppercase font-semibold px-2 py-0.5 rounded border ${getCategoryBadgeClass(
                        source.source_category
                      )}`}
                    >
                      {source.source_category.replace("_", " ")}
                    </span>
                    <span
                      className={`text-[10px] font-medium px-2 py-0.5 rounded border flex items-center space-x-1 ${
                        source.is_company_specific
                          ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                          : "bg-indigo-500/10 text-indigo-400 border-indigo-500/20"
                      }`}
                    >
                      {source.is_company_specific ? (
                        <>
                          <Building className="w-2.5 h-2.5" />
                          <span>Company Intel</span>
                        </>
                      ) : (
                        <>
                          <BookOpen className="w-2.5 h-2.5" />
                          <span>General Prep</span>
                        </>
                      )}
                    </span>
                  </div>

                  {source.is_reported && (
                    <span className="text-[10px] font-semibold text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded border border-rose-500/20 flex items-center space-x-1">
                      <AlertTriangle className="w-2.5 h-2.5" />
                      <span>Reported</span>
                    </span>
                  )}
                </div>

                {/* Title & Link */}
                <a
                  href={source.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group flex items-start justify-between gap-2 text-sm font-semibold text-content-primary hover:text-accent-blue transition-colors"
                >
                  <span className="line-clamp-2">{source.source_title}</span>
                  <ExternalLink className="w-4 h-4 flex-shrink-0 text-content-muted group-hover:text-accent-blue transition-colors mt-0.5" />
                </a>

                {/* Excerpt */}
                <p className="text-xs text-content-secondary mt-2 line-clamp-3 leading-relaxed bg-zinc-900/40 p-2.5 rounded-lg border border-border-default/50 font-mono text-[11px]">
                  &ldquo;{source.content_excerpt}&rdquo;
                </p>

                {/* Reported Warning Note */}
                {source.is_reported && source.report_reason && (
                  <div className="mt-2 text-[11px] text-rose-300/90 bg-rose-950/30 p-2 rounded border border-rose-900/30">
                    <span className="font-semibold">User Report:</span> {source.report_reason}
                  </div>
                )}
              </div>

              {/* Footer: Metadata & Actions */}
              <div className="mt-4 pt-3 border-t border-border-default/60 flex items-center justify-between text-[11px] text-content-muted">
                <div className="flex items-center space-x-3">
                  <span className="flex items-center space-x-1" title={source.retrieved_at}>
                    <Clock className="w-3 h-3 text-content-muted" />
                    <span>{new Date(source.retrieved_at).toLocaleDateString()}</span>
                  </span>

                  {source.content_hash && (
                    <span
                      className="flex items-center space-x-1 font-mono text-[10px]"
                      title={`SHA-256: ${source.content_hash}`}
                    >
                      <Hash className="w-3 h-3 text-content-muted" />
                      <span>{source.content_hash.slice(0, 8)}...</span>
                    </span>
                  )}
                </div>

                {/* Action Controls */}
                <div className="flex items-center space-x-1">
                  {!source.is_reported && (
                    <button
                      onClick={() => setReportingId(source.id || source.source_url)}
                      title="Report inaccurate or stale source"
                      className="p-1.5 hover:bg-zinc-800 rounded text-content-muted hover:text-amber-400 transition-colors"
                    >
                      <Flag className="w-3.5 h-3.5" />
                    </button>
                  )}

                  <button
                    onClick={() => source.id && handleDelete(source.id)}
                    title="Remove source citation"
                    className="p-1.5 hover:bg-zinc-800 rounded text-content-muted hover:text-rose-400 transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* Inline Report Input Modal / Prompt */}
              {reportingId === (source.id || source.source_url) && (
                <div className="mt-3 p-2.5 bg-zinc-900 rounded-lg border border-amber-500/30 space-y-2">
                  <div className="text-[11px] font-semibold text-amber-400 flex items-center space-x-1">
                    <AlertTriangle className="w-3 h-3" />
                    <span>Report Source</span>
                  </div>
                  <input
                    type="text"
                    value={reportReason}
                    onChange={(e) => setReportReason(e.target.value)}
                    placeholder="Reason (e.g. outdated tech stack, broken URL)..."
                    className="w-full text-xs bg-zinc-950 border border-zinc-800 rounded px-2.5 py-1.5 text-content-primary focus:outline-none focus:border-amber-500"
                  />
                  <div className="flex justify-end space-x-1.5">
                    <button
                      onClick={() => {
                        setReportingId(null);
                        setReportReason("");
                      }}
                      className="px-2 py-1 text-[11px] text-content-secondary hover:text-content-primary"
                    >
                      Cancel
                    </button>
                    <button
                      disabled={isSubmittingReport || !reportReason.trim()}
                      onClick={() => source.id && handleReport(source.id)}
                      className="px-2.5 py-1 text-[11px] bg-amber-500/20 text-amber-300 border border-amber-500/40 rounded hover:bg-amber-500/30 disabled:opacity-50"
                    >
                      {isSubmittingReport ? "Submitting..." : "Confirm Report"}
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
