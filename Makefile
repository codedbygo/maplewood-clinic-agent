.PHONY: check lint coverage help install backend backend-stop ui ui-build ui-dev server run eval holdout stability demo test test-web
.DEFAULT_GOAL := help
PORT ?= 8000

help: ## List every command
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  make %-14s %s\n", $$1, $$2}'

install: ## One-time setup: Python deps (uv) and frontend deps (pnpm)
	uv sync
	cd web && pnpm install --frozen-lockfile

# ---- run ----

backend: ## Run the backend API on http://localhost:8000 (PORT=... to change) (serves the UI too if built)
	uv run uvicorn console.app:app --port $(PORT)

backend-stop: ## Stop whatever is listening on the backend port
	@pid=$$(lsof -ti tcp:$(PORT)); [ -n "$$pid" ] && kill $$pid && echo "stopped $$pid" || echo "nothing on :$(PORT)"

ui-build: ## Build the frontend into web/dist
	cd web && pnpm install --frozen-lockfile --silent && pnpm exec vite build --logLevel warn

ui: ui-build ## Build the frontend and run backend + UI on http://localhost:8000 (PORT=... to change)
	@echo "Maplewood console: http://localhost:$(PORT)"
	uv run uvicorn console.app:app --port $(PORT)

ui-dev: ## Dev mode: API on :8000 with reload, UI with hot reload on http://localhost:5173
	uv run uvicorn console.app:app --port $(PORT) --reload --reload-dir agent --reload-dir console --reload-dir clinic_mcp & \
	cd web && pnpm exec vite --port 5173 --strictPort; kill %1

server: ## Run only the MCP server over stdio
	uv run python -m clinic_mcp.server

demo: ## Process one message from the terminal
	uv run python -m agent.cli process --from "Unknown Sender" --contact "555-0000" --channel sms --text "Hi, are you open on Saturday?"

# ---- agent runs and evaluation (need ANTHROPIC_API_KEY in .env) ----

run: ## Process all 40 sample messages
	uv run python -m agent.cli run --messages data/messages_sample.json --out results/results_sample.json

eval: ## Score the sample run: results/eval_report.md
	uv run python -m eval.harness --results results/results_sample.json --labels data/labels_sample.json --out results/eval_report

holdout: ## Run and score the 13 held-out messages
	uv run python -m agent.cli run --messages eval/holdout_messages.json --out results/results_holdout.json
	uv run python -m eval.harness --results results/results_holdout.json --labels eval/holdout_labels.json --out results/eval_report_holdout

stability: ## Run the sample 3 times and count changed outcomes
	uv run python -m eval.stability --runs 3

# ---- tests ----

test: ## Python tests
	uv run pytest -q

lint: ## Python lint, format and type checks (ruff, mypy)
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy

check: lint coverage test-web ## Every gate: lint, types, tests with coverage floor, frontend gate

coverage: ## Python tests with line+branch coverage; fails under 100%
	uv run pytest -q --cov --cov-report=term-missing --cov-fail-under=100

test-web: ## Frontend gate: format, lint, types, tests, coverage, audit
	cd web && $(MAKE) --no-print-directory check
