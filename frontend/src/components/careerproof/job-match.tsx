"use client";
import { useState } from "react";
import {
  ChevronDown,
  Check,
  CircleHelp,
  Minus,
  Folder,
  ArrowRight,
} from "lucide-react";
import type { Application, Achievement } from "@/lib/careerproof/types";
import { requirements, sampleJob } from "@/lib/careerproof/demo-service";
import { Badge, ContinueButton } from "./ui";
const labels = {
  work: "Work experience",
  project: "Project experience",
  clarify: "Needs clarification",
  gap: "No evidence yet",
};
export function JobMatch({
  app,
  evidence,
  onChange,
  onEvidence,
  onContinue,
}: {
  app: Application;
  evidence: Achievement[];
  onChange: (a: Application) => void;
  onEvidence: (e: Achievement) => void;
  onContinue: () => void;
}) {
  const [show, setShow] = useState(!!app.jd);
  const matches = requirements(app.jd, evidence);
  return (
    <div className="job-layout">
      <section className="main-surface">
        <div className="surface-title">
          <span className="step-kicker">03 / THE OPPORTUNITY</span>
          <button
            className="inline-link"
            onClick={() => {
              onChange({ ...app, ...sampleJob() });
              setShow(true);
            }}
          >
            Use sample job <ArrowRight size={13} />
          </button>
        </div>
        <h2>What does this role need?</h2>
        <p className="muted">
          Compare the requirements with what your evidence actually supports.
        </p>
        <div className="form-grid">
          <label>
            Company
            <input
              value={app.company}
              placeholder="e.g. Meridian"
              onChange={(e) => onChange({ ...app, company: e.target.value })}
            />
          </label>
          <label>
            Role
            <input
              value={app.role}
              placeholder="e.g. Backend Engineer"
              onChange={(e) => onChange({ ...app, role: e.target.value })}
            />
          </label>
        </div>
        <label className="field-label" htmlFor="jd">
          Job description
        </label>
        <textarea
          id="jd"
          rows={10}
          value={app.jd}
          placeholder="Paste the complete job description, including required and preferred qualifications…"
          onChange={(e) => {
            onChange({ ...app, jd: e.target.value });
            setShow(false);
          }}
        />
        <div className="form-bottom">
          <span className="micro">
            Demo comparison uses a fixed technical vocabulary.
          </span>
          <button
            className="button secondary"
            disabled={!app.jd.trim()}
            onClick={() => setShow(true)}
          >
            Compare evidence
            <ArrowRight size={15} />
          </button>
        </div>
        {show && (
          <section className="requirements">
            <div className="subheading">
              <h3>Evidence, not a score.</h3>
              <Badge>
                {
                  matches.filter(
                    (m) => m.status === "work" || m.status === "project",
                  ).length
                }{" "}
                of {matches.length} supported
              </Badge>
            </div>
            {matches.length ? (
              matches.map((m) => (
                <details className="requirement" key={m.id}>
                  <summary>
                    <span className={`requirement-icon ${m.status}`}>
                      {m.status === "work" ? (
                        <Check size={15} />
                      ) : m.status === "project" ? (
                        <Folder size={14} />
                      ) : m.status === "clarify" ? (
                        <CircleHelp size={15} />
                      ) : (
                        <Minus size={15} />
                      )}
                    </span>
                    <strong>
                      {m.name}
                      <small>
                        {m.preferred ? "Preferred" : "Required / mentioned"}
                      </small>
                    </strong>
                    <span className="requirement-status">
                      {labels[m.status]}
                    </span>
                    <ChevronDown size={14} />
                  </summary>
                  <div className="requirement-details">
                    <p>{m.explanation}</p>
                    {m.evidenceIds.map((id) => {
                      const e = evidence.find((item) => item.id === id)!;
                      return (
                        <button
                          className="evidence-excerpt"
                          key={id}
                          onClick={() => onEvidence(e)}
                        >
                          <span>{e.company}</span>
                          {e.text}
                        </button>
                      );
                    })}
                  </div>
                </details>
              ))
            ) : (
              <p className="notice">
                No terms in the demo vocabulary matched. Use the sample job to
                explore evidence coverage; arbitrary JD extraction needs the
                server workflow.
              </p>
            )}
          </section>
        )}
        <div className="step-footer">
          <span className="micro">
            Unsupported qualifications stay visible as gaps.
          </span>
          <ContinueButton
            disabled={
              !show ||
              !app.company.trim() ||
              !app.role.trim() ||
              !matches.length
            }
            onClick={onContinue}
          >
            Fill in the missing context
          </ContinueButton>
        </div>
      </section>
      <aside className="context-panel">
        <span className="eyebrow">THE MATCH, EXPLAINED</span>
        <h3>
          Show what fits.
          <br />
          Be honest about what doesn’t.
        </h3>
        <p className="muted">
          A keyword is only useful when there’s real experience behind it.
        </p>
        <div className="panel-divider" />
        {Object.entries(labels).map(([key, label]) => (
          <div className="legend-item" key={key}>
            <span className={`legend-dot ${key}`} />
            <div>
              <strong>{label}</strong>
              <p>
                {key === "work"
                  ? "A specific professional contribution."
                  : key === "project"
                    ? "Hands-on work outside employment."
                    : key === "clarify"
                      ? "Related evidence needs more context."
                      : "A gap to acknowledge, never invent."}
              </p>
            </div>
          </div>
        ))}
        <div className="quiet-note">
          <p>
            Demo questions follow the sample API and Redis scenario. Live
            questions are selected by the backend.
          </p>
        </div>
      </aside>
    </div>
  );
}
