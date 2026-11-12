"use client";

import React, { useState } from "react";
import {
  ShieldCheck,
  UserCircle,
  Briefcase,
  FileText,
  Activity,
  Menu,
  X,
  Layers,
} from "lucide-react";

export type TabKey = "onboarding" | "matches" | "packages" | "audit";

interface NavbarProps {
  activeTab: TabKey;
  onTabChange: (tab: TabKey) => void;
}

export const Navbar: React.FC<NavbarProps> = ({ activeTab, onTabChange }) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navItems: { key: TabKey; label: string; icon: React.ReactNode }[] = [
    { key: "onboarding", label: "Profile & Onboarding", icon: <UserCircle className="w-4 h-4" /> },
    { key: "matches", label: "Job Matches", icon: <Briefcase className="w-4 h-4" /> },
    { key: "packages", label: "Application Packages", icon: <FileText className="w-4 h-4" /> },
    { key: "audit", label: "Audit & Runs", icon: <Activity className="w-4 h-4" /> },
  ];

  return (
    <header className="border-b border-border-default/60 bg-app-nav/80 backdrop-blur-md sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex justify-between items-center h-16">
        {/* Brand identity */}
        <div className="flex items-center space-x-3 cursor-pointer" onClick={() => onTabChange("onboarding")}>
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-accent-primary to-accent-purple flex items-center justify-center shadow-lg shadow-accent-primary/20 ring-1 ring-white/10">
            <Layers className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="font-bold text-content-primary text-base tracking-tight leading-none">
                AgentFlow
              </h1>
              <span className="text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded bg-accent-primary/10 text-accent-secondary border border-accent-primary/20">
                Copilot
              </span>
            </div>
            <p className="text-[11px] text-content-secondary mt-0.5 font-normal">
              Multi-Agent Job Search Platform
            </p>
          </div>
        </div>

        {/* Desktop Navigation */}
        <nav className="hidden md:flex items-center space-x-1">
          {navItems.map((item) => {
            const isActive = activeTab === item.key;
            return (
              <button
                key={item.key}
                onClick={() => onTabChange(item.key)}
                className={`flex items-center space-x-2 px-3.5 py-2 rounded-lg text-xs font-medium transition-all ${
                  isActive
                    ? "bg-app-card text-accent-secondary border border-border-default shadow-sm"
                    : "text-content-secondary hover:text-content-primary hover:bg-app-cardSecondary/60"
                }`}
              >
                {item.icon}
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Safe Gate Status Badge */}
        <div className="hidden sm:flex items-center space-x-3">
          <div className="flex items-center space-x-2 px-3 py-1.5 rounded-full bg-accent-emerald/10 border border-accent-emerald/25 shadow-sm">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent-emerald opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-accent-emerald"></span>
            </span>
            <ShieldCheck className="w-3.5 h-3.5 text-accent-emerald" />
            <span className="text-xs font-medium text-accent-emerald">Safe Gate Active</span>
          </div>
        </div>

        {/* Mobile menu trigger */}
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="md:hidden p-2 rounded-lg bg-app-card text-content-secondary hover:text-content-primary border border-border-default"
        >
          {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden border-b border-border-default bg-app-secondary px-4 pt-2 pb-4 space-y-1">
          {navItems.map((item) => {
            const isActive = activeTab === item.key;
            return (
              <button
                key={item.key}
                onClick={() => {
                  onTabChange(item.key);
                  setMobileMenuOpen(false);
                }}
                className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-xs font-medium transition ${
                  isActive
                    ? "bg-app-card text-accent-secondary border border-border-default"
                    : "text-content-secondary hover:bg-app-cardSecondary"
                }`}
              >
                {item.icon}
                <span>{item.label}</span>
              </button>
            );
          })}
          <div className="pt-2">
            <div className="flex items-center space-x-2 px-3 py-2 rounded-lg bg-accent-emerald/10 border border-accent-emerald/20 text-xs text-accent-emerald font-medium">
              <ShieldCheck className="w-4 h-4" />
              <span>Safe Gate Active (Zero Unattended Actions)</span>
            </div>
          </div>
        </div>
      )}
    </header>
  );
};
