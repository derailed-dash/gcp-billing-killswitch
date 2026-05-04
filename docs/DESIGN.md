# Design Guidelines


## Visual Identity


This is a backend utility; there is no frontend UI. Visual identity is focused on clear, actionable logging and console output.

## Logic Design


### Event Handling

The function is designed to be idempotent. If a budget alert is received for a project that is already detached, the function should handle it gracefully without error.

### Error Handling

The function implements robust error handling for:
- **API Failures**: Retries or clear error logging for transient or permanent GCP API errors.
- **Malformed Messages**: Validation of incoming Pub/Sub payloads.
- **Permission Issues**: Specifically identifying and logging 403 Forbidden errors to guide IAM configuration.

### Simulation Mode

A core design feature is the `SIMULATE_DEACTIVATION` flag. This allows for safe end-to-end testing of the notification pipeline.

## CLI & Environment Design


### Environment Variables

We use a `.env` file for local development to manage sensitive or project-specific configuration. 

### Makefile Commands

Commands are designed to be short, descriptive, and consistent (e.g., `make install`, `make test`, `make lint`).

### Shell Setup

The `scripts/setup-env.sh` script is the primary entry point for developers, automating the configuration of `gcloud` and Python environments.
