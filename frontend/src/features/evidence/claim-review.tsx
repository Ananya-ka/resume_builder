"use client";
import { useState } from "react";
import { Check, X, Save, Link2, Tag, FileText } from "lucide-react";
import { Modal, Button } from "@/components/workspace/primitives";
import { type Catalog, type Claim, type ClaimData, catalogApi } from "./api";
export function ClaimReview({
  catalog,
  claim,
  onClose,
  onSaved,
}: {
  catalog: Catalog;
  claim: Claim;
  onClose: () => void;
  onSaved: (c: Catalog) => void;
}) {
  const [data, setData] = useState<ClaimData>(claim.data);
  const [reason, setReason] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [artifact, setArtifact] = useState(false);
  const [artifactTitle, setArtifactTitle] = useState("");
  const [artifactText, setArtifactText] = useState("");
  const [quote, setQuote] = useState("");
  const [attest, setAttest] = useState(false);
  const dirty = JSON.stringify(data) !== JSON.stringify(claim.data);
  async function save(action: string) {
    setBusy(true);
    setError("");
    try {
      onSaved(
        await catalogApi.action(catalog, claim, action, {
          reason,
          confirm_accuracy: confirmed,
          ...(action === "edit"
            ? { data }
            : action === "organize"
              ? { tags: data.tags }
              : {}),
        }),
      );
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      open
      onOpenChange={(v) => {
        if (!v && !busy) onClose();
      }}
      title="Review this claim"
      description="Approve only what accurately describes this candidate’s work."
      drawer
    >
      <div className="ec-review">
        <div className="ec-badges">
          <span>{claim.verification.replaceAll("_", " ")}</span>
          <span>{claim.approval}</span>
          <span>Revision {claim.revision}</span>
        </div>
        <p>{claim.confidence_indicator}</p>
        {!!claim.conflict_ids.length && (
          <div className="ec-warning">
            Resolve the linked contradictions before approving this claim.
          </div>
        )}
        <label>
          Claim
          <textarea
            value={data.text}
            onChange={(e) => setData({ ...data, text: e.target.value })}
            rows={4}
          />
        </label>
        <div className="ec-form-grid">
          <label>
            Project / employer
            <input
              value={data.association}
              onChange={(e) =>
                setData({ ...data, association: e.target.value })
              }
            />
          </label>
          <label>
            Role
            <input
              value={data.role}
              onChange={(e) => setData({ ...data, role: e.target.value })}
            />
          </label>
          <label>
            Dates (as supported)
            <input
              value={data.dates}
              onChange={(e) => setData({ ...data, dates: e.target.value })}
            />
          </label>
          <label>
            Work status
            <select
              value={data.temporal_status}
              onChange={(e) =>
                setData({
                  ...data,
                  temporal_status: e.target
                    .value as ClaimData["temporal_status"],
                })
              }
            >
              {["unknown", "planned", "in_progress", "completed"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
        </div>
        <label>
          Personal contribution
          <textarea
            value={data.contribution}
            onChange={(e) => setData({ ...data, contribution: e.target.value })}
            placeholder="Leave unknown unless explicitly confirmed"
            rows={2}
          />
        </label>
        <label>
          Technologies (one per line)
          <textarea
            value={data.technologies.join("\n")}
            onChange={(e) =>
              setData({
                ...data,
                technologies: e.target.value.split("\n").filter(Boolean),
              })
            }
            rows={2}
          />
        </label>
        <label>
          Metrics (one per line)
          <textarea
            value={data.metrics.join("\n")}
            onChange={(e) =>
              setData({
                ...data,
                metrics: e.target.value.split("\n").filter(Boolean),
              })
            }
            rows={2}
          />
        </label>
        <label>
          Organize with tags (comma separated)
          <input
            value={data.tags.join(", ")}
            onChange={(e) =>
              setData({
                ...data,
                tags: e.target.value
                  .split(",")
                  .map((s) => s.trim())
                  .filter(Boolean),
              })
            }
          />
        </label>
        <h3>
          <FileText size={16} /> Supporting sources
        </h3>
        {claim.sources.map((s, i) => (
          <div className="ec-source" key={`${s.id}-${i}`}>
            <strong>{s.filename}</strong>
            <small>
              {s.kind} · claim revision {s.revision}
              {s.start !== null
                ? ` · text offsets ${s.start}–${s.end}`
                : " · exact location unavailable"}
            </small>
            <blockquote>{s.quote}</blockquote>
            <details>
              <summary>Source fingerprint</summary>
              <code>{s.sha256}</code>
            </details>
          </div>
        ))}
        {!claim.sources.length && (
          <p>
            Candidate-confirmed detail. Inspect the activity history for the
            confirmation.
          </p>
        )}
        <label>
          Reason for this decision
          <input
            required
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Explain what you checked or corrected"
          />
        </label>
        <label className="ec-check">
          <input
            type="checkbox"
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
          />{" "}
          I confirm that these facts, attribution and personal contribution are
          accurate.
        </label>
        {error && (
          <p role="alert" className="ec-error">
            {error}
          </p>
        )}
        <div className="ec-actions">
          <Button
            disabled={busy || !reason.trim() || !confirmed || !dirty}
            onClick={() => save("edit")}
          >
            <Save size={14} /> Save correction
          </Button>
          <Button
            disabled={
              busy ||
              !reason.trim() ||
              dirty ||
              !confirmed ||
              !!claim.conflict_ids.length
            }
            onClick={() => save("approve")}
          >
            <Check size={14} /> Approve
          </Button>
          <Button
            disabled={busy || !reason.trim()}
            onClick={() => save("reject")}
          >
            <X size={14} /> Reject
          </Button>
          <Button
            disabled={busy || !reason.trim()}
            onClick={() => save("organize")}
          >
            <Tag size={14} /> Save tags only
          </Button>
        </div>
        <small>
          Corrections create a new pending revision. Approval is a separate
          decision. Historical sources remain attached to their original
          revision.
        </small>
        <button className="ec-link" onClick={() => setArtifact(!artifact)}>
          <Link2 size={14} /> Attach supporting artifact text
        </button>
        {artifact && (
          <div className="ec-artifact">
            <p>
              Paste an excerpt from your own test report, project document or
              other artifact. This records candidate-attested support, not
              independent authenticity verification.
            </p>
            <label>
              Artifact title
              <input
                value={artifactTitle}
                onChange={(e) => setArtifactTitle(e.target.value)}
              />
            </label>
            <label>
              Artifact text
              <textarea
                value={artifactText}
                onChange={(e) => setArtifactText(e.target.value)}
              />
            </label>
            <label>
              Exact supporting quote
              <textarea
                value={quote}
                onChange={(e) => setQuote(e.target.value)}
              />
            </label>
            <label className="ec-check">
              <input
                type="checkbox"
                checked={attest}
                onChange={(e) => setAttest(e.target.checked)}
              />{" "}
              This quote supports this exact claim.
            </label>
            <Button
              disabled={
                busy ||
                !attest ||
                !quote.trim() ||
                !artifactText.trim() ||
                !artifactTitle.trim()
              }
              onClick={async () => {
                setBusy(true);
                try {
                  onSaved(
                    await catalogApi.artifact(catalog, claim, {
                      title: artifactTitle,
                      text: artifactText,
                      quote,
                      attest_support: attest,
                    }),
                  );
                  onClose();
                } catch (e) {
                  setError(
                    e instanceof Error
                      ? e.message
                      : "Could not attach artifact",
                  );
                } finally {
                  setBusy(false);
                }
              }}
            >
              Attach excerpt
            </Button>
          </div>
        )}
        <h3>Decision history</h3>
        {catalog.events
          .filter((e) => e.claim_id === claim.id)
          .map((e) => (
            <details key={e.id}>
              <summary>
                {e.action.replaceAll("_", " ")} ·{" "}
                {e.created_at ? new Date(e.created_at).toLocaleString() : ""}
              </summary>
              <pre>{JSON.stringify(e.details, null, 2)}</pre>
            </details>
          ))}
      </div>
    </Modal>
  );
}
