# ScrapeGrape

ScrapeGrape is an AI-powered compliance analysis tool that scans publisher websites to detect Web Application Firewalls (WAFs), discover Terms of Service pages, and evaluate what activities — scraping, AI/ML training, caching, redistribution, and more — are permitted or prohibited.

## What It Does

Given a list of publisher URLs, ScrapeGrape runs a three-stage analysis pipeline:

1. **WAF Detection** — Uses [wafw00f](https://github.com/EnableSecurity/wafw00f) to identify web application firewalls protecting a site
2. **Terms Discovery** — Fetches the publisher's homepage via [Zyte](https://www.zyte.com/) proxy and uses an LLM (GPT-4.1-nano) to locate the Terms of Service URL
3. **Terms Evaluation** — Fetches the ToS page and uses an LLM to classify permissions across 8 activity types:
   - Web scraping / crawling
   - AI/ML usage (training, fine-tuning)
   - Manual content usage
   - Caching / archiving / dataset creation
   - Text and Data Mining (TDM)
   - API / RSS feed usage
   - Content redistribution
   - User-generated content (UGC) usage

Each activity is classified as **explicitly permitted**, **explicitly prohibited**, or **conditional/ambiguous**, with relevant excerpts and confidence scores. Territorial exceptions and arbitration clauses are also extracted.

Results are displayed in an interactive React table with expandable rows for detailed permission breakdowns.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django 5.2, Django REST Framework |
| Frontend | React 19, TypeScript, TailwindCSS 4, TanStack Table |
| Build | Vite 7, django-vite |
| Database | PostgreSQL 17 |
| Task Queue | django-tasks (database backend) |
| AI | pydantic-ai with OpenAI (GPT-4.1-nano) |
| WAF Scanning | wafw00f |
| Web Fetching | Zyte API (proxy) |
| Package Manager | uv |

## Project Structure

```
itsascout/
├── pyproject.toml                 # Python dependencies (managed by uv)
├── sites.csv                      # Publisher URLs for bulk ingestion
├── sgui/                          # React frontend (Vite + TypeScript)
│   ├── src/
│   │   ├── App.tsx                # Entry point, loads publisher data
│   │   └── datatable/
│   │       ├── table.tsx          # DataTable with sorting, filtering, expansion
│   │       └── columns.tsx        # Column definitions and TypeScript types
│   └── vite.config.ts
└── scrapegrape/                   # Django project
    ├── manage.py
    ├── docker-compose.yml         # PostgreSQL container
    ├── scrapegrape/               # Django settings & URL config
    │   ├── settings.py
    │   └── urls.py
    ├── publishers/                # Publisher data & orchestration
    │   ├── models.py              # Publisher, WAFReport
    │   ├── views.py               # Main table view
    │   ├── serializers.py         # DRF serializers
    │   ├── tasks.py               # analyze_url async task
    │   ├── admin.py               # Admin with custom actions
    │   ├── waf_check.py           # wafw00f integration
    │   └── management/commands/
    │       └── bulk_ingestion.py  # CSV bulk import
    ├── ingestion/                 # AI-powered analysis
    │   ├── models.py              # TermsDiscoveryResult, TermsEvaluationResult
    │   ├── services.py            # Zyte API HTML fetching
    │   ├── terms_discovery.py     # LLM-based ToS URL discovery
    │   └── terms_evaluation.py    # LLM-based ToS permission analysis
    └── templates/
        ├── base.html              # Base template with Vite integration
        └── index.html             # Main table view
```

## Setup

### Prerequisites

- Python 3.12+
- Node.js
- Docker & Docker Compose
- API keys: **OpenAI**, **Zyte**

### 1. Install Python dependencies

```bash
uv sync
```

### 2. Configure environment variables

Create `scrapegrape/.env`:

```env
DATABASE_URL=postgres://postgres:postgres@localhost:5432/scrapegrape
OPENAI_API_KEY=sk-...
ZYTE_API_KEY=...
LOGFIRE_TOKEN=...  # optional
```

### 3. Start PostgreSQL

```bash
cd scrapegrape
docker compose up -d
```

### 4. Run migrations and create a superuser

```bash
cd scrapegrape
python manage.py migrate
python manage.py createsuperuser
```

### 5. Build the frontend

```bash
cd sgui
npm install
npm run build
```

### 6. Start the dev server

```bash
cd scrapegrape
python manage.py runserver
```

The app is available at http://localhost:8000/ and the admin at http://localhost:8000/admin/.

For frontend hot-reload during development, run `npm run dev` in `sgui/` alongside the Django server.

## Usage

### Bulk ingestion

Import publisher URLs from `sites.csv` and queue them all for analysis:

```bash
cd scrapegrape
python manage.py bulk_ingestion
```

### Admin interface

The Django admin provides several actions on publishers:

- **Perform WAF scan** — detect firewalls on selected publishers
- **Discover terms** — find Terms of Service URLs using AI
- **Evaluate terms** — analyze ToS content for permissions
- **Discover and evaluate terms** — run both steps in sequence
- **Queue URL analysis** — enqueue the full pipeline as an async task

There's also a custom admin view at `/admin/publishers/publisher/analyze-url/` for submitting individual URLs.

### Async task processing

Long-running analyses are queued via django-tasks with a database backend. The `analyze_url` task runs the full pipeline (WAF scan, terms discovery, terms evaluation) for a given URL.

## Data Flow

```
URL input (CSV or admin form)
  → analyze_url task enqueued
  → wafw00f WAF scan
  → Zyte API fetches homepage HTML
  → LLM discovers ToS URL
  → Zyte API fetches ToS HTML
  → LLM evaluates permissions
  → Results stored in PostgreSQL
  → DRF serializers format response
  → React table renders with expandable details
```
