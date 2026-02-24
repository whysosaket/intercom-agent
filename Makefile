.PHONY: build up down logs restart shell mock prod-build prod-up prod-down prod-logs \
       frontend-install frontend-dev frontend-build dev

# Development
build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

restart:
	docker compose restart

shell:
	docker compose exec app bash

# Local mock mode (no Docker, no external services needed)
mock:
	MOCK_MODE=true uvicorn app.main:api --host 0.0.0.0 --port 8000 --reload

# Frontend
frontend-install:
	cd frontend && pnpm install

frontend-dev:
	cd frontend && pnpm run dev

frontend-build:
	cd frontend && pnpm run build

# Full local dev (backend mock + frontend dev server)
dev:
	$(MAKE) -j2 mock frontend-dev

# Production (with Nginx + SSL)
prod-build:
	docker compose -f docker-compose.prod.yml build

prod-up:
	docker compose -f docker-compose.prod.yml up -d

prod-down:
	docker compose -f docker-compose.prod.yml down

prod-logs:
	docker compose -f docker-compose.prod.yml logs -f
