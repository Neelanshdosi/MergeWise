"use client";

import React, { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { ScoredIssueCandidate, IssuePlanResponse } from "@/lib/types";
import { fetchIssuePlan } from "@/lib/api";
import { XIcon, CopyIcon, CheckIcon, SyncIcon, AlertIcon } from "./Octicons";

interface PlanModalProps {
  isOpen: boolean;
  onClose: () => void;
  candidate: ScoredIssueCandidate;
  jwtToken?: string | null;
  initialPlan?: IssuePlanResponse;
  disablePortal?: boolean;
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
  initialPlan,
  disablePortal = false,
}: PlanModalProps) {
  const { issue } = candidate;

  const [mounted, setMounted] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(!initialPlan);
  const [error, setError] = useState<string | null>(null);
  const [plan, setPlan] = useState<IssuePlanResponse | null>(initialPlan || null);
  const [loadingStepIndex, setLoadingStepIndex] = useState<number>(0);
  const [copiedComment, setCopiedComment] = useState<boolean>(false);
  const [copiedSetup, setCopiedSetup] = useState<boolean>(false);
  const [copiedTest, setCopiedTest] = useState<boolean>(false);
  const [overrideEffort, setOverrideEffort] = useState<string>("");
  const [showHealthDetails, setShowHealthDetails] = useState<boolean>(false);

  const modalRef = useRef<HTMLDivElement>(null);
  const previousActiveElement = useRef<HTMLElement | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Lock body scroll and trap focus
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

  // Handle Escape key
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

  // Cycle loading messages
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
      if (initialPlan) {
        setPlan(initialPlan);
        setLoading(false);
        if (initialPlan.difficulty && !overrideEffort) {
          setOverrideEffort(initialPlan.difficulty);
        }
      } else {
        loadPlan(false);
      }
    } else {
      setPlan(null);
      setError(null);
      setOverrideEffort("");
      setShowHealthDetails(false);
    }
  }, [isOpen, issue.repo_full_name, issue.issue_number, initialPlan]);

  // Focus trap
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

  if (!isOpen) return null;
  if (!disablePortal && !mounted) return null;

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
      aria-labelledby="primer-plan-title"
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(27, 31, 36, 0.7)",
        backdropFilter: "blur(4px)",
        WebkitBackdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 99999,
        padding: "16px",
      }}
      onClick={onClose}
    >
      <div
        ref={modalRef}
        tabIndex={-1}
        onKeyDown={handleDialogKeyDown}
        className="Box"
        style={{
          width: "min(768px, 94vw)",
          maxHeight: "88vh",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          outline: "none",
          boxShadow: "0 8px 24px rgba(140, 149, 159, 0.2)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="Box-header" style={{ padding: "14px 16px" }}>
          <div style={{ flex: 1, minWidth: 0, paddingRight: "12px" }}>
            <div style={{ fontSize: "12px", color: "var(--color-fg-muted)", marginBottom: "2px" }}>
              {issue.repo_full_name} #{issue.issue_number}
            </div>
            <h2
              id="primer-plan-title"
              style={{
                fontSize: "16px",
                fontWeight: 600,
                color: "var(--color-fg-default)",
                margin: 0,
                lineHeight: 1.3,
                wordBreak: "break-word",
              }}
            >
              How to Start: {issue.title}
            </h2>
          </div>

          <button
            onClick={onClose}
            className="btn-octicon"
            aria-label="Close dialog"
            title="Close (Esc)"
          >
            <XIcon size={16} />
          </button>
        </div>

        {/* Scrollable Body */}
        <div
          className="Box-body"
          style={{
            overflowY: "auto",
            flex: 1,
            display: "flex",
            flexDirection: "column",
            gap: "16px",
            padding: "16px",
          }}
        >
          {/* Loading State */}
          {loading && (
            <div style={{ padding: "48px 16px", textAlign: "center" }}>
              <div
                style={{
                  display: "inline-block",
                  animation: "spin 1s linear infinite",
                  marginBottom: "16px",
                  color: "var(--color-accent-fg)",
                }}
              >
                <SyncIcon size={28} />
              </div>
              <div style={{ fontSize: "14px", fontWeight: 600, color: "var(--color-fg-default)", marginBottom: "6px" }}>
                {LOADING_MESSAGES[loadingStepIndex]}
              </div>
              <div style={{ fontSize: "12px", color: "var(--color-fg-muted)" }}>
                Checking repository manifests, documentation, and maintainer responsiveness.
              </div>
            </div>
          )}

          {/* Fatal Error State */}
          {!loading && error && !plan && (
            <div className="Flash Flash--error">
              <AlertIcon size={16} />
              <div style={{ flex: 1 }}>
                <strong>Could not generate plan:</strong> {error}
                <div style={{ marginTop: "10px" }}>
                  <button onClick={() => loadPlan(true)} className="btn btn-sm btn-primary">
                    Try Again
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Plan Content */}
          {!loading && plan && (
            <>
              {/* LLM Fallback Warning */}
              {(!plan.llm_used || plan.llm_error) && (
                <div className="Flash Flash--warning">
                  <AlertIcon size={16} />
                  <div style={{ flex: 1 }}>
                    <strong>Automated steps unavailable:</strong> {plan.llm_error || "Could not synthesize AI steps."}
                    <div style={{ marginTop: "6px" }}>
                      <button onClick={() => loadPlan(true)} className="btn btn-sm">
                        Retry synthesis
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* 1. Effort & Repository Health Box */}
              <div
                style={{
                  border: "1px solid var(--color-border-default)",
                  borderRadius: "var(--border-radius)",
                  padding: "14px",
                  backgroundColor: "var(--color-canvas-subtle)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: "8px",
                    marginBottom: "12px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                    <span style={{ fontSize: "12px", color: "var(--color-fg-muted)", fontWeight: 500 }}>
                      Estimated Effort:
                    </span>
                    <span
                      className="IssueLabel"
                      style={{
                        fontWeight: 600,
                        backgroundColor:
                          plan.difficulty === "Beginner"
                            ? "var(--color-success-subtle)"
                            : plan.difficulty === "Intermediate"
                            ? "var(--color-accent-subtle)"
                            : "var(--color-attention-subtle)",
                        color:
                          plan.difficulty === "Beginner"
                            ? "var(--color-success-fg)"
                            : plan.difficulty === "Intermediate"
                            ? "var(--color-accent-fg)"
                            : "var(--color-attention-fg)",
                        borderColor: "currentColor",
                      }}
                    >
                      {plan.difficulty} ({plan.estimated_hours})
                    </span>

                    {plan.effort_reasoning && (
                      <span style={{ fontSize: "12px", color: "var(--color-fg-muted)", fontStyle: "italic" }}>
                        — {plan.effort_reasoning}
                      </span>
                    )}
                  </div>

                  {plan.user_can_override_effort && (
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      <label htmlFor="effort-override-select" style={{ fontSize: "12px", color: "var(--color-fg-muted)" }}>
                        Override:
                      </label>
                      <select
                        id="effort-override-select"
                        value={overrideEffort}
                        onChange={(e) => handleEffortOverrideChange(e.target.value)}
                        style={{
                          fontSize: "12px",
                          padding: "3px 8px",
                          borderRadius: "var(--border-radius)",
                          border: "1px solid var(--color-border-default)",
                          backgroundColor: "var(--color-canvas-default)",
                          color: "var(--color-fg-default)",
                        }}
                      >
                        <option value="Beginner">Beginner (1–3 hours)</option>
                        <option value="Intermediate">Intermediate (3–6 hours)</option>
                        <option value="Advanced">Advanced (6–12+ hours)</option>
                      </select>
                    </div>
                  )}
                </div>

                {/* Health Metrics Row */}
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                    gap: "8px",
                  }}
                >
                  <div
                    style={{
                      padding: "8px 10px",
                      borderRadius: "var(--border-radius)",
                      backgroundColor: "var(--color-canvas-default)",
                      border: "1px solid var(--color-border-default)",
                    }}
                  >
                    <div style={{ fontSize: "11px", color: "var(--color-fg-muted)", marginBottom: "2px" }}>
                      Maintainer Response
                    </div>
                    <div style={{ fontSize: "13px", fontWeight: 600, color: "var(--color-fg-default)" }}>
                      {repoHealth?.response_time_human || "insufficient data"}
                    </div>
                  </div>

                  <div
                    style={{
                      padding: "8px 10px",
                      borderRadius: "var(--border-radius)",
                      backgroundColor: "var(--color-canvas-default)",
                      border: "1px solid var(--color-border-default)",
                    }}
                  >
                    <div style={{ fontSize: "11px", color: "var(--color-fg-muted)", marginBottom: "2px" }}>
                      Newcomer Merge Rate
                    </div>
                    <div style={{ fontSize: "13px", fontWeight: 600, color: "var(--color-success-fg)" }}>
                      {repoHealth?.first_time_pr_merge_rate_human || "insufficient data"}
                    </div>
                  </div>

                  <div
                    style={{
                      padding: "8px 10px",
                      borderRadius: "var(--border-radius)",
                      backgroundColor: "var(--color-canvas-default)",
                      border: "1px solid var(--color-border-default)",
                    }}
                  >
                    <div style={{ fontSize: "11px", color: "var(--color-fg-muted)", marginBottom: "2px" }}>
                      Last Code Push
                    </div>
                    <div style={{ fontSize: "13px", fontWeight: 600, color: "var(--color-fg-default)" }}>
                      {repoHealth?.days_since_last_push_human || "insufficient data"}
                    </div>
                  </div>
                </div>

                {/* Collapsible Health Details Toggle */}
                <div style={{ marginTop: "10px", paddingTop: "8px", borderTop: "1px solid var(--color-border-default)" }}>
                  <button
                    onClick={() => setShowHealthDetails(!showHealthDetails)}
                    style={{
                      background: "none",
                      border: "none",
                      color: "var(--color-accent-fg)",
                      fontSize: "12px",
                      cursor: "pointer",
                      padding: 0,
                    }}
                  >
                    {showHealthDetails ? "▲ Hide detailed health metrics" : "▼ Show detailed health metrics"}
                  </button>

                  {showHealthDetails && (
                    <div
                      style={{
                        marginTop: "8px",
                        padding: "8px 10px",
                        backgroundColor: "var(--color-canvas-default)",
                        borderRadius: "var(--border-radius)",
                        border: "1px solid var(--color-border-default)",
                        fontSize: "12px",
                        display: "flex",
                        flexDirection: "column",
                        gap: "4px",
                        color: "var(--color-fg-default)",
                      }}
                    >
                      <div>
                        <strong>Overall status:</strong> {repoHealth?.overall_badge || "Unknown"}
                      </div>
                      <div>
                        <strong>Contributing Guide:</strong>{" "}
                        {repoHealth?.has_contributing_guide ? (
                          <a
                            href={contributingGuideUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            ✓ {repoHealth.contributing_guide_path || "CONTRIBUTING.md"} ↗
                          </a>
                        ) : (
                          <span style={{ color: "var(--color-fg-muted)" }}>Not found</span>
                        )}
                      </div>
                      {repoHealth?.summary && (
                        <div>
                          <strong>Summary:</strong> {repoHealth.summary}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* 2. Setup & Test Commands */}
              <div
                style={{
                  border: "1px solid var(--color-border-default)",
                  borderRadius: "var(--border-radius)",
                  padding: "14px",
                }}
              >
                <div style={{ fontSize: "12px", fontWeight: 600, color: "var(--color-fg-muted)", textTransform: "uppercase", marginBottom: "10px" }}>
                  Verified Setup &amp; Test Commands
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  {/* Setup */}
                  <div
                    style={{
                      backgroundColor: "var(--color-canvas-subtle)",
                      border: "1px solid var(--color-border-default)",
                      borderRadius: "var(--border-radius)",
                      padding: "10px 12px",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                      <span style={{ fontSize: "12px", fontWeight: 600 }}>
                        Setup Environment:
                        {plan.setup_citation && (
                          <span style={{ fontSize: "11px", color: "var(--color-fg-muted)", fontWeight: 400, marginLeft: "6px" }}>
                            (Source: {plan.setup_citation})
                          </span>
                        )}
                      </span>
                      {!isCommandMissing(plan.setup_command) && (
                        <button
                          onClick={() => handleCopy(plan.setup_command, "setup")}
                          className="btn btn-sm"
                          style={{ height: "24px", padding: "0 8px", fontSize: "11px" }}
                        >
                          {copiedSetup ? <CheckIcon size={12} color="var(--color-success-fg)" /> : <CopyIcon size={12} />}
                          <span>{copiedSetup ? "Copied" : "Copy"}</span>
                        </button>
                      )}
                    </div>

                    {isCommandMissing(plan.setup_command) ? (
                      <span style={{ fontSize: "12px", color: "var(--color-fg-muted)", fontStyle: "italic" }}>
                        No setup command documented. Check CONTRIBUTING guide or README.
                      </span>
                    ) : (
                      <pre style={{ margin: 0, padding: "6px 8px", backgroundColor: "var(--color-canvas-default)", borderRadius: "var(--border-radius)", overflowX: "auto" }}>
                        <code>{plan.setup_command}</code>
                      </pre>
                    )}
                  </div>

                  {/* Test */}
                  <div
                    style={{
                      backgroundColor: "var(--color-canvas-subtle)",
                      border: "1px solid var(--color-border-default)",
                      borderRadius: "var(--border-radius)",
                      padding: "10px 12px",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                      <span style={{ fontSize: "12px", fontWeight: 600 }}>
                        Run Test Suite:
                        {plan.test_citation && (
                          <span style={{ fontSize: "11px", color: "var(--color-fg-muted)", fontWeight: 400, marginLeft: "6px" }}>
                            (Source: {plan.test_citation})
                          </span>
                        )}
                      </span>
                      {!isCommandMissing(plan.test_command) && (
                        <button
                          onClick={() => handleCopy(plan.test_command, "test")}
                          className="btn btn-sm"
                          style={{ height: "24px", padding: "0 8px", fontSize: "11px" }}
                        >
                          {copiedTest ? <CheckIcon size={12} color="var(--color-success-fg)" /> : <CopyIcon size={12} />}
                          <span>{copiedTest ? "Copied" : "Copy"}</span>
                        </button>
                      )}
                    </div>

                    {isCommandMissing(plan.test_command) ? (
                      <span style={{ fontSize: "12px", color: "var(--color-fg-muted)", fontStyle: "italic" }}>
                        No test command documented. Check repository CI configuration.
                      </span>
                    ) : (
                      <pre style={{ margin: 0, padding: "6px 8px", backgroundColor: "var(--color-canvas-default)", borderRadius: "var(--border-radius)", overflowX: "auto" }}>
                        <code>{plan.test_command}</code>
                      </pre>
                    )}
                  </div>
                </div>
              </div>

              {/* 3. Verified Files to Inspect / Edit */}
              <div
                style={{
                  border: "1px solid var(--color-border-default)",
                  borderRadius: "var(--border-radius)",
                  padding: "14px",
                }}
              >
                <div style={{ fontSize: "12px", fontWeight: 600, color: "var(--color-fg-muted)", textTransform: "uppercase", marginBottom: "8px" }}>
                  Verified Files to Inspect / Edit
                </div>
                {plan.verified_files_to_edit && plan.verified_files_to_edit.length > 0 ? (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                    {plan.verified_files_to_edit.map((f, i) => (
                      <code
                        key={i}
                        style={{
                          padding: "3px 8px",
                          borderRadius: "var(--border-radius)",
                          backgroundColor: "var(--color-canvas-subtle)",
                          border: "1px solid var(--color-border-default)",
                          color: "var(--color-fg-default)",
                        }}
                      >
                        ✓ {f}
                      </code>
                    ))}
                  </div>
                ) : (
                  <span style={{ fontSize: "12px", color: "var(--color-fg-muted)", fontStyle: "italic" }}>
                    No specific source files cited in issue body.
                  </span>
                )}
              </div>

              {/* 4. Implementation Steps */}
              {plan.llm_used && !plan.llm_error && plan.steps && plan.steps.length > 0 && (
                <div
                  style={{
                    border: "1px solid var(--color-border-default)",
                    borderRadius: "var(--border-radius)",
                    padding: "14px",
                  }}
                >
                  <div style={{ fontSize: "12px", fontWeight: 600, color: "var(--color-fg-muted)", textTransform: "uppercase", marginBottom: "10px" }}>
                    Step-by-Step Implementation Strategy
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    {plan.steps.map((st, i) => (
                      <div
                        key={i}
                        style={{
                          display: "flex",
                          gap: "10px",
                          padding: "8px 10px",
                          borderRadius: "var(--border-radius)",
                          backgroundColor: "var(--color-canvas-subtle)",
                          border: "1px solid var(--color-border-default)",
                          alignItems: "flex-start",
                        }}
                      >
                        <span
                          style={{
                            width: "20px",
                            height: "20px",
                            borderRadius: "50%",
                            backgroundColor: "var(--color-accent-subtle)",
                            color: "var(--color-accent-fg)",
                            display: "inline-flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: "11px",
                            fontWeight: 700,
                            flexShrink: 0,
                            marginTop: "1px",
                          }}
                        >
                          {i + 1}
                        </span>
                        <div style={{ fontSize: "13px", color: "var(--color-fg-default)", lineHeight: 1.45 }}>
                          {cleanStepText(st)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 5. Claim Comment */}
              {plan.llm_used && !plan.llm_error && plan.draft_claim_comment && (
                <div
                  style={{
                    border: "1px solid var(--color-accent-border)",
                    backgroundColor: "var(--color-accent-subtle)",
                    borderRadius: "var(--border-radius)",
                    padding: "14px",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                    <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--color-fg-default)" }}>
                      Polite Claim Comment (Ready to Paste)
                    </span>
                    <button
                      onClick={() => handleCopy(plan.draft_claim_comment, "comment")}
                      className="btn btn-sm btn-primary"
                    >
                      {copiedComment ? <CheckIcon size={12} /> : <CopyIcon size={12} />}
                      <span>{copiedComment ? "Copied to Clipboard!" : "Copy Claim Comment"}</span>
                    </button>
                  </div>
                  <pre
                    style={{
                      margin: 0,
                      padding: "10px 12px",
                      backgroundColor: "var(--color-canvas-default)",
                      border: "1px solid var(--color-border-default)",
                      borderRadius: "var(--border-radius)",
                      whiteSpace: "pre-wrap",
                      fontSize: "12px",
                      color: "var(--color-fg-default)",
                    }}
                  >
                    <code>{plan.draft_claim_comment}</code>
                  </pre>
                  <div style={{ fontSize: "11px", color: "var(--color-fg-muted)", marginTop: "6px" }}>
                    MergeWise never posts to GitHub automatically. Click to copy and paste onto the issue thread yourself.
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: "12px 16px",
            borderTop: "1px solid var(--color-border-default)",
            backgroundColor: "var(--color-canvas-subtle)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "10px",
          }}
        >
          <div>
            {plan && (
              <button
                onClick={() => loadPlan(true)}
                disabled={loading}
                className="btn btn-sm"
              >
                <SyncIcon size={13} />
                <span>Refresh Live Plan</span>
              </button>
            )}
          </div>

          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            {plan?.llm_used && !plan?.llm_error && plan?.draft_claim_comment && (
              <button
                onClick={() => handleCopy(plan.draft_claim_comment, "comment")}
                className="btn btn-sm btn-primary"
              >
                {copiedComment ? "Copied!" : "Copy Claim Comment"}
              </button>
            )}

            <a
              href={gitHubIssueUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-sm"
            >
              Open on GitHub ↗
            </a>

            <button onClick={onClose} className="btn btn-sm">
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  if (disablePortal || typeof document === "undefined") {
    return modalContent;
  }

  return createPortal(modalContent, document.body);
}
