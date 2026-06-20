COMPOSE ?= docker compose
BACKEND_PORT ?= 8000
FRONTEND_DIR ?= frontend
BACKEND_DIR ?= backend

.PHONY: help up up-infra down logs ps restart clean dev dev-backend dev-frontend dev-worker

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

up: ## Start all supporting services in the background
	$(COMPOSE) up -d

down: ## Stop and remove containers (data volumes are kept)
	$(COMPOSE) down

logs: ## Tail logs from all services (Ctrl-C to stop)
	$(COMPOSE) logs -f

ps: ## Show status of all services
	$(COMPOSE) ps

restart: ## Recreate all services
	$(COMPOSE) down && $(COMPOSE) up -d

clean: ## Stop services AND delete volumes (wipes all data)
	$(COMPOSE) down -v

up-infra: ## Start the infra `dev` needs (Postgres + Qdrant + Redis)
	$(COMPOSE) up -d postgres qdrant redis

dev: up-infra ## Run backend + worker + frontend together (one Ctrl-C stops all)
	@echo "backend -> http://localhost:$(BACKEND_PORT)   frontend -> http://localhost:3000   (+ celery worker)"
	@echo "(Ctrl-C stops all)"
	@trap 'kill 0' EXIT INT TERM; \
		( cd $(BACKEND_DIR) && .venv/bin/uvicorn app.main:app --reload --port $(BACKEND_PORT) ) & \
		( cd $(BACKEND_DIR) && .venv/bin/celery -A app.workers.celery_app worker --loglevel=info --pool=solo ) & \
		( cd $(FRONTEND_DIR) && npm run dev ) & \
		wait

dev-backend: up-infra ## Run only the backend (uvicorn --reload)
	cd $(BACKEND_DIR) && .venv/bin/uvicorn app.main:app --reload --port $(BACKEND_PORT)

dev-worker: up-infra ## Run only the Celery worker
	cd $(BACKEND_DIR) && .venv/bin/celery -A app.workers.celery_app worker --loglevel=info --pool=solo

dev-frontend: ## Run only the frontend (next dev)
	cd $(FRONTEND_DIR) && npm run dev
