import json
import math
import re
from typing import Dict, List, Optional, Set, Tuple
from .schemas import UserSkillProfile, IssueMetadata, CandidateFeatureVector


def extract_frameworks_from_manifest(filename: str, content: str) -> List[str]:
    """
    Parses manifest files (package.json, requirements.txt, go.mod, Cargo.toml)
    to extract key developer frameworks and libraries.
    """
    if not content:
        return []

    frameworks: Set[str] = set()
    fname = filename.lower()

    try:
        if fname.endswith("package.json"):
            data = json.loads(content)
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            # Curated popular frameworks/tools
            key_js_frameworks = {
                "react", "next", "vue", "nuxt", "svelte", "angular", "express",
                "fastify", "nest", "nestjs", "tailwind", "tailwindcss", "prisma",
                "drizzle-orm", "jest", "vitest", "playwright", "cypress", "graphql",
                "redux", "zustand", "trpc", "electron", "three", "react-native"
            }
            for dep in deps.keys():
                dep_clean = dep.lstrip("@").split("/")[0].lower()
                if dep_clean in key_js_frameworks or dep.lower() in key_js_frameworks:
                    frameworks.add(dep)

        elif fname.endswith("requirements.txt") or fname.endswith("pipfile"):
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                pkg_match = re.split(r"[><=~!;]", line)
                if pkg_match:
                    pkg_name = pkg_match[0].strip().lower()
                    if pkg_name:
                        frameworks.add(pkg_name)

        elif fname.endswith("pyproject.toml"):
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("#") or not line:
                    continue
                # Match lines like "pytest>=7.0", 'ruff', or pytest = "^7.0"
                m = re.match(r'^(?:["\']?)([a-zA-Z0-9_-]+)(?:["\']?\s*(?:[><=~!^;]|=[><=~!^;]?|\s*=|,|\s*$))', line)
                if m:
                    pkg_name = m.group(1).lower().replace("_", "-")
                    if pkg_name not in {"python", "tool", "project", "build-system", "version", "name", "description"}:
                        frameworks.add(pkg_name)

        elif fname.endswith("go.mod"):
            in_require = False
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("require ("):
                    in_require = True
                    continue
                if in_require and line == ")":
                    in_require = False
                    continue
                if (in_require or line.startswith("require ")) and line:
                    parts = line.replace("require ", "").split()
                    if parts:
                        mod = parts[0].split("/")[-1].lower()
                        frameworks.add(mod)

        elif fname.endswith("cargo.toml"):
            in_deps = False
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("[dependencies]") or line.startswith("[dev-dependencies]"):
                    in_deps = True
                    continue
                elif line.startswith("[") and line.endswith("]"):
                    in_deps = False
                elif in_deps and "=" in line:
                    crate = line.split("=")[0].strip().lower()
                    if crate:
                        frameworks.add(crate)
    except Exception:
        pass

    return sorted(list(frameworks))


# --------------------------------------------------------------------------
# CONFIGURATION CONSTANTS: Ubiquitous libraries stop-list
# Edit this set to add/remove dependencies that must NOT count toward
# framework/domain matching or appear in recommendation reasons.
# --------------------------------------------------------------------------
UBIQUITOUS_DEPENDENCY_STOP_LIST: Set[str] = {
    # Testing, linting, formatting & dev tools
    "pytest",
    "pytest-cov",
    "pytest_cov",
    "ruff",
    "black",
    "flake8",
    "mypy",
    "isort",
    "eslint",
    "prettier",
    "typescript",
    "jest",
    "tox",
    "coverage",
    "pre-commit",
    "pre_commit",
    # CLI, serialization, config & utilities
    "pyyaml",
    "yaml",
    "click",
    "rich",
    "typer",
    "python-dotenv",
    "dotenv",
    "pydantic",
    "attrs",
    "six",
    "tqdm",
    "requests",
    # Numerical & data ubiquitous
    "numpy",
    "pandas",
    # Packaging, build & distribution
    "wheel",
    "pip",
    "build",
    "twine",
    "setuptools",
}

# Alias for backwards-compatibility
DEV_DEPENDENCY_STOP_LIST = UBIQUITOUS_DEPENDENCY_STOP_LIST


def is_stopped_dependency(name: str) -> bool:
    """Returns True if dependency is in the ubiquitous stop-list or is a type stub."""
    if not name:
        return True
    clean = name.lower().strip()
    if clean.startswith("@") and "/" in clean:
        clean = clean.split("/", 1)[1]
    norm = clean.replace("_", "-")

    if clean in UBIQUITOUS_DEPENDENCY_STOP_LIST or norm in UBIQUITOUS_DEPENDENCY_STOP_LIST:
        return True

    # Common type-stub packages (types-*)
    if norm.startswith("types-") or norm.startswith("@types/"):
        return True

    return False


def find_matching_dependencies(user_frameworks: List[str], repo_frameworks: List[str]) -> List[str]:
    """
    Compares user dependency names to candidate repo manifest dependencies.
    Matches only when BOTH sides have the dependency in their manifests.
    Excludes ubiquitous dev tools, linters, and libraries defined in UBIQUITOUS_DEPENDENCY_STOP_LIST.
    """
    if not user_frameworks or not repo_frameworks:
        return []

    def normalize_name(name: str) -> str:
        clean = name.lower().strip()
        if clean.startswith("@") and "/" in clean:
            clean = clean.split("/", 1)[1]
        return clean.replace("_", "-")

    # Filter out stop-list dependencies
    valid_user_frameworks = [uf for uf in user_frameworks if not is_stopped_dependency(uf)]
    if not valid_user_frameworks:
        return []

    valid_repo_frameworks = [rf for rf in repo_frameworks if not is_stopped_dependency(rf)]
    if not valid_repo_frameworks:
        return []

    repo_dep_norm = {normalize_name(rf): rf for rf in valid_repo_frameworks if rf}
    repo_dep_exact = {rf.lower().strip(): rf for rf in valid_repo_frameworks if rf}

    matches: List[str] = []
    for uf in valid_user_frameworks:
        norm_u = normalize_name(uf)
        raw_u = uf.lower().strip()
        if norm_u in repo_dep_norm or raw_u in repo_dep_exact:
            if uf not in matches:
                matches.append(uf)
        else:
            # Check prefix/suffix alias for well-known libs (e.g. bigquery <-> google-cloud-bigquery)
            for r_norm, r_orig in repo_dep_norm.items():
                if len(norm_u) >= 4 and len(r_norm) >= 4 and (norm_u in r_norm or r_norm in norm_u):
                    if uf not in matches:
                        matches.append(uf)
                    break

    return sorted(matches)


class ScoreResult(tuple):
    """Subclass of 2-tuple (score, reason) providing .breakdown attribute."""
    def __new__(cls, score: float, reason: str, breakdown: dict):
        obj = super().__new__(cls, (score, reason))
        obj.score = score
        obj.reason = reason
        obj.breakdown = breakdown
        return obj


def compute_feature_vector(
    profile: UserSkillProfile,
    issue: IssueMetadata,
    text_cosine_sim: float = 0.0
) -> CandidateFeatureVector:
    """
    Computes candidate feature vector from user profile and issue metadata.
    Shared between live serving and BigQuery evaluation.
    """
    # 1. Language Familiarity
    issue_lang = (issue.primary_language or "").lower()
    lang_weights = {k.lower(): v for k, v in profile.primary_languages.items()}
    lang_commit_share = lang_weights.get(issue_lang, 0.0)
    lang_match = 1.0 if issue_lang and issue_lang in lang_weights else 0.0

    # Detect matching frameworks strictly by comparing candidate repo manifest dependencies to user profile
    issue.matching_frameworks = find_matching_dependencies(profile.frameworks, issue.repo_frameworks)

    # Detect code snippets in issue body
    issue.has_code_snippet = ("```" in issue.body or "`" in issue.body)

    # 2. Domain Topic & Framework Overlap (excluding stop-list dependencies)
    profile_tokens: Set[str] = {t.lower() for t in profile.topics}
    profile_tokens.update({
        f.lower() for f in profile.frameworks
        if not is_stopped_dependency(f)
    })

    issue_tokens: Set[str] = {lbl.lower() for lbl in issue.labels}
    issue_tokens.update([part.lower() for part in re.findall(r"[a-zA-Z0-9_-]+", issue.repo_full_name)])
    issue_tokens.update([t.lower() for t in issue.repo_topics])

    if profile_tokens and issue_tokens:
        overlap = len(profile_tokens.intersection(issue_tokens)) + len(issue.matching_frameworks)
        domain_topic_overlap = min(1.0, overlap / math.sqrt(len(profile_tokens) * max(1, len(issue_tokens))))
    else:
        domain_topic_overlap = 0.0

    # 3. Issue & Repo Features
    repo_stars_log = math.log1p(max(0, issue.stars))
    issue_body_length_log = math.log1p(max(0, issue.body_length))

    labels_lower = [l.lower() for l in issue.labels]
    has_gfi = 1 if any("good first issue" in l or "good-first-issue" in l for l in labels_lower) else 0
    has_hw = 1 if any("help wanted" in l or "help-wanted" in l for l in labels_lower) else 0

    # 4. Recency-weighted activeness
    recency_act = (
        3.0 * float(profile.activity_last_1m) +
        2.0 * float(profile.activity_last_2m) +
        1.0 * float(profile.activity_last_3m)
    ) / 6.0

    return CandidateFeatureVector(
        lang_match=lang_match,
        lang_commit_share=lang_commit_share,
        domain_topic_overlap=domain_topic_overlap,
        text_cosine_sim=text_cosine_sim,
        user_total_commits=profile.total_commits,
        user_total_prs=profile.total_prs,
        user_total_reviews=profile.total_reviews,
        user_total_repos=profile.total_repos_contributed,
        user_act_1m=profile.activity_last_1m,
        user_act_2m=profile.activity_last_2m,
        user_act_3m=profile.activity_last_3m,
        recency_weighted_activeness=recency_act,
        repo_stars_log=repo_stars_log,
        issue_body_length_log=issue_body_length_log,
        has_good_first_issue_label=has_gfi,
        has_help_wanted_label=has_hw,
    )


def score_candidate_issue(
    profile: UserSkillProfile,
    issue: IssueMetadata,
    features: CandidateFeatureVector,
    dep_counts: Optional[Dict[str, int]] = None,
    total_candidates: Optional[int] = None,
) -> ScoreResult:
    """
    PFIRec-aligned multi-factor ranker with score variance and specific truthful reasons.
    Produces discriminating scores across issues and returns detailed feature breakdown.
    Weights domain matches using inverse frequency across candidate pool (rarer-is-stronger).
    """
    # 1. Language familiarity component (0.0 to 0.35)
    lang_score = (features.lang_match * 0.20) + (features.lang_commit_share * 0.15)

    # 2. Domain, Framework & Topic overlap component (rarer-is-stronger inverse frequency)
    fw_bonus = 0.0
    if issue.matching_frameworks:
        for fw in issue.matching_frameworks:
            clean_fw = fw.lower().strip().replace("_", "-")
            if total_candidates and total_candidates > 1 and dep_counts:
                count = dep_counts.get(clean_fw, 1)
                rarity = max(0.05, (total_candidates - count) / (total_candidates - 1))
            else:
                rarity = 1.0
            fw_bonus += 0.30 * rarity
        fw_bonus = min(0.38, fw_bonus)

    topic_bonus = min(0.08, features.domain_topic_overlap * 0.12)
    domain_score = min(0.38, fw_bonus + topic_bonus)

    # 3. Label accessibility component (0.0 to 0.15)
    label_score = 0.0
    if features.has_good_first_issue_label:
        label_score += 0.10
    if features.has_help_wanted_label:
        label_score += 0.05

    # 4. Content clarity & scoping (0.0 to 0.12)
    content_score = 0.0
    if issue.has_code_snippet:
        content_score += 0.05
    if 100 <= issue.body_length <= 1600:
        content_score += 0.07
    elif 1601 <= issue.body_length <= 3500:
        content_score += 0.04
    elif issue.body_length > 3500:
        content_score += 0.02

    # 5. Repo background & maintainer health
    repo_score = 0.0
    # Real stars logarithmic contribution
    if issue.stars > 0:
        repo_score += min(0.06, math.log10(issue.stars + 1) * 0.015)

    # Star bonus and penalties:
    # >= 50 stars: +0.06 soft bonus
    # < 5 stars: -0.15 penalty
    # 5 to 20 stars: -0.05 penalty
    if issue.stars >= 50:
        repo_score += 0.06
    elif issue.stars < 5:
        repo_score -= 0.15
    elif issue.stars < 20:
        repo_score -= 0.05

    # Push recency
    if issue.days_since_push is not None:
        if issue.days_since_push <= 7:
            repo_score += 0.06
        elif issue.days_since_push <= 30:
            repo_score += 0.04
        elif issue.days_since_push <= 90:
            repo_score += 0.02

    # Total score calculation with natural variance
    raw_score = lang_score + domain_score + label_score + content_score + repo_score
    final_score = round(min(0.98, max(0.10, raw_score)), 3)

    breakdown = {
        "language_familiarity": round(lang_score, 3),
        "domain_framework_fit": round(domain_score, 3),
        "labels_accessibility": round(label_score, 3),
        "issue_clarity_scoping": round(content_score, 3),
        "repo_health_recency": round(repo_score, 3),
    }

    # Construct truthful, issue-specific explanation (Rules 1, 2, 3)
    reasons: List[str] = []

    # 1. Language match part
    if issue.primary_language:
        if features.lang_commit_share > 0:
            reasons.append(f"{issue.primary_language} repo ({round(features.lang_commit_share * 100)}% of your activity)")
        else:
            reasons.append(f"{issue.primary_language} repo")

    # 2. Framework match part (ONLY when both user and candidate repo manifest have the dependency)
    if issue.matching_frameworks:
        fw_display = ", ".join(issue.matching_frameworks[:2])
        reasons.append(f"uses {fw_display} like your repos")

    # 3. Issue type and scope: only say "bug" if issue has a bug label.
    # Otherwise describe from labels (docs, enhancement, maintenance, small feature).
    labels_lower = [l.lower() for l in issue.labels]
    has_bug = any("bug" in l or "defect" in l for l in labels_lower)
    has_doc = any("doc" in l or "documentation" in l for l in labels_lower)
    has_enhancement = any("enhancement" in l or "feature" in l for l in labels_lower)
    has_maint = any(m in l for m in ["maintenance", "chore", "refactor", "cleanup", "tech-debt", "dependencies"] for l in labels_lower)

    is_small_scoped = (20 <= issue.body_length < 800)
    has_code = issue.has_code_snippet

    if has_bug:
        type_str = "bug"
    elif has_doc:
        type_str = "docs"
    elif has_enhancement:
        type_str = "small feature" if is_small_scoped else "enhancement"
    elif has_maint:
        type_str = "maintenance"
    elif features.has_good_first_issue_label:
        type_str = "small feature" if is_small_scoped else "starter task"
    elif features.has_help_wanted_label:
        type_str = "enhancement"
    else:
        type_str = ""

    # Scope and code snippet formatting: drop "small scoped ... with code snippet" unless true
    if type_str:
        if is_small_scoped and has_code:
            reasons.append(f"small scoped {type_str} with code snippet")
        elif is_small_scoped:
            reasons.append(f"small scoped {type_str}")
        elif has_code:
            reasons.append(f"{type_str} with code snippet")
        else:
            reasons.append(type_str)
    else:
        if is_small_scoped and has_code:
            reasons.append("small scoped task with code snippet")
        elif is_small_scoped:
            reasons.append("small scoped task")
        elif has_code:
            reasons.append("task with code snippet")

    # 4. Repo updated recency: "repo updated today" for 0 days, "1 day ago", then "N days ago"
    if issue.days_since_push is not None:
        if issue.days_since_push == 0:
            reasons.append("repo updated today")
        elif issue.days_since_push == 1:
            reasons.append("repo updated 1 day ago")
        else:
            reasons.append(f"repo updated {issue.days_since_push} days ago")

    # 5. Stars (only if >= 50)
    if issue.stars >= 50:
        reasons.append(f"{issue.stars:,} stars")

    one_line_reason = "; ".join(reasons) if reasons else "Viable open issue with clear specifications."
    return ScoreResult(final_score, one_line_reason, breakdown)
