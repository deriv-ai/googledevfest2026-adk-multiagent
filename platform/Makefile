# Maintainer commands for the platform: tests, synthetic data, local dev, security scans.
# Run from the repo root with `make -C platform <target>`, or from here.
# Workshop participants never need these; the root Makefile has theirs.

ENGINE ?= $(if $(shell command -v docker 2>/dev/null),docker,podman)
ifeq ($(ENGINE),podman)
COMPOSE ?= podman-compose -f ../compose.yaml
else
COMPOSE ?= docker compose -f ../compose.yaml
endif
EXEC ?= $(ENGINE) exec

UV     := $(shell command -v uv 2>/dev/null)
PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
ifneq ($(wildcard .venv/bin/pytest),)
PYTEST := .venv/bin/pytest
else
PYTEST := uv run pytest
endif

.DEFAULT_GOAL := help
.PHONY: help test judge data seed-tools dev update-pkg \
        trivy-scan trivy-config trivy-image trivy-patch trivy-verify trivy-audit

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' Makefile | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

test: ## Python tests + web typecheck
	$(PYTEST)
	cd web && npm run typecheck

# The stack must be running (make up). SUBMISSIONS is the downloaded Drive folder, or the zip
# Drive gives you: one <name>.zip (from make submit) or <name>/ folder per participant.
judge: ## Score competition submissions into .judge/leaderboard.html (SUBMISSIONS=folder-or-zip)
ifndef SUBMISSIONS
	$(error SUBMISSIONS is required, e.g. make judge SUBMISSIONS=~/Downloads/submissions)
endif
	uv run --env-file ../.env python -m devfest_agents.judge "$(SUBMISSIONS)" --engine $(ENGINE) $(JUDGE_ARGS)

data: ## Regenerate db/seed/*.csv (then `make reset` from the repo root to load them)
	$(PYTHON) scripts/generate_synthetic_data.py
	@echo "CSV files regenerated. Run 'make reset' from the repo root to reload the database."

seed-tools: ## Force re-upsert seed/starter_tools.yaml into tools.tools
	$(EXEC) nimbus-app python -m devfest_agents.seed --force

dev: ## db + news-mcp in containers; run the API (uv) and the SPA (vite) locally
	$(COMPOSE) up -d --build db news-mcp
	@echo ""
	@echo "Now, in two terminals:"
	@echo "  DATABASE_URL=postgresql://app:app@localhost:5432/nimbus \\"
	@echo "  AGENT_DATABASE_URL=postgresql://agent_ro:agent_ro@localhost:5432/nimbus \\"
	@echo "  NEWS_MCP_URL=http://localhost:8001/mcp STARTER_TOOLS_PATH=seed/starter_tools.yaml \\"
	@echo "  PYTHONPATH=.. uv run --env-file ../.env uvicorn devfest_agents.api.main:app --reload --port 8080"
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
TRIVY_IMAGES   := nimbus-app nimbus-news-mcp

trivy-scan: ## Fail on fixable HIGH/CRITICAL vulns in uv.lock + web/package-lock.json
	trivy fs --scanners vuln --severity $(TRIVY_SEVERITY) --ignore-unfixed --exit-code 1 $(TRIVY_SKIP) .

trivy-config: ## Report Dockerfile / compose misconfigurations (report only, never fails)
	trivy config --severity $(TRIVY_SEVERITY) --exit-code 0 $(TRIVY_SKIP) ..

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
