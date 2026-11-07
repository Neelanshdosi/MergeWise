# MergeWise Post-Deploy Smoke Checklist

This checklist verifies the operational readiness of MergeWise microservices on Google Cloud Run (`asia-south1`) following any production deployment.

---

## 1. Automated Smoke Test Script

Run the automated verification suite directly against live Cloud Run services:

```bash
python deploy/smoke_test.py
```

---

## 2. Manual Verification Checklist

### A. Backend Health & Production Security
- [ ] **Health Probe**:
  ```bash
  curl -i https://mergewise-backend-708575763180.asia-south1.run.app/health
  ```
  - **Expected Status**: `HTTP/2 200`
  - **Expected Payload**:
    ```json
    {
      "status": "healthy",
      "service": "mergewise-backend",
      "environment": "production",
      "gemini_model_id": "gemini-3.8-flash"
    }
    ```

- [ ] **Production Documentation Hardening**:
  ```bash
  curl -s -o /dev/null -w "%{http_code}\n" https://mergewise-backend-708575763180.asia-south1.run.app/docs
  curl -s -o /dev/null -w "%{http_code}\n" https://mergewise-backend-708575763180.asia-south1.run.app/redoc
  curl -s -o /dev/null -w "%{http_code}\n" https://mergewise-backend-708575763180.asia-south1.run.app/openapi.json
  ```
  - **Expected Status**: `404` for all three endpoints when `ENVIRONMENT=production`.

- [ ] **Unauthenticated Protection**:
  ```bash
  curl -i https://mergewise-backend-708575763180.asia-south1.run.app/api/me
  ```
  - **Expected Status**: `HTTP/2 401 Unauthorized`
  - **Expected Payload**: `{"detail": "Missing Authorization header"}`

---

### B. Distributed Rate Limiting & Quotas (Firestore-Backed)
- [ ] **Recommendations Rate Limit**:
  - Exceeding `RATE_LIMIT_RECOMMENDATIONS_PER_MINUTE` (default: 10/min) returns `HTTP 429 Too Many Requests`.
  - Response includes `Retry-After: <seconds>` header.
  - Detail message specifies when the counter resets: `"Resets at <ISO-timestamp> (in <seconds>s)"`.
- [ ] **Gemini Plan Rate Limit**:
  - Exceeding `RATE_LIMIT_PLAN_PER_MINUTE` (default: 5/min) returns `HTTP 429`.
  - Exceeding `GEMINI_USER_DAILY_CAP` (default: 20/day) returns `HTTP 429` with daily reset notice.
  - Exceeding `GEMINI_GLOBAL_DAILY_CAP` (default: 500/day) returns `HTTP 429` with global quota notice.
- [ ] **Firestore Persistence**:
  - Verify documents are recorded in Firestore Native mode under `users/{user_id}/rate_limits/` and `rate_limits/`.

---

### C. Frontend Service Verification
- [ ] **HTTP 200 Response**:
  ```bash
  curl -i https://mergewise-frontend-708575763180.asia-south1.run.app
  ```
  - **Expected Status**: `HTTP/2 200`
- [ ] **Next.js & Clerk Script Initialization**:
  - Page loads HTML skeleton with Clerk SDK initialization.
  - No client-side script errors in browser console.

---

### D. End-to-End User Flow
1. [ ] **Sign-In**: Visit `https://mergewise-frontend-708575763180.asia-south1.run.app` in browser. Click **Sign in with GitHub**.
2. [ ] **Profile Ingestion**: Verify dashboard renders user's GitHub avatar, primary languages, and experience level.
3. [ ] **Viable Recommendations**: Verify 5 issue cards appear with:
   - Green "Viable" badge
   - "Why viable" verification (no assignee, open state, no competing PR)
   - Estimated fit score
4. [ ] **Implementation Plan Generation**:
   - Click **Generate Implementation Plan** on an issue.
   - Verify Gemini agent returns:
     - Cited setup command
     - Cited test command
     - Verified file paths
     - Implementation steps
     - Draft claim comment
5. [ ] **Outcome Recording**:
   - Click "Attempted" or "Too Hard".
   - Confirm status toast appears and preference persists.

---

### E. Cloud Run Operational Constraints
- [ ] **Max Instances**:
  ```bash
  gcloud run services describe mergewise-backend --region=asia-south1 --format="value(spec.template.metadata.annotations['autoscaling.knative.dev/maxScale'])"
  gcloud run services describe mergewise-frontend --region=asia-south1 --format="value(spec.template.metadata.annotations['autoscaling.knative.dev/maxScale'])"
  ```
  - **Expected Value**: `3` for both services.
- [ ] **Scale to Zero**:
  - When idle, container instance counts drop to 0.
