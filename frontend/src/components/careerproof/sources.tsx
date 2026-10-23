"use client";
import { useRef, useState } from "react";
import {
  UploadCloud,
  FileText,
  Check,
  X,
  ArrowUpRight,
  Shield,
  Layers,
  Plus,
  AlertTriangle,
  RefreshCw,
} from "lucide-react";
import type { Source } from "@/lib/careerproof/types";
import { validateFiles } from "@/lib/careerproof/api";
import { Badge, ContinueButton } from "./ui";
export function Sources({
  sources,
  onSample,
  onContinue,
  onRemove,
  onInspect,
  onNotes,
  onServer,
}: {
  sources: Source[];
  onSample: () => void;
  onContinue: () => void;
  onRemove: (id: string) => void;
  onInspect: (source: Source) => void;
  onNotes: (text: string) => void;
  onServer: () => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<
    { file: File; text?: string; error?: string }[]
  >([]);
  const [error, setError] = useState("");
  const [drag, setDrag] = useState(false);
  const [notes, setNotes] = useState("");
  async function add(incoming: File[]) {
    const issue = validateFiles(incoming, files.length);
    if (issue) {
      setError(issue);
      return;
    }
    setError("");
    const rows = await Promise.all(
      incoming.map(async (file) => {
        if (/\.txt$/i.test(file.name)) {
          try {
            return { file, text: await file.text() };
          } catch {
            return {
              file,
              error: "Could not read this file. Remove it and choose it again.",
            };
          }
        }
        return { file };
      }),
    );
    setFiles((prev) => [...prev, ...rows]);
  }
  return (
    <div className="sources-layout">
      <section className="main-surface source-main">
        <div className="surface-title">
          <span className="step-kicker">01 / YOUR SOURCE MATERIAL</span>
          <Badge>Up to 3 resumes</Badge>
        </div>
        <h2>Start with what you’ve already done.</h2>
        <p className="muted leading">
          Different resumes tell different parts of your story. Bring them
          together, then decide what belongs in this application.
        </p>
        <div
          className={`dropzone ${drag ? "dragging" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDrag(true);
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDrag(false);
            void add(Array.from(e.dataTransfer.files));
          }}
        >
          <div className="upload-symbol">
            <UploadCloud size={27} strokeWidth={1.4} />
          </div>
          <h3>Drop your resumes here</h3>
          <p>
            or{" "}
            <button
              className="text-button"
              onClick={() => input.current?.click()}
            >
              browse files
            </button>{" "}
            from your computer
          </p>
          <span className="micro">PDF, DOCX, or TXT · Up to 10 MB each</span>
          <input
            ref={input}
            type="file"
            multiple
            accept=".pdf,.docx,.txt"
            className="visually-hidden"
            aria-label="Choose resume files"
            onChange={(e) => {
              void add(Array.from(e.target.files || []));
              e.target.value = "";
            }}
          />
        </div>
        {error && (
          <p className="notice error" role="alert">
            <AlertTriangle size={16} />
            {error}
          </p>
        )}
        {files.length > 0 && (
          <div className="personal-files">
            <p className="notice">
              <Shield size={17} />
              These files are in memory only. This demo does not parse personal
              PDFs or DOCX files. Use the server workspace to explicitly upload
              and parse them.
            </p>
            {files.map((row, i) => (
              <div className="file-row" key={`${row.file.name}-${i}`}>
                <FileText size={20} />
                <div className="file-content">
                  <strong>{row.file.name}</strong>
                  <span>
                    {row.error ||
                      (row.text
                        ? "Text read locally · not parsed into a profile"
                        : "Ready for server upload · not parsed")}
                  </span>
                  {row.text && (
                    <details>
                      <summary>Preview text read from file</summary>
                      <pre>{row.text}</pre>
                    </details>
                  )}
                </div>
                {row.error && (
                  <button
                    className="icon-button"
                    aria-label={`Retry reading ${row.file.name}`}
                    onClick={async () => {
                      try {
                        const text = await row.file.text();
                        setFiles((prev) =>
                          prev.map((r, n) =>
                            n === i ? { file: r.file, text } : r,
                          ),
                        );
                      } catch {
                        setError(
                          "Reading failed. Try choosing the file again.",
                        );
                      }
                    }}
                  >
                    <RefreshCw size={16} />
                  </button>
                )}
                <button
                  className="icon-button"
                  aria-label={`Remove ${row.file.name}`}
                  onClick={() =>
                    setFiles((prev) => prev.filter((_, n) => n !== i))
                  }
                >
                  <X size={16} />
                </button>
              </div>
            ))}
            <button className="button secondary" onClick={onServer}>
              Open server workspace <ArrowUpRight size={15} />
            </button>
          </div>
        )}
        {!sources.length ? (
          <div className="sample-strip">
            <div className="sample-icon">
              <Layers size={19} />
            </div>
            <div>
              <strong>Take a look around first.</strong>
              <p>Three fictional resumes. A few gaps. A stronger story.</p>
            </div>
            <button className="button secondary" onClick={onSample}>
              Try sample resumes <ArrowUpRight size={15} />
            </button>
          </div>
        ) : (
          <div className="source-files">
            <div className="list-label">
              <span>SELECTED SOURCES</span>
              <span>{sources.length} / 3</span>
            </div>
            {sources.map((source) => (
              <div className="file-row" key={source.id}>
                <div className="file-icon">
                  <FileText size={21} />
                </div>
                <div className="file-content">
                  <strong>{source.name}</strong>
                  <span>{source.size} · Fictional sample document</span>
                  <button
                    className="inline-link"
                    onClick={() => onInspect(source)}
                  >
                    View source text <ArrowUpRight size={12} />
                  </button>
                </div>
                <Badge tone="teal">
                  <Check size={11} />
                  Sample loaded
                </Badge>
                <button
                  className="icon-button"
                  aria-label={`Remove ${source.name}`}
                  onClick={() => onRemove(source.id)}
                >
                  <X size={16} />
                </button>
              </div>
            ))}
          </div>
        )}
        <details className="notes-details">
          <summary>
            <Plus size={15} /> Add project notes{" "}
            <span className="muted">Optional</span>
          </summary>
          <label className="field-label" htmlFor="project-notes">
            Anything your resumes leave out?
          </label>
          <textarea
            id="project-notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Describe the project and your own contribution. You can attach it to the right project in your profile."
            rows={3}
          />
          <button
            className="button secondary"
            disabled={!notes.trim()}
            onClick={() => {
              onNotes(notes.trim());
              setNotes("");
            }}
          >
            Add to profile as your statement
          </button>
        </details>
        <div className="step-footer">
          <span className="micro">
            <Shield size={13} />
            Uploaded files stay in memory
          </span>
          <ContinueButton disabled={!sources.length} onClick={onContinue}>
            Review combined profile
          </ContinueButton>
        </div>
      </section>
      <aside className="context-panel source-guide">
        <span className="eyebrow">A STRONGER START</span>
        <h3>
          One career.
          <br />
          More of the picture.
        </h3>
        <p className="muted">
          We’ll help you bring the useful details together. You stay in control
          of what they mean.
        </p>
        <ol className="guide-list">
          <li>
            <span>1</span>
            <div>
              <strong>Gather the evidence</strong>
              <p>Keep the original words and where they came from.</p>
            </div>
          </li>
          <li>
            <span>2</span>
            <div>
              <strong>Make the details agree</strong>
              <p>Review conflicting dates or project attribution yourself.</p>
            </div>
          </li>
          <li>
            <span>3</span>
            <div>
              <strong>Find the missing context</strong>
              <p>Answer up to four focused questions about your work.</p>
            </div>
          </li>
        </ol>
        <div className="quiet-note">
          <Shield size={19} />
          <p>
            A clearer story.
            <br />
            <strong>Never a made-up one.</strong>
          </p>
        </div>
      </aside>
    </div>
  );
}
