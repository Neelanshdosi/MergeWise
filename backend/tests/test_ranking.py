from mergewise_features import (
    UserSkillProfile,
    IssueMetadata,
    ColdStartQuestionnaire,
    compute_feature_vector,
    extract_frameworks_from_manifest,
    score_candidate_issue,
)
from app.ranker.heuristic import rank_viable_issues


def test_manifest_framework_extraction():
    # 1. package.json
    pkg_json = """{
        "dependencies": {
            "react": "^18.2.0",
            "next": "14.0.0",
            "@tailwindcss/forms": "^0.5.0",
            "lodash": "^4.17.21"
        },
        "devDependencies": {
            "typescript": "^5.0.0",
            "vitest": "^1.0.0"
        }
    }"""
    frameworks = extract_frameworks_from_manifest("package.json", pkg_json)
    assert "react" in frameworks
    assert "next" in frameworks
    assert "vitest" in frameworks

    # 2. requirements.txt
    req_txt = """
    fastapi>=0.100.0
    pydantic==2.5.0
    uvicorn[standard]
    # some comment
    pytest
    """
    py_frameworks = extract_frameworks_from_manifest("requirements.txt", req_txt)
    assert "fastapi" in py_frameworks
    assert "pydantic" in py_frameworks
    assert "pytest" in py_frameworks


def test_feature_vector_calculation():
    profile = UserSkillProfile(
        username="dev1",
        primary_languages={"TypeScript": 0.7, "Python": 0.3},
        frameworks=["react", "fastapi"],
        topics=["cli", "developer-tools"],
        total_commits=150,
        total_prs=25,
        total_reviews=10,
        total_repos_contributed=8,
        activity_last_1m=12,
        activity_last_2m=6,
        activity_last_3m=2,
    )

    issue = IssueMetadata(
        issue_url="https://api.github.com/repos/facebook/react/issues/100",
        repo_full_name="facebook/react",
        issue_number=100,
        title="Fix hydration error in dev tools",
        body="Short reproduction steps for hydration mismatch.",
        primary_language="TypeScript",
        labels=["good first issue", "developer-tools"],
        stars=210000,
        body_length=45,
    )

    features = compute_feature_vector(profile, issue)
    assert features.lang_match == 1.0
    assert features.lang_commit_share == 0.7
    assert features.has_good_first_issue_label == 1
    assert features.user_total_commits == 150
    # Recency weighted: (3*12 + 2*6 + 1*2) / 6 = (36 + 12 + 2) / 6 = 50 / 6 = 8.333
    assert abs(features.recency_weighted_activeness - (50.0 / 6.0)) < 0.01

    score, reason = score_candidate_issue(profile, issue, features)
    assert score > 0.5
    assert "TypeScript" in reason
    assert "small feature" in reason


def test_manifest_framework_matching_not_issue_text():
    """
    Test requirement 2:
    - Matches must compare user dependency names to candidate repo manifest dependencies.
    - Matches must NEVER be inferred from words in the issue text.
    - Show matches ONLY when both sides have the dependency.
    """
    profile = UserSkillProfile(
        username="test_dev",
        frameworks=["pytest", "ruff", "pyspark"],
    )

    # Candidate 1: issue text mentions pytest and ruff and pyspark, but repo manifest does NOT have them
    issue_text_only = IssueMetadata(
        issue_url="https://api.github.com/repos/org/repo1/issues/1",
        repo_full_name="org/repo1",
        title="We should migrate to pytest, ruff, and pyspark",
        body="This issue talks heavily about pytest and ruff and pyspark all over the body.",
        primary_language="Python",
        repo_frameworks=["flask", "sqlalchemy"],
    )

    feat1 = compute_feature_vector(profile, issue_text_only)
    score1, reason1 = score_candidate_issue(profile, issue_text_only, feat1)
    assert issue_text_only.matching_frameworks == []
    assert "uses pytest" not in reason1
    assert "uses ruff" not in reason1
    assert "uses pyspark" not in reason1

    # Candidate 2: issue text has generic wording, repo manifest HAS pytest and pyspark.
    # pytest must be ignored (stop list), pyspark must match and appear in reason!
    issue_manifest_match = IssueMetadata(
        issue_url="https://api.github.com/repos/org/repo2/issues/2",
        repo_full_name="org/repo2",
        title="Fix subtle calculation error",
        body="Generic bug description with `calc()` function snippet.",
        primary_language="Python",
        labels=["bug"],
        repo_frameworks=["pytest", "pyspark", "numpy"],
        stars=100,
        days_since_push=3,
        body_length=300,
        has_code_snippet=True,
    )

    feat2 = compute_feature_vector(profile, issue_manifest_match)
    score2, reason2 = score_candidate_issue(profile, issue_manifest_match, feat2)
    assert "pyspark" in issue_manifest_match.matching_frameworks
    assert "pytest" not in issue_manifest_match.matching_frameworks
    assert "uses pyspark like your repos" in reason2
    assert "pytest" not in reason2
    assert "small scoped bug with code snippet" in reason2
    assert "repo updated 3 days ago" in reason2


def test_domain_framework_bigquery_outranks_pytest_only():
    """
    Test requirement:
    One candidate matches only pytest (stop-list dev dependency).
    Another candidate matches google-cloud-bigquery (heavy domain match).
    The bigquery candidate must rank higher.
    """
    profile = UserSkillProfile(
        username="data_dev",
        primary_languages={"Python": 1.0},
        frameworks=["pytest", "google-cloud-bigquery"],
    )

    # Candidate A: repo matches only pytest
    candidate_pytest_only = IssueMetadata(
        issue_url="https://api.github.com/repos/org/pytest-repo/issues/1",
        repo_full_name="org/pytest-repo",
        title="Fix subtle bug in runner",
        body="Short bug description.",
        primary_language="Python",
        labels=["good first issue"],
        stars=100,
        body_length=150,
        repo_frameworks=["pytest", "setuptools"],
        days_since_push=1,
    )

    # Candidate B: repo matches google-cloud-bigquery
    candidate_bigquery = IssueMetadata(
        issue_url="https://api.github.com/repos/org/bigquery-repo/issues/2",
        repo_full_name="org/bigquery-repo",
        title="Improve partition schema handling",
        body="Short issue description.",
        primary_language="Python",
        labels=["good first issue"],
        stars=100,
        body_length=150,
        repo_frameworks=["google-cloud-bigquery"],
        days_since_push=1,
    )

    ranked = rank_viable_issues(profile, [candidate_pytest_only, candidate_bigquery], top_k=2)

    assert len(ranked) == 2
    # The bigquery issue must rank higher than the pytest-only issue
    assert ranked[0].issue.repo_full_name == "org/bigquery-repo"
    assert ranked[0].score > ranked[1].score
    assert "google-cloud-bigquery" in ranked[0].issue.matching_frameworks
    assert "uses google-cloud-bigquery like your repos" in ranked[0].one_line_reason

    # The pytest-only candidate must NOT match pytest in matching_frameworks or in reason
    assert ranked[1].issue.matching_frameworks == []
    assert "pytest" not in ranked[1].one_line_reason


def test_push_recency_wording():
    """
    Test requirement 3:
    "repo updated today" for 0 days, "1 day ago", then "N days ago".
    """
    profile = UserSkillProfile(username="dev", primary_languages={"Python": 1.0})

    issue_0 = IssueMetadata(issue_url="url0", repo_full_name="org/r0", primary_language="Python", days_since_push=0)
    issue_1 = IssueMetadata(issue_url="url1", repo_full_name="org/r1", primary_language="Python", days_since_push=1)
    issue_5 = IssueMetadata(issue_url="url5", repo_full_name="org/r5", primary_language="Python", days_since_push=5)

    _, reason_0 = score_candidate_issue(profile, issue_0, compute_feature_vector(profile, issue_0))
    _, reason_1 = score_candidate_issue(profile, issue_1, compute_feature_vector(profile, issue_1))
    _, reason_5 = score_candidate_issue(profile, issue_5, compute_feature_vector(profile, issue_5))

    assert "repo updated today" in reason_0
    assert "repo updated 1 day ago" in reason_1
    assert "repo updated 5 days ago" in reason_5


def test_pyyaml_stop_list_scores_lower_than_bigquery_even_if_more_recent():
    """
    Test requirement 4:
    A candidate matching only pyyaml (ubiquitous stop-list library) must score
    lower than one matching google-cloud-bigquery (domain framework),
    even if the pyyaml repo was updated more recently.
    """
    profile = UserSkillProfile(
        username="data_dev",
        primary_languages={"Python": 1.0},
        frameworks=["pyyaml", "google-cloud-bigquery"],
    )

    # Candidate 1: matches pyyaml only, updated TODAY (0 days ago), 100 stars
    candidate_pyyaml = IssueMetadata(
        issue_url="https://api.github.com/repos/org/yaml-tool/issues/1",
        repo_full_name="org/yaml-tool",
        title="Fix yaml config parsing",
        body="Short description with reproduction.",
        primary_language="Python",
        labels=["good first issue"],
        stars=100,
        body_length=200,
        repo_frameworks=["pyyaml"],
        days_since_push=0,  # updated today (max recency)
    )

    # Candidate 2: matches google-cloud-bigquery, updated 45 days ago, 100 stars
    candidate_bigquery = IssueMetadata(
        issue_url="https://api.github.com/repos/org/gcp-tool/issues/2",
        repo_full_name="org/gcp-tool",
        title="Partition query optimization",
        body="Short description with reproduction.",
        primary_language="Python",
        labels=["good first issue"],
        stars=100,
        body_length=200,
        repo_frameworks=["google-cloud-bigquery"],
        days_since_push=45,  # updated 45 days ago (less recency)
    )

    ranked = rank_viable_issues(profile, [candidate_pyyaml, candidate_bigquery], top_k=2)

    assert len(ranked) == 2
    # The bigquery candidate must rank higher despite being older
    assert ranked[0].issue.repo_full_name == "org/gcp-tool"
    assert ranked[0].score > ranked[1].score

    # bigquery candidate has matching domain framework and reason
    assert "google-cloud-bigquery" in ranked[0].issue.matching_frameworks
    assert "uses google-cloud-bigquery like your repos" in ranked[0].one_line_reason
    assert "repo updated 45 days ago" in ranked[0].one_line_reason

    # pyyaml candidate must NOT match pyyaml (stop list)
    assert ranked[1].issue.matching_frameworks == []
    assert "pyyaml" not in ranked[1].one_line_reason
    assert "repo updated today" in ranked[1].one_line_reason


def test_star_bonus_and_penalty():
    """
    Test requirement 3:
    < 5 stars penalty (-0.15)
    5-20 stars penalty (-0.05)
    >= 50 stars bonus (+0.06)
    """
    profile = UserSkillProfile(username="dev", primary_languages={"Python": 1.0})
    issue_high = IssueMetadata(
        issue_url="https://api.github.com/repos/org/high/issues/1",
        repo_full_name="org/high",
        primary_language="Python",
        stars=100,
        body_length=200,
    )
    issue_mid = IssueMetadata(
        issue_url="https://api.github.com/repos/org/mid/issues/2",
        repo_full_name="org/mid",
        primary_language="Python",
        stars=12,
        body_length=200,
    )
    issue_low = IssueMetadata(
        issue_url="https://api.github.com/repos/org/low/issues/3",
        repo_full_name="org/low",
        primary_language="Python",
        stars=2,
        body_length=200,
    )
    f_high = compute_feature_vector(profile, issue_high)
    f_mid = compute_feature_vector(profile, issue_mid)
    f_low = compute_feature_vector(profile, issue_low)
    score_high, _ = score_candidate_issue(profile, issue_high, f_high)
    score_mid, _ = score_candidate_issue(profile, issue_mid, f_mid)
    score_low, _ = score_candidate_issue(profile, issue_low, f_low)

    assert score_high > score_mid
    assert score_mid > score_low
    assert score_high - score_low >= 0.20


def test_rank_viable_issues_ordering():
    profile = UserSkillProfile(
        username="python_dev",
        primary_languages={"Python": 1.0},
        topics=["fastapi", "backend"],
    )

    # Issue A: matches language and topic
    issue_a = IssueMetadata(
        issue_url="https://api.github.com/repos/tiangolo/fastapi/issues/1",
        repo_full_name="tiangolo/fastapi",
        title="Issue in Python backend",
        primary_language="Python",
        labels=["good first issue", "fastapi"],
        stars=70000,
        body_length=200,
    )

    # Issue B: unrelated language and topic
    issue_b = IssueMetadata(
        issue_url="https://api.github.com/repos/rust-lang/cargo/issues/2",
        repo_full_name="rust-lang/cargo",
        title="Issue in Rust",
        primary_language="Rust",
        labels=[],
        stars=12000,
        body_length=150,
    )

    ranked = rank_viable_issues(profile, [issue_b, issue_a], top_k=2)
    assert len(ranked) == 2
    assert ranked[0].issue.repo_full_name == "tiangolo/fastapi"
    assert ranked[0].score > ranked[1].score
    assert "Python" in ranked[0].one_line_reason


def test_inverse_frequency_rarer_is_stronger():
    """
    Test requirement 2:
    Weight a dependency match by how uncommon it is across the current candidate pool
    (inverse frequency), so a library present in most candidates adds almost nothing
    and a rare one like google-cloud-bigquery adds a lot.
    """
    profile = UserSkillProfile(
        username="dev",
        primary_languages={"Python": 1.0},
        frameworks=["fastapi", "google-cloud-bigquery"],
    )

    # 1 candidate with rare framework google-cloud-bigquery
    rare_cand = IssueMetadata(
        issue_url="url-rare",
        repo_full_name="org/rare",
        primary_language="Python",
        stars=100,
        body_length=200,
        repo_frameworks=["google-cloud-bigquery"],
    )

    # 9 candidates with common framework fastapi
    common_cands = [
        IssueMetadata(
            issue_url=f"url-common-{i}",
            repo_full_name=f"org/common-{i}",
            primary_language="Python",
            stars=100,
            body_length=200,
            repo_frameworks=["fastapi"],
        )
        for i in range(9)
    ]

    all_cands = [common_cands[0], rare_cand] + common_cands[1:]
    ranked = rank_viable_issues(profile, all_cands, top_k=10)

    # The rare candidate must be ranked #1
    assert ranked[0].issue.repo_full_name == "org/rare"
    assert "google-cloud-bigquery" in ranked[0].issue.matching_frameworks

    # Verify score difference: rare framework (rarity=1.0) bonus ~0.30 vs common framework (count=9/10, rarity ~0.11)
    rare_score = ranked[0].score
    common_score = ranked[1].score
    assert rare_score > common_score + 0.20
