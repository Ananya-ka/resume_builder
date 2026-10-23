"use client";
import { useState } from "react";
import {
  Mail,
  FileText,
  HelpCircle,
  Copy,
  Check,
  ShieldCheck,
  Sparkles,
  ExternalLink,
  AlertCircle,
  ArrowRight,
  Zap,
  Rocket
} from "lucide-react";
import {
  type OutreachPack,
  type ColdInMail,
  type GroundedCoverLetter,
  type ScreeningAnswer
} from "@/lib/careerproof/api";
import { Badge } from "./ui";

export function OutreachView({ pack }: { pack: OutreachPack }) {
  const [activeTab, setActiveTab] = useState<"inmail" | "cover_letter" | "screening">("inmail");
  const [copiedItem, setCopiedItem] = useState<string | null>(null);

  function copyText(key: string, text: string) {
    void navigator.clipboard.writeText(text);
    setCopiedItem(key);
    setTimeout(() => {
      setCopiedItem(null);
    }, 2200);
  }

  const isLaunch = pack.mode === "launch";

  return (
    <div className="objection-engine-panel" style={{ marginTop: 16 }}>
      {/* Header */}
      <div className="objection-engine-header">
        <div className="objection-header-left">
          <div
            className="objection-icon-badge"
            style={{
              background: isLaunch ? "#fef3c7" : "#edf3fa",
              borderColor: isLaunch ? "#fcd34d" : "#c4d8ee",
              color: isLaunch ? "#92400e" : "#1e527d",
            }}
          >
            {isLaunch ? <Rocket size={20} /> : <Zap size={20} />}
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <h3 className="objection-title">Evidence-Grounded Outreach &amp; Application Pack</h3>
              <Badge tone={isLaunch ? "amber" : "teal"}>
                {isLaunch ? "CareerProof Launch Mode" : "CareerProof Advance Mode"}
              </Badge>
            </div>
            <p className="objection-subtitle">
              Every message claim, letter paragraph, and screening answer is anchored to verified evidence with zero hallucinations.
            </p>
          </div>
        </div>

        {/* Tab switcher */}
        <div className="ats-mini-metrics">
          <button
            type="button"
            className={`persona-btn ${activeTab === "inmail" ? "active" : ""}`}
            style={{ padding: "5px 12px" }}
            onClick={() => setActiveTab("inmail")}
          >
            <Mail size={13} style={{ marginRight: 4, display: "inline-block", verticalAlign: "middle" }} />
            Cold InMail
          </button>
          <button
            type="button"
            className={`persona-btn ${activeTab === "cover_letter" ? "active" : ""}`}
            style={{ padding: "5px 12px" }}
            onClick={() => setActiveTab("cover_letter")}
          >
            <FileText size={13} style={{ marginRight: 4, display: "inline-block", verticalAlign: "middle" }} />
            Cover Letter
          </button>
          <button
            type="button"
            className={`persona-btn ${activeTab === "screening" ? "active" : ""}`}
            style={{ padding: "5px 12px" }}
            onClick={() => setActiveTab("screening")}
          >
            <HelpCircle size={13} style={{ marginRight: 4, display: "inline-block", verticalAlign: "middle" }} />
            Screening Answers ({pack.screening_answers?.length || 0})
          </button>
        </div>
      </div>

      {/* Tab 1: Cold InMail / DM */}
      {activeTab === "inmail" && (
        <div style={{ marginTop: 14 }}>
          {/* Pre-empted objection banner */}
          {pack.cold_inmail.objection_addressed && (
            <div
              style={{
                marginBottom: 12,
                padding: "8px 12px",
                background: "#f0fdf4",
                border: "1px solid #bbf7d0",
                borderRadius: 6,
                fontSize: 12,
                color: "#166534",
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <ShieldCheck size={16} color="#16a34a" style={{ flexShrink: 0 }} />
              <span>
                <strong>Pre-empts Objection Up Front:</strong> “{pack.cold_inmail.objection_addressed}”
              </span>
            </div>
          )}

          {/* Subject Line */}
          <div style={{ marginBottom: 10, background: "#f8faf9", padding: "10px 12px", borderRadius: 6, border: "1px solid #e1ebe4" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
              <span className="small-label" style={{ color: "#4d6b5b" }}>SUBJECT LINE</span>
              <button
                type="button"
                className="button secondary small"
                style={{ padding: "3px 8px", fontSize: 11 }}
                onClick={() => copyText("inmail_subject", pack.cold_inmail.subject)}
              >
                {copiedItem === "inmail_subject" ? <Check size={12} color="#16a34a" /> : <Copy size={12} />}
                {copiedItem === "inmail_subject" ? "Copied" : "Copy Subject"}
              </button>
            </div>
            <code style={{ fontSize: 13, fontWeight: 600, color: "var(--ink)", display: "block" }}>
              {pack.cold_inmail.subject}
            </code>
          </div>

          {/* Message Body */}
          <div style={{ background: "#ffffff", padding: "14px 16px", borderRadius: 8, border: "1px solid #d4e4db", position: "relative" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span className="small-label">OUTREACH MESSAGE</span>
                <span
                  style={{
                    fontSize: 11,
                    padding: "2px 8px",
                    borderRadius: 999,
                    background: pack.cold_inmail.character_count <= 600 ? "#dcfce7" : "#fef9c3",
                    color: pack.cold_inmail.character_count <= 600 ? "#166534" : "#854d0e",
                    fontWeight: 600,
                  }}
                >
                  {pack.cold_inmail.character_count} chars · {pack.cold_inmail.word_count} words
                </span>
              </div>
              <button
                type="button"
                className="button primary small"
                onClick={() => copyText("inmail_body", pack.cold_inmail.body)}
              >
                {copiedItem === "inmail_body" ? <Check size={13} /> : <Copy size={13} />}
                {copiedItem === "inmail_body" ? "Copied Message!" : "Copy Full Message"}
              </button>
            </div>

            <pre
              style={{
                whiteSpace: "pre-wrap",
                fontFamily: "inherit",
                fontSize: 13,
                lineHeight: 1.6,
                color: "var(--ink)",
                margin: 0,
              }}
            >
              {pack.cold_inmail.body}
            </pre>

            {/* Claims Cited Chips */}
            {pack.cold_inmail.claims_used?.length > 0 && (
              <div style={{ marginTop: 14, paddingTop: 10, borderTop: "1px solid #eef3f0" }}>
                <span className="small-label" style={{ display: "block", marginBottom: 6 }}>
                  VERIFIED CLAIMS CITED IN MESSAGE
                </span>
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {pack.cold_inmail.claims_used.map((c, idx) => (
                    <div
                      key={idx}
                      style={{
                        padding: "6px 10px",
                        background: "#f4f8f5",
                        borderRadius: 6,
                        border: "1px solid #dfeae2",
                        fontSize: 11,
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                      }}
                    >
                      <Badge tone="teal">[Claim #{idx + 1}]</Badge>
                      <span style={{ color: "#2d4437", flex: 1 }}>{c.bullet_text}</span>
                      <span className="muted">({c.company})</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 2: Tailored Cover Letter */}
      {activeTab === "cover_letter" && (
        <div style={{ marginTop: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
            <div>
              <h4 style={{ margin: 0, fontSize: 14, color: "var(--ink)" }}>{pack.cover_letter.title}</h4>
              <span className="muted small">{pack.cover_letter.word_count} words · Grounded in {pack.cover_letter.claims_used?.length || 0} verified bullets</span>
            </div>
            <button
              type="button"
              className="button primary small"
              onClick={() => copyText("cover_letter", pack.cover_letter.body)}
            >
              {copiedItem === "cover_letter" ? <Check size={13} /> : <Copy size={13} />}
              {copiedItem === "cover_letter" ? "Copied Cover Letter!" : "Copy Cover Letter"}
            </button>
          </div>

          <div
            style={{
              background: "#ffffff",
              padding: "18px 22px",
              borderRadius: 8,
              border: "1px solid #d4e4db",
              fontSize: 13,
              lineHeight: 1.7,
              color: "#1e293b",
              whiteSpace: "pre-wrap",
            }}
          >
            {pack.cover_letter.body}
          </div>
        </div>
      )}

      {/* Tab 3: Screening Answers */}
      {activeTab === "screening" && (
        <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 12 }}>
          {pack.screening_answers.map((sa, idx) => (
            <article
              key={idx}
              className="objection-card"
              style={{ background: "#ffffff", border: "1px solid #d4e4db", padding: 14 }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                <strong style={{ fontSize: 13, color: "var(--ink)", lineHeight: 1.4 }}>
                  Q{idx + 1}: {sa.question}
                </strong>
                <button
                  type="button"
                  className="button secondary small"
                  style={{ padding: "3px 8px", fontSize: 11, flexShrink: 0, marginLeft: 10 }}
                  onClick={() => copyText(`screening_${idx}`, sa.answer)}
                >
                  {copiedItem === `screening_${idx}` ? <Check size={12} color="#16a34a" /> : <Copy size={12} />}
                  {copiedItem === `screening_${idx}` ? "Copied" : "Copy"}
                </button>
              </div>

              <div
                style={{
                  padding: "10px 12px",
                  background: "#f8faf9",
                  borderRadius: 6,
                  border: "1px solid #e1ebe4",
                  fontSize: 12.5,
                  lineHeight: 1.55,
                  color: "#243a2d",
                  marginBottom: 8,
                }}
              >
                {sa.answer}
              </div>

              {sa.truth_boundary_note && (
                <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "#92400e" }}>
                  <AlertCircle size={13} color="#d97706" style={{ flexShrink: 0 }} />
                  <span><strong>Truth Boundary:</strong> {sa.truth_boundary_note}</span>
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
