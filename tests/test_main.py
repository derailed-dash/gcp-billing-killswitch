"""
Unit tests for the `disable_billing_for_projects` Cloud Function.

These tests use pytest fixtures to create mock clients and test data, allowing
the function's logic to be tested in isolation without making actual API calls
to Google Cloud services.
"""
import base64
import json
import os
from unittest.mock import ANY, patch

import pytest
from cloudevents.http import CloudEvent
from google.api_core import exceptions
from google.cloud.billing.budgets_v1.types import Budget, Filter

from src.main import disable_billing_for_projects


@pytest.fixture
def mock_clients():
    """Fixture to mock the Google Cloud clients."""
    # We mock the clients to prevent our tests from making real API calls,
    # ensuring they are fast, repeatable, and don't depend on external services.
    with patch("src.main.billing_client", autospec=True) as mock_billing_client, \
         patch("src.main.budget_client", autospec=True) as mock_budget_client:
        yield mock_billing_client, mock_budget_client


@pytest.fixture
def cloud_event_factory():
    """Factory to create a CloudEvent for testing."""
    # A factory fixture is useful for creating repeatable, complex test objects.
    # This one simulates the structure of a Pub/Sub message delivered as a CloudEvent.
    def _create_cloud_event(data, attributes):
        event_data = {
            "message": {
                "data": base64.b64encode(json.dumps(data).encode("utf-8")).decode("utf-8"),
                "attributes": attributes,
            }
        }
        return CloudEvent({"type": "test-type", "source": "test-source"}, event_data)

    return _create_cloud_event


@pytest.fixture
def non_simulation_env():
    """Fixture to ensure SIMULATE_DEACTIVATION is not set."""
    # This fixture prevents test pollution. It ensures that tests that should
    # perform the real action don't accidentally run in simulation mode if the
    # environment variable is set externally.
    original_value = os.environ.pop("SIMULATE_DEACTIVATION", None)
    yield
    # After the test runs, restore the original environment variable if it existed.
    if original_value is not None:
        os.environ["SIMULATE_DEACTIVATION"] = original_value


def test_cost_less_than_budget_no_action(mock_clients, cloud_event_factory, caplog):
    """Test that no action is taken if the cost is less than or equal to the budget."""
    mock_billing_client, mock_budget_client = mock_clients
    event = cloud_event_factory(
        data={"costAmount": 100, "budgetAmount": 100, "budgetDisplayName": "Test Budget"},
        attributes={"budgetId": "test-budget", "billingAccountId": "test-billing-account"},
    )

    disable_billing_for_projects(event)

    # Assert that the key informational message is present, without checking for exact formatting.
    assert any("has not exceeded budget" in rec.message for rec in caplog.records)
    mock_budget_client.get_budget.assert_not_called()
    mock_billing_client.update_project_billing_info.assert_not_called()


def test_no_billing_account_id(mock_clients, cloud_event_factory, caplog):
    """Test that the function exits if no billingAccountId is present in the message attributes."""
    mock_billing_client, mock_budget_client = mock_clients
    event = cloud_event_factory(
        data={"costAmount": 120, "budgetAmount": 100, "budgetDisplayName": "Test Budget"},
        attributes={"budgetId": "test-budget"},
    )

    disable_billing_for_projects(event)

    assert any("No billingAccountId found" in rec.message for rec in caplog.records)
    mock_budget_client.get_budget.assert_not_called()
    mock_billing_client.update_project_billing_info.assert_not_called()


def test_no_budget_id(mock_clients, cloud_event_factory, caplog):
    """Test that the function exits if no budgetId is present in the message attributes."""
    mock_billing_client, mock_budget_client = mock_clients
    event = cloud_event_factory(
        data={"costAmount": 120, "budgetAmount": 100, "budgetDisplayName": "Test Budget"},
        attributes={"billingAccountId": "test-billing-account"},
    )

    disable_billing_for_projects(event)

    assert any("No budgetId found" in rec.message for rec in caplog.records)
    mock_budget_client.get_budget.assert_not_called()
    mock_billing_client.update_project_billing_info.assert_not_called()


def test_get_budget_api_error(mock_clients, cloud_event_factory, caplog):
    """Test that an error is logged if the call to get the budget fails."""
    mock_billing_client, mock_budget_client = mock_clients
    # Use side_effect to simulate an exception being raised when the mock is called.
    mock_budget_client.get_budget.side_effect = Exception("API Error")
    event = cloud_event_factory(
        data={"costAmount": 120, "budgetAmount": 100, "budgetDisplayName": "Test Budget"},
        attributes={"budgetId": "test-budget", "billingAccountId": "test-billing-account"},
    )

    disable_billing_for_projects(event)

    assert any("Error getting budget details" in rec.message for rec in caplog.records)
    mock_billing_client.update_project_billing_info.assert_not_called()


def test_budget_not_scoped_to_projects(mock_clients, cloud_event_factory, caplog):
    """Test that a warning is logged if the budget is not scoped to any projects."""
    mock_billing_client, mock_budget_client = mock_clients
    budget = Budget(budget_filter=Filter(projects=[]))
    mock_budget_client.get_budget.return_value = budget
    event = cloud_event_factory(
        data={"costAmount": 120, "budgetAmount": 100, "budgetDisplayName": "Test Budget"},
        attributes={"budgetId": "test-budget", "billingAccountId": "test-billing-account"},
    )

    disable_billing_for_projects(event)

    assert any("is not scoped to any projects" in rec.message for rec in caplog.records)
    mock_billing_client.update_project_billing_info.assert_not_called()


def test_disable_billing_for_single_project_success(mock_clients, cloud_event_factory, caplog, non_simulation_env):
    """Test that billing is successfully disabled for a single project."""
    mock_billing_client, mock_budget_client = mock_clients
    budget = Budget(budget_filter=Filter(projects=["projects/test-project-1"]))
    mock_budget_client.get_budget.return_value = budget
    mock_billing_client.get_project_billing_info.return_value.billing_enabled = True
    event = cloud_event_factory(
        data={"costAmount": 120, "budgetAmount": 100, "budgetDisplayName": "Test Budget"},
        attributes={"budgetId": "test-budget", "billingAccountId": "test-billing-account"},
    )

    disable_billing_for_projects(event)

    assert any("Successfully disabled billing for project projects/test-project-1" in rec.message for rec in caplog.records)
    # Check that the billing client was called correctly.
    # We use ANY because the exact ProjectBillingInfo object is complex to construct
    # and not critical to verify for this test's purpose.
    mock_billing_client.update_project_billing_info.assert_called_once_with(
        name="projects/test-project-1",
        project_billing_info=ANY
    )


def test_disable_billing_for_multiple_projects_success(mock_clients, cloud_event_factory, caplog, non_simulation_env):
    """Test that billing is disabled for all projects associated with the budget."""
    mock_billing_client, mock_budget_client = mock_clients
    budget = Budget(budget_filter=Filter(projects=["projects/test-project-1", "projects/test-project-2"]))
    mock_budget_client.get_budget.return_value = budget
    mock_billing_client.get_project_billing_info.return_value.billing_enabled = True
    event = cloud_event_factory(
        data={"costAmount": 120, "budgetAmount": 100, "budgetDisplayName": "Test Budget"},
        attributes={"budgetId": "test-budget", "billingAccountId": "test-billing-account"},
    )

    disable_billing_for_projects(event)

    # Check that success messages are logged for both projects.
    logs = " ".join(rec.message for rec in caplog.records)
    assert "Successfully disabled billing for project projects/test-project-1" in logs
    assert "Successfully disabled billing for project projects/test-project-2" in logs
    assert mock_billing_client.update_project_billing_info.call_count == 2


def test_disable_billing_permission_denied_error(mock_clients, cloud_event_factory, caplog, non_simulation_env):
    """Test that a permission denied error is logged correctly when disabling billing."""
    mock_billing_client, mock_budget_client = mock_clients
    budget = Budget(budget_filter=Filter(projects=["projects/test-project-1"]))
    mock_budget_client.get_budget.return_value = budget
    mock_billing_client.get_project_billing_info.return_value.billing_enabled = True
    mock_billing_client.update_project_billing_info.side_effect = exceptions.PermissionDenied("Permission Denied")
    event = cloud_event_factory(
        data={"costAmount": 120, "budgetAmount": 100, "budgetDisplayName": "Test Budget"},
        attributes={"budgetId": "test-budget", "billingAccountId": "test-billing-account"},
    )

    disable_billing_for_projects(event)

    assert any("Failed to disable billing for projects/test-project-1" in rec.message and "Permission Denied" in rec.message for rec in caplog.records)


def test_simulation_mode_enabled(mock_clients, cloud_event_factory, caplog):
    """Test that in simulation mode, the billing API is not actually called."""
    # Set the environment variable to activate simulation mode for this test.
    os.environ["SIMULATE_DEACTIVATION"] = "true"
    mock_billing_client, mock_budget_client = mock_clients
    budget = Budget(budget_filter=Filter(projects=["projects/test-project-1"]))
    mock_budget_client.get_budget.return_value = budget
    mock_billing_client.get_project_billing_info.return_value.billing_enabled = True
    event = cloud_event_factory(
        data={"costAmount": 120, "budgetAmount": 100, "budgetDisplayName": "Test Budget"},
        attributes={"budgetId": "test-budget", "billingAccountId": "test-billing-account"},
    )

    disable_billing_for_projects(event)

    assert any("SIMULATION MODE" in rec.message and "would have been disabled" in rec.message for rec in caplog.records)
    mock_billing_client.update_project_billing_info.assert_not_called()

    # Clean up the environment variable
    del os.environ["SIMULATE_DEACTIVATION"]


def test_billing_already_disabled(mock_clients, cloud_event_factory, caplog, non_simulation_env):
    """Test that no action is taken if billing is already disabled for a project."""
    mock_billing_client, mock_budget_client = mock_clients
    
    # Mock the budget response
    budget = Budget(budget_filter=Filter(projects=["projects/test-project-1"]))
    mock_budget_client.get_budget.return_value = budget
    
    # Mock the get_project_billing_info response to indicate billing is disabled
    mock_billing_client.get_project_billing_info.return_value.billing_enabled = False
    
    event = cloud_event_factory(
        data={"costAmount": 120, "budgetAmount": 100, "budgetDisplayName": "Test Budget"},
        attributes={"budgetId": "test-budget", "billingAccountId": "test-billing-account"},
    )

    disable_billing_for_projects(event)

    assert any("Billing is already disabled for project test-project-1" in rec.message for rec in caplog.records)
    mock_billing_client.update_project_billing_info.assert_not_called()


def test_billing_enabled_and_disabled_successfully(mock_clients, cloud_event_factory, caplog, non_simulation_env):
    """Test that billing is disabled if it is currently enabled."""
    mock_billing_client, mock_budget_client = mock_clients
    
    # Mock the budget response
    budget = Budget(budget_filter=Filter(projects=["projects/test-project-1"]))
    mock_budget_client.get_budget.return_value = budget
    
    # Mock the get_project_billing_info response to indicate billing is enabled
    mock_billing_client.get_project_billing_info.return_value.billing_enabled = True
    
    event = cloud_event_factory(
        data={"costAmount": 120, "budgetAmount": 100, "budgetDisplayName": "Test Budget"},
        attributes={"budgetId": "test-budget", "billingAccountId": "test-billing-account"},
    )

    disable_billing_for_projects(event)

    assert any("Successfully disabled billing for project projects/test-project-1" in rec.message for rec in caplog.records)
    mock_billing_client.get_project_billing_info.assert_called_once_with(name="projects/test-project-1")
    mock_billing_client.update_project_billing_info.assert_called_once_with(
        name="projects/test-project-1",
        project_billing_info=ANY
    )


def test_get_billing_info_generic_api_error_assumes_disabled(mock_clients, cloud_event_factory, caplog, non_simulation_env):
    """
    Test that if a generic error occurs while checking billing, it's assumed to be disabled.
    """
    mock_billing_client, mock_budget_client = mock_clients
    
    # Mock the budget response
    budget = Budget(budget_filter=Filter(projects=["projects/test-project-1"]))
    mock_budget_client.get_budget.return_value = budget
    
    # Simulate an exception when checking billing info
    mock_billing_client.get_project_billing_info.side_effect = Exception("API Error")
    
    event = cloud_event_factory(
        data={"costAmount": 120, "budgetAmount": 100, "budgetDisplayName": "Test Budget"},
        attributes={"budgetId": "test-budget", "billingAccountId": "test-billing-account"},
    )

    disable_billing_for_projects(event)

    logs = " ".join(rec.message for rec in caplog.records)
    assert "Unable to get billing info for project" in logs
    assert "Assuming billing is disabled" in logs
    mock_billing_client.update_project_billing_info.assert_not_called()