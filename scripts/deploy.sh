#!/bin/bash

# This script deploys the Cloud Function.
# Make sure you've sourced .env before running.

# Check that required variables are set
if [ -z "$FUNCTION_NAME" ] || [ -z "$GOOGLE_CLOUD_PROJECT" ] || [ -z "$GOOGLE_CLOUD_REGION" ] || [ -z "$BILLING_ALERT_TOPIC" ] || [ -z "$BILLING_ACCOUNT_ID" ]; then
    echo "Error: One or more required environment variables are not set in .env file."
    echo "Please set FUNCTION_NAME, GOOGLE_CLOUD_PROJECT, REGION, BILLING_ALERT_TOPIC, BILLING_ACCOUNT_ID."
    return 1
fi

# In case APIs not enabled - we need these to deploy a Cloud Run Function (2nd gen)
gcloud services enable --project=$GOOGLE_CLOUD_PROJECT \
  cloudbuild.googleapis.com \
  eventarc.googleapis.com \
  cloudfunctions.googleapis.com \
  run.googleapis.com \
  logging.googleapis.com \
  billingbudgets.googleapis.com

# Deploy the function
# Define service account variables
SERVICE_ACCOUNT_NAME="${FUNCTION_NAME}-sa"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com"

echo "Ensuring service account ${SERVICE_ACCOUNT_EMAIL} exists..."

# Create service account if it doesn't exist
if ! gcloud iam service-accounts describe "${SERVICE_ACCOUNT_EMAIL}" --project="${GOOGLE_CLOUD_PROJECT}" &> /dev/null; then
    gcloud iam service-accounts create "${SERVICE_ACCOUNT_NAME}" \
        --display-name="Service Account for ${FUNCTION_NAME}" \
        --project="${GOOGLE_CLOUD_PROJECT}"
    echo "Service account ${SERVICE_ACCOUNT_EMAIL} created."
else
    echo "Service account ${SERVICE_ACCOUNT_EMAIL} already exists."
fi

### Service Account IAM for Billing Account ###
echo "Granting roles/billing.user to ${SERVICE_ACCOUNT_EMAIL} on billing account ${BILLING_ACCOUNT_ID}..."

### Service Account IAM for Function-Hosting Project ###
gcloud billing accounts add-iam-policy-binding "${BILLING_ACCOUNT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/billing.user" \
  --project="${GOOGLE_CLOUD_PROJECT}" # This project flag is for the gcloud command itself, not the policy target

gcloud billing accounts add-iam-policy-binding "${BILLING_ACCOUNT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/billing.projectCostsManager" \
  --project="${GOOGLE_CLOUD_PROJECT}" # This project flag is for the gcloud command itself, not the policy target

echo "Granting roles to ${SERVICE_ACCOUNT_EMAIL} on the project ${GOOGLE_CLOUD_PROJECT}..."

gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/billing.projectManager"

gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/viewer"

gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/logging.logWriter"

gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/run.invoker"

gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/pubsub.subscriber"

### Deploy Cloud Run Function ###
echo "Deploying the function with service account ${SERVICE_ACCOUNT_EMAIL}..."
gcloud functions deploy "$FUNCTION_NAME" \
  --gen2 \
  --runtime=python312 \
  --project="$GOOGLE_CLOUD_PROJECT" \
  --region="$GOOGLE_CLOUD_REGION" \
  --source=./src \
  --entry-point=disable_billing_for_project \
  --trigger-topic="$BILLING_ALERT_TOPIC" \
  --service-account="${SERVICE_ACCOUNT_EMAIL}" \
  --set-env-vars SIMULATE_DEACTIVATION=true # Comment to disable simulation mode
