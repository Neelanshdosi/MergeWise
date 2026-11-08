"use client";

import React, { useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { ScoredIssueCandidate } from "@/lib/types";
import PlanModal from "./PlanModal";
import { OutcomeButtons } from "./OutcomeButtons";
import { IssueOpenedIcon, StarIcon } from "./Octicons";
import CircularScoreRing from "./CircularScoreRing";

interface IssueCardProps {
  candidate: ScoredIssueCandidate;
  index: number;
}

function getLabelStyle(label: string): { bg: string; border: string; color: string } {
  const l = label.toLowerCase();
  if (l.includes("good") || l.includes("first") || l.includes("beginner")) {
    return {
      bg: "var(--color-success-subtle)",
      border: "var(--color-success-border)",
      color: "var(--color-success-fg)",
    };
  }
  if (l.includes("bug") || l.includes("defect") || l.includes("error")) {
    return {
      bg: "var(--color-danger-subtle)",
      border: "var(--color-danger-border)",
      color: "var(--color-danger-fg)",
    };
  }
  if (l.includes("doc") || l.includes("documentation")) {
    return {
      bg: "var(--color-accent-subtle)",
      border: "var(--color-accent-border)",
      color: "var(--color-accent-fg)",
    };
  }
  if (l.includes("help") || l.includes("enhancement") || l.includes("feature")) {
    return {
      bg: "var(--color-done-subtle)",
      border: "var(--color-done-border)",
      color: "var(--color-done-fg)",
    };
  }
  return {
    bg: "var(--color-canvas-subtle)",
    border: "var(--color-border-default)",
    color: "var(--color-fg-muted)",
  };
}

export default function IssueCard({ candidate, index }: IssueCardProps) {
  const { issue, score, one_line_reason, score_breakdown, features } = candidate;
  const [showBreakdown, setShowBreakdown] = useState<boolean>(false);
  const [showFullReasoning, setShowFullReasoning] = useState<boolean>(false);
  const [isPlanModalOpen, setIsPlanModalOpen] = useState<boolean>(false);
  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const { getToken } = useAuth();

  const handleOpenPlan = async () => {
    try {
      const token = await getToken();
      setSessionToken(token);
    } catch {
      // Preview mode
    }
    setIsPlanModalOpen(true);
  };

  const daysAgo = issue.created_at_epoch
    ? Math.max(1, Math.floor((Date.now() / 1000 - issue.created_at_epoch) / 86400))
    : 7;

  const repoOwner = issue.repo_full_name.includes("/")
    ? issue.repo_full_name.split("/")[0]
    : "github";

  // Derive contextual reason chips
  const chips: { label: string; tooltip: string }[] = [];

  // 1. Language share chip
  if (features?.lang_commit_share && features.lang_commit_share > 0) {
    chips.push({
      label: `${issue.primary_language || "Language"}: ${Math.round(features.lang_commit_share * 100)}% of code`,
      tooltip: "Matches your primary language footprint",
    });
  } else if (issue.primary_language) {
    chips.push({
      label: `${issue.primary_language}`,
      tooltip: "Primary repository language",
    });
  }

  // 2. Framework / Domain overlap chip
  if (features?.domain_topic_overlap && features.domain_topic_overlap > 0) {
    chips.push({
      label: "Stack fit",
      tooltip: "Repository topics and manifests align with your tools",
    });
  }

  // 3. Issue type chip
  const lowerLabels = (issue.labels || []).map((lbl) => lbl.toLowerCase());
  if (lowerLabels.some((l) => l.includes("good") || l.includes("first"))) {
    chips.push({
      label: "Good first issue",
      tooltip: "Targeted for first-time contributors",
    });
  } else if (lowerLabels.some((l) => l.includes("bug"))) {
    chips.push({
      label: "Bug fix",
      tooltip: "Scoped defect correction",
    });
  } else if (lowerLabels.some((l) => l.includes("doc"))) {
    chips.push({
      label: "Docs",
      tooltip: "Documentation improvement",
    });
  }

  // 4. Repo updated chip
  chips.push({
    label: `Repo updated ${daysAgo}d ago`,
    tooltip: "Active maintainer engagement within 90 days",
  });

  return (
    <div className="RepoTable-row">
      {/* Col 1: Open Issue Icon & Title + Meta line */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: "10px" }}>
          <div style={{ marginTop: "3px", flexShrink: 0 }}>
            <IssueOpenedIcon size={16} color="var(--color-success-fg)" />
          </div>

          <div style={{ flex: 1, minWidth: 0 }}>
            {/* Title & Label Pills */}
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                alignItems: "baseline",
                gap: "6px 8px",
                marginBottom: "4px",
              }}
            >
              <a
                href={issue.html_url || issue.issue_url}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  fontSize: "14px",
                  fontWeight: 600,
                  color: "var(--color-fg-default)",
                  lineHeight: 1.35,
                  wordBreak: "break-word",
                  textDecoration: "none",
                }}
                className="issue-title-link"
              >
                {issue.title}
              </a>

              {/* Tinted label pills */}
              <div style={{ display: "inline-flex", flexWrap: "wrap", gap: "4px", verticalAlign: "middle" }}>
                {issue.labels.slice(0, 3).map((lbl, i) => {
                  const { bg, border, color } = getLabelStyle(lbl);
                  return (
                    <span
                      key={i}
                      className="IssueLabel"
                      style={{
                        backgroundColor: bg,
                        borderColor: border,
                        color: color,
                        fontSize: "11px",
                        lineHeight: "16px",
                        padding: "0 6px",
                      }}
                    >
                      {lbl}
                    </span>
                  );
                })}
              </div>
            </div>

            {/* Subtitle: Owner avatar, repo #number, language, score details */}
            <div
              style={{
                fontSize: "12px",
                color: "var(--color-fg-muted)",
                display: "flex",
                flexWrap: "wrap",
                alignItems: "center",
                gap: "6px 10px",
              }}
            >
              <div style={{ display: "inline-flex", alignItems: "center", gap: "5px" }}>
                <img
                  src={`https://github.com/${repoOwner}.png?size=40`}
                  alt={repoOwner}
                  width={16}
                  height={16}
                  style={{
                    borderRadius: "50%",
                    flexShrink: 0,
                    border: "1px solid var(--color-border-default)",
                  }}
                  onError={(e) => {
                    (e.target as HTMLElement).style.display = "none";
                  }}
                />
                <span style={{ fontWeight: 500, color: "var(--color-fg-muted)" }}>
                  {issue.repo_full_name} #{issue.issue_number}
                </span>
              </div>

              {issue.primary_language && (
                <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
                  <span
                    style={{
                      width: "8px",
                      height: "8px",
                      borderRadius: "50%",
                      backgroundColor: "var(--color-accent-fg)",
                      display: "inline-block",
                    }}
                  />
                  {issue.primary_language}
                </span>
              )}

              {score_breakdown && (
                <button
                  onClick={() => setShowBreakdown(!showBreakdown)}
                  style={{
                    background: "none",
                    border: "none",
                    color: "var(--color-fg-muted)",
                    cursor: "pointer",
                    fontSize: "11px",
                    padding: "0 4px",
                    textDecoration: "underline",
                  }}
                >
                  {showBreakdown ? "Hide score" : "Score details"}
                </button>
              )}
            </div>

            {/* Score Breakdown Drawer */}
            {showBreakdown && score_breakdown && (
              <div
                style={{
                  backgroundColor: "var(--color-canvas-subtle)",
                  border: "1px solid var(--color-border-default)",
                  borderRadius: "6px",
                  padding: "8px 12px",
                  marginTop: "8px",
                  fontSize: "11px",
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
                  gap: "6px",
                  color: "var(--color-fg-default)",
                }}
              >
                <div>
                  <span style={{ color: "var(--color-fg-muted)" }}>Lang match:</span>{" "}
                  <strong>{Math.round((score_breakdown.language_familiarity || 0) * 100)}%</strong>
                </div>
                <div>
                  <span style={{ color: "var(--color-fg-muted)" }}>Stack fit:</span>{" "}
                  <strong>{Math.round((score_breakdown.domain_framework_fit || 0) * 100)}%</strong>
                </div>
                <div>
                  <span style={{ color: "var(--color-fg-muted)" }}>Scope clarity:</span>{" "}
                  <strong>{Math.round((score_breakdown.issue_clarity_scoping || 0) * 100)}%</strong>
                </div>
                <div>
                  <span style={{ color: "var(--color-fg-muted)" }}>Labels:</span>{" "}
                  <strong>{Math.round((score_breakdown.labels_accessibility || 0) * 100)}%</strong>
                </div>
                <div>
                  <span style={{ color: "var(--color-fg-muted)" }}>Repo health:</span>{" "}
                  <strong>{Math.round((score_breakdown.repo_health_recency || 0) * 100)}%</strong>
                </div>
              </div>
            )}

            {/* Outcome Progression Buttons */}
            <div className="RepoTable-outcome-container">
              <OutcomeButtons
                repoFullName={issue.repo_full_name}
                issueNumber={issue.issue_number}
                issueTitle={issue.title}
                primaryLanguage={issue.primary_language}
                labels={issue.labels}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Col 2: Reason Chips (Hidden on mobile) */}
      <div className="RepoTable-col-chips" style={{ width: "260px", flexShrink: 0 }}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "4px", marginBottom: "4px" }}>
          {chips.map((chip, idx) => (
            <span
              key={idx}
              title={chip.tooltip}
              style={{
                fontSize: "11px",
                fontWeight: 500,
                padding: "1px 6px",
                borderRadius: "12px",
                backgroundColor: "var(--color-canvas-subtle)",
                border: "1px solid var(--color-border-default)",
                color: "var(--color-fg-muted)",
              }}
            >
              {chip.label}
            </span>
          ))}
        </div>

        {one_line_reason && (
          <div>
            <button
              onClick={() => setShowFullReasoning(!showFullReasoning)}
              style={{
                background: "none",
                border: "none",
                color: "var(--color-accent-fg)",
                fontSize: "11px",
                cursor: "pointer",
                padding: "2px 0",
              }}
            >
              {showFullReasoning ? "Hide reasoning" : "Why this issue ▾"}
            </button>
            {showFullReasoning && (
              <div
                style={{
                  fontSize: "11px",
                  color: "var(--color-fg-muted)",
                  backgroundColor: "var(--color-canvas-subtle)",
                  border: "1px solid var(--color-border-default)",
                  borderRadius: "4px",
                  padding: "6px 8px",
                  marginTop: "4px",
                  lineHeight: 1.4,
                }}
              >
                {one_line_reason}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Col 3: Score Ring, Stars, Updated + Action Buttons */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "flex-end",
          gap: "8px",
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          {issue.stars > 0 && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "3px",
                fontSize: "12px",
                color: "var(--color-fg-muted)",
              }}
            >
              <StarIcon size={13} color="var(--color-fg-muted)" />
              {issue.stars.toLocaleString()}
            </span>
          )}

          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span style={{ fontSize: "11px", color: "var(--color-fg-muted)", fontWeight: 500 }}>
              Match
            </span>
            <CircularScoreRing score={score} size={30} strokeWidth={3} />
          </div>
        </div>

        {/* Action Buttons: How to Start (Green) & View on GitHub */}
        <div className="RepoTable-row-actions">
          <button
            onClick={handleOpenPlan}
            className="btn btn-sm btn-primary"
            title="Generate AI onboarding plan with verified file citations"
          >
            How to Start
          </button>
          <a
            href={issue.html_url || issue.issue_url}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-sm"
          >
            View on GitHub
          </a>
        </div>
      </div>

      {/* How to Start Modal */}
      {isPlanModalOpen && (
        <PlanModal
          candidate={candidate}
          isOpen={isPlanModalOpen}
          onClose={() => setIsPlanModalOpen(false)}
          jwtToken={sessionToken}
        />
      )}
    </div>
  );
}
