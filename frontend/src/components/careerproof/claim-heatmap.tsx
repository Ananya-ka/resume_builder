"use client";
import { useState } from "react";
import {
  Flame,
  Award,
  AlertTriangle,
  TrendingUp,
  Briefcase,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Sparkles,
  Layers,
  ArrowRight
} from "lucide-react";
import { type ClaimHeatmapReport, type ClaimHeatmapItem } from "@/lib/careerproof/api";
import { Badge } from "./ui";

export function ClaimHeatmapView({ report }: { report: ClaimHeatmapReport }) {
  const [filterTier, setFilterTier] = useState<string>("all");

  const { summary, heatmap } = report;

  const filteredClaims = heatmap.filter((item) => {
    if (filterTier === "all") return true;
    return item.win_tier === filterTier;
  });

  return (
    <div className="objection-engine-panel" style={{ marginTop: 18 }}>
      {/* Header */}
      <div className="objection-engine-header">
        <div className="objection-header-left">
          <div
            className="objection-icon-badge"
            style={{
              background: "#ecfdf5",
              borderColor: "#a7f3d0",
              color: "#059669",
            }}
          >
            <Flame size={20} />
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <h3 className="objection-title">Claim Conversion Heatmap &amp; Win Rate Audit</h3>
              <Badge tone="teal">Outcome-Based Analytics</Badge>
            </div>
            <p className="objection-subtitle">
              Tracking empirical callback and interview win rates for every resume claim, not just vanity usage counts.
            </p>
          </div>
        </div>
      </div>

      {/* KPI Dashboard */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: 10,
          margin: "14px 0",
        }}
      >
        <div
          style={{
            padding: "12px 14px",
            background: "#ffffff",
            borderRadius: 8,
            border: "1px solid #d4e4db",
          }}
        >
          <span className="small-label" style={{ color: "#456152" }}>INTERVIEW WIN RATE</span>
          <div style={{ display: "flex", alignItems: "baseline", gap: 6, marginTop: 4 }}>
            <span style={{ fontSize: 24, fontWeight: 800, color: "var(--teal)" }}>
              {summary.overall_interview_rate}%
            </span>
            <span className="muted small">
              ({summary.total_interviews}/{summary.total_applications_tracked} apps)
            </span>
          </div>
        </div>

        <div
          style={{
            padding: "12px 14px",
            background: "#ffffff",
            borderRadius: 8,
            border: "1px solid #d4e4db",
          }}
        >
          <span className="small-label" style={{ color: "#065f46" }}>🏆 HIGH PERFORMERS</span>
          <div style={{ fontSize: 24, fontWeight: 800, color: "#059669", marginTop: 4 }}>
            {summary.high_performing_count}
          </div>
          <span className="muted small">Claims with &gt;35% callback rate</span>
        </div>

        <div
          style={{
            padding: "12px 14px",
            background: summary.underperforming_count > 0 ? "#fff5f5" : "#ffffff",
            borderRadius: 8,
            border: `1px solid ${summary.underperforming_count > 0 ? "#fecaca" : "#d4e4db"}`,
          }}
        >
          <span className="small-label" style={{ color: summary.underperforming_count > 0 ? "#991b1b" : "#456152" }}>
            ⚠️ NEEDS REWORK
          </span>
          <div
            style={{
              fontSize: 24,
              fontWeight: 800,
              color: summary.underperforming_count > 0 ? "#dc2626" : "var(--ink)",
              marginTop: 4,
            }}
          >
            {summary.underperforming_count}
          </div>
          <span className="muted small">3+ apps with 0 callbacks</span>
        </div>

        <div
          style={{
            padding: "12px 14px",
            background: "#ffffff",
            borderRadius: 8,
            border: "1px solid #d4e4db",
          }}
        >
          <span className="small-label" style={{ color: "#456152" }}>TOTAL CLAIMS IN CATALOG</span>
          <div style={{ fontSize: 24, fontWeight: 800, color: "var(--ink)", marginTop: 4 }}>
            {summary.total_claims}
          </div>
          <span className="muted small">
            {summary.tested_count} tested · {summary.untested_count} untested
          </span>
        </div>
      </div>

      {/* Top Converting Claim Banner */}
      {summary.top_converting_claim && (
        <div
          style={{
            padding: "10px 14px",
            background: "#ecfdf5",
            borderRadius: 8,
            border: "1px solid #a7f3d0",
            marginBottom: 14,
            display: "flex",
            alignItems: "center",
            gap: 10,
          }}
        >
          <Award size={18} color="#059669" style={{ flexShrink: 0 }} />
          <div style={{ fontSize: 12, color: "#065f46", lineHeight: 1.45 }}>
            <strong>Highest-Converting Anchor Claim:</strong> “{summary.top_converting_claim}”
          </div>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="persona-selector" style={{ marginBottom: 14 }}>
        <button
          type="button"
          className={`persona-btn ${filterTier === "all" ? "active" : ""}`}
          onClick={() => setFilterTier("all")}
        >
          All Claims ({heatmap.length})
        </button>
        <button
          type="button"
          className={`persona-btn ${filterTier === "high_performer" ? "active" : ""}`}
          onClick={() => setFilterTier("high_performer")}
        >
          🏆 High Performers ({summary.high_performing_count})
        </button>
        <button
          type="button"
          className={`persona-btn ${filterTier === "underperforming" ? "active" : ""}`}
          onClick={() => setFilterTier("underperforming")}
        >
          ⚠️ Needs Rework ({summary.underperforming_count})
        </button>
        <button
          type="button"
          className={`persona-btn ${filterTier === "tested" ? "active" : ""}`}
          onClick={() => setFilterTier("tested")}
        >
          📊 Tested ({summary.tested_count})
        </button>
        <button
          type="button"
          className={`persona-btn ${filterTier === "untested" ? "active" : ""}`}
          onClick={() => setFilterTier("untested")}
        >
          ⚪ Untested ({summary.untested_count})
        </button>
      </div>

      {/* Claim Cards Grid */}
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {!filteredClaims.length ? (
          <p className="muted" style={{ padding: "16px 0" }}>
            No claims found matching this filter.
          </p>
        ) : (
          filteredClaims.map((item) => {
            const isHigh = item.win_tier === "high_performer";
            const isUnder = item.win_tier === "underperforming";
            const isTested = item.win_tier === "tested";

            return (
              <article
                key={item.evidence_id}
                className="objection-card"
                style={{
                  background: "#ffffff",
                  border: isUnder ? "1px solid #fca5a5" : isHigh ? "1px solid #86efac" : "1px solid #d4e4db",
                  padding: 14,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 10 }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                      <span className="eyebrow">
                        {item.company} · {item.role} · {item.section}
                      </span>
                      <Badge tone={isHigh ? "teal" : isUnder ? "amber" : isTested ? "neutral" : "neutral"}>
                        {isHigh
                          ? "🏆 High Performer"
                          : isUnder
                          ? "⚠️ Needs Rework"
                          : isTested
                          ? "📊 Tested Signal"
                          : "⚪ Untested"}
                      </Badge>
                    </div>
                    <strong style={{ fontSize: 13, color: "var(--ink)", lineHeight: 1.5, display: "block" }}>
                      “{item.content}”
                    </strong>
                  </div>

                  {/* Win Rate Metric Block */}
                  <div style={{ textAlign: "right", flexShrink: 0 }}>
                    <div style={{ fontSize: 16, fontWeight: 800, color: isHigh ? "#059669" : isUnder ? "#dc2626" : "var(--ink)" }}>
                      {item.win_rate}%
                    </div>
                    <span className="muted small">
                      {item.interview_count} / {item.application_count} callbacks
                    </span>
                  </div>
                </div>

                {/* Progress Bar */}
                {item.application_count > 0 && (
                  <div style={{ margin: "10px 0 8px 0" }}>
                    <div
                      style={{
                        height: 6,
                        background: "#e2e8f0",
                        borderRadius: 3,
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          height: "100%",
                          width: `${Math.min(item.win_rate, 100)}%`,
                          background: isHigh ? "#10b981" : isUnder ? "#ef4444" : "#3b82f6",
                          borderRadius: 3,
                          transition: "width 0.3s ease",
                        }}
                      />
                    </div>
                  </div>
                )}

                {/* Market Signal / Recommendation */}
                <div
                  style={{
                    marginTop: 8,
                    padding: "8px 10px",
                    background: isUnder ? "#fff1f2" : isHigh ? "#f0fdf4" : "#f8faf9",
                    borderRadius: 6,
                    border: `1px solid ${isUnder ? "#fecdd3" : isHigh ? "#bbf7d0" : "#e2ebe5"}`,
                    fontSize: 11.5,
                    lineHeight: 1.45,
                    color: isUnder ? "#9f1239" : isHigh ? "#166534" : "#374151",
                  }}
                >
                  {isUnder && <AlertTriangle size={13} style={{ display: "inline-block", marginRight: 4, verticalAlign: "middle" }} />}
                  {isHigh && <CheckCircle2 size={13} style={{ display: "inline-block", marginRight: 4, verticalAlign: "middle" }} />}
                  {item.market_signal}
                </div>

                {/* Companies Applied Tag Chips */}
                {item.companies_applied?.length > 0 && (
                  <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap", fontSize: 11 }}>
                    <span className="muted">Submitted to:</span>
                    {item.companies_applied.map((c, idx) => (
                      <span
                        key={idx}
                        style={{
                          padding: "2px 6px",
                          background: "#f1f5f9",
                          borderRadius: 4,
                          color: "#475569",
                          fontWeight: 500,
                        }}
                      >
                        {c}
                      </span>
                    ))}
                  </div>
                )}
              </article>
            );
          })
        )}
      </div>
    </div>
  );
}
