"use client";

import { useState, useEffect, useMemo, useRef } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  ArrowUpRight,
  ArrowRight,
  Plus,
  Search,
  Command,
  PanelLeftClose,
  PanelLeftOpen,
  LayoutDashboard,
  Layers,
  ScanSearch,
  ShieldCheck,
  GitBranch,
  FileText,
  MessagesSquare,
  Briefcase,
  Settings,
  ChevronDown,
  ChevronRight,
  Check,
  CheckCheck,
  ExternalLink,
  Link2,
  Sparkles,
  Activity,
  Target,
  Clock,
  Download,
  RotateCcw,
  GripVertical,
  X,
  Menu,
  CheckCircle2,
  Circle,
  ArrowLeft,
  SlidersHorizontal,
  Eye,
  BookOpen,
  BarChart3,
  Upload,
  RefreshCw,
  AlertTriangle,
  FileCode,
  Send,
  Zap,
  UploadCloud,
  FileUp,
  HelpCircle,
  Compass,
  Info,
  Trash2,
} from "lucide-react";
import { Badge, Button, Modal } from "./primitives";
import {
  navigation,
  stages,
  type Section,
  type Evidence,
  type Application,
} from "@/lib/workspace/data";
import {
  api,
  downloadExport,
  ResumePageLimitError,
  getDefaultLatexTemplate,
  validateFiles,
  pasteResumeText,
  deleteResume,
  getATSCatalog,
  type ServerResume,
  type ServerDraft,
  type ServerOptimization,
  type ServerEvidence,
  type ServerSession,
  type ObjectionReport,
  type DefenseCard,
  type DefenseEvaluationResult,
  type ProofSpec,
  type ATSCatalog,
  type ATSCatalogItem,
  type SystemStatus,
  type ClaimHeatmapReport,
} from "@/lib/careerproof/api";
import { ATSCheckerModal } from "@/components/careerproof/ats-checker";
import { HiringObjectionView } from "@/components/careerproof/objections";
import { InterviewDefenseView } from "@/components/careerproof/defense";
import { ClaimHeatmapView } from "@/components/careerproof/claim-heatmap";
import "./workspace.css";

const icons = [
  LayoutDashboard,
  ScanSearch,
  FileText,
  Sparkles,
  BarChart3,
  ShieldCheck,
  MessagesSquare,
  Layers,
  Briefcase,
  Settings,
];

const subtitles: Record<Section, string> = {
  Dashboard: "Overview & guided workflow: pick target job, tailor your resume, and export 1-page PDF.",
  "Job Analyzer": "Step 1: Pick or paste target Job Description to extract requirements and skills.",
  "Resume Studio": "Step 2: ⚡ Tailor resume bullets with AI, enforce 1-page limit, and export LaTeX PDF.",
  "Gap Resolver": "Step 3: Answer targeted questions to bridge JD gaps with your real evidence.",
  "ATS Scanner": "Sideline Check: Scan ATS keyword density, hard skills, and tenure duration match.",
  "Objection Engine": "Sideline Defense: Uncover what recruiters will question on your CV.",
  "Interview Defense": "Sideline Defense: Interactive flashcards with truth boundaries to ace technical probes.",
  "Evidence Vault": "Your verified career achievements, metrics, and document sources.",
  Applications: "Track your active job pipeline across interview stages with claim win-rate analytics.",
  Settings: "Configure your system status, model parameters, and local environment.",
};

const navHints: Record<Section, string> = {
  Dashboard: "Guided overview",
  "Job Analyzer": "Target roles & JD",
  "Resume Studio": "⚡ Tailor & 1-page PDF",
  "Gap Resolver": "Bridge skill gaps",
  "ATS Scanner": "Sideline score scan",
  "Objection Engine": "Recruiter doubts",
  "Interview Defense": "Practice probes",
  "Evidence Vault": "Verified facts",
  Applications: "Pipeline tracker",
  Settings: "Status & config",
};

type Bullet = {
  id: string;
  text: string;
  included: boolean;
  originalText?: string;
  company?: string;
  role?: string;
};

export default function Workspace() {
  const [section, setSection] = useState<Section>("Dashboard");
  const [collapsed, setCollapsed] = useState(false);
  const [mobile, setMobile] = useState(false);
  const [command, setCommand] = useState(false);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("All evidence");
  const [selectedEvidence, setSelectedEvidence] = useState<Evidence | null>(null);

  // Backend live state
  const [resumes, setResumes] = useState<ServerResume[]>([]);
  const [selectedResumeId, setSelectedResumeId] = useState<number | undefined>();
  const [draftsList, setDraftsList] = useState<ServerDraft[]>([]);
  const [activeDraftId, setActiveDraftId] = useState<number | null>(null);
  const [optimization, setOptimization] = useState<ServerOptimization | null>(null);
  const [objectionReport, setObjectionReport] = useState<ObjectionReport | null>(null);
  const [defenseCards, setDefenseCards] = useState<DefenseCard[]>([]);
  const [proofSpecs, setProofSpecs] = useState<ProofSpec[]>([]);
  const [evidenceList, setEvidenceList] = useState<Evidence[]>([]);
  const [catalog, setCatalog] = useState<ATSCatalog>({ resumes: [], jobs: [] });
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [candidateMode, setCandidateMode] = useState<"launch" | "advance">("advance");

  // UI modals
  const [showAtsScanner, setShowAtsScanner] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showExportModal, setShowExportModal] = useState(false);
  const [showPasteModal, setShowPasteModal] = useState(false);
  const [showAddJobModal, setShowAddJobModal] = useState(false);

  // Upload state
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [uploadBusy, setUploadBusy] = useState(false);
  const [pastedText, setPastedText] = useState("");
  const [pastedName, setPastedName] = useState("My Resume.txt");
  const dashboardFileInputRef = useRef<HTMLInputElement>(null);

  // Custom Job state
  const [newCompany, setNewCompany] = useState("");
  const [newRole, setNewRole] = useState("");
  const [newJdText, setNewJdText] = useState("");

  // Target Job state
  const [selectedJob, setSelectedJob] = useState<{
    id: string;
    company: string;
    role: string;
    logo: string;
    match: number;
    color: string;
    location: string;
    description: string;
    skills: string[];
    raw_id?: number;
  }>({
    id: "amgen",
    company: "Amgen",
    role: "Machine Learning Engineer",
    logo: "A",
    match: 84,
    color: "#3b82f6",
    location: "Remote · AI/ML",
    description:
      "Design and deploy production machine learning models, statistical evaluation pipelines, and LLM orchestration systems with Python, PyTorch, and cloud services.",
    skills: ["Python", "PyTorch", "Machine Learning", "FastAPI", "Docker", "RAG"],
  });

  // Primary Workflow Card States
  const [selectedResumeIds, setSelectedResumeIds] = useState<number[]>([]);
  const [companyInput, setCompanyInput] = useState("Amgen");
  const [roleInput, setRoleInput] = useState("Machine Learning Engineer");
  const [jdInput, setJdInput] = useState(
    "Design and deploy production machine learning models, statistical evaluation pipelines, and LLM orchestration systems with Python, PyTorch, and cloud services.",
  );
  const [projectNotes, setProjectNotes] = useState("");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [showDirectPaste, setShowDirectPaste] = useState(false);
  const [directPasteText, setDirectPasteText] = useState("");
  const [directPasteName, setDirectPasteName] = useState("My Resume.txt");
  const [isTailoring, setIsTailoring] = useState(false);

  // Local & tailored bullets
  const [bullets, setBullets] = useState<Bullet[]>([]);

  // Defense testing state
  const [cardIndex, setCardIndex] = useState(0);
  const [cardFlipped, setCardFlipped] = useState(false);
  const [defenseAnswer, setDefenseAnswer] = useState("");
  const [defenseEvaluating, setDefenseEvaluating] = useState(false);
  const [defenseFeedback, setDefenseFeedback] =
    useState<DefenseEvaluationResult | null>(null);

  // LaTeX export modal state
  const [exportTemplate, setExportTemplate] = useState<"default" | "custom">("default");
  const [pagePolicy, setPagePolicy] = useState<"ask" | "one_page" | "keep">("one_page");
  const [isExportingPdf, setIsExportingPdf] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  // Applications kanban state
  const [applications, setApplications] = useState<Application[]>([
    {
      id: "1",
      company: "Amgen",
      role: "Machine Learning Engineer",
      stage: "Preparing",
      date: "Oct 8",
      version: "Amgen · v2",
    },
    {
      id: "2",
      company: "OpenAI",
      role: "Staff MLOps Engineer",
      stage: "Applied",
      date: "Oct 6",
      version: "OpenAI · v1",
    },
    {
      id: "3",
      company: "NovaTech",
      role: "Senior Fullstack Engineer",
      stage: "Interviewing",
      date: "Oct 4",
      version: "NovaTech · v1",
    },
  ]);

  const [expanded, setExpanded] = useState<string[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [savedAnswers, setSavedAnswers] = useState<Record<string, string>>({});
  const [toast, setToast] = useState("");
  const [ready, setReady] = useState(false);
  const [name, setName] = useState("Candidate");
  const [notifications, setNotifications] = useState(true);
  const [showLegacyObjectionsView, setShowLegacyObjectionsView] = useState(false);
  const [showLegacyDefenseView, setShowLegacyDefenseView] = useState(false);
  const [showClaimHeatmap, setShowClaimHeatmap] = useState(false);
  const [claimHeatmap, setClaimHeatmap] = useState<ClaimHeatmapReport | null>(null);

  async function handleToggleClaimHeatmap() {
    if (!showClaimHeatmap && !claimHeatmap) {
      try {
        const rep = await api<ClaimHeatmapReport>("/analytics/claim-heatmap");
        setClaimHeatmap(rep);
      } catch (e) {
        console.error("Failed to load claim heatmap", e);
      }
    }
    setShowClaimHeatmap((v) => !v);
  }

  const reduce = useReducedMotion();

  // Helper function to extract candidate name from parsed resume
  function extractCandidateName(r?: ServerResume): string | null {
    if (!r) return null;
    const raw = r.parsed_raw?.raw_source_text;
    if (raw) {
      const firstLine = raw.trim().split("\n")[0].trim();
      if (firstLine && firstLine.length < 40 && !firstLine.includes("@") && !firstLine.includes("http")) {
        return firstLine.replace(/[^\w\s-]/g, "").trim();
      }
    }
    const filenameMatch = r.name.match(/^([A-Za-z]+(?:_[A-Za-z]+)?)/);
    if (filenameMatch) {
      return filenameMatch[1].replace(/_/g, " ");
    }
    return null;
  }

  // Load all live backend data
  async function loadBackendData(preferredResumeId?: number) {
    try {
      const [rs, ds, evs, cat, sys] = await Promise.all([
        api<ServerResume[]>("/resumes").catch(() => []),
        api<ServerDraft[]>("/evidence-drafts").catch(() => []),
        api<ServerEvidence[]>("/evidence").catch(() => []),
        getATSCatalog().catch(() => ({ resumes: [], jobs: [] })),
        api<SystemStatus>("/system/status").catch(() => null),
      ]);

      setResumes(rs);
      setDraftsList(ds);
      setCatalog(cat);
      if (sys) setSystemStatus(sys);

      // Determine active resume
      let activeRes: ServerResume | undefined;
      if (preferredResumeId) {
        activeRes = rs.find((r) => r.id === preferredResumeId);
      }
      if (!activeRes && rs.length > 0) {
        // Pick ready resume with bullets first
        activeRes = rs.find((r) => r.bullets && r.bullets.length > 0) || rs[0];
      }
      if (activeRes) {
        setSelectedResumeId(activeRes.id);
        setSelectedResumeIds((prev) => (prev.length > 0 ? prev : [activeRes.id]));
        const parsedName = extractCandidateName(activeRes);
        if (parsedName) setName(parsedName);
      } else {
        setSelectedResumeId(undefined);
        setSelectedResumeIds([]);
        setName("Candidate");
      }

      // Convert backend evidence to frontend model
      const convertedEv: Evidence[] = [];
      if (evs && evs.length > 0) {
        evs.forEach((ev) => {
          const content = ev.data.content || "";
          const org = ev.data.company
            ? `${ev.data.company} ${ev.data.role ? `· ${ev.data.role}` : ""}`
            : "Verified Experience";
          const shortTitle =
            content.split(/[.\n]/)[0].slice(0, 50) + (content.length > 50 ? "…" : "");
          const isConfirmed = !!(
            ev.data.ownership ||
            (ev.data as any).ownership_confirmed ||
            ev.data.depth === "professional"
          );
          convertedEv.push({
            id: `ev-${ev.id}`,
            title: shortTitle || `Achievement #${ev.id}`,
            organization: org.trim(),
            kind: ev.data.section === "Projects" ? "Project" : "Experience",
            status: isConfirmed ? "Verified" : "Needs context",
            text: content,
            skills: ev.data.confirmed_terms || ["Python", "FastAPI", "AI/ML"],
            source: ev.source_refs?.join(", ") || "Candidate Resume",
            history: [
              `Recorded in evidence catalog · rev ${ev.revision}`,
              isConfirmed
                ? "Ownership verified by candidate"
                : "Awaiting candidate ownership confirmation",
            ],
          });
        });
      }

      // Add bullets from active resume if not already in evidence
      if (activeRes?.bullets) {
        activeRes.bullets.forEach((b) => {
          const exists = convertedEv.some((e) => e.text === b.bullet);
          if (!exists) {
            const bAny = b as any;
            convertedEv.push({
              id: `bullet-${b.id}`,
              title: b.bullet.split(/[.\n]/)[0].slice(0, 50) + "…",
              organization: b.company
                ? `${b.company} · ${bAny.role || ""}`
                : "Candidate Experience",
              kind: b.section === "Projects" ? "Project" : "Experience",
              status: "Verified",
              text: b.bullet,
              skills: bAny.technologies?.length
                ? bAny.technologies
                : ["Python", "Engineering"],
              source: `${activeRes?.name || "Uploaded Resume"}`,
              history: ["Imported from structured resume parse"],
            });
          }
        });
      }

      setEvidenceList(convertedEv);

      // Determine active draft and load optimization details
      const targetDraft = ds.find((d) => d.status === "complete") || ds[0];
      if (targetDraft) {
        setActiveDraftId(targetDraft.id);
        void loadOptimization(targetDraft.id);
      } else if (convertedEv.length > 0) {
        // Fallback bullets from evidence
        setBullets(
          convertedEv.map((e) => ({
            id: e.id,
            text: e.text,
            included: true,
            originalText: e.text,
            company: e.organization,
          })),
        );
      } else {
        setBullets([]);
        setOptimization(null);
        setObjectionReport(null);
        setDefenseCards([]);
        setProofSpecs([]);
      }
    } catch (err) {
      console.error("Failed to load live backend data", err);
    } finally {
      setReady(true);
    }
  }

  // Load a specific optimization draft
  async function loadOptimization(draftId: number) {
    setActiveDraftId(draftId);
    try {
      const opt = await api<ServerOptimization>(`/optimizations/${draftId}`);
      setOptimization(opt);

      // Set tailored bullets
      if (opt.optimized_content && opt.optimized_content.length > 0) {
        setBullets(
          opt.optimized_content.map((c) => ({
            id: `opt-${c.original_id}`,
            text: c.optimized_bullet,
            included: (c as any).action !== "exclude" && (c as any).included !== false,
            originalText: c.original_bullet,
            company: c.company,
            role: c.role,
          })),
        );
      }

      // Objections report
      if (opt.gap_report?.objection_analysis) {
        setObjectionReport(opt.gap_report.objection_analysis);
      } else {
        const obj = await api<ObjectionReport>(`/evidence-drafts/${draftId}/objections`);
        setObjectionReport(obj);
      }

      // Defense cards, proof specs
      const [cards, specs] = await Promise.all([
        api<DefenseCard[]>(
          `/evidence-drafts/${draftId}/defense-cards?mode=${candidateMode}`,
        ).catch(() => []),
        api<ProofSpec[]>(
          `/evidence-drafts/${draftId}/proof-specs?mode=${candidateMode}`,
        ).catch(() => []),
      ]);
      setDefenseCards(cards);
      setProofSpecs(specs);

      // Update active target job if draft provides details
      if (opt.job_company || opt.job_role) {
        setSelectedJob((prev) => ({
          ...prev,
          company: opt.job_company || prev.company,
          role: opt.job_role || prev.role,
        }));
      }
    } catch (e) {
      console.error("Could not load optimization", e);
    }
  }

  useEffect(() => {
    void loadBackendData();
    // Poll backend every 10 seconds for updates
    const timer = setInterval(() => {
      void loadBackendData(selectedResumeId);
    }, 10000);
    return () => clearInterval(timer);
  }, []);

  // Keyboard shortcut for command palette
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCommand((v) => !v);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // Toast timer
  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(""), 3500);
    return () => clearTimeout(id);
  }, [toast]);

  function go(s: Section) {
    if (window.innerWidth < 761) setCollapsed(false);
    if (s === "ATS Scanner") {
      setShowAtsScanner(true);
    }
    setSection(s);
    setQuery("");
    setMobile(false);
    setCommand(false);
  }

  function move(id: string, stage: string) {
    setApplications((a) => a.map((x) => (x.id === id ? { ...x, stage } : x)));
    setToast(`Application moved to ${stage.toLowerCase()}`);
  }

  // Handle defense testing
  async function handleTestDefense(cardId: string) {
    if (!defenseAnswer.trim() || !activeDraftId) return;
    setDefenseEvaluating(true);
    try {
      const res = await api<DefenseEvaluationResult>(
        `/evidence-drafts/${activeDraftId}/evaluate-defense`,
        "POST",
        { card_id: cardId, explanation: defenseAnswer.trim() },
      );
      setDefenseFeedback(res);
      setToast("Defense evaluated! Feedback received.");
    } catch (e) {
      console.error(e);
      setToast("Evaluation request failed. Ensure backend is running.");
    } finally {
      setDefenseEvaluating(false);
    }
  }

  // Handle PDF Export
  async function handleExportPdf() {
    if (!activeDraftId) {
      setToast("No optimization draft selected for PDF export.");
      return;
    }
    setIsExportingPdf(true);
    setExportError(null);
    try {
      const result = await downloadExport(activeDraftId, "pdf", {
        templateChoice: exportTemplate,
        pagePolicy,
      });
      setToast(
        `Downloaded ${result.pages}-page resume.${pagePolicy === "one_page" ? ` Compact 1-page budget applied.` : ""}`,
      );
      setShowExportModal(false);
    } catch (err: unknown) {
      if (err instanceof ResumePageLimitError) {
        setExportError(
          `Resume exceeds 1 page (${err.pages} pages). Select 'Compact 1-page' policy or deselect a bullet.`,
        );
        return;
      }
      setExportError(err instanceof Error ? err.message : "Failed to compile PDF.");
    } finally {
      setIsExportingPdf(false);
    }
  }

  // Handle LaTeX Source Export
  async function handleExportLatex() {
    if (!activeDraftId) return;
    setIsExportingPdf(true);
    try {
      await downloadExport(activeDraftId, "latex", { templateChoice: exportTemplate });
      setToast("Downloaded LaTeX (.tex) source code.");
      setShowExportModal(false);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : "Failed to download LaTeX source.");
    } finally {
      setIsExportingPdf(false);
    }
  }

  // Handle Resume Upload
  async function handleUploadFiles() {
    if (!uploadFiles.length) return;
    setUploadBusy(true);
    try {
      const form = new FormData();
      uploadFiles.forEach((f) => form.append("files", f));
      const uploaded = await api<ServerResume[]>("/resumes/upload-batch", "POST", form);
      setUploadFiles([]);
      setShowUploadModal(false);
      setToast(`Uploaded ${uploaded.length} resume(s). Parsing completed!`);
      if (uploaded.length > 0) {
        await loadBackendData(uploaded[0].id);
      }
    } catch (err) {
      setToast(err instanceof Error ? err.message : "Failed to upload resume.");
    } finally {
      setUploadBusy(false);
    }
  }

  // Quick direct upload from dashboard input
  async function handleDirectFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const incoming = Array.from(e.target.files || []);
    if (!incoming.length) return;
    const issue = validateFiles(incoming, selectedFiles.length);
    if (issue) {
      setToast(issue);
      return;
    }
    setSelectedFiles((prev) => [...prev, ...incoming]);
    e.target.value = "";
  }

  // Upload pending selected files from workflow card
  async function handleUploadSelectedFiles() {
    if (!selectedFiles.length) return;
    setUploadBusy(true);
    try {
      const form = new FormData();
      selectedFiles.forEach((f) => form.append("files", f));
      const uploaded = await api<ServerResume[]>("/resumes/upload-batch", "POST", form);
      setToast(`Uploaded ${uploaded.length} resume(s)! Text extraction complete.`);
      setSelectedFiles([]);
      if (uploaded.length > 0) {
        const newIds = uploaded.map((r) => r.id);
        setSelectedResumeIds(newIds);
        setSelectedResumeId(uploaded[0].id);
        await loadBackendData(uploaded[0].id);
      }
    } catch (err) {
      setToast(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploadBusy(false);
    }
  }

  // Ingest direct text from inline paste box
  async function handleIngestDirectPaste() {
    if (!directPasteText.trim()) return;
    setUploadBusy(true);
    try {
      const r = await pasteResumeText(directPasteText.trim(), directPasteName);
      setDirectPasteText("");
      setShowDirectPaste(false);
      setSelectedResumeIds([r.id]);
      setSelectedResumeId(r.id);
      setToast("Pasted resume processed and saved to library.");
      await loadBackendData(r.id);
    } catch (err) {
      setToast(err instanceof Error ? err.message : "Failed to parse text.");
    } finally {
      setUploadBusy(false);
    }
  }

  // Handle Pasting Resume Text
  async function handlePasteResume() {
    if (!pastedText.trim()) return;
    setUploadBusy(true);
    try {
      const r = await pasteResumeText(pastedText.trim(), pastedName);
      setPastedText("");
      setShowPasteModal(false);
      setSelectedResumeIds([r.id]);
      setSelectedResumeId(r.id);
      setToast("Pasted resume processed and saved to library.");
      await loadBackendData(r.id);
    } catch (err) {
      setToast(err instanceof Error ? err.message : "Failed to parse text.");
    } finally {
      setUploadBusy(false);
    }
  }

  // Handle Deleting a Resume from Server
  async function handleDeleteResume(resumeId: number) {
    const target = resumes.find((r) => r.id === resumeId);
    const resumeName = target?.name || `Resume #${resumeId}`;
    if (!window.confirm(`Delete "${resumeName}" from server? This will remove parsed bullets and cannot be undone.`)) {
      return;
    }
    setToast(`Deleting ${resumeName}...`);
    try {
      await deleteResume(resumeId);
      const remaining = resumes.filter((r) => r.id !== resumeId);
      setResumes(remaining);
      const remainingIds = selectedResumeIds.filter((id) => id !== resumeId);
      setSelectedResumeIds(remainingIds);
      if (selectedResumeId === resumeId) {
        setSelectedResumeId(remaining[0]?.id);
      }
      setToast(`Deleted "${resumeName}".`);
      await loadBackendData(remaining[0]?.id);
    } catch (err) {
      setToast(err instanceof Error ? err.message : "Failed to delete resume.");
    }
  }

  // Handle Adding Custom Job
  async function handleAddCustomJob() {
    if (!newCompany.trim() || !newRole.trim() || !newJdText.trim()) return;
    try {
      const res = await api<{ id: number }>("/jobs", "POST", {
        company: newCompany.trim(),
        role: newRole.trim(),
        raw_text: newJdText.trim(),
      });
      setSelectedJob({
        id: `job-${res.id}`,
        company: newCompany.trim(),
        role: newRole.trim(),
        logo: newCompany.charAt(0).toUpperCase(),
        match: 80,
        color: "#6947ae",
        location: "Custom Target Role",
        description: newJdText.slice(0, 300) + "…",
        skills: ["Required competencies from JD"],
        raw_id: res.id,
      });
      setCompanyInput(newCompany.trim());
      setRoleInput(newRole.trim());
      setJdInput(newJdText.trim());
      setShowAddJobModal(false);
      setNewCompany("");
      setNewRole("");
      setNewJdText("");
      setToast("New job added to Job Analyzer!");
    } catch (err) {
      setToast(err instanceof Error ? err.message : "Failed to add job.");
    }
  }

  // Core Hero Action: ⚡ Tailor Resume for Target Job
  async function handleTailorJob(
    targetOrCompany?: string | { company: string; role: string; description?: string; raw_id?: number },
    targetRole?: string,
    targetJd?: string,
    customResumeIds?: number[],
    notes = projectNotes,
  ) {
    if (!resumes || resumes.length === 0) {
      setToast("Upload a resume first to extract your verified career evidence.");
      return;
    }

    let finalCompany = (companyInput || selectedJob.company || "Target Company").trim();
    let finalRole = (roleInput || selectedJob.role || "Target Role").trim();
    let finalJd = (jdInput || selectedJob.description || "").trim();
    let finalJobId = selectedJob.raw_id;

    if (targetOrCompany) {
      if (typeof targetOrCompany === "object") {
        finalCompany = (targetOrCompany.company || finalCompany).trim();
        finalRole = (targetOrCompany.role || finalRole).trim();
        finalJd = (targetOrCompany.description || finalJd).trim();
        finalJobId = targetOrCompany.raw_id;
      } else {
        finalCompany = targetOrCompany.trim();
        if (targetRole) finalRole = targetRole.trim();
        if (targetJd) finalJd = targetJd.trim();
      }
    }

    let targetResumeIds = customResumeIds && customResumeIds.length > 0
      ? customResumeIds
      : (selectedResumeIds.length > 0
          ? selectedResumeIds
          : (selectedResumeId ? [selectedResumeId] : (resumes[0]?.id ? [resumes[0].id] : [])));

    if (!targetResumeIds || targetResumeIds.length === 0) {
      setToast("Choose or upload a resume first.");
      return;
    }

    setIsTailoring(true);
    setToast(`⚡ Starting AI tailoring for ${finalCompany}...`);

    try {
      // 1. Ensure target job exists in backend
      let jobId = finalJobId;
      if (!jobId) {
        const existingJobs = await api<any[]>("/jobs").catch(() => []);
        const match = existingJobs.find(
          (j) =>
            j.company?.toLowerCase() === finalCompany.toLowerCase() &&
            j.role?.toLowerCase() === finalRole.toLowerCase(),
        );
        if (match) {
          jobId = match.id;
        } else {
          const createdJob = await api<{ id: number }>("/jobs", "POST", {
            company: finalCompany,
            role: finalRole,
            raw_text:
              finalJd ||
              `${finalRole} at ${finalCompany}. Required skills: Python, SQL, Cloud Services.`,
          });
          jobId = createdJob.id;
        }
      }

      // Sync selectedJob state
      setSelectedJob({
        id: `job-${jobId}`,
        company: finalCompany,
        role: finalRole,
        logo: finalCompany.charAt(0).toUpperCase(),
        match: 86,
        color: "#3b82f6",
        location: "Active Target Role",
        description: finalJd,
        skills: ["Required competencies from JD"],
        raw_id: jobId,
      });

      // 2. Start discovery session
      const session = await api<ServerSession>("/discovery", "POST", {
        resume_ids: targetResumeIds,
        job_id: jobId,
        project_notes: notes,
      });

      // 3. Trigger optimization draft
      const optRes = await api<{ id: number }>(`/discovery/${session.id}/optimize`, "POST");
      const optId = optRes.id;

      setToast(`⚡ Customizing bullets for ${finalCompany}...`);

      // 4. Poll for draft completion
      let attempts = 0;
      while (attempts < 15) {
        await new Promise((r) => setTimeout(r, 1000));
        attempts++;
        try {
          const drafts = await api<ServerDraft[]>("/evidence-drafts");
          const targetDraft = drafts.find((d) => d.id === optId);
          if (targetDraft && (targetDraft.status === "complete" || targetDraft.status === "failed")) {
            break;
          }
        } catch {
          // ignore transient poll error
        }
      }

      // 5. Load the completed optimization
      if (optId) {
        await loadOptimization(optId);
      }
      await loadBackendData(targetResumeIds[0]);

      // 6. Navigate directly to Resume Studio
      setSection("Resume Studio");
      setToast(`⚡ Resume successfully tailored for ${finalCompany}!`);
    } catch (err: any) {
      console.error("Tailoring error", err);
      setToast(err?.message || "Tailoring encountered an error. Please try again.");
    } finally {
      setIsTailoring(false);
    }
  }

  // Unified Workflow Card Continue/Tailor Button
  async function handleWorkflowTailor() {
    let activeIds = [...selectedResumeIds];

    if (selectedFiles.length > 0) {
      setUploadBusy(true);
      try {
        const form = new FormData();
        selectedFiles.forEach((f) => form.append("files", f));
        const uploaded = await api<ServerResume[]>("/resumes/upload-batch", "POST", form);
        setSelectedFiles([]);
        activeIds = uploaded.map((r) => r.id);
        setSelectedResumeIds(activeIds);
        if (uploaded.length > 0) {
          setSelectedResumeId(uploaded[0].id);
          await loadBackendData(uploaded[0].id);
        }
      } catch {
        setToast("Failed to upload file before tailoring.");
        setUploadBusy(false);
        return;
      }
      setUploadBusy(false);
    }

    if (activeIds.length === 0 && resumes.length > 0) {
      activeIds = [selectedResumeId || resumes[0].id];
    }

    await handleTailorJob(companyInput, roleInput, jdInput, activeIds, projectNotes);
  }

  // Filtered evidence for Vault
  const filteredEvidence = evidenceList.filter(
    (e) =>
      (filter === "All evidence" || e.kind === filter || e.status === filter) &&
      `${e.title} ${e.organization} ${e.skills.join(" ")}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );

  // Target jobs list from catalog + sample
  const displayJobs = useMemo(() => {
    const list = [
      {
        id: "amgen",
        company: "Amgen",
        logo: "A",
        role: "Machine Learning Engineer",
        match: 86,
        color: "#3b82f6",
        location: "Remote · AI/ML",
        description:
          "Design and deploy production machine learning models, statistical evaluation pipelines, and LLM orchestration systems with Python, PyTorch, and cloud services.",
        skills: ["Python", "PyTorch", "FastAPI", "Docker", "RAG", "Model Evaluation"],
      },
      {
        id: "openai",
        company: "OpenAI",
        logo: "O",
        role: "Staff MLOps Engineer",
        match: 82,
        color: "#10a37f",
        location: "San Francisco · Hybrid",
        description:
          "Scale inference clusters, latency optimization, high-throughput model serving, and distributed systems for production frontier models.",
        skills: ["Python", "MLOps", "Kubernetes", "Docker", "FastAPI", "Distributed Systems"],
      },
      {
        id: "novatech",
        company: "NovaTech",
        logo: "N",
        role: "Senior Fullstack Engineer",
        match: 78,
        color: "#8b5cf6",
        location: "New York · Hybrid",
        description:
          "Build scalable backend microservices, real-time data pipelines, and responsive frontend interfaces.",
        skills: ["Python", "TypeScript", "FastAPI", "PostgreSQL", "Docker"],
      },
    ];

    if (catalog.jobs && catalog.jobs.length > 0) {
      catalog.jobs.slice(0, 5).forEach((j) => {
        if (!list.some((existing) => existing.company === j.company)) {
          list.push({
            id: `cat-${j.id}`,
            company: j.company || "Enterprise Corp",
            logo: (j.company || "E")[0].toUpperCase(),
            role: j.role || "Software Engineer",
            match: 80,
            color: "#6947ae",
            location: "Active Job Catalog",
            description: `Target role requiring ${j.keywords_count || 10}+ core technical competencies and ${j.experience_years || 2}+ years experience.`,
            skills: ["Python", "Backend", "APIs", "Cloud"],
          });
        }
      });
    }
    return list;
  }, [catalog.jobs]);

  const activeResumeObj = resumes.find((r) => r.id === selectedResumeId);
  const activeDefenseCard = defenseCards[cardIndex] || defenseCards[0];

  const matches = useMemo(
    () => navigation.filter((n) => n.toLowerCase().includes(query.toLowerCase())),
    [query],
  );

  return (
    <div className={`cp-workspace ${collapsed ? "is-collapsed" : ""}`}>
      {/* SIDEBAR */}
      <aside className={`cp-sidebar ${mobile ? "is-mobile-open" : ""}`}>
        <a
          className="cp-brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            go("Dashboard");
          }}
        >
          <span className="cp-brand-mark">
            <Layers size={19} />
          </span>
          {!collapsed && (
            <span>
              careerproof<span className="cp-brand-dot">.</span>
            </span>
          )}
        </a>

        {/* User profile / active resume chip */}
        <button
          className="cp-team"
          onClick={() => setShowUploadModal(true)}
          title="Upload or switch resume"
        >
          <span className="cp-avatar">
            {resumes.length > 0
              ? name
                  .split(" ")
                  .map((n) => n[0])
                  .slice(0, 2)
                  .join("")
              : "+"}
          </span>
          {!collapsed && (
            <>
              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {activeResumeObj ? activeResumeObj.name : "No resume loaded"}
                <small>
                  {resumes.length > 0 ? `${resumes.length} resume saved` : "Click to upload"}
                  <span className="cp-tiny-dot" />
                </small>
              </span>
              <ChevronDown size={13} />
            </>
          )}
        </button>

        <button
          className="cp-search-launch"
          onClick={() => {
            setQuery("");
            setCommand(true);
          }}
        >
          <Search size={15} />
          {!collapsed && (
            <>
              <span>Quick search</span>
              <kbd>⌘ K</kbd>
            </>
          )}
        </button>

        <div className="cp-nav-label">{collapsed ? "···" : "CORE WORKFLOW"}</div>

        <nav aria-label="Workspace">
          {navigation.map((n, i) => {
            const Icon = icons[i] || LayoutDashboard;
            const isAts = n === "ATS Scanner";
            const isStudio = n === "Resume Studio";
            const hint = navHints[n];

            // Render subheader divider before ATS Scanner (Sideline) and Evidence Vault
            const showSidelineDivider = n === "ATS Scanner";
            const showPortfolioDivider = n === "Evidence Vault";

            return (
              <div key={n}>
                {showSidelineDivider && !collapsed && (
                  <div className="cp-nav-label" style={{ marginTop: 10 }}>
                    SIDELINE VERIFICATION & DEFENSE
                  </div>
                )}
                {showPortfolioDivider && !collapsed && (
                  <div className="cp-nav-label" style={{ marginTop: 10 }}>
                    PORTFOLIO & PIPELINE
                  </div>
                )}
                <button
                  title={collapsed ? `${n} — ${hint}` : undefined}
                  aria-current={section === n ? "page" : undefined}
                  onClick={() => go(n)}
                  className={section === n ? "active" : ""}
                >
                  <Icon size={18} />
                  {!collapsed && (
                    <div style={{ display: "flex", flexDirection: "column", flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                        <span style={{ fontWeight: isAts || isStudio ? 600 : undefined }}>{n}</span>
                        {n === "Objection Engine" && objectionReport?.summary && (
                          <span className="cp-nav-count">
                            {objectionReport.summary.total_objections}
                          </span>
                        )}
                        {isAts && (
                          <span
                            style={{
                              fontSize: "0.65rem",
                              fontWeight: 700,
                              background: "#f0eafa",
                              color: "#6947ae",
                              padding: "1px 6px",
                              borderRadius: 8,
                              border: "1px solid #ded3f0",
                            }}
                          >
                            Scan
                          </span>
                        )}
                      </div>
                      <small style={{ fontSize: "10px", color: "#6b7280", marginTop: "1px" }}>
                        {hint}
                      </small>
                    </div>
                  )}
                </button>
              </div>
            );
          })}
        </nav>

        <div className="cp-sidebar-bottom">
          {!collapsed && (
            <div className="cp-plan">
              <span>
                <Sparkles size={15} /> ⚡ Career Guide
              </span>
              <p>Upload resume ➜ Select target JD ➜ ⚡ Tailor bullets with AI ➜ Defend in interviews.</p>
              <button onClick={() => go("Resume Studio")}>
                Open Tailor Studio <Sparkles size={14} />
              </button>
            </div>
          )}
          <button className="cp-user" onClick={() => go("Settings")}>
            <span className="cp-avatar photo">
              {resumes.length > 0
                ? name
                    .split(" ")
                    .map((n) => n[0])
                    .slice(0, 2)
                    .join("")
                : "U"}
            </span>
            {!collapsed && (
              <span>
                {name}
                <small>Local User (user_test)</small>
              </span>
            )}
          </button>
        </div>
      </aside>

      {mobile && (
        <button
          className="cp-mobile-shade"
          aria-label="Close navigation"
          onClick={() => setMobile(false)}
        />
      )}

      {/* MAIN CONTAINER */}
      <div className="cp-main">
        {/* TOPBAR */}
        <header className="cp-topbar">
          <div>
            <button
              className="cp-icon-button cp-desktop-toggle"
              aria-label="Toggle sidebar"
              onClick={() => setCollapsed(!collapsed)}
            >
              {collapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}
            </button>
            <button
              className="cp-icon-button cp-mobile-toggle"
              aria-label="Open navigation"
              onClick={() => {
                setCollapsed(false);
                setMobile(true);
              }}
            >
              <Menu size={18} />
            </button>
            <span className="cp-breadcrumb">
              Workspace <ChevronRight size={13} /> <strong>{section}</strong>
            </span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {/* Live Backend Connection Badge */}
            <span
              className="cp-demo"
              style={{
                color: "#16a34a",
                borderColor: "#bbf7d0",
                background: "#f0fdf4",
                fontWeight: 600,
              }}
            >
              <span style={{ background: "#22c55e" }} /> Live Backend (8000)
            </span>

            {/* Resume Selector Dropdown */}
            {resumes.length > 0 ? (
              <select
                value={selectedResumeId}
                onChange={(e) => {
                  const id = Number(e.target.value);
                  setSelectedResumeId(id);
                  const found = resumes.find((r) => r.id === id);
                  if (found) {
                    const parsed = extractCandidateName(found);
                    if (parsed) setName(parsed);
                  }
                  setToast(`Switched active resume.`);
                }}
                style={{
                  padding: "6px 10px",
                  borderRadius: 6,
                  border: "1px solid #d1d5db",
                  background: "#ffffff",
                  fontSize: "0.8rem",
                  color: "#374151",
                  cursor: "pointer",
                  maxWidth: 180,
                  textOverflow: "ellipsis",
                }}
              >
                {resumes.map((r) => (
                  <option key={r.id} value={r.id}>
                    📄 {r.name}
                  </option>
                ))}
              </select>
            ) : (
              <button
                type="button"
                onClick={() => setShowUploadModal(true)}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "6px 12px",
                  borderRadius: 6,
                  border: "1px solid #ded8e8",
                  background: "#ffffff",
                  fontSize: "0.8rem",
                  color: "#6947ae",
                  fontWeight: 500,
                  cursor: "pointer",
                }}
              >
                <Upload size={14} /> Upload Resume
              </button>
            )}

            {/* ATS Score Checker Button (subtle sideline) */}
            <button
              type="button"
              onClick={() => setShowAtsScanner(true)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 5,
                background: "#ffffff",
                border: "1px solid #ded8e8",
                color: "#6b6377",
                fontWeight: 500,
                padding: "6px 12px",
                borderRadius: 6,
                fontSize: "0.8rem",
                cursor: "pointer",
              }}
            >
              <BarChart3 size={14} color="#6947ae" />
              <span>ATS Score</span>
            </button>

            <button
              className="cp-icon-button"
              aria-label="Open command palette"
              onClick={() => {
                setQuery("");
                setCommand(true);
              }}
            >
              <Command size={16} />
            </button>
          </div>
        </header>

        {/* CONTENT */}
        <main id="main-content" className="cp-content">
          <AnimatePresence mode="wait">
            <motion.div
              key={section}
              initial={{ opacity: 0, y: reduce ? 0 : 7 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.16 }}
            >
              {/* PAGE HEADING WITH CONTEXT HINT */}
              <div className="cp-page-heading">
                <div>
                  <div className="cp-eyebrow">
                    {section === "Dashboard"
                      ? "YOUR CAREER, GROUNDED IN REALITY"
                      : `CAREERPROOF WORKFLOW · ${section.toUpperCase()}`}
                  </div>
                  <h1>
                    {section === "Dashboard"
                      ? resumes.length > 0
                        ? `Good morning, ${name.split(" ")[0]}.`
                        : "Welcome to CareerProof"
                      : section}
                  </h1>
                  <p>{subtitles[section]}</p>
                </div>

                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  {section === "Dashboard" && resumes.length > 0 && (
                    <span style={{ fontSize: "12px", color: "#6b6377", display: "inline-flex", alignItems: "center", gap: 6 }}>
                      <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#6947ae", display: "inline-block" }} />
                      {resumes.length} saved resume{resumes.length > 1 ? "s" : ""}
                    </span>
                  )}
                  {section === "Evidence Vault" && (
                    <Button variant="default" onClick={() => setShowUploadModal(true)}>
                      <Upload size={16} /> Add resume or evidence
                    </Button>
                  )}
                  {section === "Job Analyzer" && (
                    <Button variant="default" onClick={() => setShowAddJobModal(true)}>
                      <Plus size={16} /> Add target role
                    </Button>
                  )}
                  {section === "Resume Studio" && (
                    <Button
                      variant="default"
                      onClick={() => setShowExportModal(true)}
                      disabled={!activeDraftId && bullets.length === 0}
                    >
                      <Download size={16} /> Export PDF / LaTeX
                    </Button>
                  )}
                  {section === "Applications" && (
                    <Button
                      variant="secondary"
                      onClick={() => void handleToggleClaimHeatmap()}
                    >
                      <Zap size={16} /> {showClaimHeatmap ? "View Kanban" : "View Claim Heatmap"}
                    </Button>
                  )}
                </div>
              </div>

              {!ready ? (
                <div className="cp-skeleton" aria-label="Loading workspace" />
              ) : (
                <>
                  {/* SECTION 1: DASHBOARD */}
                  {section === "Dashboard" && (
                    <>
                      {/* HERO WORKFLOW CARD: CLEAN WHITE AND PURPLE THEME */}
                      <section
                        style={{
                          padding: "32px 36px",
                          marginBottom: "28px",
                          background: "#ffffff",
                          borderRadius: "10px",
                          boxShadow: "0 4px 24px rgba(105, 71, 174, 0.05), 0 1px 3px rgba(32, 27, 49, 0.04)",
                          border: "1px solid #ede8f5",
                        }}
                      >
                        {/* Title matching legacy screenshot */}
                        <h2
                          style={{
                            fontSize: "26px",
                            fontWeight: 600,
                            color: "#201b31",
                            margin: "0 0 24px 0",
                            letterSpacing: "-0.5px",
                          }}
                        >
                          Add resumes
                        </h2>

                        {/* Hidden file input */}
                        <input
                          ref={dashboardFileInputRef}
                          type="file"
                          multiple
                          accept=".pdf,.docx,.txt"
                          style={{ display: "none" }}
                          disabled={uploadBusy}
                          onChange={(e) => void handleDirectFileSelect(e)}
                        />

                        {/* 1. CHOOSE UP TO THREE RESUMES */}
                        <div style={{ marginBottom: "20px" }}>
                          <label
                            style={{
                              display: "block",
                              fontSize: "13px",
                              fontWeight: 600,
                              color: "#3f3850",
                              marginBottom: "8px",
                            }}
                          >
                            Choose up to three resumes
                          </label>

                          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                            <button
                              type="button"
                              onClick={() => dashboardFileInputRef.current?.click()}
                              disabled={uploadBusy}
                              style={{
                                padding: "10px 14px",
                                border: "1px solid #ded8e8",
                                borderRadius: "6px",
                                background: "#ffffff",
                                fontSize: "13px",
                                color: selectedFiles.length > 0 ? "#201b31" : "#746d84",
                                cursor: "pointer",
                                display: "inline-flex",
                                alignItems: "center",
                                gap: 8,
                              }}
                            >
                              <Upload size={14} color="#6947ae" />
                              {selectedFiles.length > 0
                                ? `${selectedFiles.length} file(s) selected`
                                : "Choose Files  no files selected"}
                            </button>

                            <button
                              type="button"
                              disabled={!selectedFiles.length || uploadBusy}
                              onClick={() => void handleUploadSelectedFiles()}
                              style={{
                                padding: "10px 16px",
                                borderRadius: "6px",
                                background: "#6947ae",
                                color: "#ffffff",
                                border: "none",
                                fontSize: "13px",
                                fontWeight: 600,
                                cursor: selectedFiles.length ? "pointer" : "not-allowed",
                                opacity: selectedFiles.length ? 1 : 0.65,
                                display: "inline-flex",
                                alignItems: "center",
                                gap: 6,
                              }}
                            >
                              {uploadBusy ? <RefreshCw size={14} className="spin" /> : null}
                              Add resumes <ArrowRight size={14} />
                            </button>

                            <button
                              type="button"
                              onClick={() => setShowDirectPaste(!showDirectPaste)}
                              style={{
                                padding: "10px 16px",
                                border: "1px solid #ded8e8",
                                borderRadius: "6px",
                                background: showDirectPaste ? "#f0eafa" : "#ffffff",
                                color: showDirectPaste ? "#6947ae" : "#201b31",
                                fontSize: "13px",
                                fontWeight: 500,
                                cursor: "pointer",
                              }}
                            >
                              {showDirectPaste ? "Cancel paste" : "Or paste text directly"}
                            </button>
                          </div>

                          {/* Selected files preview */}
                          {selectedFiles.length > 0 && (
                            <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 6 }}>
                              {selectedFiles.map((f, i) => (
                                <div
                                  key={`${f.name}-${i}`}
                                  style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: 8,
                                    padding: "6px 12px",
                                    background: "#f8f6fc",
                                    borderRadius: 6,
                                    fontSize: "12px",
                                    width: "fit-content",
                                    border: "1px solid #ede8f5",
                                  }}
                                >
                                  <FileText size={14} color="#6947ae" />
                                  <span style={{ fontWeight: 500, color: "#201b31" }}>{f.name}</span>
                                  <span style={{ color: "#746d84" }}>({Math.round(f.size / 1024)} KB)</span>
                                  <button
                                    type="button"
                                    onClick={() => setSelectedFiles(selectedFiles.filter((_, j) => i !== j))}
                                    style={{ background: "none", border: "none", cursor: "pointer", color: "#958fa0", padding: 2 }}
                                  >
                                    <X size={13} />
                                  </button>
                                </div>
                              ))}
                            </div>
                          )}

                          {/* Inline Paste Text Box */}
                          {showDirectPaste && (
                            <div
                              style={{
                                marginTop: 12,
                                padding: "14px 16px",
                                border: "1px solid #ded8e8",
                                borderRadius: 6,
                                background: "#faf8fd",
                              }}
                            >
                              <div style={{ fontWeight: 600, fontSize: "13px", color: "#201b31", marginBottom: 4 }}>
                                Paste Resume Text
                              </div>
                              <p style={{ fontSize: "12px", color: "#6b6377", margin: "0 0 8px" }}>
                                Ideal for scanned documents, OCR fallbacks, or plain text resumes.
                              </p>
                              <input
                                style={{
                                  width: "100%",
                                  marginBottom: 8,
                                  padding: "9px 12px",
                                  fontSize: "13px",
                                  border: "1px solid #ded8e8",
                                  borderRadius: 6,
                                  background: "#ffffff",
                                  color: "#201b31",
                                }}
                                value={directPasteName}
                                placeholder="Resume name (e.g. My Resume.txt)"
                                onChange={(e) => setDirectPasteName(e.target.value)}
                              />
                              <textarea
                                style={{
                                  width: "100%",
                                  height: 120,
                                  fontFamily: "monospace",
                                  fontSize: "12px",
                                  padding: "9px 12px",
                                  border: "1px solid #ded8e8",
                                  borderRadius: 6,
                                  background: "#ffffff",
                                  color: "#201b31",
                                  resize: "vertical",
                                }}
                                value={directPasteText}
                                placeholder="Paste full resume text here..."
                                onChange={(e) => setDirectPasteText(e.target.value)}
                              />
                              <div style={{ marginTop: 8 }}>
                                <button
                                  type="button"
                                  disabled={!directPasteText.trim() || uploadBusy}
                                  onClick={() => void handleIngestDirectPaste()}
                                  style={{
                                    padding: "8px 16px",
                                    fontSize: "12px",
                                    fontWeight: 600,
                                    background: "#6947ae",
                                    color: "#ffffff",
                                    border: "none",
                                    borderRadius: 6,
                                    cursor: directPasteText.trim() ? "pointer" : "not-allowed",
                                  }}
                                >
                                  {uploadBusy ? <RefreshCw size={13} className="spin" /> : "Ingest Pasted Text"}
                                </button>
                              </div>
                            </div>
                          )}
                        </div>

                        {/* Divider */}
                        <div style={{ height: 1, background: "#ede8f5", margin: "24px 0" }} />

                        {/* 2. CHOOSE EXISTING SERVER SOURCES (1-3) */}
                        <div style={{ marginBottom: "22px" }}>
                          <label
                            style={{
                              display: "block",
                              fontSize: "13px",
                              fontWeight: 600,
                              color: "#3f3850",
                              marginBottom: "12px",
                            }}
                          >
                            Choose existing server sources (1–3)
                          </label>

                          {resumes.length === 0 ? (
                            <div
                              style={{
                                padding: "14px 16px",
                                background: "#faf8fd",
                                borderRadius: 6,
                                border: "1px dashed #ded8e8",
                                color: "#6b6377",
                                fontSize: "13px",
                              }}
                            >
                              No resumes saved on server yet. Choose a file or paste text above to start.
                            </div>
                          ) : (
                            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                              {resumes.map((r) => {
                                const isSelected = selectedResumeIds.includes(r.id);
                                const isAi = r.parsed_raw?.ai_enhanced;
                                const isLocalReview = r.parsed_raw?.needs_review && !isAi;
                                const extractedText = r.parsed_raw?.raw_source_text || (r.bullets || []).join("\n\n");
                                return (
                                  <div
                                    key={r.id}
                                    style={{
                                      display: "flex",
                                      alignItems: "flex-start",
                                      justifyContent: "space-between",
                                      gap: 12,
                                      padding: "12px 14px",
                                      borderRadius: 6,
                                      border: isSelected ? "1px solid #c9bde0" : "1px solid #ede8f5",
                                      background: isSelected ? "#f8f6fc" : "#ffffff",
                                      transition: "all 0.15s ease",
                                    }}
                                  >
                                    <div style={{ display: "flex", alignItems: "flex-start", gap: 12, flex: 1 }}>
                                      <input
                                        type="checkbox"
                                        checked={isSelected}
                                        disabled={uploadBusy || (!isSelected && selectedResumeIds.length >= 3)}
                                        onChange={(e) => {
                                          if (e.target.checked) {
                                            setSelectedResumeIds((prev) => [...prev, r.id]);
                                            setSelectedResumeId(r.id);
                                          } else {
                                            const next = selectedResumeIds.filter((id) => id !== r.id);
                                            setSelectedResumeIds(next);
                                            if (next.length > 0) setSelectedResumeId(next[0]);
                                          }
                                        }}
                                        style={{
                                          marginTop: 3,
                                          accentColor: "#6947ae",
                                          width: 16,
                                          height: 16,
                                          cursor: "pointer",
                                        }}
                                      />
                                      <div style={{ flex: 1 }}>
                                        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                                          <strong style={{ fontSize: "13px", color: "#201b31" }}>{r.name}</strong>
                                          {isLocalReview && (
                                            <span
                                              style={{
                                                background: "#f4f0fa",
                                                color: "#6b6377",
                                                padding: "2px 7px",
                                                borderRadius: 4,
                                                fontSize: "11px",
                                                fontWeight: 500,
                                              }}
                                            >
                                              Local Draft
                                            </span>
                                          )}
                                          {isAi && (
                                            <span
                                              style={{
                                                background: "#f0eafa",
                                                color: "#6947ae",
                                                padding: "2px 7px",
                                                borderRadius: 4,
                                                fontSize: "11px",
                                                fontWeight: 500,
                                              }}
                                            >
                                              AI Enhanced
                                            </span>
                                          )}
                                          {!isLocalReview && !isAi && (
                                            <span
                                              style={{
                                                background: "#f0eafa",
                                                color: "#6947ae",
                                                padding: "2px 7px",
                                                borderRadius: 4,
                                                fontSize: "11px",
                                                fontWeight: 500,
                                              }}
                                            >
                                              Ready
                                            </span>
                                          )}
                                        </div>
                                        <div style={{ fontSize: "12px", color: "#746d84", marginTop: 2 }}>
                                          {isAi
                                            ? "AI enhanced · ready to review"
                                            : "Local extraction (needs review) · ready"}
                                        </div>
                                        {extractedText && (
                                          <details style={{ marginTop: 5 }}>
                                            <summary
                                              style={{
                                                cursor: "pointer",
                                                color: "#6947ae",
                                                fontSize: "12px",
                                                fontWeight: 600,
                                              }}
                                            >
                                              Read extracted text
                                            </summary>
                                            <pre
                                              style={{
                                                maxHeight: 120,
                                                overflowY: "auto",
                                                background: "#faf8fd",
                                                border: "1px solid #ede8f5",
                                                padding: "8px 10px",
                                                borderRadius: 5,
                                                fontSize: "12px",
                                                lineHeight: 1.6,
                                                whiteSpace: "pre-wrap",
                                                marginTop: 5,
                                                color: "#3f3850",
                                              }}
                                            >
                                              {extractedText}
                                            </pre>
                                          </details>
                                        )}
                                      </div>
                                    </div>

                                    {/* Delete Resume Option */}
                                    <button
                                      type="button"
                                      onClick={() => void handleDeleteResume(r.id)}
                                      title={`Delete ${r.name}`}
                                      style={{
                                        display: "inline-flex",
                                        alignItems: "center",
                                        gap: 4,
                                        padding: "4px 9px",
                                        borderRadius: 5,
                                        border: "1px solid #fecaca",
                                        background: "#fff5f5",
                                        color: "#dc2626",
                                        fontSize: "11px",
                                        fontWeight: 500,
                                        cursor: "pointer",
                                        flexShrink: 0,
                                        marginLeft: 10,
                                      }}
                                    >
                                      <Trash2 size={12} />
                                      Delete
                                    </button>
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>

                        {/* 3. ADD PROJECT NOTES (OPTIONAL) */}
                        <div style={{ marginBottom: "22px" }}>
                          <details>
                            <summary
                              style={{
                                cursor: "pointer",
                                fontWeight: 600,
                                fontSize: "13px",
                                color: "#3f3850",
                              }}
                            >
                              Add project notes (Optional)
                            </summary>
                            <div style={{ marginTop: 8 }}>
                              <p style={{ fontSize: "12px", color: "#6b6377", margin: "0 0 6px" }}>
                                Include the project name, what you personally did, and any results missing from your resumes.
                              </p>
                              <textarea
                                rows={4}
                                maxLength={6000}
                                value={projectNotes}
                                onChange={(e) => setProjectNotes(e.target.value)}
                                placeholder="Add relevant project details here…"
                                style={{
                                  width: "100%",
                                  padding: "10px 12px",
                                  fontSize: "13px",
                                  border: "1px solid #ded8e8",
                                  borderRadius: 6,
                                  background: "#ffffff",
                                  color: "#201b31",
                                  resize: "vertical",
                                }}
                              />
                            </div>
                          </details>
                        </div>

                        {/* 4. TARGET JOB: COMPANY & ROLE */}
                        <div style={{ marginBottom: "16px" }}>
                          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                            <div>
                              <label
                                style={{
                                  display: "block",
                                  fontSize: "13px",
                                  fontWeight: 600,
                                  color: "#3f3850",
                                  marginBottom: 6,
                                }}
                              >
                                Company
                              </label>
                              <input
                                style={{
                                  width: "100%",
                                  padding: "10px 12px",
                                  fontSize: "13px",
                                  border: "1px solid #ded8e8",
                                  borderRadius: 6,
                                  background: "#ffffff",
                                  color: "#201b31",
                                }}
                                value={companyInput}
                                placeholder="e.g. Amgen"
                                onChange={(e) => setCompanyInput(e.target.value)}
                              />
                            </div>
                            <div>
                              <label
                                style={{
                                  display: "block",
                                  fontSize: "13px",
                                  fontWeight: 600,
                                  color: "#3f3850",
                                  marginBottom: 6,
                                }}
                              >
                                Role
                              </label>
                              <input
                                style={{
                                  width: "100%",
                                  padding: "10px 12px",
                                  fontSize: "13px",
                                  border: "1px solid #ded8e8",
                                  borderRadius: 6,
                                  background: "#ffffff",
                                  color: "#201b31",
                                }}
                                value={roleInput}
                                placeholder="e.g. Machine Learning Engineer"
                                onChange={(e) => setRoleInput(e.target.value)}
                              />
                            </div>
                          </div>

                          {/* Subtle quick presets */}
                          <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 10, flexWrap: "wrap" }}>
                            <span style={{ fontSize: "11px", color: "#6b6377" }}>Presets:</span>
                            {displayJobs.map((j) => (
                              <button
                                key={j.id}
                                type="button"
                                onClick={() => {
                                  setCompanyInput(j.company);
                                  setRoleInput(j.role);
                                  setJdInput(j.description || "");
                                  setSelectedJob(j);
                                }}
                                style={{
                                  padding: "3px 9px",
                                  borderRadius: 12,
                                  border: companyInput === j.company ? "1px solid #6947ae" : "1px solid #ede8f5",
                                  background: companyInput === j.company ? "#f0eafa" : "#ffffff",
                                  color: companyInput === j.company ? "#6947ae" : "#6b6377",
                                  fontSize: "11px",
                                  fontWeight: 500,
                                  cursor: "pointer",
                                }}
                              >
                                {j.company} · {j.role}
                              </button>
                            ))}
                            <button
                              type="button"
                              onClick={() => {
                                setCompanyInput("");
                                setRoleInput("");
                                setJdInput("");
                              }}
                              style={{
                                padding: "3px 9px",
                                borderRadius: 12,
                                border: "1px dashed #ded8e8",
                                background: "#ffffff",
                                color: "#6b6377",
                                fontSize: "11px",
                                cursor: "pointer",
                              }}
                            >
                              + Clear
                            </button>
                          </div>
                        </div>

                        {/* 5. JOB DESCRIPTION */}
                        <div style={{ marginBottom: "22px" }}>
                          <label
                            style={{
                              display: "block",
                              fontSize: "13px",
                              fontWeight: 600,
                              color: "#3f3850",
                              marginBottom: 6,
                            }}
                          >
                            Job description
                          </label>
                          <textarea
                            rows={7}
                            style={{
                              width: "100%",
                              padding: "11px 12px",
                              fontSize: "13px",
                              border: "1px solid #ded8e8",
                              borderRadius: 6,
                              background: "#ffffff",
                              color: "#201b31",
                              lineHeight: 1.6,
                              resize: "vertical",
                            }}
                            value={jdInput}
                            placeholder="Paste job description here..."
                            onChange={(e) => setJdInput(e.target.value)}
                          />
                        </div>

                        {/* 6. PRIMARY ACTION: WHITE AND PURPLE CONTINUE BUTTON */}
                        <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap", paddingTop: 8 }}>
                          <button
                            type="button"
                            disabled={
                              isTailoring ||
                              (resumes.length === 0 && selectedFiles.length === 0) ||
                              !companyInput.trim() ||
                              !roleInput.trim() ||
                              !jdInput.trim()
                            }
                            onClick={() => void handleWorkflowTailor()}
                            style={{
                              padding: "12px 28px",
                              fontSize: "13px",
                              fontWeight: 600,
                              background: "#6947ae",
                              color: "#ffffff",
                              borderRadius: 6,
                              border: "none",
                              cursor: isTailoring ? "wait" : "pointer",
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 8,
                              opacity:
                                !isTailoring &&
                                (resumes.length > 0 || selectedFiles.length > 0) &&
                                companyInput.trim() &&
                                roleInput.trim() &&
                                jdInput.trim()
                                  ? 1
                                  : 0.55,
                            }}
                          >
                            {isTailoring ? (
                              <>
                                <RefreshCw size={15} className="spin" /> Tailoring with AI...
                              </>
                            ) : (
                              <>
                                Continue <ArrowRight size={15} />
                              </>
                            )}
                          </button>

                          <button
                            type="button"
                            onClick={() => setShowAtsScanner(true)}
                            style={{
                              background: "none",
                              border: "none",
                              color: "#6947ae",
                              fontSize: "13px",
                              cursor: "pointer",
                              textDecoration: "underline",
                              textUnderlineOffset: 4,
                            }}
                          >
                            Or check ATS score (sideline)
                          </button>
                        </div>
                      </section>

                      {/* DASHBOARD LOWER: Target Roles & Quick Actions */}
                      <div className="cp-dashboard-lower">
                        <section className="cp-panel">
                          <div className="cp-section-head">
                            <h2>
                              Target Roles Catalog <span>{displayJobs.length}</span>
                            </h2>
                            <button
                              className="cp-text-link"
                              onClick={() => go("Job Analyzer")}
                            >
                              View all roles <ArrowUpRight size={14} />
                            </button>
                          </div>
                          {displayJobs.slice(0, 3).map((j) => (
                            <button
                              className="cp-job-row"
                              key={j.id}
                              onClick={() => {
                                setSelectedJob(j);
                                go("Job Analyzer");
                              }}
                            >
                              <span
                                className="cp-company-logo"
                                style={{ color: j.color }}
                              >
                                {j.logo}
                              </span>
                              <span className="cp-grow">
                                <strong>{j.role}</strong>
                                <small>
                                  {j.company} <span>·</span> {j.location}
                                </small>
                              </span>
                              <span className="cp-match">
                                {j.match}%<small>fit</small>
                              </span>
                              <ChevronRight size={16} />
                            </button>
                          ))}
                          <div className="cp-panel-foot">
                            <span className="cp-small">
                              Click any role above to inspect required skills or paste your own job posting.
                            </span>
                          </div>
                        </section>

                        <section className="cp-panel cp-activity">
                          <div className="cp-section-head">
                            <h2>What each tool does</h2>
                            <span className="cp-small">TOOL DIRECTORY</span>
                          </div>
                          {[
                            {
                              title: "ATS Scanner",
                              body: "Instant match score, missing keywords, and tenure length checks.",
                              action: () => setShowAtsScanner(true),
                              icon: BarChart3,
                            },
                            {
                              title: "Hiring Objection Engine",
                              body: "Flags recruiter doubts about scope, titles, and unexpressed tools.",
                              action: () => go("Objection Engine"),
                              icon: ShieldCheck,
                            },
                            {
                              title: "Interview Defense Practice",
                              body: "Practice defending claims with architecture tradeoffs and AI scoring.",
                              action: () => go("Interview Defense"),
                              icon: MessagesSquare,
                            },
                          ].map((a, i) => (
                            <button
                              className="cp-action-row"
                              key={a.title}
                              onClick={a.action}
                            >
                              <span className={`cp-action-icon color-${i}`}>
                                <a.icon size={17} />
                              </span>
                              <span>
                                <strong>{a.title}</strong>
                                <small>{a.body}</small>
                              </span>
                              <ArrowUpRight size={15} />
                            </button>
                          ))}
                        </section>
                      </div>

                      <div className="cp-bottom-note">
                        <ShieldCheck size={14} /> Grounded in evidence. Never invented by AI.
                        <span>Every strong claim starts with real production experience.</span>
                      </div>
                    </>
                  )}

                  {/* SECTION 2: ATS SCANNER (FIRST CLASS VIEW) */}
                  {section === "ATS Scanner" && (
                    <div>
                      {/* Explanatory Help Card */}
                      <div
                        style={{
                          background: "#f8f6fc",
                          border: "1px solid #ede8f5",
                          borderRadius: 8,
                          padding: "12px 16px",
                          marginBottom: 16,
                          display: "flex",
                          alignItems: "center",
                          gap: 12,
                        }}
                      >
                        <Info size={20} color="#6947ae" style={{ flexShrink: 0 }} />
                        <div style={{ fontSize: "0.825rem", color: "#201b31", lineHeight: 1.4 }}>
                          <strong>How this works:</strong> Upload or pick any resume on the left, and choose or paste a Job Description on the right. The scanner parses exact keywords, validates mandatory sections, checks minimum tenure duration (months/years), and gives you actionable fixes.
                        </div>
                      </div>

                      <ATSCheckerModal
                        initialResumeId={selectedResumeId}
                        onSelectDraft={(draftId) => {
                          void loadOptimization(draftId);
                          go("Resume Studio");
                        }}
                        onApplyJobToWorkspace={(comp, rle, jdText) => {
                          setSelectedJob((prev) => ({
                            ...prev,
                            company: comp,
                            role: rle,
                            description: jdText,
                          }));
                          go("Job Analyzer");
                          setToast("Applied job to Job Analyzer!");
                        }}
                      />
                    </div>
                  )}

                  {/* SECTION 3: JOB ANALYZER */}
                  {section === "Job Analyzer" && (
                    <div>
                      <div
                        style={{
                          background: "#f8f6fc",
                          border: "1px solid #ede8f5",
                          borderRadius: 8,
                          padding: "12px 16px",
                          marginBottom: 16,
                          display: "flex",
                          alignItems: "center",
                          gap: 12,
                        }}
                      >
                        <Info size={20} color="#6947ae" style={{ flexShrink: 0 }} />
                        <div style={{ fontSize: "0.825rem", color: "#201b31", lineHeight: 1.4 }}>
                          <strong>How this works:</strong> Select a target role from our database or click <strong>"+ Add Custom JD"</strong> to paste any posting from LinkedIn or company websites. We extract required technologies and check which ones you already have in your resume.
                        </div>
                      </div>

                      <div className="cp-analysis-layout">
                        <div className="cp-job-list">
                          {displayJobs.map((j) => (
                            <button
                              key={j.id}
                              className={`cp-panel cp-job-choice ${selectedJob.id === j.id ? "selected" : ""}`}
                              onClick={() => setSelectedJob(j)}
                            >
                              <span className="cp-company-logo">{j.logo}</span>
                              <strong>{j.company}</strong>
                              <p>{j.role}</p>
                              <Badge tone="violet">{j.match}% target alignment</Badge>
                            </button>
                          ))}
                          <Button
                            variant="secondary"
                            onClick={() => setShowAddJobModal(true)}
                            style={{ width: "100%", justifyContent: "center", marginTop: 8 }}
                          >
                            <Plus size={15} /> + Add Custom JD
                          </Button>
                        </div>

                        <section className="cp-panel cp-job-detail">
                          <div className="cp-panel-top">
                            <span className="cp-label">ROLE BRIEF</span>
                            <Badge tone="green">Selected Role</Badge>
                          </div>
                          <h2>{selectedJob.role}</h2>
                          <p>
                            {selectedJob.company} · {selectedJob.location}
                          </p>
                          <h3>What the role needs</h3>
                          <p style={{ whiteSpace: "pre-line" }}>{selectedJob.description}</p>

                          <h3>Your evidence, mapped</h3>
                          {selectedJob.skills.map((skill) => {
                            const source = evidenceList.find((e) =>
                              e.skills.some((s) => s.toLowerCase() === skill.toLowerCase()) ||
                              e.text.toLowerCase().includes(skill.toLowerCase()),
                            );
                            return (
                              <div className="cp-requirement" key={skill}>
                                <span>
                                  {source ? (
                                    <CheckCircle2 size={17} color="#16a34a" />
                                  ) : (
                                    <Circle size={17} color="#9ca3af" />
                                  )}
                                </span>
                                <div>
                                  <strong>{skill}</strong>
                                  <small>
                                    {source
                                      ? source.title
                                      : "Not explicitly stated in resume · clarify if you have experience"}
                                  </small>
                                </div>
                                {source ? (
                                  <button
                                    className="cp-text-link"
                                    onClick={() => setSelectedEvidence(source)}
                                  >
                                    View source <ArrowUpRight size={13} />
                                  </button>
                                ) : (
                                  <Badge tone="amber">Needs context</Badge>
                                )}
                              </div>
                            );
                          })}

                          <div style={{ display: "flex", gap: 10, marginTop: 20, flexWrap: "wrap" }}>
                            <Button
                              variant="default"
                              disabled={isTailoring}
                              onClick={() => void handleTailorJob(selectedJob)}
                              style={{ background: "#6947ae", color: "#fff", fontWeight: 700, padding: "10px 20px", borderColor: "#58379f" }}
                            >
                              {isTailoring ? (
                                <>
                                  <RefreshCw size={15} className="spin" /> Tailoring with AI...
                                </>
                              ) : (
                                <>
                                  <Sparkles size={16} /> ⚡ Tailor Resume for {selectedJob.company}
                                </>
                              )}
                            </Button>
                            <Button
                              variant="secondary"
                              onClick={() => setShowAtsScanner(true)}
                            >
                              <BarChart3 size={15} /> Check ATS Score (Sideline)
                            </Button>
                            <Button
                              variant="secondary"
                              onClick={() => go("Objection Engine")}
                            >
                              Review Recruiter Objections <ArrowRight size={14} />
                            </Button>
                          </div>
                        </section>
                      </div>
                    </div>
                  )}

                  {/* SECTION 4: RESUME STUDIO */}
                  {section === "Resume Studio" && (
                    <>
                      <div
                        style={{
                          background: "#f0fdf4",
                          border: "1px solid #bbf7d0",
                          borderRadius: 8,
                          padding: "12px 16px",
                          marginBottom: 16,
                          display: "flex",
                          alignItems: "center",
                          gap: 12,
                        }}
                      >
                        <Info size={20} color="#16a34a" style={{ flexShrink: 0 }} />
                        <div style={{ fontSize: "0.825rem", color: "#166534", lineHeight: 1.4 }}>
                          <strong>How this works:</strong> Edit your resume bullet points and toggle which ones to include. When ready, click <strong>"LaTeX / PDF Export"</strong> to compile a clean, executive 1-page PDF using our backend LaTeX engine with strict budget enforcement.
                        </div>
                      </div>

                      <div className="cp-studio-toolbar" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                        <div>
                          <Badge tone="violet">
                            Target Role: {selectedJob.company} · {selectedJob.role}
                          </Badge>
                          <span className="cp-small" style={{ marginLeft: 8, color: "#64748b" }}>
                            {activeDraftId ? `Tailored Draft #${activeDraftId} Active` : "Base resume bullets"}
                          </span>
                        </div>
                        <div style={{ display: "flex", gap: 8 }}>
                          <Button
                            variant="default"
                            disabled={isTailoring}
                            onClick={() => void handleTailorJob(selectedJob)}
                            style={{ background: "#6947ae", color: "#fff", fontWeight: 600, borderColor: "#58379f" }}
                          >
                            {isTailoring ? (
                              <>
                                <RefreshCw size={15} className="spin" /> Tailoring with AI...
                              </>
                            ) : (
                              <>
                                <Sparkles size={15} /> ⚡ {activeDraftId ? `Re-Tailor for ${selectedJob.company}` : `Tailor Resume for ${selectedJob.company}`}
                              </>
                            )}
                          </Button>
                          <Button
                            variant="default"
                            onClick={() => setShowExportModal(true)}
                            style={{ background: "#6947ae", borderColor: "#58379f" }}
                          >
                            <Download size={15} /> Export 1-Page LaTeX PDF
                          </Button>
                        </div>
                      </div>

                      <div className="cp-studio">
                        <section className="cp-panel cp-editor">
                          <div className="cp-section-head">
                            <h2>Tailored Bullets</h2>
                            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                              {activeDraftId && (
                                <Badge tone="violet">⚡ Tailored for {selectedJob.company}</Badge>
                              )}
                              <Badge>
                                {bullets.filter((b) => b.included).length} selected of {bullets.length}
                              </Badge>
                            </div>
                          </div>

                          {bullets.length === 0 ? (
                            <div style={{ padding: 24, textAlign: "center", color: "#64748b" }}>
                              <p>No bullets loaded. Upload a resume or tailor for your target role.</p>
                              <div style={{ display: "flex", justifyContent: "center", gap: 8, marginTop: 12 }}>
                                <Button
                                  variant="secondary"
                                  onClick={() => setShowUploadModal(true)}
                                >
                                  Upload Resume
                                </Button>
                                <Button
                                  variant="default"
                                  disabled={isTailoring}
                                  onClick={() => void handleTailorJob(selectedJob)}
                                  style={{ background: "#6947ae", color: "#fff", borderColor: "#58379f" }}
                                >
                                  {isTailoring ? "Tailoring..." : `⚡ Tailor for ${selectedJob.company}`}
                                </Button>
                              </div>
                            </div>
                          ) : (
                            bullets.map((b) => (
                              <div
                                className={`cp-bullet ${!b.included ? "muted" : ""}`}
                                key={b.id}
                              >
                                <div className="cp-panel-top">
                                  <label style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 600 }}>
                                    <input
                                      type="checkbox"
                                      checked={b.included}
                                      onChange={() =>
                                        setBullets((bs) =>
                                          bs.map((x) =>
                                            x.id === b.id ? { ...x, included: !x.included } : x,
                                          ),
                                        )
                                      }
                                    />
                                    {b.company || "Experience"}
                                  </label>
                                  {b.originalText && b.text !== b.originalText && (
                                    <button
                                      className="cp-icon-button"
                                      title="Revert bullet"
                                      onClick={() =>
                                        setBullets((bs) =>
                                          bs.map((x) =>
                                            x.id === b.id ? { ...x, text: b.originalText! } : x,
                                          ),
                                        )
                                      }
                                    >
                                      <RotateCcw size={14} />
                                    </button>
                                  )}
                                </div>
                                <textarea
                                  aria-label="Edit bullet"
                                  value={b.text}
                                  onChange={(e) =>
                                    setBullets((bs) =>
                                      bs.map((x) =>
                                        x.id === b.id ? { ...x, text: e.target.value } : x,
                                      ),
                                    )
                                  }
                                  rows={3}
                                />
                                {b.originalText && b.text !== b.originalText && (
                                  <small className="cp-edit-note">
                                    Your edit · verify all metrics and claims match source evidence.
                                  </small>
                                )}
                              </div>
                            ))
                          )}
                        </section>

                        <section className="cp-preview">
                          <div className="cp-preview-header">
                            <span>
                              <span className="cp-status-dot" /> LIVE RESUME PREVIEW
                            </span>
                            <span>{name.toUpperCase()}</span>
                          </div>

                          <div className="cp-resume-paper compact">
                            <h2>{name.toUpperCase()}</h2>
                            <p className="cp-resume-contact">
                              Software / ML Engineer
                              <br />
                              Candidate Portfolio · Verified Production Systems
                            </p>
                            <h3>EXPERIENCE & PRODUCTION DELIVERIES</h3>
                            {bullets
                              .filter((b) => b.included)
                              .map((b) => (
                                <div className="cp-resume-entry" key={b.id}>
                                  <h4>{b.company || "Engineering Delivery"}</h4>
                                  <p>• {b.text}</p>
                                </div>
                              ))}
                          </div>
                        </section>
                      </div>
                    </>
                  )}

                  {/* SECTION 5: OBJECTION ENGINE */}
                  {section === "Objection Engine" && (
                    <>
                      <div
                        style={{
                          background: "#fffbeb",
                          border: "1px solid #fde68a",
                          borderRadius: 8,
                          padding: "12px 16px",
                          marginBottom: 16,
                          display: "flex",
                          alignItems: "center",
                          gap: 12,
                        }}
                      >
                        <Info size={20} color="#d97706" style={{ flexShrink: 0 }} />
                        <div style={{ fontSize: "0.825rem", color: "#92400e", lineHeight: 1.4 }}>
                          <strong>How this works:</strong> Simulates hiring decision filters. We look for red flags that recruiters or technical bar-raisers might spot (e.g., missing required tools, senior titles without baseline metrics) and show you how to resolve them honestly.
                        </div>
                      </div>

                      <div className="cp-context-bar">
                        <span className="cp-company-logo">{selectedJob.logo}</span>
                        <div>
                          <strong>{selectedJob.role}</strong>
                          <small>
                            {selectedJob.company} · {objectionReport?.objections?.length || 2} hiring hypotheses
                          </small>
                        </div>
                        <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
                          <span style={{ fontSize: "0.8rem", color: "#6b7280" }}>Mode:</span>
                          <button
                            className={`cp-button ${candidateMode === "advance" ? "cp-button-primary" : "cp-button-secondary"}`}
                            style={{ padding: "4px 10px", fontSize: "0.75rem" }}
                            onClick={() => {
                              setCandidateMode("advance");
                              if (activeDraftId) void loadOptimization(activeDraftId);
                            }}
                          >
                            CareerProof Advance
                          </button>
                          <button
                            className={`cp-button ${candidateMode === "launch" ? "cp-button-primary" : "cp-button-secondary"}`}
                            style={{ padding: "4px 10px", fontSize: "0.75rem" }}
                            onClick={() => {
                              setCandidateMode("launch");
                              if (activeDraftId) void loadOptimization(activeDraftId);
                            }}
                          >
                            CareerProof Launch
                          </button>
                          <Button
                            variant="ghost"
                            onClick={() => setShowLegacyObjectionsView(!showLegacyObjectionsView)}
                            style={{ fontSize: "0.75rem" }}
                          >
                            {showLegacyObjectionsView ? "Card view" : "Deep matrix view"}
                          </Button>
                        </div>
                      </div>

                      {showLegacyObjectionsView && objectionReport ? (
                        <HiringObjectionView report={objectionReport} />
                      ) : (
                        <div className="cp-objection-grid">
                          {(objectionReport?.objections || [
                            {
                              id: "obj_rec_1",
                              persona: "Recruiter Screen",
                              title: "Stack buzzwords may be unexpressed",
                              severity: "High",
                              confidence: 90,
                              body: "Recruiter scanning for core skills won't see explicit required keywords and may assume zero exposure.",
                              evidence: "Absence of explicit keywords in active resume",
                              action: "Add verified project or clarify exposure",
                            },
                            {
                              id: "obj_tech_1",
                              persona: "Technical Bar-Raiser",
                              title: "Hands-on implementation depth probe",
                              severity: "Medium",
                              confidence: 85,
                              body: "Interviewer will test architecture tradeoffs and failure modes. Ensure claims have concrete scale limits.",
                              evidence: "High-level claims without baseline metrics",
                              action: "Prepare interview defense card",
                            },
                          ]).map((rawO, i) => {
                            const o = rawO as any;
                            const severity = o.confidence === "High" ? "High" : o.severity || "Medium";
                            const confidence = typeof o.confidence === "number" ? o.confidence : 85;
                            const title = o.title || o.hypothesis || "Hiring Objection";
                            const bodyText = o.body || o.hypothesis || "";
                            const trigger = o.jd_trigger || o.evidence || "Evidence trigger";
                            const actionText = o.resolution_action?.action || o.action || "Resolve hesitation";

                            return (
                              <section key={o.id} className="cp-panel cp-objection">
                                <div className={`cp-persona color-${i}`}>
                                  <span>
                                    {i === 0 ? <Search size={20} /> : <Briefcase size={20} />}
                                  </span>
                                  <div>
                                    <h2>{o.persona}</h2>
                                    <small>Hiring Decision Persona</small>
                                  </div>
                                </div>
                                <div className="cp-objection-content">
                                  <div className="cp-panel-top">
                                    <Badge
                                      tone={
                                        savedAnswers[o.id]
                                          ? "green"
                                          : severity === "High"
                                            ? "amber"
                                            : "violet"
                                      }
                                    >
                                      {savedAnswers[o.id] ? "Context added" : `${severity} priority`}
                                    </Badge>
                                    <span className="cp-small">{confidence}% confidence</span>
                                  </div>
                                  <button
                                    className="cp-expand"
                                    aria-expanded={expanded.includes(o.id)}
                                    onClick={() =>
                                      setExpanded((v) =>
                                        v.includes(o.id)
                                          ? v.filter((id) => id !== o.id)
                                          : [...v, o.id],
                                      )
                                    }
                                  >
                                    <h3>{title}</h3>
                                    <ChevronDown size={17} />
                                  </button>
                                  <p>{bodyText}</p>
                                  <div className="cp-confidence">
                                    <span style={{ width: `${confidence}%` }} />
                                  </div>
                                  {expanded.includes(o.id) && (
                                    <div className="cp-objection-extra">
                                      <span className="cp-label">SUPPORTING TRIGGER</span>
                                      <p>{trigger}</p>
                                      <p style={{ marginTop: 6, color: "#6947ae", fontWeight: 600 }}>
                                        ➜ {actionText}
                                      </p>
                                    </div>
                                  )}
                                  <Button
                                    onClick={() => go("Interview Defense")}
                                  >
                                    {savedAnswers[o.id] ? "Review context" : "Prepare interview defense"}
                                    <ArrowRight size={14} />
                                  </Button>
                                </div>
                              </section>
                            );
                          })}
                        </div>
                      )}

                      <div className="cp-info">
                        <ShieldCheck size={18} />
                        <span>
                          Pre-empting objections protects your interview conversion. Never fabricate experience; clarify existing work with truth boundaries.
                        </span>
                      </div>
                    </>
                  )}

                  {/* SECTION 6: INTERVIEW DEFENSE */}
                  {section === "Interview Defense" && (
                    <div className="cp-defense">
                      <div
                        style={{
                          background: "#f5f3ff",
                          border: "1px solid #ddd6fe",
                          borderRadius: 8,
                          padding: "12px 16px",
                          marginBottom: 16,
                          display: "flex",
                          alignItems: "center",
                          gap: 12,
                        }}
                      >
                        <Info size={20} color="#7c3aed" style={{ flexShrink: 0 }} />
                        <div style={{ fontSize: "0.825rem", color: "#5b21b6", lineHeight: 1.4 }}>
                          <strong>How this works:</strong> Flip these cards to see what deep technical questions interviewers will ask about your resume claims. Review your <strong>"Truth Boundary"</strong> (what not to overreach on) and use the interactive box below to test your explanation with AI feedback.
                        </div>
                      </div>

                      <div className="cp-defense-toolbar">
                        <Badge tone="violet">
                          {selectedJob.company} · Claim Defense Cards
                        </Badge>
                        <div style={{ marginLeft: "auto", display: "flex", gap: 10 }}>
                          <span className="cp-small">
                            CARD {cardIndex + 1} OF {Math.max(defenseCards.length, 1)}
                          </span>
                          <Button
                            variant="ghost"
                            onClick={() => setShowLegacyDefenseView(!showLegacyDefenseView)}
                            style={{ fontSize: "0.75rem" }}
                          >
                            {showLegacyDefenseView ? "Flashcard view" : "Full evaluation view"}
                          </Button>
                        </div>
                      </div>

                      {showLegacyDefenseView && activeDraftId ? (
                        <InterviewDefenseView
                          draftId={activeDraftId}
                          cards={defenseCards}
                          proofSpecs={proofSpecs}
                        />
                      ) : activeDefenseCard ? (
                        <>
                          <motion.button
                            key={`${cardIndex}-${cardFlipped}`}
                            initial={{ opacity: 0.5, rotateX: reduce ? 0 : 8 }}
                            animate={{ opacity: 1, rotateX: 0 }}
                            className={`cp-panel cp-flashcard ${cardFlipped ? "flipped" : ""}`}
                            onClick={() => setCardFlipped(!cardFlipped)}
                          >
                            <span className="cp-label">
                              {cardFlipped
                                ? "TRUTH BOUNDARY & ARCHITECTURE QUESTION"
                                : "RESUME CLAIM & TECHNICAL PROBE"}
                            </span>
                            <span className="cp-flashcard-text">
                              {cardFlipped
                                ? `Do not cross: ${activeDefenseCard.truth_boundary?.do_not_cross_rule || "Stay within verified scope"}`
                                : `“${activeDefenseCard.bullet_text}”`}
                            </span>

                            {cardFlipped ? (
                              <div style={{ textAlign: "left", marginTop: 12 }}>
                                <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "#1e293b" }}>
                                  Architecture tradeoff question:
                                </div>
                                <p style={{ fontSize: "0.825rem", color: "#475569", marginTop: 4 }}>
                                  {activeDefenseCard.architecture_tradeoff_question}
                                </p>
                                <div style={{ marginTop: 10, display: "flex", gap: 6, flexWrap: "wrap" }}>
                                  {activeDefenseCard.recommended_talking_points?.map((tp, idx) => (
                                    <Badge key={idx} tone="green">
                                      {tp.slice(0, 45)}…
                                    </Badge>
                                  ))}
                                </div>
                              </div>
                            ) : (
                              <span className="cp-flashcard-question">
                                Technical Probe: {activeDefenseCard.technical_probe}
                              </span>
                            )}

                            <span className="cp-flip-hint">
                              <RotateCcw size={14} /> Click to{" "}
                              {cardFlipped ? "return to claim" : "reveal truth boundary and tradeoffs"}
                            </span>
                          </motion.button>

                          <div className="cp-defense-controls">
                            <Button
                              aria-label="Previous card"
                              onClick={() => {
                                setCardIndex((c) => (c + defenseCards.length - 1) % defenseCards.length);
                                setCardFlipped(false);
                                setDefenseFeedback(null);
                              }}
                            >
                              <ArrowLeft size={17} />
                            </Button>
                            <div>
                              {defenseCards.map((c, i) => (
                                <button
                                  key={c.id}
                                  className={cardIndex === i ? "active" : ""}
                                  onClick={() => {
                                    setCardIndex(i);
                                    setCardFlipped(false);
                                    setDefenseFeedback(null);
                                  }}
                                />
                              ))}
                            </div>
                            <Button
                              aria-label="Next card"
                              onClick={() => {
                                setCardIndex((c) => (c + 1) % defenseCards.length);
                                setCardFlipped(false);
                                setDefenseFeedback(null);
                              }}
                            >
                              <ArrowRight size={17} />
                            </Button>
                          </div>

                          {/* Test your defense interactive box */}
                          <div
                            style={{
                              marginTop: 16,
                              background: "#ffffff",
                              borderRadius: 10,
                              padding: 16,
                              border: "1px solid #e5e7eb",
                            }}
                          >
                            <div style={{ fontWeight: 600, fontSize: "0.9rem", color: "#111827" }}>
                              Test Your Answer Against AI Evaluator
                            </div>
                            <p style={{ fontSize: "0.8rem", color: "#6b7280", margin: "4px 0 10px" }}>
                              Type how you would answer the interviewer's technical probe. The AI will evaluate truth boundaries, overreach, and depth.
                            </p>
                            <textarea
                              value={defenseAnswer}
                              onChange={(e) => setDefenseAnswer(e.target.value)}
                              placeholder="Explain your approach, metrics, baseline, and team boundary..."
                              rows={3}
                              style={{ width: "100%", padding: 10, borderRadius: 6, border: "1px solid #d1d5db" }}
                            />
                            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8 }}>
                              <Button
                                variant="default"
                                disabled={!defenseAnswer.trim() || defenseEvaluating}
                                onClick={() => handleTestDefense(activeDefenseCard.id)}
                              >
                                {defenseEvaluating ? (
                                  <>
                                    <RefreshCw size={14} className="spin" /> Evaluating...
                                  </>
                                ) : (
                                  <>
                                    <Send size={14} /> Submit & Check Defense
                                  </>
                                )}
                              </Button>
                            </div>

                            {defenseFeedback && (
                              <div
                                style={{
                                  marginTop: 12,
                                  padding: 12,
                                  borderRadius: 8,
                                  background:
                                    defenseFeedback.status === "solid_defense"
                                      ? "#f0fdf4"
                                      : "#fffbeb",
                                  border: `1px solid ${
                                    defenseFeedback.status === "solid_defense"
                                      ? "#bbf7d0"
                                      : "#fde68a"
                                  }`,
                                }}
                              >
                                <div style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 700 }}>
                                  <Badge
                                    tone={
                                      defenseFeedback.status === "solid_defense"
                                        ? "green"
                                        : "amber"
                                    }
                                  >
                                    {defenseFeedback.status}
                                  </Badge>
                                  <span>Score: {defenseFeedback.score}/100</span>
                                </div>
                                <p style={{ fontSize: "0.85rem", marginTop: 6, color: "#1f2937" }}>
                                  {defenseFeedback.feedback}
                                </p>
                              </div>
                            )}
                          </div>
                        </>
                      ) : (
                        <div style={{ textAlign: "center", padding: 30, background: "#ffffff", borderRadius: 10 }}>
                          <p>No defense cards found for active draft. Upload a resume or select a target role to generate defense cards.</p>
                        </div>
                      )}
                    </div>
                  )}

                  {/* SECTION 7: EVIDENCE VAULT */}
                  {section === "Evidence Vault" && (
                    <>
                      <div
                        style={{
                          background: "#f8f6fc",
                          border: "1px solid #ede8f5",
                          borderRadius: 8,
                          padding: "12px 16px",
                          marginBottom: 16,
                          display: "flex",
                          alignItems: "center",
                          gap: 12,
                        }}
                      >
                        <Info size={20} color="#6947ae" style={{ flexShrink: 0 }} />
                        <div style={{ fontSize: "0.825rem", color: "#201b31", lineHeight: 1.4 }}>
                          <strong>How this works:</strong> This is your repository of verified achievements, projects, and technologies extracted from your resumes. Every claim is anchored to source documents so your applications remain strictly factual.
                        </div>
                      </div>

                      <div className="cp-toolbar">
                        <label className="cp-search-field">
                          <Search size={16} />
                          <input
                            aria-label="Search evidence"
                            placeholder="Search achievements, skills, or companies…"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                          />
                        </label>
                        <select
                          aria-label="Filter evidence"
                          value={filter}
                          onChange={(e) => setFilter(e.target.value)}
                        >
                          {[
                            "All evidence",
                            "Experience",
                            "Project",
                            "Verified",
                            "Needs context",
                          ].map((f) => (
                            <option key={f}>{f}</option>
                          ))}
                        </select>
                        <span className="cp-small">{filteredEvidence.length} records</span>
                      </div>

                      <div className="cp-evidence-grid">
                        {filteredEvidence.map((e) => (
                          <button
                            className="cp-panel cp-evidence-card"
                            key={e.id}
                            onClick={() => setSelectedEvidence(e)}
                          >
                            <div className="cp-panel-top">
                              <span className="cp-tile-icon">
                                <Layers size={19} />
                              </span>
                              <Badge tone={e.status === "Verified" ? "green" : "amber"}>
                                {e.status === "Verified" ? (
                                  <CheckCircle2 size={12} />
                                ) : (
                                  <Circle size={12} />
                                )}{" "}
                                {e.status}
                              </Badge>
                            </div>
                            <small>{e.organization}</small>
                            <h2>{e.title}</h2>
                            <p>{e.text}</p>
                            <div className="cp-tags">
                              {e.skills.slice(0, 4).map((s) => (
                                <Badge key={s}>{s}</Badge>
                              ))}
                            </div>
                            <div className="cp-evidence-source">
                              <Link2 size={13} />
                              {e.source}
                              <ArrowUpRight size={14} />
                            </div>
                          </button>
                        ))}
                      </div>

                      {!filteredEvidence.length && (
                        <div
                          style={{
                            textAlign: "center",
                            padding: "40px 20px",
                            background: "#ffffff",
                            borderRadius: 10,
                            border: "1px solid #e5e7eb",
                          }}
                        >
                          <h3>No evidence records found</h3>
                          <p style={{ color: "#6b7280", marginTop: 4 }}>
                            Upload your resume to automatically extract verified achievements.
                          </p>
                          <Button
                            variant="default"
                            onClick={() => setShowUploadModal(true)}
                            style={{ marginTop: 12, background: "#6947ae", borderColor: "#58379f" }}
                          >
                            <Upload size={14} /> Upload Resume
                          </Button>
                        </div>
                      )}

                      <div className="cp-info">
                        <ShieldCheck size={17} />
                        <span>
                          Every claim is traceable to source files or candidate discovery. Click any card to inspect provenance.
                        </span>
                      </div>
                    </>
                  )}

                  {/* SECTION 8: GAP RESOLVER */}
                  {section === "Gap Resolver" && (
                    <div className="cp-gap-layout">
                      <section>
                        <div
                          style={{
                            background: "#eff6ff",
                            border: "1px solid #bfdbfe",
                            borderRadius: 8,
                            padding: "12px 16px",
                            marginBottom: 16,
                          }}
                        >
                          <p style={{ fontSize: "0.825rem", color: "#1e40af", margin: 0 }}>
                            <strong>Targeted Clarifications:</strong> Answer these guided prompts to add verified context to your work. Only confirmed details will be saved to your evidence.
                          </p>
                        </div>

                        <div className="cp-progress-label">
                          <span>
                            {Object.keys(savedAnswers).length} of{" "}
                            {Math.max(objectionReport?.objections?.length || 2, 2)} questions answered
                          </span>
                          <strong>
                            {Math.round(
                              (Object.keys(savedAnswers).length /
                                Math.max(objectionReport?.objections?.length || 2, 2)) *
                                100,
                            )}
                            %
                          </strong>
                        </div>
                        <div className="cp-progress">
                          <span
                            style={{
                              width: `${
                                (Object.keys(savedAnswers).length /
                                  Math.max(objectionReport?.objections?.length || 2, 2)) *
                                100
                              }%`,
                            }}
                          />
                        </div>

                        {(objectionReport?.objections || [
                          {
                            id: "q1",
                            persona: "Technical Bar-Raiser",
                            question: "For your API or backend systems, what baseline latency did you measure and what failure modes did you handle?",
                            help: "Add operational context to prove production ownership without overreaching.",
                          },
                          {
                            id: "q2",
                            persona: "Hiring Manager",
                            question: "Which technical decisions were your individual responsibility vs decided by team leads?",
                            help: "Clarify individual ownership to defend your experience level.",
                          },
                        ]).map((o: any, i: number) => (
                          <article className="cp-panel cp-question" key={o.id}>
                            <div className="cp-panel-top">
                              <span className="cp-label">
                                {savedAnswers[o.id] ? (
                                  <CheckCheck size={15} />
                                ) : (
                                  <span>0{i + 1}</span>
                                )}{" "}
                                {o.persona.toUpperCase()}
                              </span>
                              <Badge tone={savedAnswers[o.id] ? "green" : "neutral"}>
                                {savedAnswers[o.id] ? "Answer saved" : "Targeted question"}
                              </Badge>
                            </div>
                            <h2>{o.question || o.hypothesis}</h2>
                            <p className="cp-why">
                              <Sparkles size={15} />
                              {o.help || "Clarifies technical scope with truth boundaries."}
                            </p>
                            <textarea
                              aria-label={o.question || o.hypothesis}
                              value={answers[o.id] || ""}
                              onChange={(e) =>
                                setAnswers((a) => ({ ...a, [o.id]: e.target.value }))
                              }
                              placeholder="Describe what you actually did. Include metrics, baseline, and constraints you personally handled..."
                              rows={4}
                            />
                            <div className="cp-question-footer">
                              <span className="cp-small">
                                Only confirmed facts belong in your resume.
                              </span>
                              <Button
                                variant="default"
                                disabled={!answers[o.id]?.trim()}
                                onClick={() => {
                                  setSavedAnswers((s) => ({
                                    ...s,
                                    [o.id]: answers[o.id].trim(),
                                  }));
                                  setToast("Answer saved to evidence anchor.");
                                }}
                              >
                                Save answer <Check size={14} />
                              </Button>
                            </div>
                          </article>
                        ))}
                      </section>

                      <aside className="cp-panel cp-gap-aside">
                        <span className="cp-tile-icon">
                          <GitBranch size={22} />
                        </span>
                        <h2>Proof-Building Guidance</h2>
                        <p>
                          Do not inflate your resume with buzzwords you cannot defend in a technical screen.
                        </p>
                        {proofSpecs.length > 0 ? (
                          proofSpecs.slice(0, 2).map((p, idx) => (
                            <div key={idx} style={{ marginTop: 12 }}>
                              <Badge tone="violet">{p.proof_tier} tier</Badge>
                              <h3 style={{ marginTop: 4 }}>{p.title}</h3>
                              <p style={{ fontSize: "0.825rem", color: "#6b7280" }}>
                                {p.problem_statement}
                              </p>
                            </div>
                          ))
                        ) : (
                          <>
                            <h3>Transferable skills</h3>
                            <p>
                              If you lack hands-on experience in a stack requirement, build an open-source proof artifact before claiming it on your CV.
                            </p>
                          </>
                        )}
                        <hr />
                        <span className="cp-small">
                          Anchored to candidate evidence: {activeResumeObj?.name || "Uploaded Resume"}
                        </span>
                      </aside>
                    </div>
                  )}

                  {/* SECTION 9: APPLICATIONS */}
                  {section === "Applications" && (
                    <>
                      <div
                        style={{
                          background: "#f8f6fc",
                          border: "1px solid #ede8f5",
                          borderRadius: 8,
                          padding: "12px 16px",
                          marginBottom: 16,
                          display: "flex",
                          alignItems: "center",
                          gap: 12,
                        }}
                      >
                        <Info size={20} color="#6947ae" style={{ flexShrink: 0 }} />
                        <div style={{ fontSize: "0.825rem", color: "#201b31", lineHeight: 1.4 }}>
                          <strong>How this works:</strong> Drag and drop cards across columns to track application progress. Click <strong>"View Claim Heatmap"</strong> to see which resume bullets correlate with interview callbacks.
                        </div>
                      </div>

                      {showClaimHeatmap ? (
                        claimHeatmap ? (
                          <ClaimHeatmapView report={claimHeatmap} />
                        ) : (
                          <div style={{ padding: 40, textAlign: "center", background: "#ffffff", borderRadius: 10 }}>
                            <RefreshCw size={24} className="spin" style={{ margin: "0 auto 8px", color: "#6947ae" }} />
                            <p style={{ color: "#6b6377" }}>Loading application claim heatmap analytics...</p>
                          </div>
                        )
                      ) : (
                        <>
                          <div className="cp-toolbar">
                            <label className="cp-search-field">
                              <Search size={16} />
                              <input
                                aria-label="Search applications"
                                placeholder="Find a company or role…"
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                              />
                            </label>
                            <span className="cp-small">
                              {applications.length} opportunities · drag cards to move
                            </span>
                          </div>

                          <div className="cp-kanban">
                            {stages.map((stage, i) => (
                              <section
                                key={stage}
                                className="cp-kanban-column"
                                onDragOver={(e) => {
                                  e.preventDefault();
                                  e.dataTransfer.dropEffect = "move";
                                }}
                                onDrop={(e) => {
                                  e.preventDefault();
                                  const id = e.dataTransfer.getData("text/plain");
                                  if (applications.some((a) => a.id === id)) move(id, stage);
                                }}
                              >
                                <div className="cp-kanban-heading">
                                  <span className={`cp-stage-dot stage-${i}`} />
                                  <h2>{stage}</h2>
                                  <span>
                                    {applications.filter((a) => a.stage === stage).length}
                                  </span>
                                </div>
                                {applications
                                  .filter(
                                    (a) =>
                                      a.stage === stage &&
                                      `${a.company} ${a.role}`
                                        .toLowerCase()
                                        .includes(query.toLowerCase()),
                                  )
                                  .map((a) => (
                                    <article
                                      className="cp-panel cp-application"
                                      key={a.id}
                                      draggable
                                      onDragStart={(e) => e.dataTransfer.setData("text/plain", a.id)}
                                    >
                                      <div className="cp-panel-top">
                                        <span className="cp-company-logo">
                                          {a.company.slice(0, 1)}
                                        </span>
                                        <GripVertical size={16} />
                                      </div>
                                      <h3>{a.company}</h3>
                                      <p>{a.role}</p>
                                      <div className="cp-application-footer">
                                        <small>{a.date}</small>
                                        <select
                                          aria-label={`Stage for ${a.company}`}
                                          value={a.stage}
                                          onChange={(e) => move(a.id, e.target.value)}
                                        >
                                          {stages.map((s) => (
                                            <option key={s}>{s}</option>
                                          ))}
                                        </select>
                                      </div>
                                    </article>
                                  ))}
                              </section>
                            ))}
                          </div>
                        </>
                      )}
                    </>
                  )}

                  {/* SECTION 10: SETTINGS */}
                  {section === "Settings" && (
                    <div className="cp-panel cp-settings">
                      <h2>Connected Workspace Settings</h2>
                      <p>Backend API synchronization, system capabilities, and user preferences.</p>

                      <div className="cp-setting-row">
                        <div>
                          <strong>Candidate Name</strong>
                          <p>Extracted from your resume or manually set.</p>
                        </div>
                        <input
                          value={name}
                          onChange={(e) => setName(e.target.value)}
                          maxLength={50}
                          style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #d1d5db" }}
                        />
                      </div>

                      <div className="cp-setting-row">
                        <div>
                          <strong>Backend Status</strong>
                          <p>Connected to FastAPI server at http://localhost:8000</p>
                        </div>
                        <Badge tone="green">Online ✓</Badge>
                      </div>

                      <div className="cp-setting-row">
                        <div>
                          <strong>Active User ID</strong>
                          <p>Default authentication header: X-User-Id</p>
                        </div>
                        <code style={{ background: "#f3f4f6", padding: "4px 8px", borderRadius: 4 }}>
                          user_test
                        </code>
                      </div>

                      <div className="cp-setting-row">
                        <div>
                          <strong>System Capabilities</strong>
                          <p>Local OCR, structured parsing, LaTeX compiler, objection engine.</p>
                        </div>
                        <div style={{ display: "flex", gap: 6 }}>
                          <Badge tone="violet">LaTeX Engine</Badge>
                          <Badge tone="green">FastAPI Live</Badge>
                        </div>
                      </div>

                      <div className="cp-info">
                        <ShieldCheck size={17} />
                        <span>
                          All your uploads and draft optimizations stay private and local to your system.
                        </span>
                      </div>
                    </div>
                  )}
                </>
              )}
            </motion.div>
          </AnimatePresence>
        </main>

        {/* FOOTER */}
        <footer className="cp-footer">
          <span>
            <span className="cp-status-dot" /> Connected to http://localhost:8000 · User: user_test
          </span>
          <button
            onClick={() => {
              setQuery("");
              setCommand(true);
            }}
          >
            Quick navigation <kbd>⌘ K</kbd>
          </button>
        </footer>
      </div>

      {/* MODAL 1: COMMAND PALETTE */}
      <Modal
        open={command}
        onOpenChange={setCommand}
        title="Go anywhere"
        description="Jump to any section in your workspace."
      >
        <label className="cp-command-search">
          <Search size={19} />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search workspace…"
            aria-label="Search workspace"
            onKeyDown={(e) => {
              if (e.key === "Enter" && matches[0]) go(matches[0]);
            }}
          />
        </label>
        <div className="cp-command-results">
          {matches.map((n) => (
            <button key={n} onClick={() => go(n)}>
              <span>{n}</span>
              <ArrowRight size={15} />
            </button>
          ))}
          {!matches.length && <div className="cp-command-empty">No matching pages</div>}
        </div>
      </Modal>

      {/* MODAL 2: EVIDENCE INSPECTOR */}
      <Modal
        open={!!selectedEvidence}
        onOpenChange={(v) => !v && setSelectedEvidence(null)}
        title={selectedEvidence?.title || "Evidence detail"}
        description={selectedEvidence?.organization}
        drawer
      >
        {selectedEvidence && (
          <div className="cp-drawer-body">
            <div className="cp-panel-top">
              <span className="cp-label">CONFIRMED TEXT</span>
              <Badge tone={selectedEvidence.status === "Verified" ? "green" : "amber"}>
                {selectedEvidence.status}
              </Badge>
            </div>
            <p className="cp-drawer-claim">“{selectedEvidence.text}”</p>
            <div className="cp-panel-top">
              <span className="cp-label">EXTRACTED SKILLS</span>
            </div>
            <div className="cp-tags">
              {selectedEvidence.skills.map((s) => (
                <Badge key={s}>{s}</Badge>
              ))}
            </div>
            <div className="cp-panel-top" style={{ marginTop: 16 }}>
              <span className="cp-label">DOCUMENT SOURCE</span>
            </div>
            <p className="cp-drawer-source">
              <Link2 size={13} /> {selectedEvidence.source}
            </p>
          </div>
        )}
      </Modal>

      {/* MODAL 3: UPLOAD RESUME MODAL */}
      <Modal
        open={showUploadModal}
        onOpenChange={setShowUploadModal}
        title="Upload Resume File"
        description="Choose a PDF, DOCX, or TXT file to extract your verified bullet points."
      >
        <div style={{ padding: "10px 0" }}>
          <label
            style={{
              display: "block",
              border: "2px dashed #cbd5e1",
              borderRadius: 8,
              padding: 24,
              textAlign: "center",
              cursor: "pointer",
              background: "#f8fafc",
            }}
          >
            <Upload size={28} style={{ margin: "0 auto 8px", color: "#6947ae" }} />
            <span style={{ fontWeight: 600, color: "#1e293b", display: "block" }}>
              Choose resume files (PDF, DOCX, TXT)
            </span>
            <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>Up to 10 MB each</span>
            <input
              type="file"
              multiple
              accept=".pdf,.docx,.txt"
              style={{ display: "none" }}
              onChange={(e) => {
                const incoming = Array.from(e.target.files || []);
                const issue = validateFiles(incoming, uploadFiles.length);
                if (issue) setToast(issue);
                else setUploadFiles((prev) => [...prev, ...incoming]);
                e.target.value = "";
              }}
            />
          </label>

          {uploadFiles.map((f, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "8px 12px",
                background: "#ffffff",
                border: "1px solid #e2e8f0",
                borderRadius: 6,
                marginTop: 8,
              }}
            >
              <span>{f.name}</span>
              <button
                onClick={() => setUploadFiles(uploadFiles.filter((_, idx) => idx !== i))}
                style={{ border: "none", background: "transparent", cursor: "pointer" }}
              >
                <X size={16} />
              </button>
            </div>
          ))}

          <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
            <Button
              variant="default"
              disabled={!uploadFiles.length || uploadBusy}
              onClick={handleUploadFiles}
              style={{ flex: 1, justifyContent: "center", background: "#6947ae", borderColor: "#58379f" }}
            >
              {uploadBusy ? (
                <>
                  <RefreshCw size={15} className="spin" /> Reading & Parsing...
                </>
              ) : (
                <>Upload & Parse Resume</>
              )}
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                setShowUploadModal(false);
                setShowPasteModal(true);
              }}
            >
              Or Paste Text
            </Button>
          </div>
        </div>
      </Modal>

      {/* MODAL 4: PASTE RESUME TEXT MODAL */}
      <Modal
        open={showPasteModal}
        onOpenChange={setShowPasteModal}
        title="Paste Resume Text"
        description="Direct plain text extraction for fast indexing."
      >
        <div style={{ padding: "10px 0" }}>
          <input
            value={pastedName}
            onChange={(e) => setPastedName(e.target.value)}
            placeholder="Resume title (e.g. My_Resume.txt)"
            style={{
              width: "100%",
              padding: "8px 12px",
              borderRadius: 6,
              border: "1px solid #d1d5db",
              marginBottom: 10,
            }}
          />
          <textarea
            value={pastedText}
            onChange={(e) => setPastedText(e.target.value)}
            placeholder="Paste raw resume text here..."
            rows={8}
            style={{
              width: "100%",
              padding: "10px 12px",
              borderRadius: 6,
              border: "1px solid #d1d5db",
              fontFamily: "monospace",
              fontSize: "0.85rem",
            }}
          />
          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 12 }}>
            <Button
              variant="default"
              disabled={!pastedText.trim() || uploadBusy}
              onClick={handlePasteResume}
              style={{ background: "#6947ae", borderColor: "#58379f" }}
            >
              {uploadBusy ? "Processing..." : "Save & Extract Evidence"}
            </Button>
          </div>
        </div>
      </Modal>

      {/* MODAL 5: ADD TARGET JOB MODAL */}
      <Modal
        open={showAddJobModal}
        onOpenChange={setShowAddJobModal}
        title="Add Target Role"
        description="Add a new job description to analyze requirements and tailor your application."
      >
        <div style={{ padding: "10px 0" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 10 }}>
            <div>
              <label style={{ fontSize: "0.8rem", fontWeight: 600, color: "#374151", display: "block", marginBottom: 4 }}>
                Company Name
              </label>
              <input
                value={newCompany}
                onChange={(e) => setNewCompany(e.target.value)}
                placeholder="e.g. OpenAI"
                style={{ width: "100%", padding: "8px 10px", borderRadius: 6, border: "1px solid #d1d5db" }}
              />
            </div>
            <div>
              <label style={{ fontSize: "0.8rem", fontWeight: 600, color: "#374151", display: "block", marginBottom: 4 }}>
                Target Role
              </label>
              <input
                value={newRole}
                onChange={(e) => setNewRole(e.target.value)}
                placeholder="e.g. Staff MLOps Engineer"
                style={{ width: "100%", padding: "8px 10px", borderRadius: 6, border: "1px solid #d1d5db" }}
              />
            </div>
          </div>
          <label style={{ fontSize: "0.8rem", fontWeight: 600, color: "#374151", display: "block", marginBottom: 4 }}>
            Job Description Text
          </label>
          <textarea
            value={newJdText}
            onChange={(e) => setNewJdText(e.target.value)}
            placeholder="Paste full job description text here..."
            rows={7}
            style={{ width: "100%", padding: "10px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: "0.85rem" }}
          />
          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 12 }}>
            <Button
              variant="default"
              disabled={!newCompany.trim() || !newRole.trim() || !newJdText.trim()}
              onClick={handleAddCustomJob}
              style={{ background: "#6947ae", borderColor: "#58379f" }}
            >
              Save Target Role
            </Button>
          </div>
        </div>
      </Modal>

      {/* MODAL 6: LATEX / PDF EXPORT MODAL */}
      <Modal
        open={showExportModal}
        onOpenChange={setShowExportModal}
        title="Compile LaTeX & Export PDF"
        description="Choose formatting options to generate an employer-ready resume."
      >
        <div style={{ padding: "10px 0" }}>
          {exportError && (
            <div
              style={{
                padding: "10px 12px",
                borderRadius: 6,
                background: "#fef2f2",
                border: "1px solid #fecaca",
                color: "#dc2626",
                fontSize: "0.85rem",
                marginBottom: 12,
              }}
            >
              {exportError}
            </div>
          )}

          <div style={{ marginBottom: 14 }}>
            <label style={{ fontWeight: 600, fontSize: "0.85rem", color: "#374151", display: "block", marginBottom: 6 }}>
              Page Budget Enforcement
            </label>
            <div style={{ display: "flex", gap: 10 }}>
              <label
                style={{
                  flex: 1,
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "10px 12px",
                  borderRadius: 6,
                  border: pagePolicy === "one_page" ? "2px solid #6947ae" : "1px solid #ded8e8",
                  background: pagePolicy === "one_page" ? "#f0eafa" : "#ffffff",
                  cursor: "pointer",
                }}
              >
                <input
                  type="radio"
                  name="pagePolicy"
                  checked={pagePolicy === "one_page"}
                  onChange={() => setPagePolicy("one_page")}
                />
                <span style={{ fontSize: "0.825rem", fontWeight: 600 }}>Compact 1-Page (Recommended)</span>
              </label>

              <label
                style={{
                  flex: 1,
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "10px 12px",
                  borderRadius: 6,
                  border: pagePolicy === "keep" ? "2px solid #6947ae" : "1px solid #ded8e8",
                  background: pagePolicy === "keep" ? "#f0eafa" : "#ffffff",
                  cursor: "pointer",
                }}
              >
                <input
                  type="radio"
                  name="pagePolicy"
                  checked={pagePolicy === "keep"}
                  onChange={() => setPagePolicy("keep")}
                />
                <span style={{ fontSize: "0.825rem", fontWeight: 600 }}>Keep Full Length</span>
              </label>
            </div>
          </div>

          <div style={{ marginBottom: 16 }}>
            <label style={{ fontWeight: 600, fontSize: "0.85rem", color: "#374151", display: "block", marginBottom: 6 }}>
              LaTeX Typography Style
            </label>
            <select
              value={exportTemplate}
              onChange={(e) => setExportTemplate(e.target.value as "default" | "custom")}
              style={{ width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid #d1d5db" }}
            >
              <option value="default">Classic Professional (Engineering Standard)</option>
              <option value="custom">Modern Clean (Sans-Serif)</option>
            </select>
          </div>

          <div style={{ display: "flex", gap: 10 }}>
            <Button
              variant="default"
              disabled={isExportingPdf}
              onClick={handleExportPdf}
              style={{ flex: 1, justifyContent: "center", background: "#6947ae", borderColor: "#58379f" }}
            >
              {isExportingPdf ? (
                <>
                  <RefreshCw size={14} className="spin" /> Compiling PDF...
                </>
              ) : (
                <>
                  <Download size={14} /> Download Compiled PDF
                </>
              )}
            </Button>
            <Button
              variant="secondary"
              disabled={isExportingPdf}
              onClick={handleExportLatex}
            >
              <FileCode size={14} /> Download .tex
            </Button>
          </div>
        </div>
      </Modal>

      {/* MODAL 7: ATS SCORE CHECKER MODAL */}
      {showAtsScanner && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 1000,
            background: "rgba(15, 23, 42, 0.65)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 20,
            overflowY: "auto",
          }}
          onClick={() => setShowAtsScanner(false)}
        >
          <div
            style={{
              width: "100%",
              maxWidth: 960,
              maxHeight: "90vh",
              overflowY: "auto",
              background: "#ffffff",
              borderRadius: 12,
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <ATSCheckerModal
              initialResumeId={selectedResumeId}
              onClose={() => setShowAtsScanner(false)}
              onSelectDraft={(draftId) => {
                void loadOptimization(draftId);
                setShowAtsScanner(false);
                go("Resume Studio");
              }}
              onApplyJobToWorkspace={(comp, rle, jdText) => {
                setSelectedJob((prev) => ({
                  ...prev,
                  company: comp,
                  role: rle,
                  description: jdText,
                }));
                setShowAtsScanner(false);
                go("Job Analyzer");
                setToast("Applied job details to Job Analyzer.");
              }}
            />
          </div>
        </div>
      )}

      {/* TOAST NOTIFICATION */}
      {toast && (
        <div className="cp-toast" role="status">
          <Check size={14} /> {toast}
        </div>
      )}
    </div>
  );
}
