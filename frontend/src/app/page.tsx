"use client";

import React, { useEffect, useState, useMemo, useRef } from "react";
import { useAuth, useUser } from "@clerk/nextjs";
import {
  fetchUserProfile,
  fetchRecommendations,
  submitColdStart,
  deleteMyData,
  fetchContributions,
  fetchFunnel,
} from "@/lib/api";
import {
  UserProfileResponse,
  RecommendationsResponse,
  ColdStartQuestionnaire,
  ContributionsResponse,
  FunnelMetricsResponse,
  ScoredIssueCandidate,
} from "@/lib/types";
import IssueCard from "@/components/IssueCard";
import ColdStartModal from "@/components/ColdStartModal";
import ContributionsTab from "@/components/ContributionsTab";
import ProgressTab from "@/components/ProgressTab";
import LandingHero from "@/components/LandingHero";
import { useSearch, SortOption } from "@/lib/searchContext";
import { isStoppedTool } from "@/lib/stoplist";
import {
  SyncIcon,
  AlertIcon,
  IssueOpenedIcon,
  GearIcon,
  CheckIcon,
  TrashIcon,
  GitPullRequestIcon,
  BookIcon,
  PulseIcon,
  RepoIcon,
  SearchIcon,
  TriangleDownIcon,
} from "@/components/Octicons";

const LANG_COLORS: Record<string, string> = {
  TypeScript: "#3178c6",
  JavaScript: "#f1e05a",
  Python: "#3572A5",
  Go: "#00ADD8",
  Rust: "#dea584",
  Java: "#b07219",
  "C++": "#f34b7d",
  C: "#555555",
  Ruby: "#701516",
  PHP: "#4F5D95",
  HTML: "#e34c26",
  CSS: "#563d7c",
  Shell: "#89e051",
};

export default function HomePage() {
  const { getToken, isSignedIn, isLoaded } = useAuth();
  const { user } = useUser();
  const {
    searchQuery,
    setSearchQuery,
    sortBy,
    setSortBy,
    languageFilter,
    setLanguageFilter,
    isPipelineDetailsOpen,
    setIsPipelineDetailsOpen,
  } = useSearch();

  const [activeTab, setActiveTab] = useState<"recommended" | "contributions" | "progress">("recommended");
  const [profileMeta, setProfileMeta] = useState<UserProfileResponse | null>(null);
  const [recData, setRecData] = useState<RecommendationsResponse | null>(null);
  const [contribData, setContribData] = useState<ContributionsResponse | null>(null);
  const [funnelData, setFunnelData] = useState<FunnelMetricsResponse | null>(null);

  const [loadingRecs, setLoadingRecs] = useState<boolean>(false);
  const [loadingContribs, setLoadingContribs] = useState<boolean>(false);
  const [loadingFunnel, setLoadingFunnel] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [showColdStartOverride, setShowColdStartOverride] = useState<boolean>(false);
  const [refreshCooldown, setRefreshCooldown] = useState<number>(0);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<boolean>(false);
  const [isDeletingData, setIsDeletingData] = useState<boolean>(false);
  const [deleteSuccessMsg, setDeleteSuccessMsg] = useState<string | null>(null);

  const [isSortMenuOpen, setIsSortMenuOpen] = useState(false);
  const [isLangMenuOpen, setIsLangMenuOpen] = useState(false);

  const sortMenuRef = useRef<HTMLDivElement>(null);
  const langMenuRef = useRef<HTMLDivElement>(null);

  // Close dropdowns on outside click
  useEffect(() => {
    const handleOutside = (e: MouseEvent) => {
      if (sortMenuRef.current && !sortMenuRef.current.contains(e.target as Node)) {
        setIsSortMenuOpen(false);
      }
      if (langMenuRef.current && !langMenuRef.current.contains(e.target as Node)) {
        setIsLangMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, []);

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

      const [userMeta, recs] = await Promise.all([
        fetchUserProfile(token).catch((e) => {
          console.warn("Could not load user profile:", e);
          return null;
        }),
        fetchRecommendations(token, forceRefresh),
      ]);

      if (userMeta) setProfileMeta(userMeta);
      setRecData(recs);

      loadContributions(token, forceRefresh);
      loadFunnel(token);
    } catch (err: any) {
      console.error("Failed to load recommendations:", err);
      setError(err.message || "Failed to communicate with recommendation service.");
    } finally {
      setLoadingRecs(false);
    }
  };

  const loadContributions = async (token?: string, forceRefresh: boolean = false) => {
    setLoadingContribs(true);
    try {
      const authToken = token || (await getToken());
      if (!authToken) return;
      const resp = await fetchContributions(authToken, forceRefresh);
      setContribData(resp);
    } catch (err: any) {
      console.warn("Failed to load contributions:", err);
    } finally {
      setLoadingContribs(false);
    }
  };

  const loadFunnel = async (token?: string) => {
    setLoadingFunnel(true);
    try {
      const authToken = token || (await getToken());
      if (!authToken) return;
      const resp = await fetchFunnel(authToken);
      setFunnelData(resp);
    } catch (err: any) {
      console.warn("Failed to load funnel:", err);
    } finally {
      setLoadingFunnel(false);
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
      const recs = await fetchRecommendations(token, true);
      setRecData(recs);
    } catch (err: any) {
      setError(err.message || "Cold start failed.");
    } finally {
      setLoadingRecs(false);
    }
  };

  const handleDeleteMyData = async () => {
    setIsDeletingData(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Missing session token.");
      await deleteMyData(token);
      setRecData(null);
      setProfileMeta(null);
      setContribData(null);
      setFunnelData(null);
      setShowDeleteConfirm(false);
      setDeleteSuccessMsg("All profile data and recommendation history have been permanently purged.");
      setTimeout(() => setDeleteSuccessMsg(null), 6000);
    } catch (err: any) {
      setError(err.message || "Could not delete data.");
    } finally {
      setIsDeletingData(false);
    }
  };

  useEffect(() => {
    if (isSignedIn) {
      loadData(false);
    }
  }, [isSignedIn]);

  // Derive languages and frameworks
  const languages: [string, number][] = useMemo(() => {
    const raw: Record<string, number> = recData?.profile?.primary_languages || {};
    return Object.entries(raw).sort((a, b) => b[1] - a[1]);
  }, [recData]);

  const validFrameworks = useMemo(() => {
    const raw: string[] = recData?.profile?.frameworks || [];
    return raw.filter((fw) => !isStoppedTool(fw));
  }, [recData]);

  const stats = recData?.pipeline_stats;
  const mergedCount = contribData?.summary?.merged_count ?? recData?.profile?.total_prs ?? 0;
  const repoCount = contribData?.summary?.repo_count ?? recData?.profile?.total_repos_contributed ?? 0;

  // Client-side search, sort & language filtering of recommended issues
  const filteredRecommendations = useMemo(() => {
    let list: ScoredIssueCandidate[] = recData?.recommendations ? [...recData.recommendations] : [];

    // 1. Language Filter
    if (languageFilter && languageFilter !== "all") {
      list = list.filter(
        (c) => (c.issue.primary_language || "").toLowerCase() === languageFilter.toLowerCase()
      );
    }

    // 2. Search Query Filter (matches title, repo name, labels, language)
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      list = list.filter((c) => {
        const titleMatch = (c.issue.title || "").toLowerCase().includes(q);
        const repoMatch = (c.issue.repo_full_name || "").toLowerCase().includes(q);
        const langMatch = (c.issue.primary_language || "").toLowerCase().includes(q);
        const labelMatch = (c.issue.labels || []).some((l) => l.toLowerCase().includes(q));
        return titleMatch || repoMatch || langMatch || labelMatch;
      });
    }

    // 3. Sorting
    if (sortBy === "match") {
      list.sort((a, b) => b.score - a.score);
    } else if (sortBy === "newest") {
      list.sort((a, b) => (b.issue.created_at_epoch || 0) - (a.issue.created_at_epoch || 0));
    } else if (sortBy === "stars") {
      list.sort((a, b) => (b.issue.stars || 0) - (a.issue.stars || 0));
    }

    return list;
  }, [recData?.recommendations, searchQuery, languageFilter, sortBy]);

  // Loading state: match dark background (no flicker / no landing flash)
  if (!isLoaded) {
    return <div style={{ minHeight: "100vh", backgroundColor: "#0E1116" }} />;
  }

  // Signed out visitors: show Landing Hero
  if (!isSignedIn) {
    return <LandingHero />;
  }

  const sortLabel =
    sortBy === "match" ? "Match" : sortBy === "newest" ? "Newest" : "Stars";
  const langLabel = languageFilter === "all" ? "All languages" : languageFilter;

  return (
    <div style={{ backgroundColor: "var(--color-canvas-default)", minHeight: "100vh" }}>
      {/* 2. Underline Nav under Header (GitHub Repo Style) */}
      <nav className="RepoNav" aria-label="Repository navigation">
        <div className="RepoNav-container" role="tablist">
          <button
            role="tab"
            id="tab-recommended"
            aria-selected={activeTab === "recommended"}
            className={`RepoNav-item ${activeTab === "recommended" ? "selected" : ""}`}
            onClick={() => setActiveTab("recommended")}
          >
            <IssueOpenedIcon size={16} />
            <span>Recommended</span>
            {recData?.recommendations?.length ? (
              <span className="Counter">{recData.recommendations.length}</span>
            ) : null}
          </button>

          <button
            role="tab"
            id="tab-contributions"
            aria-selected={activeTab === "contributions"}
            className={`RepoNav-item ${activeTab === "contributions" ? "selected" : ""}`}
            onClick={() => setActiveTab("contributions")}
          >
            <GitPullRequestIcon size={16} />
            <span>My contributions</span>
            {contribData?.summary?.merged_count !== undefined ? (
              <span className="Counter">{contribData.summary.merged_count}</span>
            ) : null}
          </button>

          <button
            role="tab"
            id="tab-progress"
            aria-selected={activeTab === "progress"}
            className={`RepoNav-item ${activeTab === "progress" ? "selected" : ""}`}
            onClick={() => setActiveTab("progress")}
          >
            <CheckIcon size={16} />
            <span>Progress</span>
          </button>
        </div>
      </nav>

      {/* Main Container */}
      <div className="RepoLayout">
        {/* Flash Banners */}
        {deleteSuccessMsg && (
          <div className="Flash Flash--success" style={{ marginBottom: "16px" }}>
            <CheckIcon size={16} />
            <span>{deleteSuccessMsg}</span>
          </div>
        )}

        {error && (
          <div className="Flash Flash--error" style={{ marginBottom: "16px" }}>
            <AlertIcon size={16} />
            <span>{error}</span>
          </div>
        )}

        {/* GitHub Rate Limit Warning Banner */}
        {(stats?.rate_limit_notice || stats?.search_rate_limit?.is_limited) && (
          <div className="Flash Flash--warning" style={{ marginBottom: "16px" }}>
            <AlertIcon size={16} />
            <div>
              <strong>GitHub Rate Limit Reached:</strong>{" "}
              {stats?.rate_limit_notice ||
                `Search quota exhausted. Resets at ${stats?.search_rate_limit?.reset_time || "shortly"}.`}
              <div style={{ fontSize: "12px", color: "var(--color-fg-muted)", marginTop: "4px" }}>
                Your footprint profile and cached recommendations are preserved.
              </div>
            </div>
          </div>
        )}

        {/* Cold Start / Preferences Modal */}
        {(showColdStartOverride || (recData?.is_cold_start && !recData.recommendations.length)) && (
          <ColdStartModal onComplete={handleColdStartSubmit} isLoading={loadingRecs} />
        )}

        {/* 3. Title Row: Owner avatar, MergeWise in large weight, OSS Match pill, action buttons */}
        <div className="RepoTitleRow">
          <div className="RepoTitle-left">
            {user?.imageUrl ? (
              <img
                src={user.imageUrl}
                alt="MergeWise"
                width={32}
                height={32}
                style={{ width: "32px", height: "32px", borderRadius: "50%", objectFit: "cover" }}
                className="RepoTitle-avatar"
              />
            ) : (
              <img
                src="/mergewise-logo.png"
                alt="MergeWise"
                width={32}
                height={32}
                style={{ width: "32px", height: "32px", borderRadius: "50%", objectFit: "cover" }}
                className="RepoTitle-avatar"
              />
            )}
            <h1 className="RepoTitle-name" style={{ margin: 0, padding: 0 }}>
              MergeWise
            </h1>
            <span className="RepoTitle-badge">OSS Match</span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <button
              onClick={() => setShowColdStartOverride(!showColdStartOverride)}
              className="btn btn-sm"
              title="Adjust skill preferences and target frameworks"
            >
              <GearIcon size={14} />
              <span>Preferences</span>
            </button>

            <button
              onClick={() => loadData(true)}
              className="btn btn-sm btn-primary"
              disabled={loadingRecs || refreshCooldown > 0}
              title="Scan GitHub for fresh viable issues"
            >
              <SyncIcon size={14} />
              <span>
                {loadingRecs
                  ? "Scanning..."
                  : refreshCooldown > 0
                  ? `Cooldown (${refreshCooldown}s)`
                  : "Refresh"}
              </span>
            </button>
          </div>
        </div>

        {/* 4. Toolbar Row (like branch/file row): Sort dropdown, Language filter dropdown, Go to issue... */}
        {activeTab === "recommended" && (
          <div className="RepoToolbar">
            <div className="RepoToolbar-left">
              {/* Sort Dropdown */}
              <div className="RepoDropdown-wrapper" ref={sortMenuRef}>
                <button
                  className="btn btn-sm"
                  onClick={() => setIsSortMenuOpen(!isSortMenuOpen)}
                  aria-haspopup="true"
                  aria-expanded={isSortMenuOpen}
                >
                  <span>Sort: {sortLabel}</span>
                  <TriangleDownIcon size={12} />
                </button>
                {isSortMenuOpen && (
                  <div className="RepoDropdown-menu" role="menu">
                    <button
                      className={`RepoDropdown-item ${sortBy === "match" ? "selected" : ""}`}
                      onClick={() => {
                        setSortBy("match");
                        setIsSortMenuOpen(false);
                      }}
                    >
                      <span>Match (Best fit)</span>
                      {sortBy === "match" && <CheckIcon size={14} />}
                    </button>
                    <button
                      className={`RepoDropdown-item ${sortBy === "newest" ? "selected" : ""}`}
                      onClick={() => {
                        setSortBy("newest");
                        setIsSortMenuOpen(false);
                      }}
                    >
                      <span>Newest (Created)</span>
                      {sortBy === "newest" && <CheckIcon size={14} />}
                    </button>
                    <button
                      className={`RepoDropdown-item ${sortBy === "stars" ? "selected" : ""}`}
                      onClick={() => {
                        setSortBy("stars");
                        setIsSortMenuOpen(false);
                      }}
                    >
                      <span>Stars (Most stars)</span>
                      {sortBy === "stars" && <CheckIcon size={14} />}
                    </button>
                  </div>
                )}
              </div>

              {/* Language Filter Dropdown */}
              <div className="RepoDropdown-wrapper" ref={langMenuRef}>
                <button
                  className="btn btn-sm"
                  onClick={() => setIsLangMenuOpen(!isLangMenuOpen)}
                  aria-haspopup="true"
                  aria-expanded={isLangMenuOpen}
                >
                  <span>Language: {langLabel}</span>
                  <TriangleDownIcon size={12} />
                </button>
                {isLangMenuOpen && (
                  <div className="RepoDropdown-menu" role="menu">
                    <button
                      className={`RepoDropdown-item ${languageFilter === "all" ? "selected" : ""}`}
                      onClick={() => {
                        setLanguageFilter("all");
                        setIsLangMenuOpen(false);
                      }}
                    >
                      <span>All languages</span>
                      {languageFilter === "all" && <CheckIcon size={14} />}
                    </button>
                    {languages.map(([lang]) => (
                      <button
                        key={lang}
                        className={`RepoDropdown-item ${languageFilter.toLowerCase() === lang.toLowerCase() ? "selected" : ""}`}
                        onClick={() => {
                          setLanguageFilter(lang);
                          setIsLangMenuOpen(false);
                        }}
                      >
                        <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                          <span
                            style={{
                              width: "8px",
                              height: "8px",
                              borderRadius: "50%",
                              backgroundColor: LANG_COLORS[lang] || "var(--color-accent-fg)",
                            }}
                          />
                          {lang}
                        </span>
                        {languageFilter.toLowerCase() === lang.toLowerCase() && <CheckIcon size={14} />}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Go to issue... search field */}
              <div className="RepoToolbar-search">
                <SearchIcon size={13} color="var(--color-fg-muted)" />
                <input
                  type="text"
                  placeholder="Go to issue..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  aria-label="Filter issues by title or repository"
                />
              </div>
            </div>
          </div>
        )}

        {/* 5. Main 2-column layout: Main Column + 296px Right Sidebar */}
        <div className="RepoGrid">
          {/* Main Column */}
          <main className="RepoMain">
            {/* TAB 1: RECOMMENDED ISSUES */}
            {activeTab === "recommended" && (
              <div>
                {/* Issue Table Box (File list style) */}
                <div className="RepoTable">
                  {/* Box Header Bar (Like latest commit bar) */}
                  <div className="RepoTable-header">
                    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                      {user?.imageUrl ? (
                        <img
                          src={user.imageUrl}
                          alt="user"
                          style={{
                            width: "20px",
                            height: "20px",
                            borderRadius: "50%",
                            border: "1px solid var(--color-border-default)",
                          }}
                        />
                      ) : (
                        <div
                          style={{
                            width: "20px",
                            height: "20px",
                            borderRadius: "50%",
                            background: "var(--color-accent-emphasis)",
                            color: "#fff",
                            fontSize: "10px",
                            fontWeight: 700,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                          }}
                        >
                          MW
                        </div>
                      )}
                      <span style={{ fontWeight: 600, color: "var(--color-fg-default)" }}>
                        Scanned {stats?.candidates_fetched ?? 5} candidates,{" "}
                        <span style={{ color: "var(--color-success-fg)" }}>
                          {stats?.passed_viability ?? (recData?.recommendations?.length || 5)} passed viability
                        </span>
                      </span>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: "12px", fontSize: "12px" }}>
                      <span>updated 2 minutes ago</span>
                      <button
                        onClick={() => setIsPipelineDetailsOpen((prev) => !prev)}
                        style={{
                          background: "transparent",
                          border: "none",
                          color: "var(--color-accent-fg)",
                          cursor: "pointer",
                          fontSize: "12px",
                          fontWeight: 500,
                          padding: "2px 4px",
                          textDecoration: "underline",
                        }}
                      >
                        {isPipelineDetailsOpen ? "Hide pipeline details" : "Pipeline details"}
                      </button>
                    </div>
                  </div>

                  {/* Inline Expanded Telemetry Table */}
                  {isPipelineDetailsOpen && stats && (
                    <div
                      style={{
                        padding: "16px",
                        backgroundColor: "var(--color-canvas-subtle)",
                        borderBottom: "1px solid var(--color-border-default)",
                      }}
                    >
                      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
                        <tbody>
                          <tr style={{ borderBottom: "1px solid var(--color-border-default)" }}>
                            <td style={{ padding: "6px 12px", color: "var(--color-fg-muted)" }}>Targeted Queries Executed</td>
                            <td style={{ padding: "6px 12px", fontWeight: 600, color: "var(--color-fg-default)" }}>
                              {stats.queries_run.length}
                            </td>
                          </tr>
                          <tr style={{ borderBottom: "1px solid var(--color-border-default)" }}>
                            <td style={{ padding: "6px 12px", color: "var(--color-fg-muted)" }}>Candidates Fetched</td>
                            <td style={{ padding: "6px 12px", fontWeight: 600, color: "var(--color-fg-default)" }}>
                              {stats.candidates_fetched}
                            </td>
                          </tr>
                          <tr style={{ borderBottom: "1px solid var(--color-border-default)" }}>
                            <td style={{ padding: "6px 12px", color: "var(--color-fg-muted)" }}>Passed Viability</td>
                            <td style={{ padding: "6px 12px", fontWeight: 600, color: "var(--color-success-fg)" }}>
                              {stats.passed_viability}
                            </td>
                          </tr>
                          <tr style={{ borderBottom: "1px solid var(--color-border-default)" }}>
                            <td style={{ padding: "6px 12px", color: "var(--color-fg-muted)" }}>Search API Limit</td>
                            <td style={{ padding: "6px 12px", fontWeight: 600, color: "var(--color-fg-default)" }}>
                              {stats.search_rate_limit?.remaining ?? "?"}/{stats.search_rate_limit?.limit ?? 30} req/min
                            </td>
                          </tr>
                          <tr style={{ borderBottom: "1px solid var(--color-border-default)" }}>
                            <td style={{ padding: "6px 12px", color: "var(--color-fg-muted)" }}>Core API Limit</td>
                            <td style={{ padding: "6px 12px", fontWeight: 600, color: "var(--color-fg-default)" }}>
                              {stats.core_rate_limit?.remaining ?? "?"}/{stats.core_rate_limit?.limit ?? 5000} req/hr
                            </td>
                          </tr>
                          <tr>
                            <td style={{ padding: "6px 12px", color: "var(--color-fg-muted)" }}>Filter Breakdown</td>
                            <td style={{ padding: "6px 12px", color: "var(--color-fg-default)" }}>
                              {stats.rejected_by_reason["ALREADY_ASSIGNED"] || 0} assigned ·{" "}
                              {stats.rejected_by_reason["COMPETING_OPEN_PR"] || 0} competing PRs ·{" "}
                              {stats.rejected_by_reason["CLAIMED_IN_COMMENTS"] || 0} claimed in comments
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  )}

                  {/* Skeleton Rows while loading */}
                  {loadingRecs && !recData && (
                    <div>
                      {[0, 1, 2, 3, 4].map((i) => (
                        <div key={i} className="RepoTable-row" style={{ alignItems: "center" }}>
                          <div
                            className="SkeletonBar"
                            style={{ width: "16px", height: "16px", borderRadius: "50%", flexShrink: 0 }}
                          />
                          <div style={{ flex: 1 }}>
                            <div className="SkeletonBar" style={{ width: "55%", height: "16px", marginBottom: "6px" }} />
                            <div className="SkeletonBar" style={{ width: "30%", height: "12px" }} />
                          </div>
                          <div className="SkeletonBar" style={{ width: "100px", height: "28px", flexShrink: 0 }} />
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Populated Issue Rows */}
                  {filteredRecommendations.length > 0 && (
                    <div>
                      {filteredRecommendations.map((item, idx) => (
                        <IssueCard key={item.issue.issue_url || idx} candidate={item} index={idx} />
                      ))}
                    </div>
                  )}

                  {/* Empty State */}
                  {!loadingRecs && filteredRecommendations.length === 0 && (
                    <div style={{ textAlign: "center", padding: "48px 16px" }}>
                      <div style={{ color: "var(--color-fg-muted)", marginBottom: "12px" }}>
                        <IssueOpenedIcon size={32} />
                      </div>
                      <div style={{ fontSize: "16px", fontWeight: 600, color: "var(--color-fg-default)", marginBottom: "6px" }}>
                        {searchQuery || languageFilter !== "all"
                          ? "No issues match your current filters"
                          : "No viable issues currently found"}
                      </div>
                      <p style={{ fontSize: "13px", color: "var(--color-fg-muted)", maxWidth: "520px", margin: "0 auto 16px auto" }}>
                        {searchQuery || languageFilter !== "all"
                          ? "Try clearing the search query or changing the language filter to see more issues."
                          : "We scanned GitHub for your top languages, but all fetched candidates were either already claimed or had competing PRs."}
                      </p>
                      <div style={{ display: "flex", justifyContent: "center", gap: "8px" }}>
                        {searchQuery || languageFilter !== "all" ? (
                          <button
                            onClick={() => {
                              setSearchQuery("");
                              setLanguageFilter("all");
                            }}
                            className="btn btn-sm"
                          >
                            Clear filters
                          </button>
                        ) : (
                          <>
                            <button onClick={() => setShowColdStartOverride(true)} className="btn btn-sm">
                              Adjust Preferences
                            </button>
                            <button onClick={() => loadData(true)} className="btn btn-sm btn-primary">
                              Force Scan GitHub
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  )}
                </div>

                {/* 7. "Why these results" README-Style Box */}
                {recData?.why_these_results && (
                  <div className="ReadmeBox">
                    <div className="ReadmeBox-header">
                      <BookIcon size={16} color="var(--color-fg-muted)" />
                      <span>README.md - Why these results</span>
                    </div>
                    <div className="ReadmeBox-body">
                      <div style={{ marginBottom: "12px", fontWeight: 600, color: "var(--color-fg-default)" }}>
                        Active Personalization Memory
                      </div>
                      <p style={{ margin: 0, lineHeight: 1.6, color: "var(--color-fg-muted)", fontSize: "13px" }}>
                        {recData.why_these_results}
                      </p>
                    </div>
                  </div>
                )}

                {/* 10. Danger Zone Box */}
                <div className="DangerBox" id="danger-zone">
                  <div className="DangerBox-header">
                    <span>Danger Zone</span>
                  </div>
                  <div className="DangerBox-body">
                    <div>
                      <div style={{ fontWeight: 600, color: "var(--color-fg-default)", fontSize: "14px" }}>
                        Delete my data
                      </div>
                      <div style={{ fontSize: "12px", color: "var(--color-fg-muted)", marginTop: "2px" }}>
                        Permanently purges your skill footprint, outcome progression, and recommendation cache.
                      </div>
                    </div>

                    {!showDeleteConfirm ? (
                      <button
                        onClick={() => setShowDeleteConfirm(true)}
                        className="btn btn-danger btn-sm"
                      >
                        <TrashIcon size={14} />
                        <span>Delete my data</span>
                      </button>
                    ) : (
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <button
                          onClick={handleDeleteMyData}
                          disabled={isDeletingData}
                          className="btn btn-danger btn-sm"
                        >
                          {isDeletingData ? "Purging data..." : "Confirm Delete"}
                        </button>
                        <button
                          onClick={() => setShowDeleteConfirm(false)}
                          disabled={isDeletingData}
                          className="btn btn-sm"
                        >
                          Cancel
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* TAB 2: MY CONTRIBUTIONS */}
            {activeTab === "contributions" && (
              <ContributionsTab
                data={contribData}
                loading={loadingContribs}
                onRefresh={() => loadContributions(undefined, true)}
                onSwitchToRecommended={() => setActiveTab("recommended")}
              />
            )}

            {/* TAB 3: PROGRESS FUNNEL & WHY THESE RESULTS */}
            {activeTab === "progress" && (
              <ProgressTab
                funnel={funnelData}
                whyTheseResults={recData?.why_these_results}
                loading={loadingFunnel}
                onRefreshFunnel={() => loadFunnel()}
              />
            )}
          </main>

          {/* 8. Right Sidebar "About" (modeled after the screenshot) */}
          <aside className="RepoSidebar">
            <div className="RepoSidebar-heading">
              <span>About</span>
              <button
                onClick={() => setShowColdStartOverride(true)}
                style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--color-fg-muted)", padding: 0 }}
                title="Edit preferences"
                aria-label="Edit preferences"
              >
                <GearIcon size={14} />
              </button>
            </div>

            <p className="RepoSidebar-description">
              Skill profile built from your GitHub footprint and repository manifests.
            </p>

            <ul className="RepoSidebar-list">
              <li className="RepoSidebar-item">
                <BookIcon size={16} />
                <button onClick={() => setShowColdStartOverride(true)}>
                  Preferences
                </button>
              </li>
              <li className="RepoSidebar-item">
                <PulseIcon size={16} />
                <span>Activity: {recData?.profile?.activity_last_1m ?? 12} actions in 30 days</span>
              </li>
              <li className="RepoSidebar-item">
                <GitPullRequestIcon size={16} />
                <span>
                  <strong>{mergedCount}</strong> merged PR{mergedCount === 1 ? "" : "s"}
                </span>
              </li>
              <li className="RepoSidebar-item">
                <RepoIcon size={16} />
                <span>
                  <strong>{repoCount}</strong> repos contributed
                </span>
              </li>
            </ul>

            <div className="RepoSidebar-divider" />

            {/* Languages Section with Segmented Multi-Color Bar */}
            {languages.length > 0 && (
              <div style={{ marginBottom: "16px" }}>
                <div style={{ fontSize: "14px", fontWeight: 600, color: "var(--color-fg-default)", marginBottom: "8px" }}>
                  Languages
                </div>
                <div
                  style={{
                    display: "flex",
                    height: "8px",
                    borderRadius: "4px",
                    overflow: "hidden",
                    backgroundColor: "var(--color-border-default)",
                    marginBottom: "10px",
                  }}
                >
                  {languages.map(([lang, pct]) => (
                    <div
                      key={lang}
                      style={{
                        width: `${Math.round(pct * 100)}%`,
                        backgroundColor: LANG_COLORS[lang] || "var(--color-accent-fg)",
                      }}
                      title={`${lang}: ${Math.round(pct * 100)}%`}
                    />
                  ))}
                </div>

                <div style={{ display: "flex", flexWrap: "wrap", gap: "8px 14px", fontSize: "12px" }}>
                  {languages.slice(0, 5).map(([lang, pct]) => (
                    <span key={lang} style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                      <span
                        style={{
                          width: "8px",
                          height: "8px",
                          borderRadius: "50%",
                          backgroundColor: LANG_COLORS[lang] || "var(--color-accent-fg)",
                        }}
                      />
                      <span style={{ color: "var(--color-fg-default)", fontWeight: 500 }}>{lang}</span>
                      <span style={{ color: "var(--color-fg-muted)" }}>{Math.round(pct * 100)}%</span>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Frameworks Section (ubiquitous stoplist tools hidden) */}
            {validFrameworks.length > 0 && (
              <div style={{ marginBottom: "16px" }}>
                <div style={{ fontSize: "14px", fontWeight: 600, color: "var(--color-fg-default)", marginBottom: "8px" }}>
                  Frameworks
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                  {validFrameworks.slice(0, 8).map((fw) => (
                    <span
                      key={fw}
                      className="IssueLabel"
                      style={{
                        fontSize: "11px",
                        fontWeight: 500,
                        backgroundColor: "var(--color-canvas-subtle)",
                        borderColor: "var(--color-border-default)",
                        color: "var(--color-fg-default)",
                      }}
                    >
                      {fw}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div className="RepoSidebar-divider" />

            {/* Open-Source Footprint */}
            <div>
              <div style={{ fontSize: "14px", fontWeight: 600, color: "var(--color-fg-default)", marginBottom: "6px" }}>
                Open-source footprint
              </div>
              <div style={{ fontSize: "12px", color: "var(--color-fg-muted)", lineHeight: 1.5 }}>
                <span className="IssueLabel IssueLabel--good-first" style={{ fontSize: "11px", marginBottom: "8px", display: "inline-block" }}>
                  ✓ GitHub connected
                </span>
                <div>Derived securely via your authenticated GitHub token.</div>
              </div>
            </div>
          </aside>
        </div>

        {/* Small footer line */}
        <footer className="RepoFooter">
          <span>Not affiliated with GitHub.</span>
        </footer>
      </div>
    </div>
  );
}
