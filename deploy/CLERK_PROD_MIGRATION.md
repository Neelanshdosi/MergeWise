# Clerk Development to Production Migration Guide

This document specifies exactly what configuration and infrastructure changes occur when transitioning MergeWise from a Clerk Development Instance to a Clerk Production Instance.

---

## 1. Domain & DNS Configuration

| Component | Development Instance | Production Instance |
| :--- | :--- | :--- |
| **Issuer URL (`CLERK_ISSUER`)** | `https://mutual-panther-6595.clerk.accounts.dev` | `https://clerk.yourdomain.com` (custom domain) or `https://accounts.yourdomain.com` |
| **JWKS Endpoint (`CLERK_JWKS_URL`)** | `https://mutual-panther-6595.clerk.accounts.dev/.well-known/jwks.json` | `https://clerk.yourdomain.com/.well-known/jwks.json` |
| **Frontend Origin (`FRONTEND_URL`)** | `http://localhost:3000` / `http://localhost:3005` | `https://mergewise-frontend-708575763180.asia-south1.run.app` or `https://mergewise.yourdomain.com` |
| **Authorized Parties (`azp` claim)** | `["http://localhost:3000", "http://localhost:3005"]` | `["https://mergewise-frontend-708575763180.asia-south1.run.app"]` |
| **DNS CNAME Records** | None required (hosted on `accounts.dev`) | 3x CNAME records added to domain registrar (Clerk SSL certificates, frontend API proxy, and email SPF/DKIM) |

---

## 2. API Keys & Secrets

| Key | Development Instance | Production Instance | Storage Location |
| :--- | :--- | :--- | :--- |
| **Publishable Key (`CLERK_PUBLISHABLE_KEY`)** | `pk_test_bXV0dWFsLXBhbnRoZXItNjU5NS...` | `pk_live_...` | Frontend build arg & Cloud Build substitution |
| **Secret Key (`CLERK_SECRET_KEY`)** | `sk_test_EyLy9lJOtL...` | `sk_live_...` | **GCP Secret Manager** (`projects/oss-match/secrets/clerk-secret-key/versions/latest`) |

> [!CAUTION]
> Never commit `sk_live_...` to git or bake it into container images. It must be stored strictly in Secret Manager and mounted as an environment secret in Cloud Run.

---

## 3. GitHub OAuth Application Configuration

In Clerk Development instances, Clerk uses a shared pre-configured development OAuth app. For Production instances, you **must register your own custom GitHub OAuth Application**.

### Steps to register:
1. Navigate to **GitHub Settings** -> **Developer Settings** -> **OAuth Apps** -> **New OAuth App**:
   - **Application Name**: `MergeWise`
   - **Homepage URL**: `https://mergewise-frontend-708575763180.asia-south1.run.app` (or custom domain)
   - **Authorization Callback URL**:
     - Standard: `https://clerk.yourdomain.com/v1/oauth_callback`
     - Or Clerk production domain: `https://<prod-instance-id>.clerk.accounts.dev/v1/oauth_callback`
2. Generate a new **Client Secret** in GitHub.
3. In Clerk Dashboard:
   - Navigate to **Configure** -> **SSO Connections** -> **Social Connections** -> **GitHub**.
   - Toggle **Use custom credentials**.
   - Paste the GitHub **Client ID** and **Client Secret**.
   - Scopes: Select `read:user` and optionally `repo` (if reading private repositories or issue tracking).
   - Save changes.

---

## 4. Session & Cookie Policy Differences

1. **Strict SameSite / Secure Cookies**:
   - Development allows HTTP on `localhost` with relaxed cookie settings.
   - Production enforces `Secure`, `HttpOnly`, and `SameSite=Lax` / `None` depending on subdomains.
2. **Session Token Expiration**:
   - Default session token lifespan is 60 seconds. Clerk's client SDK automatically handles rolling refreshes.
   - The backend validates the `exp` claim against UTC time.
3. **CORS Restrictions**:
   - The backend strictly enforces `CORSMiddleware` against `FRONTEND_URL`. When switching to custom domains, update the Cloud Run backend's `FRONTEND_URL` environment variable.

---

## 5. Cloud Run Environment Variable Updates

When deploying with the production Clerk instance, run:

```bash
# 1. Update Secret Manager with production live secret key
echo -n "sk_live_..." | gcloud secrets versions add clerk-secret-key --data-file=- --project=oss-match

# 2. Update backend Cloud Run service environment
gcloud run services update mergewise-backend \
  --region asia-south1 \
  --project oss-match \
  --update-env-vars "ENVIRONMENT=production,CLERK_ISSUER=https://clerk.yourdomain.com,FRONTEND_URL=https://mergewise-frontend-708575763180.asia-south1.run.app"

# 3. Rebuild frontend with production publishable key
gcloud builds submit --config=cloudbuild-frontend.yaml \
  --substitutions "_API_URL=https://mergewise-backend-708575763180.asia-south1.run.app,_CLERK_KEY=pk_live_..." \
  --project oss-match .
```

