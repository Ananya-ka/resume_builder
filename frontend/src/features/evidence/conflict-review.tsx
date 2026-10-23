"use client";
import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import { type Catalog, type Conflict, catalogApi } from "./api";
export function ConflictReview({
  catalog,
  conflict,
  onSaved,
}: {
  catalog: Catalog;
  conflict: Conflict;
  onSaved: (c: Catalog) => void;
}) {
  const [choice, setChoice] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <article className="ec-conflict">
      <span className="ec-kicker">
        <AlertTriangle size={14} /> POSSIBLE{" "}
        {conflict.kind.replaceAll("_", " ").toUpperCase()} CONFLICT
      </span>
      <h3>{conflict.question}</h3>
      <p>{conflict.benefit}</p>
      {conflict.claim_ids.map((id) => {
        const c = catalog.claims.find((c) => c.id === id);
        return (
          <label className="ec-alternative" key={id}>
            <input
              type="radio"
              name={`conflict-${conflict.id}`}
              value={id}
              checked={choice === String(id)}
              onChange={() => setChoice(String(id))}
            />
            <span>
              <strong>
                {c?.data.association} · {c?.data.role}
              </strong>
              {c?.data.text}
              <small>{c?.sources.map((s) => s.filename).join(" · ")}</small>
            </span>
          </label>
        );
      })}
      <label className="ec-alternative">
        <input
          type="radio"
          name={`conflict-${conflict.id}`}
          checked={choice === "both"}
          onChange={() => setChoice("both")}
        />
        <span>Both are accurate and describe separate work</span>
      </label>
      <label>
        Clarification
        <input
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="What distinguishes these facts, or which source was wrong?"
        />
      </label>
      <button
        disabled={busy || !choice || !reason.trim()}
        onClick={async () => {
          setBusy(true);
          setError("");
          try {
            onSaved(
              await catalogApi.resolve(
                catalog,
                conflict,
                choice === "both" ? "keep_both" : "select",
                choice === "both" ? null : Number(choice),
                reason,
              ),
            );
          } catch (e) {
            setError(
              e instanceof Error ? e.message : "Could not save clarification",
            );
          } finally {
            setBusy(false);
          }
        }}
      >
        Save clarification
      </button>
      {error && (
        <p role="alert" className="ec-error">
          {error}
        </p>
      )}
      <small>
        Selecting an alternative rejects the other. The remaining claim still
        needs approval.
      </small>
    </article>
  );
}
