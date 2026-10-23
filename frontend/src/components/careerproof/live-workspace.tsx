"use client";
import { useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  Code,
  Download,
  Eye,
  FileCode,
  FileText,
  RefreshCw,
  Shield,
  Sparkles,
  X,
  ShieldAlert,
  ShieldCheck,
  Mail,
  Rocket,
  Zap,
  Flame,
  BookmarkPlus,
  BarChart3,
} from "lucide-react";
import {
  api,
  downloadExport,
  ResumePageLimitError,
  getDefaultLatexTemplate,
  validateFiles,
  pasteResumeText,
  type ServerResume,
  type ServerSession,
  type ServerDraft,
  type ServerOptimization,
  type ServerEvidence,
  type ObjectionReport,
  type DefenseCard,
  type ProofSpec,
  type OutreachPack,
  type ClaimHeatmapReport,
} from "@/lib/careerproof/api";
import { Badge, Dialog } from "./ui";
import { HiringObjectionView } from "./objections";
import { InterviewDefenseView } from "./defense";
import { OutreachView } from "./outreach";
import { ClaimHeatmapView } from "./claim-heatmap";
import { ATSCheckerModal } from "./ats-checker";
export function LiveWorkspace() {
  const [resumes, setResumes] = useState<ServerResume[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [files, setFiles] = useState<File[]>([]);
  const [drafts, setDrafts] = useState<ServerDraft[]>([]);
  const [session, setSession] = useState<ServerSession | null>(null);
  const [preview, setPreview] = useState<ServerOptimization | null>(null);
  const [mode, setMode] = useState<"launch" | "advance">("advance");
  const [objectionReport, setObjectionReport] = useState<ObjectionReport | null>(null);
  const [showObjections, setShowObjections] = useState<boolean>(true);
  const [defenseCards, setDefenseCards] = useState<DefenseCard[]>([]);
  const [proofSpecs, setProofSpecs] = useState<ProofSpec[]>([]);
  const [showDefensePack, setShowDefensePack] = useState<boolean>(false);
  const [outreachPack, setOutreachPack] = useState<OutreachPack | null>(null);
  const [showOutreachPack, setShowOutreachPack] = useState<boolean>(false);
  const [claimHeatmap, setClaimHeatmap] = useState<ClaimHeatmapReport | null>(null);
  const [showHeatmap, setShowHeatmap] = useState<boolean>(false);
  const [showAtsScanner, setShowAtsScanner] = useState<boolean>(false);
  const [trackedAppStatus, setTrackedAppStatus] = useState<string | null>(null);
  const [trackingBusy, setTrackingBusy] = useState<boolean>(false);

  async function loadOptimization(optId: number) {
    await act(async () => {
      const opt = await api<ServerOptimization>(`/optimizations/${optId}`);
      setPreview(opt);
      if (opt.gap_report?.objection_analysis) {
        setObjectionReport(opt.gap_report.objection_analysis);
      } else {
        try {
          const rep = await api<ObjectionReport>(
            `/evidence-drafts/${optId}/objections`,
          );
          setObjectionReport(rep);
        } catch (e) {
          console.error(e);
        }
      }
      const activeMode =
        (opt.gap_report?.mode as "launch" | "advance") || mode;
      setMode(activeMode);
      try {
        const [cards, specs, outreach] = await Promise.all([
          api<DefenseCard[]>(
            `/evidence-drafts/${optId}/defense-cards?mode=${activeMode}`,
          ),
          api<ProofSpec[]>(
            `/evidence-drafts/${optId}/proof-specs?mode=${activeMode}`,
          ),
          api<OutreachPack>(
            `/evidence-drafts/${optId}/outreach?mode=${activeMode}`,
          ),
        ]);
        setDefenseCards(cards);
        setProofSpecs(specs);
        setOutreachPack(outreach);
      } catch (e) {
        console.error("Could not load defense cards / outreach", e);
      }
    });
  }
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");
  const [jd, setJd] = useState("");
  const [projectNotes, setProjectNotes] = useState("");
  const [answer, setAnswer] = useState("");
  const [depth, setDepth] = useState("unspecified");
  const [location, setLocation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [editing, setEditing] = useState<ServerEvidence | null>(null);
  const [correction, setCorrection] = useState("");
  const [correctionLocation, setCorrectionLocation] = useState("");
  const [showPaste, setShowPaste] = useState(false);
  const [pastedText, setPastedText] = useState("");
  const [pastedName, setPastedName] = useState("Pasted Resume.txt");
  const [exportPdfDraftId, setExportPdfDraftId] = useState<number | null>(null);
  const [templateChoice, setTemplateChoice] = useState<"default" | "custom">(
    "default",
  );
  const [customTemplate, setCustomTemplate] = useState<string>("");
  const [defaultTemplate, setDefaultTemplate] = useState<string>("");
  const [showDefaultPreview, setShowDefaultPreview] = useState<boolean>(false);
  const [isExportingPdf, setIsExportingPdf] = useState<boolean>(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [claimEdit, setClaimEdit] = useState<{
    id: number;
    text: string;
  } | null>(null);
  const [overflowPages, setOverflowPages] = useState<number | null>(null);

  async function openExportModal(draftId: number) {
    setExportPdfDraftId(draftId);
    setTemplateChoice("default");
    setExportError(null);
    setOverflowPages(null);
    setShowDefaultPreview(false);
    if (!defaultTemplate) {
      try {
        const tmpl = await getDefaultLatexTemplate();
        setDefaultTemplate(tmpl);
      } catch (e) {
        console.error("Could not load default template", e);
      }
    }
  }

  async function handleGeneratePdf(
    pagePolicy: "ask" | "keep" | "one_page" = "ask",
  ) {
    if (!exportPdfDraftId) return;
    setIsExportingPdf(true);
    setExportError(null);
    try {
      const result = await downloadExport(exportPdfDraftId, "pdf", {
        templateChoice,
        customTemplate:
          templateChoice === "custom" ? customTemplate : undefined,
        pagePolicy,
      });
      setNotice(
        `Downloaded ${result.pages}-page resume.${pagePolicy === "one_page" ? ` Created a concise copy; omitted ${result.omitted} lower-priority bullets. Your saved draft is unchanged.` : ""}`,
      );
      setExportPdfDraftId(null);
    } catch (err: unknown) {
      if (err instanceof ResumePageLimitError) {
        setOverflowPages(err.pages);
        return;
      }
      setExportError(
        err instanceof Error
          ? err.message
          : "Failed to compile and download PDF.",
      );
    } finally {
      setIsExportingPdf(false);
    }
  }

  async function handleDownloadLatex() {
    if (!exportPdfDraftId) return;
    setIsExportingPdf(true);
    setExportError(null);
    try {
      await downloadExport(exportPdfDraftId, "latex", {
        templateChoice,
        customTemplate:
          templateChoice === "custom" ? customTemplate : undefined,
      });
    } catch (err: unknown) {
      setExportError(
        err instanceof Error ? err.message : "Failed to download LaTeX source.",
      );
    } finally {
      setIsExportingPdf(false);
    }
  }

  async function refresh() {
    const [rs, ds] = await Promise.all([
      api<ServerResume[]>("/resumes"),
      api<ServerDraft[]>("/evidence-drafts"),
    ]);
    setResumes(rs);
    setDrafts(ds);
  }
  function sourceLabel(ref: string) {
    const id = /^resume:(\d+)/.exec(ref)?.[1];
    if (id)
      return (
        resumes.find((r) => r.id === Number(id))?.name || "Uploaded resume"
      );
    return ref.startsWith("discovery:")
      ? "Candidate-confirmed answer"
      : "Candidate evidence";
  }
  async function reviewClaim(
    bullet: ServerOptimization["optimized_content"][number],
    action: "accept" | "revert" | "edit" | "include" | "exclude",
    text = "",
  ) {
    if (!preview) return;
    const updated = await api<ServerOptimization>(
      `/evidence-drafts/${preview.id}/review`,
      "POST",
      {
        evidence_id: bullet.original_id,
        action,
        text,
        expected_text: bullet.optimized_bullet,
      },
    );
    setPreview(updated);
    if (updated.gap_report?.objection_analysis) {
      setObjectionReport(updated.gap_report.objection_analysis);
    }
    try {
      const [cards, specs, outreach] = await Promise.all([
        api<DefenseCard[]>(`/evidence-drafts/${preview.id}/defense-cards?mode=${mode}`),
        api<ProofSpec[]>(`/evidence-drafts/${preview.id}/proof-specs?mode=${mode}`),
        api<OutreachPack>(`/evidence-drafts/${preview.id}/outreach?mode=${mode}`),
      ]);
      setDefenseCards(cards);
      setProofSpecs(specs);
      setOutreachPack(outreach);
    } catch (e) {
      console.error(e);
    }
    setClaimEdit(null);
  }

  async function handleModeChange(newMode: "launch" | "advance") {
    setMode(newMode);
    if (!preview) return;
    try {
      const res = await api<{ mode: string; objection_analysis: ObjectionReport }>(
        `/evidence-drafts/${preview.id}/mode`,
        "POST",
        { mode: newMode }
      );
      if (res.objection_analysis) {
        setObjectionReport(res.objection_analysis);
      }
      const [cards, specs, outreach] = await Promise.all([
        api<DefenseCard[]>(`/evidence-drafts/${preview.id}/defense-cards?mode=${newMode}`),
        api<ProofSpec[]>(`/evidence-drafts/${preview.id}/proof-specs?mode=${newMode}`),
        api<OutreachPack>(`/evidence-drafts/${preview.id}/outreach?mode=${newMode}`),
      ]);
      setDefenseCards(cards);
      setProofSpecs(specs);
      setOutreachPack(outreach);
    } catch (err) {
      console.error("Failed to update candidate mode", err);
    }
  }

  async function handleTrackCurrentApplication(
    status: "Applied" | "OA" | "Interview" | "Offer" | "Rejected" = "Applied"
  ) {
    if (!preview) return;
    setTrackingBusy(true);
    try {
      await api("/tracker/track-draft", "POST", {
        optimization_id: preview.id,
        status,
        notes: `Tracked with ${mode === "launch" ? "CareerProof Launch" : "CareerProof Advance"} tailored claims.`,
      });
      setTrackedAppStatus(status);
      try {
        const heatmapReport = await api<ClaimHeatmapReport>("/analytics/claim-heatmap");
        setClaimHeatmap(heatmapReport);
      } catch (e) {
        console.error(e);
      }
    } catch (err) {
      console.error("Failed to track application", err);
    } finally {
      setTrackingBusy(false);
    }
  }

  async function handleToggleHeatmap() {
    if (!showHeatmap && !claimHeatmap) {
      try {
        const report = await api<ClaimHeatmapReport>("/analytics/claim-heatmap");
        setClaimHeatmap(report);
      } catch (err) {
        console.error("Failed to load claim heatmap", err);
      }
    }
    setShowHeatmap((prev) => !prev);
  }

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const [rs, ds] = await Promise.all([
          api<ServerResume[]>("/resumes"),
          api<ServerDraft[]>("/evidence-drafts"),
        ]);
        if (active) {
          setResumes(rs);
          setDrafts(ds);
        }
      } catch {
        if (active)
          setError(
            "Cannot reach the backend. Start the API, database, and worker, then retry. Please retry once it is available.",
          );
      }
    }
    void load();
    const timer = setInterval(load, 5000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);
  async function act(fn: () => Promise<unknown>) {
    setError("");
    setNotice("");
    setBusy(true);
    try {
      await fn();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Request failed. Please retry.",
      );
    } finally {
      setBusy(false);
    }
  }
  const q =
    session?.status === "discovering" ? session.questions.at(-1) : undefined;
  const ready = (r: ServerResume) =>
    !!r.bullets.length &&
    !["queued", "parsing", "failed"].includes(
      r.parsed_raw?.parsing_status || "",
    );
  async function submitAnswer(extra: object = {}) {
    if (!session || !q) return;
    setSession(
      await api<ServerSession>(`/discovery/${session.id}/answers`, "POST", {
        question_id: q.id,
        answer,
        depth,
        company: location,
        section: depth === "professional" ? "Experience" : "Projects",
        ...extra,
      }),
    );
    setAnswer("");
    setDepth("unspecified");
    setLocation("");
  }
  return (
    <div className="live-workspace">
      {busy && (
        <p className="notice" role="status">
          <RefreshCw size={16} />
          Waiting for the server… Your current evidence stays visible.
        </p>
      )}
      {error && (
        <div className="notice error" role="alert">
          <AlertTriangle size={17} />
          <span>{error}</span>
          <button className="inline-link" onClick={() => void act(refresh)}>
            Retry connection
          </button>
        </div>
      )}
      {notice && (
        <div className="notice success" role="status">
          <Check size={17} />
          {notice}
        </div>
      )}

      {/* Top Application Studio Action Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "1.25rem",
          background: "#ffffff",
          padding: "14px 20px",
          borderRadius: 10,
          border: "1px solid #e5e7eb",
          boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <strong style={{ fontSize: "1.1rem", color: "#111827" }}>CareerProof Studio</strong>
            <span
              style={{
                fontSize: "0.7rem",
                fontWeight: 700,
                color: "#1d4ed8",
                background: "#eff6ff",
                border: "1px solid #bfdbfe",
                padding: "2px 8px",
                borderRadius: 100,
              }}
            >
              ATS & Evidence Engine
            </span>
          </div>
          <p style={{ margin: "3px 0 0", fontSize: "0.825rem", color: "#6b7280" }}>
            Benchmark any existing resume, overcome recruiter objections, and tailor grounded application assets.
          </p>
        </div>
        <button
          type="button"
          className={`button secondary ${showAtsScanner ? "active" : ""}`}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 7,
            background: showAtsScanner ? "#eff6ff" : "#ffffff",
            borderColor: showAtsScanner ? "#2563eb" : "#d1d5db",
            color: showAtsScanner ? "#1d4ed8" : "#111827",
            fontWeight: 600,
            padding: "8px 16px",
            borderRadius: 7,
            cursor: "pointer",
            boxShadow: showAtsScanner ? "0 0 0 2px rgba(37,99,235,0.2)" : "0 1px 2px rgba(0,0,0,0.05)",
          }}
          onClick={() => setShowAtsScanner(!showAtsScanner)}
        >
          <BarChart3 size={16} color="#2563eb" />
          <span>{showAtsScanner ? "Close ATS Scanner" : "📊 Check Existing ATS Score"}</span>
        </button>
      </div>

      {showAtsScanner && (
        <ATSCheckerModal
          initialResumeId={selected[0]}
          onSelectDraft={(optId) => {
            void loadOptimization(optId);
            setShowAtsScanner(false);
          }}
          onApplyJobToWorkspace={(comp, rle, jdText) => {
            setCompany(comp);
            setRole(rle);
            setJd(jdText);
            setShowAtsScanner(false);
            setNotice("Applied job details to workspace form.");
          }}
        />
      )}

      {!session ? (
        <section className="main-surface">
          <div className="surface-title">
            <h2>Add resumes</h2>
          </div>
          <label className="field-label">
            Choose up to three resumes
            <input
              type="file"
              multiple
              accept=".pdf,.docx,.txt"
              disabled={busy}
              onChange={(e) => {
                const incoming = Array.from(e.target.files || []);
                const issue = validateFiles(incoming, files.length);
                if (issue) setError(issue);
                else setFiles((prev) => [...prev, ...incoming]);
                e.target.value = "";
              }}
            />
          </label>
          {files.map((f, i) => (
            <div className="file-row" key={`${f.name}-${i}`}>
              <FileText size={18} />
              <span>{f.name}</span>
              <Badge>In memory</Badge>
              <button
                className="icon-button"
                aria-label={`Remove ${f.name}`}
                onClick={() => setFiles(files.filter((_, j) => i !== j))}
              >
                <X size={16} />
              </button>
            </div>
          ))}
          <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
            <button
              className="button primary"
              disabled={!files.length || busy}
              onClick={() =>
                void act(async () => {
                  const form = new FormData();
                  files.forEach((f) => form.append("files", f));
                  const uploaded = await api<ServerResume[]>(
                    "/resumes/upload-batch",
                    "POST",
                    form,
                  );
                  setSelected(uploaded.map((r) => r.id));
                  setSession(null);
                  setPreview(null);
                  setFiles([]);
                  await refresh();
                  setNotice(
                    "Files uploaded. Text extraction and AI parsing started automatically.",
                  );
                })
              }
            >
              Add resumes
              <ArrowRight size={15} />
            </button>
            <button
              type="button"
              className="button secondary"
              onClick={() => setShowPaste(!showPaste)}
            >
              {showPaste ? "Cancel paste" : "Or paste text directly"}
            </button>
          </div>

          {showPaste && (
            <div
              style={{
                marginTop: "1rem",
                padding: "1rem",
                border: "1px solid var(--border)",
                borderRadius: "8px",
              }}
            >
              <h4>Paste Resume Text</h4>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "var(--muted)",
                  marginBottom: "0.5rem",
                }}
              >
                Ideal for scanned documents, OCR fallbacks, or plain text
                resumes.
              </p>
              <input
                style={{ width: "100%", marginBottom: "0.5rem" }}
                value={pastedName}
                placeholder="Resume name (e.g. My Resume.txt)"
                onChange={(e) => setPastedName(e.target.value)}
              />
              <textarea
                style={{
                  width: "100%",
                  height: "140px",
                  fontFamily: "monospace",
                  fontSize: "0.85rem",
                }}
                value={pastedText}
                placeholder="Paste your resume text here..."
                onChange={(e) => setPastedText(e.target.value)}
              />
              <button
                type="button"
                className="button primary"
                disabled={!pastedText.trim() || busy}
                style={{ marginTop: "0.5rem" }}
                onClick={() =>
                  void act(async () => {
                    const r = await pasteResumeText(pastedText, pastedName);
                    setPastedText("");
                    setShowPaste(false);
                    setSelected([r.id]);
                    setSession(null);
                    setPreview(null);
                    await refresh();
                    setNotice(
                      "Pasted resume queued for extraction and parsing.",
                    );
                  })
                }
              >
                Ingest Pasted Text
              </button>
            </div>
          )}

          <fieldset
            className="server-source-list"
            style={{ marginTop: "1.5rem" }}
          >
            <legend>Choose existing server sources (1–3)</legend>
            {resumes.map((r) => {
              const isOcrNeeded = r.parsed_raw?.parsing_status === "needs_ocr";
              const isLocalReview =
                r.parsed_raw?.needs_review && !r.parsed_raw?.ai_enhanced;
              const isAi = r.parsed_raw?.ai_enhanced;
              return (
                <label key={r.id}>
                  <input
                    type="checkbox"
                    checked={selected.includes(r.id)}
                    disabled={
                      !ready(r) ||
                      busy ||
                      (!selected.includes(r.id) && selected.length >= 3)
                    }
                    onChange={(e) =>
                      setSelected(
                        e.target.checked
                          ? [...selected, r.id]
                          : selected.filter((id) => id !== r.id),
                      )
                    }
                  />
                  <span>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "0.5rem",
                      }}
                    >
                      <strong>{r.name}</strong>
                      {isOcrNeeded && <Badge tone="amber">Needs OCR</Badge>}
                      {isLocalReview && (
                        <Badge tone="neutral">Local Draft</Badge>
                      )}
                      {isAi && <Badge tone="teal">AI Enhanced</Badge>}
                    </div>
                    <small>
                      {ready(r)
                        ? isAi
                          ? "AI enhanced · ready to review"
                          : "Local extraction (needs review) · ready"
                        : isOcrNeeded
                          ? "This document needs OCR. Paste text directly to proceed."
                          : r.parsed_raw?.error ||
                            r.parsed_raw?.parsing_status ||
                            "Waiting for parsing"}
                    </small>
                    {r.parsed_raw?.raw_source_text && (
                      <details>
                        <summary>Read extracted text</summary>
                        <pre>{r.parsed_raw.raw_source_text}</pre>
                      </details>
                    )}
                  </span>
                </label>
              );
            })}
          </fieldset>
          <details style={{ margin: "1.5rem 0" }}>
            <summary>Add project notes (Optional)</summary>
            <label className="field-label">
              Include the project name, what you personally did, and any results
              missing from your resumes.
              <textarea
                rows={4}
                maxLength={6000}
                value={projectNotes}
                onChange={(event) => setProjectNotes(event.target.value)}
                placeholder="Add relevant project details here…"
              />
            </label>
          </details>
          <div className="form-grid">
            <label>
              Company
              <input
                value={company}
                onChange={(e) => setCompany(e.target.value)}
              />
            </label>
            <label>
              Role
              <input value={role} onChange={(e) => setRole(e.target.value)} />
            </label>
          </div>
          <label className="field-label">
            Job description
            <textarea
              rows={7}
              value={jd}
              onChange={(e) => setJd(e.target.value)}
            />
          </label>
          <button
            className="button primary"
            disabled={
              busy ||
              !selected.length ||
              selected.some(
                (id) => !resumes.find((r) => r.id === id && ready(r)),
              ) ||
              !company.trim() ||
              !role.trim() ||
              !jd.trim()
            }
            onClick={() =>
              void act(async () => {
                const job = await api<{ id: number }>("/jobs", "POST", {
                  company,
                  role,
                  raw_text: jd,
                });
                setSession(
                  await api<ServerSession>("/discovery", "POST", {
                    resume_ids: selected,
                    job_id: job.id,
                    project_notes: projectNotes,
                  }),
                );
              })
            }
          >
            Continue
            <ArrowRight size={15} />
          </button>
        </section>
      ) : (
        <>
          <div className="subheading">
            <h2>Discovery session #{session.id}</h2>
            <button
              className="button secondary"
              disabled={busy}
              onClick={() => {
                setSession(null);
                setPreview(null);
              }}
            >
              Start another application
            </button>
          </div>
          {session.profile && (
            <section className="main-surface">
              <div className="subheading">
                <h2>Combined candidate profile</h2>
                <Badge>{session.resume_ids.length} source resumes</Badge>
              </div>
              <p>{session.profile.name || "Candidate"}</p>
              <p className="muted">{session.profile.skills.join(" · ")}</p>
              {session.profile.education.map((e, i) => (
                <p key={i}>
                  {e.school} · {e.degree}
                </p>
              ))}
              <details>
                <summary>Supporting profile sources</summary>
                {session.resume_ids.map((id) => (
                  <div key={id}>
                    <strong>
                      {resumes.find((r) => r.id === id)?.name ||
                        "Uploaded resume"}
                    </strong>
                    <p style={{ whiteSpace: "pre-wrap" }}>
                      {resumes.find((r) => r.id === id)?.parsed_raw
                        ?.raw_source_text ||
                        "Source text is saved with this resume."}
                    </p>
                  </div>
                ))}
              </details>
              {session.conflicts?.map((conflict) => (
                <article className="server-evidence" key={conflict.id}>
                  <h3>Confirm conflicting details</h3>
                  <p>{conflict.field}</p>
                  <p className="muted">
                    Choose the supported version before tailoring. To correct
                    both, edit the underlying evidence below.
                  </p>
                  {conflict.options.map((option, i) => (
                    <div key={i}>
                      <p>{option.label || String(option.value)}</p>
                      <p className="muted small">
                        Sources: {option.sources.map(sourceLabel).join(", ")}
                      </p>
                      <button
                        className="button secondary"
                        disabled={busy}
                        onClick={() =>
                          void act(async () =>
                            setSession(
                              await api<ServerSession>(
                                `/discovery/${session.id}/resolve`,
                                "POST",
                                {
                                  conflict_id: conflict.id,
                                  choice: option.value,
                                },
                              ),
                            ),
                          )
                        }
                      >
                        Confirm this version
                      </button>
                    </div>
                  ))}
                </article>
              ))}
            </section>
          )}
          {q && session.status === "discovering" && (
            <section className="main-surface live-question">
              <Badge>{q.id} of at most 4</Badge>
              <h2>{q.prompt}</h2>
              <div className="question-benefit">
                <strong>How this helps</strong>
                <p>{q.benefit}</p>
              </div>
              {q.kind === "interpretation" ? (
                <div className="row">
                  <button
                    className="button primary"
                    disabled={busy}
                    onClick={() =>
                      void act(() => submitAnswer({ confirm: true }))
                    }
                  >
                    Yes, that describes my work
                  </button>
                  <button
                    className="button secondary"
                    disabled={busy}
                    onClick={() =>
                      void act(() => submitAnswer({ confirm: false }))
                    }
                  >
                    No, leave that term out
                  </button>
                </div>
              ) : (
                <>
                  <label>
                    Your answer
                    <textarea
                      rows={4}
                      value={answer}
                      onChange={(e) => setAnswer(e.target.value)}
                    />
                  </label>
                  {["gap", "ownership"].includes(q.kind) && (
                    <label>
                      Experience level
                      <select
                        value={depth}
                        onChange={(e) => setDepth(e.target.value)}
                      >
                        <option value="unspecified">
                          Choose experience level…
                        </option>
                        <option value="professional">Professional work</option>
                        <option value="personal_project">
                          Personal project
                        </option>
                        <option value="tutorial">Guided tutorial</option>
                        <option value="familiarity">
                          Studied / familiarity
                        </option>
                        <option value="team_only">
                          Team used it; I did not
                        </option>
                      </select>
                    </label>
                  )}
                  {q.kind === "gap" && (
                    <label>
                      Project or employer
                      <input
                        value={location}
                        onChange={(e) => setLocation(e.target.value)}
                      />
                    </label>
                  )}
                  <button
                    className="button primary"
                    disabled={
                      busy ||
                      !answer.trim() ||
                      (["gap", "ownership"].includes(q.kind) &&
                        depth === "unspecified") ||
                      (q.kind === "gap" && !location.trim())
                    }
                    onClick={() => void act(() => submitAnswer())}
                  >
                    Save answer
                    <ArrowRight size={15} />
                  </button>
                </>
              )}
              <button
                className="button ghost"
                disabled={busy}
                onClick={() => void act(() => submitAnswer({ skip: true }))}
              >
                Skip / I don’t remember
              </button>
            </section>
          )}
          <section className="main-surface">
            <div className="subheading">
              <h2>Candidate-supplied evidence</h2>
              <Badge>{session.evidence.length} achievements</Badge>
            </div>
            {session.evidence.map((e) => (
              <article className="server-evidence" key={e.id}>
                <span className="eyebrow">
                  {e.data.company} · {e.data.section} · Revision {e.revision}
                </span>
                <p>{e.data.content}</p>
                {e.data.discovery_notes && (
                  <p className="muted">
                    Your context: {e.data.discovery_notes}
                  </p>
                )}
                {e.data.ownership && (
                  <p className="muted">Your contribution: {e.data.ownership}</p>
                )}
                <button
                  className="inline-link"
                  disabled={busy}
                  onClick={() => {
                    setEditing(e);
                    setCorrection(e.data.content);
                    setCorrectionLocation(e.data.company);
                  }}
                >
                  Correct evidence or a previous answer
                  <ArrowUpRightIcon />
                </button>
              </article>
            ))}
            {session.status === "ready" && (
              <button
                className="button primary"
                disabled={busy}
                onClick={() =>
                  void act(async () => {
                    const draft = await api<{ id: number }>(
                      `/discovery/${session.id}/optimize`,
                      "POST",
                    );
                    await refresh();
                    setNotice(
                      `Draft #${draft.id} queued. It will appear as complete when the worker finishes.`,
                    );
                  })
                }
              >
                Create tailored draft
                <ArrowRight size={15} />
              </button>
            )}
          </section>
        </>
      )}
      <section className="main-surface">
        <div className="subheading" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2>Saved server versions</h2>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <button
              type="button"
              className={`button secondary small ${showAtsScanner ? "active" : ""}`}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                background: showAtsScanner ? "#eff6ff" : "#ffffff",
                borderColor: showAtsScanner ? "#2563eb" : "#d1d5db",
                color: showAtsScanner ? "#1d4ed8" : "var(--ink)",
                fontWeight: 600,
              }}
              onClick={() => setShowAtsScanner(!showAtsScanner)}
            >
              <BarChart3 size={14} color="#2563eb" />
              {showAtsScanner ? "Hide ATS Scanner" : "Check ATS Score"}
            </button>
            <button
              type="button"
              className={`button secondary small ${showHeatmap ? "active" : ""}`}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                background: showHeatmap ? "#ecfdf5" : "#ffffff",
                borderColor: showHeatmap ? "#10b981" : "#d1d5db",
                color: showHeatmap ? "#065f46" : "var(--ink)",
                fontWeight: 600,
              }}
              onClick={() => void handleToggleHeatmap()}
            >
              <Flame size={14} color="#059669" />
              {showHeatmap ? "Hide Claim Heatmap" : "Claim Heatmap & Win Rates"}
            </button>
            <button
              className="icon-button"
              aria-label="Refresh saved drafts"
              disabled={busy}
              onClick={() => void act(refresh)}
            >
              <RefreshCw size={16} />
            </button>
          </div>
        </div>
        {showHeatmap && claimHeatmap && (
          <div style={{ marginBottom: 18 }}>
            <ClaimHeatmapView report={claimHeatmap} />
          </div>
        )}
        {!drafts.length && (
          <p className="muted">Your first completed draft will appear here.</p>
        )}
        {drafts.map((d) => (
          <article className="server-draft" key={d.id}>
            <div className="row between">
              <div>
                <strong>Resume #{d.id}</strong>
                {(d.job_company || d.job_role) && (
                  <span className="muted small" style={{ marginLeft: 8 }}>
                    Target: {d.job_company || "JD"}{d.job_role ? ` · ${d.job_role}` : ""}
                  </span>
                )}
              </div>
              <Badge tone={d.status === "complete" ? "teal" : "neutral"}>
                {d.submitted ? "Submitted snapshot" : d.status}
              </Badge>
            </div>
            {d.status === "complete" && d.ats_score !== undefined && (
              <div className="ats-score-pill-card">
                <div className="ats-score-main">
                  <span className="ats-score-number">{Math.round(d.ats_score)}%</span>
                  <span className="ats-score-title">
                    ATS Match vs {d.job_company || "Uploaded JD"}
                  </span>
                </div>
                <div className="ats-mini-metrics">
                  {d.keyword_match !== undefined && (
                    <span className="ats-chip">Keywords {Math.round(d.keyword_match)}%</span>
                  )}
                  {d.skill_match !== undefined && (
                    <span className="ats-chip">Skills {Math.round(d.skill_match)}%</span>
                  )}
                  {d.experience_match !== undefined && (
                    <span className="ats-chip">Exp {Math.round(d.experience_match)}%</span>
                  )}
                </div>
              </div>
            )}
            {d.error && <p className="notice error">{d.error}</p>}
            {!!d.stale_evidence_ids.length && (
              <p className="notice warning">
                {d.stale_evidence_ids.length} evidence record(s) changed. This
                copy stays unchanged.
              </p>
            )}
            <div className="review-actions">
              <button
                className="button secondary"
                disabled={busy}
                onClick={() =>
                  void act(async () =>
                    setSession(
                      await api<ServerSession>(`/discovery/${d.session_id}`),
                    ),
                  )
                }
              >
                Resume session
              </button>
              {d.status === "complete" && (
                <>
                  <button
                    className="button secondary"
                    disabled={busy}
                    onClick={() => void loadOptimization(d.id)}
                  >
                    Review claims
                  </button>
                  {(["pdf", "docx"] as const).map((format) => (
                    <button
                      key={format}
                      className="button secondary"
                      disabled={busy}
                      onClick={() => {
                        if (format === "pdf") {
                          void openExportModal(d.id);
                        } else {
                          void act(() => downloadExport(d.id, format));
                        }
                      }}
                    >
                      <Download size={13} />
                      {format.toUpperCase()}
                    </button>
                  ))}
                  {!d.submitted && !d.stale_evidence_ids.length && (
                    <button
                      className="button primary"
                      disabled={busy}
                      onClick={() =>
                        void act(async () => {
                          await api(`/evidence-drafts/${d.id}/submit`, "POST");
                          await refresh();
                        })
                      }
                    >
                      Mark submitted
                    </button>
                  )}
                </>
              )}
              {(!!d.stale_evidence_ids.length || d.status === "failed") && (
                <button
                  className="button primary"
                  disabled={busy}
                  onClick={() =>
                    void act(async () => {
                      await api(`/evidence-drafts/${d.id}/revise`, "POST");
                      await refresh();
                    })
                  }
                >
                  Create corrected version
                </button>
              )}
            </div>
          </article>
        ))}
      </section>
      {preview && (
        <Dialog
          title={`Review resume #${preview.id}`}
          wide
          onClose={() => setPreview(null)}
        >
          {error && (
            <p role="alert" className="notice error">
              {error}
            </p>
          )}
          <p className="muted">
            Review the proposed wording against its own sources. Accept, edit,
            or revert each included claim before exporting. New facts belong in
            the evidence record, not an unsupported wording edit.
          </p>
          {/* Dual-Mode Candidate Perspective Switcher */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "12px 16px",
              background: mode === "launch" ? "#fffdf5" : "#f5f9fc",
              border: `1.5px solid ${mode === "launch" ? "#fcd34d" : "#bfdbfe"}`,
              borderRadius: 8,
              margin: "14px 0",
              flexWrap: "wrap",
              gap: 12,
            }}
          >
            <div>
              <span
                className="small-label"
                style={{ color: mode === "launch" ? "#92400e" : "#1e40af" }}
              >
                CANDIDATE PERSPECTIVE MODE
              </span>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  marginTop: 2,
                }}
              >
                <strong style={{ fontSize: 13, color: "var(--ink)" }}>
                  {mode === "launch"
                    ? "CareerProof Launch (0–2 YOE Mode)"
                    : "CareerProof Advance (3+ YOE Mode)"}
                </strong>
                <span className="muted small">
                  {mode === "launch"
                    ? "Tuned for Freshers & Early-Career: Proves genuine project proof, testing & benchmarks over tutorial skepticism."
                    : "Tuned for Experienced & Switchers: Proves architectural trade-offs, ownership & business impact over Jira execution."}
                </span>
              </div>
            </div>

            <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
              <button
                type="button"
                className={`persona-btn ${mode === "launch" ? "active" : ""}`}
                style={{
                  padding: "6px 12px",
                  fontSize: 12,
                  background: mode === "launch" ? "#fef3c7" : "#ffffff",
                  borderColor: mode === "launch" ? "#d97706" : "#e2e8f0",
                  color: mode === "launch" ? "#92400e" : "var(--ink)",
                  fontWeight: mode === "launch" ? 700 : 500,
                }}
                onClick={() => void handleModeChange("launch")}
              >
                <Rocket
                  size={13}
                  style={{
                    marginRight: 4,
                    display: "inline-block",
                    verticalAlign: "middle",
                  }}
                />
                CareerProof Launch
              </button>
              <button
                type="button"
                className={`persona-btn ${mode === "advance" ? "active" : ""}`}
                style={{
                  padding: "6px 12px",
                  fontSize: 12,
                  background: mode === "advance" ? "#edf3fa" : "#ffffff",
                  borderColor: mode === "advance" ? "#1e527d" : "#e2e8f0",
                  color: mode === "advance" ? "#1e527d" : "var(--ink)",
                  fontWeight: mode === "advance" ? 700 : 500,
                }}
                onClick={() => void handleModeChange("advance")}
              >
                <Zap
                  size={13}
                  style={{
                    marginRight: 4,
                    display: "inline-block",
                    verticalAlign: "middle",
                  }}
                />
                CareerProof Advance
              </button>
            </div>
          </div>
          {/* 1-Click Application Tracker Bar */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "10px 14px",
              background: "#ffffff",
              border: "1px solid #d4e4db",
              borderRadius: 8,
              margin: "10px 0 14px 0",
              flexWrap: "wrap",
              gap: 8,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <BookmarkPlus size={16} color="var(--teal)" />
              <span style={{ fontSize: 12.5, fontWeight: 650, color: "var(--ink)" }}>
                Application Tracker Loop:
              </span>
              <span className="muted small">
                Log application status to track claim win rates &amp; callbacks
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              {(["Applied", "OA", "Interview", "Offer", "Rejected"] as const).map((st) => (
                <button
                  key={st}
                  type="button"
                  disabled={trackingBusy}
                  className={`button small ${trackedAppStatus === st ? "primary" : "secondary"}`}
                  style={{ padding: "4px 9px", fontSize: 11 }}
                  onClick={() => void handleTrackCurrentApplication(st)}
                >
                  {trackedAppStatus === st ? `✓ ${st}` : st}
                </button>
              ))}
            </div>
          </div>
          {preview.ats_score !== undefined && (
            <div className="ats-match-panel">
              <div className="ats-match-header">
                <div className="ats-gauge">
                  <div className="ats-gauge-circle">
                    <span className="ats-gauge-val">
                      {Math.round(preview.ats_score)}%
                    </span>
                  </div>
                  <div>
                    <h3 className="ats-match-heading">
                      Estimated ATS Match vs{" "}
                      {preview.job?.company ||
                        preview.job_company ||
                        "Uploaded Job Description"}
                    </h3>
                    <p className="muted small">
                      {preview.job?.role || preview.job_role
                        ? `Target Role: ${preview.job?.role || preview.job_role} · `
                        : ""}
                      {preview.gap_report?.score_label ||
                        "Deterministic keyword & skill match against uploaded JD"}
                    </p>
                  </div>
                </div>
              </div>
              <div className="ats-match-grid">
                <div className="ats-stat-card">
                  <span className="ats-stat-label">Keyword Match</span>
                  <strong className="ats-stat-value">
                    {Math.round(preview.keyword_match ?? 0)}%
                  </strong>
                  <div className="ats-bar">
                    <div
                      className="ats-bar-fill"
                      style={{
                        width: `${Math.min(preview.keyword_match ?? 0, 100)}%`,
                      }}
                    />
                  </div>
                </div>
                <div className="ats-stat-card">
                  <span className="ats-stat-label">Skill Match</span>
                  <strong className="ats-stat-value">
                    {Math.round(preview.skill_match ?? 0)}%
                  </strong>
                  <div className="ats-bar">
                    <div
                      className="ats-bar-fill"
                      style={{
                        width: `${Math.min(preview.skill_match ?? 0, 100)}%`,
                      }}
                    />
                  </div>
                </div>
                <div className="ats-stat-card">
                  <span className="ats-stat-label">Experience Match</span>
                  <strong className="ats-stat-value">
                    {Math.round(preview.experience_match ?? 0)}%
                  </strong>
                  <div className="ats-bar">
                    <div
                      className="ats-bar-fill"
                      style={{
                        width: `${Math.min(preview.experience_match ?? 0, 100)}%`,
                      }}
                    />
                  </div>
                </div>
              </div>
              {preview.gap_report?.matched_keywords &&
                preview.gap_report.matched_keywords.length > 0 && (
                  <div
                    className="ats-missing-section"
                    style={{ borderTop: "none", paddingBottom: 10 }}
                  >
                    <span
                      className="small-label"
                      style={{ color: "var(--teal)" }}
                    >
                      MATCHED JD KEYWORDS &amp; SKILLS
                    </span>
                    <div className="ats-keyword-chips">
                      {preview.gap_report.matched_keywords
                        .slice(0, 12)
                        .map((kw, idx) => (
                          <span
                            className="ats-chip"
                            key={idx}
                            style={{
                              background: "#edf6f1",
                              borderColor: "#c2e0cf",
                              color: "var(--teal)",
                            }}
                          >
                            ✓ {kw}
                          </span>
                        ))}
                    </div>
                  </div>
                )}
              {preview.gap_report?.missing_keywords &&
                preview.gap_report.missing_keywords.length > 0 && (
                  <div className="ats-missing-section">
                    <span className="small-label">
                      TOP MISSING KEYWORDS FROM UPLOADED JD
                    </span>
                    <div className="ats-keyword-chips">
                      {preview.gap_report.missing_keywords
                        .slice(0, 10)
                        .map((kw, idx) => (
                          <span className="ats-keyword-badge" key={idx}>
                            + {kw}
                          </span>
                        ))}
                    </div>
                  </div>
                )}
            </div>
          )}
          {objectionReport && (
            <div style={{ margin: "14px 0" }}>
              <button
                type="button"
                className="button secondary"
                style={{
                  width: "100%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "10px 16px",
                  background: showObjections ? "#edf5ef" : "#f8faf8",
                  borderColor: showObjections ? "var(--teal)" : "#d0ded5",
                }}
                onClick={() => setShowObjections((prev) => !prev)}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <ShieldAlert size={16} color="var(--teal)" />
                  <span style={{ fontWeight: 650, color: "var(--ink)" }}>
                    Hiring Objection Engine Analysis
                  </span>
                  <Badge
                    tone={
                      objectionReport.hard_constraints.length > 0
                        ? "amber"
                        : "teal"
                    }
                  >
                    {objectionReport.objections.length} Hypotheses
                    {objectionReport.hard_constraints.length > 0
                      ? ` · ${objectionReport.hard_constraints.length} Constraint`
                      : ""}
                  </Badge>
                </div>
                <span className="small-label" style={{ color: "var(--teal)" }}>
                  {showObjections ? "Hide Panel" : "View Objections"}
                </span>
              </button>
              {showObjections && (
                <HiringObjectionView report={objectionReport} />
              )}
            </div>
          )}
          {defenseCards.length > 0 && (
            <div style={{ margin: "14px 0" }}>
              <button
                type="button"
                className="button secondary"
                style={{
                  width: "100%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "10px 16px",
                  background: showDefensePack ? "#edf3fa" : "#f8fafc",
                  borderColor: showDefensePack ? "#1e527d" : "#cddde8",
                }}
                onClick={() => setShowDefensePack((prev) => !prev)}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <ShieldCheck size={16} color="#1e527d" />
                  <span style={{ fontWeight: 650, color: "var(--ink)" }}>
                    Interview Defense Pack &amp; Minimum Proof
                  </span>
                  <Badge tone="teal">
                    {defenseCards.length} Cards
                    {proofSpecs.length > 0
                      ? ` · ${proofSpecs.length} Proof Specs`
                      : ""}
                  </Badge>
                </div>
                <span className="small-label" style={{ color: "#1e527d" }}>
                  {showDefensePack ? "Hide Defense Pack" : "Open Interview Pack"}
                </span>
              </button>
              {showDefensePack && (
                <InterviewDefenseView
                  draftId={preview.id}
                  cards={defenseCards}
                  proofSpecs={proofSpecs}
                />
              )}
            </div>
          )}
          {outreachPack && (
            <div style={{ margin: "14px 0" }}>
              <button
                type="button"
                className="button secondary"
                style={{
                  width: "100%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "10px 16px",
                  background: showOutreachPack ? "#fef8ee" : "#fdfbf7",
                  borderColor: showOutreachPack ? "#d97706" : "#f0d9b5",
                }}
                onClick={() => setShowOutreachPack((prev) => !prev)}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Mail size={16} color="#d97706" />
                  <span style={{ fontWeight: 650, color: "var(--ink)" }}>
                    Evidence-Grounded Outreach &amp; Application Pack
                  </span>
                  <Badge tone={mode === "launch" ? "amber" : "teal"}>
                    Cold InMail · Cover Letter · {outreachPack.screening_answers?.length || 0} Screening Answers
                  </Badge>
                </div>
                <span className="small-label" style={{ color: "#d97706" }}>
                  {showOutreachPack ? "Hide Outreach Pack" : "Open Outreach Pack"}
                </span>
              </button>
              {showOutreachPack && (
                <OutreachView pack={outreachPack} />
              )}
            </div>
          )}
          {preview.optimized_content.map((b, i) => (
            <div className="server-evidence" key={i}>
              <span className="eyebrow">
                {b.company} · {b.section}
              </span>
              <div className="wording original">
                <span className="small-label">ORIGINAL</span>
                <p>{b.original_bullet}</p>
              </div>
              <div className="wording proposed">
                <span className="small-label">RESULT</span>
                <p>{b.optimized_bullet}</p>
              </div>
              <p className="muted small">{b.reason_for_change}</p>
              <p className="muted small">{b.selection_reason}</p>
              <Badge tone={b.review_state === "pending" ? "amber" : "teal"}>
                {b.included === false
                  ? "Not selected"
                  : b.review_state || "Saved"}
              </Badge>
              <details>
                <summary>Supporting evidence</summary>
                <p style={{ whiteSpace: "pre-wrap" }}>
                  {b.evidence_context || b.original_bullet}
                </p>
                <p className="muted small">
                  {b.source_refs?.map(sourceLabel).join(" · ")}
                </p>
              </details>
              {!drafts.find((d) => d.id === preview.id)?.submitted && (
                <div className="review-actions">
                  <button
                    className="button secondary"
                    disabled={busy}
                    onClick={() => void act(() => reviewClaim(b, "accept"))}
                  >
                    Accept
                  </button>
                  <button
                    className="button secondary"
                    disabled={busy}
                    onClick={() => void act(() => reviewClaim(b, "revert"))}
                  >
                    Revert to source
                  </button>
                  <button
                    className="button secondary"
                    disabled={busy}
                    onClick={() =>
                      setClaimEdit({
                        id: b.original_id,
                        text: b.optimized_bullet,
                      })
                    }
                  >
                    Edit wording
                  </button>
                  <button
                    className="button secondary"
                    disabled={busy}
                    onClick={() =>
                      void act(() =>
                        reviewClaim(
                          b,
                          b.included === false ? "include" : "exclude",
                        ),
                      )
                    }
                  >
                    {b.included === false ? "Include" : "Omit"}
                  </button>
                </div>
              )}
              {claimEdit?.id === b.original_id && (
                <div>
                  <label>
                    Proposed wording
                    <textarea
                      aria-label="Proposed wording"
                      rows={4}
                      value={claimEdit.text}
                      onChange={(e) =>
                        setClaimEdit({ ...claimEdit, text: e.target.value })
                      }
                    />
                  </label>
                  <button
                    className="button primary"
                    disabled={busy || !claimEdit.text.trim()}
                    onClick={() =>
                      void act(() => reviewClaim(b, "edit", claimEdit.text))
                    }
                  >
                    Verify and save edit
                  </button>
                  <button
                    className="button secondary"
                    onClick={() => setClaimEdit(null)}
                  >
                    Cancel edit
                  </button>
                </div>
              )}
            </div>
          ))}
        </Dialog>
      )}
      {editing && (
        <Dialog
          title="Correct the source evidence"
          onClose={() => setEditing(null)}
        >
          <p className="muted">
            This replaces the claim and its earlier context. Affected drafts
            will be flagged; submitted copies stay unchanged.
          </p>
          <label>
            Corrected achievement / personal contribution
            <textarea
              rows={5}
              value={correction}
              onChange={(e) => setCorrection(e.target.value)}
            />
          </label>
          <label>
            Actual project or employer
            <input
              value={correctionLocation}
              onChange={(e) => setCorrectionLocation(e.target.value)}
            />
          </label>
          <button
            className="button primary"
            disabled={busy || !correction.trim() || !correctionLocation.trim()}
            onClick={() =>
              void act(async () => {
                const result = await api<{ affected_drafts: ServerDraft[] }>(
                  `/evidence/${editing.id}`,
                  "PUT",
                  {
                    revision: editing.revision,
                    content: correction,
                    company: correctionLocation,
                    role: editing.data.role,
                    section: editing.data.section,
                    depth: editing.data.depth,
                    ownership: correction,
                    reason: "Candidate corrected the evidence in CareerProof",
                  },
                );
                if (session)
                  setSession(
                    await api<ServerSession>(`/discovery/${session.id}`),
                  );
                await refresh();
                setNotice(
                  `Correction saved on server. ${result.affected_drafts.length} version(s) affected.`,
                );
                setEditing(null);
              })
            }
          >
            Confirm and save correction
          </button>
        </Dialog>
      )}
      {exportPdfDraftId !== null && (
        <Dialog
          title="Export Resume PDF"
          wide
          onClose={() => {
            if (!isExportingPdf) setExportPdfDraftId(null);
          }}
        >
          <p className="muted">
            Choose whether to generate your PDF using our ATS-friendly default
            LaTeX template or provide your own custom LaTeX template.
          </p>
          {(() => {
            const currentDraft = drafts.find((d) => d.id === exportPdfDraftId);
            if (currentDraft && currentDraft.ats_score !== undefined) {
              return (
                <div
                  className="ats-score-pill-card"
                  style={{ margin: "14px 0 16px" }}
                >
                  <div className="ats-score-main">
                    <span className="ats-score-number">
                      {Math.round(currentDraft.ats_score)}%
                    </span>
                    <span className="ats-score-title">
                      Estimated ATS Match Score
                    </span>
                  </div>
                  <div className="ats-mini-metrics">
                    {currentDraft.keyword_match !== undefined && (
                      <span className="ats-chip">
                        Keywords {Math.round(currentDraft.keyword_match)}%
                      </span>
                    )}
                    {currentDraft.skill_match !== undefined && (
                      <span className="ats-chip">
                        Skills {Math.round(currentDraft.skill_match)}%
                      </span>
                    )}
                    {currentDraft.experience_match !== undefined && (
                      <span className="ats-chip">
                        Exp {Math.round(currentDraft.experience_match)}%
                      </span>
                    )}
                  </div>
                </div>
              );
            }
            return null;
          })()}

          <div className="pdf-export-selector">
            <div
              role="button"
              tabIndex={0}
              className={`template-option-card ${templateChoice === "default" ? "selected" : ""}`}
              onClick={() => setTemplateChoice("default")}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setTemplateChoice("default");
                }
              }}
            >
              <div className="template-card-icon">
                <Sparkles size={18} />
              </div>
              <div className="template-card-content">
                <div className="template-card-header">
                  <span className="template-card-title">
                    Default ATS-Friendly Template
                  </span>
                  <Badge tone="teal">Recommended</Badge>
                </div>
                <p className="template-card-desc">
                  Clean, modern letterpaper layout formatted with Charter
                  typography, two-column aligned dates/roles, custom section
                  rules, and bullet highlights.
                </p>
                <div style={{ marginTop: 8 }}>
                  <button
                    type="button"
                    className="button ghost small"
                    onClick={(e) => {
                      e.stopPropagation();
                      setShowDefaultPreview((prev) => !prev);
                    }}
                  >
                    <Eye size={12} />
                    {showDefaultPreview
                      ? "Hide template code"
                      : "Preview template structure"}
                  </button>
                </div>
              </div>
            </div>

            {showDefaultPreview && (
              <pre className="template-code-preview">
                {defaultTemplate || "Loading template..."}
              </pre>
            )}

            <div
              role="button"
              tabIndex={0}
              className={`template-option-card ${templateChoice === "custom" ? "selected" : ""}`}
              onClick={() => {
                setTemplateChoice("custom");
                if (!customTemplate && defaultTemplate) {
                  setCustomTemplate(defaultTemplate);
                }
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setTemplateChoice("custom");
                  if (!customTemplate && defaultTemplate) {
                    setCustomTemplate(defaultTemplate);
                  }
                }
              }}
            >
              <div className="template-card-icon">
                <Code size={18} />
              </div>
              <div className="template-card-content">
                <div className="template-card-header">
                  <span className="template-card-title">
                    Custom LaTeX Template
                  </span>
                  <Badge tone="neutral">Custom</Badge>
                </div>
                <p className="template-card-desc">
                  Supply your own LaTeX template (.tex). Customize the styling,
                  packages, or layout to match your personal preference.
                </p>
              </div>
            </div>
          </div>

          {templateChoice === "custom" && (
            <div className="template-custom-editor-container">
              <p>
                Start with the default and edit its layout, or upload a template
                with dynamic placeholders. Example names and experience must be
                replaced with placeholders so they cannot appear in your resume.
              </p>
              <label className="field">
                Upload LaTeX template (.tex)
                <input
                  type="file"
                  accept=".tex,text/plain"
                  disabled={isExportingPdf}
                  onChange={async (event) => {
                    const file = event.target.files?.[0];
                    if (!file) return;
                    if (file.size > 100_000) {
                      setExportError("Use a template under 100 KB.");
                      return;
                    }
                    setCustomTemplate(await file.text());
                    setOverflowPages(null);
                    setExportError(null);
                  }}
                />
              </label>
              <div className="template-editor-toolbar">
                <span className="eyebrow">LaTeX Template Editor</span>
                <div style={{ display: "flex", gap: 6 }}>
                  <button
                    type="button"
                    className="button secondary small"
                    onClick={() => {
                      if (defaultTemplate) setCustomTemplate(defaultTemplate);
                    }}
                  >
                    Reset to Default
                  </button>
                  <button
                    type="button"
                    className="button ghost small"
                    onClick={() => setCustomTemplate("")}
                  >
                    Clear
                  </button>
                </div>
              </div>

              <textarea
                className="template-editor-textarea"
                rows={10}
                placeholder="Paste your \documentclass[10pt, letterpaper]{article} ... code here"
                value={customTemplate}
                onChange={(e) => setCustomTemplate(e.target.value)}
              />

              <div style={{ marginTop: 8 }}>
                <small
                  className="muted"
                  style={{ display: "block", marginBottom: 4 }}
                >
                  Available dynamic tags:
                </small>
                <div className="placeholder-pills">
                  {[
                    "{{NAME}}",
                    "{{EMAIL}}",
                    "{{PHONE}}",
                    "{{SUMMARY}}",
                    "{{SKILLS}}",
                    "{{EXPERIENCE}}",
                    "{{PROJECTS}}",
                    "{{EDUCATION}}",
                  ].map((tag) => (
                    <span
                      key={tag}
                      className="placeholder-pill"
                      onClick={() =>
                        setCustomTemplate((prev) => prev + " " + tag)
                      }
                      title="Click to insert into editor"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}

          {exportError && (
            <div
              style={{
                marginTop: 14,
                padding: "10px 14px",
                background: "#fdf2f2",
                border: "1px solid #f8b4b4",
                borderRadius: 6,
                color: "#9b1c1c",
                fontSize: 12,
              }}
            >
              <strong>Error:</strong> {exportError}
            </div>
          )}

          {overflowPages && (
            <section role="alert" className="main-surface">
              <h3>Your resume is {overflowPages} pages</h3>
              <p>
                Keep the full version, or shorten verified bullets to fit one
                page? If needed, the concise copy omits lower-priority bullets
                while retaining every role and education entry. Your saved draft
                stays unchanged.
              </p>
              <div className="dialog-actions">
                <button
                  className="button secondary"
                  disabled={isExportingPdf}
                  onClick={() => void handleGeneratePdf("keep")}
                >
                  Keep all {overflowPages} pages
                </button>
                <button
                  className="button primary"
                  disabled={isExportingPdf}
                  onClick={() => void handleGeneratePdf("one_page")}
                >
                  Make a concise one-page copy
                </button>
              </div>
            </section>
          )}

          <div className="dialog-actions">
            <button
              className="button secondary"
              disabled={isExportingPdf}
              onClick={() => setExportPdfDraftId(null)}
            >
              Cancel
            </button>
            <button
              className="button secondary"
              disabled={isExportingPdf}
              onClick={() => void handleDownloadLatex()}
              title="Download the compiled LaTeX source file (.tex)"
            >
              <FileCode size={14} />
              Download .tex
            </button>
            <button
              className="button primary"
              disabled={isExportingPdf}
              onClick={() => void handleGeneratePdf()}
            >
              <Download size={14} />
              {isExportingPdf ? "Compiling PDF..." : "Generate & Download PDF"}
            </button>
          </div>
        </Dialog>
      )}
    </div>
  );
}
function ArrowUpRightIcon() {
  return <ArrowRight size={13} />;
}
