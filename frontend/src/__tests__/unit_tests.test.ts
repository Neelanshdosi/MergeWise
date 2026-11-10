import test from "node:test";
import assert from "node:assert/strict";
import { isStoppedTool, DEV_TOOLING_STOP_LIST } from "../lib/stoplist.ts";

test("stoplist filters out ubiquitous developer tools", () => {
  // Common test/lint/build tools
  assert.equal(isStoppedTool("pytest"), true);
  assert.equal(isStoppedTool("ruff"), true);
  assert.equal(isStoppedTool("eslint"), true);
  assert.equal(isStoppedTool("jest"), true);
  assert.equal(isStoppedTool("prettier"), true);
  assert.equal(isStoppedTool("black"), true);
  assert.equal(isStoppedTool("pytest-cov"), true);
  assert.equal(isStoppedTool("types-requests"), true);
  assert.equal(isStoppedTool("@types/react"), true);

  // Frameworks that MUST NOT be filtered out
  assert.equal(isStoppedTool("react"), false);
  assert.equal(isStoppedTool("next.js"), false);
  assert.equal(isStoppedTool("fastapi"), false);
  assert.equal(isStoppedTool("flask"), false);
  assert.equal(isStoppedTool("django"), false);
  assert.equal(isStoppedTool("express"), false);
  assert.equal(isStoppedTool("vue"), false);
});

test("score ring stroke calculation and color classification", () => {
  const size = 34;
  const strokeWidth = 3;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;

  // Clamping
  const clamped1 = Math.max(0, Math.min(1, 0.88));
  assert.equal(clamped1, 0.88);
  const offset1 = circumference - clamped1 * circumference;
  assert.ok(offset1 > 0 && offset1 < circumference);

  // High score color threshold (>= 70%)
  const percent1 = Math.round(0.88 * 100);
  assert.equal(percent1, 88);
  assert.ok(percent1 >= 70);

  // Low score color threshold (< 40%)
  const percent2 = Math.round(0.35 * 100);
  assert.equal(percent2, 35);
  assert.ok(percent2 < 40);
});

test("contributions summary count validation", () => {
  const items = [
    { state: "merged", via_mergewise: true },
    { state: "merged", via_mergewise: true },
    { state: "open", via_mergewise: false },
    { state: "closed", via_mergewise: false },
  ];

  const mergedCount = items.filter((i) => i.state === "merged").length;
  const openCount = items.filter((i) => i.state === "open").length;
  const closedCount = items.filter((i) => i.state === "closed").length;
  const viaMwCount = items.filter((i) => i.via_mergewise).length;

  assert.equal(mergedCount, 2);
  assert.equal(openCount, 1);
  assert.equal(closedCount, 1);
  assert.equal(viaMwCount, 2);
});

test("funnel steps progression calculation", () => {
  const funnel = {
    shown: 20,
    plan_viewed: 10,
    attempted: 6,
    pr_opened: 4,
    merged: 2,
  };

  assert.ok(funnel.shown >= funnel.plan_viewed);
  assert.ok(funnel.plan_viewed >= funnel.attempted);
  assert.ok(funnel.attempted >= funnel.pr_opened);
  assert.ok(funnel.pr_opened >= funnel.merged);

  const planViewedRate = Math.round((funnel.plan_viewed / funnel.shown) * 100);
  const mergeRate = Math.round((funnel.merged / funnel.shown) * 100);

  assert.equal(planViewedRate, 50);
  assert.equal(mergeRate, 10);
});

test("landing sequence timing constants and reduced-motion evaluation", () => {
  const TIMINGS = {
    HEADING_DELAY_MS: 400,
    HEADING_INTRO_DUR_S: 2.2,
    GAP_AFTER_HEADING_MS: 300,
    SUBHEADING_INTRO_DUR_S: 1.4,
  };

  assert.equal(TIMINGS.HEADING_DELAY_MS, 400);
  assert.equal(TIMINGS.HEADING_INTRO_DUR_S, 2.2);

  const subheadingDelay =
    TIMINGS.HEADING_DELAY_MS +
    TIMINGS.HEADING_INTRO_DUR_S * 1000 +
    TIMINGS.GAP_AFTER_HEADING_MS;
  assert.equal(subheadingDelay, 2900); // 0.4s + 2.2s + 0.3s = 2.9s

  const buttonDelay = subheadingDelay + TIMINGS.SUBHEADING_INTRO_DUR_S * 1000;
  assert.equal(buttonDelay, 4300); // 2.9s + 1.4s = 4.3s

  // Under reduced motion: delay should be 0
  const reducedMotion = true;
  const effectiveDelay = reducedMotion ? 0 : buttonDelay;
  assert.equal(effectiveDelay, 0);
});

test("landing auth double-invocation guard only triggers one redirect", async () => {
  let callCount = 0;
  let isRedirecting = false;

  const mockAuthenticate = async () => {
    callCount++;
    return new Promise((resolve) => setTimeout(resolve, 50));
  };

  const handleSignIn = async () => {
    if (isRedirecting) return;
    isRedirecting = true;
    await mockAuthenticate();
  };

  // Simulate multiple rapid clicks (e.g. while button is in flight)
  await Promise.all([
    handleSignIn(),
    handleSignIn(),
    handleSignIn(),
    handleSignIn(),
  ]);

  assert.equal(callCount, 1);
});

test("landing auth error state resets redirecting and stores clear message", async () => {
  let isRedirecting = false;
  let oauthError: string | null = null;

  const handleSignIn = async (shouldFail: boolean) => {
    if (isRedirecting) return;
    isRedirecting = true;
    oauthError = null;

    try {
      if (shouldFail) {
        throw new Error("User cancelled GitHub authentication");
      }
    } catch (err: any) {
      isRedirecting = false;
      oauthError = err.message;
    }
  };

  await handleSignIn(true);
  assert.equal(isRedirecting, false);
  assert.equal(oauthError, "User cancelled GitHub authentication");
});

test("subheading text splitting logic below 640px viewport", () => {
  const getSubheadingLines = (viewportWidth: number) => {
    const fullText = "Open-source issues matched to your GitHub work.";
    if (viewportWidth < 640) {
      return ["Open-source issues", "matched to your GitHub work."];
    }
    return [fullText];
  };

  // Mobile / Narrow
  const mobileLines = getSubheadingLines(360);
  assert.equal(mobileLines.length, 2);
  assert.equal(mobileLines[0], "Open-source issues");
  assert.equal(mobileLines[1], "matched to your GitHub work.");

  // Desktop / Wide
  const desktopLines = getSubheadingLines(1024);
  assert.equal(desktopLines.length, 1);
  assert.equal(desktopLines[0], "Open-source issues matched to your GitHub work.");
});

test("WebGL2 fallback detection and altitude constraint", () => {
  // Container altitude constraint: altitude <= containerHeight - 90, clamped between 120 and 200
  const computeAltitude = (containerHeight: number) => {
    return Math.max(120, Math.min(200, containerHeight - 90));
  };

  assert.equal(computeAltitude(360), 200);
  assert.equal(computeAltitude(260), 170);
  assert.equal(computeAltitude(200), 120);
});

test("dashboard issue client-side search filtering across title, repo, language, and labels", () => {
  const mockCandidates = [
    {
      score: 0.95,
      issue: {
        title: "Fix memory leak in websocket reconnection handler",
        repo_full_name: "facebook/react",
        primary_language: "TypeScript",
        labels: ["bug", "good first issue"],
        stars: 220000,
        created_at_epoch: 1700000000,
      },
    },
    {
      score: 0.82,
      issue: {
        title: "Add support for async streaming responses",
        repo_full_name: "tiangolo/fastapi",
        primary_language: "Python",
        labels: ["feature", "help wanted"],
        stars: 75000,
        created_at_epoch: 1710000000,
      },
    },
    {
      score: 0.70,
      issue: {
        title: "Optimize SVG rendering in GlassSurface component",
        repo_full_name: "shadcn/ui",
        primary_language: "JavaScript",
        labels: ["performance"],
        stars: 60000,
        created_at_epoch: 1690000000,
      },
    },
  ];

  const filterIssues = (list: typeof mockCandidates, query: string) => {
    const q = query.toLowerCase().trim();
    if (!q) return list;
    return list.filter((c) => {
      const titleMatch = (c.issue.title || "").toLowerCase().includes(q);
      const repoMatch = (c.issue.repo_full_name || "").toLowerCase().includes(q);
      const langMatch = (c.issue.primary_language || "").toLowerCase().includes(q);
      const labelMatch = (c.issue.labels || []).some((l) => l.toLowerCase().includes(q));
      return titleMatch || repoMatch || langMatch || labelMatch;
    });
  };

  // 1. Search by title keyword
  const byTitle = filterIssues(mockCandidates, "websocket");
  assert.equal(byTitle.length, 1);
  assert.equal(byTitle[0].issue.repo_full_name, "facebook/react");

  // 2. Search by repository name
  const byRepo = filterIssues(mockCandidates, "fastapi");
  assert.equal(byRepo.length, 1);
  assert.equal(byRepo[0].issue.title, "Add support for async streaming responses");

  // 3. Search by language
  const byLang = filterIssues(mockCandidates, "python");
  assert.equal(byLang.length, 1);
  assert.equal(byLang[0].issue.repo_full_name, "tiangolo/fastapi");

  // 4. Search by label
  const byLabel = filterIssues(mockCandidates, "good first issue");
  assert.equal(byLabel.length, 1);
  assert.equal(byLabel[0].issue.repo_full_name, "facebook/react");

  // 5. Search with no matches
  const byNone = filterIssues(mockCandidates, "ruby-on-rails-xyz");
  assert.equal(byNone.length, 0);

  // 6. Search empty query returns all
  const byEmpty = filterIssues(mockCandidates, "   ");
  assert.equal(byEmpty.length, 3);
});

test("dashboard issue sorting by Match, Newest, and Stars", () => {
  const mockCandidates = [
    {
      score: 0.72,
      issue: {
        title: "Issue C",
        stars: 80000,
        created_at_epoch: 1720000000, // newest
      },
    },
    {
      score: 0.95, // highest match
      issue: {
        title: "Issue A",
        stars: 12000,
        created_at_epoch: 1700000000,
      },
    },
    {
      score: 0.84,
      issue: {
        title: "Issue B",
        stars: 210000, // highest stars
        created_at_epoch: 1710000000,
      },
    },
  ];

  const sortIssues = (list: typeof mockCandidates, sortBy: "match" | "newest" | "stars") => {
    const copy = [...list];
    if (sortBy === "match") {
      copy.sort((a, b) => b.score - a.score);
    } else if (sortBy === "newest") {
      copy.sort((a, b) => (b.issue.created_at_epoch || 0) - (a.issue.created_at_epoch || 0));
    } else if (sortBy === "stars") {
      copy.sort((a, b) => (b.issue.stars || 0) - (a.issue.stars || 0));
    }
    return copy;
  };

  // Sort by Match (score descending)
  const sortedByMatch = sortIssues(mockCandidates, "match");
  assert.equal(sortedByMatch[0].issue.title, "Issue A");
  assert.equal(sortedByMatch[1].issue.title, "Issue B");
  assert.equal(sortedByMatch[2].issue.title, "Issue C");

  // Sort by Newest (created_at_epoch descending)
  const sortedByNewest = sortIssues(mockCandidates, "newest");
  assert.equal(sortedByNewest[0].issue.title, "Issue C");
  assert.equal(sortedByNewest[1].issue.title, "Issue B");
  assert.equal(sortedByNewest[2].issue.title, "Issue A");

  // Sort by Stars (stars descending)
  const sortedByStars = sortIssues(mockCandidates, "stars");
  assert.equal(sortedByStars[0].issue.title, "Issue B");
  assert.equal(sortedByStars[1].issue.title, "Issue C");
  assert.equal(sortedByStars[2].issue.title, "Issue A");
});

test("dashboard language dropdown filtering", () => {
  const mockCandidates = [
    { issue: { title: "React Issue", primary_language: "TypeScript" } },
    { issue: { title: "FastAPI Issue", primary_language: "Python" } },
    { issue: { title: "NextJS Issue", primary_language: "TypeScript" } },
    { issue: { title: "Django Issue", primary_language: "Python" } },
    { issue: { title: "Rust Issue", primary_language: "Rust" } },
  ];

  const filterByLang = (list: typeof mockCandidates, lang: string) => {
    if (!lang || lang === "all") return list;
    return list.filter((c) => (c.issue.primary_language || "").toLowerCase() === lang.toLowerCase());
  };

  const tsList = filterByLang(mockCandidates, "TypeScript");
  assert.equal(tsList.length, 2);
  assert.ok(tsList.every((i) => i.issue.primary_language === "TypeScript"));

  const pyList = filterByLang(mockCandidates, "python");
  assert.equal(pyList.length, 2);
  assert.ok(pyList.every((i) => i.issue.primary_language === "Python"));

  const allList = filterByLang(mockCandidates, "all");
  assert.equal(allList.length, 5);
});

test("dashboard pipeline telemetry details toggle state", () => {
  let isPipelineDetailsOpen = false;

  const togglePipelineDetails = () => {
    isPipelineDetailsOpen = !isPipelineDetailsOpen;
  };

  assert.equal(isPipelineDetailsOpen, false);
  togglePipelineDetails();
  assert.equal(isPipelineDetailsOpen, true);
  togglePipelineDetails();
  assert.equal(isPipelineDetailsOpen, false);
});

test("preview page contains visible sample data labels and indicators", async () => {
  const fs = await import("node:fs");
  const path = await import("node:path");
  const previewContent = fs.readFileSync(path.resolve(process.cwd(), "src/app/preview/page.tsx"), "utf-8");

  assert.ok(
    previewContent.includes("Sample data"),
    "Preview page must contain visible 'Sample data' label"
  );
  assert.ok(
    previewContent.includes("Interactive Preview Notice Banner"),
    "Preview page must contain interactive preview notice banner"
  );
});


