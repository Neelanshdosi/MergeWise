"use client";

import React from "react";
import { ScoredIssueCandidate } from "@/lib/types";

interface IssueCardProps {
  candidate: ScoredIssueCandidate;
  index: number;
}

export default function IssueCard({ candidate, index }: IssueCardProps) {
  const { issue, score, one_line_reason, score_breakdown } = candidate;
  const scorePercent = Math.round(score * 100);
  const [showBreakdown, setShowBreakdown] = React.useState<boolean>(false);

  return (
    <div
      className="glass-panel"
      style={{
        padding: "24px",
        marginBottom: "20px",
        borderLeft: `4px solid ${index === 0 ? "var(--accent-primary)" : "rgba(255, 255, 255, 0.15)"}`,
        transition: "transform 0.2s ease, border-color 0.2s ease",
      }}
    >
      {/* Header Row: Rank, Score, and Viability Badge */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px", flexWrap: "wrap", gap: "10px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span style={{
            width: "28px",
            height: "28px",
            borderRadius: "50%",
            background: index === 0 ? "var(--accent-gradient)" : "rgba(255, 255, 255, 0.1)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "0.85rem",
            fontWeight: 700,
          }}>
            #{index + 1}
          </span>
          <span style={{ fontSize: "0.9rem", color: "var(--text-muted)", fontWeight: 500 }}>
            {issue.repo_full_name}
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          {/* Match Score */}
          <span style={{
            fontSize: "0.8rem",
            fontWeight: 700,
            padding: "4px 10px",
            borderRadius: "6px",
            background: scorePercent >= 70 ? "rgba(99, 102, 241, 0.2)" : "rgba(255, 255, 255, 0.08)",
            color: scorePercent >= 70 ? "#a5b4fc" : "var(--text-secondary)",
            border: "1px solid rgba(99, 102, 241, 0.3)",
          }}>
            Match Score: {scorePercent}%
          </span>

          {score_breakdown && (
            <button
              onClick={() => setShowBreakdown(!showBreakdown)}
              style={{
                background: "none",
                border: "none",
                color: "#a5b4fc",
                cursor: "pointer",
                fontSize: "0.75rem",
                textDecoration: "underline",
              }}
            >
              {showBreakdown ? "Hide Breakdown" : "Score Breakdown"}
            </button>
          )}

          {/* Viability Verified Badge */}
          <span className="badge badge-success" title="Verified open, unassigned, and no competing PRs">
            ✓ Viability Verified
          </span>
        </div>
      </div>

      {/* Score Breakdown Drawer */}
      {showBreakdown && score_breakdown && (
        <div style={{
          backgroundColor: "rgba(0, 0, 0, 0.25)",
          borderRadius: "var(--radius-sm)",
          padding: "10px 14px",
          marginBottom: "14px",
          fontSize: "0.75rem",
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
          gap: "8px",
          color: "var(--text-secondary)",
          border: "1px dashed rgba(255, 255, 255, 0.1)",
        }}>
          <div>
            <span style={{ color: "var(--text-muted)" }}>Language Match:</span>{" "}
            <strong>{Math.round((score_breakdown.language_familiarity || 0) * 100)}%</strong>
          </div>
          <div>
            <span style={{ color: "var(--text-muted)" }}>Stack / Domain:</span>{" "}
            <strong>{Math.round((score_breakdown.domain_framework_fit || 0) * 100)}%</strong>
          </div>
          <div>
            <span style={{ color: "var(--text-muted)" }}>Scope & Clarity:</span>{" "}
            <strong>{Math.round((score_breakdown.issue_clarity_scoping || 0) * 100)}%</strong>
          </div>
          <div>
            <span style={{ color: "var(--text-muted)" }}>Labels:</span>{" "}
            <strong>{Math.round((score_breakdown.labels_accessibility || 0) * 100)}%</strong>
          </div>
          <div>
            <span style={{ color: "var(--text-muted)" }}>Repo Recency:</span>{" "}
            <strong>{Math.round((score_breakdown.repo_health_recency || 0) * 100)}%</strong>
          </div>
        </div>
      )}

      {/* Issue Title */}
      <h3 style={{ fontSize: "1.2rem", fontWeight: 600, marginBottom: "12px", lineHeight: 1.4 }}>
        <a
          href={issue.html_url || issue.issue_url}
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: "var(--text-primary)", transition: "color 0.15s ease" }}
          onMouseOver={(e) => (e.currentTarget.style.color = "#a5b4fc")}
          onMouseOut={(e) => (e.currentTarget.style.color = "var(--text-primary)")}
        >
          {issue.title}
        </a>
      </h3>

      {/* One-Line Personalized Match Reason */}
      <div style={{
        backgroundColor: "rgba(99, 102, 241, 0.08)",
        border: "1px solid rgba(99, 102, 241, 0.2)",
        borderRadius: "var(--radius-sm)",
        padding: "10px 14px",
        marginBottom: "16px",
        display: "flex",
        alignItems: "center",
        gap: "10px",
      }}>
        <span style={{ fontSize: "1.1rem" }}>🎯</span>
        <span style={{ fontSize: "0.9rem", color: "#c7d2fe", fontWeight: 500 }}>
          {one_line_reason}
        </span>
      </div>

      {/* Tags & Action Row */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
          {issue.primary_language && (
            <span style={{
              fontSize: "0.75rem",
              padding: "4px 8px",
              borderRadius: "4px",
              background: "rgba(255, 255, 255, 0.06)",
              color: "var(--text-secondary)",
            }}>
              ● {issue.primary_language}
            </span>
          )}
          {issue.labels.slice(0, 3).map((lbl, i) => (
            <span
              key={i}
              style={{
                fontSize: "0.75rem",
                padding: "4px 8px",
                borderRadius: "4px",
                background: lbl.toLowerCase().includes("good") ? "rgba(16, 185, 129, 0.1)" : "rgba(255, 255, 255, 0.06)",
                color: lbl.toLowerCase().includes("good") ? "var(--success)" : "var(--text-muted)",
              }}
            >
              {lbl}
            </span>
          ))}
          {/* Show real star count if > 0, otherwise hidden */}
          {issue.stars > 0 && (
            <span style={{ fontSize: "0.75rem", padding: "4px 8px", color: "var(--text-muted)", background: "rgba(255, 255, 255, 0.03)", borderRadius: "4px" }}>
              ★ {issue.stars.toLocaleString()}
            </span>
          )}
        </div>

        <a
          href={issue.html_url || issue.issue_url}
          target="_blank"
          rel="noopener noreferrer"
          className="btn-secondary"
          style={{ padding: "6px 14px", fontSize: "0.85rem" }}
        >
          View on GitHub ↗
        </a>
      </div>
    </div>
  );
}
