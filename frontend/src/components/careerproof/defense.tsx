"use client";
import { useState } from "react";
import {
  ShieldAlert,
  ShieldCheck,
  AlertOctagon,
  Sparkles,
  Layers,
  CheckCircle2,
  Send,
  HelpCircle,
  FileCode,
  Flame,
  ChevronDown,
  ChevronUp,
  Award
} from "lucide-react";
import {
  api,
  type DefenseCard,
  type DefenseEvaluationResult,
  type ProofSpec
} from "@/lib/careerproof/api";
import { Badge } from "./ui";

export function InterviewDefenseView({
  draftId,
  cards,
  proofSpecs,
}: {
  draftId: number;
  cards: DefenseCard[];
  proofSpecs: ProofSpec[];
}) {
  const [activeTab, setActiveTab] = useState<"defense" | "proof">("defense");
  const [activeCardId, setActiveCardId] = useState<string>(cards[0]?.id || "");
  const [explanationText, setExplanationText] = useState<Record<string, string>>({});
  const [evaluating, setEvaluating] = useState<boolean>(false);
  const [evalResults, setEvalResults] = useState<Record<string, DefenseEvaluationResult>>({});

  async function handleTestDefense(cardId: string) {
    const text = explanationText[cardId]?.trim();
    if (!text) return;
    setEvaluating(true);
    try {
      const result = await api<DefenseEvaluationResult>(
        `/evidence-drafts/${draftId}/evaluate-defense`,
        "POST",
        { card_id: cardId, explanation: text }
      );
      setEvalResults((prev) => ({ ...prev, [cardId]: result }));
    } catch (err) {
      console.error("Evaluation failed", err);
    } finally {
      setEvaluating(false);
    }
  }

  return (
    <div className="objection-engine-panel" style={{ marginTop: 16 }}>
      {/* Header */}
      <div className="objection-engine-header">
        <div className="objection-header-left">
          <div className="objection-icon-badge" style={{ background: "#edf3fa", borderColor: "#c4d8ee", color: "#1e527d" }}>
            <ShieldCheck size={20} />
          </div>
          <div>
            <h3 className="objection-title">Interview Defense Pack &amp; Minimum Proof</h3>
            <p className="objection-subtitle">
              Personalized technical interview defense cards grounded in every approved resume bullet
            </p>
          </div>
        </div>
        <div className="ats-mini-metrics">
          <button
            type="button"
            className={`persona-btn ${activeTab === "defense" ? "active" : ""}`}
            style={{ padding: "5px 12px", minWidth: 100 }}
            onClick={() => setActiveTab("defense")}
          >
            Defense Cards ({cards.length})
          </button>
          <button
            type="button"
            className={`persona-btn ${activeTab === "proof" ? "active" : ""}`}
            style={{ padding: "5px 12px", minWidth: 100 }}
            onClick={() => setActiveTab("proof")}
          >
            Minimum Proof ({proofSpecs.length})
          </button>
        </div>
      </div>

      {activeTab === "defense" && (
        <div>
          {!cards.length ? (
            <p className="muted" style={{ padding: "14px 0" }}>
              No included bullets to generate interview defense cards for.
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {cards.map((card) => {
                const isOpen = activeCardId === card.id;
                const evalRes = evalResults[card.id];

                return (
                  <article key={card.id} className="objection-card">
                    {/* Top Row */}
                    <div
                      className="objection-card-top"
                      style={{ cursor: "pointer" }}
                      onClick={() => setActiveCardId(isOpen ? "" : card.id)}
                    >
                      <div>
                        <span className="eyebrow" style={{ display: "block", marginBottom: 3 }}>
                          {card.company} · {card.role} · {card.topic}
                        </span>
                        <strong style={{ fontSize: 13, color: "var(--ink)", lineHeight: 1.45, display: "block" }}>
                          “{card.bullet_text}”
                        </strong>
                      </div>
                      <button
                        type="button"
                        className="icon-button"
                        style={{ border: "none", background: "transparent" }}
                      >
                        {isOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                      </button>
                    </div>

                    {isOpen && (
                      <div style={{ marginTop: 14, paddingTop: 12, borderTop: "1px solid #e1ebe4" }}>
                        {/* Technical Probe Question */}
                        <div className="objection-hypothesis-box" style={{ borderLeftColor: "#2563eb", background: "#f0f6ff" }}>
                          <div className="objection-hypothesis-label" style={{ color: "#1e40af" }}>
                            🎯 Probable Technical Interviewer Probe
                          </div>
                          <div className="objection-hypothesis-text" style={{ fontWeight: 600, color: "#1e3a8a" }}>
                            “{card.technical_probe}”
                          </div>
                        </div>

                        {/* Architecture Trade-Off */}
                        <div style={{ margin: "10px 0", padding: "10px 12px", background: "#fbfcfb", border: "1px solid #e2ece5", borderRadius: 6 }}>
                          <span className="small-label" style={{ color: "#456152", display: "block", marginBottom: 3 }}>
                            ⚖️ Architectural Trade-off Defense
                          </span>
                          <p style={{ fontSize: 12, color: "#2d3f35", lineHeight: 1.5 }}>
                            {card.architecture_tradeoff_question}
                          </p>
                        </div>

                        {/* Truth Boundary ("Do Not Cross") */}
                        <div
                          className="hard-constraint-alert"
                          style={{
                            margin: "12px 0",
                            background: "#fffaf0",
                            borderColor: "#f5d0a9",
                          }}
                        >
                          <AlertOctagon size={16} color="#c05621" style={{ flexShrink: 0, marginTop: 2 }} />
                          <div>
                            <div className="hard-constraint-title" style={{ color: "#9c4221", fontSize: 12 }}>
                              Strict Truth Boundary (Do Not Cross In Interview)
                            </div>
                            <p style={{ fontSize: 12, color: "#7b341e", marginTop: 2 }}>
                              {card.truth_boundary.do_not_cross_rule}
                            </p>
                            <div style={{ marginTop: 6, display: "flex", gap: 10, flexWrap: "wrap", fontSize: 11, color: "#744210" }}>
                              <span><strong>Verified scale ceiling:</strong> {card.truth_boundary.verified_scale_limit}</span>
                            </div>
                          </div>
                        </div>

                        {/* Talking Points */}
                        <div style={{ margin: "10px 0" }}>
                          <span className="small-label">RECOMMENDED INTERVIEW TALKING POINTS</span>
                          <ul style={{ margin: "6px 0 0 18px", padding: 0, fontSize: 12, color: "#374b40" }}>
                            {card.recommended_talking_points.map((tp, idx) => (
                              <li key={idx} style={{ marginBottom: 4 }}>{tp}</li>
                            ))}
                          </ul>
                        </div>

                        {/* Interactive Practice Simulator */}
                        <div style={{ marginTop: 14, padding: "12px 14px", background: "#f5f9f6", border: "1px solid #d4e5da", borderRadius: 8 }}>
                          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                            <span style={{ fontSize: 12, fontWeight: 700, color: "var(--teal)" }}>
                              🎤 Test My Spoken Defense Against Evidence
                            </span>
                            {evalRes && (
                              <Badge tone={evalRes.status === "solid_defense" ? "teal" : evalRes.status === "overreach_detected" ? "amber" : "neutral"}>
                                Score: {evalRes.score}/100
                              </Badge>
                            )}
                          </div>
                          <textarea
                            rows={3}
                            placeholder="Type how you would answer this probe out loud... (e.g., 'We chose Redis because serialization was our bottleneck, and benchmarked p99 under 15ms...')"
                            value={explanationText[card.id] || ""}
                            onChange={(e) => setExplanationText({ ...explanationText, [card.id]: e.target.value })}
                            style={{ width: "100%", fontSize: 12, padding: 8, borderRadius: 6, border: "1px solid #ccdcd2" }}
                          />
                          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8 }}>
                            <button
                              type="button"
                              className="button secondary small"
                              disabled={evaluating || !explanationText[card.id]?.trim()}
                              onClick={() => void handleTestDefense(card.id)}
                            >
                              <Send size={12} />
                              {evaluating ? "Evaluating..." : "Evaluate Defense Against Evidence"}
                            </button>
                          </div>

                          {/* Evaluation Output */}
                          {evalRes && (
                            <div style={{ marginTop: 10, padding: 10, background: "#ffffff", borderRadius: 6, border: "1px solid #d8e5dd" }}>
                              <p style={{ fontSize: 12, color: "#223b2e", fontWeight: 600 }}>
                                {evalRes.feedback}
                              </p>
                              {evalRes.warnings.length > 0 && (
                                <div style={{ marginTop: 6 }}>
                                  {evalRes.warnings.map((w, wIdx) => (
                                    <p key={wIdx} style={{ fontSize: 11, color: "#b91c1c" }}>
                                      ⚠️ {w}
                                    </p>
                                  ))}
                                </div>
                              )}
                              {evalRes.strengths.length > 0 && (
                                <div style={{ marginTop: 6 }}>
                                  {evalRes.strengths.map((s, sIdx) => (
                                    <p key={sIdx} style={{ fontSize: 11, color: "var(--teal)" }}>
                                      ✓ {s}
                                    </p>
                                  ))}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          )}
        </div>
      )}

      {activeTab === "proof" && (
        <div>
          {!proofSpecs.length ? (
            <p className="muted" style={{ padding: "16px 0" }}>
              No Bucket C (True Deficit) qualification gaps detected! Your profile covers all primary required competencies.
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <p className="muted small">
                Targeted, production-grade Minimum Proof Blueprints to resolve real qualification gaps without fabricating past corporate tenure.
              </p>
              {proofSpecs.map((spec, i) => (
                <article key={i} className="objection-card" style={{ background: "#ffffff" }}>
                  <div className="objection-card-top">
                    <div>
                      <span className="eyebrow" style={{ textTransform: "uppercase" }}>
                        {spec.proof_tier} Proof Tier · {spec.estimated_effort}
                      </span>
                      <h4 style={{ fontSize: 14, fontWeight: 700, color: "var(--ink)", marginTop: 2 }}>
                        {spec.title}
                      </h4>
                    </div>
                    <Badge tone="amber">
                      {spec.proof_tier.toUpperCase()} TIER
                    </Badge>
                  </div>

                  <p style={{ fontSize: 12, color: "#42554a", margin: "8px 0" }}>
                    {spec.problem_statement}
                  </p>

                  <div style={{ margin: "10px 0", padding: "10px 12px", background: "#f8faf8", border: "1px solid #dce8e0", borderRadius: 6 }}>
                    <span className="small-label">MINIMUM DELIVERABLES &amp; CODE ARTIFACTS</span>
                    <ul style={{ margin: "6px 0 0 18px", padding: 0, fontSize: 12, color: "#2d4236" }}>
                      {spec.deliverables.map((del, dIdx) => (
                        <li key={dIdx} style={{ marginBottom: 4 }}>{del}</li>
                      ))}
                    </ul>
                  </div>

                  <div className="objection-action-box" style={{ background: "#f0f7f3", borderColor: "#c6dfcf" }}>
                    <div className="objection-action-title">
                      <Award size={13} />
                      How to Truthfully Frame on Resume:
                    </div>
                    <div className="objection-action-content">
                      {spec.truth_framing_guidance}
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
