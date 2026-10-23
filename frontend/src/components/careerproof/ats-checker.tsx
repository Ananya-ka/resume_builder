"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Search,
  CheckCircle2,
  AlertCircle,
  TrendingUp,
  FileText,
  Briefcase,
  Copy,
  Check,
  Sparkles,
  ArrowRight,
  ShieldAlert,
  Zap,
  BarChart3,
  RefreshCw,
  Sliders,
  HelpCircle,
  UploadCloud,
  FileUp,
} from "lucide-react";
import {
  getATSCatalog,
  checkATSScore,
  uploadResumeForATS,
  uploadJDForATS,
  type ATSCatalog,
  type ATSCheckResult,
  type ATSUploadResponse,
} from "@/lib/careerproof/api";

interface ATSCheckerProps {
  initialResumeId?: number;
  initialJobId?: number;
  onClose?: () => void;
  onSelectDraft?: (draftId: number) => void;
  onApplyJobToWorkspace?: (company: string, role: string, jdText: string) => void;
}

export function ATSCheckerModal({
  initialResumeId,
  initialJobId,
  onClose,
  onSelectDraft,
  onApplyJobToWorkspace,
}: ATSCheckerProps) {
  const [catalog, setCatalog] = useState<ATSCatalog>({ resumes: [], jobs: [] });
  const [loadingCatalog, setLoadingCatalog] = useState(true);

  // Resume states
  const [resumeMode, setResumeMode] = useState<"saved" | "upload" | "paste">("saved");
  const [selectedResumeId, setSelectedResumeId] = useState<number | undefined>(initialResumeId);
  const [pastedResumeText, setPastedResumeText] = useState("");
  const resumeFileInputRef = useRef<HTMLInputElement>(null);
  const [uploadedResume, setUploadedResume] = useState<ATSUploadResponse | null>(null);
  const [isUploadingResume, setIsUploadingResume] = useState(false);
  const [saveResumeToLibrary, setSaveResumeToLibrary] = useState(true);
  const [resumeUploadError, setResumeUploadError] = useState<string | null>(null);

  // Job description states
  const [jobMode, setJobMode] = useState<"saved" | "upload" | "paste">("saved");
  const [selectedJobId, setSelectedJobId] = useState<number | undefined>(initialJobId);
  const [pastedCompany, setPastedCompany] = useState("");
  const [pastedRole, setPastedRole] = useState("");
  const [pastedJdText, setPastedJdText] = useState("");
  const jdFileInputRef = useRef<HTMLInputElement>(null);
  const [uploadedJd, setUploadedJd] = useState<ATSUploadResponse | null>(null);
  const [isUploadingJd, setIsUploadingJd] = useState(false);
  const [saveJdToLibrary, setSaveJdToLibrary] = useState(true);
  const [jdUploadError, setJdUploadError] = useState<string | null>(null);

  // Scan state
  const [isScanning, setIsScanning] = useState(false);
  const [scanResult, setScanResult] = useState<ATSCheckResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copiedMissing, setCopiedMissing] = useState(false);

  useEffect(() => {
    async function loadCatalog() {
      try {
        setLoadingCatalog(true);
        const data = await getATSCatalog();
        setCatalog(data);

        // Preselect if available
        if (!selectedResumeId && data.resumes.length > 0) {
          setSelectedResumeId(data.resumes[0].id);
        }
        if (!selectedJobId && data.jobs.length > 0) {
          setSelectedJobId(data.jobs[0].id);
        }
      } catch (err) {
        console.error("Failed to load ATS catalog", err);
      } finally {
        setLoadingCatalog(false);
      }
    }
    void loadCatalog();
  }, []);

  async function handleResumeFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setResumeUploadError(null);
    setIsUploadingResume(true);
    try {
      const res = await uploadResumeForATS(file, saveResumeToLibrary);
      setUploadedResume(res);
      try {
        const cat = await getATSCatalog();
        setCatalog(cat);
      } catch (catErr) {
        console.error(catErr);
      }
      if (res.resume_id) {
        setSelectedResumeId(res.resume_id);
      }
    } catch (err: unknown) {
      setResumeUploadError(err instanceof Error ? err.message : "Failed to upload resume file.");
    } finally {
      setIsUploadingResume(false);
      e.target.value = "";
    }
  }

  async function handleJdFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setJdUploadError(null);
    setIsUploadingJd(true);
    try {
      const res = await uploadJDForATS(file, pastedCompany, pastedRole, saveJdToLibrary);
      setUploadedJd(res);
      if (res.company && !pastedCompany) setPastedCompany(res.company);
      if (res.role && !pastedRole) setPastedRole(res.role);
      try {
        const cat = await getATSCatalog();
        setCatalog(cat);
      } catch (catErr) {
        console.error(catErr);
      }
      if (res.job_id) {
        setSelectedJobId(res.job_id);
      }
    } catch (err: unknown) {
      setJdUploadError(err instanceof Error ? err.message : "Failed to upload job description file.");
    } finally {
      setIsUploadingJd(false);
      e.target.value = "";
    }
  }

  async function handleRunScan() {
    setError(null);
    setIsScanning(true);

    try {
      const payload: Parameters<typeof checkATSScore>[0] = {};

      // Resume resolution
      if (resumeMode === "saved") {
        if (!selectedResumeId) {
          throw new Error("Please choose a resume from your saved library.");
        }
        payload.resume_id = selectedResumeId;
      } else if (resumeMode === "upload") {
        if (!uploadedResume) {
          throw new Error("Please upload a resume file (PDF, DOCX, TXT).");
        }
        if (uploadedResume.resume_id) {
          payload.resume_id = uploadedResume.resume_id;
        } else {
          payload.resume_text = uploadedResume.text;
        }
      } else {
        if (!pastedResumeText.trim()) {
          throw new Error("Please paste your resume text to evaluate.");
        }
        payload.resume_text = pastedResumeText;
      }

      // Job resolution
      if (jobMode === "saved") {
        if (!selectedJobId) {
          throw new Error("Please choose a target job description.");
        }
        payload.job_id = selectedJobId;
      } else if (jobMode === "upload") {
        if (!uploadedJd) {
          throw new Error("Please upload a job description file (PDF, DOCX, TXT).");
        }
        if (uploadedJd.job_id) {
          payload.job_id = uploadedJd.job_id;
        } else {
          payload.jd_text = uploadedJd.text;
          payload.company = uploadedJd.company || pastedCompany.trim() || "Target Company";
          payload.role = uploadedJd.role || pastedRole.trim() || "Target Role";
        }
      } else {
        if (!pastedJdText.trim()) {
          throw new Error("Please paste the job description text.");
        }
        payload.jd_text = pastedJdText;
        payload.company = pastedCompany.trim() || "Target Company";
        payload.role = pastedRole.trim() || "Target Role";
      }

      const res = await checkATSScore(payload);
      setScanResult(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "ATS evaluation failed. Please check inputs.");
    } finally {
      setIsScanning(false);
    }
  }

  function handleCopyMissing() {
    if (!scanResult?.missing_keywords.length) return;
    navigator.clipboard.writeText(scanResult.missing_keywords.join(", "));
    setCopiedMissing(true);
    setTimeout(() => setCopiedMissing(false), 2000);
  }

  const scoreColor =
    !scanResult
      ? "#6b7280"
      : scanResult.ats_score >= 80
      ? "#10b981"
      : scanResult.ats_score >= 65
      ? "#3b82f6"
      : scanResult.ats_score >= 50
      ? "#f59e0b"
      : "#ef4444";

  return (
    <div
      style={{
        background: "#ffffff",
        border: "1px solid #e5e7eb",
        borderRadius: 12,
        padding: "24px 28px",
        boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.05)",
        marginBottom: 24,
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: 20,
          borderBottom: "1px solid #f3f4f6",
          paddingBottom: 16,
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 34,
                height: 34,
                borderRadius: 8,
                background: "#f0fdf4",
                color: "#16a34a",
                border: "1px solid #bbf7d0",
              }}
            >
              <BarChart3 size={18} />
            </span>
            <h2 style={{ margin: 0, fontSize: "1.25rem", fontWeight: 700, color: "#111827" }}>
              ATS Match & Gap Scanner
            </h2>
          </div>
          <p style={{ margin: "4px 0 0 44px", fontSize: "0.875rem", color: "#6b7280" }}>
            Benchmark any existing resume against a target JD. Identifies missing keywords, keyword density, section health, and CareerProof score uplift.
          </p>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            style={{
              border: "1px solid #d1d5db",
              background: "#ffffff",
              borderRadius: "6px",
              padding: "6px 12px",
              display: "flex",
              alignItems: "center",
              gap: "6px",
              color: "#374151",
              fontSize: "0.825rem",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            ✕ Close Scanner
          </button>
        )}
      </div>

      {/* Input Selection Columns */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 20,
          marginBottom: 20,
        }}
      >
        {/* Left Column: Resume Selection */}
        <div
          style={{
            border: "1px solid #e5e7eb",
            borderRadius: 10,
            padding: 16,
            background: "#fcfdfd",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 12,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 600, fontSize: "0.9rem", color: "#374151" }}>
              <FileText size={16} color="#4f46e5" />
              <span>Select Candidate Resume</span>
            </div>
            <div style={{ display: "flex", background: "#f3f4f6", borderRadius: 6, padding: 2 }}>
              <button
                type="button"
                onClick={() => setResumeMode("saved")}
                style={{
                  border: "none",
                  background: resumeMode === "saved" ? "#ffffff" : "transparent",
                  padding: "4px 8px",
                  borderRadius: 4,
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  color: resumeMode === "saved" ? "#111827" : "#6b7280",
                  cursor: "pointer",
                  boxShadow: resumeMode === "saved" ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
                }}
              >
                Saved
              </button>
              <button
                type="button"
                onClick={() => setResumeMode("upload")}
                style={{
                  border: "none",
                  background: resumeMode === "upload" ? "#ffffff" : "transparent",
                  padding: "4px 8px",
                  borderRadius: 4,
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  color: resumeMode === "upload" ? "#111827" : "#6b7280",
                  cursor: "pointer",
                  boxShadow: resumeMode === "upload" ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
                }}
              >
                Upload File
              </button>
              <button
                type="button"
                onClick={() => setResumeMode("paste")}
                style={{
                  border: "none",
                  background: resumeMode === "paste" ? "#ffffff" : "transparent",
                  padding: "4px 8px",
                  borderRadius: 4,
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  color: resumeMode === "paste" ? "#111827" : "#6b7280",
                  cursor: "pointer",
                  boxShadow: resumeMode === "paste" ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
                }}
              >
                Paste
              </button>
            </div>
          </div>

          {resumeMode === "saved" && (
            <div>
              {loadingCatalog ? (
                <div style={{ fontSize: "0.85rem", color: "#9ca3af", padding: "10px 0" }}>Loading resumes...</div>
              ) : catalog.resumes.length === 0 ? (
                <div style={{ fontSize: "0.85rem", color: "#dc2626", padding: "10px 0" }}>
                  No saved resumes found. Click "Upload File" above to add one.
                </div>
              ) : (
                <select
                  value={selectedResumeId}
                  onChange={(e) => setSelectedResumeId(Number(e.target.value))}
                  style={{
                    width: "100%",
                    padding: "9px 12px",
                    borderRadius: 6,
                    border: "1px solid #d1d5db",
                    fontSize: "0.875rem",
                    color: "#1f2937",
                    background: "#ffffff",
                    outline: "none",
                  }}
                >
                  {catalog.resumes.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name} {r.bullet_count ? `(${r.bullet_count} bullets)` : ""}
                    </option>
                  ))}
                </select>
              )}
            </div>
          )}

          {resumeMode === "upload" && (
            <div>
              <input
                ref={resumeFileInputRef}
                type="file"
                accept=".pdf,.docx,.txt"
                style={{ display: "none" }}
                onChange={(e) => void handleResumeFileUpload(e)}
              />
              {!uploadedResume ? (
                <div
                  style={{
                    border: "2px dashed #cbd5e1",
                    borderRadius: 8,
                    padding: "20px 14px",
                    textAlign: "center",
                    background: "#ffffff",
                    cursor: isUploadingResume ? "wait" : "pointer",
                    transition: "all 0.2s",
                  }}
                  onClick={() => !isUploadingResume && resumeFileInputRef.current?.click()}
                >
                  {isUploadingResume ? (
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
                      <RefreshCw size={24} className="spin" color="#4f46e5" />
                      <span style={{ fontSize: "0.85rem", color: "#4f46e5", fontWeight: 600 }}>
                        Reading & parsing resume file...
                      </span>
                    </div>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
                      <UploadCloud size={28} color="#6366f1" />
                      <span style={{ fontSize: "0.875rem", fontWeight: 600, color: "#1e293b" }}>
                        Click to select resume file (PDF, DOCX, TXT)
                      </span>
                      <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
                        Instant extraction · Up to 10 MB
                      </span>
                    </div>
                  )}
                </div>
              ) : (
                <div
                  style={{
                    background: "#f0fdf4",
                    border: "1px solid #bbf7d0",
                    borderRadius: 8,
                    padding: 12,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <FileText size={20} color="#16a34a" />
                      <div>
                        <div style={{ fontSize: "0.85rem", fontWeight: 700, color: "#166534" }}>
                          {uploadedResume.filename}
                        </div>
                        <div style={{ fontSize: "0.75rem", color: "#15803d" }}>
                          {uploadedResume.word_count} words extracted · {uploadedResume.detected_skills_count || 0} skills detected
                        </div>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setUploadedResume(null);
                        if (resumeFileInputRef.current) resumeFileInputRef.current.value = "";
                      }}
                      style={{
                        background: "none",
                        border: "none",
                        color: "#dc2626",
                        fontSize: "0.75rem",
                        fontWeight: 600,
                        cursor: "pointer",
                      }}
                    >
                      Change
                    </button>
                  </div>
                  <div style={{ marginTop: 8, fontSize: "0.75rem", color: "#166534", background: "#dcfce7", padding: "4px 8px", borderRadius: 4 }}>
                    ✓ Ready for ATS evaluation {uploadedResume.saved_to_library ? "and added to your library" : ""}
                  </div>
                  <details style={{ marginTop: 6, fontSize: "0.75rem", color: "#475569" }}>
                    <summary style={{ cursor: "pointer" }}>Preview extracted text snippet</summary>
                    <div style={{ marginTop: 4, padding: 6, background: "#ffffff", borderRadius: 4, border: "1px solid #e2e8f0", maxHeight: 70, overflowY: "auto", fontFamily: "monospace", fontSize: "0.7rem" }}>
                      {uploadedResume.preview}
                    </div>
                  </details>
                </div>
              )}
              {resumeUploadError && (
                <div style={{ color: "#dc2626", fontSize: "0.75rem", marginTop: 6 }}>
                  {resumeUploadError}
                </div>
              )}
              <label style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 8, fontSize: "0.75rem", color: "#64748b", cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={saveResumeToLibrary}
                  onChange={(e) => setSaveResumeToLibrary(e.target.checked)}
                />
                <span>Save to permanent resume library for future tailoring</span>
              </label>
            </div>
          )}

          {resumeMode === "paste" && (
            <div>
              <textarea
                value={pastedResumeText}
                onChange={(e) => setPastedResumeText(e.target.value)}
                placeholder="Paste raw resume text, bullet points, skills, and experience here..."
                rows={5}
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  borderRadius: 6,
                  border: "1px solid #d1d5db",
                  fontSize: "0.825rem",
                  color: "#1f2937",
                  fontFamily: "monospace",
                  resize: "vertical",
                  boxSizing: "border-box",
                }}
              />
              <div style={{ textAlign: "right", fontSize: "0.75rem", color: "#9ca3af", marginTop: 4 }}>
                {pastedResumeText ? `${pastedResumeText.split(/\s+/).filter(Boolean).length} words` : "Empty"}
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Target Job Selection */}
        <div
          style={{
            border: "1px solid #e5e7eb",
            borderRadius: 10,
            padding: 16,
            background: "#fcfdfd",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 12,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 600, fontSize: "0.9rem", color: "#374151" }}>
              <Briefcase size={16} color="#059669" />
              <span>Target Job Description</span>
            </div>
            <div style={{ display: "flex", background: "#f3f4f6", borderRadius: 6, padding: 2 }}>
              <button
                type="button"
                onClick={() => setJobMode("saved")}
                style={{
                  border: "none",
                  background: jobMode === "saved" ? "#ffffff" : "transparent",
                  padding: "4px 8px",
                  borderRadius: 4,
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  color: jobMode === "saved" ? "#111827" : "#6b7280",
                  cursor: "pointer",
                  boxShadow: jobMode === "saved" ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
                }}
              >
                Saved JDs
              </button>
              <button
                type="button"
                onClick={() => setJobMode("upload")}
                style={{
                  border: "none",
                  background: jobMode === "upload" ? "#ffffff" : "transparent",
                  padding: "4px 8px",
                  borderRadius: 4,
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  color: jobMode === "upload" ? "#111827" : "#6b7280",
                  cursor: "pointer",
                  boxShadow: jobMode === "upload" ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
                }}
              >
                Upload JD
              </button>
              <button
                type="button"
                onClick={() => setJobMode("paste")}
                style={{
                  border: "none",
                  background: jobMode === "paste" ? "#ffffff" : "transparent",
                  padding: "4px 8px",
                  borderRadius: 4,
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  color: jobMode === "paste" ? "#111827" : "#6b7280",
                  cursor: "pointer",
                  boxShadow: jobMode === "paste" ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
                }}
              >
                Paste
              </button>
            </div>
          </div>

          {jobMode === "saved" && (
            <div>
              {loadingCatalog ? (
                <div style={{ fontSize: "0.85rem", color: "#9ca3af", padding: "10px 0" }}>Loading jobs...</div>
              ) : catalog.jobs.length === 0 ? (
                <div style={{ fontSize: "0.85rem", color: "#dc2626", padding: "10px 0" }}>
                  No saved jobs found. Click "Upload JD" above to upload a job file.
                </div>
              ) : (
                <select
                  value={selectedJobId}
                  onChange={(e) => setSelectedJobId(Number(e.target.value))}
                  style={{
                    width: "100%",
                    padding: "9px 12px",
                    borderRadius: 6,
                    border: "1px solid #d1d5db",
                    fontSize: "0.875rem",
                    color: "#1f2937",
                    background: "#ffffff",
                    outline: "none",
                  }}
                >
                  {catalog.jobs.map((j) => (
                    <option key={j.id} value={j.id}>
                      {j.company} · {j.role} {j.keywords_count ? `(${j.keywords_count} keywords)` : ""}
                    </option>
                  ))}
                </select>
              )}
            </div>
          )}

          {jobMode === "upload" && (
            <div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 8 }}>
                <input
                  type="text"
                  placeholder="Company (optional)"
                  value={pastedCompany}
                  onChange={(e) => setPastedCompany(e.target.value)}
                  style={{
                    padding: "7px 10px",
                    borderRadius: 6,
                    border: "1px solid #d1d5db",
                    fontSize: "0.825rem",
                  }}
                />
                <input
                  type="text"
                  placeholder="Role (optional)"
                  value={pastedRole}
                  onChange={(e) => setPastedRole(e.target.value)}
                  style={{
                    padding: "7px 10px",
                    borderRadius: 6,
                    border: "1px solid #d1d5db",
                    fontSize: "0.825rem",
                  }}
                />
              </div>
              <input
                ref={jdFileInputRef}
                type="file"
                accept=".pdf,.docx,.txt"
                style={{ display: "none" }}
                onChange={(e) => void handleJdFileUpload(e)}
              />
              {!uploadedJd ? (
                <div
                  style={{
                    border: "2px dashed #cbd5e1",
                    borderRadius: 8,
                    padding: "16px 14px",
                    textAlign: "center",
                    background: "#ffffff",
                    cursor: isUploadingJd ? "wait" : "pointer",
                    transition: "all 0.2s",
                  }}
                  onClick={() => !isUploadingJd && jdFileInputRef.current?.click()}
                >
                  {isUploadingJd ? (
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
                      <RefreshCw size={24} className="spin" color="#059669" />
                      <span style={{ fontSize: "0.85rem", color: "#059669", fontWeight: 600 }}>
                        Reading & parsing job description...
                      </span>
                    </div>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
                      <UploadCloud size={28} color="#059669" />
                      <span style={{ fontSize: "0.875rem", fontWeight: 600, color: "#1e293b" }}>
                        Click to select JD file (PDF, DOCX, TXT)
                      </span>
                      <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
                        Instant extraction · Up to 10 MB
                      </span>
                    </div>
                  )}
                </div>
              ) : (
                <div
                  style={{
                    background: "#ecfdf5",
                    border: "1px solid #a7f3d0",
                    borderRadius: 8,
                    padding: 12,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <Briefcase size={20} color="#059669" />
                      <div>
                        <div style={{ fontSize: "0.85rem", fontWeight: 700, color: "#065f46" }}>
                          {uploadedJd.company || pastedCompany || "Target Company"} · {uploadedJd.role || pastedRole || "Target Role"}
                        </div>
                        <div style={{ fontSize: "0.75rem", color: "#047857" }}>
                          {uploadedJd.filename} · {uploadedJd.word_count} words · {uploadedJd.detected_keywords_count || 0} keywords
                        </div>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setUploadedJd(null);
                        if (jdFileInputRef.current) jdFileInputRef.current.value = "";
                      }}
                      style={{
                        background: "none",
                        border: "none",
                        color: "#dc2626",
                        fontSize: "0.75rem",
                        fontWeight: 600,
                        cursor: "pointer",
                      }}
                    >
                      Change
                    </button>
                  </div>
                  <div style={{ marginTop: 8, fontSize: "0.75rem", color: "#065f46", background: "#d1fae5", padding: "4px 8px", borderRadius: 4 }}>
                    ✓ Ready for ATS evaluation {uploadedJd.saved_to_library ? "and saved to jobs" : ""}
                  </div>
                  <details style={{ marginTop: 6, fontSize: "0.75rem", color: "#475569" }}>
                    <summary style={{ cursor: "pointer" }}>Preview extracted JD snippet</summary>
                    <div style={{ marginTop: 4, padding: 6, background: "#ffffff", borderRadius: 4, border: "1px solid #e2e8f0", maxHeight: 70, overflowY: "auto", fontFamily: "monospace", fontSize: "0.7rem" }}>
                      {uploadedJd.preview}
                    </div>
                  </details>
                </div>
              )}
              {jdUploadError && (
                <div style={{ color: "#dc2626", fontSize: "0.75rem", marginTop: 6 }}>
                  {jdUploadError}
                </div>
              )}
              <label style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 8, fontSize: "0.75rem", color: "#64748b", cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={saveJdToLibrary}
                  onChange={(e) => setSaveJdToLibrary(e.target.checked)}
                />
                <span>Save to permanent target jobs library</span>
              </label>
            </div>
          )}

          {jobMode === "paste" && (
            <div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 8 }}>
                <input
                  type="text"
                  placeholder="Company (e.g. Google)"
                  value={pastedCompany}
                  onChange={(e) => setPastedCompany(e.target.value)}
                  style={{
                    padding: "7px 10px",
                    borderRadius: 6,
                    border: "1px solid #d1d5db",
                    fontSize: "0.825rem",
                  }}
                />
                <input
                  type="text"
                  placeholder="Role (e.g. Senior Software Engineer)"
                  value={pastedRole}
                  onChange={(e) => setPastedRole(e.target.value)}
                  style={{
                    padding: "7px 10px",
                    borderRadius: 6,
                    border: "1px solid #d1d5db",
                    fontSize: "0.825rem",
                  }}
                />
              </div>
              <textarea
                value={pastedJdText}
                onChange={(e) => setPastedJdText(e.target.value)}
                placeholder="Paste requirements, qualifications, and role description..."
                rows={4}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  borderRadius: 6,
                  border: "1px solid #d1d5db",
                  fontSize: "0.825rem",
                  color: "#1f2937",
                  fontFamily: "monospace",
                  resize: "vertical",
                  boxSizing: "border-box",
                }}
              />
            </div>
          )}
        </div>
      </div>

      {/* Error message */}
      {error && (
        <div
          style={{
            background: "#fef2f2",
            border: "1px solid #fecaca",
            color: "#991b1b",
            padding: "10px 14px",
            borderRadius: 6,
            fontSize: "0.85rem",
            marginBottom: 16,
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      {/* Run Scan Action */}
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 20 }}>
        <button
          type="button"
          onClick={() => void handleRunScan()}
          disabled={isScanning}
          style={{
            background: isScanning ? "#9ca3af" : "#0f172a",
            color: "#ffffff",
            border: "none",
            borderRadius: 8,
            padding: "11px 24px",
            fontWeight: 600,
            fontSize: "0.95rem",
            display: "flex",
            alignItems: "center",
            gap: 8,
            cursor: isScanning ? "not-allowed" : "pointer",
            boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
          }}
        >
          {isScanning ? (
            <>
              <RefreshCw size={16} className="spin" />
              <span>Scanning ATS Compatibility...</span>
            </>
          ) : (
            <>
              <Sparkles size={16} color="#fbbf24" />
              <span>Run ATS Match Evaluation</span>
            </>
          )}
        </button>
      </div>

      {/* RESULTS SECTION */}
      {scanResult && (
        <div
          style={{
            borderTop: "2px solid #f3f4f6",
            paddingTop: 24,
            animation: "fadeIn 0.3s ease-in-out",
          }}
        >
          {/* Hero Match Score Card */}
          <div
            style={{
              background: "linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)",
              border: "1px solid #e2e8f0",
              borderRadius: 12,
              padding: "20px 24px",
              display: "grid",
              gridTemplateColumns: "180px 1fr",
              gap: 24,
              alignItems: "center",
              marginBottom: 20,
            }}
          >
            {/* Score Gauge Circle */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                textAlign: "center",
                background: "#ffffff",
                borderRadius: 12,
                padding: "16px 12px",
                boxShadow: "0 4px 6px -1px rgba(0,0,0,0.05)",
                border: "1px solid #e5e7eb",
              }}
            >
              <div
                style={{
                  fontSize: "2.6rem",
                  fontWeight: 800,
                  color: scoreColor,
                  lineHeight: 1,
                  marginBottom: 6,
                }}
              >
                {scanResult.ats_score}%
              </div>
              <span
                style={{
                  fontSize: "0.75rem",
                  fontWeight: 700,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  color: scoreColor,
                  background: `${scoreColor}15`,
                  padding: "3px 8px",
                  borderRadius: 100,
                }}
              >
                {scanResult.score_label}
              </span>
            </div>

            {/* Explanatory Summary + Comparison */}
            <div>
              <div style={{ marginBottom: 12 }}>
                <h3 style={{ margin: "0 0 4px 0", fontSize: "1.1rem", fontWeight: 700, color: "#0f172a" }}>
                  {scanResult.summary_tagline}
                </h3>
                <p style={{ margin: 0, fontSize: "0.85rem", color: "#64748b" }}>
                  Evaluated <strong>{scanResult.resume_meta.name}</strong> against <strong>{scanResult.job_meta.company} · {scanResult.job_meta.role}</strong>.
                </p>
              </div>

              {/* Comparison Banner */}
              {scanResult.comparison?.has_optimized_version ? (
                <div
                  style={{
                    background: "#ecfdf5",
                    border: "1px solid #a7f3d0",
                    borderRadius: 8,
                    padding: "10px 14px",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <Zap size={18} color="#059669" />
                    <div>
                      <div style={{ fontSize: "0.875rem", fontWeight: 600, color: "#065f46" }}>
                        CareerProof Tailored Version Available!
                      </div>
                      <div style={{ fontSize: "0.8rem", color: "#047857" }}>
                        Existing: <strong>{scanResult.ats_score}%</strong> ➔ Tailored: <strong>{scanResult.comparison.optimized_score}%</strong>{" "}
                        <span style={{ fontWeight: 700, color: (scanResult.comparison.score_delta || 0) >= 0 ? "#059669" : "#dc2626" }}>
                          ({(scanResult.comparison.score_delta || 0) >= 0 ? `+${scanResult.comparison.score_delta}%` : `${scanResult.comparison.score_delta}%`} uplift)
                        </span>
                      </div>
                    </div>
                  </div>
                  {onSelectDraft && scanResult.comparison.optimization_id && (
                    <button
                      type="button"
                      onClick={() => onSelectDraft(scanResult.comparison!.optimization_id!)}
                      style={{
                        background: "#059669",
                        color: "#ffffff",
                        border: "none",
                        borderRadius: 6,
                        padding: "6px 14px",
                        fontSize: "0.8rem",
                        fontWeight: 600,
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                      }}
                    >
                      <span>View Tailored Version</span>
                      <ArrowRight size={14} />
                    </button>
                  )}
                </div>
              ) : (
                <div
                  style={{
                    background: "#fffbeb",
                    border: "1px solid #fde68a",
                    borderRadius: 8,
                    padding: "8px 14px",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <div style={{ fontSize: "0.825rem", color: "#92400e" }}>
                    No tailored draft created yet. You can bridge these gaps by running CareerProof Discovery.
                  </div>
                  {onApplyJobToWorkspace && jobMode === "paste" && (
                    <button
                      type="button"
                      onClick={() => onApplyJobToWorkspace(pastedCompany || "Target Company", pastedRole || "Target Role", pastedJdText)}
                      style={{
                        background: "#d97706",
                        color: "#ffffff",
                        border: "none",
                        borderRadius: 6,
                        padding: "5px 12px",
                        fontSize: "0.75rem",
                        fontWeight: 600,
                        cursor: "pointer",
                      }}
                    >
                      Use in Workspace
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Hard Eligibility Screening Gates */}
          {scanResult.hard_eligibility && scanResult.hard_eligibility.gates && scanResult.hard_eligibility.gates.length > 0 && (
            <div
              style={{
                marginBottom: 20,
                border: "1px solid",
                borderColor: scanResult.hard_eligibility.is_eligible ? "#bbf7d0" : scanResult.hard_eligibility.status === "unverifiable" ? "#fed7aa" : "#fca5a5",
                background: scanResult.hard_eligibility.is_eligible ? "#f0fdf4" : scanResult.hard_eligibility.status === "unverifiable" ? "#fffaf5" : "#fef2f2",
                borderRadius: 8,
                padding: 16,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10, flexWrap: "wrap", gap: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  {scanResult.hard_eligibility.is_eligible ? (
                    <CheckCircle2 size={18} color="#16a34a" />
                  ) : (
                    <AlertCircle size={18} color={scanResult.hard_eligibility.status === "unverifiable" ? "#ea580c" : "#dc2626"} />
                  )}
                  <span style={{ fontWeight: 700, fontSize: "0.9rem", color: scanResult.hard_eligibility.is_eligible ? "#166534" : "#991b1b" }}>
                    Hard Eligibility Screening: {scanResult.hard_eligibility.is_eligible ? "PASSED (Candidate Satisfies Mandatory Gating Criteria)" : scanResult.hard_eligibility.status === "unverifiable" ? "UNVERIFIABLE (Credentials Not Stated)" : "FAILED (Unmet Mandatory Requirements)"}
                  </span>
                </div>
                <span
                  style={{
                    fontSize: "0.72rem",
                    fontWeight: 700,
                    textTransform: "uppercase",
                    padding: "3px 8px",
                    borderRadius: 100,
                    background: scanResult.hard_eligibility.is_eligible ? "#dcfce7" : "#fee2e2",
                    color: scanResult.hard_eligibility.is_eligible ? "#166534" : "#991b1b",
                  }}
                >
                  {scanResult.hard_eligibility.status}
                </span>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: `repeat(${Math.min(scanResult.hard_eligibility.gates.length, 3)}, 1fr)`, gap: 10 }}>
                {scanResult.hard_eligibility.gates.map((g, idx) => (
                  <div
                    key={idx}
                    style={{
                      background: "#ffffff",
                      border: "1px solid #e5e7eb",
                      borderRadius: 6,
                      padding: 10,
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                      <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "#374151", textTransform: "capitalize" }}>
                        {g.gate_name.replace(/_/g, " ")}
                      </span>
                      <span style={{ fontSize: "0.7rem", fontWeight: 700, color: g.is_passed ? "#16a34a" : g.status === "unverifiable" ? "#ea580c" : "#dc2626" }}>
                        {g.is_passed ? "✓ Pass" : g.status === "unverifiable" ? "? Unverified" : "✕ Fail"}
                      </span>
                    </div>
                    <div style={{ fontSize: "0.72rem", color: "#6b7280" }}>
                      Required: <strong style={{ color: "#111827" }}>{String(g.required_value)}</strong> · Detected: <strong style={{ color: "#111827" }}>{String(g.candidate_value)}</strong>
                    </div>
                    {g.reason && (
                      <div style={{ fontSize: "0.68rem", color: g.is_passed ? "#15803d" : "#b91c1c", marginTop: 4 }}>
                        {g.reason}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Breakdown Metric Cards Grid */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(4, 1fr)",
              gap: 14,
              marginBottom: 20,
            }}
          >
            {/* Keyword Match */}
            <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 14 }}>
              <div style={{ fontSize: "0.75rem", color: "#6b7280", fontWeight: 600, textTransform: "uppercase", marginBottom: 4 }}>
                Keyword Match
              </div>
              <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "#111827" }}>
                {scanResult.breakdown.keyword_match}%
              </div>
              <div style={{ width: "100%", background: "#f3f4f6", height: 6, borderRadius: 3, marginTop: 8, overflow: "hidden" }}>
                <div style={{ width: `${scanResult.breakdown.keyword_match}%`, height: "100%", background: "#3b82f6" }} />
              </div>
            </div>

            {/* Core Skills Match */}
            <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 14 }}>
              <div style={{ fontSize: "0.75rem", color: "#6b7280", fontWeight: 600, textTransform: "uppercase", marginBottom: 4 }}>
                Required Skills
              </div>
              <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "#111827" }}>
                {scanResult.breakdown.skill_match}%
              </div>
              <div style={{ width: "100%", background: "#f3f4f6", height: 6, borderRadius: 3, marginTop: 8, overflow: "hidden" }}>
                <div style={{ width: `${scanResult.breakdown.skill_match}%`, height: "100%", background: "#10b981" }} />
              </div>
            </div>

            {/* Experience Match */}
            <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 14 }}>
              <div style={{ fontSize: "0.75rem", color: "#6b7280", fontWeight: 600, textTransform: "uppercase", marginBottom: 4 }}>
                Tenure Match
              </div>
              <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", flexWrap: "wrap", gap: 4 }}>
                <span style={{ fontSize: "1.4rem", fontWeight: 700, color: "#111827" }}>
                  {scanResult.breakdown.experience_match}%
                </span>
                {scanResult.breakdown.resume_years !== undefined && (
                  <span style={{ fontSize: "0.75rem", color: "#6b7280", fontWeight: 500 }}>
                    {scanResult.breakdown.resume_years > 0
                      ? (scanResult.breakdown.resume_years < 1
                          ? `${scanResult.breakdown.resume_months ?? Math.round(scanResult.breakdown.resume_years * 12)} mos`
                          : `${scanResult.breakdown.resume_years} yrs`)
                      : "0 yrs"}
                    {scanResult.breakdown.required_years ? ` / ${scanResult.breakdown.required_years} req` : ""}
                    {scanResult.tenure_report?.preferred_years ? ` (${scanResult.tenure_report.preferred_years} pref)` : ""}
                  </span>
                )}
              </div>
              <div style={{ width: "100%", background: "#f3f4f6", height: 6, borderRadius: 3, marginTop: 8, overflow: "hidden" }}>
                <div style={{ width: `${scanResult.breakdown.experience_match}%`, height: "100%", background: "#8b5cf6" }} />
              </div>
              {scanResult.breakdown.experience_duration_known === false ? (
                <div style={{ fontSize: "0.68rem", color: "#9ca3af", marginTop: 4, fontStyle: "italic" }}>
                  No dates detected in experience
                </div>
              ) : scanResult.tenure_report?.eligibility_status === "exceeds_maximum" ? (
                <div style={{ fontSize: "0.68rem", color: "#dc2626", marginTop: 4, fontWeight: 600 }}>
                  Exceeds position maximum cap ({scanResult.tenure_report.max_years} yrs)
                </div>
              ) : scanResult.tenure_report?.is_eligible ? (
                <div style={{ fontSize: "0.68rem", color: "#16a34a", marginTop: 4, fontWeight: 600 }}>
                  Meets hard eligibility requirements ✓
                </div>
              ) : scanResult.tenure_report?.eligibility_status === "below_minimum" || (scanResult.breakdown.required_years !== undefined && scanResult.breakdown.required_years > 0 && scanResult.breakdown.resume_years !== undefined && scanResult.breakdown.resume_years < scanResult.breakdown.required_years) ? (
                <div style={{ fontSize: "0.68rem", color: "#dc2626", marginTop: 4, fontWeight: 600 }}>
                  Below required experience ({scanResult.breakdown.resume_years} vs {scanResult.breakdown.required_years} yrs required) — 0% allocated
                </div>
              ) : null}
            </div>

            {/* Action Verbs Rate */}
            <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 14 }}>
              <div style={{ fontSize: "0.75rem", color: "#6b7280", fontWeight: 600, textTransform: "uppercase", marginBottom: 4 }}>
                Action Verb Rate
              </div>
              <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "#111827" }}>
                {scanResult.breakdown.action_verb_rate}%
              </div>
              <div style={{ width: "100%", background: "#f3f4f6", height: 6, borderRadius: 3, marginTop: 8, overflow: "hidden" }}>
                <div style={{ width: `${scanResult.breakdown.action_verb_rate}%`, height: "100%", background: "#f59e0b" }} />
              </div>
            </div>
          </div>

          {/* Keywords & Gap Inspection */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: 16,
              marginBottom: 20,
            }}
          >
            {/* Matched Keywords */}
            <div
              style={{
                border: "1px solid #e5e7eb",
                borderRadius: 8,
                padding: 16,
                background: "#f9fafb",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 12 }}>
                <CheckCircle2 size={16} color="#16a34a" />
                <span style={{ fontWeight: 700, fontSize: "0.875rem", color: "#166534" }}>
                  Matched Terms ({scanResult.matched_keywords.length})
                </span>
              </div>
              {scanResult.matched_keywords.length === 0 ? (
                <div style={{ fontSize: "0.825rem", color: "#9ca3af", fontStyle: "italic" }}>
                  No exact JD keywords detected in resume text.
                </div>
              ) : (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {scanResult.matched_keywords.map((kw, i) => (
                    <span
                      key={i}
                      style={{
                        background: "#dcfce7",
                        color: "#166534",
                        border: "1px solid #bbf7d0",
                        padding: "3px 8px",
                        borderRadius: 100,
                        fontSize: "0.75rem",
                        fontWeight: 600,
                      }}
                    >
                      ✓ {kw}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Missing Keywords */}
            <div
              style={{
                border: "1px solid #fed7aa",
                borderRadius: 8,
                padding: 16,
                background: "#fffaf5",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: 12,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <AlertCircle size={16} color="#ea580c" />
                  <span style={{ fontWeight: 700, fontSize: "0.875rem", color: "#9a3412" }}>
                    Missing Keywords ({scanResult.missing_keywords.length})
                  </span>
                </div>
                {scanResult.missing_keywords.length > 0 && (
                  <button
                    type="button"
                    onClick={handleCopyMissing}
                    style={{
                      background: "#ffffff",
                      border: "1px solid #fdba74",
                      borderRadius: 4,
                      padding: "2px 8px",
                      fontSize: "0.7rem",
                      fontWeight: 600,
                      color: "#c2410c",
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                      cursor: "pointer",
                    }}
                  >
                    {copiedMissing ? <Check size={12} /> : <Copy size={12} />}
                    <span>{copiedMissing ? "Copied!" : "Copy All"}</span>
                  </button>
                )}
              </div>
              {scanResult.missing_keywords.length === 0 ? (
                <div style={{ fontSize: "0.825rem", color: "#16a34a", fontWeight: 600 }}>
                  Excellent! Zero keyword deficits detected.
                </div>
              ) : (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {scanResult.missing_keywords.map((kw, i) => (
                    <span
                      key={i}
                      style={{
                        background: "#ffedd5",
                        color: "#9a3412",
                        border: "1px solid #fed7aa",
                        padding: "3px 8px",
                        borderRadius: 100,
                        fontSize: "0.75rem",
                        fontWeight: 600,
                      }}
                    >
                      + {kw}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Multi-Dimensional Fit & Semantic Evidence Breakdown */}
          {(scanResult.responsibilities_breakdown || scanResult.education_breakdown || scanResult.domain_breakdown || (scanResult.evidence_ledger && scanResult.evidence_ledger.length > 0)) && (
            <div
              style={{
                background: "#ffffff",
                border: "1px solid #e5e7eb",
                borderRadius: 8,
                padding: 16,
                marginBottom: 20,
              }}
            >
              <div style={{ fontWeight: 700, fontSize: "0.875rem", color: "#111827", marginBottom: 14, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span>Multi-Dimensional Job Fit & Semantic Evidence</span>
                {scanResult.dimension_scores && (
                  <span style={{ fontSize: "0.75rem", color: "#6b7280", fontWeight: 500 }}>
                    Skills: <strong style={{ color: "#111827" }}>{scanResult.dimension_scores.mandatory_skills}%</strong> · Duties: <strong style={{ color: "#111827" }}>{scanResult.dimension_scores.responsibilities}%</strong> · Education: <strong style={{ color: "#111827" }}>{scanResult.dimension_scores.education}%</strong>
                  </span>
                )}
              </div>

              {/* Responsibilities Coverage */}
              {scanResult.responsibilities_breakdown && scanResult.responsibilities_breakdown.covered && scanResult.responsibilities_breakdown.covered.length > 0 && (
                <div style={{ marginBottom: 14 }}>
                  <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "#374151", marginBottom: 6, display: "flex", justifyContent: "space-between" }}>
                    <span>Core Responsibilities Coverage</span>
                    <span style={{ color: "#16a34a" }}>{scanResult.responsibilities_breakdown.coverage_pct}% Covered</span>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    {scanResult.responsibilities_breakdown.covered.slice(0, 3).map((item, idx) => (
                      <div
                        key={idx}
                        style={{
                          background: "#f9fafb",
                          border: "1px solid #f3f4f6",
                          borderRadius: 6,
                          padding: "8px 10px",
                          fontSize: "0.75rem",
                        }}
                      >
                        <div style={{ color: "#111827", fontWeight: 600 }}>✓ {item.responsibility}</div>
                        {item.matched_bullet && (
                          <div style={{ color: "#6b7280", fontStyle: "italic", marginTop: 2, fontSize: "0.72rem" }}>
                            Evidence: "{item.matched_bullet}"
                          </div>
                        )}
                      </div>
                    ))}
                    {scanResult.responsibilities_breakdown.uncovered && scanResult.responsibilities_breakdown.uncovered.length > 0 && (
                      <div style={{ fontSize: "0.72rem", color: "#ea580c", marginTop: 4 }}>
                        Unaddressed: {scanResult.responsibilities_breakdown.uncovered.slice(0, 2).join("; ")}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Semantic Evidence Ledger */}
              {scanResult.evidence_ledger && scanResult.evidence_ledger.length > 0 && (
                <div>
                  <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "#374151", marginBottom: 6 }}>
                    Semantic Evidence Ledger ({scanResult.evidence_ledger.length} verified competencies)
                  </div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6, maxHeight: 130, overflowY: "auto", padding: 2 }}>
                    {scanResult.evidence_ledger.map((ev, idx) => (
                      <span
                        key={idx}
                        title={ev.evidence_snippet}
                        style={{
                          fontSize: "0.72rem",
                          fontWeight: 500,
                          padding: "3px 8px",
                          borderRadius: 6,
                          background: ev.evidence_level === "strong" ? "#dcfce7" : ev.evidence_level === "moderate" ? "#e0e7ff" : "#f3f4f6",
                          color: ev.evidence_level === "strong" ? "#166534" : ev.evidence_level === "moderate" ? "#3730a3" : "#374151",
                          border: `1px solid ${ev.evidence_level === "strong" ? "#bbf7d0" : ev.evidence_level === "moderate" ? "#c7d2fe" : "#e5e7eb"}`,
                        }}
                      >
                        <strong>{ev.canonical || ev.term}</strong> ({ev.source_section} · {ev.evidence_level})
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Formatting & Section Diagnostics */}
          <div
            style={{
              background: "#ffffff",
              border: "1px solid #e5e7eb",
              borderRadius: 8,
              padding: 16,
              marginBottom: 20,
            }}
          >
            <div style={{ fontWeight: 700, fontSize: "0.875rem", color: "#111827", marginBottom: 12 }}>
              ATS Parsing & Formatting Diagnostics
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14 }}>
              <div>
                <div style={{ fontSize: "0.75rem", color: "#6b7280" }}>Document Word Count</div>
                <div style={{ fontSize: "0.95rem", fontWeight: 600, color: "#111827", marginTop: 2 }}>
                  {scanResult.formatting_report.word_count || 0} words{" "}
                  <span style={{ fontSize: "0.75rem", color: scanResult.formatting_report.length_status === "Optimal" ? "#16a34a" : "#dc2626" }}>
                    ({scanResult.formatting_report.length_status})
                  </span>
                </div>
              </div>

              <div>
                <div style={{ fontSize: "0.75rem", color: "#6b7280" }}>Core ATS Sections</div>
                <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
                  {Object.entries(scanResult.section_validation).map(([section, present]) => (
                    <span
                      key={section}
                      style={{
                        fontSize: "0.75rem",
                        fontWeight: 600,
                        color: present ? "#166534" : "#991b1b",
                        background: present ? "#dcfce7" : "#fee2e2",
                        padding: "2px 6px",
                        borderRadius: 4,
                      }}
                    >
                      {section} {present ? "✓" : "✕"}
                    </span>
                  ))}
                </div>
              </div>

              <div>
                <div style={{ fontSize: "0.75rem", color: "#6b7280" }}>Formatting Quality Warnings</div>
                <div style={{ fontSize: "0.85rem", color: scanResult.formatting_report.bullet_warnings?.length ? "#dc2626" : "#16a34a", fontWeight: 500, marginTop: 2 }}>
                  {scanResult.formatting_report.bullet_warnings?.length ? (
                    <span>{scanResult.formatting_report.bullet_warnings.length} bullet punctuation alert(s)</span>
                  ) : (
                    <span>All bullets end with proper punctuation ✓</span>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Actionable Recommendations */}
          {scanResult.recommendations.length > 0 && (
            <div
              style={{
                border: "1px solid #e5e7eb",
                borderRadius: 8,
                padding: 16,
                background: "#f8fafc",
              }}
            >
              <div style={{ fontWeight: 700, fontSize: "0.875rem", color: "#1e293b", marginBottom: 10 }}>
                Recommended Action Plan
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                {scanResult.recommendations.map((rec, idx) => (
                  <div
                    key={idx}
                    style={{
                      background: "#ffffff",
                      border: "1px solid #e2e8f0",
                      borderRadius: 6,
                      padding: "10px 12px",
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "space-between",
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 600, fontSize: "0.8rem", color: "#0f172a", marginBottom: 2 }}>
                        {rec.title}
                      </div>
                      <div style={{ fontSize: "0.75rem", color: "#64748b", lineHeight: 1.4 }}>
                        {rec.description}
                      </div>
                    </div>
                    <div style={{ marginTop: 8, fontSize: "0.7rem", fontWeight: 700, color: "#2563eb" }}>
                      ➜ {rec.action}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
