# MergeWise — OSS Match Agent

A personalized open-source issue recommender that analyzes your GitHub footprint to build a skill profile, finds public open-source issues you can realistically finish, verifies live viability, and drafts an actionable starter plan with outcome memory.

---

## Architecture Overview

```mermaid
flowchart TD
    subgraph Client ["Frontend (Next.js 15 App Router)"]
        UI[Dashboard & Issue Plan Modal]
        ClerkClient[Clerk GitHub Auth]
    end

    subgraph GCP ["Google Cloud (Scale-to-Zero)"]
        subgraph CloudRun ["Cloud Run Services"]
            FrontRun[mergewise-frontend]
            BackRun[mergewise-backend / FastAPI]
        end

        subgraph Security ["Security & Auth Layer"]
            JWKS[Clerk JWKS / RS256 Verification]
            TokenFilter[Token Redacting Logger]
            ClerkBAPI[Clerk Backend API: OAuth Access Tokens]
        end

        subgraph AI_Engine ["AI & Match Engine"]
            SharedFeat["Shared Feature Package\n(mergewise-features)"]
            Gemini["Vertex AI Gemini 2.0 Flash\n(Tool Calling & Starter Plans)"]
            Ranker["LightGBM ML Ranker / Heuristics"]
        end

        subgraph Persistence ["State & Memory"]
            Firestore[Cloud Firestore: Profiles & Outcomes]
            BQ[BigQuery: GH Archive Evaluation Table]
        end
    end

    ClerkClient -->|GitHub Login read:user| FrontRun
    FrontRun -->|Bearer Clerk JWT| BackRun
    BackRun -->|RS256 iss/azp/exp Validation| JWKS
    BackRun -->|On-demand token lookup| ClerkBAPI
    BackRun --> SharedFeat
    BackRun --> Gemini
    BackRun --> Ranker
    BackRun --> Firestore
```

---

## Phase 1 Acceptance Status: COMPLETED

- [x] **Backend Skeleton**: FastAPI configured with restricted CORS and health check `/health`.
- [x] **Zero-Leak Token Redaction**: Custom `SensitiveDataRedactor` intercepts all logs to prevent GitHub tokens, Bearer strings, or Clerk keys from leaking into stdout/logs.
- [x] **Clerk JWT Verification**: Strict validation of `exp`, `iss` (Clerk instance), and `azp` (Authorized Party/Frontend origin).
- [x] **Clerk Backend GitHub Token Broker**: Verified against current Clerk Backend API (`/v1/users/{user_id}/oauth_access_tokens/oauth_github`).
- [x] **Shared Feature Core**: `shared/mergewise_features` package created for identical feature calculations across live serving and offline evaluation.
- [x] **Frontend**: Next.js App Router with Clerk GitHub login, rich glassmorphic dashboard, and live backend verification card.
- [x] **Automated Tests**: Unit tests for JWT validation, expired tokens, azp mismatch, endpoint auth, and token log redaction all passing (`pytest tests/ -v`).
- [x] **Cloud Run Infrastructure**: Dockerfiles for both services and deployment scripts (`deploy/setup_gcp.sh`, `deploy/deploy_cloudrun.sh`).
