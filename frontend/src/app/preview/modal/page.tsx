"use client";

import React, { useState, useEffect } from "react";
import PlanModal from "@/components/PlanModal";
import { ScoredIssueCandidate, IssuePlanResponse } from "@/lib/types";

const SAMPLE_CANDIDATE: ScoredIssueCandidate = {
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
    lang_match: 1,
    lang_commit_share: 0.65,
    domain_topic_overlap: 0.8,
    text_cosine_sim: 0.75,
    user_total_commits: 120,
    user_total_prs: 15,
    user_total_reviews: 8,
    user_total_repos: 5,
    user_act_1m: 35,
    user_act_2m: 20,
    user_act_3m: 10,
    recency_weighted_activeness: 0.85,
    repo_stars_log: 12.3,
    issue_body_length_log: 5.7,
    has_good_first_issue_label: 1,
    has_help_wanted_label: 1,
  },
  score: 0.94,
  one_line_reason: "Matches your deep TypeScript experience and React library contributions.",
  viability_verified: true,
  score_breakdown: {
    language_familiarity: 0.95,
    domain_framework_fit: 0.92,
    issue_clarity_scoping: 0.88,
    labels_accessibility: 1.0,
    repo_health_recency: 0.95,
  },
};

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

export default function ModalPreviewPage() {
  const [open, setOpen] = useState(true);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const qTheme = params.get("theme");
      if (qTheme === "light" || qTheme === "dark") {
        document.documentElement.setAttribute("data-theme", qTheme);
      }
    }
  }, []);

  return (
    <div style={{ minHeight: "100vh", backgroundColor: "var(--color-canvas-default)", padding: "20px" }}>
      <PlanModal
        isOpen={open}
        onClose={() => setOpen(false)}
        candidate={SAMPLE_CANDIDATE}
        initialPlan={SAMPLE_PLAN}
        disablePortal={true}
      />
    </div>
  );
}
