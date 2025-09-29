#!/bin/bash
# This script is meant to be sourced to set up your development environment.
# It configures gcloud, installs dependencies, and activates the virtualenv.
#
# Usage:
#   source ./setup-env.sh [--noauth]
#
# Options:
#   --noauth: Skip gcloud authentication.
#   -t, --target-env: Set the target environment (DEV or PROD). Defaults to DEV.

# --- Color and Style Definitions ---
RESET='\033[0m'
BOLD='\033[1m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'

# --- Parameter parsing ---
TARGET_ENV="DEV"
AUTH_ENABLED=true

while [[ $# -gt 0 ]]; do
    case "$1" in
        --noauth)
            AUTH_ENABLED=false
            shift
            ;;
        *)
            shift
            ;;
    esac
done


echo -e "${BLUE}${BOLD}--- ☁️  Configuring Google Cloud environment ---${RESET}"

# 1. Check for .env file
if [ ! -f .env ]; then
	echo -e "${RED}❌ Error: .env file not found.${RESET}"
	echo "Please create a .env file with your project variables and run this command again."
	return 1
fi

# 2. Source environment variables and export them
echo -e "Sourcing variables from ${BLUE}.env${RESET} file..."
set -a # automatically export all variables (allexport = on)
source .env
set +a # disable allexport mode

# 3. Authenticate with gcloud and configure project
if [ "$AUTH_ENABLED" = true ]; then
    echo -e "\n🔐 Authenticating with gcloud and setting project to ${BOLD}$GOOGLE_CLOUD_PROJECT...${RESET}"
    gcloud auth login --update-adc 2>&1 | grep -v -e '^$' -e 'WSL' -e 'xdg-open' # Suppress any annoying WSL messages
    gcloud config set project "$GOOGLE_CLOUD_PROJECT"
    gcloud auth application-default set-quota-project "$GOOGLE_CLOUD_PROJECT"
else
    echo -e "\n${YELLOW}Skipping gcloud authentication as requested.${RESET}"
    gcloud config set project "$GOOGLE_CLOUD_PROJECT"
fi

echo -e "\n${BLUE}--- Current gcloud project configuration ---${RESET}"
gcloud config list project
echo -e "${BLUE}------------------------------------------${RESET}"

# 5. Get project numbers
echo "Getting project number..."
export PROJECT_NUMBER=$(gcloud projects describe $GOOGLE_CLOUD_PROJECT --format="value(projectNumber)")
echo -e "${BOLD}PROJECT_NUMBER:${RESET} $PROJECT_NUMBER"
echo -e "${BLUE}------------------------------------------${RESET}"

# 6. Sync Python dependencies and activate venv
echo "Activating Python virtual environment..."
source .venv/bin/activate

echo "Syncing python dependencies with uv..."
uv sync --dev --extra jupyter

echo -e "\n${GREEN}✅ Environment setup complete with project ${BOLD}$GOOGLE_CLOUD_PROJECT${RESET}${GREEN}. Your shell is now configured.${RESET}"