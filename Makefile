# Nimbus Markets ADK multi-agent demo
#   make up          docker compose (ENGINE=docker)
#   make podman-up   podman-compose
# Run `make help` for everything.

ENGINE ?= docker
ifeq ($(ENGINE),podman)
COMPOSE ?= podman-compose -f compose.yaml
EXEC    ?= podman exec
else
COMPOSE ?= docker compose -f compose.yaml
EXEC    ?= docker exec
endif
PODMAN_COMPOSE ?= podman-compose -f compose.yaml

UV     := $(shell command -v uv 2>/dev/null)
PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
ifneq ($(wildcard .venv/bin/pytest),)
PYTEST := .venv/bin/pytest
else
PYTEST := uv run pytest
endif

ENV_MSG := add your LITELLM_GEMINI_API_KEY (or GEMINI_API_KEY) to .env, then re-run

.DEFAULT_GOAL := help
.PHONY: help check-env up down logs ps reset build \
        podman-up podman-down podman-logs podman-ps podman-reset podman-build \
        test data seed-tools dev

help: ## Show this help
	@echo "Nimbus Markets ADK demo - all data is synthetic."
	@echo ""
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "URLs once up: chat UI http://localhost:8080 | ADK dev UI http://localhost:8000 | Postgres localhost:5432 (postgres/postgres, db nimbus)"

# --- .env guard ---------------------------------------------------------------
check-env: ## Make sure .env exists and has an LLM key (creates it from .env.example)
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env from .env.example."; \
		echo "$(ENV_MSG)"; \
		exit 1; \
	fi
	@key_set() { grep -E "^[[:space:]]*(export[[:space:]]+)?$$1[[:space:]]*=" .env | tail -n 1 \
		| sed -E 's/^[^=]*=[[:space:]]*//; s/^#.*$$//; s/[[:space:]]+#.*$$//; s/^"(.*)"[[:space:]]*$$/\1/; s/^'"'"'(.*)'"'"'[[:space:]]*$$/\1/; s/[[:space:]]*$$//' \
		| grep -q .; }; \
	if key_set LITELLM_GEMINI_API_KEY || key_set GEMINI_API_KEY; then \
		echo "check-env: LLM key configured."; \
	else \
		echo "$(ENV_MSG)"; \
		exit 1; \
	fi

# --- docker compose (ENGINE=docker) ---------------------------------------------
up: check-env ## Build + start everything (docker compose)
	$(COMPOSE) up -d --build
	@echo "Chat UI: http://localhost:8080   ADK dev UI: http://localhost:8000   Postgres: localhost:5432"

down: ## Stop everything (keeps the database volume)
	$(COMPOSE) down

logs: ## Follow logs of all services
	$(COMPOSE) logs -f

ps: ## Show service status
	$(COMPOSE) ps

build: ## Build the images only
	$(COMPOSE) build

reset: ## Wipe the database volume and start again (reloads the synthetic CSVs)
	$(COMPOSE) down -v
	$(MAKE) up

# --- podman-compose ---------------------------------------------------------------
podman-up: check-env ## Build + start everything (podman-compose)
	$(PODMAN_COMPOSE) up -d --build
	@echo "Chat UI: http://localhost:8080   ADK dev UI: http://localhost:8000   Postgres: localhost:5432"

podman-down: ## Stop everything (podman; keeps the database volume)
	$(PODMAN_COMPOSE) down

podman-logs: ## Follow logs (podman)
	$(PODMAN_COMPOSE) logs -f

podman-ps: ## Show service status (podman)
	$(PODMAN_COMPOSE) ps

podman-build: ## Build the images only (podman)
	$(PODMAN_COMPOSE) build

podman-reset: ## Wipe the database volume and start again (podman)
	$(PODMAN_COMPOSE) down -v
	$(MAKE) podman-up

# --- dev helpers --------------------------------------------------------------------
test: ## Python tests + web typecheck
	$(PYTEST)
	cd web && npm run typecheck

data: ## Regenerate db/seed/*.csv (dev only; then `make reset` / `make podman-reset` to load them)
	$(PYTHON) scripts/generate_synthetic_data.py
	@echo "CSV files regenerated. Run 'make reset' (or 'make podman-reset') to reload the database."

seed-tools: ## Force re-upsert seed/starter_tools.yaml into tools.tools (ENGINE=podman for podman)
	$(EXEC) nimbus-app python -m devfest_agents.seed --force

dev: ## db + news-mcp in containers; run the API (uv) and the SPA (vite) locally
	$(COMPOSE) up -d --build db news-mcp
	@echo ""
	@echo "Now, in two terminals:"
	@echo "  DATABASE_URL=postgresql://app:app@localhost:5432/nimbus \\"
	@echo "  AGENT_DATABASE_URL=postgresql://agent_ro:agent_ro@localhost:5432/nimbus \\"
	@echo "  NEWS_MCP_URL=http://localhost:8001/mcp STARTER_TOOLS_PATH=seed/starter_tools.yaml \\"
	@echo "    uv run --env-file .env uvicorn devfest_agents.api.main:app --reload --port 8080"
	@echo "  cd web && npm install && npm run dev      # http://localhost:5173"
