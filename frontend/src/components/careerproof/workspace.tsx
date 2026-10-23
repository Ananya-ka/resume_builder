"use client";
import { useEffect, useState } from "react";
import { LiveWorkspace } from "./live-workspace";
import { Sources } from "./sources";
import { Profile } from "./profile";
import { JobMatch } from "./job-match";
import { Questions } from "./questions";
import { Review } from "./review";
import { Badge, Dialog, SectionHeading } from "./ui";
import { emptyWorkspace, loadSamples } from "@/lib/careerproof/fixtures";
import {
  readDemo,
  saveDemo,
  newApplication,
  replaceApplication,
  correctEvidence,
  recordAnswer,
  draftBullets,
} from "@/lib/careerproof/demo-service";
import {
  STEPS,
  type Workspace,
  type Application,
  type Achievement,
  type Step,
} from "@/lib/careerproof/types";

export default function CareerWorkspace() {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [activeId, setActiveId] = useState("");
  const [server, setServer] = useState(false);
  const [notice, setNotice] = useState("");
  const [inspect, setInspect] = useState<{
    title: string;
    text: string;
  } | null>(null);
  const [editing, setEditing] = useState<Achievement | null>(null);
  const [conflictId, setConflictId] = useState<string | null>(null);
  useEffect(() => {
    let restored: Workspace;
    try {
      restored = readDemo() || emptyWorkspace();
    } catch {
      restored = emptyWorkspace();
    }
    if (!restored.applications.length)
      restored = { ...restored, applications: [newApplication()] };
    setWorkspace(restored);
    setActiveId(restored.applications[0].id);
  }, []);
  useEffect(() => {
    if (workspace) {
      try {
        saveDemo(workspace);
      } catch {
        setNotice(
          "Browser storage is unavailable. Keep this tab open to retain your demo changes.",
        );
      }
    }
  }, [workspace]);
  if (!workspace)
    return <main className="workspace-content">Loading demo workspace…</main>;
  const app =
    workspace.applications.find((a) => a.id === activeId) ||
    workspace.applications[0];
  function update(a: Application) {
    setWorkspace((w) => w && replaceApplication(w, a));
  }
  function go(step: Step) {
    update({ ...app, step });
  }
  function addEvidence(text = "") {
    setEditing({
      id: crypto.randomUUID(),
      text,
      company: "",
      role: "",
      section: "Projects",
      skills: [],
      sourceIds: [],
      excerpt: text,
      origin: "user",
      depth: "unspecified",
      revision: 1,
    });
  }
  function review() {
    update({
      ...app,
      step: 4,
      profileDate: workspace!.employmentDate,
      sourceIds: workspace!.sources.map((s) => s.id),
      bullets: draftBullets(workspace!.achievements, app.jd),
      staleIds: [],
    });
  }
  const conflict = workspace.conflicts.find((c) => c.id === conflictId);
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">CareerProof</div>
        <div className="sidebar-section-label">YOUR WORKSPACE</div>
        <nav aria-label="Resume steps">
          {STEPS.map((step, index) => (
            <button
              key={step}
              className={!server && app.step === index ? "active" : ""}
              onClick={() => {
                setServer(false);
                go(index as Step);
              }}
            >
              {String(index + 1).padStart(2, "0")} · {step}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <strong>Built on your evidence</strong>
          <p>
            Explore with fictional resumes. Demo changes stay in this browser.
          </p>
        </div>
        <div className="sidebar-bottom">
          <button onClick={() => setServer(!server)}>
            {server ? "Back to demo" : "Open server workspace"}
          </button>
        </div>
      </aside>
      <div className="workspace-shell">
        <header className="topbar">
          <strong>{server ? "Server workspace" : "Demo workspace"}</strong>
          <Badge tone="teal">
            {server ? "Connected application" : "Interactive sample"}
          </Badge>
        </header>
        <main className="workspace-content" id="main-content">
          {notice && (
            <p role="status">
              {notice}{" "}
              <button className="inline-link" onClick={() => setNotice("")}>
                Dismiss
              </button>
            </p>
          )}
          {server ? (
            <LiveWorkspace />
          ) : (
            <>
              <SectionHeading
                eyebrow="YOUR EXPERIENCE, CLEARLY TOLD"
                title={STEPS[app.step]}
                description="Build a resume you can stand behind."
                action={
                  <button
                    className="button secondary"
                    onClick={() => {
                      const next = newApplication();
                      setWorkspace({
                        ...workspace,
                        applications: [...workspace.applications, next],
                      });
                      setActiveId(next.id);
                    }}
                  >
                    New application
                  </button>
                }
              />
              {workspace.applications.length > 1 && (
                <label>
                  Application{" "}
                  <select
                    value={app.id}
                    onChange={(e) => setActiveId(e.target.value)}
                  >
                    {workspace.applications.map((a, i) => (
                      <option key={a.id} value={a.id}>
                        {a.company || `Application ${i + 1}`} · v{a.version}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {app.step === 0 && (
                <Sources
                  sources={workspace.sources}
                  onSample={() => setWorkspace(loadSamples(workspace))}
                  onContinue={() => go(1)}
                  onRemove={(id) =>
                    setWorkspace({
                      ...workspace,
                      sources: workspace.sources.filter((s) => s.id !== id),
                    })
                  }
                  onInspect={(s) => setInspect({ title: s.name, text: s.text })}
                  onNotes={(text) => addEvidence(text)}
                  onServer={() => setServer(true)}
                />
              )}
              {app.step === 1 && (
                <Profile
                  workspace={workspace}
                  onEvidence={(e) =>
                    setInspect({ title: e.company, text: e.excerpt || e.text })
                  }
                  onEdit={setEditing}
                  onAdd={() => addEvidence()}
                  onResolve={setConflictId}
                  onContinue={() => go(2)}
                />
              )}
              {app.step === 2 && (
                <JobMatch
                  app={app}
                  evidence={workspace.achievements}
                  onChange={update}
                  onEvidence={(e) =>
                    setInspect({ title: e.company, text: e.text })
                  }
                  onContinue={() => go(3)}
                />
              )}
              {app.step === 3 && (
                <Questions
                  key={app.id}
                  app={app}
                  onAnswer={(answer) =>
                    setWorkspace((w) => w && recordAnswer(w, app.id, answer))
                  }
                  onAddEvidence={(e) =>
                    setWorkspace(
                      (w) =>
                        w && {
                          ...w,
                          achievements: [
                            ...w.achievements.filter((a) => a.id !== e.id),
                            e,
                          ],
                        },
                    )
                  }
                  onContinue={review}
                />
              )}
              {app.step === 4 && (
                <Review
                  app={app}
                  evidence={workspace.achievements}
                  onChange={update}
                  onEdit={(b) => {
                    const e = workspace.achievements.find(
                      (a) => a.id === b.evidenceId,
                    );
                    if (e) setEditing(e);
                  }}
                  onCorrect={setEditing}
                  onNewVersion={() => {
                    const next = {
                      ...app,
                      id: crypto.randomUUID(),
                      status: "draft" as const,
                      version: app.version + 1,
                      staleIds: [],
                      bullets: draftBullets(workspace.achievements, app.jd),
                    };
                    setWorkspace({
                      ...workspace,
                      applications: [...workspace.applications, next],
                    });
                    setActiveId(next.id);
                  }}
                  onSubmit={() => update({ ...app, status: "submitted" })}
                  onNotice={setNotice}
                />
              )}
            </>
          )}
        </main>
      </div>
      {inspect && (
        <Dialog title={inspect.title} onClose={() => setInspect(null)}>
          <p style={{ whiteSpace: "pre-wrap" }}>{inspect.text}</p>
        </Dialog>
      )}
      {editing && (
        <Dialog title="Edit evidence" onClose={() => setEditing(null)}>
          <label>
            Employer or project
            <input
              value={editing.company}
              onChange={(e) =>
                setEditing({ ...editing, company: e.target.value })
              }
            />
          </label>
          <label>
            Your role
            <input
              value={editing.role}
              onChange={(e) => setEditing({ ...editing, role: e.target.value })}
            />
          </label>
          <label>
            What you did
            <textarea
              rows={5}
              value={editing.text}
              onChange={(e) => setEditing({ ...editing, text: e.target.value })}
            />
          </label>
          <button
            className="button primary"
            disabled={!editing.text.trim() || !editing.company.trim()}
            onClick={() => {
              setWorkspace(
                workspace.achievements.some((e) => e.id === editing.id)
                  ? correctEvidence(workspace, editing.id, editing)
                  : {
                      ...workspace,
                      achievements: [...workspace.achievements, editing],
                    },
              );
              setEditing(null);
            }}
          >
            Save evidence
          </button>
        </Dialog>
      )}
      {conflict && (
        <Dialog title={conflict.title} onClose={() => setConflictId(null)}>
          <p>{conflict.detail}</p>
          {conflict.options.map((option) => (
            <button
              className="button secondary"
              key={option}
              onClick={() => {
                const next = conflict.achievementId
                  ? correctEvidence(workspace, conflict.achievementId, {
                      company: option,
                    })
                  : { ...workspace, employmentDate: option };
                setWorkspace({
                  ...next,
                  conflicts: next.conflicts.map((c) =>
                    c.id === conflict.id ? { ...c, resolved: option } : c,
                  ),
                });
                setConflictId(null);
              }}
            >
              {option}
            </button>
          ))}
        </Dialog>
      )}
    </div>
  );
}
