"use client";

import React from "react";
import { FunnelMetricsResponse } from "@/lib/types";
import {
  IssueOpenedIcon,
  CheckIcon,
  GitPullRequestIcon,
  GitMergeIcon,
  InfoIcon,
} from "./Octicons";

interface ProgressTabProps {
  funnel: FunnelMetricsResponse | null;
  whyTheseResults?: string | null;
  loading: boolean;
  onRefreshFunnel?: () => void;
}

export default function ProgressTab({
  funnel,
  whyTheseResults,
  loading,
}: ProgressTabProps) {
  const data = funnel || {
    shown: 0,
    plan_viewed: 0,
    attempted: 0,
    pr_opened: 0,
    merged: 0,
  };

  const steps = [
    {
      id: "shown",
      number: 1,
      name: "Recommended",
      count: data.shown,
      icon: <IssueOpenedIcon size={16} color="var(--color-accent-fg)" />,
      description: "Issues matched to your skills",
    },
    {
      id: "plan_viewed",
      number: 2,
      name: "Plan viewed",
      count: data.plan_viewed,
      icon: <InfoIcon size={16} color="var(--color-attention-fg)" />,
      description: "Onboarding plans inspected",
    },
    {
      id: "attempted",
      number: 3,
      name: "Working on it",
      count: data.attempted,
      icon: <CheckIcon size={16} color="var(--color-success-fg)" />,
      description: "Active local work started",
    },
    {
      id: "pr_opened",
      number: 4,
      name: "PR opened",
      count: data.pr_opened,
      icon: <GitPullRequestIcon size={16} color="var(--color-accent-fg)" />,
      description: "Pull requests submitted",
    },
    {
      id: "merged",
      number: 5,
      name: "Merged",
      count: data.merged,
      icon: <GitMergeIcon size={16} color="var(--color-done-fg)" />,
      description: "Successfully merged into upstream",
    },
  ];

  return (
    <div>
      {/* Funnel Box */}
      <div className="Box" style={{ marginBottom: "24px" }}>
        <div className="Box-header">
          <span style={{ fontWeight: 600, fontSize: "14px", color: "var(--color-fg-default)" }}>
            Open-Source Progression Funnel
          </span>
          <span style={{ fontSize: "12px", color: "var(--color-fg-muted)" }}>
            Tracking issues from initial recommendation to merged PR
          </span>
        </div>

        <div className="Box-body" style={{ padding: "20px 16px" }}>
          {/* Horizontal Steps Grid */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
              gap: "12px",
            }}
          >
            {steps.map((st, i) => {
              // Calculate conversion rate against initial recommended
              const rate =
                data.shown > 0
                  ? `${Math.round((st.count / data.shown) * 100)}%`
                  : i === 0
                  ? "100%"
                  : "0%";

              return (
                <div
                  key={st.id}
                  style={{
                    backgroundColor: "var(--color-canvas-subtle)",
                    border: "1px solid var(--color-border-default)",
                    borderRadius: "var(--border-radius)",
                    padding: "16px 12px",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    textAlign: "center",
                    position: "relative",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                      marginBottom: "6px",
                    }}
                  >
                    {st.icon}
                    <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--color-fg-muted)" }}>
                      Step {st.number}
                    </span>
                  </div>

                  <div
                    style={{
                      fontSize: "14px",
                      fontWeight: 600,
                      color: "var(--color-fg-default)",
                      marginBottom: "6px",
                    }}
                  >
                    {st.name}
                  </div>

                  <div
                    style={{
                      fontSize: "28px",
                      fontWeight: 800,
                      lineHeight: 1.1,
                      color:
                        st.id === "merged"
                          ? "var(--color-done-fg)"
                          : st.id === "attempted" || st.id === "pr_opened"
                          ? "var(--color-success-fg)"
                          : "var(--color-fg-default)",
                      marginBottom: "6px",
                    }}
                  >
                    {st.count}
                  </div>

                  <div
                    style={{
                      fontSize: "11px",
                      color: "var(--color-fg-muted)",
                      marginBottom: "8px",
                    }}
                  >
                    {st.description}
                  </div>

                  {/* Conversion pill */}
                  <span
                    className="IssueLabel"
                    style={{
                      fontSize: "10px",
                      fontWeight: 600,
                      padding: "1px 6px",
                      backgroundColor: "var(--color-canvas-default)",
                    }}
                  >
                    {i === 0 ? "Entry point" : `${rate} of recs`}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* "Why these results" Section */}
      <div className="Box">
        <div className="Box-header">
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <InfoIcon size={16} color="var(--color-accent-fg)" />
            <span style={{ fontWeight: 600, fontSize: "14px", color: "var(--color-fg-default)" }}>
              Why These Results &amp; Continuous Learning
            </span>
          </div>
        </div>

        <div className="Box-body" style={{ padding: "20px 20px" }}>
          {/* Active Personalized Feedback Note */}
          {whyTheseResults ? (
            <div
              className="Flash Flash--info"
              style={{ marginBottom: "16px" }}
            >
              <InfoIcon size={16} />
              <div>
                <strong>Active Memory Note: </strong>
                <span>{whyTheseResults}</span>
              </div>
            </div>
          ) : (
            <div
              style={{
                fontSize: "13px",
                color: "var(--color-fg-muted)",
                backgroundColor: "var(--color-canvas-subtle)",
                padding: "12px 14px",
                borderRadius: "var(--border-radius)",
                border: "1px solid var(--color-border-subtle)",
                marginBottom: "16px",
              }}
            >
              MergeWise tracks your interactions locally and in your isolated user database. As you mark issues as attempted, PR opened, or skipped, your recommendation weights adapt in real time.
            </div>
          )}

          {/* Transparent Reinforcement Memory Rules */}
          <div style={{ fontSize: "13px", color: "var(--color-fg-default)", lineHeight: 1.6 }}>
            <h4 style={{ fontSize: "14px", fontWeight: 600, marginBottom: "8px", color: "var(--color-fg-default)" }}>
              How Reinforcement Weighting Operates
            </h4>
            <ul style={{ paddingLeft: "20px", margin: "0 0 16px 0", color: "var(--color-fg-muted)" }}>
              <li>
                <strong>Half-Life Decay (60 days):</strong> Recent outcomes have the greatest influence; older outcomes decay exponentially so shifting project interests naturally take over.
              </li>
              <li>
                <strong>Positive Feedback (+0.05 / +0.03):</strong> Issues marked as PR Opened, Merged, or Working On It boost matching primary languages, repository topics, and issue domains.
              </li>
              <li>
                <strong>Negative Feedback (-0.02 / -0.05):</strong> Issues skipped lower the weight for that language/repo. Issues marked &quot;Too hard&quot; are automatically hidden for 30 days.
              </li>
              <li>
                <strong>Bounded Safeguards:</strong> Total outcome adjustments are strictly clamped to [-0.30, +0.30] to prevent filter bubbles and preserve diversity.
              </li>
            </ul>

            <div style={{ fontSize: "12px", color: "var(--color-fg-muted)" }}>
              All outcome history and memory weights are permanently removed whenever you initiate &quot;Delete my data&quot;.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

