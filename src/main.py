"""
This script contains a Google Cloud Function designed to automatically disable billing for a Google Cloud project.

The function is triggered by a Pub/Sub message, which is published by a Cloud Billing budget alert. 
When a project's spending exceeds a defined threshold, the alert is sent, and this function is invoked.

The function parses the incoming Pub/Sub message to identify the project and then uses the Cloud Billing API 
to detach the project from its billing account, effectively disabling billing.

**⚠️ Warning: This is a destructive action.** Disconnecting a project from its billing account will 
stop all paid services. The project enters a 30-day grace period. If billing is not re-enabled within this period, 
the project and all its resources may be **permanently deleted**.
"""
import base64
import json
import os

import functions_framework
from google.cloud import billing_v1, logging
from google.cloud.billing.budgets_v1 import BudgetServiceClient

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
        logger.log_text(f"Budget {budget_id} is not scoped to any projects. No action taken.", severity="WARNING")
        return

    project_ids = [p.split("/")[1] for p in budget.budget_filter.projects]
    billing_client = billing_v1.CloudBillingClient()

    for project_id in project_ids:
        logger.log_text(f"Budget exceeded for project: {project_id}. Disabling billing.")
        
        project_billing_info = {
            "name": f"projects/{project_id}/billingInfo",
            "billing_account_name": "",  # Setting to an empty string disables billing
        }

        # Check for simulation mode
        simulate_deactivation = os.getenv("SIMULATE_DEACTIVATION", "false").lower() == "true"

        if simulate_deactivation:
            logger.log_text(f"SIMULATION MODE: Billing would have been disabled for project {project_id}.")
        else:
            try:
                billing_client.update_project_billing_info(project_billing_info)
                logger.log_text(f"Successfully disabled billing for project {project_id}.")
            except Exception as e:
                logger.log_text(f"Error disabling billing for project {project_id}: {e}", severity="ERROR")

