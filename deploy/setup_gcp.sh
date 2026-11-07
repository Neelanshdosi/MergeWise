#!/usr/bin/env bash
# ==============================================================================
# MergeWise / OSS Match Agent — GCP Environment Setup & Budget Protection
# ==============================================================================
set -euo pipefail

# 1. Project & Region Check
if [ -z "${GCP_PROJECT_ID:-}" ]; then
  echo "Error: GCP_PROJECT_ID is not set. Run: export GCP_PROJECT_ID=your-project-id"
  exit 1
fi

REGION="${GCP_REGION:-asia-south1}"
GCP_LOCATION="${GCP_LOCATION:-global}"
echo "Configuring GCP Project: $GCP_PROJECT_ID in Region: $REGION..."

gcloud config set project "$GCP_PROJECT_ID"

# 2. Enable Required APIs (Cloud Run, Artifact Registry, Vertex AI, Firestore, BigQuery, Secret Manager)
echo "Enabling necessary Google Cloud APIs..."
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  aiplatform.googleapis.com \
  firestore.googleapis.com \
  bigquery.googleapis.com

# 3. Create Artifact Registry Repository for Docker images
echo "Creating Artifact Registry repository: mergewise-repo..."
gcloud artifacts repositories create mergewise-repo \
  --repository-format=docker \
  --location="$REGION" \
  --description="Docker repository for MergeWise frontend and backend" \
  || echo "Artifact registry repository already exists."

# 4. Create Service Account with Least Privilege
SA_NAME="mergewise-runner"
SA_EMAIL="${SA_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"

echo "Creating Cloud Run service account: $SA_EMAIL..."
gcloud iam service-accounts create "$SA_NAME" \
  --description="Service account for MergeWise Cloud Run microservices" \
  --display-name="MergeWise Runner" \
  || echo "Service account already exists."

# Grant roles
echo "Granting least-privilege IAM roles..."
ROLES=(
  "roles/aiplatform.user"
  "roles/datastore.user"
  "roles/bigquery.jobUser"
  "roles/secretmanager.secretAccessor"
)

for role in "${ROLES[@]}"; do
  gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="$role" \
    --condition=None
done

# 5. Store Clerk Secret Key in Secret Manager
echo "Configuring Secret Manager for Clerk Secret Key..."
if [ -n "${CLERK_SECRET_KEY:-}" ]; then
  echo -n "$CLERK_SECRET_KEY" | gcloud secrets create clerk-secret-key \
    --replication-policy="automatic" \
    --data-file=- || \
  echo -n "$CLERK_SECRET_KEY" | gcloud secrets versions add clerk-secret-key --data-file=-
  echo "Secret clerk-secret-key configured in Secret Manager."
else
  echo "Note: CLERK_SECRET_KEY not set in current shell. You can create it manually:"
  echo "echo -n 'sk_live_...' | gcloud secrets create clerk-secret-key --data-file=-"
fi

# 6. Verify Firestore in Native Mode (default database preserved in asia-south1)
echo "Checking Firestore database status..."
gcloud firestore databases describe --database="(default)" >/dev/null 2>&1 && echo "Firestore (default) is active in asia-south1 — retaining existing database." || gcloud firestore databases create --location="$REGION" --type=firestore-native

echo "=============================================================================="
echo "GCP Setup Complete!"
echo "Service Account: $SA_EMAIL"
echo "Artifact Registry: $REGION-docker.pkg.dev/$GCP_PROJECT_ID/mergewise-repo"
echo "=============================================================================="
