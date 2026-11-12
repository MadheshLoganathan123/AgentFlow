import React from "react";
import { CheckCircle2, ShieldCheck, Database, Cpu, Layers } from "lucide-react";

export const DashboardHero: React.FC = () => {
  return (
    <div className="relative overflow-hidden rounded-2xl bg-gradient-to-b from-app-secondary via-app-card to-app-bg border border-border-default/80 p-6 sm:p-7 shadow-dark-lg">
      {/* Subtle ambient lighting element */}
      <div className="absolute top-0 right-1/4 -mt-12 w-96 h-96 bg-accent-primary/5 rounded-full blur-3xl pointer-events-none" />

      <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
        <div className="space-y-2.5 max-w-3xl">
          {/* Metadata Badges */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-accent-primary/10 text-accent-secondary border border-accent-primary/20">
              <span className="w-1.5 h-1.5 rounded-full bg-accent-primary animate-pulse" />
              <span>Week 1 Completed</span>
            </span>
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-app-cardSecondary text-content-secondary border border-border-subtle">
              6 Phases Integrated
            </span>
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-app-cardSecondary text-content-secondary border border-border-subtle">
              100% Open Source Stack
            </span>
          </div>

          {/* Heading & Mission */}
          <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-content-primary">
            AgentFlow — Multi-Agent Job Search Copilot
          </h2>
          <p className="text-xs sm:text-sm text-content-secondary leading-relaxed">
            One workflow authority (<span className="text-accent-secondary font-medium">LangGraph StateGraph</span>) coordinates agent state, 
            PostgreSQL + pgvector powers deterministic persistence, and non-bypassable human verification gates protect candidate decisions.
          </p>
        </div>

        {/* Human Gate Status Panel */}
        <div className="flex-shrink-0 flex items-center space-x-3.5 bg-app-cardSecondary/90 border border-border-default/90 px-4 py-3 rounded-xl shadow-dark-sm backdrop-blur">
          <div className="p-2 rounded-lg bg-accent-emerald/10 border border-accent-emerald/20 text-accent-emerald">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div className="text-xs">
            <p className="font-semibold text-content-primary">Human Approval Gate</p>
            <p className="text-content-secondary font-normal">Zero Unattended Actions</p>
          </div>
        </div>
      </div>

      {/* Technology Indicators */}
      <div className="relative z-10 grid grid-cols-2 sm:grid-cols-4 gap-3 mt-6 pt-5 border-t border-border-subtle/80 text-xs">
        <div className="flex items-center space-x-2 text-content-secondary hover:text-content-primary transition">
          <Cpu className="w-4 h-4 text-accent-primary" />
          <span className="truncate">FastAPI + Python 3.11</span>
        </div>
        <div className="flex items-center space-x-2 text-content-secondary hover:text-content-primary transition">
          <Database className="w-4 h-4 text-accent-emerald" />
          <span className="truncate">PostgreSQL + pgvector</span>
        </div>
        <div className="flex items-center space-x-2 text-content-secondary hover:text-content-primary transition">
          <Layers className="w-4 h-4 text-accent-purple" />
          <span className="truncate">LangGraph StateGraph</span>
        </div>
        <div className="flex items-center space-x-2 text-content-secondary hover:text-content-primary transition">
          <CheckCircle2 className="w-4 h-4 text-accent-secondary" />
          <span className="truncate">Next.js 14 App Router</span>
        </div>
      </div>
    </div>
  );
};
