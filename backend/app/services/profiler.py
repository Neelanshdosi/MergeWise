import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from mergewise_features.schemas import UserSkillProfile, ColdStartQuestionnaire
from mergewise_features.extractor import extract_frameworks_from_manifest
from .github import GitHubClient

logger = logging.getLogger("mergewise.profiler")


async def build_user_profile(
    client: GitHubClient,
    username: str,
    cold_start_answers: Optional[ColdStartQuestionnaire] = None,
) -> UserSkillProfile:
    """
    Builds a developer skill profile by analyzing:
    1. Language distributions weighted by recency.
    2. Manifest dependencies (package.json, requirements.txt, go.mod, Cargo.toml).
    3. Activity over 1, 2, and 3 months from contribution events.
    4. Applies cold-start questionnaire if historical activity is insufficient.
    """
    profile = UserSkillProfile(username=username)

    try:
        repos = await client.get_user_repos(username, max_repos=15)
    except Exception as e:
        logger.error(f"Failed to fetch repositories for {username}: {e}")
        repos = []

    try:
        events = await client.get_user_events(username)
    except Exception as e:
        logger.error(f"Failed to fetch user events for {username}: {e}")
        events = []

    # 1. Activity buckets (last 1m, 2m, 3m)
    now = datetime.now(timezone.utc)
    m1_cutoff = now - timedelta(days=30)
    m2_cutoff = now - timedelta(days=60)
    m3_cutoff = now - timedelta(days=90)

    act_1m = 0
    act_2m = 0
    act_3m = 0
    total_commits = 0
    total_prs = 0

    for ev in events:
        created_str = ev.get("created_at")
        if not created_str:
            continue
        try:
            ev_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
        except Exception:
            continue

        ev_type = ev.get("type")
        if ev_type == "PushEvent":
            commits = ev.get("payload", {}).get("commits", [])
            total_commits += len(commits)
        elif ev_type == "PullRequestEvent":
            total_prs += 1

        if ev_dt >= m1_cutoff:
            act_1m += 1
        elif ev_dt >= m2_cutoff:
            act_2m += 1
        elif ev_dt >= m3_cutoff:
            act_3m += 1

    profile.activity_last_1m = act_1m
    profile.activity_last_2m = act_2m
    profile.activity_last_3m = act_3m
    profile.total_commits = total_commits
    profile.total_prs = total_prs
    profile.total_repos_contributed = len(repos)

    # 2. Extract Languages (weighted by repo recency and stars)
    lang_counts: Dict[str, float] = {}
    frameworks: List[str] = []
    topics: List[str] = []

    for idx, repo in enumerate(repos):
        lang = repo.get("language")
        recency_weight = 1.0 / (1.0 + 0.1 * idx)  # higher weight for most recently pushed repos

        if lang:
            lang_clean = lang.strip()
            lang_counts[lang_clean] = lang_counts.get(lang_clean, 0.0) + (10.0 * recency_weight)

        # Collect topics
        repo_topics = repo.get("topics") or []
        for t in repo_topics:
            if t not in topics:
                topics.append(t)

        # Inspect manifest files on the top 5 most recently updated repositories
        if idx < 5:
            full_name = repo.get("full_name")
            if full_name:
                manifest_files = [
                    "package.json",
                    "requirements.txt",
                    "go.mod",
                    "Cargo.toml",
                ]
                for mf in manifest_files:
                    content = await client.get_file_content(full_name, mf)
                    if content:
                        extracted = extract_frameworks_from_manifest(mf, content)
                        for fw in extracted:
                            if fw not in frameworks:
                                frameworks.append(fw)

    # Normalize language proportions
    total_lang_weight = sum(lang_counts.values())
    if total_lang_weight > 0:
        profile.primary_languages = {
            lang: round(weight / total_lang_weight, 3)
            for lang, weight in sorted(lang_counts.items(), key=lambda x: x[1], reverse=True)
        }

    profile.frameworks = frameworks
    profile.topics = topics

    # 3. Cold Start Detection (< 5 commits and no active repos)
    if profile.total_repos_contributed == 0 and profile.total_commits < 5:
        profile.is_cold_start = True

    # 4. Merge Cold-Start Answers if provided
    if cold_start_answers:
        profile.cold_start_answers = cold_start_answers
        for lang in cold_start_answers.languages:
            if lang not in profile.primary_languages:
                profile.primary_languages[lang] = 0.5
        for fw in cold_start_answers.frameworks:
            if fw not in profile.frameworks:
                profile.frameworks.append(fw)
        for interest in cold_start_answers.interests:
            if interest not in profile.topics:
                profile.topics.append(interest)
        profile.is_cold_start = False

    return profile
