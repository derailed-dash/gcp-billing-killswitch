# Project: GCP Billing Killswitch

## Project Overview

The goal of this project is to create a Google Cloud Run Function (2nd Gen) designed to automatically disable billing for a Google Cloud project. It is triggered by a Pub/Sub message, which is published by a Cloud Billing budget alert. See the `README.md` for further details.

## Building and Running

### Dependencies

- **uv:** Python package manager
- **Google Cloud SDK:** For interacting with GCP services
- **make:** For running common development tasks

Project dependencies are managed in `pyproject.toml` and can be installed using `uv`. The `make` commands streamline many commands.

Note that the Google Cloud Run Function requires its own `requirements.txt`. This should be populated using the core dependencies listed in `pyproject.toml`.

## Important References

Before offering advice, make sure you have read these URLs for additional context. Use the `webFetch` tool to read the content:

- [https://cloud.google.com/blog/products/gcp/better-cost-control-with-google-cloud-billing-programmatic-notifications](https://cloud.google.com/blog/products/gcp/better-cost-control-with-google-cloud-billing-programmatic-notifications)
- [Set up programmatic notifications](https://cloud.google.com/billing/docs/how-to/budgets-programmatic-notifications)
- [Programmatic notifications: Notification format](https://cloud.google.com/billing/docs/how-to/budgets-programmatic-notifications#notification_format)
- [Enable, disable, or change billing for a project](https://cloud.google.com/billing/docs/how-to/modify-project)
- [Disable billing usage with notifications](https://cloud.google.com/billing/docs/how-to/disable-billing-with-notifications)