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
  - `budgetDisplayName` (str): The display name of the budget.

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

logging_client = None

# Calling `setup_logging()` intercepts Python's standard `logging` module
# and attaches a Cloud Logging handler to it. This automatically 
# sends all standard logger output (like logger.info) to GCP.
if os.environ.get("DISABLE_CLOUD_LOGGING", "false").lower() != "true":
    logging_client = google.cloud.logging.Client()
    logging_client.setup_logging(log_level=log_level_num)

app_name = "billing-killswitch"
logger = logging.getLogger(app_name)
logger.setLevel(log_level_num)

# Ensure local fallback logging works if cloud logging is disabled
if os.environ.get("DISABLE_CLOUD_LOGGING", "false").lower() == "true":
    logging.basicConfig(level=log_level_num)

billing_client = billing_v1.CloudBillingClient()
budget_client = BudgetServiceClient()

def _parse_and_validate_message(cloud_event: CloudEvent) -> dict | None:
    """Parses and validates the incoming Pub/Sub message."""
    # The Pub/Sub message is base64-encoded
    message_data = base64.b64decode(cloud_event.data["message"]["data"]).decode("utf-8")
    message_json = json.loads(message_data)
    attributes = cloud_event.data["message"]["attributes"]

    logger.debug(f"Pub/Sub message attributes: {attributes}")
    logger.debug(f"Pub/Sub message data: {message_data}")

    budget_name = message_json.get("budgetDisplayName", "Unknown Budget")

    if "costAmount" not in message_json or "budgetAmount" not in message_json:
        logger.error(f"Budget '{budget_name}': Missing 'costAmount' or 'budgetAmount' in message payload. Aborting for safety.")
        return None

    cost_amount = message_json["costAmount"]
    budget_amount = message_json["budgetAmount"]

    # Only disable billing if the cost has exceeded the budget
    if cost_amount <= budget_amount:
        logger.info(f"Budget '{budget_name}': "
                    f"{cost_amount} has not exceeded budget {budget_amount}. No action taken.")
        return None

    # Get the budget ID and billing_account_id from the message attributes
    budget_id = attributes.get("budgetId", "")
    billing_account_id = attributes.get("billingAccountId", "")
    if not billing_account_id:
        logger.error("No billingAccountId found in message payload.")
        return None
    
    if not budget_id:
        logger.error("No budgetId found in message attributes.")
        return None

    return {
        "budget_name": budget_name,
        "cost_amount": cost_amount,
        "budget_amount": budget_amount,
        "budget_id": budget_id,
        "billing_account_id": billing_account_id
    }

@functions_framework.cloud_event
def disable_billing_for_projects(cloud_event: CloudEvent):
    """
    Cloud Function to disable billing for projects based on a Pub/Sub message from a billing alert.
    """
    # Check for simulation mode
    simulate_deactivation = os.getenv("SIMULATE_DEACTIVATION", "false").lower() == "true"

    logger.debug("Invoked from Pub/Sub message.")

    parsed_msg = _parse_and_validate_message(cloud_event)
    if not parsed_msg:
        return

    budget_name = parsed_msg["budget_name"]
    cost_amount = parsed_msg["cost_amount"]
    budget_amount = parsed_msg["budget_amount"]
    budget_id = parsed_msg["budget_id"]
    billing_account_id = parsed_msg["billing_account_id"]

    logger.info(f"Budget '{budget_name}': {cost_amount} has exceeded budget {budget_amount}.")

    try:
        # Use the budget ID to get the budget details
        full_budget_name = f"billingAccounts/{billing_account_id}/budgets/{budget_id}"
        budget = budget_client.get_budget(name=full_budget_name)
    except Exception as e:
        logger.error(f"Budget '{budget_name}': Error getting budget details: {e}")
        return

    # The budget filter contains the projects the budget is scoped to
    if not budget.budget_filter or not budget.budget_filter.projects:
        logger.warning(f"Budget '{budget_name}' is not scoped to any projects. No action taken.")
        return

    # Get all projects associated with this budget
    project_ids = [p.split("/")[1] for p in budget.budget_filter.projects]

    for project_id in project_ids:
        project_name = f"projects/{project_id}"
        
        # Determine whether billing is enabled for the project. 
        # Returns True if enabled, False if disabled, and None if an error occurred.
        billing_enabled = _is_billing_enabled_for_project(project_name)
        
        if billing_enabled is True:
            logger.info(f"Budget '{budget_name}': Disabling billing for {project_id}...")
            
            if simulate_deactivation:
                logger.info(f"SIMULATION MODE: Billing would have been disabled for project {project_id} "
                            f"for budget {budget_name}.")
            else:
                _disable_billing_for_project(project_name)
        elif billing_enabled is False:
            logger.info(f"Budget '{budget_name}': Billing is already disabled for project {project_id}.")
        # If billing_enabled is None, an error occurred and was already logged in _is_billing_enabled_for_project

def _is_billing_enabled_for_project(project_name: str) -> bool | None:
    """Determine whether billing is enabled for a project.

    Args:
        project_name: Project to check, with the format 'projects/<project_id>'.

    Returns:
        Whether project has billing enabled or not, or None if an error occurred.
    """
    try:
        logger.debug(f"Getting billing info for project '{project_name}'...")
        response = billing_client.get_project_billing_info(name=project_name)

        return response.billing_enabled
    except exceptions.PermissionDenied as e:
        logger.error(f"Permission denied for {project_name}. "
                     f"Ensure service account has 'roles/billing.projectManager' on the project: {e}")
        return None
    except Exception as e:
        logger.warning(f"Unable to get billing info for project {project_name}. "
                       f"Error message: {e}")
        return None

    
def _disable_billing_for_project(project_name: str) -> None:
    """Disable billing for a project by removing its billing account.

    Args:
        project_name: Project to disable billing for, with the format 'projects/<project_id>'.
    """

    # Find more information about `updateBillingInfo` API method here:
    # https://cloud.google.com/billing/docs/reference/rest/v1/projects/updateBillingInfo
    try:
        # To disable billing set the `billing_account_name` field to empty
        project_billing_info = billing_v1.ProjectBillingInfo(billing_account_name="")
        billing_client.update_project_billing_info(name=project_name, project_billing_info=project_billing_info)

        logger.info(f"Successfully disabled billing for project {project_name}")
    except exceptions.PermissionDenied as e:
        logger.error(f"Failed to disable billing for {project_name}, check permissions: {e}")
    except Exception as e:
        logger.error(f"Error disabling billing for project {project_name}: {e}")
