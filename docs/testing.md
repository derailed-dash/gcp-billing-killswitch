# Testing & Quality Assurance

## Tooling

*   **Test Runner**: `pytest`
*   **Linting/Formatting**: `ruff`, `codespell`, `mypy`
*   **Package Manager**: `uv`

## CI/CD vs Local

For local development, we use `pytest` with `unittest.mock` to simulate Google Cloud APIs. This allows for rapid iteration without incurring costs or risking real project deactivations.

Integration and End-to-End tests are performed in a dedicated Google Cloud staging environment.

- **Mocking Strategy**: We mock the `google.cloud.billing` and `google.cloud.resourcemanager` clients to verify that the correct API calls are made with the expected project and billing account IDs.

## Commands

*   `make test`: Run all unit and integration tests.
*   `make lint`: Run all quality checks (codespell, ruff, mypy).

## Test Categories

### Unit Tests

Located in `tests/test_main.py`. These tests verify the core logic of the `disable_billing_for_project` function in isolation, covering various scenarios such as:
- Successful billing deactivation.
- Handling of multiple projects in a single budget alert.
- Scenarios where costs do not exceed the budget.
- Missing IDs or malformed messages.

### Integration Tests

These tests verify that the Cloud Function correctly interacts with real Google Cloud services (Pub/Sub, Cloud Billing API) in a controlled staging project.
- **Method**: Deploy the function with `SIMULATE_DEACTIVATION=true` and publish real Pub/Sub messages to a test topic.
- **Verification**: Check Cloud Logging to confirm the function was triggered and would have detached the billing account.

### End-to-End Tests

Validates the entire workflow from a real budget alert to billing disablement.
- **Method**: Set up a real budget with a low threshold in a disposable project. Incur costs to trigger the alert and verify the final billing status of the project.

### Manual Verification

A template for manual Pub/Sub message publishing is provided in `tests/budget_alert.json.template`. 

You can use the following commands to manually trigger and test the function:

```bash
export TEST_PROJECT_NUMBER=$(gcloud projects describe $GOOGLE_CLOUD_PROJECT --format="value(projectNumber)")

# CREATE TEST MSG by replacing placeholders in the template using values from env vars
sed "s/TEST_PROJECT_NUMBER/${TEST_PROJECT_NUMBER}/g" tests/budget_alert.json.template > tests/budget_alert.json

msg=$(cat tests/budget_alert.json)

# Ideally, create a budget alert for this test project, and store its ID in your .env
# Then publish the test message
gcloud pubsub topics publish $BILLING_ALERT_TOPIC \
    --project="$GOOGLE_CLOUD_PROJECT" \
    --message="$msg" \
    --attribute="budgetId=$SAMPLE_BUDGET_ID,billingAccountId=$BILLING_ACCOUNT_ID"
```

Now review Cloud Logging to verify the Cloud Run Function was triggered and is working as expected.

## Monitoring and Alerting

To ensure the function operates correctly in production:

- **Cloud Logging**: Ensure logs include critical info like project ID, billing account ID, and the outcome of the billing disablement.
- **Cloud Monitoring Alerts**:
    - **Function Errors**: Alert on any errors or exceptions logged by the Cloud Function.
    - **Function Invocations**: Monitor the number of times the function is invoked.
    - **Budget Alerts**: Monitor the Pub/Sub topic for incoming budget alert messages.