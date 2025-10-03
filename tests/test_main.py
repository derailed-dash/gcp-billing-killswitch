
import base64
import json
import unittest
from unittest.mock import MagicMock, PropertyMock, patch

from google.cloud.billing_v1.types import ProjectBillingInfo

from main import disable_billing_for_projects


class TestDisableBilling(unittest.TestCase):
    def _create_mock_event(self, data, attributes: dict):
        """Helper function to create a mock CloudEvent."""
        event = MagicMock()
        encoded_data = base64.b64encode(json.dumps(data).encode("utf-8"))

        # Mock the nested structure of the cloud event
        type(event).data = PropertyMock(
            return_value={"message": {"data": encoded_data, "attributes": attributes}}
        )
        return event

    @patch("main.billing_client")
    @patch("main.budget_client")
    @patch("main.logging_client")
    def test_billing_disabled_when_cost_exceeds_budget(
        self, mock_logging, mock_budget_client, mock_billing_client
    ):
        """Test that billing is disabled when cost is greater than budget."""
        # Mock budget response
        mock_budget = MagicMock()
        mock_budget.budget_filter.projects = ["projects/test-project-123"]
        mock_budget_client.get_budget.return_value = mock_budget

        # Mock Pub/Sub message
        data = {
            "costAmount": 120.0,
            "budgetAmount": 100.0,
            "billingAccountId": "billing-account-id",
        }
        attributes: dict[str, str] = {"budgetId": "test-budget-id"}
        event = self._create_mock_event(data, attributes)

        disable_billing_for_projects(event)

        # Assert that the billing client was called to update the project
        mock_billing_client.update_project_billing_info.assert_called_once_with(
            name="projects/test-project-123",
            project_billing_info=ProjectBillingInfo(billing_account_name=""),
        )

    @patch("main.billing_client")
    @patch("main.budget_client")
    @patch("main.logging_client")
    def test_billing_not_disabled_when_cost_equals_budget(
        self, mock_logging, mock_budget_client, mock_billing_client
    ):
        """Test that billing is not disabled when cost is equal to the budget."""
        data = {
            "costAmount": 100.0,
            "budgetAmount": 100.0,
            "billingAccountId": "billing-account-id",
        }
        attributes: dict[str, str] = {"budgetId": "test-budget-id"}
        event = self._create_mock_event(data, attributes)

        disable_billing_for_projects(event)

        # Assert that the billing client was NOT called
        mock_billing_client.update_project_billing_info.assert_not_called()

    @patch("main.billing_client")
    @patch("main.budget_client")
    @patch("main.logging_client")
    def test_no_action_if_budgetId_is_missing(
        self, mock_logging, mock_budget_client, mock_billing_client
    ):
        """Test that no action is taken if the budgetId is missing from attributes."""
        data = {
            "costAmount": 120.0,
            "budgetAmount": 100.0,
            "billingAccountId": "billing-account-id",
        }
        attributes: dict[str, str] = {}
        event = self._create_mock_event(data, attributes)

        disable_billing_for_projects(event)

        mock_billing_client.update_project_billing_info.assert_not_called()

    @patch("main.billing_client")
    @patch("main.budget_client")
    @patch("main.logging_client")
    def test_no_action_if_billingAccountId_is_missing(
        self, mock_logging, mock_budget_client, mock_billing_client
    ):
        """Test that no action is taken if the billingAccountId is missing from the payload."""
        data = {"costAmount": 120.0, "budgetAmount": 100.0}
        attributes: dict[str, str] = {"budgetId": "test-budget-id"}
        event = self._create_mock_event(data, attributes)

        disable_billing_for_projects(event)

        mock_billing_client.update_project_billing_info.assert_not_called()

    @patch("main.billing_client")
    @patch("main.budget_client")
    @patch("main.logging_client")
    def test_no_action_if_budget_not_scoped_to_project(
        self, mock_logging, mock_budget_client, mock_billing_client
    ):
        """Test that no action is taken if the budget is not scoped to a project."""
        mock_budget = MagicMock()
        mock_budget.budget_filter.projects = []  # No project in filter
        mock_budget_client.get_budget.return_value = mock_budget

        data = {
            "costAmount": 120.0,
            "budgetAmount": 100.0,
            "billingAccountId": "billing-account-id",
        }
        attributes: dict[str, str] = {"budgetId": "test-budget-id"}
        event = self._create_mock_event(data, attributes)

        disable_billing_for_projects(event)

        mock_billing_client.update_project_billing_info.assert_not_called()

    @patch("main.billing_client")
    @patch("main.budget_client")
    @patch("main.logging_client")
    def test_billing_disabled_for_multiple_projects(
        self, mock_logging, mock_budget_client, mock_billing_client
    ):
        """Test that billing is disabled for all projects when a budget is scoped to multiple projects."""
        # Mock budget response with multiple projects
        mock_budget = MagicMock()
        mock_budget.budget_filter.projects = [
            "projects/test-project-123",
            "projects/test-project-456",
        ]
        mock_budget_client.get_budget.return_value = mock_budget

        # Mock Pub/Sub message
        data = {
            "costAmount": 120.0,
            "budgetAmount": 100.0,
            "billingAccountId": "billing-account-id",
        }
        attributes: dict[str, str] = {"budgetId": "test-budget-id"}
        event = self._create_mock_event(data, attributes)

        disable_billing_for_projects(event)

        # Assert that the billing client was called for both projects
        self.assertEqual(mock_billing_client.update_project_billing_info.call_count, 2)
        mock_billing_client.update_project_billing_info.assert_any_call(
            name="projects/test-project-123",
            project_billing_info=ProjectBillingInfo(billing_account_name=""),
        )
        mock_billing_client.update_project_billing_info.assert_any_call(
            name="projects/test-project-456",
            project_billing_info=ProjectBillingInfo(billing_account_name=""),
        )

    @patch.dict("os.environ", {"SIMULATE_DEACTIVATION": "true"})
    @patch("main.billing_client")
    @patch("main.budget_client")
    @patch("main.logging.info")
    def test_simulate_deactivation_flag(
        self, mock_log_info, mock_budget_client, mock_billing_client
    ):
        """Test that billing is not disabled when SIMULATE_DEACTIVATION is true."""
        # Mock budget response
        mock_budget = MagicMock()
        mock_budget.budget_filter.projects = ["projects/test-project-123"]
        mock_budget_client.get_budget.return_value = mock_budget

        # Mock Pub/Sub message
        data = {
            "costAmount": 120.0,
            "budgetAmount": 100.0,
            "billingAccountId": "billing-account-id",
        }
        attributes: dict[str, str] = {"budgetId": "test-budget-id"}
        event = self._create_mock_event(data, attributes)

        disable_billing_for_projects(event)

        # Assert that the billing client was NOT called to update the project
        mock_billing_client.update_project_billing_info.assert_not_called()
        # Assert that the simulation log message was called
        mock_log_info.assert_any_call(
            "SIMULATION MODE: Billing would have been disabled for project test-project-123."
        )


    def tearDown(self):
        """Close the logging client after each test."""
        from main import logging_client
        logging_client.close()
