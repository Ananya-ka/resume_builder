"use client";
import { useState } from "react";
import {
  AlertTriangle,
  ShieldAlert,
  Search,
  CheckCircle2,
  HelpCircle,
  Briefcase,
  Layers,
  ArrowRight,
  Info
} from "lucide-react";
import type { ObjectionReport, HiringObjection, GapClassification } from "@/lib/careerproof/api";
import { Badge } from "./ui";

export function HiringObjectionView({ report }: { report: ObjectionReport }) {
  const [activePersona, setActivePersona] = useState<string>("all");

  const personas = [
    { id: "all", label: `All Hypotheses (${report.objections.length})` },
    {
      id: "Recruiter Screen",
      label: `Recruiter Screen (${report.objections.filter((o) => o.persona === "Recruiter Screen").length})`,
    },
    {
      id: "Hiring Manager",
      label: `Hiring Manager (${report.objections.filter((o) => o.persona === "Hiring Manager").length})`,
    },
    {
      id: "Technical Bar-Raiser",
      label: `Technical Bar-Raiser (${report.objections.filter((o) => o.persona === "Technical Bar-Raiser").length})`,
    },
  ];

  const filteredObjections =
    activePersona === "all"
      ? report.objections
      : report.objections.filter((o) => o.persona === activePersona);

  return (
    <div className="objection-engine-panel">
      {/* Header */}
      <div className="objection-engine-header">
        <div className="objection-header-left">
          <div className="objection-icon-badge">
            <ShieldAlert size={20} />
          </div>
          <div>
            <h3 className="objection-title">Hiring Objection Engine</h3>
            <p className="objection-subtitle">
              Pre-empting recruiter and interviewer hesitations grounded in verified evidence
            </p>
          </div>
        </div>
        <div className="ats-mini-metrics">
          <span className="ats-chip">
            <strong>{report.summary.total_objections}</strong> Hypotheses
          </span>
          {report.summary.hard_constraints_count > 0 && (
            <span
              className="ats-chip"
              style={{ background: "#faecec", borderColor: "#e8bcbc", color: "#a82020" }}
            >
              <strong>{report.summary.hard_constraints_count}</strong> Hard Constraint
            </span>
          )}
          <span className="ats-chip">
            <strong>{report.summary.transferable_gaps}</strong> Transferable
          </span>
        </div>
      </div>

      {/* Bucket D: Hard Constraints Warning */}
      {report.hard_constraints.length > 0 && (
        <div className="hard-constraint-alert" role="alert">
          <AlertTriangle size={18} color="#b91c1c" />
          <div>
            <div className="hard-constraint-title">
              Hard Eligibility Constraint Detected ({report.hard_constraints.length})
            </div>
            {report.hard_constraints.map((hc, idx) => (
              <p key={idx} className="hard-constraint-desc">
                <strong>{hc.type}:</strong> {hc.requirement}. {hc.action_guidance}
              </p>
            ))}
          </div>
        </div>
      )}

      {/* Persona Tabs */}
      <div className="persona-nav" role="tablist">
        {personas.map((p) => (
          <button
            key={p.id}
            role="tab"
            aria-selected={activePersona === p.id}
            className={`persona-btn ${activePersona === p.id ? "active" : ""}`}
            onClick={() => setActivePersona(p.id)}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Objections List */}
      <div>
        {!filteredObjections.length ? (
          <p className="muted" style={{ padding: "16px 0" }}>
            No specific hesitations detected for this perspective.
          </p>
        ) : (
          filteredObjections.map((obj) => (
            <article key={obj.id} className="objection-card">
              <div className="objection-card-top">
                <span className="objection-trigger">
                  🎯 Trigger: {obj.jd_trigger}
                </span>
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  <Badge tone={obj.confidence === "High" ? "amber" : "neutral"}>
                    {obj.confidence} Confidence
                  </Badge>
                  <span
                    className={`gap-bucket-badge ${obj.gap_bucket}`}
                    style={{ margin: 0 }}
                  >
                    {obj.gap_bucket.replace("_", " ")}
                  </span>
                </div>
              </div>

              {/* Hypothesis Box */}
              <div className="objection-hypothesis-box">
                <div className="objection-hypothesis-label">
                  Probable {obj.persona} Concern (Evaluative Hypothesis)
                </div>
                <div className="objection-hypothesis-text">
                  “{obj.hypothesis}”
                </div>
              </div>

              {/* Evidence State */}
              <div className="objection-evidence-state">
                <strong>Evidence state:</strong> {obj.evidence_state}
              </div>

              {/* Action Box */}
              <div className="objection-action-box">
                <div className="objection-action-title">
                  <CheckCircle2 size={13} />
                  Resolution: {obj.resolution_action.type}
                </div>
                <div className="objection-action-content">
                  {obj.resolution_action.action}
                </div>
              </div>
            </article>
          ))
        )}
      </div>

      {/* 4-Bucket Gap Taxonomy Grid */}
      <div style={{ marginTop: 24, paddingTop: 16, borderTop: "1px dashed #dbe5de" }}>
        <h4 style={{ fontSize: 13, fontWeight: 700, color: "var(--ink)", marginBottom: 4 }}>
          4-Bucket Evidence Gap Breakdown
        </h4>
        <p className="muted small" style={{ marginBottom: 12 }}>
          Distinguishing omitted background facts, transferable technology, true deficits, and hard constraints
        </p>

        <div className="gap-buckets-grid">
          {/* Bucket A */}
          <div className="gap-bucket-card">
            <span className="gap-bucket-badge unexpressed">Bucket A · Unexpressed</span>
            <div>
              <span className="gap-bucket-count">{report.summary.unexpressed_gaps}</span>
              <span className="small-label">Found in catalog, not on resume</span>
            </div>
            <p className="gap-bucket-desc">
              Achievements exist in your profile records. Ready to incorporate into resume draft.
            </p>
          </div>

          {/* Bucket B */}
          <div className="gap-bucket-card">
            <span className="gap-bucket-badge transferable">Bucket B · Transferable</span>
            <div>
              <span className="gap-bucket-count">{report.summary.transferable_gaps}</span>
              <span className="small-label">Adjacent technical domains</span>
            </div>
            <p className="gap-bucket-desc">
              You possess adjacent patterns (e.g. RabbitMQ ➔ Kafka). Reframe honestly without overclaiming.
            </p>
          </div>

          {/* Bucket C */}
          <div className="gap-bucket-card">
            <span className="gap-bucket-badge true_deficit">Bucket C · True Deficit</span>
            <div>
              <span className="gap-bucket-count">{report.summary.true_deficits}</span>
              <span className="small-label">Missing technical competencies</span>
            </div>
            <p className="gap-bucket-desc">
              No historical exposure. Suggests Minimum Proof Building (Implementation or Operational).
            </p>
          </div>

          {/* Bucket D */}
          <div className="gap-bucket-card">
            <span className="gap-bucket-badge hard_constraint">Bucket D · Hard Constraint</span>
            <div>
              <span className="gap-bucket-count">{report.summary.hard_constraints_count}</span>
              <span className="small-label">Institutional / Legal</span>
            </div>
            <p className="gap-bucket-desc">
              Degrees, licenses, clearances, or work authorization. Cannot be bypassed by re-wording.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
