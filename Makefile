DC = docker compose
MANAGE = $(DC) exec django uv run scrapegrape/manage.py

.PHONY: help up down logs build migrate superuser ingest shell dbshell lint setup worker test

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

up: ## Start all services (postgres, django, vite)
	$(DC) up -d

down: ## Stop all services
	$(DC) down

logs: ## Tail logs from all services
	$(DC) logs -f

build: ## Rebuild images (after dependency changes)
	$(DC) build

migrate: ## Run Django migrations
	$(MANAGE) migrate

superuser: ## Create a Django superuser
	$(MANAGE) createsuperuser

ingest: ## Run bulk ingestion from sites.csv
	$(MANAGE) bulk_ingestion

shell: ## Open Django shell
	$(MANAGE) shell

dbshell: ## Open database shell
	$(DC) exec postgres psql -U postgres scrapegrape

lint: ## Lint frontend code
	$(DC) exec vite npm run lint

worker: ## Tail worker logs
	$(DC) logs -f worker

test: ## Run pytest test suite
	uv run pytest scrapegrape/ -v

setup: build up migrate ## First-time setup (build, start, migrate)
