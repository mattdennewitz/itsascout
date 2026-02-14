---
phase: 08-core-pipeline-sse
plan: 01
subsystem: pipeline
tags: [rq, redis-pubsub, pipeline, supervisor, waf, tos, tdd, monkeypatch]

# Dependency graph
requires:
  - phase: 06-02
    provides: "Publisher/ResolutionJob models with domain, UUID PK, JSON result columns, factories"
  - phase: 07-01
    provides: "FetchStrategyManager for page fetching with fallback"
provides:
  - Pipeline supervisor RQ job (run_pipeline) that runs all steps sequentially
  - WAF step function wrapping scan_url_with_wafw00f
  - ToS discovery step calling discover_terms_and_privacy agent
  - ToS evaluation step calling evaluate_terms_and_conditions agent
  - Redis pub/sub event publisher (publish_step_event) for step progress
  - Freshness TTL check (should_skip_publisher_steps) using PUBLISHER_FRESHNESS_TTL
  - 15 unit tests covering all pipeline components with mocked externals
affects: [08-02-sse-endpoint, 08-03-frontend, 09-robots-sitemap]

# Tech tracking
tech-stack:
  added: [pytest-asyncio 1.3.0]
  patterns: ["Single supervisor RQ job calling step functions sequentially", "Redis pub/sub for worker-to-SSE communication", "Monkeypatch module-level function references for test isolation", "Step results saved to ResolutionJob before publishing events"]

key-files:
  created:
    - scrapegrape/publishers/pipeline/__init__.py
    - scrapegrape/publishers/pipeline/events.py
    - scrapegrape/publishers/pipeline/steps.py
    - scrapegrape/publishers/pipeline/supervisor.py
    - scrapegrape/publishers/tests/test_pipeline.py
  modified:
    - pyproject.toml
    - uv.lock

key-decisions:
  - "Pipeline steps call existing ingestion agents (terms_discovery, terms_evaluation) directly rather than rewriting"
  - "Each step saves result to ResolutionJob *before* publishing event (data persists even if subscriber misses event)"
  - "Supervisor merges ToS evaluation data into existing tos_result dict (discovery + evaluation in one field)"
  - "Publisher flat fields (waf_detected, waf_type, tos_url, tos_permissions) updated in supervisor for quick reads"

patterns-established:
  - "publish_step_event(job_id, step, status, data) for all pipeline progress communication"
  - "Step functions return plain dicts, supervisor handles DB persistence and event publishing"
  - "should_skip_publisher_steps(publisher) checks PUBLISHER_FRESHNESS_TTL (24h default)"
  - "Pipeline try/except wraps entire body: sets status='failed' and publishes failure event on exception"

# Metrics
duration: 3min
completed: 2026-02-14
---

# Phase 8 Plan 1: Pipeline Supervisor & Steps Summary

**Sequential pipeline supervisor RQ job with WAF check, ToS discovery, ToS evaluation steps, Redis pub/sub events, and freshness TTL skip logic -- all TDD with 15 unit tests**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-14T15:39:02Z
- **Completed:** 2026-02-14T15:42:00Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Pipeline supervisor runs as single RQ job, executing WAF -> ToS discovery -> ToS evaluation sequentially
- Each step saves results to ResolutionJob and publishes Redis events for SSE streaming
- Freshness TTL check skips publisher-level steps when checked within 24 hours
- Publisher flat fields (waf_detected, waf_type, tos_url, tos_permissions) updated for quick reads
- TDD: 15 tests written first (RED), implementation makes all pass (GREEN), 60 total tests passing

## Task Commits

Each task was committed atomically:

1. **Task 1: RED -- Write failing tests** - `b8bb42c` (test)
2. **Task 2: GREEN -- Implement pipeline module** - `782c4c9` (feat)

_TDD: Task 1 = RED (all 15 tests fail with ModuleNotFoundError), Task 2 = GREEN (all 60 tests pass)_

## Files Created/Modified
- `scrapegrape/publishers/pipeline/__init__.py` - Package exports run_pipeline and publish_step_event
- `scrapegrape/publishers/pipeline/events.py` - Redis pub/sub event publishing helper
- `scrapegrape/publishers/pipeline/steps.py` - WAF, ToS discovery, ToS evaluation step functions + freshness TTL check
- `scrapegrape/publishers/pipeline/supervisor.py` - Pipeline supervisor RQ job orchestrating all steps
- `scrapegrape/publishers/tests/test_pipeline.py` - 15 tests for all pipeline components
- `pyproject.toml` - Added pytest-asyncio dev dependency
- `uv.lock` - Updated lockfile

## Decisions Made
- Pipeline steps call existing ingestion agents directly (discover_terms_and_privacy, evaluate_terms_and_conditions) rather than rewriting them -- keeps backward compatibility with admin actions
- Each step saves result to ResolutionJob before publishing Redis event, so data persists even if SSE subscriber misses the event
- Supervisor merges ToS evaluation data into existing tos_result dict (discovery + evaluation combined in one JSON field)
- Publisher flat fields updated in supervisor for quick reads without joining to ResolutionJob

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Pipeline supervisor ready to be queued from URL submission endpoint
- Redis pub/sub events ready for SSE endpoint subscription (Plan 02)
- All step results stored on ResolutionJob for frontend display (Plan 03)
- 60 tests passing, zero regressions

## Self-Check: PASSED

All 5 created files verified present. Both task commits (b8bb42c, 782c4c9) verified in git log. 60/60 tests passing.

---
*Phase: 08-core-pipeline-sse*
*Completed: 2026-02-14*
