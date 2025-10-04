
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
    with patch("src.main.billing_client", autospec=True) as mock_billing_client, \
         patch("src.main.budget_client", autospec=True) as mock_budget_client:
        yield mock_billing_client, mock_budget_client


@pytest.fixture
def cloud_event_factory():
    """Factory to create a CloudEvent for testing."""

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
    original_value = os.environ.pop("SIMULATE_DEACTIVATION", None)
    yield
    if original_value is not None:
        os.environ["SIMULATE_DEACTIVATION"] = original_value


def test_cost_less_than_budget_no_action(mock_clients, cloud_event_factory, caplog):
    """Test that no action is taken if the cost is less than or equal to the budget."""
    mock_billing_client, mock_budget_client = mock_clients
    event = cloud_event_factory(
        data={"costAmount": 100, "budgetAmount": 100},
        attributes={"budgetId": "test-budget", "billingAccountId": "test-billing-account"},
    )

    disable_billing_for_projects(event)

    assert "Cost (100) has not exceeded budget (100). No action taken." in caplog.text
    mock_budget_client.get_budget.assert_not_called()
    mock_billing_client.update_project_billing_info.assert_not_called()


def test_no_billing_account_id(mock_clients, cloud_event_factory, caplog):
    """Test that the function exits if no billingAccountId is present in the message attributes."""
    mock_billing_client, mock_budget_client = mock_clients
    event = cloud_event_factory(
        data={"costAmount": 120, "budgetAmount": 100},
        attributes={"budgetId": "test-budget"},
    )

    disable_billing_for_projects(event)

    assert "No billingAccountId found in message payload." in caplog.text
    mock_budget_client.get_budget.assert_not_called()
    mock_billing_client.update_project_billing_info.assert_not_called()


def test_no_budget_id(mock_clients, cloud_event_factory, caplog):
    """Test that the function exits if no budgetId is present in the message attributes."""
    mock_billing_client, mock_budget_client = mock_clients
    event = cloud_event_factory(
        data={"costAmount": 120, "budgetAmount": 100},
        attributes={"billingAccountId": "test-billing-account"},
    )

    disable_billing_for_projects(event)

    assert "No budgetId found in message attributes." in caplog.text
    mock_budget_client.get_budget.assert_not_called()
    mock_billing_client.update_project_billing_info.assert_not_called()


def test_get_budget_api_error(mock_clients, cloud_event_factory, caplog):
    """Test that an error is logged if the call to get the budget fails."""
    mock_billing_client, mock_budget_client = mock_clients
    mock_budget_client.get_budget.side_effect = Exception("API Error")
    event = cloud_event_factory(
        data={"costAmount": 120, "budgetAmount": 100},
        attributes={"budgetId": "test-budget", "billingAccountId": "test-billing-account"},
    )

    disable_billing_for_projects(event)

    assert "Error getting budget details: API Error" in caplog.text
    mock_billing_client.update_project_billing_info.assert_not_called()


def test_budget_not_scoped_to_projects(mock_clients, cloud_event_factory, caplog):
    """Test that a warning is logged if the budget is not scoped to any projects."""
    mock_billing_client, mock_budget_client = mock_clients
    budget = Budget(budget_filter=Filter(projects=[]))
    mock_budget_client.get_budget.return_value = budget
    event = cloud_event_factory(
        data={"costAmount": 120, "budgetAmount": 100},
        attributes={"budgetId": "test-budget", "billingAccountId": "test-billing-account"},
    )

    disable_billing_for_projects(event)

    assert "Budget test-budget is not scoped to any projects. No action taken." in caplog.text
    mock_billing_client.update_project_billing_info.assert_not_called()


def test_disable_billing_for_single_project_success(mock_clients, cloud_event_factory, caplog, non_simulation_env):
    """Test that billing is successfully disabled for a single project."""
    mock_billing_client, mock_budget_client = mock_clients
    budget = Budget(budget_filter=Filter(projects=["projects/test-project-1"]))
    mock_budget_client.get_budget.return_value = budget
    event = cloud_event_factory(
        data={"costAmount": 120, "budgetAmount": 100},
        attributes={"budgetId": "test-budget", "billingAccountId": "test-billing-account"},
    )

    disable_billing_for_projects(event)

    assert "Successfully disabled billing for project test-project-1" in caplog.text
    mock_billing_client.update_project_billing_info.assert_called_once_with(
        name="projects/test-project-1",
        project_billing_info=ANY
    )


def test_disable_billing_for_multiple_projects_success(mock_clients, cloud_event_factory, caplog, non_simulation_env):
    """Test that billing is disabled for all projects associated with the budget."""
    mock_billing_client, mock_budget_client = mock_clients
    budget = Budget(budget_filter=Filter(projects=["projects/test-project-1", "projects/test-project-2"]))
    mock_budget_client.get_budget.return_value = budget
    event = cloud_event_factory(
        data={"costAmount": 120, "budgetAmount": 100},
        attributes={"budgetId": "test-budget", "billingAccountId": "test-billing-account"},
    )

    disable_billing_for_projects(event)

    assert "Successfully disabled billing for project test-project-1" in caplog.text
    assert "Successfully disabled billing for project test-project-2" in caplog.text
    assert mock_billing_client.update_project_billing_info.call_count == 2


def test_disable_billing_permission_denied_error(mock_clients, cloud_event_factory, caplog, non_simulation_env):
    """Test that a permission denied error is logged correctly when disabling billing."""
    mock_billing_client, mock_budget_client = mock_clients
    budget = Budget(budget_filter=Filter(projects=["projects/test-project-1"]))
    mock_budget_client.get_budget.return_value = budget
    mock_billing_client.update_project_billing_info.side_effect = exceptions.PermissionDenied("Permission Denied")
    event = cloud_event_factory(
        data={"costAmount": 120, "budgetAmount": 100},
        attributes={"budgetId": "test-budget", "billingAccountId": "test-billing-account"},
    )

    disable_billing_for_projects(event)

    assert "Failed to disable billing for projects/test-project-1, check permissions: 403 Permission Denied" in caplog.text


def test_simulation_mode_enabled(mock_clients, cloud_event_factory, caplog):
    """Test that in simulation mode, the billing API is not actually called."""
    os.environ["SIMULATE_DEACTIVATION"] = "true"
    mock_billing_client, mock_budget_client = mock_clients
    budget = Budget(budget_filter=Filter(projects=["projects/test-project-1"]))
    mock_budget_client.get_budget.return_value = budget
    event = cloud_event_factory(
        data={"costAmount": 120, "budgetAmount": 100},
        attributes={"budgetId": "test-budget", "billingAccountId": "test-billing-account"},
    )

    disable_billing_for_projects(event)

    assert "SIMULATION MODE: Billing would have been disabled for project test-project-1." in caplog.text
    mock_billing_client.update_project_billing_info.assert_not_called()

    # Clean up the environment variable
    del os.environ["SIMULATE_DEACTIVATION"]
