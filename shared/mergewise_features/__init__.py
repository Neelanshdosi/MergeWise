"""Shared feature extraction package for MergeWise / OSS Match Agent."""
from .schemas import (
    CandidateFeatureVector,
    UserSkillProfile,
    IssueMetadata,
    ColdStartQuestionnaire,
    ViabilityRejectionReason,
    ScoredIssueCandidate,
    PipelineStats,
    ResourceRateLimit,
)
from .extractor import (
    compute_feature_vector,
    extract_frameworks_from_manifest,
    score_candidate_issue,
    DEV_DEPENDENCY_STOP_LIST,
    UBIQUITOUS_DEPENDENCY_STOP_LIST,
    is_stopped_dependency,
)

__all__ = [
    "CandidateFeatureVector",
    "UserSkillProfile",
    "IssueMetadata",
    "ColdStartQuestionnaire",
    "ViabilityRejectionReason",
    "ScoredIssueCandidate",
    "PipelineStats",
    "compute_feature_vector",
    "extract_frameworks_from_manifest",
    "score_candidate_issue",
    "DEV_DEPENDENCY_STOP_LIST",
    "UBIQUITOUS_DEPENDENCY_STOP_LIST",
    "is_stopped_dependency",
]
