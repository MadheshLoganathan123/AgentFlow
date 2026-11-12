"use client";

import React, { useState } from "react";
import { Navbar, TabKey } from "@/components/Navbar";
import { DashboardHero } from "@/components/DashboardHero";
import { ResumeUploader } from "@/components/ResumeUploader";
import { ProfileReviewCard } from "@/components/ProfileReviewCard";
import { RoadmapWidget } from "@/components/RoadmapWidget";
import { JobMatchesView } from "@/components/JobMatchesView";
import { ApplicationPackagesView } from "@/components/ApplicationPackagesView";
import { AuditRunsView } from "@/components/AuditRunsView";
import { FileSearch, Sparkles } from "lucide-react";

export default function Home() {
  const [activeTab, setActiveTab] = useState<TabKey>("onboarding");
  const [extractedData, setExtractedData] = useState<any>(null);
  const [isCompleted, setIsCompleted] = useState(false);

  return (
    <div className="min-h-screen flex flex-col bg-app-bg text-content-primary">
      {/* Sticky Navigation */}
      <Navbar activeTab={activeTab} onTabChange={setActiveTab} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Compact Hero Banner */}
        <DashboardHero />

        {/* Tab 1: Profile & Onboarding Workspace */}
        {activeTab === "onboarding" && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            {/* Left Column: Upload Component & Roadmap Widget */}
            <div className="lg:col-span-5 space-y-6">
              <ResumeUploader
                onProfileExtracted={(data) => {
                  setExtractedData(data);
                  setIsCompleted(false);
                }}
              />

              <RoadmapWidget />
            </div>

            {/* Right Column: Intelligent Resume Analysis & Review Card */}
            <div className="lg:col-span-7">
              {extractedData ? (
                <ProfileReviewCard
                  workflowId={extractedData.workflow_id}
                  initialProfile={extractedData.profile}
                  onConfirmed={() => setIsCompleted(true)}
                />
              ) : (
                /* Empty state */
                <div className="bg-app-card rounded-xl border-2 border-dashed border-border-default p-12 text-center text-content-muted space-y-3 shadow-dark-sm">
                  <div className="w-12 h-12 rounded-xl bg-app-cardSecondary border border-border-subtle flex items-center justify-center mx-auto text-content-muted">
                    <FileSearch className="w-6 h-6 text-accent-primary/60" />
                  </div>
                  <h4 className="font-semibold text-content-primary text-base">
                    Awaiting Resume Ingestion
                  </h4>
                  <p className="text-xs max-w-sm mx-auto text-content-secondary leading-relaxed">
                    Upload a resume file (.pdf, .docx, .txt) or paste raw text on the left to trigger the Profile Analyst extractor and pause at the human verification gate.
                  </p>
                  <div className="pt-2 flex items-center justify-center space-x-2 text-[11px] text-content-muted">
                    <Sparkles className="w-3.5 h-3.5 text-accent-purple" />
                    <span>Evidence-grounded parsing ensures zero fabricated claims</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Tab 2: Job Matches & Explainable Fit */}
        {activeTab === "matches" && <JobMatchesView />}

        {/* Tab 3: Application Packages & Readiness */}
        {activeTab === "packages" && <ApplicationPackagesView />}

        {/* Tab 4: Audit & Runs Telemetry */}
        {activeTab === "audit" && <AuditRunsView />}
      </main>
    </div>
  );
}
