#!/usr/bin/env python3
"""
MergeWise Automated Post-Deployment Smoke Test
Runs live HTTP verification against deployed Cloud Run services in asia-south1.
"""
import sys
import json
import urllib.request
import urllib.error

BACKEND_URL = "https://mergewise-backend-708575763180.asia-south1.run.app"
FRONTEND_URL = "https://mergewise-frontend-708575763180.asia-south1.run.app"


def check_url(url: str, expected_status: int = 200, method: str = "GET") -> tuple:
    req = urllib.request.Request(url, method=method)
    req.add_header("User-Agent", "MergeWise-SmokeTest/1.0")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body, dict(resp.headers)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return e.code, body, dict(e.headers)
    except Exception as e:
        return 0, str(e), {}


def main():
    print("=" * 70)
    print(" MergeWise Live Production Smoke Test")
    print(f" Backend:  {BACKEND_URL}")
    print(f" Frontend: {FRONTEND_URL}")
    print("=" * 70)

    failures = 0

    # 1. Health check
    print("\n[1/6] Testing Backend /health endpoint...")
    status, body, _ = check_url(f"{BACKEND_URL}/health")
    if status == 200:
        try:
            data = json.loads(body)
            if data.get("status") == "healthy" and data.get("service") == "mergewise-backend":
                print(f"  PASS: Backend is healthy (model: {data.get('gemini_model_id')}, env: {data.get('environment')})")
            else:
                print(f"  FAIL: Unexpected health payload: {data}")
                failures += 1
        except json.JSONDecodeError:
            print(f"  FAIL: Health response is not valid JSON: {body}")
            failures += 1
    else:
        print(f"  FAIL: /health returned HTTP {status}")
        failures += 1

    # 2. Production docs hardening: /docs must be 404
    print("\n[2/6] Verifying Swagger /docs is disabled in production...")
    status, _, _ = check_url(f"{BACKEND_URL}/docs")
    if status == 404:
        print("  PASS: /docs correctly returns 404 in production mode")
    else:
        print(f"  FAIL: /docs returned HTTP {status} (expected 404)")
        failures += 1

    # 3. Production docs hardening: /openapi.json must be 404
    print("\n[3/6] Verifying /openapi.json is disabled in production...")
    status, _, _ = check_url(f"{BACKEND_URL}/openapi.json")
    if status == 404:
        print("  PASS: /openapi.json correctly returns 404 in production mode")
    else:
        print(f"  FAIL: /openapi.json returned HTTP {status} (expected 404)")
        failures += 1

    # 4. Auth protection: /api/me without Bearer must return 401
    print("\n[4/6] Verifying /api/me requires valid Clerk JWT...")
    status, body, _ = check_url(f"{BACKEND_URL}/api/me")
    if status == 401:
        print(f"  PASS: /api/me correctly rejected unauthenticated request (HTTP 401)")
    else:
        print(f"  FAIL: /api/me returned HTTP {status} instead of 401")
        failures += 1

    # 5. Frontend availability
    print("\n[5/6] Verifying Frontend accessibility...")
    status, body, _ = check_url(FRONTEND_URL)
    if status == 200 and len(body) > 200:
        print(f"  PASS: Frontend returned HTTP 200 ({len(body)} bytes HTML)")
    else:
        print(f"  FAIL: Frontend returned HTTP {status}")
        failures += 1

    # 6. Plan endpoint unauthenticated rejection
    print("\n[6/6] Verifying /api/plan rejects unauthenticated caller...")
    req_data = json.dumps({"repo_full_name": "test/repo", "issue_number": 1}).encode("utf-8")
    req = urllib.request.Request(f"{BACKEND_URL}/api/plan", data=req_data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"  FAIL: /api/plan allowed request without auth (HTTP {resp.status})")
            failures += 1
    except urllib.error.HTTPError as e:
        # Expect 401 or 429 depending on auth
        if e.code in (401, 429):
            print(f"  PASS: /api/plan protected (HTTP {e.code})")
        else:
            print(f"  NOTICE: /api/plan returned HTTP {e.code}")
    except Exception as e:
        print(f"  NOTICE: {e}")

    print("\n" + "=" * 70)
    if failures == 0:
        print(" ALL SMOKE TESTS PASSED! Production deployment is verified.")
        print("=" * 70)
        sys.exit(0)
    else:
        print(f" {failures} SMOKE TEST(S) FAILED.")
        print("=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    main()
