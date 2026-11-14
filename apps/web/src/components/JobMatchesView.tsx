"use client";

import React, { useState } from "react";
import {
  Briefcase,
  Search,
  Filter,
  CheckCircle,
  AlertCircle,
  ExternalLink,
  Bookmark,
  ThumbsDown,
  Sparkles,
  MapPin,
  Building,
  DollarSign,
  Clock,
} from "lucide-react";

interface JobMatch {
  id: string;
  title: string;
  company: string;
  location: string;
  workMode: "Remote" | "Hybrid" | "On-site";
  salary: string;
  matchScore: number;
  scoreBreakdown: {
    skills: number;
    seniority: number;
    location: number;
    recency: number;
  };
  matchedSkills: string[];
  missingSkills: string[];
  explanation: string;
  sourceUrl: string;
  postedAt: string;
}

const SAMPLE_MATCHES: JobMatch[] = [
  {
    id: "job_01",
    title: "Senior Backend Engineer (Python / Distributed Systems)",
    company: "CloudScale Data Technologies",
    location: "San Francisco, CA (or Remote)",
    workMode: "Remote",
    salary: "$165,000 - $190,000",
    matchScore: 94,
    scoreBreakdown: { skills: 96, seniority: 95, location: 95, recency: 90 },
    matchedSkills: ["Python", "FastAPI", "PostgreSQL", "Docker", "AsyncIO"],
    missingSkills: ["Kafka"],
    explanation:
      "Strong alignment with verified candidate expertise in asynchronous Python pipelines and relational database optimization. Missing Apache Kafka is deemed a trainable gap.",
    sourceUrl: "https://example.com/jobs/cloudscale-backend",
    postedAt: "2 days ago",
  },
  {
    id: "job_02",
    title: "Lead AI Application Architect",
    company: "Synthetix Labs",
    location: "Austin, TX (Hybrid)",
    workMode: "Hybrid",
    salary: "$180,000 - $210,000",
    matchScore: 89,
    scoreBreakdown: { skills: 88, seniority: 92, location: 85, recency: 92 },
    matchedSkills: ["Python", "FastAPI", "Docker", "Pydantic"],
    missingSkills: ["Kubernetes", "Redis Streams"],
    explanation:
      "Matches seniority level and core microservices stack. Requires familiarity with container orchestration tools which can be supplemented via recent projects.",
    sourceUrl: "https://example.com/jobs/synthetix-ai-lead",
    postedAt: "1 day ago",
  },
  {
    id: "job_03",
    title: "Senior Full Stack Systems Developer",
    company: "Apex Global FinTech",
    location: "New York, NY",
    workMode: "Hybrid",
    salary: "$170,000 - $195,000",
    matchScore: 82,
    scoreBreakdown: { skills: 80, seniority: 88, location: 75, recency: 85 },
    matchedSkills: ["Python", "PostgreSQL", "TypeScript"],
    missingSkills: ["GraphQL", "React Query"],
    explanation:
      "Solid foundation in backend data modeling and core TypeScript. Location requires hybrid presence in NYC financial district.",
    sourceUrl: "https://example.com/jobs/apex-fullstack",
    postedAt: "4 days ago",
  },
];

export const JobMatchesView: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedFilter, setSelectedFilter] = useState<string>("all");
  const [shortlisted, setShortlisted] = useState<Record<string, boolean>>({});
  const [dismissed, setDismissed] = useState<Record<string, boolean>>({});

  const toggleShortlist = (id: string) => {
    setShortlisted((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const toggleDismiss = (id: string) => {
    setDismissed((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const filteredMatches = SAMPLE_MATCHES.filter((job) => {
    if (dismissed[job.id]) return false;
    if (selectedFilter !== "all" && job.workMode.toLowerCase() !== selectedFilter.toLowerCase())
      return false;
    if (
      searchTerm &&
      !job.title.toLowerCase().includes(searchTerm.toLowerCase()) &&
      !job.company.toLowerCase().includes(searchTerm.toLowerCase())
    )
      return false;
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Search & Filter Bar */}
      <div className="bg-app-card rounded-xl border border-border-default p-4 shadow-dark-sm flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-content-muted absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search roles, skills, or companies..."
            className="w-full text-xs pl-9 pr-3 py-2 bg-app-cardSecondary border border-border-default rounded-lg text-content-primary placeholder:text-content-muted focus:outline-none focus:border-border-active focus:ring-1 focus:ring-accent-primary"
          />
        </div>

        <div className="flex items-center space-x-2 w-full sm:w-auto overflow-x-auto">
          <Filter className="w-4 h-4 text-content-muted flex-shrink-0" />
          {["all", "remote", "hybrid", "on-site"].map((filter) => (
            <button
              key={filter}
              onClick={() => setSelectedFilter(filter)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition whitespace-nowrap ${
                selectedFilter === filter
                  ? "bg-accent-primary text-white"
                  : "bg-app-cardSecondary text-content-secondary hover:text-content-primary border border-border-subtle"
              }`}
            >
              {filter}
            </button>
          ))}
        </div>
      </div>

      {/* Matching Jobs List */}
      <div className="space-y-4">
        {filteredMatches.map((job) => {
          const isSaved = shortlisted[job.id];
          return (
            <div
              key={job.id}
              className="bg-app-card rounded-xl border border-border-default p-5 shadow-dark-sm space-y-4 hover:border-border-active/50 transition-all"
            >
              {/* Header row */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="text-xs font-bold text-accent-secondary bg-accent-primary/10 border border-accent-primary/20 px-2.5 py-0.5 rounded-full">
                      {job.matchScore}% Match Fit
                    </span>
                    <span className="text-[11px] text-content-muted flex items-center space-x-1">
                      <Clock className="w-3 h-3" />
                      <span>{job.postedAt}</span>
                    </span>
                  </div>
                  <h3 className="text-base font-bold text-content-primary mt-1.5">{job.title}</h3>
                  <div className="flex flex-wrap items-center gap-3 text-xs text-content-secondary mt-1">
                    <span className="flex items-center space-x-1">
                      <Building className="w-3.5 h-3.5 text-content-muted" />
                      <span>{job.company}</span>
                    </span>
                    <span className="flex items-center space-x-1">
                      <MapPin className="w-3.5 h-3.5 text-content-muted" />
                      <span>{job.location}</span>
                    </span>
                    <span className="flex items-center space-x-1">
                      <DollarSign className="w-3.5 h-3.5 text-accent-emerald" />
                      <span>{job.salary}</span>
                    </span>
                  </div>
                </div>

                {/* Score Breakdown Pills */}
                <div className="flex items-center space-x-2 text-[11px] font-mono bg-app-cardSecondary p-2 rounded-lg border border-border-subtle">
                  <div className="text-center px-2 border-r border-border-subtle">
                    <p className="text-content-muted">Skills</p>
                    <p className="font-bold text-accent-emerald">{job.scoreBreakdown.skills}%</p>
                  </div>
                  <div className="text-center px-2 border-r border-border-subtle">
                    <p className="text-content-muted">Level</p>
                    <p className="font-bold text-accent-primary">{job.scoreBreakdown.seniority}%</p>
                  </div>
                  <div className="text-center px-2">
                    <p className="text-content-muted">Location</p>
                    <p className="font-bold text-content-primary">{job.scoreBreakdown.location}%</p>
                  </div>
                </div>
              </div>

              {/* Skills matched & missing */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2 border-t border-border-subtle text-xs">
                <div>
                  <p className="text-[11px] font-bold uppercase text-content-muted mb-1.5 flex items-center">
                    <CheckCircle className="w-3 h-3 text-accent-emerald mr-1" />
                    Verified Matching Skills
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {job.matchedSkills.map((s, i) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 rounded bg-accent-emerald/10 text-accent-emerald border border-accent-emerald/20 text-[11px]"
                      >
                        {s}
                      </span>
                    ))}
                  </div>
                </div>

                <div>
                  <p className="text-[11px] font-bold uppercase text-content-muted mb-1.5 flex items-center">
                    <AlertCircle className="w-3 h-3 text-accent-amber mr-1" />
                    Skill Gaps (Trainable)
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {job.missingSkills.map((s, i) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 rounded bg-accent-amber/10 text-accent-amber border border-accent-amber/20 text-[11px]"
                      >
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Explainable Fit Reason */}
              <div className="p-3 bg-app-cardSecondary rounded-lg border border-border-subtle text-xs text-content-secondary flex items-start space-x-2">
                <Sparkles className="w-3.5 h-3.5 text-accent-purple flex-shrink-0 mt-0.5" />
                <p>
                  <strong className="text-content-primary">Match Explanation:</strong> {job.explanation}
                </p>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-between pt-1">
                <a
                  href={job.sourceUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-accent-secondary hover:underline flex items-center space-x-1"
                >
                  <span>View Original Job Posting</span>
                  <ExternalLink className="w-3 h-3" />
                </a>

                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => toggleDismiss(job.id)}
                    className="p-2 rounded-lg bg-app-cardSecondary hover:bg-app-panel text-content-muted hover:text-content-primary border border-border-subtle transition"
                    title="Dismiss Role"
                  >
                    <ThumbsDown className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => toggleShortlist(job.id)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition ${
                      isSaved
                        ? "bg-accent-emerald text-white"
                        : "bg-accent-primary hover:bg-blue-600 text-white shadow-dark-sm"
                    }`}
                  >
                    <Bookmark className="w-3.5 h-3.5" />
                    <span>{isSaved ? "Shortlisted" : "Shortlist Job"}</span>
                  </button>
                </div>
              </div>
            </div>
          );
        })}

        {filteredMatches.length === 0 && (
          <div className="p-12 text-center bg-app-card rounded-xl border border-dashed border-border-default text-content-muted space-y-2">
            <Briefcase className="w-8 h-8 mx-auto text-content-muted" />
            <p className="text-sm font-semibold text-content-primary">No Matching Roles Found</p>
            <p className="text-xs">Try adjusting your search criteria or resetting filters.</p>
          </div>
        )}
      </div>
    </div>
  );
};

