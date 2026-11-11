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
        test eval eval-final check data seed-tools dev update-pkg \
        trivy-scan trivy-config trivy-image trivy-patch trivy-verify trivy-audit

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
	if key_set LITELLM_GEMINI_API_KEY || key_set LLM_API_KEY || key_set GEMINI_API_KEY; then \
		echo "check-env: LLM key configured."; \
	else \
		echo "$(ENV_MSG)"; \
		exit 1; \
	fi

# --- docker compose (ENGINE=docker) ---------------------------------------------
up: check-env ## Build + start everything (docker compose)
	$(COMPOSE) up -d --build
	@echo "Chat UI: http://localhost:8080   ADK dev UI: http://localhost:8000"
	@echo "Next: open WORKSHOP.md and start with exercise 0."

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
	@echo "Chat UI: http://localhost:8080   ADK dev UI: http://localhost:8000"
	@echo "Next: open WORKSHOP.md and start with exercise 0."

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

eval: ## Score your agents on the practice questions (one question: Q=<id>)
	@$(EXEC) nimbus-app python -m devfest_agents.evals /app/evals/practice.yaml $(if $(Q),--only $(Q)) > evals/report.json \
		&& echo "Full report: evals/report.json" || true

eval-final: ## Score your agents on the hidden competition questions (KEY=<passphrase>)
	@$(EXEC) nimbus-app python -m devfest_agents.evals /app/evals/final.enc --key "$(KEY)" > evals/report.json \
		&& echo "Full report: evals/report.json" || true

check: ## Check a workshop exercise: make check-0, make check-1 ... make check-4
	@echo "Run make check-N, where N is the exercise number (0 to 4)."

# `|| true`: a check with things to fix is normal progress, not a make error.
check-%:
	@$(EXEC) nimbus-app python -m devfest_agents.check $* || true

data: ## Regenerate db/seed/*.csv (dev only; then `make reset` / `make podman-reset` to load them)
	$(PYTHON) scripts/generate_synthetic_data.py
	@echo "CSV files regenerated. Run 'make reset' (or 'make podman-reset') to reload the database."

seed-tools: ## Force re-upsert seed/starter_tools.yaml into tools.tools (ENGINE=podman for podman)
	$(EXEC) nimbus-app python -m devfest_agents.seed --force

dev: ## db in a container; run the API (uv) and the SPA (vite) locally
	$(COMPOSE) up -d db
	@echo ""
	@echo "Now, in two terminals:"
	@echo "  DATABASE_URL=postgresql://app:app@localhost:5432/nimbus \\"
	@echo "  AGENT_DATABASE_URL=postgresql://agent_ro:agent_ro@localhost:5432/nimbus \\"
	@echo "  STARTER_TOOLS_PATH=seed/starter_tools.yaml \\"
	@echo "    uv run --env-file .env uvicorn devfest_agents.api.main:app --reload --port 8080"
	@echo "  cd web && npm install && npm run dev      # http://localhost:5173"

update-pkg: ## Pin a package to a version: make update-pkg PKG=litellm VERSION=1.108.1
ifndef PKG
	$(error PKG is required, e.g. make update-pkg PKG=litellm VERSION=1.108.1)
endif
ifndef VERSION
	$(error VERSION is required, e.g. make update-pkg PKG=litellm VERSION=1.108.1)
endif
	@command -v $(or $(UV),uv) >/dev/null 2>&1 || { echo "uv not found: install it with 'brew install uv' (or see https://docs.astral.sh/uv/), then re-run"; exit 1; }
	$(or $(UV),uv) add "$(PKG)==$(VERSION)"

# --- security: trivy ------------------------------------------------------------------
# Scans BOTH lockfiles: uv.lock (Python) and web/package-lock.json (SPA).
# Needs trivy (https://trivy.dev, e.g. `brew install trivy`).
TRIVY_SEVERITY ?= HIGH,CRITICAL
TRIVY_SKIP     := --skip-dirs web/node_modules --skip-dirs .venv --skip-dirs .claude
TRIVY_IMAGES   := nimbus-app

trivy-scan: ## Fail on fixable HIGH/CRITICAL vulns in uv.lock + web/package-lock.json
	trivy fs --scanners vuln --severity $(TRIVY_SEVERITY) --ignore-unfixed --exit-code 1 $(TRIVY_SKIP) .

trivy-config: ## Report Dockerfile / compose misconfigurations (report only, never fails)
	trivy config --severity $(TRIVY_SEVERITY) --exit-code 0 .

trivy-image: ## Scan the built container images (OS + app packages; ENGINE=podman for podman)
	@for img in $(TRIVY_IMAGES); do \
		echo "== $$img"; \
		$(ENGINE) save -o .trivy-$$img.tar $$img:latest && \
		trivy image --input .trivy-$$img.tar --severity $(TRIVY_SEVERITY) --ignore-unfixed --exit-code 0 --quiet; \
		rm -f .trivy-$$img.tar; \
	done

# Upgrade every package trivy has a fix for, pins and majors included. Anything that
# can only be fixed by downgrading another package is rolled back and reported
# (see scripts/trivy_patch.py).
trivy-patch: ## Upgrade every fixable vulnerable package (rolls back fixes that would downgrade others)
	cd web && npm audit fix || true
	UV="$(or $(UV),uv)" $(PYTHON) scripts/trivy_patch.py

# A major upgrade can still break code at compile time; this is what catches it.
trivy-verify: ## Python tests + SPA typecheck/tests/build, after an upgrade
	$(PYTEST) -q
	cd web && npm run typecheck && npm test && npm run build

# The leading `-` lets a partly-failed patch still run verify + scan, so whatever is
# left shows up in the scan instead of hiding behind the patch error.
trivy-audit: ## Patch everything fixable, verify nothing broke, then fail if HIGH/CRITICAL remains
	-$(MAKE) trivy-patch
	$(MAKE) trivy-verify
	$(MAKE) trivy-scan
