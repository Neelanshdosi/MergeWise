#!/usr/bin/env python3
"""
MergeWise Live Smoke Script for Phase 3: Plan Agent & Repo Health
Calls /api/plan for pallets/click (or custom issue) and prints:
- llm_used & llm_error
- token_usage
- repo_health (pushed_at, contributing guide, median response, first-time PR merge rate)
- setup_command & test_command with file citations
- verified_files_to_edit
- steps & draft_claim_comment
"""
import argparse
import json
import sys
import httpx


def run_smoke_test(api_url: str, repo: str, issue_number: int):
    print("=" * 80)
    print(f"MergeWise Phase 3 Smoke Test: {repo}#{issue_number}")
    print(f"Target API Endpoint: {api_url}")
    print("=" * 80)

    payload = {
        "repo_full_name": repo,
        "issue_number": issue_number,
        "title": "Add support for custom shell completion script template",
        "body": "Look at src/click/shell_completion.py for details.",
        "labels": ["enhancement"],
        "force_refresh": True
    }

    try:
        response = httpx.post(api_url, json=payload, timeout=45.0)
    except httpx.ConnectError:
        print(f"\n[ERROR] Could not connect to backend at {api_url}.")
        print("Ensure uvicorn is running: python -m uvicorn app.main:app --port 8000")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Request failed: {e}")
        sys.exit(1)

    if response.status_code != 200:
        print(f"\n[ERROR] HTTP {response.status_code}: {response.text}")
        sys.exit(1)

    data = response.json()

    print("\n--- 1. LLM Status & Token Usage ---")
    print(f"LLM Used        : {data.get('llm_used')}")
    print(f"LLM Error       : {data.get('llm_error') or 'None (Success)'}")
    print(f"Token Usage     : {json.dumps(data.get('token_usage', {}))}")
    print(f"Latency         : {data.get('latency_ms')} ms")
    print(f"Tools Called    : {data.get('tools_called', [])}")

    print("\n--- 2. Grounded Commands & Citations ---")
    print(f"Setup Command   : {data.get('setup_command')}")
    print(f"Setup Citation  : [{data.get('setup_citation')}]")
    print(f"Test Command    : {data.get('test_command')}")
    print(f"Test Citation   : [{data.get('test_citation')}]")
    print(f"Verified Files  : {data.get('verified_files_to_edit', [])}")

    print("\n--- 3. Real Repository Health ---")
    health = data.get("repo_health", {})
    print(f"Repository      : {health.get('repo_full_name')}")
    print(f"Last Push       : {health.get('days_since_last_push_human')} (pushed_at: {health.get('pushed_at')})")
    print(f"Contributing    : {health.get('has_contributing_guide')} ({health.get('contributing_guide_path')})")
    print(f"Response Time   : {health.get('response_time_human')}")
    print(f"FT PR Merge Rate: {health.get('first_time_pr_merge_rate_human')}")
    print(f"Health Badge    : {health.get('overall_badge')}")
    print(f"API Errors      : {health.get('api_errors', {})}")

    print("\n--- 4. Effort Estimate ---")
    print(f"Difficulty      : {data.get('difficulty')}")
    print(f"Estimated Hours : {data.get('estimated_hours')}")
    print(f"Effort Reason   : {data.get('effort_reasoning')}")
    print(f"User Can Override: {data.get('user_can_override_effort')}")

    print("\n--- 5. Implementation Steps ---")
    for i, step in enumerate(data.get("steps", []), 1):
        print(f"  {i}. {step}")

    print("\n--- 6. Draft Claim Comment ---")
    print(data.get("draft_claim_comment"))

    print("\n" + "=" * 80)
    print("Smoke test complete.")
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MergeWise Phase 3 Smoke Test")
    parser.add_argument("--url", default="http://127.0.0.1:8000/api/plan", help="API Plan endpoint URL")
    parser.add_argument("--repo", default="pallets/click", help="GitHub repo 'owner/repo'")
    parser.add_argument("--issue", type=int, default=2700, help="Issue number")
    args = parser.parse_args()

    run_smoke_test(args.url, args.repo, args.issue)
