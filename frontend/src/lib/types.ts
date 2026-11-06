export interface UserProfileResponse {
  user_id: string;
  github_username: string | null;
  has_github_token: boolean;
  authorized_party: string | null;
  issuer: string | null;
  auth_status: string;
}

export interface BackendHealthResponse {
  status: string;
  service: string;
  environment: string;
  gemini_model_id: string;
}

export interface ColdStartQuestionnaire {
  languages: string[];
  frameworks: string[];
  interests: string[];
  hours_per_week: number;
  experience_level: string;
}

export interface UserSkillProfile {
  username: string;
  primary_languages: Record<string, number>;
  frameworks: string[];
  topics: string[];
  total_commits: number;
  total_prs: number;
  total_reviews: number;
  total_repos_contributed: number;
  activity_last_1m: number;
  activity_last_2m: number;
  activity_last_3m: number;
  is_cold_start: boolean;
  cold_start_answers?: ColdStartQuestionnaire;
}

export interface IssueMetadata {
  issue_url: string;
  repo_full_name: string;
  issue_number: number;
  title: string;
  body: string;
  primary_language?: string;
  labels: string[];
  stars: number;
  open_issues_count: number;
  body_length: number;
  created_at_epoch: number;
  html_url: string;
}

export interface CandidateFeatureVector {
  lang_match: number;
  lang_commit_share: number;
  domain_topic_overlap: number;
  text_cosine_sim: number;
  user_total_commits: number;
  user_total_prs: number;
  user_total_reviews: number;
  user_total_repos: number;
  user_act_1m: number;
  user_act_2m: number;
  user_act_3m: number;
  recency_weighted_activeness: number;
  repo_stars_log: number;
  issue_body_length_log: number;
  has_good_first_issue_label: number;
  has_help_wanted_label: number;
}

export interface ScoredIssueCandidate {
  issue: IssueMetadata;
  features: CandidateFeatureVector;
  score: number;
  one_line_reason: string;
  viability_verified: boolean;
  score_breakdown?: Record<string, number>;
}

export interface ResourceRateLimit {
  resource: string;
  remaining: number;
  limit: number;
  reset_epoch?: number | null;
  reset_time: string;
  is_limited: boolean;
}

export interface PipelineStats {
  queries_run: string[];
  candidates_fetched: number;
  passed_viability: number;
  rejected_by_reason: Record<string, number>;
  api_errors: number;
  relaxation_used: string | null;
  search_rate_limit?: ResourceRateLimit | null;
  core_rate_limit?: ResourceRateLimit | null;
  rate_limit_notice?: string | null;
  calls_made: number;
}

export interface RepoHealthData {
  repo_full_name: string;
  has_contributing_guide?: boolean;
  contributing_guide_path?: string | null;
  pushed_at?: string | null;
  days_since_last_push?: number | null;
  days_since_last_push_human?: string;
  median_response_time_hours?: number | null;
  response_time_human?: string;
  first_time_pr_merge_rate_pct?: number | null;
  first_time_pr_merge_rate_human?: string;
  sampled_issues_count?: number;
  sampled_prs_count?: number;
  overall_badge?: string;
  summary?: string;
  api_errors?: Record<string, string>;
}

export interface IssuePlanResponse {
  repo_full_name: string;
  issue_number: number;
  difficulty: string;
  estimated_hours: string;
  effort_reasoning: string;
  user_can_override_effort: boolean;
  setup_command: string;
  setup_citation: string;
  test_command: string;
  test_citation: string;
  verified_files_to_edit: string[];
  steps: string[];
  draft_claim_comment: string;
  repo_health: RepoHealthData;
  llm_used: boolean;
  llm_error: string | null;
  tools_called: string[];
  token_usage: {
    prompt_tokens: number;
    candidates_tokens: number;
    total_tokens: number;
  };
  cached: boolean;
}

export interface GeneratePlanRequest {
  repo_full_name: string;
  issue_number: number;
  title: string;
  body: string;
  labels: string[];
  override_effort?: string | null;
  force_refresh?: boolean;
}

export interface RecommendationsResponse {
  is_cold_start: boolean;
  profile?: UserSkillProfile;
  recommendations: ScoredIssueCandidate[];
  total_evaluated: number;
  total_viable: number;
  rejected_stats: Record<string, number>;
  pipeline_stats: PipelineStats;
  why_these_results?: string | null;
}

export type OutcomeType =
  | "attempted"
  | "pr_opened"
  | "merged"
  | "skipped"
  | "too_hard"
  | "abandoned";

export interface OutcomeRecord {
  user_id: string;
  repo_full_name: string;
  issue_number: number;
  issue_title: string;
  outcome: OutcomeType;
  is_positive: boolean;
  recorded_at: string;
  pr_url?: string | null;
  effort_label?: string | null;
  primary_language?: string | null;
  labels?: string[] | null;
  notes?: string | null;
}

export interface RecordOutcomeRequest {
  repo_full_name: string;
  issue_number: number;
  issue_title?: string;
  outcome: OutcomeType;
  pr_url?: string | null;
  effort_label?: string | null;
  primary_language?: string | null;
  labels?: string[] | null;
  notes?: string | null;
}
