# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-13)

**Core value:** Paste a URL, get a comprehensive scraping report card with real-time progress as each check completes.
**Current focus:** Phase 10 in progress (article metadata extraction).

## Current Position

Phase: 10 of 11 (Article Metadata) -- COMPLETE
Plan: 2 of 2 in current phase
Status: Phase 10 complete
Last activity: 2026-02-17 -- Plan 10-02 complete. 12-step pipeline with article extraction, paywall detection, metadata profile. Frontend article analysis section.

Progress: [█████████░] 85%

## Performance Metrics

**Velocity:**
- Total plans completed: 10 (v2.0)
- Average duration: 3.3min
- Total execution time: 0.55 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 06-infrastructure-models | 2 | 7min | 3.5min |
| 07-fetch-strategy | 1 | 3min | 3min |
| 08-core-pipeline-sse | 3 | 7min | 2.3min |
| 09-publisher-discovery | 2 | 7min | 3.5min |
| 10-article-metadata | 2 | 9min | 4.5min |

**Recent Trend:**
- Last 5 plans: 08-03 (2min), 09-01 (3min), 09-02 (4min), 10-01 (4min), 10-02 (5min)
- Trend: stable

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [v2.0 roadmap]: TDD constraint -- TEST requirements distributed across feature phases, not isolated
- [v2.0 roadmap]: RSL detection in scope (DISC-07), grade computation deferred to future milestone
- [v2.0 roadmap]: SSE serving approach folded into Phase 8 naturally (no separate ASGI requirement)
- [v2.0 roadmap]: Phase 8 is the core vertical slice (URL entry -> pipeline -> SSE -> results page)
- [06-01]: Replaced django_tasks with django-rq backed by Redis for production-grade task queue
- [06-01]: REDIS_HOST defaults to localhost for local dev/pytest, overridden to redis in Docker
- [06-01]: Installed w3lib, pytest, pytest-django, factory-boy, pytest-cov ahead of Plan 02
- [06-02]: 3-step migration pattern (add, populate, add unique) for domain field on existing data
- [06-02]: Factory get_or_create on domain to prevent duplicate publishers in tests
- [06-02]: 28 tracking params in URL sanitizer denylist covering all major ad/analytics platforms
- [07-01]: curl-cffi impersonate="chrome" (latest) as default TLS fingerprint target
- [07-01]: WAF detection via 6 content signatures + 403 status -- no body-length heuristic
- [07-01]: Publisher.fetch_strategy saved only on change to avoid unnecessary DB writes
- [07-01]: ZyteFetcher reads ZYTE_API_KEY at call time (not init) for per-request validation
- [08-01]: Pipeline steps call existing ingestion agents directly rather than rewriting
- [08-01]: Each step saves result to ResolutionJob before publishing Redis event (data persists if subscriber misses)
- [08-01]: Supervisor merges ToS evaluation data into existing tos_result dict (one JSON field)
- [08-01]: Publisher flat fields updated in supervisor for quick reads without joining to ResolutionJob
- [08-02]: Daphne as first INSTALLED_APPS entry to hook into runserver for async SSE
- [08-02]: Completed/failed jobs return single terminal SSE event (no Redis subscription needed)
- [08-02]: Publisher get_or_create on domain for submit_url (matches factory pattern from 06-02)
- [08-03]: Standard HTML form POST to /submit (not Inertia useForm) so redirect is handled as SPA transition
- [08-03]: CSRF token read from document.cookie (csrftoken) matching Django's default cookie name
- [08-03]: Completed jobs build stepStatuses from props (waf_result, tos_result) without SSE
- [09-01]: protego 0.6.0 for robots.txt parsing (Scrapy ecosystem, wildcard support, Sitemap extraction)
- [09-01]: Content-Type text/html guard treats WAF challenge pages as robots.txt not found
- [09-01]: Plain requests.get for robots.txt (no FetchStrategyManager needed for plain text)
- [09-01]: HEAD-then-GET fallback for sitemap probing (handles servers blocking HEAD)
- [08-03]: EventSource closes on 'done' event, then reloads via router.reload() for final server props
- [09-02]: stdlib html.parser.HTMLParser for feed/RSL link extraction (no external dependency)
- [09-02]: Homepage HTML fetched once and shared between RSS and RSL steps
- [09-02]: RSL detection best-effort across three sources (robots.txt, HTML link, HTTP Link header)
- [10-01]: GPT-4.1-nano for metadata profile agent (cheaper than gpt-5-mini, sufficient for profiling)
- [10-01]: hasPart nesting check for isAccessibleForFree (Google's recommended pattern)
- [10-01]: High confidence bar: single heuristic signal alone -> unknown, not paywalled
- [10-01]: extruct uniform=False to preserve native OpenGraph list-of-tuples format
- [10-02]: Article steps run outside publisher freshness branch with own ARTICLE_FRESHNESS_TTL
- [10-02]: homepage_html initialized before branch to prevent NameError when publisher steps skipped

### Pending Todos

None yet.

### Roadmap Evolution

- Phase 12 added: Django Built-in Authentication

### Blockers/Concerns

None currently.

## Session Continuity

Last session: 2026-02-17
Stopped at: Completed 10-02-PLAN.md. Phase 10 complete. 12-step pipeline with frontend. Ready for Phase 11.
Resume file: None
