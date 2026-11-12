import React from "react";
import { CheckCircle2, ChevronRight, Layers, Sparkles } from "lucide-react";

interface PhaseItem {
  number: number;
  title: string;
  scope: string;
  status: "completed" | "current" | "upcoming";
}

const PHASES: PhaseItem[] = [
  {
    number: 1,
    title: "Foundation & Monorepo Infrastructure",
    scope: "Monorepo, Next.js, FastAPI, CI pipelines",
    status: "completed",
  },
  {
    number: 2,
    title: "Database Schema & Models (20 Tables)",
    scope: "PostgreSQL, pgvector, Alembic migrations",
    status: "completed",
  },
  {
    number: 3,
    title: "Typed Agent Contracts (9 Agents)",
    scope: "Pydantic v2 schemas, provenance, telemetry",
    status: "completed",
  },
  {
    number: 4,
    title: "Multi-Format Extraction & Evidence",
    scope: "PDF/DOCX/TXT parser, verbatim citations",
    status: "completed",
  },
  {
    number: 5,
    title: "LangGraph StateGraph & Checkpointer",
    scope: "Durable pauses, human confirmation gate",
    status: "completed",
  },
  {
    number: 6,
    title: "Web Dashboard & Onboarding UI",
    scope: "Dark-mode workspace, proof-of-concept demo",
    status: "completed",
  },
];

export const RoadmapWidget: React.FC = () => {
  const completedCount = PHASES.filter((p) => p.status === "completed").length;
  const progressPercent = Math.round((completedCount / PHASES.length) * 100);

  return (
    <div className="bg-app-card rounded-xl p-5 border border-border-default shadow-dark-sm space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border-subtle pb-3">
        <div className="flex items-center space-x-2">
          <Layers className="w-4 h-4 text-accent-primary" />
          <h4 className="text-xs font-bold uppercase tracking-wider text-content-primary">
            Week 1 Implementation Roadmap
          </h4>
        </div>
        <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-accent-emerald/10 text-accent-emerald border border-accent-emerald/20">
          {progressPercent}% Complete
        </span>
      </div>

      {/* Progress Bar */}
      <div className="w-full bg-app-cardSecondary rounded-full h-1.5 overflow-hidden">
        <div
          className="bg-gradient-to-r from-accent-primary to-accent-emerald h-1.5 rounded-full transition-all duration-500"
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      {/* Phase List */}
      <div className="space-y-2">
        {PHASES.map((phase) => (
          <div
            key={phase.number}
            className={`group p-2.5 rounded-lg border text-xs transition flex items-start justify-between ${
              phase.status === "completed"
                ? "bg-app-cardSecondary/40 border-border-subtle/80 hover:border-border-default"
                : phase.status === "current"
                ? "bg-accent-primary/5 border-accent-primary/40 shadow-sm"
                : "bg-app-bg/50 border-border-subtle/40 text-content-muted"
            }`}
          >
            <div className="flex items-start space-x-2.5">
              <div className="mt-0.5">
                {phase.status === "completed" ? (
                  <CheckCircle2 className="w-4 h-4 text-accent-emerald flex-shrink-0" />
                ) : (
                  <div className="w-4 h-4 rounded-full border-2 border-accent-primary flex items-center justify-center">
                    <div className="w-1.5 h-1.5 rounded-full bg-accent-primary animate-pulse" />
                  </div>
                )}
              </div>
              <div>
                <p className="font-semibold text-content-primary leading-tight">
                  Phase {phase.number}: {phase.title}
                </p>
                <p className="text-[11px] text-content-secondary mt-0.5">
                  {phase.scope}
                </p>
              </div>
            </div>

            <ChevronRight className="w-3.5 h-3.5 text-content-muted opacity-0 group-hover:opacity-100 transition mt-1" />
          </div>
        ))}
      </div>

      {/* Acceptance Criteria Notice */}
      <div className="pt-2 border-t border-border-subtle">
        <div className="flex items-start space-x-2 text-[11px] text-content-secondary leading-snug">
          <Sparkles className="w-3.5 h-3.5 text-accent-purple flex-shrink-0 mt-0.5" />
          <span>
            <strong className="text-content-primary">End-of-week demo ready:</strong> Full pipeline from resume ingest to evidence review and human approval resumption verified.
          </span>
        </div>
      </div>
    </div>
  );
};
