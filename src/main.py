
import base64
import json
import os

import functions_framework
from google.cloud import billing_v1
from google.cloud.billing.budgets_v1 import BudgetServiceClient
from google.cloud import logging

# Set up logging
logging_client = logging.Client()
log_name = "billing-disabler"
logger = logging_client.logger(log_name)

@functions_framework.cloud_event
def disable_billing_for_project(cloud_event):
    """
    Cloud Function to disable billing for a project based on a Pub/Sub message from a billing alert.
    """
    # The Pub/Sub message is base64-encoded
    message_data = base64.b64decode(cloud_event.data["message"]["data"]).decode("utf-8")
    message_json = json.loads(message_data)

    cost_amount = message_json.get("costAmount", 0.0)
    budget_amount = message_json.get("budgetAmount", 0.0)
    billing_account_id = message_json.get("billingAccountId")

    if not billing_account_id:
        logger.log_text("No billingAccountId found in message payload.", severity="ERROR")
        return

    # Only disable billing if the cost has exceeded the budget
    if cost_amount <= budget_amount:
        logger.log_text(f"Cost ({cost_amount}) has not exceeded budget ({budget_amount}). No action taken.")
        return

    # Get the budget ID from the message attributes
    attributes = cloud_event.data["message"].get("attributes", {})
    budget_id = attributes.get("budgetId")

    if not budget_id:
        logger.log_text("No budgetId found in message attributes.", severity="ERROR")
        return

    # Use the budget ID to get the budget details
    budget_client = BudgetServiceClient()
    budget_name = f"billingAccounts/{billing_account_id}/budgets/{budget_id}"
    
    try:
        budget = budget_client.get_budget(name=budget_name)
    except Exception as e:
        logger.log_text(f"Error getting budget details: {e}", severity="ERROR")
        return

    # The budget filter contains the projects the budget is scoped to
    if not budget.budget_filter or not budget.budget_filter.projects:
        logger.log_text(f"Budget {budget_id} is not scoped to a single project.", severity="WARNING")
        return

    # Extract the project ID (e.g., "projects/123456789012")
    target_project_id_full = budget.budget_filter.projects[0]
    target_project_id = target_project_id_full.split("/")[1]


    logger.log_text(f"Budget exceeded for project: {target_project_id}. Disabling billing.")

    billing_client = billing_v1.CloudBillingClient()
    project_billing_info = {
        "name": f"projects/{target_project_id}/billingInfo",
        "billing_account_name": "",  # Setting to an empty string disables billing
    }

    try:
        billing_client.update_project_billing_info(project_billing_info)
        logger.log_text(f"Successfully disabled billing for project {target_project_id}.")
    except Exception as e:
        logger.log_text(f"Error disabling billing for project {target_project_id}: {e}", severity="ERROR")

