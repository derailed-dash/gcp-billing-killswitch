SHELL := /bin/bash

# Install dependencies using uv package manager
install:
	@command -v uv >/dev/null 2>&1 || { echo "uv is not installed. Installing uv..."; curl -LsSf https://astral.sh/uv/0.6.12/install.sh | sh; source $HOME/.local/bin/env; }
	uv sync --dev

# Run unit and integration tests
test:
	@test -n "$(GOOGLE_CLOUD_PROJECT)" || (echo "Error: GOOGLE_CLOUD_PROJECT is not set. Setup environment before running tests" && exit 1)
	uv run pytest tests

# Run code quality checks (codespell, ruff, mypy)
lint:
	@echo "Running code quality checks..."
	uv sync --dev
	uv run codespell -s
	uv run ruff check . --diff
	uv run mypy .

# Deploy the Cloud Run Function
deploy:
	@if [ ! -f .env ]; then echo "Error: .env file not found."; exit 1; fi
	@source .env && \
	export SERVICE_ACCOUNT_NAME="$$FUNCTION_NAME-sa" && \
	export SERVICE_ACCOUNT_EMAIL="$$SERVICE_ACCOUNT_NAME@$$GOOGLE_CLOUD_PROJECT.iam.gserviceaccount.com" && \
	gcloud run deploy $$FUNCTION_NAME \
	  --base-image=python312 \
	  --project=$$GOOGLE_CLOUD_PROJECT \
	  --region=$$GOOGLE_CLOUD_REGION \
	  --source=./src \
	  --function=disable_billing_for_projects \
	  --no-allow-unauthenticated \
	  --execution-environment=gen1 \
	  --cpu=0.2 \
	  --memory=256Mi \
	  --concurrency=1 \
	  --min-instances=0 \
	  --max-instances=1 \
	  --service-account="$$SERVICE_ACCOUNT_EMAIL" \
	  --set-env-vars LOG_LEVEL=$$LOG_LEVEL,SIMULATE_DEACTIVATION=$$SIMULATE_DEACTIVATION
