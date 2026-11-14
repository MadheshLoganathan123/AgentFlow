"use client";

import React, { useState } from "react";
import {
  FileText,
  ShieldCheck,
  CheckCircle,
  AlertTriangle,
  ArrowRight,
  Download,
  Eye,
  Lock,
  Layers,
  Sparkles,
  ExternalLink,
} from "lucide-react";

interface ApplicationPackage {
  id: string;
  jobTitle: string;
  company: string;
  destinationDomain: string;
  readinessScore: number;
  blockers: string[];
  warnings: string[];
  tailoredResumeVersion: string;
  coverLetterSnippet: string;
  status: "ready_for_review" | "user_confirmed" | "submitted";
}

const SAMPLE_PACKAGES: ApplicationPackage[] = [
  {
    id: "pkg_01",
    jobTitle: "Senior Backend Engineer (Python / Distributed Systems)",
    company: "CloudScale Data Technologies",
    destinationDomain: "jobs.lever.co/cloudscale",
    readinessScore: 100,
    blockers: [],
    warnings: ["Ensure contact phone includes international country code"],
    tailoredResumeVersion: "v1.2 (Targeted: High-throughput ingestion & PostgreSQL)",
    coverLetterSnippet:
      "Dear CloudScale Hiring Team, I am writing to express my strong interest in the Senior Backend Engineer position. With 5+ years building asynchronous Python microservices and scaling PostgreSQL workloads, I look forward to contributing immediately...",
    status: "ready_for_review",
  },
  {
    id: "pkg_02",
    jobTitle: "Lead AI Application Architect",
    company: "Synthetix Labs",
    destinationDomain: "boards.greenhouse.io/synthetix",
    readinessScore: 85,
    blockers: ["Work authorization proof requires user upload in preferences"],
    warnings: ["Container orchestration experience should be highlighted in intro"],
    tailoredResumeVersion: "v1.1 (Targeted: Architecture leadership & LLM systems)",
    coverLetterSnippet:
      "To the Synthetix Labs Engineering Team, My background in distributed orchestration and LangGraph state machines aligns cleanly with your core platform objectives...",
    status: "ready_for_review",
  },
];

export const ApplicationPackagesView: React.FC = () => {
  const [packages, setPackages] = useState<ApplicationPackage[]>(SAMPLE_PACKAGES);
  const [previewPackage, setPreviewPackage] = useState<ApplicationPackage | null>(null);

  const confirmPackage = (id: string) => {
    setPackages((prev) =>
      prev.map((pkg) =>
        pkg.id === id ? { ...pkg, status: "user_confirmed" } : pkg
      )
    );
  };

  return (
    <div className="space-y-6">
      {/* Banner */}
      <div className="p-4 bg-app-card rounded-xl border border-border-default shadow-dark-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-lg bg-accent-purple/10 border border-accent-purple/20 text-accent-purple">
            <FileText className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-content-primary">
              Application Readiness & Tailored Document Packages
            </h3>
            <p className="text-xs text-content-secondary">
              Grounded tailored resumes and cover letters. Submission is non-bypassable and requires per-job user confirmation.
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2 text-xs font-semibold px-3 py-1 rounded-full bg-accent-emerald/10 text-accent-emerald border border-accent-emerald/25">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>Zero Mass Automation</span>
        </div>
      </div>

      {/* Package Cards */}
      <div className="space-y-4">
        {packages.map((pkg) => (
          <div
            key={pkg.id}
            className="bg-app-card rounded-xl border border-border-default p-5 shadow-dark-sm space-y-4 hover:border-border-active/40 transition"
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border-subtle pb-3">
              <div>
                <span className="text-[10px] uppercase font-bold text-content-muted">Target Role</span>
                <h4 className="text-base font-bold text-content-primary">{pkg.jobTitle}</h4>
                <p className="text-xs text-content-secondary mt-0.5">
                  {pkg.company} • Destination: <span className="font-mono text-accent-secondary">{pkg.destinationDomain}</span>
                </p>
              </div>

              <div className="flex items-center space-x-2">
                <span className="text-xs font-mono px-2.5 py-1 rounded-lg bg-app-cardSecondary border border-border-subtle text-content-primary">
                  Readiness: <strong className={pkg.readinessScore === 100 ? "text-accent-emerald" : "text-accent-amber"}>{pkg.readinessScore}%</strong>
                </span>
                {pkg.status === "user_confirmed" ? (
                  <span className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-accent-emerald/10 text-accent-emerald border border-accent-emerald/20 flex items-center space-x-1">
                    <CheckCircle className="w-3 h-3" />
                    <span>Approved</span>
                  </span>
                ) : (
                  <span className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-accent-amber/10 text-accent-amber border border-accent-amber/20 flex items-center space-x-1">
                    <Lock className="w-3 h-3" />
                    <span>Pending Gate</span>
                  </span>
                )}
              </div>
            </div>

            {/* Document versions */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
              <div className="p-3 bg-app-cardSecondary rounded-lg border border-border-subtle space-y-1">
                <p className="font-bold text-content-primary flex items-center">
                  <FileText className="w-3.5 h-3.5 text-accent-primary mr-1.5" />
                  Tailored Resume Version
                </p>
                <p className="text-content-secondary font-mono text-[11px]">{pkg.tailoredResumeVersion}</p>
                <p className="text-content-muted text-[11px]">Strictly derived from verified candidate profile evidence.</p>
              </div>

              <div className="p-3 bg-app-cardSecondary rounded-lg border border-border-subtle space-y-1">
                <p className="font-bold text-content-primary flex items-center">
                  <Sparkles className="w-3.5 h-3.5 text-accent-purple mr-1.5" />
                  Grounded Cover Letter
                </p>
                <p className="text-content-secondary line-clamp-2 text-[11px] italic">
                  &ldquo;{pkg.coverLetterSnippet}&rdquo;
                </p>
              </div>
            </div>

            {/* Blockers or Warnings */}
            {pkg.blockers.length > 0 && (
              <div className="p-3 rounded-lg bg-accent-rose/10 border border-accent-rose/25 text-xs text-accent-rose flex items-start space-x-2">
                <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-bold">Submission Blocked:</p>
                  <p>{pkg.blockers.join(", ")}</p>
                </div>
              </div>
            )}

            {/* Actions & Confirmation Gate */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => setPreviewPackage(pkg)}
                  className="px-3 py-1.5 rounded-lg bg-app-cardSecondary hover:bg-app-panel text-content-primary text-xs font-medium border border-border-subtle flex items-center space-x-1.5 transition"
                >
                  <Eye className="w-3.5 h-3.5" />
                  <span>Preview Payload</span>
                </button>
                <button
                  className="px-3 py-1.5 rounded-lg bg-app-cardSecondary hover:bg-app-panel text-content-secondary hover:text-content-primary text-xs font-medium border border-border-subtle flex items-center space-x-1.5 transition"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Export Package (.zip)</span>
                </button>
              </div>

              {pkg.status !== "user_confirmed" ? (
                <button
                  onClick={() => confirmPackage(pkg.id)}
                  disabled={pkg.blockers.length > 0}
                  className="px-4 py-2 rounded-lg bg-accent-emerald hover:bg-emerald-600 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-bold flex items-center space-x-1.5 shadow-dark-sm transition"
                >
                  <Lock className="w-3.5 h-3.5" />
                  <span>Review & Authorize Application</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              ) : (
                <div className="text-xs font-semibold text-accent-emerald flex items-center space-x-1.5">
                  <CheckCircle className="w-4 h-4" />
                  <span>Confirmed by Candidate (Ready for assisted handoff)</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Modal Preview */}
      {previewPackage && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-app-card border border-border-default rounded-2xl max-w-2xl w-full p-6 space-y-4 shadow-dark-lg text-xs">
            <div className="flex justify-between items-center border-b border-border-subtle pb-3">
              <h4 className="font-bold text-sm text-content-primary">
                Application Package Preview: {previewPackage.jobTitle}
              </h4>
              <button
                onClick={() => setPreviewPackage(null)}
                className="text-content-muted hover:text-content-primary p-1 rounded-lg hover:bg-app-panel"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <span className="text-[10px] uppercase font-bold text-content-muted">Destination Endpoint</span>
                <p className="font-mono text-accent-secondary mt-0.5">https://{previewPackage.destinationDomain}</p>
              </div>
              <div>
                <span className="text-[10px] uppercase font-bold text-content-muted">Cover Letter Content</span>
                <p className="p-3 bg-app-cardSecondary rounded-lg border border-border-subtle mt-1 text-content-secondary leading-relaxed">
                  {previewPackage.coverLetterSnippet}
                </p>
              </div>
              <div className="p-3 bg-accent-primary/10 border border-accent-primary/20 rounded-lg text-content-secondary">
                <span className="font-bold text-accent-secondary">Safety Assurance: </span>
                AgentFlow never submits automatically without manual confirmation and never solves CAPTCHAs or bypasses anti-bot systems.
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setPreviewPackage(null)}
                className="px-4 py-2 bg-app-cardSecondary hover:bg-app-panel text-content-primary rounded-lg font-medium border border-border-subtle"
              >
                Close Preview
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

