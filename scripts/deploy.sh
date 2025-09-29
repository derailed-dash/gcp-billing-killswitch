#!/bin/bash

# This script deploys the Cloud Function.

# Check that required variables are set
if [ -z "$FUNCTION_NAME" ] || [ -z "$GOOGLE_CLOUD_PROJECT" ] || [ -z "$REGION" ] || [ -z "$BILLING_ALERT_TOPIC" ]; then
    echo "Error: One or more required environment variables are not set in .env file."
    echo "Please set FUNCTION_NAME, GOOGLE_CLOUD_PROJECT, REGION, and BILLING_ALERT_TOPIC."
    exit 1
fi

# Deploy the function
gcloud functions deploy "$FUNCTION_NAME" \
  --gen2 \
  --runtime=python312 \
  --project="$GOOGLE_CLOUD_PROJECT" \
  --region="$REGION" \
  --source=./src \
  --entry-point=disable_billing_for_project \
  --trigger-topic="$BILLING_ALERT_TOPIC"

