"use client";

import React, { useEffect, useState } from "react";
import { useAuth, useUser, SignInButton, SignedIn, SignedOut } from "@clerk/nextjs";
import { fetchUserProfile, fetchRecommendations, submitColdStart, deleteMyData } from "@/lib/api";
import { UserProfileResponse, RecommendationsResponse, ColdStartQuestionnaire } from "@/lib/types";
import IssueCard from "@/components/IssueCard";
import ColdStartModal from "@/components/ColdStartModal";

export default function HomePage() {
  const { getToken, isSignedIn } = useAuth();
  const { user } = useUser();
  const [profileMeta, setProfileMeta] = useState<UserProfileResponse | null>(null);
  const [recData, setRecData] = useState<RecommendationsResponse | null>(null);
  const [loadingRecs, setLoadingRecs] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [showColdStartOverride, setShowColdStartOverride] = useState<boolean>(false);
  const [showQueriesDrawer, setShowQueriesDrawer] = useState<boolean>(false);
  const [refreshCooldown, setRefreshCooldown] = useState<number>(0);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<boolean>(false);
  const [isDeletingData, setIsDeletingData] = useState<boolean>(false);
  const [deleteSuccessMsg, setDeleteSuccessMsg] = useState<string | null>(null);

  useEffect(() => {
    if (refreshCooldown <= 0) return;
    const interval = setInterval(() => {
      setRefreshCooldown((prev) => Math.max(0, prev - 1));
    }, 1000);
    return () => clearInterval(interval);
  }, [refreshCooldown]);

  const loadData = async (forceRefresh: boolean = false) => {
    if (!isSignedIn) return;
    if (forceRefresh) {
      setRefreshCooldown(30);
    }
    setLoadingRecs(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Could not acquire Clerk session token.");

      // 1. Get backend user verification
      const userMeta = await fetchUserProfile(token);
      setProfileMeta(userMeta);

      // 2. Fetch live recommendations & pipeline telemetry
      const recs = await fetchRecommendations(token, forceRefresh);
      setRecData(recs);
    } catch (err: any) {
      console.error("Failed to load recommendations:", err);
      setError(err.message || "Failed to communicate with recommendation service.");
    } finally {
      setLoadingRecs(false);
    }
  };

  const handleColdStartSubmit = async (answers: ColdStartQuestionnaire) => {
    setLoadingRecs(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Missing session token.");
      await submitColdStart(token, answers);
      setShowColdStartOverride(false);
      // Reload recommendations with new preferences
      const recs = await fetchRecommendations(token, true);
      setRecData(recs);
    } catch (err: any) {
      setError(err.message || "Failed to update preferences.");
    } finally {
      setLoadingRecs(false);
    }
  };

  const handleDeleteMyData = async () => {
    setIsDeletingData(true);
    try {
      const token = await getToken();
      if (!token) throw new Error("Missing session token.");
      await deleteMyData(token);
      setShowDeleteConfirm(false);
      setDeleteSuccessMsg("All your profile, issue outcomes, and recommendations data have been permanently deleted.");
      setTimeout(() => setDeleteSuccessMsg(null), 6000);
      // Reload recommendations cleanly without previous history
      await loadData(true);
    } catch (err: any) {
      setError(err.message || "Failed to delete user data.");
    } finally {
      setIsDeletingData(false);
    }
  };

  useEffect(() => {
    if (isSignedIn) {
      loadData(false);
    }
  }, [isSignedIn]);

  const stats = recData?.pipeline_stats;

  return (
    <div className="container" style={{ paddingTop: "40px", paddingBottom: "100px" }}>
      {/* Signed Out View */}
      <SignedOut>
        <div style={{ textAlign: "center", maxWidth: "800px", margin: "40px auto" }}>
          <div style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            padding: "6px 16px",
            borderRadius: "9999px",
            background: "rgba(99, 102, 241, 0.1)",
            border: "1px solid rgba(99, 102, 241, 0.3)",
            fontSize: "0.85rem",
            color: "#a5b4fc",
            marginBottom: "24px",
          }}>
            <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#6366f1" }} />
            Phase 2: Live Viability Filter & Personalized Heuristic Matching
          </div>

          <h1 style={{
            fontSize: "3.2rem",
            fontWeight: 800,
            lineHeight: 1.15,
            letterSpacing: "-0.03em",
            marginBottom: "20px",
          }}>
            Find Open-Source Issues You Can{" "}
            <span style={{
              background: "var(--accent-gradient)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}>
              Actually Finish
            </span>
          </h1>

          <p style={{
            fontSize: "1.2rem",
            color: "var(--text-secondary)",
            marginBottom: "36px",
            lineHeight: 1.6,
          }}>
            MergeWise analyzes your real GitHub footprint (languages, manifests, recency),
            verifies live issue viability (unassigned, no competing PRs), and delivers 5 matched issues.
          </p>

          <SignInButton mode="modal">
            <button className="btn-primary" style={{ padding: "14px 32px", fontSize: "1.05rem" }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
              </svg>
              Sign In with GitHub to View Your Matches
            </button>
          </SignInButton>
        </div>
      </SignedOut>

      {/* Signed In View */}
      <SignedIn>
        <div>
          {/* Top Profile Summary Bar */}
          <div className="glass-panel" style={{ padding: "24px", marginBottom: "24px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px" }}>
                  <h1 style={{ fontSize: "1.7rem", fontWeight: 700 }}>
                    Welcome, {profileMeta?.github_username || user?.username || "Developer"}
                  </h1>
                  <span className="badge badge-success">GitHub Connected</span>
                </div>
                <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
                  Skill profile built from your GitHub footprint & repository manifests.
                </p>
              </div>

              <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                <button
                  onClick={() => setShowDeleteConfirm(true)}
                  className="btn-secondary"
                  style={{ fontSize: "0.85rem", padding: "8px 12px", color: "#f87171", borderColor: "rgba(248, 113, 113, 0.3)" }}
                  title="Purges all outcomes, memory, and personal documents from database"
                >
                  🗑 Delete my data
                </button>
                <button
                  onClick={() => setShowColdStartOverride(!showColdStartOverride)}
                  className="btn-secondary"
                  style={{ fontSize: "0.85rem", padding: "8px 14px" }}
                >
                  ⚙ Preferences
                </button>
                <button
                  onClick={() => loadData(true)}
                  className="btn-primary"
                  style={{ fontSize: "0.85rem", padding: "8px 16px" }}
                  disabled={loadingRecs || refreshCooldown > 0}
                >
                  {loadingRecs
                    ? "Scanning GitHub..."
                    : refreshCooldown > 0
                    ? `Refresh Cool-off (${refreshCooldown}s)`
                    : "↻ Refresh Issues"}
                </button>
              </div>
            </div>

            {/* Profile Statistics Pills */}
            {recData?.profile && (
              <div style={{
                marginTop: "20px",
                paddingTop: "20px",
                borderTop: "1px solid var(--border-color)",
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                gap: "16px",
              }}>
                <div>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", display: "block" }}>
                    Top Languages
                  </span>
                  <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginTop: "6px" }}>
                    {Object.entries(recData.profile.primary_languages).slice(0, 3).map(([lang, pct]) => (
                      <span key={lang} style={{ fontSize: "0.8rem", padding: "3px 8px", borderRadius: "4px", background: "rgba(99, 102, 241, 0.15)", color: "#c7d2fe" }}>
                        {lang}: {Math.round(pct * 100)}%
                      </span>
                    ))}
                    {Object.keys(recData.profile.primary_languages).length === 0 && (
                      <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>None detected</span>
                    )}
                  </div>
                </div>

                <div>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", display: "block" }}>
                    Manifest Frameworks
                  </span>
                  <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginTop: "6px" }}>
                    {recData.profile.frameworks.slice(0, 4).map((fw) => (
                      <span key={fw} style={{ fontSize: "0.8rem", padding: "3px 8px", borderRadius: "4px", background: "rgba(255, 255, 255, 0.06)", color: "var(--text-secondary)" }}>
                        {fw}
                      </span>
                    ))}
                    {recData.profile.frameworks.length === 0 && (
                      <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>No manifests indexed</span>
                    )}
                  </div>
                </div>

                <div>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", display: "block" }}>
                    Recent Activity
                  </span>
                  <div style={{ marginTop: "6px", fontSize: "0.85rem", color: "var(--text-primary)" }}>
                    {recData.profile.activity_last_1m} actions (30d) · {recData.profile.total_commits} commits
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Cold Start Questionnaire Modal (if account is cold start or user requested override) */}
          {(showColdStartOverride || (recData?.is_cold_start && !recData.recommendations.length)) && (
            <ColdStartModal onComplete={handleColdStartSubmit} isLoading={loadingRecs} />
          )}

          {/* Error Message */}
          {error && (
            <div style={{
              padding: "16px",
              borderRadius: "var(--radius-sm)",
              backgroundColor: "rgba(239, 68, 68, 0.15)",
              border: "1px solid rgba(239, 68, 68, 0.3)",
              color: "#fca5a5",
              marginBottom: "24px",
            }}>
              <strong>Error:</strong> {error}
            </div>
          )}

          {/* Rate Limit Notice Banner (Never blank page, show notice with reset time) */}
          {(stats?.rate_limit_notice || stats?.search_rate_limit?.is_limited) && (
            <div style={{
              padding: "16px 20px",
              borderRadius: "var(--radius-md)",
              backgroundColor: "rgba(245, 158, 11, 0.15)",
              border: "1px solid rgba(245, 158, 11, 0.4)",
              color: "#fde68a",
              marginBottom: "24px",
              display: "flex",
              alignItems: "flex-start",
              gap: "12px",
            }}>
              <span style={{ fontSize: "1.4rem", lineHeight: 1 }}>⚠️</span>
              <div>
                <strong style={{ color: "#fbbf24" }}>GitHub Rate Limit Reached:</strong>{" "}
                {stats?.rate_limit_notice || `Search quota exhausted. Resets at ${stats?.search_rate_limit?.reset_time || "shortly"}.`}
                <div style={{ fontSize: "0.85rem", color: "#fef3c7", marginTop: "4px" }}>
                  Your skill profile and last verified recommendations are preserved. Real-time discovery will resume automatically once GitHub resets the quota.
                </div>
              </div>
            </div>
          )}

          {/* PIPELINE TELEMETRY & VIABILITY STATS DRAWER (Visible ALWAYS, even when empty) */}
          {stats && (
            <div className="glass-panel" style={{ padding: "18px 24px", marginBottom: "28px", borderLeft: "4px solid var(--accent-secondary)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
                <div>
                  <span style={{ fontWeight: 700, fontSize: "0.95rem" }}>Viability Pipeline Telemetry:</span>{" "}
                  <span style={{ color: "var(--text-secondary)" }}>
                    Executed <strong>{stats.queries_run.length}</strong> targeted queries · Fetched <strong>{stats.candidates_fetched}</strong> candidates · Found{" "}
                    <strong style={{ color: stats.passed_viability > 0 ? "var(--success)" : "var(--warning)" }}>
                      {stats.passed_viability} truly viable
                    </strong>
                  </span>
                </div>

                {stats.relaxation_used && (
                  <span className="badge badge-warning" style={{ fontSize: "0.75rem" }}>
                    Relaxation: {stats.relaxation_used}
                  </span>
                )}
              </div>

              {/* Rejection breakdown */}
              <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", marginTop: "12px", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                <span style={{ fontWeight: 600, color: "var(--text-muted)" }}>Filtered:</span>
                {stats.rejected_by_reason["ALREADY_ASSIGNED"] > 0 && (
                  <span style={{ background: "rgba(255, 255, 255, 0.05)", padding: "2px 8px", borderRadius: "4px" }}>
                    {stats.rejected_by_reason["ALREADY_ASSIGNED"]} assigned
                  </span>
                )}
                {stats.rejected_by_reason["COMPETING_OPEN_PR"] > 0 && (
                  <span style={{ background: "rgba(255, 255, 255, 0.05)", padding: "2px 8px", borderRadius: "4px" }}>
                    {stats.rejected_by_reason["COMPETING_OPEN_PR"]} competing PRs
                  </span>
                )}
                {stats.rejected_by_reason["CLAIMED_IN_COMMENTS"] > 0 && (
                  <span style={{ background: "rgba(255, 255, 255, 0.05)", padding: "2px 8px", borderRadius: "4px" }}>
                    {stats.rejected_by_reason["CLAIMED_IN_COMMENTS"]} claimed in comments
                  </span>
                )}
                {stats.rejected_by_reason["ISSUE_CLOSED"] > 0 && (
                  <span style={{ background: "rgba(255, 255, 255, 0.05)", padding: "2px 8px", borderRadius: "4px" }}>
                    {stats.rejected_by_reason["ISSUE_CLOSED"]} closed
                  </span>
                )}
                {stats.rejected_by_reason["NOT_ELIGIBLE"] > 0 && (
                  <span style={{ background: "rgba(255, 255, 255, 0.05)", padding: "2px 8px", borderRadius: "4px" }}>
                    {stats.rejected_by_reason["NOT_ELIGIBLE"]} pull requests
                  </span>
                )}
                {stats.api_errors > 0 && (
                  <span style={{ color: "var(--warning)" }}>
                    ({stats.api_errors} transient API errors handled safely)
                  </span>
                )}

                <button
                  onClick={() => setShowQueriesDrawer(!showQueriesDrawer)}
                  style={{
                    background: "none",
                    border: "none",
                    color: "#a5b4fc",
                    cursor: "pointer",
                    fontSize: "0.8rem",
                    textDecoration: "underline",
                    marginLeft: "auto",
                  }}
                >
                  {showQueriesDrawer ? "Hide Queries" : `Show Queries (${stats.queries_run.length})`}
                </button>
              </div>

              {/* Separate Search and Core Rate Limits Quota Breakdown */}
              <div style={{
                marginTop: "14px",
                paddingTop: "12px",
                borderTop: "1px solid rgba(255, 255, 255, 0.08)",
                display: "flex",
                flexWrap: "wrap",
                alignItems: "center",
                gap: "16px",
                fontSize: "0.82rem",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <span style={{ color: "var(--text-muted)" }}>Search API Limit:</span>
                  <span style={{
                    fontWeight: 600,
                    color: stats.search_rate_limit?.is_limited ? "#f87171" : (stats.search_rate_limit && stats.search_rate_limit.remaining < 5) ? "#fbbf24" : "#34d399",
                  }}>
                    {stats.search_rate_limit?.remaining ?? "?"}/{stats.search_rate_limit?.limit ?? 30} req/min
                  </span>
                  {stats.search_rate_limit?.is_limited && (
                    <span style={{ color: "#f87171", fontWeight: 600 }}>
                      (LIMITED - resets at {stats.search_rate_limit.reset_time})
                    </span>
                  )}
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <span style={{ color: "var(--text-muted)" }}>Core API Limit:</span>
                  <span style={{
                    fontWeight: 600,
                    color: stats.core_rate_limit?.is_limited ? "#f87171" : "#34d399",
                  }}>
                    {stats.core_rate_limit?.remaining ?? "?"}/{stats.core_rate_limit?.limit ?? 5000} req/hr
                  </span>
                  {stats.core_rate_limit?.is_limited && (
                    <span style={{ color: "#f87171", fontWeight: 600 }}>
                      (LIMITED - resets at {stats.core_rate_limit.reset_time})
                    </span>
                  )}
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "6px", marginLeft: "auto", color: "var(--text-muted)" }}>
                  <span>Search Calls:</span>
                  <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>{stats.calls_made || stats.queries_run.length} (max 8)</span>
                </div>
              </div>

              {/* Collapsible raw queries list */}
              {showQueriesDrawer && (
                <div style={{ marginTop: "12px", paddingTop: "12px", borderTop: "1px dashed var(--border-color)", fontSize: "0.75rem", fontFamily: "monospace", color: "var(--text-muted)" }}>
                  {stats.queries_run.map((q, i) => (
                    <div key={i} style={{ marginBottom: "4px" }}>
                      → {q}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Delete Data Confirmation Modal */}
          {showDeleteConfirm && (
            <div style={{
              position: "fixed",
              inset: 0,
              backgroundColor: "rgba(0, 0, 0, 0.75)",
              backdropFilter: "blur(4px)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 9999,
              padding: "20px",
            }}>
              <div className="glass-panel" style={{
                maxWidth: "480px",
                width: "100%",
                padding: "24px",
                borderRadius: "var(--radius-md)",
                border: "1px solid rgba(248, 113, 113, 0.4)",
              }}>
                <h3 style={{ fontSize: "1.3rem", fontWeight: 700, color: "#f87171", marginBottom: "12px" }}>
                  Delete All Your Data?
                </h3>
                <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", lineHeight: 1.5, marginBottom: "20px" }}>
                  This action is permanent and cannot be undone. It removes your skill profile, all issue outcomes (skipped, attempted, PRs, etc.), and recommendations telemetry from our database.
                </p>
                <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
                  <button
                    onClick={() => setShowDeleteConfirm(false)}
                    className="btn-secondary"
                    disabled={isDeletingData}
                    style={{ padding: "8px 16px", fontSize: "0.85rem" }}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleDeleteMyData}
                    style={{
                      padding: "8px 18px",
                      fontSize: "0.85rem",
                      borderRadius: "var(--radius-sm)",
                      backgroundColor: "#ef4444",
                      color: "#fff",
                      border: "none",
                      fontWeight: 600,
                      cursor: isDeletingData ? "not-allowed" : "pointer",
                    }}
                    disabled={isDeletingData}
                  >
                    {isDeletingData ? "Deleting..." : "Yes, Delete Everything"}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Delete Success Alert */}
          {deleteSuccessMsg && (
            <div style={{
              padding: "16px",
              borderRadius: "var(--radius-sm)",
              backgroundColor: "rgba(16, 185, 129, 0.15)",
              border: "1px solid rgba(16, 185, 129, 0.3)",
              color: "#6ee7b7",
              marginBottom: "24px",
            }}>
              ✓ {deleteSuccessMsg}
            </div>
          )}

          {/* Recommendations Header */}
          <div style={{ marginBottom: "20px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <h2 style={{ fontSize: "1.4rem", fontWeight: 700 }}>
                  Top 5 Recommended Issues for You
                </h2>
                <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                  Ranked using PFIRec-aligned features & verified unassigned with no competing PRs.
                </p>
              </div>
            </div>

            {/* Why these results note (Phase 4 requirement 4) */}
            {recData?.why_these_results && (
              <div style={{
                marginTop: "12px",
                padding: "10px 14px",
                borderRadius: "var(--radius-sm)",
                backgroundColor: "rgba(99, 102, 241, 0.12)",
                border: "1px solid rgba(99, 102, 241, 0.25)",
                fontSize: "0.82rem",
                color: "#c7d2fe",
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}>
                <span style={{ fontSize: "1rem" }}>💡</span>
                <span>
                  <strong>Why these results:</strong> {recData.why_these_results}
                </span>
              </div>
            )}
          </div>

          {/* Loading Indicator */}
          {loadingRecs && !recData && (
            <div className="glass-panel" style={{ padding: "60px", textAlign: "center", color: "var(--text-secondary)" }}>
              <div style={{ fontSize: "2rem", marginBottom: "12px" }}>🔍</div>
              <p style={{ fontSize: "1.1rem", fontWeight: 600, color: "var(--text-primary)" }}>
                Executing targeted search per language and verifying live viability...
              </p>
              <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginTop: "6px" }}>
                Checking assignees, competing PRs, and recent claim comments.
              </p>
            </div>
          )}

          {/* Recommendations List */}
          {recData?.recommendations && recData.recommendations.length > 0 && (
            <div>
              {recData.recommendations.map((item, idx) => (
                <IssueCard key={item.issue.issue_url || idx} candidate={item} index={idx} />
              ))}
            </div>
          )}

          {/* Empty State */}
          {recData && !loadingRecs && recData.recommendations.length === 0 && !recData.is_cold_start && (
            <div className="glass-panel" style={{ padding: "40px", textAlign: "center" }}>
              <div style={{ fontSize: "2.2rem", marginBottom: "12px" }}>🔎</div>
              <p style={{ fontSize: "1.2rem", fontWeight: 700, marginBottom: "8px" }}>
                No viable issues currently found for this exact combination.
              </p>
              <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", maxWidth: "600px", margin: "0 auto 24px auto" }}>
                The pipeline searched GitHub for your top languages, but all fetched candidates were either already claimed or had competing PRs. Click below to adjust languages or force a wider scan.
              </p>
              <div style={{ display: "flex", justifyContent: "center", gap: "12px" }}>
                <button onClick={() => setShowColdStartOverride(true)} className="btn-secondary">
                  ⚙ Adjust Languages & Frameworks
                </button>
                <button
                  onClick={() => loadData(true)}
                  className="btn-primary"
                  disabled={loadingRecs || refreshCooldown > 0}
                >
                  {refreshCooldown > 0 ? `Scan Cooldown (${refreshCooldown}s)` : "↻ Force Scan GitHub"}
                </button>
              </div>
            </div>
          )}
        </div>
      </SignedIn>
    </div>
  );
}
