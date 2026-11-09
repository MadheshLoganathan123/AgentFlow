import React from "react";
import { ShieldCheck, UserCircle, Briefcase, FileText, Activity } from "lucide-react";

export const Navbar: React.FC = () => {
  return (
    <header className="border-b border-slate-200 bg-white sticky top-0 z-50 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex justify-between items-center h-16">
        <div className="flex items-center space-x-3">
          <div className="bg-blue-600 text-white p-2 rounded-lg font-bold text-lg flex items-center justify-center shadow-md">
            AF
          </div>
          <div>
            <h1 className="font-bold text-slate-900 text-lg leading-tight">AgentFlow</h1>
            <p className="text-xs text-slate-500 font-medium">Job-Seeker AI Copilot</p>
          </div>
        </div>

        <nav className="flex space-x-6 text-sm font-medium text-slate-600">
          <a href="#" className="flex items-center space-x-1.5 text-blue-600 hover:text-blue-700">
            <UserCircle className="w-4 h-4" />
            <span>Profile & Onboarding</span>
          </a>
          <a href="#" className="flex items-center space-x-1.5 hover:text-slate-900">
            <Briefcase className="w-4 h-4" />
            <span>Job Matches</span>
          </a>
          <a href="#" className="flex items-center space-x-1.5 hover:text-slate-900">
            <FileText className="w-4 h-4" />
            <span>Application Packages</span>
          </a>
          <a href="#" className="flex items-center space-x-1.5 hover:text-slate-900">
            <Activity className="w-4 h-4" />
            <span>Audit & Runs</span>
          </a>
        </nav>

        <div className="flex items-center space-x-2">
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
            <ShieldCheck className="w-3.5 h-3.5 mr-1" />
            Safe Gate Active
          </span>
        </div>
      </div>
    </header>
  );
};

