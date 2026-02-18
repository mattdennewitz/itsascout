# itsascout

## What This Is

A publisher website analysis tool where users paste a single URL and get a streaming scraping report card — WAF detection, ToS discovery, robots.txt analysis, metadata profiling, RSS/sitemap discovery, RSL licensing checks, and competitive intelligence signals (Common Crawl presence, Google News readiness, publishing frequency). Publisher intelligence accumulates over time, so repeat lookups against the same domain are instant. Built on Django-Inertia with an async task pipeline and real-time SSE progress updates.

## Core Value

Paste a URL, get a comprehensive scraping report card — what's allowed, what's blocked, and what structured data is available — with real-time progress as each check completes.

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
- ✓ Single-URL submission with job creation and UUID tracking — v2.0
- ✓ URL sanitization and deduplication — v2.0
- ✓ Publisher resolution by domain — v2.0
- ✓ Publisher freshness TTL with configurable refresh interval — v2.0
- ✓ Fetch strategy discovery (curl-cffi first, Zyte fallback, remembered per publisher) — v2.0
- ✓ Publisher metadata profiling via LLM — v2.0
- ✓ Structured data format detection (JSON-LD, OpenGraph, Microdata indicators) — v2.0
- ✓ robots.txt discovery and per-URL permission checking — v2.0
- ✓ Sitemap discovery (common patterns/filenames) — v2.0
- ✓ RSS feed URL discovery — v2.0
- ✓ RSL (Really Simple Licensing) indicator detection — v2.0
- ✓ ToS/privacy discovery integrated into pipeline — v2.0
- ✓ Article-level metadata extraction via extruct — v2.0
- ✓ Real-time SSE progress updates during pipeline execution — v2.0
- ✓ Report card results page (publisher + article findings at unique URL) — v2.0
- ✓ RQ worker infrastructure in Docker Compose — v2.0
- ✓ Existing publisher table stays as admin/management view — v2.0
- ✓ Field-presence table showing canonical fields across metadata formats — v2.0
- ✓ Full integration test (URL submission → pipeline → completed job) — v2.0

- ✓ Common Crawl domain presence check via CC CDX Index API — v2.1
- ✓ Google News readiness detection (news sitemap, NewsArticle/NewsMediaOrganization schema) — v2.1
- ✓ Publisher update frequency estimation from RSS dates with sitemap lastmod fallback — v2.1
- ✓ Competitive Intelligence report card section with CC, Google News, and frequency — v2.1
- ✓ Pipeline TTL skip paths for all competitive intelligence steps — v2.1
- ✓ SSE progress events for all competitive intelligence steps — v2.1

### Active

<!-- Current scope. Building toward these. -->

(No active milestone — use `/gsd:new-milestone` to start next)

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- RSS feed crawling — just discover and remember URLs, don't fetch content (v2.1 added date extraction for frequency)
- Sitemap crawling — discover existence and sample for news namespace, don't parse all entries
- Mobile app — web-first approach
- SSR setup — adds Node.js process complexity, defer until needed
- Batch/bulk URL analysis — single-URL flow first, batch later
- Google News Publisher Center API — requires publisher authentication, not available to third parties
- Real-time CC API monitoring — single point-in-time check per analysis, not ongoing monitoring
- Competitor comparison — side-by-side intelligence for multiple publishers (future milestone)

## Context

**Current state (post v2.1):**
- Stack: Django 5.2 + React 19.1 + Inertia.js + Vite + TailwindCSS + Daphne ASGI
- Architecture: Django views → inertia_render() → React page components, with SSE for real-time updates
- Frontend: scrapegrape/frontend/ with 5 page components (Index, Create, Edit, BulkUpload, Jobs/Show)
- Models: Publisher (domain, WAF, ToS, robots, sitemaps, RSS, RSL, fetch strategy, metadata profile, CC presence, news sitemap, Google News readiness, update frequency), ResolutionJob (UUID, URL, status, pipeline results + cc_result, sitemap_analysis_result, frequency_result, news_signals_result), ArticleMetadata
- Pipeline: 16 steps running sequentially in RQ worker — publisher resolution, WAF, ToS, robots.txt, sitemap, RSS, RSL, CC presence, sitemap analysis, frequency estimation, article extraction, paywall detection, metadata profiling, field presence, structured data, Google News readiness
- Infrastructure: Docker Compose with PostgreSQL, Redis 7, RQ worker, Daphne ASGI
- Tests: pytest with factory patterns, mocked external services, full integration test
- Dependencies: feedparser 6.0.12 added in v2.1
- Codebase: ~8,000+ LOC Python + ~3,500+ LOC TypeScript

## Constraints

- **Stack**: Django + React + Vite + TailwindCSS + Inertia.js + Daphne ASGI (established through v2.0)
- **Async**: RQ for task execution, Redis for queue + SSE pub/sub
- **Fetching**: curl-cffi preferred, Zyte as fallback (cost consideration)
- **LLM**: pydantic-ai agents with GPT-4.1-nano for publisher resolution, ToS, and metadata profiling
- **Backwards compatibility**: Existing publisher table and admin must continue working
- **Development approach**: TDD with pytest — tests written before implementation

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
| SSE via Redis pub/sub + Daphne ASGI | Real-time progress without polling; Daphne as first INSTALLED_APPS hooks runserver | ✓ Good — seamless streaming, no separate process |
| curl-cffi first, Zyte fallback | Minimize Zyte costs, curl-cffi handles most sites | ✓ Good — strategy remembered per publisher |
| LLM metadata profiling (GPT-4.1-nano) | Human-readable "what's available" instead of raw format listing | ✓ Good — cheap, fast, useful summaries |
| django-rq over django_tasks | Production-grade task queue with Redis backend and admin monitoring | ✓ Good — reliable job execution with visibility |
| protego for robots.txt parsing | Scrapy ecosystem, wildcard support, sitemap extraction | ✓ Good — handles edge cases well |
| extruct for structured data extraction | Extracts JSON-LD, OpenGraph, Microdata from HTML in one pass | ✓ Good — comprehensive format coverage |
| Plain HTML form POST for URL submission | Standard form POST to /submit, redirect handled as SPA transition | ✓ Good — simple, reliable, works with CSRF |
| Article freshness TTL separate from publisher | Articles may need re-checking more frequently than publisher metadata | ✓ Good — flexible caching granularity |
| Google News heuristic signals (not binary) | No public API for Google News inclusion; signals give honest assessment | ✓ Good — 4-tier readiness avoids false promises |
| CC step non-critical with graceful error handling | External API shouldn't block pipeline; "unavailable" is acceptable | ✓ Good — pipeline never fails on CC timeout |
| RSS dates preferred over sitemap lastmod | RSS dates are publication dates; sitemap lastmod may reflect edits | ✓ Good — more accurate frequency estimation |
| feedparser as only new dependency | Minimize dependency footprint; feedparser is mature and focused | ✓ Good — single addition for v2.1 |
| CC CDX endpoint hardcoded to latest crawl | Simplest approach; can parameterize later if needed | — Pending review |
| String search for xmlns:news detection | Faster than XML namespace parsing; sufficient for detection | ✓ Good — simple and reliable |

---
*Last updated: 2026-02-18 after v2.1 milestone complete*
