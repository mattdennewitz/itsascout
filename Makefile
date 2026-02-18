.PHONY: build up down

build:
	docker compose -f docker-compose.yml -f docker-compose.override.yml build

up:
	docker compose -f docker-compose.yml -f docker-compose.override.yml up -d

down:
	docker compose -f docker-compose.yml -f docker-compose.override.yml down