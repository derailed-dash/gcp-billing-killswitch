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
3.  **A Pub/Sub topic** that receives notifications from your Cloud Billing budgets.
4.  **A Cloud Billing Budget** configured to monitor a specific project and send alerts to the aforementioned Pub/Sub topic.
5.  **Local Tools:** `gcloud` CLI and `uv` must be installed on your local machine.

## Local Environment Setup

To configure your local development environment, you must first create a `.env` file and then run the provided setup script.

1.  **Create a `.env` file** in the root of the project. This file will be used by both the setup and deployment scripts. It should contain:

    ```bash
    # For gcloud authentication and project setup
    GOOGLE_CLOUD_PROJECT="your-finops-project-id"

    # For deployment
    FUNCTION_NAME="your-function-name"
    REGION="your-region"
    BILLING_ALERT_TOPIC="your-billing-alert-topic"
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

Once your environment is configured and you have populated the `.env` file, you can deploy the function by first generating the `requirements.txt` and then running the deployment script:

```bash
make requirements
./scripts/deploy.sh
```

## Useful Commands

| Command                       | Description                                                                           |
| ----------------------------- | ------------------------------------------------------------------------------------- |
| `source scripts/setup-env.sh` | Setup Google Cloud project, ADC, and Python dependencies |
| `make install`                | Install all required dependencies using `uv` |
| `make requirements`           | Create a `requirements.txt` for the Cloud Run Function, from `pyproject.toml` |
| `make test`                   | Run unit and integration tests |
| `make lint`                   | Run code quality checks (codespell, ruff, mypy) |

For full command options and usage, refer to the [Makefile](Makefile).

## Useful References

- [Create, edit, or delete budgets and budget alerts](https://cloud.google.com/billing/docs/how-to/budgets)
- [https://cloud.google.com/blog/products/gcp/better-cost-control-with-google-cloud-billing-programmatic-notifications](https://cloud.google.com/blog/products/gcp/better-cost-control-with-google-cloud-billing-programmatic-notifications)
- [Set up programmatic notifications](https://cloud.google.com/billing/docs/how-to/budgets-programmatic-notifications)
- [Enable, disable, or change billing for a project](https://cloud.google.com/billing/docs/how-to/modify-project)
- [Disable billing usage with notifications](https://cloud.google.com/billing/docs/how-to/disable-billing-with-notifications)
