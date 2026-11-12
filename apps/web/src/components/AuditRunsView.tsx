"use client";

import React, { useState } from "react";
import {
  Activity,
  CheckCircle,
  Clock,
  Cpu,
  Database,
  Layers,
  Shield,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Terminal,
} from "lucide-react";

interface AgentRun {
  id: string;
  agentRole: string;
  stage: string;
  status: "success" | "paused" | "in_progress";
  timestamp: string;
  modelVersion: string;
  toolCallsCount: number;
  auditMessage: string;
  checkpointId: string;
  details: Record<string, any>;
}

const SAMPLE_RUNS: AgentRun[] = [
  {
    id: "run_9918",
    agentRole: "Profile Analyst",
    stage: "awaiting_profile_confirmation",
    status: "paused",
    timestamp: "Just now",
    modelVersion: "deterministic_extractor:v1",
    toolCallsCount: 2,
    auditMessage: "Extracted 4 skills, 2 work experiences. Paused at human verification gate.",
    checkpointId: "ckpt_v2_f891",
    details: {
      input_bytes: 4096,
      grounded_citations_count: 4,
      unconfirmed_inferences: 2,
      checkpoint_saver: "memory",
      state_thread_id: "wf_demo_981",
    },
  },
  {
    id: "run_9917",
    agentRole: "Resume Parser Engine",
    stage: "profile_ingestion",
    status: "success",
    timestamp: "2 mins ago",
    modelVersion: "pypdf+pdfplumber:cpu",
    toolCallsCount: 1,
    auditMessage: "Multi-format file bytes decoded without text corruption.",
    checkpointId: "ckpt_v1_c102",
    details: {
      format: "PDF",
      extracted_char_count: 3120,
      processing_latency_ms: 142,
    },
  },
  {
    id: "run_9916",
    agentRole: "Orchestrator State Machine",
    stage: "profile_validation",
    status: "success",
    timestamp: "5 mins ago",
    modelVersion: "langgraph:v1.2",
    toolCallsCount: 0,
    auditMessage: "StateGraph thread initialized. Checkpoint persisted to repository.",
    checkpointId: "ckpt_v0_a001",
    details: {
      active_node: "profile_validate",
      interrupt_gate: "awaiting_confirmation",
      checkpointer: "MemorySaver",
    },
  },
];

export const AuditRunsView: React.FC = () => {
  const [expandedId, setExpandedId] = useState<string | null>("run_9918");

  const toggleExpand = (id: string) => {
    setExpandedId((prev) => (prev === id ? null : id));
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="p-4 bg-app-card rounded-xl border border-border-default shadow-dark-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-lg bg-accent-primary/10 border border-accent-primary/20 text-accent-primary">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-content-primary">
              LangGraph Orchestrator Telemetry & Audit Logs
            </h3>
            <p className="text-xs text-content-secondary">
              Immutable trail of state checkpoints, agent executions, and human approval verification gates.
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2 text-xs font-mono text-content-muted">
          <span>Saver:</span>
          <span className="px-2 py-0.5 rounded bg-app-cardSecondary border border-border-subtle text-accent-secondary">
            MemorySaver (PostgreSQL Ready)
          </span>
        </div>
      </div>

      {/* Execution Timeline */}
      <div className="space-y-3">
        {SAMPLE_RUNS.map((run) => {
          const isExpanded = expandedId === run.id;
          return (
            <div
              key={run.id}
              className="bg-app-card rounded-xl border border-border-default overflow-hidden shadow-dark-sm transition"
            >
              <div
                onClick={() => toggleExpand(run.id)}
                className="p-4 flex items-center justify-between cursor-pointer hover:bg-app-cardSecondary/60 transition"
              >
                <div className="flex items-center space-x-3">
                  <div className="p-1.5 rounded-lg bg-app-cardSecondary border border-border-subtle text-content-muted">
                    {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                  </div>
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-bold text-content-primary">{run.agentRole}</span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-app-cardSecondary border border-border-subtle text-content-muted">
                        {run.stage}
                      </span>
                    </div>
                    <p className="text-xs text-content-secondary mt-0.5">{run.auditMessage}</p>
                  </div>
                </div>

                <div className="flex items-center space-x-3">
                  <span className="text-[11px] text-content-muted hidden sm:inline-flex items-center space-x-1">
                    <Clock className="w-3 h-3" />
                    <span>{run.timestamp}</span>
                  </span>

                  {run.status === "paused" ? (
                    <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-accent-amber/10 text-accent-amber border border-accent-amber/20 flex items-center space-x-1">
                      <Shield className="w-3 h-3" />
                      <span>Paused Gate</span>
                    </span>
                  ) : (
                    <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-accent-emerald/10 text-accent-emerald border border-accent-emerald/20 flex items-center space-x-1">
                      <CheckCircle className="w-3 h-3" />
                      <span>Executed</span>
                    </span>
                  )}
                </div>
              </div>

              {/* Expanded JSON & State Details */}
              {isExpanded && (
                <div className="border-t border-border-subtle bg-app-cardSecondary/70 p-4 space-y-3 text-xs">
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
                    <div className="p-2 rounded bg-app-card border border-border-subtle">
                      <span className="text-content-muted">Model / Extractor</span>
                      <p className="font-mono font-semibold text-content-primary truncate">{run.modelVersion}</p>
                    </div>
                    <div className="p-2 rounded bg-app-card border border-border-subtle">
                      <span className="text-content-muted">Checkpoint ID</span>
                      <p className="font-mono font-semibold text-accent-secondary truncate">{run.checkpointId}</p>
                    </div>
                    <div className="p-2 rounded bg-app-card border border-border-subtle">
                      <span className="text-content-muted">Tool Invocations</span>
                      <p className="font-mono font-semibold text-content-primary">{run.toolCallsCount}</p>
                    </div>
                    <div className="p-2 rounded bg-app-card border border-border-subtle">
                      <span className="text-content-muted">Telemetry Run ID</span>
                      <p className="font-mono font-semibold text-content-primary truncate">{run.id}</p>
                    </div>
                  </div>

                  <div>
                    <span className="text-[10px] uppercase font-bold text-content-muted flex items-center space-x-1 mb-1">
                      <Terminal className="w-3 h-3" />
                      <span>Execution Metadata Payload</span>
                    </span>
                    <pre className="p-3 bg-app-bg text-content-secondary rounded-lg font-mono text-[11px] overflow-x-auto border border-border-subtle">
                      {JSON.stringify(run.details, null, 2)}
                    </pre>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
