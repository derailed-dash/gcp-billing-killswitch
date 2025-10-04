"""
This script contains a Google Cloud Function designed to automatically disable billing for 
any Google Cloud projects associated with an exceeded budget.

The function is triggered by a Pub/Sub message, which is published by a Cloud Billing budget alert. 
When a project's spending exceeds a defined threshold, the alert is sent, and this function is invoked.
The function parses the incoming Pub/Sub message to identify the associated project(s)
and then uses the Cloud Billing API to detach the project from its billing account, 
effectively disabling billing.

The Pub/Sub message is expected to have the following format:

- **Message Payload (JSON):**
  - `costAmount` (float): The amount of cost that has been incurred.
  - `budgetAmount` (float): The budgeted amount.

- **Message Attributes:**
  - `billingAccountId` (str): The ID of the billing account.
  - `budgetId` (str): The ID of the budget.

**⚠️ Warning: This is a destructive action.** Disconnecting a project from its billing account will 
stop all paid services.
"""
import base64
import json
import logging
import os

import functions_framework
import google.cloud.logging
from cloudevents.http.event import CloudEvent
from google.api_core import exceptions
from google.cloud import billing_v1
from google.cloud.billing.budgets_v1 import BudgetServiceClient

log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
log_level_num = getattr(logging, log_level, logging.INFO)

# Configure a Cloud Logging handler and integrate it with Python's logging module
logging_client = google.cloud.logging.Client()
logging_client.setup_logging(log_level=log_level_num) 

app_name = "billing-killswitch"
logger = logging_client.logger(app_name)

billing_client = billing_v1.CloudBillingClient()
budget_client = BudgetServiceClient()


@functions_framework.cloud_event
def disable_billing_for_projects(cloud_event: CloudEvent):
    """
    Cloud Function to disable billing for projects based on a Pub/Sub message from a billing alert.
    """
    logging.info(f"{app_name} Cloud Run Function invoked from Pub/Sub message.")

    # The Pub/Sub message is base64-encoded
    message_data = base64.b64decode(cloud_event.data["message"]["data"]).decode("utf-8")
    message_json = json.loads(message_data)
    attributes = cloud_event.data["message"]["attributes"]

    logging.debug(f"Pub/Sub message attributes: {attributes}")
    logging.debug(f"Pub/Sub message data: {message_data}")

    cost_amount = message_json["costAmount"]
    budget_amount = message_json["budgetAmount"]

    # Only disable billing if the cost has exceeded the budget
    if cost_amount <= budget_amount:
        logging.info(f"Cost ({cost_amount}) has not exceeded budget ({budget_amount}). No action taken.")
        return

    # Get the budget ID and billing_account_id from the message attributes
    budget_id = attributes.get("budgetId", "")
    billing_account_id = attributes.get("billingAccountId", "")
    if not billing_account_id:
        logging.error("No billingAccountId found in message payload.")
        return
    
    if not budget_id:
        logging.error("No budgetId found in message attributes.")
        return

    # Use the budget ID to get the budget details
    budget_name = f"billingAccounts/{billing_account_id}/budgets/{budget_id}"

    try:
        logging.info(f"Cost {cost_amount} has exceeded budget {budget_amount} for budget {budget_id}.")
        budget = budget_client.get_budget(name=budget_name)
    except Exception as e:
        logging.error(f"Error getting budget details: {e}")
        return

    # The budget filter contains the projects the budget is scoped to
    if not budget.budget_filter or not budget.budget_filter.projects:
        logging.warning(f"Budget {budget_id} is not scoped to any projects. No action taken.")
        return

    project_ids = [p.split("/")[1] for p in budget.budget_filter.projects]

    for project_id in project_ids:
        logging.info(f"Disabling billing for {project_id}...")

        # Check for simulation mode
        simulate_deactivation = os.getenv("SIMULATE_DEACTIVATION", "false").lower() == "true"

        if simulate_deactivation:
            logging.info(f"SIMULATION MODE: Billing would have been disabled for project {project_id}.")
        else:
            _disable_billing_for_project(project_id)


def _disable_billing_for_project(project_id: str) -> None:
    """Disable billing for a project by removing its billing account.

    Args:
        project_id: ID of the project to disable billing for.
    """
    project_name = f"projects/{project_id}"

    # Find more information about `updateBillingInfo` API method here:
    # https://cloud.google.com/billing/docs/reference/rest/v1/projects/updateBillingInfo
    try:
        # To disable billing set the `billing_account_name` field to empty
        project_billing_info = billing_v1.ProjectBillingInfo(billing_account_name="")
        billing_client.update_project_billing_info(name=project_name, project_billing_info=project_billing_info)

        logging.info(f"Successfully disabled billing for project {project_id}")
    except exceptions.PermissionDenied as e:
        logging.error(f"Failed to disable billing for {project_name}, check permissions: {e}")
    except Exception as e:
        logging.error(f"Error disabling billing for project {project_name}: {e}")
