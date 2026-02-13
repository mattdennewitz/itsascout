# itsascout

## What This Is

A publisher website analysis tool where users paste a single URL and get a streaming scraping report card — WAF detection, ToS discovery, robots.txt analysis, metadata profiling, RSS/sitemap discovery, and RSL licensing checks. Publisher intelligence accumulates over time, so repeat lookups against the same domain are instant. Built on Django-Inertia with an async task pipeline and real-time SSE progress updates.

## Core Value

Paste a URL, get a comprehensive scraping report card — what's allowed, what's blocked, and what structured data is available — with real-time progress as each check completes.

## Current Milestone: v2.0 Core Workflow

**Goal:** Build the end-to-end URL analysis workflow with streaming progress, durable publisher intelligence, and a report card UI.

**Target features:**
- Single-URL entry point with real-time SSE progress
- Resolution job pipeline (publisher resolution → discovery → article analysis)
- Publisher report card (WAF, ToS, robots.txt, sitemap, RSS, RSL, metadata profile)
- Article-level metadata extraction and crawl permission check
- RQ task infrastructure in Docker
- curl-cffi with Zyte fallback fetch strategy (remembered per publisher)
- URL sanitization to prevent duplicates
- Configurable publisher freshness TTL

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- Publisher URL ingestion from CSV (bulk import)
- WAF detection via wafw00f integration
- ToS URL discovery via pydantic-ai agent (GPT-4.1-nano)
- ToS permissions evaluation via pydantic-ai agent
- HTML fetching through Zyte proxy API
- Interactive React data table with sorting, filtering, expandable rows
- Django admin with custom actions (WAF scan, discover terms, evaluate, queue analysis)
- Async task pipeline (WAF → discovery → evaluation)
- PostgreSQL data persistence
- ✓ Django-Inertia SPA architecture with cookie-based CSRF — v1.0
- ✓ Consolidated frontend in scrapegrape/frontend/ with Pages/Components/Layouts — v1.0
- ✓ Shared data middleware for auth and flash messages — v1.0
- ✓ Persistent layouts with SPA-like navigation — v1.0
- ✓ Form submissions with useForm and session-based validation — v1.0
- ✓ Deferred props and partial reloads for performance — v1.0
- ✓ Debounced search with preserved table state — v1.0

### Active

<!-- Current scope. Building toward these. -->

- Single-URL submission with job creation and UUID tracking
- URL sanitization and deduplication
- Publisher resolution by domain (homepage visit or LLM web search)
- Publisher freshness TTL with configurable refresh interval
- Fetch strategy discovery (curl-cffi first, Zyte fallback, remembered per publisher)
- Publisher metadata profiling via LLM (article details, byline, paywall, thumbnail, etc.)
- Structured data format detection (json-ld, opengraph, microdata yes/no indicators)
- robots.txt discovery and per-URL permission checking
- Sitemap discovery (common patterns/filenames)
- RSS feed URL discovery (remember, don't crawl)
- RSL (Really Simple Licensing) indicator detection
- ToS/privacy discovery integrated into pipeline
- Article-level metadata extraction via extruct
- Real-time SSE progress updates during pipeline execution
- Report card results page (publisher + article findings at unique URL)
- RQ worker infrastructure in Docker Compose
- Existing publisher table stays as admin/management view

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- RSS feed crawling — just discover and remember URLs, don't fetch content
- Sitemap crawling — discover existence, don't parse entries
- Mobile app — web-first approach
- SSR setup — adds Node.js process complexity, defer until needed
- New UI for publisher management table — current table serves admin use case
- Batch/bulk URL analysis — single-URL flow first, batch later

## Context

**Current state (post v1.0):**
- Stack: Django 5.2 + React 19.1 + Inertia.js + Vite + TailwindCSS
- Architecture: Django views → inertia_render() → React page components
- Frontend: scrapegrape/frontend/ with 4 page components (Index, Create, Edit, BulkUpload)
- Existing models: Publisher (domain, name, WAF, ToS, permissions, etc.)
- Existing tasks: WAF scan, ToS discovery, permissions evaluation (all via Django admin actions)
- Docker: PostgreSQL + Django, no RQ worker yet

**v2.0 changes needed:**
- New models: ResolutionJob (UUID, URL, status, progress), publisher metadata profile
- Extend Publisher model: fetch strategy, last checked date, robots.txt, sitemap URLs, RSS URLs, RSL status, metadata capabilities
- New services: URL sanitizer, publisher resolver, fetch strategy manager, metadata profiler
- New infrastructure: RQ worker in Docker, Redis for queue + SSE
- New frontend: URL entry page, streaming results page

## Constraints

- **Stack**: Django + React + Vite + TailwindCSS + Inertia.js (established in v1.0)
- **Async**: RQ for task execution (already partially in place, needs Docker setup)
- **Fetching**: curl-cffi preferred, Zyte as fallback (cost consideration)
- **LLM**: pydantic-ai agents for publisher resolution and metadata profiling
- **Backwards compatibility**: Existing publisher table and admin must continue working
- **Development approach**: TDD with pytest — tests written before implementation for each pipeline step and service

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| django-inertia over other SPA approaches | Keeps Django as source of truth, avoids building separate API layer | ✓ Good — clean integration, no API layer needed |
| Consolidate into scrapegrape/frontend/ | Single project, simpler DX, co-located code | ✓ Good — simplified build and deployment |
| Cookie-based CSRF via Axios defaults | Avoids anti-pattern (meta tag); cleaner integration | ✓ Good — zero CSRF issues across all forms |
| Session-based validation (not InertiaValidationError) | InertiaValidationError doesn't exist in inertia-django 1.2.0 | ✓ Good — reliable pattern using Django sessions |
| Incremental migration (5 phases) | Allows rollback at each boundary, validates early | ✓ Good — zero blockers, zero rollbacks |
| defer() for expensive queries | Instant initial render with loading spinner | ✓ Good — perceived performance improvement |
| Partial reloads with only: ['publishers'] | Only refetch what changed during search | ✓ Good — reduced bandwidth, preserved state |
| SSE for real-time progress | User sees pipeline steps complete in real time, better than polling | — Pending |
| curl-cffi first, Zyte fallback | Minimize Zyte costs, curl-cffi handles most sites | — Pending |
| Publisher-level metadata profiling via LLM | Human-readable "what's available" instead of raw format listing | — Pending |

---
*Last updated: 2026-02-13 after v2.0 milestone start*
