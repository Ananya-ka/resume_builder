"use client";

import { useState, useEffect, useMemo } from "react";
import {
  FileText,
  Search,
  Plus,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  GitBranch,
  ArrowRight,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Layers,
  X,
  Target,
} from "lucide-react";
import { catalogApi, type CatalogSummary } from "@/features/evidence/api";
import { jdApi } from "./api";
import type {
  JobVersion,
  JobRequirement,
  AnalysisRun,
  RequirementCategory,
  MatchStatus,
  CreateJobPayload,
  RequirementMatch,
  MatchedClaimSnapshot,
} from "./types";
import "./jd.css";

const CATEGORY_LABELS: Record<RequirementCategory, string> = {
  mandatory_skill: "Mandatory Skills",
  preferred_skill: "Preferred Skills",
  responsibility: "Core Responsibilities",
  education: "Education Expectations",
  experience: "Experience & Tenure",
  seniority: "Seniority & Leadership",
  domain: "Domain Knowledge",
  eligibility_constraint: "Eligibility Constraints",
};

export default function JDWorkspace() {
  const [jobs, setJobs] = useState<JobVersion[]>([]);
  const [selectedJob, setSelectedJob] = useState<JobVersion | null>(null);
  const [jobVersions, setJobVersions] = useState<JobVersion[]>([]);
  const [catalogs, setCatalogs] = useState<CatalogSummary[]>([]);
  const [selectedCatalogId, setSelectedCatalogId] = useState<number | null>(null);
  const [activeAnalysis, setActiveAnalysis] = useState<AnalysisRun | null>(null);

  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  // Filters
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [showAmbiguousOnly, setShowAmbiguousOnly] = useState(false);

  // New Job Modal
  const [showNewJobModal, setShowNewJobModal] = useState(false);
  const [newRoleTitle, setNewRoleTitle] = useState("");
  const [newCompanyName, setNewCompanyName] = useState("");
  const [newTargetDomain, setNewTargetDomain] = useState("");
  const [newLocation, setNewLocation] = useState("");
  const [newRawText, setNewRawText] = useState("");

  // Expanded requirement card state
  const [expandedReqIds, setExpandedReqIds] = useState<Record<number, boolean>>({});

  useEffect(() => {
    let cancelled = false;
    Promise.all([jdApi.listJobs(), catalogApi.list()])
      .then(async ([jList, cList]) => {
        if (cancelled) return;
        setJobs(jList);
        setCatalogs(cList);

        if (cList.length > 0) {
          const storedCatId = Number(localStorage.getItem("careerproof-catalog-id"));
          const matchedCat = cList.find((c) => c.id === storedCatId) || cList[0];
          setSelectedCatalogId(matchedCat.id);
        }

        if (jList.length > 0) {
          const first = jList[0];
          setSelectedJob(first);
          loadJobVersionsAndAnalysis(first.job_id, cList[0]?.id);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || "Failed to load JD workspace.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  async function loadJobVersionsAndAnalysis(jobId: number, catalogId?: number) {
    try {
      const vers = await jdApi.getJobVersions(jobId);
      setJobVersions(vers);

      const targetCatId = catalogId || selectedCatalogId;
      if (targetCatId) {
        const analyses = await jdApi.listCatalogAnalyses(targetCatId);
        const match = analyses.find((a) =>
          vers.some((v) => v.id === a.job_version_id)
        );
        if (match) {
          setActiveAnalysis(match);
        } else {
          setActiveAnalysis(null);
        }
      }
    } catch (e) {
      console.error(e);
    }
  }

  async function handleSelectJob(job: JobVersion) {
    setSelectedJob(job);
    await loadJobVersionsAndAnalysis(job.job_id);
  }

  async function handleSelectVersion(versionId: number) {
    const found = jobVersions.find((v) => v.id === versionId);
    if (found) {
      setSelectedJob(found);
      if (selectedCatalogId) {
        const analyses = await jdApi.listCatalogAnalyses(selectedCatalogId);
        const match = analyses.find((a) => a.job_version_id === found.id);
        setActiveAnalysis(match || null);
      }
    }
  }

  async function handleCreateJob(e: React.FormEvent) {
    e.preventDefault();
    if (!newRoleTitle.trim() || !newCompanyName.trim() || !newRawText.trim()) {
      setError("Please fill in role title, company name, and job description text.");
      return;
    }

    setBusy(true);
    setError("");
    setNotice("");
    try {
      const payload: CreateJobPayload = {
        role_title: newRoleTitle.trim(),
        company_name: newCompanyName.trim(),
        raw_text: newRawText.trim(),
        target_domain: newTargetDomain.trim() || undefined,
        location: newLocation.trim() || undefined,
      };

      const createdVersion = await jdApi.createOrUpdateJob(payload);
      const updatedJobs = await jdApi.listJobs();
      setJobs(updatedJobs);
      setSelectedJob(createdVersion);
      setShowNewJobModal(false);
      resetNewJobForm();

      await loadJobVersionsAndAnalysis(createdVersion.job_id);
      setNotice(
        `Job parsed successfully: extracted ${createdVersion.requirements.length} structured requirements.`
      );

      // Automatically run analysis if catalog is selected
      if (selectedCatalogId) {
        await runAnalysisForJob(createdVersion.job_id, selectedCatalogId);
      }
    } catch (err: any) {
      setError(err.message || "Failed to create and parse job.");
    } finally {
      setBusy(false);
    }
  }

  async function runAnalysisForJob(jobId: number, catalogId: number) {
    setBusy(true);
    setError("");
    try {
      const analysis = await jdApi.analyze({
        job_id: jobId,
        catalog_id: catalogId,
      });
      setActiveAnalysis(analysis);
      setNotice("Evidence mapping complete: requirements matched against approved claims.");
    } catch (err: any) {
      setError(err.message || "Failed to analyze evidence against requirements.");
    } finally {
      setBusy(false);
    }
  }

  function resetNewJobForm() {
    setNewRoleTitle("");
    setNewCompanyName("");
    setNewTargetDomain("");
    setNewLocation("");
    setNewRawText("");
  }

  function fillSampleJob() {
    setNewRoleTitle("Senior Backend Engineer");
    setNewCompanyName("Acme Cloud Corp");
    setNewTargetDomain("Distributed Systems / Cloud Infrastructure");
    setNewLocation("Remote / San Francisco, CA");
    setNewRawText(`About Acme Cloud:
We build planetary-scale streaming and database infrastructure.

Role Requirements:
- 5+ years of production experience in Python or Go.
- Strong hands-on expertise with PostgreSQL, schema migration, and transaction isolation.
- Experience with Docker, Kubernetes, and automated deployment pipelines.
- Familiarity with modern AI tools and LLM workflows.
- Experience with Kafka or RabbitMQ event-driven architectures.
- Bachelor's or Master's degree in Computer Science, or equivalent practical industry experience.

Core Responsibilities:
- Architect and maintain high-throughput ingestion pipelines serving millions of queries daily.
- Partner with product and platform teams to design clean, typed APIs.
- Monitor system latencies and drive p99 query performance down across database clusters.

Preferred Qualifications:
- Familiarity with Redis distributed locking and caching mechanisms.
- Prior experience in financial data compliance or healthcare environments.`);
  }

  const toggleExpand = (reqId: number) => {
    setExpandedReqIds((prev) => ({ ...prev, [reqId]: !prev[reqId] }));
  };

  // Requirement items with match results merged
  const requirementCards = useMemo(() => {
    if (!selectedJob) return [];

    const matchesMap = new Map<number, RequirementMatch>();
    if (activeAnalysis?.matches) {
      activeAnalysis.matches.forEach((m) => {
        matchesMap.set(m.requirement_id, m);
      });
    }

    return selectedJob.requirements.map((req) => {
      const match = matchesMap.get(req.id);
      return {
        req,
        match,
        status: (match?.match_status || "missing") as MatchStatus,
      };
    });
  }, [selectedJob, activeAnalysis]);

  // Filtered requirements
  const filteredCards = useMemo(() => {
    return requirementCards.filter(({ req, match, status }) => {
      if (categoryFilter !== "all" && req.category !== categoryFilter) {
        return false;
      }
      if (statusFilter !== "all" && status !== statusFilter) {
        return false;
      }
      if (showAmbiguousOnly && !req.is_ambiguous) {
        return false;
      }
      if (search.trim()) {
        const query = search.toLowerCase();
        const inTitle = req.title.toLowerCase().includes(query);
        const inQuote = req.verbatim_quote.toLowerCase().includes(query);
        const inRationale = match?.score_rationale?.toLowerCase().includes(query);
        const inTerms = req.normalized_terms.some((t) => t.toLowerCase().includes(query));
        if (!inTitle && !inQuote && !inRationale && !inTerms) {
          return false;
        }
      }
      return true;
    });
  }, [requirementCards, categoryFilter, statusFilter, showAmbiguousOnly, search]);

  const summary = activeAnalysis?.summary;

  return (
    <div className="jd-workspace">
      {/* Header */}
      <header className="jd-header">
        <div>
          <div className="jd-kicker">
            <Target size={13} />
            <span>Phase 2 Engine: JD Intelligence & Evidence Mapping</span>
          </div>
          <h1>Job Description Intelligence</h1>
          <p>
            Ground-truth requirement extraction anchored to verbatim quotes, with deterministic
            matching against approved Universal Evidence Catalog claims.
          </p>
        </div>

        <div className="jd-header-actions">
          <button
            type="button"
            className="jd-primary"
            onClick={() => setShowNewJobModal(true)}
            disabled={busy}
          >
            <Plus size={14} /> New Job Posting
          </button>
          <button
            type="button"
            onClick={() => {
              if (selectedJob && selectedCatalogId) {
                runAnalysisForJob(selectedJob.job_id, selectedCatalogId);
              }
            }}
            disabled={busy || !selectedJob || !selectedCatalogId}
          >
            <RefreshCw size={13} className={busy ? "animate-spin" : ""} /> Re-run Evidence Mapping
          </button>
        </div>
      </header>

      {/* Notices & Errors */}
      {error && (
        <div className="jd-banner error">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}
      {notice && (
        <div className="jd-banner notice">
          <CheckCircle2 size={16} />
          <span>{notice}</span>
        </div>
      )}

      {/* Target Job & Catalog Selector Bar */}
      <div className="jd-job-bar">
        <div className="jd-job-meta">
          <div className="jd-form-group" style={{ minWidth: 220 }}>
            <label>Active Job Posting</label>
            <select
              value={selectedJob?.job_id || ""}
              onChange={(e) => {
                const j = jobs.find((x) => x.job_id === Number(e.target.value));
                if (j) handleSelectJob(j);
              }}
            >
              {jobs.map((j) => (
                <option key={j.job_id} value={j.job_id}>
                  {j.role_title} ({j.company_name})
                </option>
              ))}
            </select>
          </div>

          {jobVersions.length > 1 && (
            <div className="jd-form-group" style={{ minWidth: 150 }}>
              <label>Version History</label>
              <select
                value={selectedJob?.id || ""}
                onChange={(e) => handleSelectVersion(Number(e.target.value))}
              >
                {jobVersions.map((v) => (
                  <option key={v.id} value={v.id}>
                    v{v.version_number} ({v.text_hash.slice(0, 7)})
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="jd-form-group" style={{ minWidth: 200 }}>
            <label>Candidate Evidence Catalog</label>
            <select
              value={selectedCatalogId || ""}
              onChange={(e) => {
                const id = Number(e.target.value);
                setSelectedCatalogId(id);
                localStorage.setItem("careerproof-catalog-id", String(id));
                if (selectedJob) {
                  runAnalysisForJob(selectedJob.job_id, id);
                }
              }}
            >
              {catalogs.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} (rev {c.revision})
                </option>
              ))}
            </select>
          </div>
        </div>

        {selectedJob && (
          <div className="jd-version-pill">
            <GitBranch size={12} />
            <span>
              sha256: {selectedJob.text_hash.slice(0, 10)}... (v{selectedJob.version_number})
            </span>
          </div>
        )}
      </div>

      {/* Summary Metrics Grid */}
      {summary ? (
        <div className="jd-metrics-grid">
          <div className="jd-metric-card">
            <span className="jd-metric-label">Total Requirements</span>
            <span className="jd-metric-val">{summary.total_requirements}</span>
          </div>
          <div className="jd-metric-card">
            <span className="jd-metric-label">Direct Matches</span>
            <span className="jd-metric-val direct">{summary.direct_matches}</span>
          </div>
          <div className="jd-metric-card">
            <span className="jd-metric-label">Transferable</span>
            <span className="jd-metric-val transferable">{summary.transferable_matches}</span>
          </div>
          <div className="jd-metric-card">
            <span className="jd-metric-label">Missing Gaps</span>
            <span className="jd-metric-val missing">{summary.missing_requirements}</span>
          </div>
          <div className="jd-metric-card">
            <span className="jd-metric-label">Unresolved</span>
            <span className="jd-metric-val unresolved">{summary.unresolved_requirements}</span>
          </div>
          <div className="jd-metric-card">
            <span className="jd-metric-label">Direct Match Rate</span>
            <span className="jd-metric-val direct">{summary.direct_match_pct}%</span>
          </div>
          <div className="jd-metric-card">
            <span className="jd-metric-label">Total Coverage</span>
            <span className="jd-metric-val">{summary.coverage_pct}%</span>
          </div>
        </div>
      ) : (
        <div
          className="jd-banner"
          style={{ background: "#1c1828", border: "1px solid #3c3152", color: "#c8bee0" }}
        >
          <Sparkles size={16} />
          <span>
            Click "Re-run Evidence Mapping" above to evaluate candidate evidence against this job posting.
          </span>
        </div>
      )}

      {/* Controls & Filter Bar */}
      <div className="jd-controls-bar">
        <div className="jd-pills-row">
          <button
            type="button"
            className={`jd-filter-pill ${categoryFilter === "all" ? "active" : ""}`}
            onClick={() => setCategoryFilter("all")}
          >
            All Categories
          </button>
          {Object.entries(CATEGORY_LABELS).map(([catKey, label]) => (
            <button
              key={catKey}
              type="button"
              className={`jd-filter-pill ${categoryFilter === catKey ? "active" : ""}`}
              onClick={() => setCategoryFilter(catKey)}
            >
              {label}
            </button>
          ))}
        </div>

        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ fontSize: 11 }}
          >
            <option value="all">All Match Statuses</option>
            <option value="direct">Direct Match</option>
            <option value="transferable">Transferable</option>
            <option value="missing">Missing Gaps</option>
            <option value="unresolved">Unresolved Claims</option>
          </select>

          <button
            type="button"
            className={`jd-filter-pill ${showAmbiguousOnly ? "active" : ""}`}
            onClick={() => setShowAmbiguousOnly(!showAmbiguousOnly)}
          >
            Ambiguous Only
          </button>

          <div style={{ position: "relative" }}>
            <input
              type="text"
              placeholder="Filter requirements..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ width: 190, paddingLeft: 26 }}
            />
            <Search
              size={13}
              style={{ position: "absolute", left: 8, top: 9, color: "#8a819e" }}
            />
          </div>
        </div>
      </div>

      {/* Requirements List */}
      <div className="jd-requirements-list">
        {filteredCards.length === 0 ? (
          <div
            style={{
              padding: "40px 20px",
              textAlign: "center",
              background: "#16131e",
              borderRadius: 8,
              border: "1px dashed #342d42",
            }}
          >
            <p style={{ margin: 0 }}>No requirements match the active search or filters.</p>
          </div>
        ) : (
          filteredCards.map(({ req, match, status }) => {
            const isExpanded = !!expandedReqIds[req.id];

            return (
              <div key={req.id} className={`jd-req-card ${status}`}>
                <div className="jd-req-header">
                  <div className="jd-req-title-group">
                    <div className="jd-badges-row">
                      <span className={`jd-badge ${req.is_mandatory ? "mandatory" : "preferred"}`}>
                        {req.is_mandatory ? "Mandatory" : "Preferred"}
                      </span>
                      <span className="jd-badge category">
                        {CATEGORY_LABELS[req.category] || req.category}
                      </span>
                      <span className={`jd-badge status-${status}`}>
                        {status === "direct" && "Direct Match"}
                        {status === "transferable" && "Transferable"}
                        {status === "missing" && "Missing Evidence"}
                        {status === "unresolved" && "Unresolved Claims"}
                      </span>
                      {req.is_ambiguous && (
                        <span className="jd-badge ambiguous" title={req.ambiguity_explanation || ""}>
                          Ambiguous Formulation
                        </span>
                      )}
                    </div>
                    <h3 style={{ marginTop: 4 }}>{req.title}</h3>
                  </div>

                  <button
                    type="button"
                    onClick={() => toggleExpand(req.id)}
                    style={{ padding: "4px 8px", fontSize: 11 }}
                  >
                    {isExpanded ? (
                      <>
                        <span>Less</span> <ChevronUp size={13} />
                      </>
                    ) : (
                      <>
                        <span>Details</span> <ChevronDown size={13} />
                      </>
                    )}
                  </button>
                </div>

                {/* Exact JD Source Quote */}
                <div className="jd-quote-box">
                  <div>"{req.verbatim_quote}"</div>
                  <div className="jd-quote-citation">
                    <span>Source citation:</span>
                    <code>
                      offsets [{req.start_offset} - {req.end_offset}]
                    </code>
                    {req.normalized_terms.length > 0 && (
                      <span style={{ marginLeft: "auto" }}>
                        Normalized: {req.normalized_terms.join(", ")}
                      </span>
                    )}
                  </div>
                </div>

                {/* Ambiguity explanation note */}
                {req.is_ambiguous && req.ambiguity_explanation && (
                  <div
                    style={{
                      fontSize: 11,
                      color: "#fef08a",
                      background: "#2a2211",
                      border: "1px solid #57431c",
                      padding: "6px 10px",
                      borderRadius: 5,
                      marginBottom: 8,
                    }}
                  >
                    <strong>Ambiguity Note:</strong> {req.ambiguity_explanation}
                  </div>
                )}

                {/* Evidence Mapping & Rationale */}
                {match && (
                  <div className="jd-evidence-section">
                    {/* Transferable Technology Banner */}
                    {match.match_status === "transferable" && match.transferable_details && (
                      <div className="jd-transferable-banner">
                        <div style={{ fontWeight: 600 }}>
                          Transferable Competency Identified:{" "}
                          <span style={{ color: "#a78bfa" }}>
                            {match.transferable_details.candidate_technology}
                          </span>{" "}
                          →{" "}
                          <span style={{ color: "#f472b6" }}>
                            {match.transferable_details.target_technology}
                          </span>{" "}
                          ({match.transferable_details.cluster_name})
                        </div>
                        <div>{match.transferable_details.rationale}</div>
                      </div>
                    )}

                    {/* Clarification Question for Gaps / Missing Requirements */}
                    {match.clarification_question && (
                      <div className="jd-clarification-banner">
                        <div style={{ fontWeight: 600, display: "flex", alignItems: "center", gap: 5 }}>
                          <HelpCircle size={13} /> Candidate Clarification Question:
                        </div>
                        <div style={{ marginTop: 3 }}>{match.clarification_question}</div>
                      </div>
                    )}

                    {/* Score Rationale */}
                    <div className="jd-rationale-box">
                      <strong>Mapping Rationale:</strong> {match.score_rationale}
                    </div>

                    {/* Matched Claims Detail */}
                    {match.matched_claims && match.matched_claims.length > 0 && (
                      <div className="jd-matched-claims-list">
                        <div style={{ fontSize: 11, fontWeight: 600, color: "#b9adcf" }}>
                          Approved Candidate Claims ({match.matched_claims.length}):
                        </div>
                        {match.matched_claims.map((claim: MatchedClaimSnapshot) => (
                          <div key={claim.id} className="jd-claim-item">
                            <div style={{ fontWeight: 550 }}>{claim.text}</div>
                            <div className="jd-claim-meta">
                              {claim.association && <span>Org: {claim.association}</span>}
                              {claim.role && <span>Role: {claim.role}</span>}
                              {claim.dates && <span>Dates: {claim.dates}</span>}
                              {claim.contribution && (
                                <span>Contribution: {claim.contribution}</span>
                              )}
                            </div>
                            {claim.sources && claim.sources.length > 0 && (
                              <div className="jd-claim-source-quote">
                                Citation: "{claim.sources[0].quote}" ({claim.sources[0].filename})
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* New Job Modal */}
      {showNewJobModal && (
        <div className="jd-modal-overlay" onClick={() => setShowNewJobModal(false)}>
          <div className="jd-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="jd-modal-header">
              <h2>Add Target Job Description</h2>
              <button
                type="button"
                onClick={() => setShowNewJobModal(false)}
                style={{ background: "transparent", border: "none", padding: 4 }}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleCreateJob}>
              <div className="jd-modal-body">
                <div style={{ display: "flex", justifyContent: "flex-end" }}>
                  <button
                    type="button"
                    onClick={fillSampleJob}
                    style={{ fontSize: 11, background: "#2a2238", borderColor: "#554473" }}
                  >
                    <Sparkles size={12} /> Auto-fill Sample Tech JD
                  </button>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  <div className="jd-form-group">
                    <label>Role Title *</label>
                    <input
                      type="text"
                      placeholder="e.g. Senior Backend Engineer"
                      value={newRoleTitle}
                      onChange={(e) => setNewRoleTitle(e.target.value)}
                      required
                    />
                  </div>
                  <div className="jd-form-group">
                    <label>Company Name *</label>
                    <input
                      type="text"
                      placeholder="e.g. Stripe, Acme Cloud"
                      value={newCompanyName}
                      onChange={(e) => setNewCompanyName(e.target.value)}
                      required
                    />
                  </div>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  <div className="jd-form-group">
                    <label>Target Domain (Optional)</label>
                    <input
                      type="text"
                      placeholder="e.g. FinTech, Distributed Systems"
                      value={newTargetDomain}
                      onChange={(e) => setNewTargetDomain(e.target.value)}
                    />
                  </div>
                  <div className="jd-form-group">
                    <label>Location (Optional)</label>
                    <input
                      type="text"
                      placeholder="e.g. Remote, San Francisco"
                      value={newLocation}
                      onChange={(e) => setNewLocation(e.target.value)}
                    />
                  </div>
                </div>

                <div className="jd-form-group">
                  <label>
                    Full Job Description Text * ({newRawText.length} characters)
                  </label>
                  <textarea
                    rows={12}
                    placeholder="Paste the raw text of the job description here..."
                    value={newRawText}
                    onChange={(e) => setNewRawText(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div className="jd-modal-footer">
                <button
                  type="button"
                  onClick={() => setShowNewJobModal(false)}
                  disabled={busy}
                >
                  Cancel
                </button>
                <button type="submit" className="jd-primary" disabled={busy}>
                  {busy ? "Parsing & Extracting..." : "Parse & Extract Requirements"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
