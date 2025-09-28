#!/bin/bash

# This script deploys the Cloud Function.

# Check that required variables are set
if [ -z "$FUNCTION_NAME" ] || [ -z "$FINOPS_PROJECT_ID" ] || [ -z "$REGION" ] || [ -z "$BILLING_ALERT_TOPIC" ]; then
    echo "Error: One or more required environment variables are not set in .env file."
    echo "Please set FUNCTION_NAME, FINOPS_PROJECT_ID, REGION, and BILLING_ALERT_TOPIC."
    exit 1
fi

# Deploy the function
gcloud functions deploy "$FUNCTION_NAME" \
  --gen2 \
  --runtime=python312 \
  --project="$FINOPS_PROJECT_ID" \
  --region="$REGION" \
  --source=./src \
  --entry-point=disable_billing_for_project \
  --trigger-topic="$BILLING_ALERT_TOPIC"

