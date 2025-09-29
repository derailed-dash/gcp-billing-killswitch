#!/bin/bash

# This script deploys the Cloud Function.

# Check that required variables are set
if [ -z "$FUNCTION_NAME" ] || [ -z "$GOOGLE_CLOUD_PROJECT" ] || [ -z "$GOOGLE_CLOUD_REGION" ] || [ -z "$BILLING_ALERT_TOPIC" ]; then
    echo "Error: One or more required environment variables are not set in .env file."
    echo "Please set FUNCTION_NAME, GOOGLE_CLOUD_PROJECT, REGION, and BILLING_ALERT_TOPIC."
    return 1
fi

# In case APIs not enabled - we need these to deploy a Cloud Run Function (2nd gen)
gcloud services enable cloudbuild.googleapis.com --project=$GOOGLE_CLOUD_PROJECT
gcloud services enable eventarc.googleapis.com --project=$GOOGLE_CLOUD_PROJECT
gcloud services enable cloudfunctions.googleapis.com --project=$GOOGLE_CLOUD_PROJECT
gcloud services enable run.googleapis.com --project=$GOOGLE_CLOUD_PROJECT

# Deploy the function
gcloud functions deploy "$FUNCTION_NAME" \
  --gen2 \
  --runtime=python312 \
  --project="$GOOGLE_CLOUD_PROJECT" \
  --region="$GOOGLE_CLOUD_REGION" \
  --source=./src \
  --entry-point=disable_billing_for_project \
  --trigger-topic="$BILLING_ALERT_TOPIC" \
  # Uncomment the following line to enable simulation mode (billing will not be disabled)
  --set-env-vars SIMULATE_DEACTIVATION=true

