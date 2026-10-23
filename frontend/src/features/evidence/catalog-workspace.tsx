"use client";
import { useState, useEffect, useRef } from "react";
import {
  Layers,
  Search,
  Upload,
  CheckCircle2,
  GitMerge,
  ArrowUpRight,
  RefreshCw,
  Plus,
  ShieldCheck,
} from "lucide-react";
import { api, validateFiles, type ServerResume } from "@/lib/careerproof/api";
import {
  catalogApi,
  type Catalog,
  type CatalogSummary,
  type Claim,
} from "./api";
import { ClaimReview } from "./claim-review";
import { ConflictReview } from "./conflict-review";
import "./catalog.css";
export default function CatalogWorkspace() {
  const [catalogs, setCatalogs] = useState<CatalogSummary[]>([]);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [resumes, setResumes] = useState<ServerResume[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [files, setFiles] = useState<File[]>([]);
  const [same, setSame] = useState(false);
  const [name, setName] = useState("");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [review, setReview] = useState<Claim | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [ingest, setIngest] = useState(false);
  const request = useRef(0);
  useEffect(() => {
    let cancelled = false;
    Promise.all([catalogApi.list(), api<ServerResume[]>("/resumes")])
      .then(async ([cs, rs]) => {
        if (cancelled) return;
        setCatalogs(cs);
        setResumes(rs);
        const preferred = Number(
          localStorage.getItem("careerproof-catalog-id"),
        );
        const first = cs.find((c) => c.id === preferred) || cs[0];
        if (first) {
          const c = await catalogApi.get(first.id);
          if (!cancelled) setCatalog(c);
        }
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);
  function saved(c: Catalog) {
    setCatalog(c);
    setCatalogs((cs) =>
      [
        ...cs.filter((x) => x.id !== c.id),
        { id: c.id, name: c.name, revision: c.revision },
      ].sort((a, b) => a.id - b.id),
    );
    setNotice("Saved to your evidence catalog.");
  }
  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
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
  async function refresh() {
    await run(async () => {
      const [cs, rs] = await Promise.all([
        catalogApi.list(),
        api<ServerResume[]>("/resumes"),
      ]);
      setCatalogs(cs);
      setResumes(rs);
      if (catalog) setCatalog(await catalogApi.get(catalog.id));
    });
  }
  async function switchCatalog(id: number) {
    const token = ++request.current;
    setReview(null);
    setError("");
    setLoading(true);
    try {
      const c = await catalogApi.get(id);
      if (token === request.current) {
        setCatalog(c);
        localStorage.setItem("careerproof-catalog-id", String(id));
      }
    } catch (e) {
      if (token === request.current)
        setError(e instanceof Error ? e.message : "Could not load catalog");
    } finally {
      if (token === request.current) setLoading(false);
    }
  }
  async function importSources() {
    if (!catalog || !same) return;
    await run(async () => {
      let ids = selected;
      if (files.length) {
        const validation = validateFiles(files);
        if (validation) throw new Error(validation);
        const form = new FormData();
        files.forEach((f) => form.append("files", f));
        const uploaded = await api<ServerResume[]>(
          "/resumes/upload-batch",
          "POST",
          form,
        );
        ids = uploaded.map((r) => r.id);
        setSelected(ids);
        setFiles([]);
        setNotice("Sources uploaded. Waiting for extraction…");
        let ready = false;
        for (let i = 0; i < 60; i++) {
          const rs = await api<ServerResume[]>("/resumes");
          setResumes(rs);
          const current = rs.filter((r) => ids.includes(r.id));
          const failed = current.find((r) =>
            ["failed", "needs_ocr"].includes(
              r.parsed_raw?.parsing_status || "",
            ),
          );
          if (failed)
            throw new Error(
              `${failed.name}: ${failed.parsed_raw?.error || "Needs source review"}`,
            );
          if (
            current.length === ids.length &&
            current.every((r) => r.parsed_raw?.parsing_status === "ready")
          ) {
            ready = true;
            break;
          }
          await new Promise((r) => setTimeout(r, 2000));
        }
        if (!ready)
          throw new Error(
            "Parsing is still running. Your uploads are saved. Refresh and import the selected sources when ready.",
          );
      }
      if (!ids.length || ids.length > 3)
        throw new Error("Select one to three parsed sources.");
      saved(await catalogApi.import(catalog, ids));
      setIngest(false);
      setSelected([]);
      setSame(false);
    });
  }
  const open = catalog?.conflicts.filter((c) => c.state === "open") || [];
  const claims =
    catalog?.claims.filter(
      (c) =>
        (filter === "all" ||
          c.approval === filter ||
          c.verification === filter) &&
        [
          c.data.text,
          c.data.association,
          ...c.data.technologies,
          ...c.data.tags,
        ]
          .join(" ")
          .toLowerCase()
          .includes(search.toLowerCase()),
    ) || [];
  return (
    <section className="ec-workspace">
      <header className="ec-header">
        <div>
          <span className="ec-kicker">
            <Layers size={15} /> CAREERPROOF / EVIDENCE INTELLIGENCE
          </span>
          <h1>Everything you can stand behind.</h1>
          <p>
            Your experience, organized into sourced claims. You decide what’s
            accurate.
          </p>
        </div>
        <a href="/">
          Resume workspace <ArrowUpRight size={15} />
        </a>
      </header>
      <div className="ec-top">
        <div className="ec-select">
          <label htmlFor="catalog-choice">Candidate catalog</label>
          <select
            id="catalog-choice"
            value={catalog?.id || ""}
            disabled={busy || loading}
            onChange={(e) => switchCatalog(Number(e.target.value))}
          >
            <option value="" disabled>
              Select catalog
            </option>
            {catalogs.map((c) => (
              <option value={c.id} key={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            run(async () => {
              const c = await catalogApi.create(name);
              saved(c);
              setName("");
              localStorage.setItem("careerproof-catalog-id", String(c.id));
            });
          }}
        >
          <input
            aria-label="New candidate catalog name"
            placeholder="New candidate name"
            value={name}
            maxLength={150}
            onChange={(e) => setName(e.target.value)}
          />
          <button disabled={busy || !name.trim()}>
            <Plus size={15} /> Create catalog
          </button>
        </form>
        <button disabled={busy} aria-label="Refresh catalog" onClick={refresh}>
          <RefreshCw size={16} />
        </button>
      </div>
      {error && (
        <div className="ec-error" role="alert">
          {error}{" "}
          <button onClick={refresh} disabled={busy}>
            Refresh
          </button>
        </div>
      )}
      {notice && (
        <p role="status" className="ec-notice">
          {notice}
        </p>
      )}
      {loading ? (
        <div className="ec-loading" role="status">
          Loading your catalog…
        </div>
      ) : !catalog ? (
        <div className="ec-empty">
          <Layers size={35} />
          <h2>Start with your experience.</h2>
          <p>
            Create a candidate catalog above, then import two or three resume
            versions. No job description required.
          </p>
        </div>
      ) : (
        <>
          <div className="ec-stats">
            {[
              {
                icon: Layers,
                title: "Source-linked claims",
                value: catalog.claims.length,
              },
              {
                icon: CheckCircle2,
                title: "Approved by you",
                value: catalog.claims.filter(
                  (c) => c.approval === "approved" && !c.conflict_ids.length,
                ).length,
              },
              {
                icon: GitMerge,
                title: "Needs clarification",
                value: open.length,
              },
            ].map((s) => (
              <div key={s.title}>
                <s.icon size={19} />
                <strong>{s.value}</strong>
                <span>{s.title}</span>
              </div>
            ))}
            <button
              className="ec-primary"
              disabled={busy}
              onClick={() => setIngest(!ingest)}
            >
              <Upload size={17} /> Import resume versions
            </button>
          </div>
          {ingest && (
            <section className="ec-ingestion">
              <h2>Bring your resume versions together</h2>
              <p>
                Upload two or three files, or select existing parsed sources.
                Each candidate gets a separate catalog. You can also add one
                source later.
              </p>
              <label className="ec-upload">
                <Upload size={20} /> Choose PDF, DOCX or TXT files
                <input
                  type="file"
                  aria-label="Upload resumes"
                  accept=".pdf,.docx,.txt"
                  multiple
                  disabled={busy}
                  onChange={(e) => {
                    setFiles(Array.from(e.target.files || []));
                    setSelected([]);
                  }}
                />
              </label>
              {files.length > 0 && (
                <p>{files.map((f) => f.name).join(" · ")}</p>
              )}
              {!files.length && (
                <div className="ec-source-options">
                  {resumes.map((r) => (
                    <label key={r.id}>
                      <input
                        type="checkbox"
                        disabled={
                          busy ||
                          r.parsed_raw?.parsing_status !== "ready" ||
                          (!selected.includes(r.id) && selected.length >= 3)
                        }
                        checked={selected.includes(r.id)}
                        onChange={() =>
                          setSelected((s) =>
                            s.includes(r.id)
                              ? s.filter((id) => id !== r.id)
                              : [...s, r.id],
                          )
                        }
                      />
                      <span>
                        {r.name}
                        <small>
                          {r.parsed_raw?.parsing_status || "unknown"}
                        </small>
                      </span>
                    </label>
                  ))}
                  {!resumes.length && <p>No uploaded sources yet.</p>}
                </div>
              )}
              <label className="ec-check">
                <input
                  type="checkbox"
                  checked={same}
                  onChange={(e) => setSame(e.target.checked)}
                />{" "}
                These sources belong to the same candidate. Their claims still
                need review.
              </label>
              <button
                className="ec-primary"
                disabled={
                  busy ||
                  !same ||
                  (!files.length && !selected.length) ||
                  files.length > 3
                }
                onClick={importSources}
              >
                {busy ? "Processing sources…" : "Extract and merge evidence"}
              </button>
            </section>
          )}
          {!!open.length && (
            <div className="ec-conflict-section">
              <div className="ec-section-title">
                <h2>Let’s clarify the differences.</h2>
                <span>{open.length} open · no guesses</span>
              </div>
              <div className="ec-conflict-grid">
                {open.map((c) => (
                  <ConflictReview
                    key={`${c.id}-${catalog.revision}`}
                    catalog={catalog}
                    conflict={c}
                    onSaved={saved}
                  />
                ))}
              </div>
            </div>
          )}
          <div className="ec-toolbar">
            <label>
              <Search size={16} />
              <input
                aria-label="Search catalog claims"
                placeholder="Search claims, technologies, projects or tags…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </label>
            <select
              aria-label="Filter claims"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            >
              {[
                "all",
                "pending",
                "approved",
                "rejected",
                "extracted",
                "user_confirmed",
                "artifact_supported",
                "unresolved",
              ].map((v) => (
                <option key={v} value={v}>
                  {v.replaceAll("_", " ")}
                </option>
              ))}
            </select>
            <span>{claims.length} claims</span>
          </div>
          <div className="ec-claim-grid">
            {claims.map((c) => (
              <button
                className="ec-claim"
                key={c.id}
                onClick={() => setReview(c)}
              >
                <div className="ec-claim-top">
                  <span>{c.data.kind}</span>
                  <span className={`ec-state ${c.verification}`}>
                    {c.verification.replaceAll("_", " ")}
                  </span>
                </div>
                <h3>{c.data.association}</h3>
                <p>{c.data.text}</p>
                <div className="ec-badges">
                  {c.data.technologies.map((t) => (
                    <span key={t}>{t}</span>
                  ))}
                  {c.data.tags.map((t) => (
                    <span key={t}>#{t}</span>
                  ))}
                </div>
                <div className="ec-card-foot">
                  <span>
                    {c.sources.length} source references · rev {c.revision}
                  </span>
                  <strong>{c.approval}</strong>
                </div>
              </button>
            ))}
          </div>
          {!claims.length && (
            <div className="ec-empty">
              <ShieldCheck size={30} />
              <h2>
                {catalog.claims.length
                  ? "No matching claims"
                  : "Your evidence starts here."}
              </h2>
              <p>
                {catalog.claims.length
                  ? "Try another search or status."
                  : "Import your resume versions to see sourced claims and possible contradictions."}
              </p>
            </div>
          )}
          <footer className="ec-footer">
            <ShieldCheck size={14} /> Extracted ≠ approved. Artifact support is
            candidate-attested, not independent verification.
            <span>Catalog revision {catalog.revision}</span>
          </footer>
        </>
      )}
      {review && catalog && (
        <ClaimReview
          key={`${review.id}-${catalog.revision}`}
          catalog={catalog}
          claim={catalog.claims.find((c) => c.id === review.id) || review}
          onClose={() => setReview(null)}
          onSaved={saved}
        />
      )}
    </section>
  );
}
