import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AgentFlow — Multi-Agent Job Search Copilot",
  description: "Collaborative multi-agent job-search copilot with human-in-the-loop verification and LangGraph workflow orchestration.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased min-h-screen bg-app-bg text-content-primary selection:bg-accent-primary/30 selection:text-white">
        {children}
      </body>
    </html>
  );
}
