"use client";

import React, { useState } from "react";
import { Upload, FileText, CheckCircle2, AlertCircle } from "lucide-react";

interface ResumeUploaderProps {
  onProfileExtracted: (data: any) => void;
}

export const ResumeUploader: React.FC<ResumeUploaderProps> = ({ onProfileExtracted }) => {
  const [file, setFile] = useState<File | null>(null);
  const [rawText, setRawText] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file && !rawText.trim()) {
      setError("Please select a resume file or paste text content.");
      return;
    }

    setIsLoading(true);
    setError(null);

    const formData = new FormData();
    if (file) {
      formData.append("file", file);
    } else {
      formData.append("raw_text", rawText);
    }
    formData.append("user_id", "demo_job_seeker");

    try {
      const response = await fetch("http://localhost:8000/api/v1/profile/upload-resume", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed with status ${response.status}`);
      }

      const result = await response.json();
      onProfileExtracted(result);
    } catch (err: any) {
      // Fallback for demonstration when backend server is spun up locally
      console.warn("API request error:", err);
      setError("Could not connect to backend API at http://localhost:8000. Ensure FastAPI is running.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
      <div className="flex items-center space-x-3 mb-4">
        <div className="p-2.5 bg-blue-50 text-blue-600 rounded-lg">
          <Upload className="w-5 h-5" />
        </div>
        <div>
          <h2 className="text-lg font-bold text-slate-900">Step 1: Upload Resume & Profile Ingestion</h2>
          <p className="text-sm text-slate-500">
            Open-source parser extracts factual claims with exact citations and flags inferences.
          </p>
        </div>
      </div>

      <form onSubmit={handleUpload} className="space-y-4">
        <div className="border-2 border-dashed border-slate-200 hover:border-blue-400 rounded-lg p-6 text-center cursor-pointer transition">
          <input
            type="file"
            id="resume-file"
            accept=".pdf,.txt"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="hidden"
          />
          <label htmlFor="resume-file" className="cursor-pointer">
            <FileText className="w-10 h-10 text-slate-400 mx-auto mb-2" />
            <span className="text-sm font-semibold text-blue-600 hover:underline">
              {file ? file.name : "Choose PDF or TXT resume"}
            </span>
            <p className="text-xs text-slate-400 mt-1">PDF or Plain Text up to 15MB</p>
          </label>
        </div>

        <div className="text-center text-xs text-slate-400 uppercase font-semibold">Or paste resume text</div>

        <textarea
          rows={4}
          value={rawText}
          onChange={(e) => setRawText(e.target.value)}
          placeholder="Paste resume text directly here..."
          className="w-full text-xs font-mono p-3 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        />

        {error && (
          <div className="flex items-center space-x-2 text-rose-600 bg-rose-50 p-3 rounded-lg text-xs">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <button
          type="submit"
          disabled={isLoading}
          className="w-full py-2.5 px-4 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition disabled:opacity-50 flex items-center justify-center space-x-2"
        >
          {isLoading ? (
            <span>Extracting facts & checking evidence...</span>
          ) : (
            <>
              <CheckCircle2 className="w-4 h-4" />
              <span>Ingest & Extract Facts</span>
            </>
          )}
        </button>
      </form>
    </div>
  );
};

