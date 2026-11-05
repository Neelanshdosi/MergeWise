"""
Phase 4: Outcomes Router
POST   /api/outcomes            - Record a user outcome for an issue
GET    /api/outcomes            - List recent outcomes for the authenticated user
GET    /api/outcomes/{repo}/{issue_number} - Get outcome for a specific issue
DELETE /api/outcomes/{repo}/{issue_number} - Remove an outcome record
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from ..auth.dependencies import AuthenticatedUser, get_current_user
from ..services.memory import (
    record_outcome,
    get_user_outcomes,
    get_outcome_for_issue,
    delete_outcome,
    VALID_OUTCOMES,
    OutcomeType,
)

logger = logging.getLogger("mergewise.routers.outcomes")
router = APIRouter(prefix="/api/outcomes", tags=["Outcomes"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class RecordOutcomeRequest(BaseModel):
    repo_full_name: str = Field(..., description="owner/repo format")
    issue_number: int = Field(..., ge=1, description="GitHub issue number")
    issue_title: str = Field(default="", max_length=512)
    outcome: str = Field(
        ...,
        description=(
            f"One of: {', '.join(sorted(VALID_OUTCOMES))}. "
            "Use 'attempted' when you've started work, 'pr_opened' once a PR exists, "
            "'merged' when your PR lands, 'skipped' or 'too_hard' to dismiss."
        ),
    )
    pr_url: Optional[str] = Field(default=None, max_length=512)
    effort_label: Optional[str] = Field(default=None, max_length=64)
    primary_language: Optional[str] = Field(default=None, max_length=64)
    labels: Optional[List[str]] = Field(default=None, max_length=20)
    notes: Optional[str] = Field(default=None, max_length=500)


class OutcomeRecord(BaseModel):
    user_id: str
    repo_full_name: str
    issue_number: int
    issue_title: str = ""
    outcome: str
    is_positive: bool
    recorded_at: str
    pr_url: Optional[str] = None
    effort_label: Optional[str] = None
    primary_language: Optional[str] = None
    labels: Optional[List[str]] = None
    notes: Optional[str] = None


class RecordOutcomeResponse(BaseModel):
    success: bool
    message: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=RecordOutcomeResponse, status_code=status.HTTP_201_CREATED)
async def record_issue_outcome(
    req: RecordOutcomeRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> RecordOutcomeResponse:
    """
    Records a user's outcome for a specific GitHub issue.
    Valid outcomes: attempted, pr_opened, merged, skipped, too_hard, abandoned.
    Idempotent: calling again with the same issue merges/overwrites the record.
    """
    if "/" not in req.repo_full_name or req.repo_full_name.count("/") != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="repo_full_name must be in 'owner/repo' format",
        )

    if req.outcome not in VALID_OUTCOMES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid outcome '{req.outcome}'. Valid values: {sorted(VALID_OUTCOMES)}",
        )

    success = await record_outcome(
        user_id=user.user_id,
        repo_full_name=req.repo_full_name,
        issue_number=req.issue_number,
        issue_title=req.issue_title,
        outcome=req.outcome,
        pr_url=req.pr_url,
        effort_label=req.effort_label,
        primary_language=req.primary_language,
        labels=req.labels,
        notes=req.notes,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to record outcome. Please try again.",
        )

    return RecordOutcomeResponse(
        success=True,
        message=f"Outcome '{req.outcome}' recorded for {req.repo_full_name}#{req.issue_number}",
    )


@router.get("", response_model=List[OutcomeRecord])
async def list_outcomes(
    user: AuthenticatedUser = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100, description="Number of outcomes to return"),
    outcome_filter: Optional[str] = Query(
        default=None,
        alias="outcome",
        description=f"Filter by outcome type. One of: {', '.join(sorted(VALID_OUTCOMES))}",
    ),
) -> List[OutcomeRecord]:
    """
    Lists recent outcomes for the authenticated user, newest first.
    Optionally filtered by outcome type.
    """
    if outcome_filter and outcome_filter not in VALID_OUTCOMES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid outcome filter '{outcome_filter}'. Valid values: {sorted(VALID_OUTCOMES)}",
        )

    outcomes = await get_user_outcomes(
        user_id=user.user_id,
        limit=limit,
        outcome_filter=outcome_filter,
    )
    return [OutcomeRecord(**o) for o in outcomes]


@router.get("/{owner}/{repo}/{issue_number}", response_model=Optional[OutcomeRecord])
async def get_issue_outcome(
    owner: str = Path(..., min_length=1, max_length=100),
    repo: str = Path(..., min_length=1, max_length=100),
    issue_number: int = Path(..., ge=1),
    user: AuthenticatedUser = Depends(get_current_user),
) -> Optional[OutcomeRecord]:
    """
    Returns the recorded outcome for a specific issue, or 404 if none.
    """
    repo_full_name = f"{owner}/{repo}"
    outcome = await get_outcome_for_issue(
        user_id=user.user_id,
        repo_full_name=repo_full_name,
        issue_number=issue_number,
    )
    if outcome is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No outcome recorded for {repo_full_name}#{issue_number}",
        )
    return OutcomeRecord(**outcome)


@router.delete(
    "/{owner}/{repo}/{issue_number}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_issue_outcome(
    owner: str = Path(..., min_length=1, max_length=100),
    repo: str = Path(..., min_length=1, max_length=100),
    issue_number: int = Path(..., ge=1),
    user: AuthenticatedUser = Depends(get_current_user),
) -> None:
    """
    Removes the recorded outcome for a specific issue.
    Returns 204 No Content on success, 404 if no record exists.
    """
    repo_full_name = f"{owner}/{repo}"

    # Confirm it exists before deleting
    existing = await get_outcome_for_issue(
        user_id=user.user_id,
        repo_full_name=repo_full_name,
        issue_number=issue_number,
    )
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No outcome recorded for {repo_full_name}#{issue_number}",
        )

    success = await delete_outcome(
        user_id=user.user_id,
        repo_full_name=repo_full_name,
        issue_number=issue_number,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to delete outcome. Please try again.",
        )

