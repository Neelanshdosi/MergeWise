from typing import Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field


class ViabilityRejectionReason(str, Enum):
    CLOSED = "ISSUE_CLOSED"
    ALREADY_ASSIGNED = "ALREADY_ASSIGNED"
    COMPETING_OPEN_PR = "COMPETING_OPEN_PR"
    CLAIMED_IN_COMMENTS = "CLAIMED_IN_COMMENTS"
    API_RATE_LIMIT = "API_RATE_LIMIT"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"


class ColdStartQuestionnaire(BaseModel):
    """Fallback questionnaire for developers with little public GitHub footprint."""
    languages: List[str] = Field(default_factory=list, description="e.g. ['TypeScript', 'Python']")
    frameworks: List[str] = Field(default_factory=list, description="e.g. ['React', 'FastAPI']")
    interests: List[str] = Field(default_factory=list, description="e.g. ['Developer Tools', 'CLI', 'Web']")
    hours_per_week: int = Field(default=5, ge=1, le=40)
    experience_level: str = Field(default="beginner", description="beginner, intermediate, advanced")


class UserSkillProfile(BaseModel):
    """Developer profile extracted from historical GitHub activity or cold start."""
    username: str
    primary_languages: Dict[str, float] = Field(default_factory=dict, description="Language name to proportion or commit weight")
    frameworks: List[str] = Field(default_factory=list, description="Extracted manifest dependencies")
    topics: List[str] = Field(default_factory=list, description="Topics of repos contributed to")
    total_commits: int = 0
    total_prs: int = 0
    total_reviews: int = 0
    total_repos_contributed: int = 0
    activity_last_1m: int = 0
    activity_last_2m: int = 0
    activity_last_3m: int = 0
    is_cold_start: bool = False
    cold_start_answers: Optional[ColdStartQuestionnaire] = None


class IssueMetadata(BaseModel):
    """Metadata of target issue to evaluate."""
    issue_url: str
    repo_full_name: str
    issue_number: int = 0
    title: str = ""
    body: str = ""
    primary_language: Optional[str] = None
    labels: List[str] = Field(default_factory=list)
    stars: int = 0
    open_issues_count: int = 0
    body_length: int = 0
    created_at_epoch: int = 0
    html_url: str = ""
    has_code_snippet: bool = False
    repo_topics: List[str] = Field(default_factory=list)
    days_since_push: Optional[int] = None
    maintainer_active_recent: bool = False
    matching_frameworks: List[str] = Field(default_factory=list)
    repo_frameworks: List[str] = Field(default_factory=list, description="Extracted manifest dependencies of candidate repo")


class CandidateFeatureVector(BaseModel):
    """
    Exact feature vector aligned with PFIRec (Xiao et al., ASE 2023).
    Shared between live ranking inference (backend) and offline evaluation (eval).
    """
    # 1. Language Familiarity
    lang_match: float = 0.0
    lang_commit_share: float = 0.0

    # 2. Domain & Content Preference
    domain_topic_overlap: float = 0.0
    text_cosine_sim: float = 0.0

    # 3. General OSS Experience
    user_total_commits: int = 0
    user_total_prs: int = 0
    user_total_reviews: int = 0
    user_total_repos: int = 0

    # 4. Activeness (weighted by recency)
    user_act_1m: int = 0
    user_act_2m: int = 0
    user_act_3m: int = 0
    recency_weighted_activeness: float = 0.0

    # 5. Issue & Repo Features
    repo_stars_log: float = 0.0
    issue_body_length_log: float = 0.0
    has_good_first_issue_label: int = 0
    has_help_wanted_label: int = 0

    def to_feature_list(self) -> List[float]:
        """Ordered float list for LightGBM inference."""
        return [
            self.lang_match,
            self.lang_commit_share,
            self.domain_topic_overlap,
            self.text_cosine_sim,
            float(self.user_total_commits),
            float(self.user_total_prs),
            float(self.user_total_reviews),
            float(self.user_total_repos),
            float(self.user_act_1m),
            float(self.user_act_2m),
            float(self.user_act_3m),
            self.recency_weighted_activeness,
            self.repo_stars_log,
            self.issue_body_length_log,
            float(self.has_good_first_issue_label),
            float(self.has_help_wanted_label),
        ]

    @classmethod
    def feature_names(cls) -> List[str]:
        return [
            "lang_match",
            "lang_commit_share",
            "domain_topic_overlap",
            "text_cosine_sim",
            "user_total_commits",
            "user_total_prs",
            "user_total_reviews",
            "user_total_repos",
            "user_act_1m",
            "user_act_2m",
            "user_act_3m",
            "recency_weighted_activeness",
            "repo_stars_log",
            "issue_body_length_log",
            "has_good_first_issue_label",
            "has_help_wanted_label",
        ]


class ScoredIssueCandidate(BaseModel):
    """An issue that passed live viability checks with calculated match score and explanation."""
    issue: IssueMetadata
    features: CandidateFeatureVector
    score: float
    one_line_reason: str
    viability_verified: bool = True
    score_breakdown: Optional[Dict[str, float]] = None


class ResourceRateLimit(BaseModel):
    resource: str = "core"  # "core" or "search"
    remaining: int = 5000
    limit: int = 5000
    reset_epoch: Optional[int] = None
    reset_time: str = ""
    is_limited: bool = False


class PipelineStats(BaseModel):
    """Execution telemetry of the issue recommendation and viability pipeline."""
    queries_run: List[str] = Field(default_factory=list)
    candidates_fetched: int = 0
    passed_viability: int = 0
    rejected_by_reason: Dict[str, int] = Field(default_factory=dict)
    api_errors: int = 0
    relaxation_used: Optional[str] = None
    search_rate_limit: Optional[ResourceRateLimit] = None
    core_rate_limit: Optional[ResourceRateLimit] = None
    rate_limit_notice: Optional[str] = None
    calls_made: int = 0
