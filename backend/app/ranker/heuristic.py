import logging
from typing import Dict, List

from mergewise_features import (
    UserSkillProfile,
    IssueMetadata,
    ScoredIssueCandidate,
    compute_feature_vector,
    score_candidate_issue,
)

logger = logging.getLogger("mergewise.ranker.heuristic")


def rank_viable_issues(
    profile: UserSkillProfile,
    candidates: List[IssueMetadata],
    top_k: int = 5,
    max_per_repo: int = 2,
) -> List[ScoredIssueCandidate]:
    """
    Ranks viable candidates using the shared PFIRec-aligned feature vector,
    heuristic scoring formula, and diversity constraint (at most max_per_repo per repo).
    """
    # Count occurrences of dependencies across candidate pool for inverse frequency weighting (rarer-is-stronger)
    dep_counts: Dict[str, int] = {}
    total_candidates = len(candidates)
    for c in candidates:
        seen_in_cand = set()
        for rf in c.repo_frameworks:
            norm_rf = rf.lower().strip().replace("_", "-")
            if norm_rf and norm_rf not in seen_in_cand:
                seen_in_cand.add(norm_rf)
                dep_counts[norm_rf] = dep_counts.get(norm_rf, 0) + 1

    scored_list: List[ScoredIssueCandidate] = []

    for issue in candidates:
        features = compute_feature_vector(profile, issue)
        score_res = score_candidate_issue(
            profile,
            issue,
            features,
            dep_counts=dep_counts,
            total_candidates=total_candidates,
        )
        score = score_res[0]
        reason = score_res[1]
        breakdown = getattr(score_res, "breakdown", None)

        scored_list.append(
            ScoredIssueCandidate(
                issue=issue,
                features=features,
                score=score,
                one_line_reason=reason,
                viability_verified=True,
                score_breakdown=breakdown,
            )
        )

    # Sort descending by match score
    scored_list.sort(key=lambda x: x.score, reverse=True)

    # Enforce repo diversity (at most max_per_repo per repo in top results)
    diversified: List[ScoredIssueCandidate] = []
    repo_counts: Dict[str, int] = {}

    for item in scored_list:
        repo = item.issue.repo_full_name
        if repo_counts.get(repo, 0) < max_per_repo:
            diversified.append(item)
            repo_counts[repo] = repo_counts.get(repo, 0) + 1
            if len(diversified) >= top_k:
                break

    return diversified
