#!/usr/bin/env bash
# ==============================================================================
# MergeWise / OSS Match Agent — Cloud Run Deployment Script (Scale to Zero)
# ==============================================================================
set -euo pipefail

if [ -z "${GCP_PROJECT_ID:-}" ]; then
  echo "Error: GCP_PROJECT_ID environment variable is required."
  exit 1
fi

REGION="${GCP_REGION:-asia-south1}"
GCP_LOCATION="${GCP_LOCATION:-global}"
SA_EMAIL="mergewise-runner@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
REGISTRY="${REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/mergewise-repo"

echo "Deploying MergeWise microservices to Cloud Run..."
echo "Project: $GCP_PROJECT_ID | Cloud Run Region: $REGION | Vertex Location: $GCP_LOCATION"

# ------------------------------------------------------------------------------
# 1. Build and Deploy Backend (FastAPI)
# ------------------------------------------------------------------------------
echo "Building backend container image using Cloud Build..."
gcloud builds submit --config=cloudbuild-backend.yaml .

echo "Deploying mergewise-backend to Cloud Run..."
gcloud run deploy mergewise-backend \
  --image "${REGISTRY}/mergewise-backend:latest" \
  --region "$REGION" \
  --platform managed \
  --service-account "$SA_EMAIL" \
  --min-instances 0 \
  --max-instances 3 \
  --memory 512Mi \
  --cpu 1 \
  --allow-unauthenticated \
  --set-secrets "CLERK_SECRET_KEY=clerk-secret-key:latest" \
  --set-env-vars "ENVIRONMENT=production,GEMINI_MODEL_ID=${GEMINI_MODEL_ID:-gemini-3.8-flash},GCP_PROJECT_ID=${GCP_PROJECT_ID},GCP_LOCATION=${GCP_LOCATION},FIRESTORE_DATABASE_ID=(default),CLERK_ISSUER=${CLERK_ISSUER:-https://mutual-panther-6595.clerk.accounts.dev}" \
  --set-secrets "CLERK_SECRET_KEY=clerk-secret-key:latest"

BACKEND_URL=$(gcloud run services describe mergewise-backend --region "$REGION" --format 'value(status.url)')
echo "Backend deployed at: $BACKEND_URL"

# ------------------------------------------------------------------------------
# 2. Build and Deploy Frontend (Next.js)
# ------------------------------------------------------------------------------
echo "Building frontend container image with Cloud Build..."
gcloud builds submit --config=cloudbuild-frontend.yaml \
  --substitutions "_API_URL=${BACKEND_URL}" .

echo "Deploying mergewise-frontend to Cloud Run..."
gcloud run deploy mergewise-frontend \
  --image "${REGISTRY}/mergewise-frontend:latest" \
  --region "$REGION" \
  --platform managed \
  --service-account "$SA_EMAIL" \
  --min-instances 0 \
  --max-instances 3 \
  --memory 512Mi \
  --cpu 1 \
  --allow-unauthenticated \
  --set-secrets "CLERK_SECRET_KEY=clerk-secret-key:latest"

FRONTEND_URL=$(gcloud run services describe mergewise-frontend --region "$REGION" --format 'value(status.url)')
echo "Frontend deployed at: $FRONTEND_URL"

# ------------------------------------------------------------------------------
# 3. Update Backend with Frontend URL (Allowed CORS Origin)
# ------------------------------------------------------------------------------
echo "Configuring backend CORS with FRONTEND_URL=$FRONTEND_URL..."
gcloud run services update mergewise-backend \
  --region "$REGION" \
  --update-env-vars "FRONTEND_URL=${FRONTEND_URL}"

echo "=============================================================================="
echo "Deployment Finished Successfully!"
echo "Frontend URL: $FRONTEND_URL"
echo "Backend API:  $BACKEND_URL"
echo "Health Check: $BACKEND_URL/health"
echo "=============================================================================="
