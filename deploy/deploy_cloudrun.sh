#!/usr/bin/env bash
# ==============================================================================
# MergeWise / OSS Match Agent — Cloud Run Deployment Script (Scale to Zero)
# ==============================================================================
set -euo pipefail

if [ -z "${GCP_PROJECT_ID:-}" ]; then
  echo "Error: GCP_PROJECT_ID environment variable is required."
  exit 1
fi

REGION="${GCP_REGION:-us-central1}"
SA_EMAIL="mergewise-runner@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
REGISTRY="${REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/mergewise-repo"

echo "Deploying MergeWise microservices to Cloud Run..."
echo "Project: $GCP_PROJECT_ID | Region: $REGION"

# ------------------------------------------------------------------------------
# 1. Build and Deploy Backend (FastAPI)
# ------------------------------------------------------------------------------
echo "Building backend container image..."
gcloud builds submit \
  --tag "${REGISTRY}/mergewise-backend:latest" \
  --project "$GCP_PROJECT_ID" \
  -f backend/Dockerfile .

echo "Deploying mergewise-backend to Cloud Run..."
gcloud run deploy mergewise-backend \
  --image "${REGISTRY}/mergewise-backend:latest" \
  --region "$REGION" \
  --platform managed \
  --service-account "$SA_EMAIL" \
  --min-instances 0 \
  --max-instances 2 \
  --memory 512Mi \
  --cpu 1 \
  --allow-unauthenticated \
  --set-env-vars "ENVIRONMENT=production,GEMINI_MODEL_ID=${GEMINI_MODEL_ID:-gemini-2.0-flash},GCP_PROJECT_ID=${GCP_PROJECT_ID},GCP_LOCATION=${REGION}" \
  --set-secrets "CLERK_SECRET_KEY=clerk-secret-key:latest"

BACKEND_URL=$(gcloud run services describe mergewise-backend --region "$REGION" --format 'value(status.url)')
echo "Backend deployed at: $BACKEND_URL"

# ------------------------------------------------------------------------------
# 2. Build and Deploy Frontend (Next.js)
# ------------------------------------------------------------------------------
echo "Building frontend container image with NEXT_PUBLIC_API_URL=$BACKEND_URL..."
gcloud builds submit \
  --tag "${REGISTRY}/mergewise-frontend:latest" \
  --project "$GCP_PROJECT_ID" \
  --substitutions "_API_URL=${BACKEND_URL}" \
  frontend/

echo "Deploying mergewise-frontend to Cloud Run..."
gcloud run deploy mergewise-frontend \
  --image "${REGISTRY}/mergewise-frontend:latest" \
  --region "$REGION" \
  --platform managed \
  --service-account "$SA_EMAIL" \
  --min-instances 0 \
  --max-instances 2 \
  --memory 512Mi \
  --cpu 1 \
  --allow-unauthenticated

FRONTEND_URL=$(gcloud run services describe mergewise-frontend --region "$REGION" --format 'value(status.url)')
echo "Frontend deployed at: $FRONTEND_URL"

# ------------------------------------------------------------------------------
# 3. Update Backend CORS to Strictly Allow Frontend URL
# ------------------------------------------------------------------------------
echo "Configuring backend CORS with FRONTEND_URL=$FRONTEND_URL and CLERK_AUTHORIZED_PARTIES..."
gcloud run services update mergewise-backend \
  --region "$REGION" \
  --update-env-vars "FRONTEND_URL=${FRONTEND_URL},CLERK_AUTHORIZED_PARTIES=[\"${FRONTEND_URL}\"]"

echo "=============================================================================="
echo "Deployment Finished Successfully!"
echo "Frontend URL: $FRONTEND_URL"
echo "Backend API:  $BACKEND_URL"
echo "Health Check: $BACKEND_URL/health"
echo "=============================================================================="
