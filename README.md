# Google Cloud Kill Project Billing

This project contains a Google Cloud Run Function (2nd Gen) designed to automatically disable billing for a Google Cloud project. It is triggered by a Pub/Sub message, which is published by a Cloud Billing budget alert.

**⚠️ Warning: This is a destructive action.** Disconnecting a project from its billing account will stop all paid services. The project enters a 30-day grace period. If billing is not re-enabled within this period, the project and all its resources may be **permanently deleted**.

## Table of Contents

- [Repo Metadata](#repo-metadata)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Local Environment Setup](#local-environment-setup)
- [Project Structure](#project-structure)
- [IAM Permissions](#iam-permissions)
- [Unit Testing](#unit-testing)
- [Deployment](#deployment)
- [Useful Commands](#useful-commands)
- [Useful References](#useful-references)

## Repo Metadata

Author: Darren Lester

## Architecture

The architecture is simple and event-driven:

1.  A **Cloud Billing budget** is configured to send a notification to a Pub/Sub topic when a project's spending exceeds a defined threshold.
2.  A **Pub/Sub topic** receives the notification message.
3.  A **Cloud Run Function (2nd Gen)** is subscribed to this topic. When a message is published, the function is triggered.
4.  The function parses the incoming message to identify the project, and then uses the **Cloud Billing API** to detach the project from its billing account, effectively disabling billing.

## Prerequisites

Before deploying, ensure you have the following:

1.  **A Google Cloud project** to host this function (e.g., a central `finops-admin` project).
2.  **APIs Enabled:** In your host project, the following APIs must be enabled:
    -   Cloud Billing API
    -   Cloud Functions API
    -   Cloud Build API
    -   Eventarc API
    -   Cloud Run API
    
3.  **A Pub/Sub topic** that receives notifications from your Cloud Billing budgets.
4.  **A Cloud Billing Budget** configured to monitor a specific project and send alerts to the aforementioned Pub/Sub topic.
5.  **Local Tools:** `gcloud` CLI and `uv` must be installed on your local machine.

## Local Environment Setup

To configure your local development environment, you must first create a `.env` file and then run the provided setup script.

1.  **Create a `.env` file** in the root of the project. This file will be used by both the setup and deployment scripts. It should contain:

    ```bash
    # For gcloud authentication and project setup
    export GOOGLE_CLOUD_PROJECT="your-finops-project-id"
    export GOOGLE_CLOUD_REGION="your-region"

    # For deployment
    export FUNCTION_NAME="your-function-name"
    export BILLING_ALERT_TOPIC="your-billing-alert-topic"
    export BILLING_ACCOUNT_ID="your billing ID"
    ```

2.  **Run the setup script:** Source the script to configure your shell environment. This will handle `gcloud` authentication, Python dependency installation, and virtual environment activation.

    ```bash
    source scripts/setup-env.sh
    ```

## Project Structure

The project is structured as follows:

```
.
├── src
│   ├── main.py
│   └── requirements.txt
├── tests
│   └── test_main.py
├── scripts
│   ├── setup-env.sh
│   └── deploy.sh
├── .env
└── README.md
```

## IAM Permissions

The Cloud Function's **runtime service account** requires 
- The `Billing Account Administrator` role on the Cloud Billing Account.
- Or, on the projects to be disconnected: `Project Billing Manager` and one of `Project Viewer` or `Project Owner`

## Unit Testing

After setting up your environment with the `setup-env.sh` script, you can run the unit tests:

```bash
make test
```

## Deployment

Once your environment is configured and you have populated the `.env` file, you can deploy the function by first generating the `requirements.txt` and then:

### Every Session

```bash
source scripts/setup-env.sh

# If we're working with DEV project
export GOOGLE_CLOUD_PROJECT=$DEV_GOOGLE_CLOUD_PROJECT

# Define service account variables
SERVICE_ACCOUNT_NAME="${FUNCTION_NAME}-sa"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com"
```

### One-Time Project Setup (Per Project)

```bash
# Enable APIs
gcloud services enable --project=$GOOGLE_CLOUD_PROJECT \
  cloudbuild.googleapis.com \
  eventarc.googleapis.com \
  cloudfunctions.googleapis.com \
  run.googleapis.com \
  logging.googleapis.com \
  billingbudgets.googleapis.com

# First create the topic.
# Then connect your Cloud Billing budget to the Pub/Sub topic in the Cloud Console.
gcloud pubsub topics add-iam-policy-binding "${BILLING_ALERT_TOPIC}" \                                                                    │
  --member="serviceAccount:cloud-billing-pubsub-publisher@gcp-sa-billing.iam.gserviceaccount.com" \                                       │
  --role="roles/pubsub.publisher" \                                                                                                       │
  --project="${GOOGLE_CLOUD_PROJECT}"                                                                                                     │

# Define service account variables
SERVICE_ACCOUNT_NAME="${FUNCTION_NAME}-sa"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com"

# Create service account if it doesn't exist
if ! gcloud iam service-accounts describe "${SERVICE_ACCOUNT_EMAIL}" --project="${GOOGLE_CLOUD_PROJECT}" &> /dev/null; then
    gcloud iam service-accounts create "${SERVICE_ACCOUNT_NAME}" \
        --display-name="Service Account for ${FUNCTION_NAME}" \
        --project="${GOOGLE_CLOUD_PROJECT}"
    echo "Service account ${SERVICE_ACCOUNT_EMAIL} created."
else
    echo "Service account ${SERVICE_ACCOUNT_EMAIL} already exists."
fi

# Service Account IAM for Billing Account
gcloud billing accounts add-iam-policy-binding "${BILLING_ACCOUNT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/billing.user" \
  --project="${GOOGLE_CLOUD_PROJECT}"

gcloud billing accounts add-iam-policy-binding "${BILLING_ACCOUNT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/billing.projectCostsManager" \
  --project="${GOOGLE_CLOUD_PROJECT}" # 

gcloud billing accounts add-iam-policy-binding "${BILLING_ACCOUNT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/billing.user" \
  --project="${GOOGLE_CLOUD_PROJECT}"

gcloud billing accounts add-iam-policy-binding "${BILLING_ACCOUNT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/billing.projectCostsManager" \
  --project="${GOOGLE_CLOUD_PROJECT}"

# Service Account IAM for Function-Hosting Project
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
```

### Deploying the Cloud Run Function

Note: for testing purposes, you can deploy the function in a simulation mode 
where it will log that billing *would have been disabled* without actually making the API call to detach the project from its billing account. 
This is controlled by the `SIMULATE_DEACTIVATION` environment variable.

```bash
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
```

## Useful Commands

| Command                       | Description                                              |
| ----------------------------- | -------------------------------------------------------- |
| `source scripts/setup-env.sh` | Setup Google Cloud project, ADC, and Python dependencies |
| `make install`                | Install all required dependencies using `uv`             |
| `make test`                   | Run unit and integration tests                           |
| `make lint`                   | Run code quality checks (codespell, ruff, mypy)          |

For full command options and usage, refer to the [Makefile](Makefile).

## Testing

We can send a message that resembles a budget alert, like this:L

```bash
# Make sure we're using a test project before proceeding
export GOOGLE_CLOUD_PROJECT=$DEV_GOOGLE_CLOUD_PROJECT
export TEST_PROJECT_NUMBER=$(gcloud projects describe $GOOGLE_CLOUD_PROJECT --format="value(projectNumber)")

# CREATE TEST MSG by replacing placeholders in the template using values from env vars
sed "s/BILLING_ACCOUNT_ID/${BILLING_ACCOUNT_ID}/g; s/TEST_PROJECT_NUMBER/${TEST_PROJECT_NUMBER}/g" \
    tests/budget_alert.json.template > tests/budget_alert.json

msg=$(cat tests/budget_alert.json)

# Publish the message
gcloud pubsub topics publish $BILLING_ALERT_TOPIC \
    --project="$GOOGLE_CLOUD_PROJECT" \
    --message="$msg" \
    --attribute="budgetId=my-test-budget-id"

# Now we can read the Cloud Function logs
```

## Useful References

- [Create, edit, or delete budgets and budget alerts](https://cloud.google.com/billing/docs/how-to/budgets)
- [https://cloud.google.com/blog/products/gcp/better-cost-control-with-google-cloud-billing-programmatic-notifications](https://cloud.google.com/blog/products/gcp/better-cost-control-with-google-cloud-billing-programmatic-notifications)
- [Set up programmatic notifications](https://cloud.google.com/billing/docs/how-to/budgets-programmatic-notifications)
- [Enable, disable, or change billing for a project](https://cloud.google.com/billing/docs/how-to/modify-project)
- [Disable billing usage with notifications](https://cloud.google.com/billing/docs/how-to/disable-billing-with-notifications)
