# The marketing agent workshop. Run `make help` for the commands you need.
# Maintainer commands (tests, data, security scans) are in platform/Makefile: `make -C platform help`.

# Docker if it's installed, otherwise Podman. Force one with ENGINE=docker or ENGINE=podman.
ENGINE ?= $(if $(shell command -v docker 2>/dev/null),docker,podman)
ifeq ($(ENGINE),podman)
COMPOSE ?= podman-compose -f compose.yaml
# podman-compose does not recreate containers on its own after a rebuild.
UP_FLAGS ?= --force-recreate
else
COMPOSE ?= docker compose -f compose.yaml
endif
EXEC ?= $(ENGINE) exec

ENV_MSG := add your LLM key to .env (see .env.example), then run make up again

.DEFAULT_GOAL := help
.PHONY: help check-env up down logs reset eval submit check

help: ## Show this help
	@echo "The marketing agent workshop. Start with README.md."
	@echo ""
	@grep -hE '^[a-zA-Z_%-]+:.*?## ' Makefile | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Once it's up: the app is at http://localhost:8080 (ADK's own dev UI: http://localhost:8000)"

check-env:
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

up: check-env ## Build and start the app
	$(COMPOSE) up -d --build $(UP_FLAGS)
	@echo ""
	@echo "Ready: http://localhost:8080. Next: exercise 0 in exercises/0-meet-nimbus.md."

down: ## Stop the app (keeps the data)
	$(COMPOSE) down

logs: ## Show the app's logs, for example after a Python error
	$(COMPOSE) logs -f app

reset: ## Reload the database from scratch, then start again
	$(COMPOSE) down -v
	$(MAKE) up

check: ## Check an exercise: make check-0, make check-1 ... make check-4
	@echo "Run make check-N, where N is the exercise number (0 to 4)."

# `|| true`: a check with things to fix is normal progress, not a make error.
check-%:
	@$(EXEC) nimbus-app python -m devfest_agents.check $* || true

eval: ## Score your agents on the practice questions (one question: Q=<id>)
	@$(EXEC) nimbus-app python -m devfest_agents.evals /app/evals/practice.yaml $(if $(Q),--only $(Q)) \
		$(if $(P),--parallel $(P)) > evals/report.json && echo "Full report: evals/report.json" || true

submit: ## Check your work is pushed, and show what to hand in for the competition
	@if ! git diff --quiet HEAD -- my_agent || [ -n "$$(git ls-files --others --exclude-standard my_agent)" ]; then \
		echo "You have changes in my_agent/ that aren't committed yet. Commit and push them first:"; \
		echo '  git add my_agent && git commit -m "My agent" && git push'; exit 1; \
	fi
	@if [ -z "$$(git branch -r --contains HEAD 2>/dev/null)" ]; then \
		echo "Your latest commit isn't on GitHub yet. Run: git push"; exit 1; \
	fi
	@echo "Hand these in on the form your facilitators shared:"
	@echo "  Fork:   $$(git remote get-url origin)"
	@echo "  Commit: $$(git rev-parse HEAD)"
