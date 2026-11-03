from datetime import datetime, timezone, timedelta
from app.services.viability import check_issue_viability
from mergewise_features.schemas import ViabilityRejectionReason


def test_viable_issue_passes():
    issue = {
        "state": "open",
        "assignee": None,
        "assignees": [],
        "number": 42,
    }
    comments = [
        {
            "created_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
            "body": "Can anyone provide steps to reproduce this on macOS?",
            "user": {"login": "curious_dev"},
        }
    ]
    timeline = []

    result = check_issue_viability(issue, comments, timeline)
    assert result.is_viable is True
    assert result.rejection_reason is None


def test_closed_issue_rejected():
    issue = {
        "state": "closed",
        "assignee": None,
        "assignees": [],
    }
    result = check_issue_viability(issue)
    assert result.is_viable is False
    assert result.rejection_reason == ViabilityRejectionReason.CLOSED


def test_assigned_issue_rejected():
    issue_single = {
        "state": "open",
        "assignee": {"login": "contributor_1"},
        "assignees": [],
    }
    res_single = check_issue_viability(issue_single)
    assert res_single.is_viable is False
    assert res_single.rejection_reason == ViabilityRejectionReason.ALREADY_ASSIGNED

    issue_multiple = {
        "state": "open",
        "assignee": None,
        "assignees": [{"login": "contributor_2"}],
    }
    res_multi = check_issue_viability(issue_multiple)
    assert res_multi.is_viable is False
    assert res_multi.rejection_reason == ViabilityRejectionReason.ALREADY_ASSIGNED


def test_competing_open_pr_rejected():
    issue = {
        "state": "open",
        "assignee": None,
        "assignees": [],
    }
    timeline = [
        {
            "event": "cross-referenced",
            "source": {
                "issue": {
                    "number": 99,
                    "pull_request": {"url": "https://api.github.com/repos/foo/bar/pulls/99"},
                    "state": "open",
                }
            },
        }
    ]
    result = check_issue_viability(issue, timeline_events=timeline)
    assert result.is_viable is False
    assert result.rejection_reason == ViabilityRejectionReason.COMPETING_OPEN_PR
    assert "#99" in result.detail


def test_claimed_in_recent_comments_rejected():
    issue = {
        "state": "open",
        "assignee": None,
        "assignees": [],
    }
    recent_ts = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    comments = [
        {
            "created_at": recent_ts,
            "body": "Hi maintainers, I'll take this and work on a fix today!",
            "user": {"login": "eager_coder"},
        }
    ]
    result = check_issue_viability(issue, comments=comments)
    assert result.is_viable is False
    assert result.rejection_reason == ViabilityRejectionReason.CLAIMED_IN_COMMENTS
    assert "@eager_coder" in result.detail


def test_old_claim_comment_ignored():
    """Claims older than 14 days without assignment or PR are considered abandoned."""
    issue = {
        "state": "open",
        "assignee": None,
        "assignees": [],
    }
    old_ts = (datetime.now(timezone.utc) - timedelta(days=25)).isoformat()
    comments = [
        {
            "created_at": old_ts,
            "body": "Can I work on this?",
            "user": {"login": "abandoned_coder"},
        }
    ]
    result = check_issue_viability(issue, comments=comments, max_comment_age_days=14)
    assert result.is_viable is True
