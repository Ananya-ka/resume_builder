"use client";
import {
  ArrowUpRight,
  Pencil,
  Plus,
  Briefcase,
  Folder,
  AlertTriangle,
  Check,
  GraduationCap,
} from "lucide-react";
import type { Achievement, Workspace } from "@/lib/careerproof/types";
import { candidate } from "@/lib/careerproof/fixtures";
import { Badge, ContinueButton } from "./ui";
export function Profile({
  workspace,
  onEvidence,
  onEdit,
  onAdd,
  onResolve,
  onContinue,
}: {
  workspace: Workspace;
  onEvidence: (e: Achievement) => void;
  onEdit: (e: Achievement) => void;
  onAdd: () => void;
  onResolve: (id: string) => void;
  onContinue?: () => void;
}) {
  const groups = [
    ...new Set(workspace.achievements.map((e) => `${e.section}|${e.company}`)),
  ];
  const unresolved = workspace.conflicts.filter((c) => !c.resolved);
  return (
    <div className="profile-layout">
      <div className="profile-main">
        {workspace.conflicts.length > 0 && (
          <div
            className={`conflict-summary ${unresolved.length ? "" : "resolved"}`}
          >
            <div className="row">
              <span className="status-symbol">
                {unresolved.length ? (
                  <AlertTriangle size={19} />
                ) : (
                  <Check size={19} />
                )}
              </span>
              <div>
                <strong>
                  {unresolved.length
                    ? `${unresolved.length} details need your attention`
                    : "Conflicting details resolved by you"}
                </strong>
                <p>
                  {unresolved.length
                    ? "Different versions tell slightly different stories. Let’s make them agree."
                    : "Your choices are saved with the profile. Source documents stay unchanged."}
                </p>
              </div>
            </div>
            {workspace.conflicts.map((c) => (
              <button
                className="conflict-row"
                key={c.id}
                onClick={() => onResolve(c.id)}
              >
                <span>{c.title}</span>
                <span>
                  {c.resolved ? "Review choice" : "Resolve"}
                  <ArrowUpRight size={14} />
                </span>
              </button>
            ))}
          </div>
        )}
        <div className="subheading">
          <h2>Your combined experience</h2>
          <button className="button secondary" onClick={onAdd}>
            <Plus size={15} />
            Add an achievement
          </button>
        </div>
        {groups.map((group) => {
          const [section, company] = group.split("|");
          const items = workspace.achievements.filter(
            (e) => e.section === section && e.company === company,
          );
          return (
            <section className="experience-group" key={group}>
              <header>
                <div className="group-symbol">
                  {section === "Experience" ? (
                    <Briefcase size={18} />
                  ) : (
                    <Folder size={18} />
                  )}
                </div>
                <div>
                  <h3>{company}</h3>
                  <p>
                    {items[0].role} ·{" "}
                    {section === "Experience"
                      ? workspace.employmentDate
                      : "Project experience"}
                  </p>
                </div>
                <Badge>{section === "Experience" ? "Work" : "Project"}</Badge>
              </header>
              {items.map((e) => (
                <article className="achievement" key={e.id}>
                  <div className="achievement-text">
                    <span className="bullet-dot" />
                    <p>{e.text}</p>
                    <button
                      className="icon-button"
                      aria-label={`Edit achievement: ${e.text}`}
                      onClick={() => onEdit(e)}
                    >
                      <Pencil size={14} />
                    </button>
                  </div>
                  <div className="achievement-meta">
                    {e.skills.map((s) => (
                      <span className="skill-tag" key={s}>
                        {s}
                      </span>
                    ))}
                    {e.needsClarification && (
                      <Badge tone="amber">Needs clarification</Badge>
                    )}
                  </div>
                  <button
                    className="inline-link source-link"
                    onClick={() => onEvidence(e)}
                  >
                    {e.origin === "answer"
                      ? "Confirmed answer"
                      : e.origin === "user"
                        ? "Your statement"
                        : `${e.sourceIds.length} source document${e.sourceIds.length !== 1 ? "s" : ""}`}
                    <ArrowUpRight size={12} />
                  </button>
                </article>
              ))}
            </section>
          );
        })}
        {!groups.length && (
          <div className="empty-state">
            <h3>Your profile starts with a source</h3>
            <p>
              Load the sample resumes or add your own statement to explore the
              profile.
            </p>
          </div>
        )}
        {onContinue && (
          <div className="step-footer">
            <span className="micro">
              {workspace.achievements.length} achievements · {unresolved.length}{" "}
              unresolved conflicts
            </span>
            <ContinueButton
              disabled={!!unresolved.length || !workspace.achievements.length}
              onClick={onContinue}
            >
              Compare with a job
            </ContinueButton>
          </div>
        )}
      </div>
      <aside className="context-panel">
        <span className="eyebrow">CAREER PROFILE</span>
        <div className="profile-avatar">AM</div>
        <h3>{candidate.name}</h3>
        <p className="muted">
          {candidate.title}
          <br />
          {candidate.location}
        </p>
        <div className="panel-divider" />
        <h4>Skills in your evidence</h4>
        <div className="skill-cloud">
          {[...new Set(workspace.achievements.flatMap((e) => e.skills))].map(
            (s) => (
              <span key={s} className="skill-tag">
                {s}
              </span>
            ),
          )}
        </div>
        <div className="panel-divider" />
        <h4 className="row">
          <GraduationCap size={16} />
          Education
        </h4>
        <p className="small muted">{candidate.education}</p>
        <div className="quiet-note">
          <p>
            These are candidate-supplied claims,{" "}
            <strong>not independently verified facts.</strong> Every source
            stays available for review.
          </p>
        </div>
      </aside>
    </div>
  );
}
