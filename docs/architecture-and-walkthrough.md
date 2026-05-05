# Architecture and Walkthrough

![Killswitch Architecture](kill-switch-arch.png)

## Design Decisions (ADRs)

| Decision | Rationale |
| :--- | :--- |
| **Cloud Run Functions** | Provides a lightweight serverless function  execution environment that we can trigger in response to a Pub/Sub event. |
| **Pub/Sub Trigger** | Standard mechanism for receiving Google Cloud Billing budget notifications. Decouples the budget alert source from the killswitch action. |
| **Simulation Mode (`SIMULATE_DEACTIVATION`)** | Crucial for safety. Allows users to test the entire alert-to-function pipeline without actually disabling billing until they are ready. |
| **`uv` for Dependency Management** | Provides extremely fast dependency resolution and a modern workflow for Python projects. |

## Solution Architecture Overview

The GCP Billing Killswitch is an event-driven serverless solution. It is designed to be a "set and forget" safety mechanism.

- **Trigger**: A Cloud Billing Budget is configured with a programmatic notification to publish messages to a Pub/Sub topic.
- **Orchestration**: A Cloud Run Function (2nd Gen) is triggered by the Pub/Sub message via an Eventarc trigger.
- **Logic**: The function parses the message, checks if the cost exceeds the budget, and if so, identifies the associated projects and calls the Cloud Billing API to remove the billing account association.
- **Logging**: Detailed execution logs are sent to Cloud Logging, providing an audit trail of killswitch activities.

> [!NOTE]
> **Understanding Trigger Frequency:** Unlike email alerts which only fire when specific thresholds are crossed, GCP programmatic notifications broadcast the *current status* of your budget periodically throughout the day (typically every 20-30 minutes) regardless of whether a threshold has been breached. As a result, this function will invoke frequently to monitor the pulse of your budgets, evaluate the current cost, and gracefully exit if the budget has not been exceeded.

## Deployment Architecture Overview

The solution is deployed as a single Cloud Run Function. It is recommended to host this in a central "FinOps-Admin" project to monitor multiple projects across an organization.

- **Hosting**: Google Cloud Run Functions (2nd Gen).
- **Messaging**: Google Cloud Pub/Sub.
- **Identity**: A dedicated Service Account with specific billing and project management roles.

## Configuration Management

Configuration is handled primarily through environment variables and a `.env` file for local development/deployment scripts.

- `LOG_LEVEL`: Controls logging verbosity.
- `SIMULATE_DEACTIVATION`: If `true`, the function will only log that it *would* have disabled billing.

## Backend

The backend is a Python-based Cloud Run Function. It uses the `google-cloud-billing` and `google-cloud-resourcemanager` libraries to interact with GCP APIs.

## Security

Security is enforced through the principle of least privilege.

- **Service Account**: A dedicated service account (`roles/billing.admin` on the billing account and `roles/billing.projectManager` on projects) handles the billing detachment.
- **IAM**: Only the service account and authorized administrators have access to the Pub/Sub topic and the function.

## User Journeys

### 1. Initial Setup

A FinOps administrator configures the central killswitch function and assigns the necessary permissions to its service account.

### 2. Budget Threshold Exceeded

A project's spending exceeds the budget threshold. Google Cloud publishes a notification. The killswitch triggers and detaches the project from billing.

### 3. Simulation Test

An administrator deploys the function with `SIMULATE_DEACTIVATION=true` and publishes a test message to verify the pipeline is working as expected.

## Pub/Sub Message Format

The function expects a Pub/Sub message with the following format:

- **Message Payload (JSON):**
  - `costAmount` (float): The amount of cost that has been incurred.
  - `budgetAmount` (float): The budgeted amount.
  - `budgetDisplayName` (str): The display name of the budget.

- **Message Attributes:**
  - `billingAccountId` (str): The ID of the billing account.
  - `budgetId` (str): The ID of the budget.
