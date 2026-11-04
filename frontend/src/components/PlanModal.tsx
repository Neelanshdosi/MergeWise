"use client";

import React, { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { ScoredIssueCandidate, IssuePlanResponse } from "@/lib/types";
import { fetchIssuePlan } from "@/lib/api";

interface PlanModalProps {
  isOpen: boolean;
  onClose: () => void;
  candidate: ScoredIssueCandidate;
  jwtToken?: string | null;
}

const LOADING_MESSAGES = [
  "Analyzing maintainer responsiveness & repository health...",
  "Searching CONTRIBUTING guides, dev docs & CI workflows for commands...",
  "Verifying candidate files against the GitHub repository tree...",
  "Synthesizing grounded starter plan with Gemini...",
  "Drafting polite issue claim comment...",
];

export default function PlanModal({
  isOpen,
  onClose,
  candidate,
  jwtToken,
}: PlanModalProps) {
  const { issue } = candidate;

  const [mounted, setMounted] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [plan, setPlan] = useState<IssuePlanResponse | null>(null);
  const [loadingStepIndex, setLoadingStepIndex] = useState<number>(0);
  const [copiedComment, setCopiedComment] = useState<boolean>(false);
  const [copiedSetup, setCopiedSetup] = useState<boolean>(false);
  const [copiedTest, setCopiedTest] = useState<boolean>(false);
  const [overrideEffort, setOverrideEffort] = useState<string>("");
  const [showHealthDetails, setShowHealthDetails] = useState<boolean>(false);

  const modalRef = useRef<HTMLDivElement>(null);
  const previousActiveElement = useRef<HTMLElement | null>(null);

  // Ensure portal only mounts on client
  useEffect(() => {
    setMounted(true);
  }, []);

  // Lock body scroll and save active element when open
  useEffect(() => {
    if (!isOpen) return;

    previousActiveElement.current = document.activeElement as HTMLElement;
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = originalOverflow;
      if (previousActiveElement.current && typeof previousActiveElement.current.focus === "function") {
        previousActiveElement.current.focus();
      }
    };
  }, [isOpen]);

  // Handle Escape key to close modal
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  // Cycle loading messages for visual feedback
  useEffect(() => {
    if (!loading) return;
    const interval = setInterval(() => {
      setLoadingStepIndex((prev) => (prev + 1) % LOADING_MESSAGES.length);
    }, 3500);
    return () => clearInterval(interval);
  }, [loading]);

  const loadPlan = async (forceRefresh: boolean = false, effortChoice?: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchIssuePlan(
        {
          repo_full_name: issue.repo_full_name,
          issue_number: issue.issue_number,
          title: issue.title,
          body: issue.body || "",
          labels: issue.labels || [],
          override_effort: effortChoice || overrideEffort || undefined,
          force_refresh: forceRefresh,
        },
        jwtToken
      );
      setPlan(res);
      if (res.difficulty && !overrideEffort) {
        setOverrideEffort(res.difficulty);
      }
    } catch (err: any) {
      console.error("Plan generation error:", err);
      setError(err?.message || "Failed to generate starter plan.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadPlan(false);
    } else {
      setPlan(null);
      setError(null);
      setOverrideEffort("");
      setShowHealthDetails(false);
    }
  }, [isOpen, issue.repo_full_name, issue.issue_number]);

  // Focus trap inside dialog
  const handleDialogKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Tab" && modalRef.current) {
      const focusableElements = modalRef.current.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      if (focusableElements.length === 0) return;

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === firstElement) {
          lastElement.focus();
          e.preventDefault();
        }
      } else {
        if (document.activeElement === lastElement) {
          firstElement.focus();
          e.preventDefault();
        }
      }
    }
  };

  if (!isOpen || !mounted) return null;

  const handleCopy = (text: string, type: "comment" | "setup" | "test") => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    if (type === "comment") {
      setCopiedComment(true);
      setTimeout(() => setCopiedComment(false), 2500);
    } else if (type === "setup") {
      setCopiedSetup(true);
      setTimeout(() => setCopiedSetup(false), 2000);
    } else {
      setCopiedTest(true);
      setTimeout(() => setCopiedTest(false), 2000);
    }
  };

  const handleEffortOverrideChange = (newEffort: string) => {
    setOverrideEffort(newEffort);
    loadPlan(true, newEffort);
  };

  const isCommandMissing = (cmd?: string) => {
    if (!cmd) return true;
    const lower = cmd.toLowerCase();
    return (
      lower.includes("not documented") ||
      lower.includes("not found") ||
      lower.includes("none") ||
      lower.trim() === ""
    );
  };

  const cleanStepText = (st: string) => {
    return st
      .replace(/\[.*?\]/g, "")
      .replace(/\(cited from .*?\)/gi, "")
      .replace(/\s{2,}/g, " ")
      .trim();
  };

  const repoHealth = plan?.repo_health;
  const contributingGuideUrl = repoHealth?.contributing_guide_path?.startsWith("http")
    ? repoHealth.contributing_guide_path
    : `https://github.com/${issue.repo_full_name}/blob/main/${repoHealth?.contributing_guide_path || "CONTRIBUTING.md"}`;

  const gitHubIssueUrl = issue.html_url || issue.issue_url;

  const modalContent = (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="plan-modal-title"
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(3, 7, 18, 0.88)",
        backdropFilter: "blur(12px)",
        WebkitBackdropFilter: "blur(12px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 100000,
        padding: "16px",
      }}
      onClick={onClose}
    >
      <div
        ref={modalRef}
        tabIndex={-1}
        onKeyDown={handleDialogKeyDown}
        className="glass-panel plan-modal-dialog"
        style={{
          width: "min(960px, 92vw)",
          height: "90vh",
          maxHeight: "90vh",
          display: "flex",
          flexDirection: "column",
          backgroundColor: "#0d131f",
          border: "1px solid rgba(99, 102, 241, 0.35)",
          boxShadow: "0 25px 60px rgba(0, 0, 0, 0.75), 0 0 35px rgba(99, 102, 241, 0.25)",
          borderRadius: "var(--radius-md)",
          overflow: "hidden",
          outline: "none",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Sticky Header */}
        <div
          className="plan-modal-header"
          style={{
            padding: "20px 28px",
            borderBottom: "1px solid var(--border-color)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            gap: "16px",
            background: "rgba(255, 255, 255, 0.025)",
            position: "sticky",
            top: 0,
            zIndex: 10,
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px", flexWrap: "wrap" }}>
              <span style={{ fontSize: "0.85rem", color: "var(--text-muted)", fontWeight: 600 }}>
                {issue.repo_full_name} #{issue.issue_number}
              </span>
              {plan?.cached && (
                <span
                  style={{
                    fontSize: "0.75rem",
                    padding: "2px 8px",
                    borderRadius: "12px",
                    background: "rgba(16, 185, 129, 0.15)",
                    color: "var(--success)",
                    border: "1px solid rgba(16, 185, 129, 0.3)",
                    fontWeight: 600,
                  }}
                  title="Plan served instantly from server cache"
                >
                  ⚡ Loaded from cache
                </span>
              )}
            </div>
            <h2
              id="plan-modal-title"
              style={{
                fontSize: "1.3rem",
                fontWeight: 700,
                color: "var(--text-primary)",
                lineHeight: 1.35,
                margin: 0,
              }}
            >
              How to Start: {issue.title}
            </h2>
          </div>

          <button
            onClick={onClose}
            aria-label="Close modal"
            style={{
              background: "rgba(255, 255, 255, 0.08)",
              border: "1px solid var(--border-color)",
              color: "var(--text-secondary)",
              width: "36px",
              height: "36px",
              borderRadius: "50%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
              fontSize: "1.3rem",
              lineHeight: 1,
              flexShrink: 0,
              transition: "background 0.15s ease, color 0.15s ease",
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.background = "rgba(255, 255, 255, 0.18)";
              e.currentTarget.style.color = "var(--text-primary)";
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.background = "rgba(255, 255, 255, 0.08)";
              e.currentTarget.style.color = "var(--text-secondary)";
            }}
          >
            ×
          </button>
        </div>

        {/* Scrollable Dialog Body */}
        <div
          className="plan-modal-body"
          style={{
            padding: "24px 28px",
            overflowY: "auto",
            flex: 1,
            display: "flex",
            flexDirection: "column",
            gap: "20px",
          }}
        >
          {/* Loading State */}
          {loading && (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                padding: "80px 20px",
                textAlign: "center",
                flex: 1,
              }}
            >
              <div
                style={{
                  width: "52px",
                  height: "52px",
                  borderRadius: "50%",
                  border: "3px solid rgba(99, 102, 241, 0.2)",
                  borderTopColor: "var(--accent-primary)",
                  animation: "planModalSpin 1s linear infinite",
                  marginBottom: "24px",
                }}
              />
              <p style={{ fontSize: "1.1rem", fontWeight: 600, color: "var(--text-primary)", marginBottom: "8px" }}>
                {LOADING_MESSAGES[loadingStepIndex]}
              </p>
              <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", maxWidth: "500px" }}>
                Grounded plan analysis typically takes 10–25s on first load as Gemini verifies documentation and GitHub repository trees.
              </p>
            </div>
          )}

          {/* Fatal Fetch Error State */}
          {!loading && error && !plan && (
            <div
              style={{
                padding: "24px",
                borderRadius: "var(--radius-sm)",
                backgroundColor: "rgba(239, 68, 68, 0.1)",
                border: "1px solid rgba(239, 68, 68, 0.3)",
                color: "#fca5a5",
              }}
            >
              <h4 style={{ fontWeight: 700, marginBottom: "8px", fontSize: "1.05rem" }}>Could not generate plan</h4>
              <p style={{ fontSize: "0.9rem", color: "var(--text-secondary)", marginBottom: "16px" }}>{error}</p>
              <button
                className="btn-primary"
                onClick={() => loadPlan(true)}
                style={{ padding: "8px 18px", fontSize: "0.85rem" }}
              >
                ↻ Try Again
              </button>
            </div>
          )}

          {/* Plan Content */}
          {!loading && plan && (
            <>
              {/* LLM Failure Notice with Retry */}
              {(!plan.llm_used || plan.llm_error) && (
                <div
                  style={{
                    padding: "16px 20px",
                    borderRadius: "var(--radius-sm)",
                    backgroundColor: "rgba(245, 158, 11, 0.12)",
                    border: "1px solid rgba(245, 158, 11, 0.35)",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: "14px",
                  }}
                >
                  <div style={{ flex: 1, minWidth: "260px" }}>
                    <div style={{ color: "#fde68a", fontWeight: 700, fontSize: "0.95rem", marginBottom: "4px" }}>
                      ⚠️ AI Plan Unavailable
                    </div>
                    <div style={{ color: "var(--text-secondary)", fontSize: "0.85rem", lineHeight: 1.4 }}>
                      {plan.llm_error || "AI service was unable to generate custom steps at this time."}
                    </div>
                  </div>
                  <button
                    onClick={() => loadPlan(true)}
                    disabled={loading}
                    className="btn-primary"
                    style={{
                      padding: "8px 16px",
                      fontSize: "0.85rem",
                      cursor: "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "6px",
                    }}
                  >
                    <span>↻</span> Retry
                  </button>
                </div>
              )}

              {/* 1. Summary Row: Effort Badge, Health Badges, Last Push */}
              <div
                style={{
                  padding: "18px 20px",
                  backgroundColor: "rgba(255, 255, 255, 0.03)",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-color)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: "14px",
                    marginBottom: "14px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                    <span style={{ fontSize: "0.85rem", color: "var(--text-muted)", fontWeight: 500 }}>
                      Estimated Effort:
                    </span>
                    <span
                      style={{
                        fontSize: "0.85rem",
                        fontWeight: 700,
                        padding: "4px 12px",
                        borderRadius: "6px",
                        background:
                          plan.difficulty === "Beginner"
                            ? "rgba(16, 185, 129, 0.15)"
                            : plan.difficulty === "Intermediate"
                            ? "rgba(99, 102, 241, 0.2)"
                            : "rgba(245, 158, 11, 0.2)",
                        color:
                          plan.difficulty === "Beginner"
                            ? "var(--success)"
                            : plan.difficulty === "Intermediate"
                            ? "#a5b4fc"
                            : "var(--warning)",
                        border: "1px solid currentColor",
                      }}
                    >
                      {plan.difficulty} ({plan.estimated_hours})
                    </span>

                    {!plan.llm_used ? (
                      <span
                        style={{
                          fontSize: "0.8rem",
                          color: "var(--warning)",
                          fontStyle: "italic",
                          backgroundColor: "rgba(245, 158, 11, 0.1)",
                          padding: "2px 8px",
                          borderRadius: "4px",
                          border: "1px solid rgba(245, 158, 11, 0.2)",
                        }}
                      >
                        rough estimate (AI unavailable)
                      </span>
                    ) : plan.effort_reasoning ? (
                      <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)", fontStyle: "italic" }}>
                        &mdash; {plan.effort_reasoning}
                      </span>
                    ) : null}
                  </div>

                  {/* Override Effort Selector */}
                  {plan.user_can_override_effort && (
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <label htmlFor="modal-effort-override" style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                        Override:
                      </label>
                      <select
                        id="modal-effort-override"
                        value={overrideEffort}
                        onChange={(e) => handleEffortOverrideChange(e.target.value)}
                        style={{
                          background: "rgba(0, 0, 0, 0.4)",
                          color: "var(--text-primary)",
                          border: "1px solid var(--border-color)",
                          borderRadius: "6px",
                          padding: "4px 10px",
                          fontSize: "0.8rem",
                          cursor: "pointer",
                        }}
                      >
                        <option value="Beginner">Beginner (1–3 hours)</option>
                        <option value="Intermediate">Intermediate (3–6 hours)</option>
                        <option value="Advanced">Advanced (6–12+ hours)</option>
                      </select>
                    </div>
                  )}
                </div>

                {/* Health Badges Row */}
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                    gap: "10px",
                  }}
                >
                  <div
                    style={{
                      padding: "10px 12px",
                      borderRadius: "6px",
                      background: "rgba(0, 0, 0, 0.25)",
                      border: "1px solid rgba(255, 255, 255, 0.05)",
                    }}
                  >
                    <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginBottom: "3px" }}>
                      Maintainer Response
                    </div>
                    <div
                      style={{
                        fontSize: "0.9rem",
                        fontWeight: 600,
                        color:
                          repoHealth?.response_time_human?.includes("insufficient") ||
                          repoHealth?.response_time_human?.includes("error")
                            ? "var(--text-muted)"
                            : "var(--text-primary)",
                        fontStyle: repoHealth?.response_time_human?.includes("insufficient") ? "italic" : "normal",
                      }}
                    >
                      {repoHealth?.response_time_human || "insufficient data"}
                    </div>
                  </div>

                  <div
                    style={{
                      padding: "10px 12px",
                      borderRadius: "6px",
                      background: "rgba(0, 0, 0, 0.25)",
                      border: "1px solid rgba(255, 255, 255, 0.05)",
                    }}
                  >
                    <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginBottom: "3px" }}>
                      Outside-contributor PR merge rate
                    </div>
                    <div
                      style={{
                        fontSize: "0.9rem",
                        fontWeight: 600,
                        color:
                          repoHealth?.first_time_pr_merge_rate_human?.includes("insufficient") ||
                          repoHealth?.first_time_pr_merge_rate_human?.includes("error")
                            ? "var(--text-muted)"
                            : "var(--success)",
                        fontStyle:
                          repoHealth?.first_time_pr_merge_rate_human?.includes("insufficient") ? "italic" : "normal",
                      }}
                    >
                      {repoHealth?.first_time_pr_merge_rate_human || "insufficient data"}
                    </div>
                  </div>

                  <div
                    style={{
                      padding: "10px 12px",
                      borderRadius: "6px",
                      background: "rgba(0, 0, 0, 0.25)",
                      border: "1px solid rgba(255, 255, 255, 0.05)",
                    }}
                  >
                    <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginBottom: "3px" }}>
                      Last Code Push
                    </div>
                    <div
                      style={{
                        fontSize: "0.9rem",
                        fontWeight: 600,
                        color: repoHealth?.days_since_last_push_human?.includes("error")
                          ? "#fca5a5"
                          : repoHealth?.days_since_last_push_human?.includes("insufficient")
                          ? "var(--text-muted)"
                          : "var(--text-primary)",
                        fontStyle:
                          repoHealth?.days_since_last_push_human?.includes("insufficient") ? "italic" : "normal",
                      }}
                    >
                      {repoHealth?.days_since_last_push_human || "insufficient data"}
                    </div>
                  </div>
                </div>

                {/* Collapsible Health Details Toggle (Collapsed by default) */}
                <div style={{ marginTop: "12px", paddingTop: "10px", borderTop: "1px solid rgba(255, 255, 255, 0.06)" }}>
                  <button
                    onClick={() => setShowHealthDetails(!showHealthDetails)}
                    style={{
                      background: "none",
                      border: "none",
                      color: "#a5b4fc",
                      fontSize: "0.8rem",
                      cursor: "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "6px",
                      padding: "2px 0",
                    }}
                  >
                    <span>{showHealthDetails ? "▲ Hide" : "▼ Show"} detailed repository health metrics</span>
                  </button>

                  {showHealthDetails && (
                    <div
                      style={{
                        marginTop: "10px",
                        padding: "12px",
                        backgroundColor: "rgba(0, 0, 0, 0.3)",
                        borderRadius: "6px",
                        fontSize: "0.8rem",
                        display: "flex",
                        flexDirection: "column",
                        gap: "6px",
                        color: "var(--text-secondary)",
                      }}
                    >
                      <div>
                        <strong>Overall Badge:</strong> {repoHealth?.overall_badge || "Unknown"}
                      </div>
                      <div>
                        <strong>Contributing Guide:</strong>{" "}
                        {repoHealth?.has_contributing_guide ? (
                          <a
                            href={contributingGuideUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{ color: "var(--success)", textDecoration: "underline" }}
                          >
                            ✓ {repoHealth.contributing_guide_path || "CONTRIBUTING.md"} ↗
                          </a>
                        ) : (
                          <span style={{ color: "var(--text-muted)", fontStyle: "italic" }}>Not found</span>
                        )}
                      </div>
                      {repoHealth?.summary && (
                        <div>
                          <strong>Summary:</strong> {repoHealth.summary}
                        </div>
                      )}
                      <div>
                        <strong>Sampled:</strong> {repoHealth?.sampled_issues_count || 0} issues, {repoHealth?.sampled_prs_count || 0} pull requests
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* 2. Setup & Test Commands Card */}
              <div
                style={{
                  padding: "18px 20px",
                  backgroundColor: "rgba(255, 255, 255, 0.03)",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-color)",
                }}
              >
                <h3
                  style={{
                    fontSize: "0.95rem",
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    color: "var(--text-muted)",
                    marginBottom: "14px",
                  }}
                >
                  Verified Setup &amp; Test Commands
                </h3>

                <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
                  {/* Setup Command */}
                  <div
                    style={{
                      background: "rgba(0, 0, 0, 0.35)",
                      border: "1px solid var(--border-color)",
                      borderRadius: "6px",
                      padding: "12px 14px",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        marginBottom: "8px",
                        flexWrap: "wrap",
                        gap: "8px",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                        <span style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-primary)" }}>
                          Environment Setup:
                        </span>
                        {!isCommandMissing(plan.setup_command) && (
                          <span
                            style={{
                              fontSize: "0.72rem",
                              padding: "2px 8px",
                              borderRadius: "4px",
                              backgroundColor: "rgba(99, 102, 241, 0.15)",
                              color: "#c7d2fe",
                              border: "1px solid rgba(99, 102, 241, 0.3)",
                              fontWeight: 500,
                            }}
                          >
                            Source: {plan.setup_citation}
                          </span>
                        )}
                      </div>

                      {!isCommandMissing(plan.setup_command) && (
                        <button
                          onClick={() => handleCopy(plan.setup_command, "setup")}
                          style={{
                            background: "none",
                            border: "none",
                            color: copiedSetup ? "var(--success)" : "#a5b4fc",
                            cursor: "pointer",
                            fontSize: "0.78rem",
                            fontWeight: 600,
                          }}
                        >
                          {copiedSetup ? "✓ Copied" : "Copy Setup"}
                        </button>
                      )}
                    </div>

                    {isCommandMissing(plan.setup_command) ? (
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          padding: "4px 0",
                          flexWrap: "wrap",
                          gap: "8px",
                        }}
                      >
                        <span style={{ fontSize: "0.85rem", color: "var(--text-muted)", fontStyle: "italic" }}>
                          No setup command documented. Check the CONTRIBUTING guide or README.
                        </span>
                        {repoHealth?.has_contributing_guide && (
                          <a
                            href={contributingGuideUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{
                              fontSize: "0.8rem",
                              color: "#a5b4fc",
                              textDecoration: "underline",
                              fontWeight: 500,
                            }}
                          >
                            Check {repoHealth.contributing_guide_path || "CONTRIBUTING.md"} ↗
                          </a>
                        )}
                      </div>
                    ) : (
                      <pre
                        style={{
                          margin: 0,
                          fontFamily: "monospace",
                          fontSize: "0.85rem",
                          color: "#e2e8f0",
                          whiteSpace: "pre-wrap",
                          wordBreak: "break-all",
                        }}
                      >
                        {plan.setup_command}
                      </pre>
                    )}
                  </div>

                  {/* Test Command */}
                  <div
                    style={{
                      background: "rgba(0, 0, 0, 0.35)",
                      border: "1px solid var(--border-color)",
                      borderRadius: "6px",
                      padding: "12px 14px",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        marginBottom: "8px",
                        flexWrap: "wrap",
                        gap: "8px",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                        <span style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-primary)" }}>
                          Run Test Suite:
                        </span>
                        {!isCommandMissing(plan.test_command) && (
                          <span
                            style={{
                              fontSize: "0.72rem",
                              padding: "2px 8px",
                              borderRadius: "4px",
                              backgroundColor: "rgba(99, 102, 241, 0.15)",
                              color: "#c7d2fe",
                              border: "1px solid rgba(99, 102, 241, 0.3)",
                              fontWeight: 500,
                            }}
                          >
                            Source: {plan.test_citation}
                          </span>
                        )}
                      </div>

                      {!isCommandMissing(plan.test_command) && (
                        <button
                          onClick={() => handleCopy(plan.test_command, "test")}
                          style={{
                            background: "none",
                            border: "none",
                            color: copiedTest ? "var(--success)" : "#a5b4fc",
                            cursor: "pointer",
                            fontSize: "0.78rem",
                            fontWeight: 600,
                          }}
                        >
                          {copiedTest ? "✓ Copied" : "Copy Test"}
                        </button>
                      )}
                    </div>

                    {isCommandMissing(plan.test_command) ? (
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          padding: "4px 0",
                          flexWrap: "wrap",
                          gap: "8px",
                        }}
                      >
                        <span style={{ fontSize: "0.85rem", color: "var(--text-muted)", fontStyle: "italic" }}>
                          No test command documented. Check the README or CI config.
                        </span>
                        {repoHealth?.has_contributing_guide && (
                          <a
                            href={contributingGuideUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{
                              fontSize: "0.8rem",
                              color: "#a5b4fc",
                              textDecoration: "underline",
                              fontWeight: 500,
                            }}
                          >
                            Check {repoHealth.contributing_guide_path || "CONTRIBUTING.md"} ↗
                          </a>
                        )}
                      </div>
                    ) : (
                      <pre
                        style={{
                          margin: 0,
                          fontFamily: "monospace",
                          fontSize: "0.85rem",
                          color: "#e2e8f0",
                          whiteSpace: "pre-wrap",
                          wordBreak: "break-all",
                        }}
                      >
                        {plan.test_command}
                      </pre>
                    )}
                  </div>
                </div>
              </div>

              {/* 3. Verified Files to Edit Card */}
              <div
                style={{
                  padding: "18px 20px",
                  backgroundColor: "rgba(255, 255, 255, 0.03)",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-color)",
                }}
              >
                <h3
                  style={{
                    fontSize: "0.95rem",
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    color: "var(--text-muted)",
                    marginBottom: "12px",
                  }}
                >
                  Verified Files to Inspect / Edit
                </h3>
                {plan.verified_files_to_edit && plan.verified_files_to_edit.length > 0 ? (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                    {plan.verified_files_to_edit.map((f, i) => (
                      <span
                        key={i}
                        style={{
                          fontFamily: "monospace",
                          fontSize: "0.82rem",
                          padding: "6px 12px",
                          borderRadius: "6px",
                          background: "rgba(16, 185, 129, 0.1)",
                          border: "1px solid rgba(16, 185, 129, 0.25)",
                          color: "#a7f3d0",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "6px",
                        }}
                      >
                        <span>✓</span> {f}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", fontStyle: "italic", margin: 0 }}>
                    No specific source files were cited in the issue body. Locate relevant modules using the steps below.
                  </p>
                )}
              </div>

              {/* 4. Numbered Implementation Steps Card (Hidden on LLM failure) */}
              {plan.llm_used && !plan.llm_error && plan.steps && plan.steps.length > 0 && (
                <div
                  style={{
                    padding: "18px 20px",
                    backgroundColor: "rgba(255, 255, 255, 0.03)",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--border-color)",
                  }}
                >
                  <h3
                    style={{
                      fontSize: "0.95rem",
                      fontWeight: 700,
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                      color: "var(--text-muted)",
                      marginBottom: "14px",
                    }}
                  >
                    Step-by-Step Implementation Strategy
                  </h3>
                  <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                    {plan.steps.map((st, i) => (
                      <div
                        key={i}
                        style={{
                          display: "flex",
                          gap: "12px",
                          padding: "12px 14px",
                          borderRadius: "var(--radius-sm)",
                          background: "rgba(0, 0, 0, 0.25)",
                          border: "1px solid rgba(255, 255, 255, 0.05)",
                          alignItems: "flex-start",
                        }}
                      >
                        <span
                          style={{
                            width: "24px",
                            height: "24px",
                            borderRadius: "50%",
                            background: "var(--accent-gradient)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: "0.75rem",
                            fontWeight: 700,
                            flexShrink: 0,
                            marginTop: "2px",
                          }}
                        >
                          {i + 1}
                        </span>
                        <p style={{ fontSize: "0.9rem", color: "var(--text-primary)", lineHeight: 1.5, margin: 0 }}>
                          {cleanStepText(st)}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 5. Claim Comment Card (Hidden on LLM failure) */}
              {plan.llm_used && !plan.llm_error && plan.draft_claim_comment && (
                <div
                  style={{
                    padding: "18px 20px",
                    borderRadius: "var(--radius-sm)",
                    background: "rgba(99, 102, 241, 0.06)",
                    border: "1px solid rgba(99, 102, 241, 0.25)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      marginBottom: "8px",
                      flexWrap: "wrap",
                      gap: "8px",
                    }}
                  >
                    <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--text-primary)" }}>
                      Polite Claim Comment (Ready to Paste)
                    </span>
                    <button
                      onClick={() => handleCopy(plan.draft_claim_comment, "comment")}
                      className="btn-primary"
                      style={{ padding: "6px 14px", fontSize: "0.8rem", borderRadius: "6px" }}
                    >
                      {copiedComment ? "✓ Copied to Clipboard!" : "Copy Claim Comment"}
                    </button>
                  </div>
                  <div
                    style={{
                      fontSize: "0.85rem",
                      color: "var(--text-secondary)",
                      backgroundColor: "rgba(0, 0, 0, 0.35)",
                      padding: "12px 14px",
                      borderRadius: "6px",
                      border: "1px dashed rgba(255, 255, 255, 0.12)",
                      lineHeight: 1.5,
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {plan.draft_claim_comment}
                  </div>
                  <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "8px", marginBottom: 0 }}>
                    🔒 <em>MergeWise never posts to GitHub automatically. Click to copy and paste onto the issue thread yourself.</em>
                  </p>
                </div>
              )}
            </>
          )}
        </div>

        {/* Sticky Footer: Always Visible Actions */}
        <div
          className="plan-modal-footer"
          style={{
            padding: "16px 28px",
            borderTop: "1px solid var(--border-color)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            background: "rgba(13, 19, 31, 0.95)",
            backdropFilter: "blur(12px)",
            WebkitBackdropFilter: "blur(12px)",
            position: "sticky",
            bottom: 0,
            zIndex: 10,
            flexWrap: "wrap",
            gap: "12px",
          }}
        >
          <div>
            {plan && (
              <button
                onClick={() => loadPlan(true)}
                disabled={loading}
                style={{
                  background: "none",
                  border: "none",
                  color: "var(--text-muted)",
                  fontSize: "0.8rem",
                  cursor: "pointer",
                  textDecoration: "underline",
                }}
              >
                ↻ Refresh Live Plan
              </button>
            )}
          </div>

          <div style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>
            {/* Sticky Action 1: Copy claim comment (if available) */}
            {plan?.llm_used && !plan?.llm_error && plan?.draft_claim_comment && (
              <button
                onClick={() => handleCopy(plan.draft_claim_comment, "comment")}
                className="btn-primary"
                style={{ padding: "8px 18px", fontSize: "0.85rem", cursor: "pointer" }}
              >
                {copiedComment ? "✓ Copied Claim Comment!" : "Copy Claim Comment"}
              </button>
            )}

            {/* Sticky Action 2: Open on GitHub */}
            <a
              href={gitHubIssueUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-secondary"
              style={{ padding: "8px 18px", fontSize: "0.85rem", display: "inline-flex", alignItems: "center", gap: "6px" }}
            >
              Open on GitHub ↗
            </a>

            <button
              onClick={onClose}
              className="btn-secondary"
              style={{ padding: "8px 16px", fontSize: "0.85rem" }}
            >
              Close
            </button>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes planModalSpin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        @media (max-width: 768px) {
          .plan-modal-dialog {
            width: 100vw !important;
            height: 100vh !important;
            max-height: 100vh !important;
            border-radius: 0 !important;
            border: none !important;
          }
          .plan-modal-header {
            padding: 16px !important;
          }
          .plan-modal-body {
            padding: 16px !important;
          }
          .plan-modal-footer {
            padding: 12px 16px !important;
            flex-direction: column-reverse !important;
            gap: 10px !important;
          }
          .plan-modal-footer > div {
            width: 100% !important;
            justify-content: stretch !important;
          }
          .plan-modal-footer button, .plan-modal-footer a {
            flex: 1 !important;
            text-align: center !important;
            justify-content: center !important;
          }
        }
      `}</style>
    </div>
  );

  return createPortal(modalContent, document.body);
}
