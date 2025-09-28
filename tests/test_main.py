
import base64
import json
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

# Add the src directory to the Python path to allow importing main
import sys
sys.path.insert(0, '../src')

from main import disable_billing_for_project

class TestDisableBilling(unittest.TestCase):

    def _create_mock_event(self, data, attributes):
        """Helper function to create a mock CloudEvent."""
        event = MagicMock()
        encoded_data = base64.b64encode(json.dumps(data).encode('utf-8'))
        
        # Mock the nested structure of the cloud event
        type(event).data = PropertyMock(return_value={
            "message": {
                "data": encoded_data,
                "attributes": attributes
            }
        })
        return event

    @patch('main.billing_v1.CloudBillingClient')
    @patch('main.BudgetServiceClient')
    @patch('main.logging.Client')
    def test_billing_disabled_when_cost_exceeds_budget(self, mock_logging, mock_budget_client, mock_billing_client):
        """Test that billing is disabled when cost is greater than budget."""
        # Mock budget response
        mock_budget = MagicMock()
        mock_budget.budget_filter.projects = ['projects/test-project-123']
        mock_budget_client.return_value.get_budget.return_value = mock_budget

        # Mock Pub/Sub message
        data = {"costAmount": 120.0, "budgetAmount": 100.0, "billingAccountId": "billing-account-id"}
        attributes = {"budgetId": "test-budget-id"}
        event = self._create_mock_event(data, attributes)

        disable_billing_for_project(event)

        # Assert that the billing client was called to update the project
        mock_billing_client.return_value.update_project_billing_info.assert_called_once_with({
            'name': 'projects/test-project-123/billingInfo',
            'billing_account_name': ''
        })

    @patch('main.billing_v1.CloudBillingClient')
    @patch('main.BudgetServiceClient')
    @patch('main.logging.Client')
    def test_billing_not_disabled_when_cost_equals_budget(self, mock_logging, mock_budget_client, mock_billing_client):
        """Test that billing is not disabled when cost is equal to the budget."""
        data = {"costAmount": 100.0, "budgetAmount": 100.0, "billingAccountId": "billing-account-id"}
        attributes = {"budgetId": "test-budget-id"}
        event = self._create_mock_event(data, attributes)

        disable_billing_for_project(event)

        # Assert that the billing client was NOT called
        mock_billing_client.return_value.update_project_billing_info.assert_not_called()

    @patch('main.billing_v1.CloudBillingClient')
    @patch('main.BudgetServiceClient')
    @patch('main.logging.Client')
    def test_no_action_if_budgetId_is_missing(self, mock_logging, mock_budget_client, mock_billing_client):
        """Test that no action is taken if the budgetId is missing from attributes."""
        data = {"costAmount": 120.0, "budgetAmount": 100.0, "billingAccountId": "billing-account-id"}
        attributes = {}
        event = self._create_mock_event(data, attributes)

        disable_billing_for_project(event)

        mock_billing_client.return_value.update_project_billing_info.assert_not_called()

    @patch('main.billing_v1.CloudBillingClient')
    @patch('main.BudgetServiceClient')
    @patch('main.logging.Client')
    def test_no_action_if_billingAccountId_is_missing(self, mock_logging, mock_budget_client, mock_billing_client):
        """Test that no action is taken if the billingAccountId is missing from the payload."""
        data = {"costAmount": 120.0, "budgetAmount": 100.0}
        attributes = {"budgetId": "test-budget-id"}
        event = self._create_mock_event(data, attributes)

        disable_billing_for_project(event)

        mock_billing_client.return_value.update_project_billing_info.assert_not_called()

    @patch('main.billing_v1.CloudBillingClient')
    @patch('main.BudgetServiceClient')
    @patch('main.logging.Client')
    def test_no_action_if_budget_not_scoped_to_project(self, mock_logging, mock_budget_client, mock_billing_client):
        """Test that no action is taken if the budget is not scoped to a project."""
        mock_budget = MagicMock()
        mock_budget.budget_filter.projects = [] # No project in filter
        mock_budget_client.return_value.get_budget.return_value = mock_budget

        data = {"costAmount": 120.0, "budgetAmount": 100.0, "billingAccountId": "billing-account-id"}
        attributes = {"budgetId": "test-budget-id"}
        event = self._create_mock_event(data, attributes)

        disable_billing_for_project(event)

        mock_billing_client.return_value.update_project_billing_info.assert_not_called()

if __name__ == '__main__':
    unittest.main()
