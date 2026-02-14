# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-13)

**Core value:** Paste a URL, get a comprehensive scraping report card with real-time progress as each check completes.
**Current focus:** Phase 8 -- Core Pipeline & SSE

## Current Position

Phase: 8 of 11 (Core Pipeline & SSE)
Plan: 1 of 3 in current phase
Status: Plan 08-01 complete
Last activity: 2026-02-14 -- Phase 8 plan 1 complete (pipeline supervisor with WAF and ToS steps)

Progress: [████░░░░░░] 36%

## Performance Metrics

**Velocity:**
- Total plans completed: 4 (v2.0)
- Average duration: 3.3min
- Total execution time: 0.22 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 06-infrastructure-models | 2 | 7min | 3.5min |
| 07-fetch-strategy | 1 | 3min | 3min |
| 08-core-pipeline-sse | 1 | 3min | 3min |

**Recent Trend:**
- Last 5 plans: 06-01 (3min), 06-02 (4min), 07-01 (3min), 08-01 (3min)
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

### Pending Todos

None yet.

### Blockers/Concerns

None currently.

## Session Continuity

Last session: 2026-02-14
Stopped at: Completed 08-01-PLAN.md. Pipeline supervisor with WAF and ToS steps. Plans 08-02 (SSE endpoint) and 08-03 (frontend) remain.
Resume file: None
