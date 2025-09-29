# Project: Kill-GCP-Project-Billing

---
***IMPORTANT: Run this check at the start of EVERY session!***

Google Cloud configuration is achieved through a combination of `.env` and the `scripts/setup-env.sh` script. 

Before providing your FIRST response in any conversation, you MUST perform the following steps:
1.  Run `printenv GOOGLE_CLOUD_PROJECT` to check the environment variable.
2.  Based only on the output of that command, state whether the variable is set.
3.  If it is not set, advise me to run `scripts/setup-env.sh` before resuming the conversation.

The presence of this environment variable indicates that the script has been run. The absence of this variable indicates that the script has NOT been run.

Note that failures with Google Cloud are likely if this script has not been run. For example, tests will fail. If tests are failing, we should check if the script has been run.
---

## Project Overview

The goal of this project is to create a Google Cloud Run Function (2nd Gen) designed to automatically disable billing for a Google Cloud project. It is triggered by a Pub/Sub message, which is published by a Cloud Billing budget alert.

## Building and Running

### Dependencies

- **uv:** Python package manager
- **Google Cloud SDK:** For interacting with GCP services
- **make:** For running common development tasks

Project dependencies are managed in `pyproject.toml` and can be installed using `uv`. The `make` commands streamline many `uv` and `adk` commands.

Note that the Google Cloud Run Function requires its own `requirements.txt`. This is created from `pyproject.toml` when we run `make requirements`.

## Important References

Before offering advice, make sure you have read these URLs. Use the `webFetch` tool to read the content:

- [Create, edit, or delete budgets and budget alerts](https://cloud.google.com/billing/docs/how-to/budgets)
- [https://cloud.google.com/blog/products/gcp/better-cost-control-with-google-cloud-billing-programmatic-notifications](https://cloud.google.com/blog/products/gcp/better-cost-control-with-google-cloud-billing-programmatic-notifications)
- [Set up programmatic notifications](https://cloud.google.com/billing/docs/how-to/budgets-programmatic-notifications)
- [Enable, disable, or change billing for a project](https://cloud.google.com/billing/docs/how-to/modify-project)
- [Disable billing usage with notifications](https://cloud.google.com/billing/docs/how-to/disable-billing-with-notifications)
