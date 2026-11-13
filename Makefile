# The marketing agent workshop. Run `make help` for the commands you need.
# Maintainer commands (tests, data, security scans) are in platform/Makefile: `make -C platform help`.

# The workshop uses Docker. Maintainers without it can use Podman: it's picked when Docker
# isn't installed, or force it with ENGINE=podman.
ENGINE ?= $(if $(shell command -v docker 2>/dev/null),docker,podman)
ifeq ($(ENGINE),podman)
COMPOSE ?= podman-compose -f compose.yaml
# podman-compose does not recreate containers on its own after a rebuild.
UP_FLAGS ?= --force-recreate
else
COMPOSE ?= docker compose -f compose.yaml
endif
EXEC ?= $(ENGINE) exec

# The competition's Google Drive folder. Facilitators: put the real link here and in exercises/5-evals.md.
DRIVE_URL := https://drive.google.com/drive/folders/DRIVE_FOLDER_ID

ENV_MSG := add your LLM key to .env (see .env.example), then run make up again

.DEFAULT_GOAL := help
.PHONY: help check-env check-engine up down logs reset eval submit check

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

check-engine:
	@if ! command -v $(ENGINE) >/dev/null 2>&1; then \
		echo "Docker isn't installed. Follow 'Install Docker' in README.md, then run make up again."; \
		exit 1; \
	fi
	@if ! $(ENGINE) info >/dev/null 2>&1; then \
		if [ "$(ENGINE)" = podman ]; then echo "Podman isn't running. Run: podman machine start"; \
		else echo "Docker is installed but not running. Start Docker Desktop (on Linux: sudo systemctl start docker),"; \
			echo "then run make up again. See 'If something goes wrong' in README.md if it still fails."; fi; \
		exit 1; \
	fi

up: check-env check-engine ## Build and start the app
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

submit: ## Zip my_agent/ for the competition: make submit NAME="your name or team"
	@if [ -z "$(NAME)" ]; then echo 'Add your name or team: make submit NAME="Ada Lovelace"'; exit 1; fi
	@mkdir -p submission && rm -f "submission/$(NAME).zip"
	@if command -v zip >/dev/null 2>&1; then \
		zip -qr "submission/$(NAME).zip" my_agent -x '*__pycache__*' '*.pyc' '*.DS_Store'; \
	elif command -v python3 >/dev/null 2>&1; then \
		python3 -m zipfile -c "submission/$(NAME).zip" my_agent; \
	else \
		echo "Can't zip here. Copy the my_agent folder, rename the copy to your name, and upload that."; exit 1; \
	fi
	@echo "Made submission/$(NAME).zip. Upload it to the competition's Google Drive folder:"
	@echo "  $(DRIVE_URL)"
	@echo "Changed something? Run this again and upload the new zip: the newest upload counts."
