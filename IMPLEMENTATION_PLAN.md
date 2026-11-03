# OSS Match Agent — Implementation Plan & Architecture

A personalized open-source issue recommender that matches developers to viable issues based on their GitHub skill profile, live issue viability, maintainer responsiveness, and past outcome memory.

---

## 1. Repository Structure (Updated with Shared Features Package)

```
MergeWise/
├── .github/
│   └── workflows/              # CI/CD deployment pipelines (Cloud Run)
├── shared/                     # Shared single-source-of-truth feature extraction
│   ├── pyproject.toml          # Shared package definition
│   └── mergewise_features/
│       ├── __init__.py
│       ├── extractor.py        # Exact feature calculations (content, lang, domain, activeness)
│       └── schemas.py          # Pydantic & dataclass feature vectors
├── backend/                    # Python FastAPI service
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py             # FastAPI entrypoint, restricted CORS & token-redacting logging
│   │   ├── config.py           # Pydantic Settings (GEMINI_MODEL_ID, CLERK_*, etc.)
│   │   ├── auth/
│   │   │   ├── clerk.py        # Clerk JWKS session verification (iss, azp, exp) & GitHub token retrieval
│   │   │   └── dependencies.py # Current authenticated user dependency
│   │   ├── services/
│   │   │   ├── github.py       # GitHub REST/GraphQL client with aggressive caching (diskcache/ttl)
│   │   │   ├── profiler.py     # Skill profile builder (commits, PRs, manifest parsing)
│   │   │   ├── viability.py    # Live issue check (unassigned, PR links, competitor comments)
│   │   │   ├── health.py       # Repo responsiveness & first-time contributor merge rate
│   │   │   ├── memory.py       # Firestore profile & outcome tracking
│   │   │   └── rag.py          # Minimal in-memory/Firestore RAG for CONTRIBUTING/README
│   │   ├── agent/
│   │   │   ├── gemini.py       # Vertex AI Gemini Flash tool-calling orchestration
│   │   │   ├── tools.py        # Registered agent tools
│   │   │   └── prompts.py      # System prompts (effort estimation, starter plan)
│   │   ├── ranker/
│   │   │   ├── heuristic.py    # Baseline scoring (Phase 2)
│   │   │   └── ml_ranker.py    # LightGBM LambdaMART inference using mergewise_features
│   │   └── routers/
│   │       ├── auth.py         # /api/me (verify user & token access)
│   │       ├── profile.py      # /api/profile (fetch/trigger profile build)
│   │       ├── recommendations.py # /api/recommendations (search, filter, viability)
│   │       ├── plan.py         # /api/plan (generate plan & claim comment)
│   │       └── outcomes.py     # /api/outcomes (save attempted, skipped, merged, etc.)
│   ├── tests/
│   │   ├── test_auth.py        # JWT verification (iss, azp, exp) edge cases
│   │   ├── test_logging_security.py # Test asserting GitHub tokens never appear in logs
│   │   ├── test_viability.py   # Issue status & competitor comment parsing
│   │   └── test_ranking.py     # Feature extraction & scoring tests
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── frontend/                   # Next.js App Router (TypeScript + Vanilla CSS)
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx      # ClerkProvider, font, theme provider
│   │   │   ├── page.tsx        # Landing / Dashboard view
│   │   │   ├── sign-in/[[...sign-in]]/page.tsx
│   │   │   ├── onboarding/     # Cold-start questionnaire for new devs
│   │   │   └── issue/[id]/     # Deep-dive starter plan & interactive checklist
│   │   ├── components/
│   │   │   ├── Navbar.tsx      # UserButton, status, theme toggle
│   │   │   ├── ProfileSummary.tsx # Visual skill radar/pills
│   │   │   ├── IssueCard.tsx   # Verified badge, viability tags, effort estimate
│   │   │   ├── PlanModal.tsx   # Step-by-step guidance, draft comment, test commands
│   │   │   └── OutcomeButtons.tsx # "Attempted", "Skipped", "Too Hard", "PR Opened"
│   │   ├── lib/
│   │   │   ├── api.ts          # Authenticated fetch wrapper passing Clerk JWT
│   │   │   └── types.ts        # Shared TypeScript interfaces
│   │   └── styles/
│   │       └── globals.css
│   ├── Dockerfile
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.js
│   └── .env.example
├── eval/                       # BigQuery GH Archive evaluation pipeline
│   ├── extract_bq.py           # Dry-run + max_bytes_billed extract into custom dataset (IssuesEvent & PullRequestEvent)
│   ├── feature_extraction.py   # Uses shared mergewise_features; computes user history strictly prior to issue date
│   ├── train_lightgbm.py       # Time-ordered split training + evaluation (P@5, Recall@K)
│   ├── evaluate_baselines.py   # Benchmark vs Random Good-First-Issue & Label-only baselines
│   └── LABEL_NOISE_ANALYSIS.md # Documentation of label noise from PR-to-issue linking heuristics
├── deploy/                     # Deployment scripts & GCP setup guides
│   ├── setup_gcp.sh            # Enable APIs, create service accounts & budget alerts
│   └── deploy_cloudrun.sh      # Container build & Cloud Run deploy commands
└── README.md
```

---

## 2. Refined Plan & User Guardrails

1. **BigQuery Safe Extraction**:
   - Every query sets `dry_run=True` to compute estimated bytes before execution.
   - Enforce `maximum_bytes_billed` (capped at 5 GB scan per query).
   - Extract historical data once from a focused time window (only `IssuesEvent` and `PullRequestEvent`) into a dedicated personal BigQuery dataset `mergewise_eval`.
   - All subsequent feature engineering runs locally or on the small dedicated table.
2. **Shared Features Package (`shared/mergewise_features`)**:
   - Both `backend/app/ranker` and `eval/feature_extraction.py` import the identical feature definition library to prevent training/serving skew.
3. **Evaluation Leakage Prevention & Label Noise**:
   - All user historical activities (PRs, commits, reviews) are computed strictly *before* `issue.created_at`.
   - Document explicit label noise nuances (unlinked PRs, merged without keyword, multi-issue PRs) in `eval/LABEL_NOISE_ANALYSIS.md`.
4. **Vertex AI Gemini Config**:
   - Model ID stored in `GEMINI_MODEL_ID` environment variable (defaults to `gemini-2.0-flash` or `gemini-1.5-flash-002` depending on region, e.g. `us-central1`).
5. **Phase 1 Auth Security & Token Guardrails**:
   - Clerk JWT strictly validates `exp`, `iss` (Clerk issuer domain), and `azp` (Authorized Party / frontend origin).
   - CORS middleware restricted explicitly to `FRONTEND_URL`.
   - Custom logging filter and sanitization ensures `gho_*`, `ghp_*`, and `Bearer *` patterns are masked in all backend logs. Automated test in `test_logging_security.py` asserts zero leakage.
   - Clerk `GET /v1/users/{user_id}/oauth_access_tokens/oauth_github` endpoint verified against Clerk API docs.

---

## 3. Phase 1 Acceptance Criteria

1. Backend FastAPI initialized with CORS restricted to frontend origin.
2. JWT verification module validating `exp`, `iss`, and `azp` against Clerk JWKS.
3. Sensitive log filter masking GitHub tokens and authorization headers.
4. Unit tests covering:
   - Valid JWT token verification
   - Expired token rejection
   - Invalid `iss` and invalid `azp` rejection
   - Redaction test confirming raw tokens never appear in application logs
5. Next.js 14/15 frontend configured with Clerk GitHub login button.
6. Frontend authenticated request to `/api/me` displaying the user's GitHub username and session verification status.
7. Dockerfiles for both frontend and backend configured for Cloud Run scale-to-zero.
8. Manual checklist provided for Clerk dashboard, GCP APIs, IAM roles, and secrets.
