"use client";

import React, { useState } from "react";
import { Navbar } from "@/components/Navbar";
import { ResumeUploader } from "@/components/ResumeUploader";
import { ProfileReviewCard } from "@/components/ProfileReviewCard";
import { CheckCircle2, ShieldCheck, Database, Cpu, Layers } from "lucide-react";

export default function Home() {
  const [extractedData, setExtractedData] = useState<any>(null);
  const [isCompleted, setIsCompleted] = useState(false);

  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <Navbar />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Banner / System Architecture Status */}
        <div className="bg-gradient-to-r from-blue-900 to-indigo-900 text-white rounded-2xl p-6 shadow-md">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center space-x-2 text-xs font-semibold text-blue-300 uppercase tracking-wider mb-1">
                <span>Phase 1 of 6 Initialized</span>
                <span>•</span>
                <span>Open Source Tech Stack</span>
              </div>
              <h2 className="text-2xl font-bold">AgentFlow — Multi-Agent Copilot Architecture</h2>
              <p className="text-sm text-blue-100 mt-1 max-w-2xl">
                One workflow authority (LangGraph) owns the state machine. FastAPI + PostgreSQL + pgvector power persistence and REST contracts.
              </p>
            </div>
            <div className="flex items-center space-x-3 bg-white/10 backdrop-blur px-4 py-2.5 rounded-xl border border-white/10">
              <ShieldCheck className="w-5 h-5 text-emerald-400" />
              <div className="text-xs">
                <p className="font-semibold text-white">Human Approval Gate</p>
                <p className="text-blue-200">Zero Unattended Submissions</p>
              </div>
            </div>
          </div>

          {/* Architecture Badges */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-6 pt-6 border-t border-white/10 text-xs">
            <div className="flex items-center space-x-2 text-blue-200">
              <Cpu className="w-4 h-4 text-blue-400" />
              <span>FastAPI + Python 3.11</span>
            </div>
            <div className="flex items-center space-x-2 text-blue-200">
              <Database className="w-4 h-4 text-emerald-400" />
              <span>PostgreSQL + pgvector</span>
            </div>
            <div className="flex items-center space-x-2 text-blue-200">
              <Layers className="w-4 h-4 text-purple-400" />
              <span>LangGraph Orchestrator</span>
            </div>
            <div className="flex items-center space-x-2 text-blue-200">
              <CheckCircle2 className="w-4 h-4 text-teal-400" />
              <span>Next.js 14 App Router</span>
            </div>
          </div>
        </div>

        {/* Core Profile Onboarding Flow */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          <div className="lg:col-span-5 space-y-6">
            <ResumeUploader
              onProfileExtracted={(data) => {
                setExtractedData(data);
                setIsCompleted(false);
              }}
            />

            {/* Phase 1 Specs Box */}
            <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-sm text-xs space-y-3">
              <h4 className="font-bold text-slate-800 uppercase tracking-wide">
                Week 1 Implementation Roadmap
              </h4>
              <ul className="space-y-2 text-slate-600">
                <li className="flex items-center space-x-2 text-blue-700 font-semibold">
                  <span className="w-2 h-2 rounded-full bg-blue-600"></span>
                  <span>Phase 1: Foundation & Monorepo Infrastructure (Current)</span>
                </li>
                <li className="flex items-center space-x-2 text-slate-500">
                  <span className="w-2 h-2 rounded-full bg-slate-300"></span>
                  <span>Phase 2: Database Schema & Relational Models</span>
                </li>
                <li className="flex items-center space-x-2 text-slate-500">
                  <span className="w-2 h-2 rounded-full bg-slate-300"></span>
                  <span>Phase 3: Typed Agent Contracts & Schemas</span>
                </li>
                <li className="flex items-center space-x-2 text-slate-500">
                  <span className="w-2 h-2 rounded-full bg-slate-300"></span>
                  <span>Phase 4: LangGraph Workflow Skeleton & Checkpointing</span>
                </li>
                <li className="flex items-center space-x-2 text-slate-500">
                  <span className="w-2 h-2 rounded-full bg-slate-300"></span>
                  <span>Phase 5: Backend API & Resume Extraction Pipeline</span>
                </li>
                <li className="flex items-center space-x-2 text-slate-500">
                  <span className="w-2 h-2 rounded-full bg-slate-300"></span>
                  <span>Phase 6: Web Dashboard & Profile Onboarding UI</span>
                </li>
              </ul>
            </div>
          </div>

          <div className="lg:col-span-7">
            {extractedData ? (
              <ProfileReviewCard
                workflowId={extractedData.workflow_id}
                initialProfile={extractedData.profile}
                onConfirmed={() => setIsCompleted(true)}
              />
            ) : (
              <div className="bg-white rounded-xl border border-dashed border-slate-300 p-12 text-center text-slate-400">
                <Layers className="w-12 h-12 mx-auto mb-3 text-slate-300" />
                <h4 className="font-semibold text-slate-700 mb-1">Awaiting Resume Ingestion</h4>
                <p className="text-xs max-w-sm mx-auto">
                  Upload a resume or paste text on the left to trigger the Profile Analyst agent and pause at the human verification gate.
                </p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

