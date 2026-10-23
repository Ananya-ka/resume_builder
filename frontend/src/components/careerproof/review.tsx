"use client";
import { useState } from "react";
import {
  Check,
  ArrowUpRight,
  ArrowUp,
  ArrowDown,
  Pin,
  RotateCcw,
  Pencil,
  Eye,
  ListFilter,
  Printer,
  Plus,
  Minus,
  FileCheck2,
  AlertTriangle,
  ArrowRight,
  ShieldCheck,
  Link2,
} from "lucide-react";
import type {
  Application,
  ResumeBullet,
  Achievement,
} from "@/lib/careerproof/types";
import { candidate } from "@/lib/careerproof/fixtures";
import { Badge } from "./ui";
export function Review({
  app,
  evidence,
  onChange,
  onEdit,
  onCorrect,
  onNewVersion,
  onSubmit,
  onNotice,
}: {
  app: Application;
  evidence: Achievement[];
  onChange: (a: Application) => void;
  onEdit: (b: ResumeBullet) => void;
  onCorrect: (e: Achievement) => void;
  onNewVersion: () => void;
  onSubmit: () => void;
  onNotice: (message: string) => void;
}) {
  const [mode, setMode] = useState<"changes" | "clean">("changes");
  const [tab, setTab] = useState<"changes" | "evidence" | "selection">(
    "changes",
  );
  const [selectedId, setSelectedId] = useState(
    app.bullets.find((b) => b.included)?.evidenceId || "",
  );
  const selected = app.bullets.find((b) => b.evidenceId === selectedId);
  const included = app.bullets.filter((b) => b.included);
  const unsupported = (b: ResumeBullet) =>
    ["familiarity", "tutorial", "team_only"].includes(b.depth);
  const problems = included.filter(
    (b) => b.needsReview || unsupported(b),
  ).length;
  const accepted = included.filter((b) => b.accepted && !b.needsReview).length;
  const historical = app.status === "submitted";
  const wordCount =
    included.reduce((total, b) => total + b.text.split(/\s+/).length, 0) + 60;
  const blocked =
    !included.length ||
    !!problems ||
    (!historical && !!app.staleIds.length) ||
    wordCount > 520;
  function update(id: string, patch: Partial<ResumeBullet>) {
    if (historical) return;
    onChange({
      ...app,
      bullets: app.bullets.map((b) =>
        b.evidenceId === id ? { ...b, ...patch } : b,
      ),
    });
  }
  function move(id: string, direction: number) {
    const bullets = [...app.bullets];
    const index = bullets.findIndex((b) => b.evidenceId === id);
    const target = index + direction;
    if (target < 0 || target >= bullets.length) return;
    [bullets[index], bullets[target]] = [bullets[target], bullets[index]];
    onChange({ ...app, bullets });
  }
  const groups = [...new Set(included.map((b) => `${b.section}|${b.company}`))];
  return (
    <div className="review-workspace">
      <div className="review-toolbar">
        <div className="segmented" aria-label="Preview mode">
          <button
            className={mode === "changes" ? "active" : ""}
            aria-pressed={mode === "changes"}
            onClick={() => setMode("changes")}
          >
            <ListFilter size={15} />
            Review changes
          </button>
          <button
            className={mode === "clean" ? "active" : ""}
            aria-pressed={mode === "clean"}
            onClick={() => setMode("clean")}
          >
            <Eye size={15} />
            Clean preview
          </button>
        </div>
        <div className="toolbar-actions">
          <span className="micro">
            Version {app.version} · {wordCount} words
          </span>
          <button
            className="button secondary"
            disabled={blocked}
            onClick={() => window.print()}
          >
            <Printer size={15} />
            Print resume
          </button>
          {!historical && (
            <button
              className="button primary"
              disabled={blocked || accepted !== included.length}
              onClick={onSubmit}
            >
              <FileCheck2 size={15} />
              Mark submitted
            </button>
          )}
        </div>
      </div>
      {historical && (
        <div className="notice">
          <ShieldCheck size={17} />
          <span>
            Submitted snapshot. This document stays exactly as it was.
          </span>
          <button className="inline-link" onClick={onNewVersion}>
            Create a new version
            <ArrowRight size={14} />
          </button>
        </div>
      )}
      {!!app.staleIds.length && (
        <div className="notice warning">
          <AlertTriangle size={17} />
          <span>
            {app.staleIds.length} source achievement
            {app.staleIds.length === 1 ? " has" : "s have"} changed. This
            version preserves its original claims.
          </span>
          <button className="inline-link" onClick={onNewVersion}>
            Review a corrected version
            <ArrowRight size={14} />
          </button>
        </div>
      )}
      {problems > 0 && (
        <div className="notice warning">
          <AlertTriangle size={16} />
          {problems} selected claim{problems === 1 ? " needs" : "s need"}{" "}
          clarification. Correct the evidence or omit the claim before printing
          or submitting.
        </div>
      )}
      {wordCount > 520 && (
        <div className="notice warning">
          This exceeds the one-page workspace budget. Omit or shorten an
          achievement before exporting.
        </div>
      )}
      <div className={`review-grid ${mode === "clean" ? "clean-mode" : ""}`}>
        <div className="paper-stage">
          <div className="paper-caption">
            <span>YOUR TAILORED RESUME</span>
            <span>
              {mode === "changes"
                ? "Select a bullet to see its story"
                : "Evidence annotations are excluded from print"}
            </span>
          </div>
          <article
            className="resume-paper print-root"
            aria-label="Resume preview"
          >
            <header className="resume-header">
              <h2>{candidate.name}</h2>
              <p className="resume-title">SOFTWARE ENGINEER</p>
              <p className="resume-contact">
                {candidate.location} <span>·</span> {candidate.email}
              </p>
            </header>
            <div className="resume-rule" />
            {["Experience", "Projects"].map((section) => (
              <section key={section} className="resume-section">
                <h3>
                  {section === "Experience"
                    ? "PROFESSIONAL EXPERIENCE"
                    : "SELECTED PROJECTS"}
                </h3>
                {groups
                  .filter((g) => g.startsWith(section + "|"))
                  .map((group) => {
                    const company = group.split("|")[1];
                    const bullets = included.filter(
                      (b) => b.section === section && b.company === company,
                    );
                    return (
                      <div className="resume-group" key={group}>
                        <div className="resume-position">
                          <strong>{company}</strong>
                          <span>
                            {section === "Experience"
                              ? app.profileDate
                              : "Personal project"}
                          </span>
                        </div>
                        {section === "Experience" && (
                          <p className="resume-role">{bullets[0].role}</p>
                        )}
                        <ul>
                          {bullets.map((b) => (
                            <li
                              className={`${mode === "changes" && selectedId === b.evidenceId ? "selected-bullet" : ""} ${b.needsReview ? "unresolved-bullet" : ""}`}
                              key={b.evidenceId}
                            >
                              {mode === "changes" ? (
                                <button
                                  className="resume-bullet"
                                  onClick={() => {
                                    setSelectedId(b.evidenceId);
                                    document
                                      .getElementById("review-details")
                                      ?.scrollIntoView({
                                        behavior: window.matchMedia(
                                          "(prefers-reduced-motion: reduce)",
                                        ).matches
                                          ? "auto"
                                          : "smooth",
                                        block: "nearest",
                                      });
                                  }}
                                >
                                  <span>{b.text}</span>
                                  <span
                                    className="bullet-state"
                                    aria-label={
                                      b.needsReview
                                        ? "Needs clarification"
                                        : b.accepted
                                          ? "Accepted"
                                          : "Proposed wording"
                                    }
                                  >
                                    {b.needsReview ? (
                                      <AlertTriangle size={12} />
                                    ) : b.accepted ? (
                                      <Check size={12} />
                                    ) : (
                                      <span className="change-marker" />
                                    )}
                                  </span>
                                  {b.pinned && (
                                    <Pin size={11} className="pin-indicator" />
                                  )}
                                </button>
                              ) : (
                                <span>{b.text}</span>
                              )}
                            </li>
                          ))}
                        </ul>
                      </div>
                    );
                  })}
              </section>
            ))}
            <section className="resume-section">
              <h3>SKILLS</h3>
              <p className="resume-skills">
                {[...new Set(included.flatMap((b) => b.skills || []))].join(
                  " · ",
                ) || "Skills represented in the selected experience above"}
              </p>
            </section>
            <section className="resume-section">
              <h3>EDUCATION</h3>
              <p className="education-line">
                <strong>Northeastern University</strong>
                <span>2022</span>
              </p>
              <p>B.S. Computer Science</p>
            </section>
          </article>
          <div className="paper-bottom">
            <Link2 size={13} />
            <span>
              Every selected achievement retains its source. Candidate
              statements are not independently verified.
            </span>
          </div>
        </div>
        <aside id="review-details" className="review-panel context-panel">
          <div className="panel-tabs" role="group" aria-label="Resume details">
            {(["changes", "evidence", "selection"] as const).map((t) => (
              <button
                key={t}
                aria-pressed={tab === t}
                className={tab === t ? "active" : ""}
                onClick={() => setTab(t)}
              >
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>
          {tab === "selection" ? (
            <div className="selection-panel">
              <div className="panel-section">
                <span className="eyebrow">MAKE ROOM FOR WHAT MATTERS</span>
                <h3>{included.length} achievements selected</h3>
                <p className="muted small">
                  Pin the essentials, reorder the story, or swap in a more
                  relevant project.
                </p>
              </div>
              {app.bullets.map((b, i) => (
                <div
                  className={`selection-row ${b.included ? "" : "omitted"}`}
                  key={b.evidenceId}
                >
                  <button
                    className="selection-title"
                    onClick={() => {
                      setSelectedId(b.evidenceId);
                      setTab("changes");
                    }}
                  >
                    <strong>{b.company}</strong>
                    <span>{b.text}</span>
                  </button>
                  <div className="selection-actions">
                    <button
                      className="icon-button"
                      disabled={historical || unsupported(b)}
                      aria-label={`${b.pinned ? "Unpin" : "Pin"} ${b.company}`}
                      aria-pressed={b.pinned}
                      onClick={() =>
                        update(b.evidenceId, {
                          pinned: !b.pinned,
                          included: true,
                        })
                      }
                    >
                      <Pin
                        size={14}
                        fill={b.pinned ? "currentColor" : "none"}
                      />
                    </button>
                    <button
                      className="icon-button"
                      disabled={historical || i === 0}
                      aria-label={`Move ${b.company} up`}
                      onClick={() => move(b.evidenceId, -1)}
                    >
                      <ArrowUp size={14} />
                    </button>
                    <button
                      className="icon-button"
                      disabled={historical || i === app.bullets.length - 1}
                      aria-label={`Move ${b.company} down`}
                      onClick={() => move(b.evidenceId, 1)}
                    >
                      <ArrowDown size={14} />
                    </button>
                    <button
                      className="inline-link"
                      disabled={
                        historical ||
                        b.pinned ||
                        (!b.included && unsupported(b))
                      }
                      onClick={() =>
                        update(b.evidenceId, { included: !b.included })
                      }
                    >
                      {b.included ? (
                        <>
                          <Minus size={12} />
                          Omit
                        </>
                      ) : (
                        <>
                          <Plus size={12} />
                          Include
                        </>
                      )}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : selected ? (
            <div className="panel-section">
              <div className="row between">
                <span className="eyebrow">
                  {selected.section === "Experience"
                    ? "WORK EXPERIENCE"
                    : "PROJECT EXPERIENCE"}
                </span>
                <Badge tone={selected.needsReview ? "amber" : "neutral"}>
                  {selected.needsReview
                    ? "Clarify"
                    : selected.accepted
                      ? "Accepted"
                      : "Proposed"}
                </Badge>
              </div>
              <h3>{selected.company}</h3>
              {tab === "changes" ? (
                <>
                  <div className="wording original">
                    <span className="small-label">ORIGINAL WORDING</span>
                    <p>{selected.original}</p>
                  </div>
                  <div className="wording proposed">
                    <span className="small-label">PROPOSED WORDING</span>
                    <p>{selected.text}</p>
                  </div>
                  {selected.original !== selected.text && (
                    <details className="word-diff">
                      <summary>Show additions and removals</summary>
                      <p>
                        <span>Removed: </span>
                        <del>{selected.original}</del>
                      </p>
                      <p>
                        <span>Added: </span>
                        <ins>{selected.text}</ins>
                      </p>
                    </details>
                  )}
                  <div className="why-change">
                    <span className="small-label">WHY THIS HELPS</span>
                    <p>{selected.reason}</p>
                  </div>
                  <div className="review-actions">
                    <button
                      className="button primary"
                      disabled={
                        historical || selected.needsReview || selected.accepted
                      }
                      onClick={() =>
                        update(selected.evidenceId, { accepted: true })
                      }
                    >
                      <Check size={14} />
                      {selected.accepted ? "Accepted" : "Accept wording"}
                    </button>
                    <button
                      className="button secondary"
                      disabled={historical}
                      onClick={() => onEdit(selected)}
                    >
                      <Pencil size={14} />
                      Edit
                    </button>
                    <button
                      className="button ghost"
                      disabled={historical}
                      onClick={() => {
                        update(selected.evidenceId, {
                          text: selected.original,
                          accepted: true,
                        });
                        onNotice(
                          "Original wording restored. Evidence concerns still need to be resolved.",
                        );
                      }}
                    >
                      <RotateCcw size={13} />
                      Revert
                    </button>
                  </div>
                  <button
                    className="source-card"
                    onClick={() => setTab("evidence")}
                  >
                    <Link2 size={16} />
                    <span>
                      <strong>
                        {selected.origin === "resume"
                          ? "Resume-derived claim"
                          : "Candidate-confirmed statement"}
                      </strong>
                      <small>View the supporting excerpt</small>
                    </span>
                    <ArrowUpRight size={14} />
                  </button>
                </>
              ) : (
                <>
                  <Badge>
                    {selected.origin === "resume"
                      ? "Source document"
                      : "Candidate statement"}
                  </Badge>
                  <blockquote className="source-quote">
                    {selected.excerpt}
                  </blockquote>
                  <p className="micro">
                    Evidence revision {selected.revision} · Preserved with this
                    version
                  </p>
                  <div className="quiet-note">
                    <p>
                      A source supports only what it says. This is
                      candidate-supplied evidence, not independent verification.
                    </p>
                  </div>
                  <button
                    className="button secondary"
                    disabled={
                      !evidence.some((e) => e.id === selected.evidenceId)
                    }
                    onClick={() => {
                      const e = evidence.find(
                        (e) => e.id === selected.evidenceId,
                      );
                      if (e) onCorrect(e);
                    }}
                  >
                    <Pencil size={14} />
                    Correct underlying evidence
                  </button>
                </>
              )}
              {selected.section === "Projects" && !historical && (
                <div className="swap-project">
                  <label htmlFor="swap-project">
                    Swap this project
                    <select
                      id="swap-project"
                      value=""
                      disabled={app.bullets.some(
                        (b) => b.company === selected.company && b.pinned,
                      )}
                      onChange={(e) => {
                        const company = e.target.value;
                        if (!company) return;
                        onChange({
                          ...app,
                          bullets: app.bullets.map((b) =>
                            b.company === selected.company
                              ? { ...b, included: false }
                              : b.company === company
                                ? { ...b, included: true }
                                : b,
                          ),
                        });
                        setSelectedId(
                          app.bullets.find((b) => b.company === company)!
                            .evidenceId,
                        );
                      }}
                    >
                      <option value="">Choose an omitted project…</option>
                      {[
                        ...new Set(
                          app.bullets
                            .filter(
                              (b) =>
                                b.section === "Projects" &&
                                !unsupported(b) &&
                                !b.included &&
                                b.company !== selected.company,
                            )
                            .map((b) => b.company),
                        ),
                      ].map((c) => (
                        <option key={c}>{c}</option>
                      ))}
                    </select>
                  </label>
                  <p className="micro">
                    Pinned projects must be unpinned before swapping.
                  </p>
                </div>
              )}
            </div>
          ) : (
            <div className="panel-section">
              <p>Select a resume bullet to inspect its evidence.</p>
            </div>
          )}
          <div className="review-panel-footer">
            <span className="acceptance-dot" />
            <span>
              {accepted} of {included.length} selected claims accepted
            </span>
            {!historical && (
              <button
                className="inline-link"
                disabled={!!problems || !!app.staleIds.length}
                onClick={() =>
                  onChange({
                    ...app,
                    bullets: app.bullets.map((b) =>
                      b.included && !b.needsReview
                        ? { ...b, accepted: true }
                        : b,
                    ),
                  })
                }
              >
                Accept all
              </button>
            )}
          </div>
        </aside>
      </div>
      <div className="export-note">
        <Printer size={15} />
        <p>
          <strong>Print-ready output.</strong> Use your browser’s “Save as PDF”
          destination. Direct PDF and DOCX downloads are available in the server
          workspace, after a real draft completes.
        </p>
      </div>
    </div>
  );
}
