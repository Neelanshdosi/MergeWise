"use client";

import React, { useState, useEffect, useMemo, useRef, use } from "react";
import IssueCard from "@/components/IssueCard";
import PlanModal from "@/components/PlanModal";
import ContributionsTab from "@/components/ContributionsTab";
import ProgressTab from "@/components/ProgressTab";
import {
  ScoredIssueCandidate,
  IssuePlanResponse,
  ContributionsResponse,
  FunnelMetricsResponse,
} from "@/lib/types";
import {
  IssueOpenedIcon,
  GearIcon,
  SyncIcon,
  TrashIcon,
  GitPullRequestIcon,
  CheckIcon,
  BookIcon,
  PulseIcon,
  RepoIcon,
  SearchIcon,
  TriangleDownIcon,
} from "@/components/Octicons";
import { isStoppedTool } from "@/lib/stoplist";

const SAMPLE_PLAN: IssuePlanResponse = {
  repo_full_name: "facebook/react",
  issue_number: 28901,
  difficulty: "Beginner",
  estimated_hours: "2–3 hours",
  effort_reasoning: "Well-isolated component scope with clear test reproduction.",
  user_can_override_effort: true,
  repo_health: {
    repo_full_name: "facebook/react",
    overall_badge: "Responsive & Healthy",
    response_time_human: "< 24 hours",
    first_time_pr_merge_rate_human: "78% merged",
    days_since_last_push_human: "2 days ago",
    has_contributing_guide: true,
    contributing_guide_path: "CONTRIBUTING.md",
    sampled_issues_count: 20,
    sampled_prs_count: 20,
    summary: "Active maintainers frequently review community PRs and provide constructive feedback.",
  },
  setup_command: "yarn install && yarn build",
  setup_citation: "CONTRIBUTING.md:42",
  test_command: "yarn test packages/react/src/__tests__/ReactSuspense-test.js",
  test_citation: ".github/workflows/runtime.yml:85",
  verified_files_to_edit: [
    "packages/react/src/ReactSuspenseBoundary.js",
    "packages/react-dom/src/client/ReactDOMComponent.js",
  ],
  steps: [
    "Clone the repository and run yarn install to ensure all workspace dependencies are satisfied.",
    "Reproduce the Suspense hydration warning locally by running the targeted Jest test suite.",
    "Inspect ReactSuspenseBoundary.js and compare server initial paint hydration markers with client state.",
    "Add a guard check to ensure nested boundary IDs match before asserting hydration equivalence.",
    "Run yarn test and verify that all Suspense regression tests pass cleanly.",
  ],
  draft_claim_comment:
    "Hi! I would love to work on this issue. I've reproduced the hydration mismatch in ReactSuspenseBoundary.js and have an initial patch ready that guards against nested boundary ID misalignment.",
  llm_used: true,
  llm_error: null,
  tools_called: ["search_repo_docs", "verify_repo_tree"],
  token_usage: {
    prompt_tokens: 450,
    candidates_tokens: 320,
    total_tokens: 770,
  },
  cached: false,
};

const SAMPLE_CANDIDATES: ScoredIssueCandidate[] = [
  {
    issue: {
      issue_url: "https://api.github.com/repos/facebook/react/issues/28901",
      repo_full_name: "facebook/react",
      issue_number: 28901,
      title: "Fix hydration warning mismatch when rendering nested Suspense boundaries",
      body: "When rendering nested Suspense boundaries with server components, hydration mismatch occurs on initial paint.",
      primary_language: "TypeScript",
      labels: ["good first issue", "component: suspense", "help wanted"],
      stars: 224500,
      open_issues_count: 850,
      body_length: 320,
      created_at_epoch: Math.floor(Date.now() / 1000) - 86400 * 3,
      html_url: "https://github.com/facebook/react/issues/28901",
    },
    features: {
      lang_commit_share: 0.65,
      domain_topic_overlap: 0.8,
      repo_stars_log: 5.35,
      issue_body_length_log: 2.85,
      has_good_first_issue_label: 1,
      has_help_wanted_label: 1,
      lang_match: 1,
      text_cosine_sim: 0.75,
      user_total_commits: 120,
      user_total_prs: 15,
      user_total_reviews: 8,
      user_total_repos: 5,
      user_act_1m: 35,
      user_act_2m: 20,
      user_act_3m: 10,
      recency_weighted_activeness: 0.85,
    },
    score: 0.88,
    one_line_reason:
      "Matches your TypeScript experience (65% of footprint) and React framework depth. Well-scoped bug with test harness.",
    viability_verified: true,
    score_breakdown: {
      language_familiarity: 0.9,
      domain_framework_fit: 0.85,
      issue_clarity_scoping: 0.88,
      labels_accessibility: 0.95,
      repo_health_recency: 0.82,
    },
  },
  {
    issue: {
      issue_url: "https://api.github.com/repos/vercel/next.js/issues/64210",
      repo_full_name: "vercel/next.js",
      issue_number: 64210,
      title: "Add error boundary fallback type definition for App Router parallel routes",
      body: "TypeScript definitions for parallel route default slot error boundary props are currently typed as any.",
      primary_language: "TypeScript",
      labels: ["good first issue", "area: TypeScript", "documentation"],
      stars: 121000,
      open_issues_count: 530,
      body_length: 240,
      created_at_epoch: Math.floor(Date.now() / 1000) - 86400 * 5,
      html_url: "https://github.com/vercel/next.js/issues/64210",
    },
    features: {
      lang_commit_share: 0.65,
      domain_topic_overlap: 0.85,
      repo_stars_log: 5.08,
      issue_body_length_log: 2.6,
      has_good_first_issue_label: 1,
      has_help_wanted_label: 0,
      lang_match: 1,
      text_cosine_sim: 0.72,
      user_total_commits: 120,
      user_total_prs: 15,
      user_total_reviews: 8,
      user_total_repos: 5,
      user_act_1m: 35,
      user_act_2m: 20,
      user_act_3m: 10,
      recency_weighted_activeness: 0.85,
    },
    score: 0.82,
    one_line_reason:
      "Direct stack fit for Next.js App Router. Clean typing task without complex runtime regressions.",
    viability_verified: true,
    score_breakdown: {
      language_familiarity: 0.88,
      domain_framework_fit: 0.9,
      issue_clarity_scoping: 0.82,
      labels_accessibility: 0.85,
      repo_health_recency: 0.75,
    },
  },
  {
    issue: {
      issue_url: "https://api.github.com/repos/pallets/flask/issues/5420",
      repo_full_name: "pallets/flask",
      issue_number: 5420,
      title: "Improve Blueprint url_prefix validation and error reporting",
      body: "Invalid url_prefix on blueprints raises generic ValueError without naming the faulty blueprint.",
      primary_language: "Python",
      labels: ["bug", "easy"],
      stars: 67000,
      open_issues_count: 120,
      body_length: 180,
      created_at_epoch: Math.floor(Date.now() / 1000) - 86400 * 8,
      html_url: "https://github.com/pallets/flask/issues/5420",
    },
    features: {
      lang_commit_share: 0.25,
      domain_topic_overlap: 0.7,
      repo_stars_log: 4.82,
      issue_body_length_log: 2.32,
      has_good_first_issue_label: 0,
      has_help_wanted_label: 0,
      lang_match: 1,
      text_cosine_sim: 0.68,
      user_total_commits: 120,
      user_total_prs: 15,
      user_total_reviews: 8,
      user_total_repos: 5,
      user_act_1m: 35,
      user_act_2m: 20,
      user_act_3m: 10,
      recency_weighted_activeness: 0.85,
    },
    score: 0.74,
    one_line_reason:
      "Matches your Python experience (25% of recent work). Very clean test suite with clear contributing guidelines.",
    viability_verified: true,
    score_breakdown: {
      language_familiarity: 0.75,
      domain_framework_fit: 0.7,
      issue_clarity_scoping: 0.85,
      labels_accessibility: 0.7,
      repo_health_recency: 0.8,
    },
  },
];

const SAMPLE_CONTRIBUTIONS: ContributionsResponse = {
  summary: {
    merged_count: 4,
    open_count: 2,
    closed_count: 1,
    repo_count: 5,
  },
  items: [
    {
      repo: "pallets/flask",
      number: 5312,
      title: "Fix Blueprint url_prefix validation error message",
      state: "merged",
      created_at: "2026-04-10T14:30:00Z",
      merged_at: "2026-04-12T09:15:00Z",
      url: "https://github.com/pallets/flask/pull/5312",
      stars: 67000,
      repo_owner_avatar_url: "https://github.com/pallets.png",
      via_mergewise: true,
    },
    {
      repo: "facebook/react",
      number: 28850,
      title: "Fix Suspense hydration mismatch in nested boundaries",
      state: "merged",
      created_at: "2026-03-22T11:00:00Z",
      merged_at: "2026-03-25T18:40:00Z",
      url: "https://github.com/facebook/react/pull/28850",
      stars: 224500,
      repo_owner_avatar_url: "https://github.com/facebook.png",
      via_mergewise: true,
    },
    {
      repo: "vercel/next.js",
      number: 64100,
      title: "Add typings for parallel route fallback props",
      state: "open",
      created_at: "2026-05-02T10:20:00Z",
      merged_at: null,
      url: "https://github.com/vercel/next.js/pull/64100",
      stars: 121000,
      repo_owner_avatar_url: "https://github.com/vercel.png",
      via_mergewise: true,
    },
    {
      repo: "encode/starlette",
      number: 2410,
      title: "Improve async exception handler response formatting",
      state: "merged",
      created_at: "2026-02-18T16:00:00Z",
      merged_at: "2026-02-20T11:30:00Z",
      url: "https://github.com/encode/starlette/pull/2410",
      stars: 10500,
      repo_owner_avatar_url: "https://github.com/encode.png",
      via_mergewise: false,
    },
    {
      repo: "fastapi/fastapi",
      number: 11020,
      title: "Docs: Clarify OAuth2 password flow refresh token handling",
      state: "open",
      created_at: "2026-01-15T09:00:00Z",
      merged_at: null,
      url: "https://github.com/fastapi/fastapi/pull/11020",
      stars: 78000,
      repo_owner_avatar_url: "https://github.com/fastapi.png",
      via_mergewise: false,
    },
  ],
};

const SAMPLE_FUNNEL: FunnelMetricsResponse = {
  shown: 24,
  plan_viewed: 14,
  attempted: 9,
  pr_opened: 5,
  merged: 4,
};

const ALL_FRAMEWORKS = [
  "react",
  "next.js",
  "fastapi",
  "flask",
  "pydantic",
  "pytest",
  "ruff",
  "black",
  "jest",
];

const LANG_COLORS: Record<string, string> = {
  TypeScript: "#3178c6",
  JavaScript: "#f1e05a",
  Python: "#3572A5",
  Go: "#00ADD8",
  Rust: "#dea584",
};

export default function PreviewPage({
  searchParams,
}: {
  searchParams?: Promise<{ tab?: string; theme?: string; modal?: string; pipeline?: string; drawer?: string }>;
}) {
  const resolvedParams = searchParams ? use(searchParams) : undefined;
  const initialTab =
    resolvedParams?.tab === "contributions" || resolvedParams?.tab === "contributions_empty"
      ? "contributions"
      : resolvedParams?.tab === "progress"
      ? "progress"
      : "recommended";
  const initialEmpty = resolvedParams?.tab === "contributions_empty";
  const initialModal = resolvedParams?.modal === "true" || resolvedParams?.modal === "open";
  const initialPipeline = resolvedParams?.pipeline === "true" || resolvedParams?.pipeline === "open";
  const currentTheme = resolvedParams?.theme || "dark";

  const [activeTab, setActiveTab] = useState<"recommended" | "contributions" | "progress">(initialTab);
  const [modalOpen, setModalOpen] = useState<boolean>(initialModal);
  const [emptyContributions, setEmptyContributions] = useState<boolean>(initialEmpty);
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState<"match" | "newest" | "stars">("match");
  const [languageFilter, setLanguageFilter] = useState("all");
  const [isPipelineOpen, setIsPipelineOpen] = useState(initialPipeline);
  const [isSortOpen, setIsSortOpen] = useState(false);
  const [isLangOpen, setIsLangOpen] = useState(false);

  const sortRef = useRef<HTMLDivElement>(null);
  const langRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (typeof document !== "undefined") {
      document.documentElement.setAttribute("data-theme", currentTheme);
    }
  }, [currentTheme]);

  useEffect(() => {
    const handleOutside = (e: MouseEvent) => {
      if (sortRef.current && !sortRef.current.contains(e.target as Node)) {
        setIsSortOpen(false);
      }
      if (langRef.current && !langRef.current.contains(e.target as Node)) {
        setIsLangOpen(false);
      }
    };
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, []);

  const validFrameworks = ALL_FRAMEWORKS.filter((fw) => !isStoppedTool(fw));

  // Client-side search & filtering
  const filteredIssues = useMemo(() => {
    let list = [...SAMPLE_CANDIDATES];
    if (languageFilter !== "all") {
      list = list.filter((c) => (c.issue.primary_language || "").toLowerCase() === languageFilter.toLowerCase());
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      list = list.filter((c) => {
        return (
          c.issue.title.toLowerCase().includes(q) ||
          c.issue.repo_full_name.toLowerCase().includes(q) ||
          (c.issue.primary_language || "").toLowerCase().includes(q) ||
          (c.issue.labels || []).some((l) => l.toLowerCase().includes(q))
        );
      });
    }
    if (sortBy === "match") {
      list.sort((a, b) => b.score - a.score);
    } else if (sortBy === "newest") {
      list.sort((a, b) => (b.issue.created_at_epoch || 0) - (a.issue.created_at_epoch || 0));
    } else if (sortBy === "stars") {
      list.sort((a, b) => (b.issue.stars || 0) - (a.issue.stars || 0));
    }
    return list;
  }, [searchQuery, languageFilter, sortBy]);

  const sortLabel = sortBy === "match" ? "Match" : sortBy === "newest" ? "Newest" : "Stars";
  const langLabel = languageFilter === "all" ? "All languages" : languageFilter;

  return (
    <div
      data-theme={currentTheme}
      style={{
        backgroundColor: "var(--color-canvas-default)",
        color: "var(--color-fg-default)",
        minHeight: "100vh",
      }}
    >
      {/* 2. Underline Nav under Header (GitHub Repo Style) */}
      <nav className="RepoNav" aria-label="Repository navigation">
        <div className="RepoNav-container" role="tablist">
          <button
            id="tab-recommended"
            role="tab"
            aria-selected={activeTab === "recommended"}
            className={`RepoNav-item ${activeTab === "recommended" ? "selected" : ""}`}
            onClick={() => setActiveTab("recommended")}
          >
            <IssueOpenedIcon size={16} />
            <span>Recommended</span>
            <span className="Counter">{SAMPLE_CANDIDATES.length}</span>
          </button>

          <button
            id="tab-contributions"
            role="tab"
            aria-selected={activeTab === "contributions"}
            className={`RepoNav-item ${activeTab === "contributions" ? "selected" : ""}`}
            onClick={() => {
              setActiveTab("contributions");
              setEmptyContributions(false);
            }}
          >
            <GitPullRequestIcon size={16} />
            <span>My contributions</span>
            <span className="Counter">{SAMPLE_CONTRIBUTIONS.summary.merged_count}</span>
          </button>

          <button
            id="tab-progress"
            role="tab"
            aria-selected={activeTab === "progress"}
            className={`RepoNav-item ${activeTab === "progress" ? "selected" : ""}`}
            onClick={() => setActiveTab("progress")}
          >
            <CheckIcon size={16} />
            <span>Progress</span>
          </button>
        </div>
      </nav>

      {/* Interactive Preview Notice Banner */}
      <div
        style={{
          backgroundColor: "rgba(210, 153, 34, 0.12)",
          borderBottom: "1px solid rgba(210, 153, 34, 0.35)",
          padding: "8px 24px",
          fontSize: "13px",
          color: "var(--color-attention-fg, #d29922)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "8px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span
            style={{
              padding: "1px 6px",
              borderRadius: "12px",
              backgroundColor: "var(--color-attention-fg, #d29922)",
              color: "#000",
              fontWeight: 700,
              fontSize: "11px",
              textTransform: "uppercase",
              letterSpacing: "0.5px",
            }}
          >
            Sample data
          </span>
          <span>
            You are viewing the interactive showcase populated with <strong>Sample data</strong> (no GitHub login required).
          </span>
        </div>
        <a
          href="/"
          style={{
            color: "var(--color-accent-fg, #58a6ff)",
            fontWeight: 500,
            textDecoration: "none",
            fontSize: "12px",
          }}
        >
          Sign in for live recommendations &rarr;
        </a>
      </div>

      {/* Main Layout Container */}
      <div className="RepoLayout">
        {/* 3. Title Row */}
        <div className="RepoTitleRow">
          <div className="RepoTitle-left">
            <img
              src="/mergewise-logo.png"
              alt="MergeWise"
              width={32}
              height={32}
              style={{ width: "32px", height: "32px", borderRadius: "50%", objectFit: "cover" }}
              className="RepoTitle-avatar"
            />
            <h1 className="RepoTitle-name" style={{ margin: 0, padding: 0 }}>
              MergeWise
            </h1>
            <span className="RepoTitle-badge">OSS Match</span>
            <span
              className="IssueLabel"
              style={{
                backgroundColor: "rgba(210, 153, 34, 0.15)",
                color: "var(--color-attention-fg, #d29922)",
                borderColor: "rgba(210, 153, 34, 0.4)",
                borderWidth: "1px",
                borderStyle: "solid",
                fontWeight: 600,
                fontSize: "12px",
                padding: "2px 8px",
                display: "inline-flex",
                alignItems: "center",
                gap: "5px",
              }}
            >
              <span style={{ width: "6px", height: "6px", borderRadius: "50%", backgroundColor: "#d29922" }} />
              Sample data
            </span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <button className="btn btn-sm">
              <GearIcon size={14} />
              <span>Preferences</span>
            </button>
            <button className="btn btn-sm btn-primary">
              <SyncIcon size={14} />
              <span>Refresh</span>
            </button>
          </div>
        </div>

        {/* 4. Toolbar Row */}
        {activeTab === "recommended" && (
          <div className="RepoToolbar">
            <div className="RepoToolbar-left">
              {/* Sort Dropdown */}
              <div className="RepoDropdown-wrapper" ref={sortRef}>
                <button
                  className="btn btn-sm"
                  onClick={() => setIsSortOpen(!isSortOpen)}
                  aria-haspopup="true"
                  aria-expanded={isSortOpen}
                >
                  <span>Sort: {sortLabel}</span>
                  <TriangleDownIcon size={12} />
                </button>
                {isSortOpen && (
                  <div className="RepoDropdown-menu" role="menu">
                    <button
                      className={`RepoDropdown-item ${sortBy === "match" ? "selected" : ""}`}
                      onClick={() => {
                        setSortBy("match");
                        setIsSortOpen(false);
                      }}
                    >
                      <span>Match (Best fit)</span>
                      {sortBy === "match" && <CheckIcon size={14} />}
                    </button>
                    <button
                      className={`RepoDropdown-item ${sortBy === "newest" ? "selected" : ""}`}
                      onClick={() => {
                        setSortBy("newest");
                        setIsSortOpen(false);
                      }}
                    >
                      <span>Newest (Created)</span>
                      {sortBy === "newest" && <CheckIcon size={14} />}
                    </button>
                    <button
                      className={`RepoDropdown-item ${sortBy === "stars" ? "selected" : ""}`}
                      onClick={() => {
                        setSortBy("stars");
                        setIsSortOpen(false);
                      }}
                    >
                      <span>Stars (Most stars)</span>
                      {sortBy === "stars" && <CheckIcon size={14} />}
                    </button>
                  </div>
                )}
              </div>

              {/* Language Filter Dropdown */}
              <div className="RepoDropdown-wrapper" ref={langRef}>
                <button
                  className="btn btn-sm"
                  onClick={() => setIsLangOpen(!isLangOpen)}
                  aria-haspopup="true"
                  aria-expanded={isLangOpen}
                >
                  <span>Language: {langLabel}</span>
                  <TriangleDownIcon size={12} />
                </button>
                {isLangOpen && (
                  <div className="RepoDropdown-menu" role="menu">
                    <button
                      className={`RepoDropdown-item ${languageFilter === "all" ? "selected" : ""}`}
                      onClick={() => {
                        setLanguageFilter("all");
                        setIsLangOpen(false);
                      }}
                    >
                      <span>All languages</span>
                      {languageFilter === "all" && <CheckIcon size={14} />}
                    </button>
                    {["TypeScript", "Python"].map((lang) => (
                      <button
                        key={lang}
                        className={`RepoDropdown-item ${languageFilter.toLowerCase() === lang.toLowerCase() ? "selected" : ""}`}
                        onClick={() => {
                          setLanguageFilter(lang);
                          setIsLangOpen(false);
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
                />
              </div>
            </div>
          </div>
        )}

        {/* 5. Main 2-column Layout */}
        <div className="RepoGrid">
          {/* Main Column */}
          <main className="RepoMain">
            {/* TAB 1: RECOMMENDED */}
            {activeTab === "recommended" && (
              <div>
                {/* 6. Issue Table Box (File-list Style) */}
                <div className="RepoTable">
                  {/* Header Bar */}
                  <div className="RepoTable-header">
                    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                      <img
                        src="https://avatars.githubusercontent.com/u/583231?v=4"
                        alt="octocat"
                        style={{
                          width: "20px",
                          height: "20px",
                          borderRadius: "50%",
                          border: "1px solid var(--color-border-default)",
                        }}
                      />
                      <span style={{ fontWeight: 600, color: "var(--color-fg-default)" }}>
                        Scanned 28 candidates,{" "}
                        <span style={{ color: "var(--color-success-fg)" }}>
                          {filteredIssues.length} passed viability
                        </span>
                      </span>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: "12px", fontSize: "12px" }}>
                      <span>updated 2 minutes ago</span>
                      <button
                        onClick={() => setIsPipelineOpen(!isPipelineOpen)}
                        style={{
                          background: "transparent",
                          border: "none",
                          color: "var(--color-accent-fg)",
                          cursor: "pointer",
                          fontSize: "12px",
                          fontWeight: 500,
                          textDecoration: "underline",
                          padding: "2px 4px",
                        }}
                      >
                        {isPipelineOpen ? "Hide pipeline details" : "Pipeline details"}
                      </button>
                    </div>
                  </div>

                  {/* Inline Pipeline Details */}
                  {isPipelineOpen && (
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
                            <td style={{ padding: "6px 12px", fontWeight: 600, color: "var(--color-fg-default)" }}>6 queries</td>
                          </tr>
                          <tr style={{ borderBottom: "1px solid var(--color-border-default)" }}>
                            <td style={{ padding: "6px 12px", color: "var(--color-fg-muted)" }}>Candidates Fetched</td>
                            <td style={{ padding: "6px 12px", fontWeight: 600, color: "var(--color-fg-default)" }}>28</td>
                          </tr>
                          <tr style={{ borderBottom: "1px solid var(--color-border-default)" }}>
                            <td style={{ padding: "6px 12px", color: "var(--color-fg-muted)" }}>Passed Viability</td>
                            <td style={{ padding: "6px 12px", fontWeight: 600, color: "var(--color-success-fg)" }}>3</td>
                          </tr>
                          <tr style={{ borderBottom: "1px solid var(--color-border-default)" }}>
                            <td style={{ padding: "6px 12px", color: "var(--color-fg-muted)" }}>Search API Limit</td>
                            <td style={{ padding: "6px 12px", fontWeight: 600 }}>24/30 req/min</td>
                          </tr>
                          <tr>
                            <td style={{ padding: "6px 12px", color: "var(--color-fg-muted)" }}>Filter Breakdown</td>
                            <td style={{ padding: "6px 12px", color: "var(--color-fg-default)" }}>
                              14 assigned · 8 competing PRs · 3 claimed in comments
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  )}

                  {/* Rows */}
                  {filteredIssues.map((cand, idx) => (
                    <IssueCard key={cand.issue.issue_number} candidate={cand} index={idx} />
                  ))}
                </div>

                {/* 7. README-Style Box: "Why these results" */}
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
                      Prioritizing TypeScript and Python based on 90-day GitHub activity. Boosted Facebook/React and Next.js due to high framework overlap and clean contributing guides. Skipped Rust issues based on user preference.
                    </p>
                  </div>
                </div>

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
                    <button className="btn btn-danger btn-sm">
                      <TrashIcon size={14} />
                      <span>Delete my data</span>
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 2: CONTRIBUTIONS */}
            {activeTab === "contributions" && (
              <ContributionsTab
                data={emptyContributions ? { summary: { merged_count: 0, open_count: 0, closed_count: 0, repo_count: 0 }, items: [] } : SAMPLE_CONTRIBUTIONS}
                loading={false}
                onRefresh={() => {}}
                onSwitchToRecommended={() => setActiveTab("recommended")}
              />
            )}

            {/* TAB 3: PROGRESS */}
            {activeTab === "progress" && (
              <ProgressTab
                funnel={SAMPLE_FUNNEL}
                whyTheseResults="Prioritizing TypeScript and Python based on 90-day GitHub activity. Boosted Facebook/React and Next.js due to high framework overlap."
                loading={false}
              />
            )}
          </main>

          {/* 8. Right Sidebar "About" */}
          <aside className="RepoSidebar">
            <div className="RepoSidebar-heading">
              <span>About</span>
              <button
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
                <button>Preferences</button>
              </li>
              <li className="RepoSidebar-item">
                <PulseIcon size={16} />
                <span>Activity: 18 actions in 30 days</span>
              </li>
              <li className="RepoSidebar-item">
                <GitPullRequestIcon size={16} />
                <span>
                  <strong>4</strong> merged PRs
                </span>
              </li>
              <li className="RepoSidebar-item">
                <RepoIcon size={16} />
                <span>
                  <strong>5</strong> repos contributed
                </span>
              </li>
            </ul>

            <div className="RepoSidebar-divider" />

            {/* Languages Bar */}
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
                <div style={{ width: "65%", backgroundColor: "#3178c6" }} title="TypeScript: 65%" />
                <div style={{ width: "25%", backgroundColor: "#3572A5" }} title="Python: 25%" />
                <div style={{ width: "10%", backgroundColor: "#dea584" }} title="Rust: 10%" />
              </div>

              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px 14px", fontSize: "12px" }}>
                <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                  <span style={{ width: "8px", height: "8px", borderRadius: "50%", backgroundColor: "#3178c6" }} />
                  <span style={{ color: "var(--color-fg-default)", fontWeight: 500 }}>TypeScript</span>
                  <span style={{ color: "var(--color-fg-muted)" }}>65%</span>
                </span>
                <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                  <span style={{ width: "8px", height: "8px", borderRadius: "50%", backgroundColor: "#3572A5" }} />
                  <span style={{ color: "var(--color-fg-default)", fontWeight: 500 }}>Python</span>
                  <span style={{ color: "var(--color-fg-muted)" }}>25%</span>
                </span>
              </div>
            </div>

            {/* Frameworks */}
            <div style={{ marginBottom: "16px" }}>
              <div style={{ fontSize: "14px", fontWeight: 600, color: "var(--color-fg-default)", marginBottom: "8px" }}>
                Frameworks
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                {validFrameworks.map((fw) => (
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

        {/* Footer */}
        <footer className="RepoFooter">
          <span>Not affiliated with GitHub.</span>
        </footer>
      </div>

      {/* How to Start Modal for Preview Testing */}
      {modalOpen && (
        <PlanModal
          candidate={SAMPLE_CANDIDATES[0]}
          isOpen={modalOpen}
          onClose={() => setModalOpen(false)}
          jwtToken="preview-mock-token"
        />
      )}
    </div>
  );
}
