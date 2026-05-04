# Installation / Deployment

## Overview

This project uses `gcloud` commands and shell scripts for provisioning and deployment.

## Prerequisites

- Google Cloud SDK (`gcloud`) installed and authenticated.
- A Google Cloud Project to host the function (e.g., "FinOps Admin Project").
- A Cloud Billing Account.
- Python 3.12+
- `uv` package manager

## Environment Setup

1.  **Create a `.env` file** in the root of the project. This file will be used by both the setup and deployment scripts. It should contain:

    ```bash
    # For gcloud authentication and project setup
    export GOOGLE_CLOUD_PROJECT="your-finops-project-id"
    export GOOGLE_CLOUD_REGION="your-region"

    # For deployment
    export FUNCTION_NAME="your-function-name"
    export BILLING_ALERT_TOPIC="your-billing-alert-topic"
    export BILLING_ACCOUNT_ID="your-billing-account-id"
    export LOG_LEVEL="INFO"
    export SIMULATE_DEACTIVATION="true"

    # Create a budget in Cloud Billing, and obtain its ID:

    # gcloud billing budgets list --billing-account=$BILLING_ACCOUNT_ID --project=$GOOGLE_CLOUD_PROJECT
    export SAMPLE_BUDGET_ID="for-testing-a-budget"
    ```

2.  **Run the setup script:** Source the script to configure your shell environment. This will handle `gcloud` authentication, Python dependency installation, and virtual environment activation.

```bash
source scripts/setup-env.sh
```

## IAM Roles

The Cloud Function's runtime service account requires the following roles to manage billing across projects:

| Level | Role | Rationale |
| :--- | :--- | :--- |
| **Billing Account** | `roles/billing.admin` | Required to manage billing associations. |
| **Organization/Project** | `roles/billing.projectManager` | Required to detach projects from billing. |
| **Host Project** | `roles/logging.logWriter` | Required to write execution logs. |
| **Host Project** | `roles/run.invoker` | Required for Eventarc to invoke the function. |

## Deployment

Run the following commands to setup the service account, Pub/Sub topic and Cloud Run function in your specified host project.

### 1. Environment Setup

```bash
#####################################################
### Do these steps for any development session ######
source scripts/setup-env.sh

# ONLY if we're working with DEV project
export GOOGLE_CLOUD_PROJECT=$DEV_GOOGLE_CLOUD_PROJECT

export SERVICE_ACCOUNT_NAME="${FUNCTION_NAME}-sa"
export SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com"
#####################################################
```

### 2. Enable APIs

```bash
# Enable APIs
gcloud services enable --project=$GOOGLE_CLOUD_PROJECT \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  pubsub.googleapis.com \
  eventarc.googleapis.com \
  cloudbilling.googleapis.com \
  cloudfunctions.googleapis.com \
  run.googleapis.com \
  logging.googleapis.com \
  billingbudgets.googleapis.com \
  cloudresourcemanager.googleapis.com
```

### 3. Create Topic

```bash
# Create the Pub/Sub topic.
gcloud pubsub topics create $BILLING_ALERT_TOPIC --project=$GOOGLE_CLOUD_PROJECT

# Create service account if it doesn't exist
if ! gcloud iam service-accounts describe "${SERVICE_ACCOUNT_EMAIL}" --project="${GOOGLE_CLOUD_PROJECT}" &> /dev/null; then
    gcloud iam service-accounts create "${SERVICE_ACCOUNT_NAME}" \
        --display-name="Service Account for ${FUNCTION_NAME}" \
        --project="${GOOGLE_CLOUD_PROJECT}"
    echo "Service account ${SERVICE_ACCOUNT_EMAIL} created."
else
    echo "Service account ${SERVICE_ACCOUNT_EMAIL} already exists."
fi
```

### 4. Assign IAM Roles

```bash
# Service Account IAM for Billing Account
gcloud billing accounts add-iam-policy-binding "${BILLING_ACCOUNT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/billing.admin" \
  --project="${GOOGLE_CLOUD_PROJECT}"

# (RECOMMENDED) Service Account IAM for Organization
# This ensures the killswitch works for ALL current and future projects.
# Get your Org ID: gcloud organizations list
export ORG_ID="your-org-id"
gcloud organizations add-iam-policy-binding "${ORG_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/billing.projectManager"

# Service Account IAM for Function-Hosting Project

gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/viewer"

gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/logging.logWriter"

gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/billing.projectManager"

gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/run.invoker"

gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/pubsub.subscriber"
```

Whenever you add a **new project to a budget monitored by this killswitch**, you must ensure the service account has the necessary permissions on that project.

You can verify existing roles like this:

1.  **Check existing roles:**
    ```bash
    gcloud projects get-iam-policy TARGET_PROJECT_ID \
        --flatten="bindings[].members" \
        --filter="bindings.members:cf-billing-killswitch-sa@YOUR_ADMIN_PROJECT.iam.gserviceaccount.com"
    ```

2.  **Assign the role (if missing):**
    ```bash
    gcloud projects add-iam-policy-binding TARGET_PROJECT_ID \
        --member="serviceAccount:cf-billing-killswitch-sa@YOUR_ADMIN_PROJECT.iam.gserviceaccount.com" \
        --role="roles/billing.projectManager"
    ```

### 5. Deploy Cloud Function

```bash
# Deploy the Cloud Run Function
# Always check your SERVICE_ACCOUNT_EMAIL variable is set
gcloud functions deploy $FUNCTION_NAME \
  --gen2 \
  --runtime=python312 \
  --project="$GOOGLE_CLOUD_PROJECT" \
  --region="$GOOGLE_CLOUD_REGION" \
  --source=./src \
  --entry-point=disable_billing_for_projects \
  --trigger-topic=$BILLING_ALERT_TOPIC \
  --service-account="${SERVICE_ACCOUNT_EMAIL}" \
  --set-env-vars LOG_LEVEL=$LOG_LEVEL,SIMULATE_DEACTIVATION=$SIMULATE_DEACTIVATION 
```

Note: for testing purposes, you can deploy the function in a simulation mode 
where it will log that billing *would have been disabled* without actually making the API call to detach the project from its billing account. This is controlled by the `SIMULATE_DEACTIVATION` environment variable. Set `SIMULATE_DEACTIVATION=true` in your `.env` file before deploying.

### Alternative Deployment Command - Using Gcloud Run Deploy

With the evolution of Cloud Functions to Cloud Run Functions, we can now deploy using the `gcloud run deploy` command. 
It converts the function code into a Cloud Run image with the specified base image to provide our runtime.
However, this command does not create the Eventarc trigger for us, so we must create the trigger as a separate command.

```bash
export SERVICE_ACCOUNT_NAME="${FUNCTION_NAME}-sa"
export SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com"

# Create the Cloud Run Function
# Notes:
# - Gen1 is ideal for very small functions that frequently spin-up from 0
# - Fractional CPUs are possible with gen1, but requires concurrency to be set to 1
# - <512MB is possible with gen1
gcloud run deploy $FUNCTION_NAME \
  --base-image=python312 \
  --project=$GOOGLE_CLOUD_PROJECT \
  --region=$GOOGLE_CLOUD_REGION \
  --source=./src \
  --function=disable_billing_for_projects \
  --no-allow-unauthenticated \
  --execution-environment=gen1 \
  --cpu=0.2 \
  --memory=256Mi \
  --concurrency=1 \
  --max-instances=1 \
  --service-account="${SERVICE_ACCOUNT_EMAIL}" \
  --set-env-vars LOG_LEVEL=$LOG_LEVEL,SIMULATE_DEACTIVATION=$SIMULATE_DEACTIVATION 

# Create the Eventarc Trigger, wiring our topic to the function
gcloud eventarc triggers create ${FUNCTION_NAME}-trigger \
    --project=$GOOGLE_CLOUD_PROJECT \
    --location=$GOOGLE_CLOUD_REGION \
    --destination-run-service=$FUNCTION_NAME \
    --destination-run-region=$GOOGLE_CLOUD_REGION \
    --event-filters="type=google.cloud.pubsub.topic.v1.messagePublished" \
    --transport-topic=projects/$GOOGLE_CLOUD_PROJECT/topics/$BILLING_ALERT_TOPIC \
    --service-account=$SERVICE_ACCOUNT_EMAIL
```
