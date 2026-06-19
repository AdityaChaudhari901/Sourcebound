COMPOSE ?= docker compose

.PHONY: help up down logs ps restart clean

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
