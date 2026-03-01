# Stage 1: Frontend Builder
FROM node:24-slim as frontend-builder
WORKDIR /app/frontend
COPY scrapegrape/frontend/package*.json ./
RUN npm install
COPY scrapegrape/frontend .
RUN npm run build

# Stage 2: Python Application
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    curl -fsSL https://github.com/BurntSushi/xsv/releases/download/0.13.0/xsv-0.13.0-x86_64-unknown-linux-musl.tar.gz \
    | tar xz -C /usr/local/bin && \
    apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# Copy the rest of the application code
COPY . .

# Copy built frontend assets
COPY --from=frontend-builder /app/frontend/dist /app/scrapegrape/static/dist

# Collect static files
RUN uv run scrapegrape/manage.py collectstatic --noinput

# Set default command for Django (can be overridden by docker-compose or Coolify)
CMD ["uv", "run", "gunicorn", "scrapegrape.asgi:application", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
