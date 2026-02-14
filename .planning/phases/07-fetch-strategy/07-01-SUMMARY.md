---
phase: 07-fetch-strategy
plan: 01
subsystem: fetching
tags: [curl-cffi, zyte, strategy-pattern, waf-detection, tls-impersonation, fallback]

# Dependency graph
requires:
  - phase: 06-infrastructure-models
    provides: Publisher model with domain field, PublisherFactory, pytest/factory-boy setup
provides:
  - FetchStrategyManager entry point for all page fetching
  - CurlCffiFetcher with browser TLS impersonation and WAF detection
  - ZyteFetcher wrapping Zyte API proxy service
  - FetchError and AllStrategiesExhausted exception hierarchy
  - Per-publisher fetch_strategy memory field with migration
  - FetchResult dataclass and BaseFetcher protocol
affects: [08-pipeline, 09-sse-ui, any phase that fetches pages]

# Tech tracking
tech-stack:
  added: [curl-cffi 0.14.0, cffi 2.0.0, pycparser 3.0]
  patterns: [Strategy pattern with Protocol, fallback chain with publisher memory, WAF signature detection heuristics]

key-files:
  created:
    - scrapegrape/publishers/fetchers/__init__.py
    - scrapegrape/publishers/fetchers/base.py
    - scrapegrape/publishers/fetchers/exceptions.py
    - scrapegrape/publishers/fetchers/curl_cffi_fetcher.py
    - scrapegrape/publishers/fetchers/zyte_fetcher.py
    - scrapegrape/publishers/fetchers/manager.py
    - scrapegrape/publishers/tests/test_fetchers.py
    - scrapegrape/publishers/migrations/0003_publisher_fetch_strategy.py
  modified:
    - scrapegrape/publishers/models.py
    - scrapegrape/publishers/factories.py
    - pyproject.toml
    - uv.lock

key-decisions:
  - "curl-cffi impersonate='chrome' (latest) as default -- auto-updates with library releases"
  - "WAF detection via 6 content signatures on 200 responses plus 403 status check -- no length heuristic"
  - "Publisher.fetch_strategy saved only when strategy changes to avoid unnecessary DB writes"
  - "AllStrategiesExhausted collects all FetchErrors for diagnostic visibility"

patterns-established:
  - "Strategy pattern: BaseFetcher Protocol with name + fetch(url) -> FetchResult"
  - "Fallback chain: FetchStrategyManager iterates ordered strategies, catches FetchError, continues"
  - "Publisher memory: fetch_strategy field persisted via save(update_fields=[...]) on strategy change"
  - "Monkeypatch pattern: patch library-level functions (curl_requests.get, requests.post) not instance methods"

# Metrics
duration: 3min
completed: 2026-02-14
---

# Phase 7 Plan 1: Fetch Strategy Manager Summary

**curl-cffi TLS impersonation fetcher with Zyte API fallback, WAF signature detection, and per-publisher strategy memory via Strategy pattern**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-14T14:46:46Z
- **Completed:** 2026-02-14T14:50:20Z
- **Tasks:** 2
- **Files modified:** 12

## Accomplishments
- CurlCffiFetcher with browser TLS impersonation (chrome fingerprint) and 6-signature WAF block detection
- ZyteFetcher wrapping Zyte API proxy with base64 decode and API key validation
- FetchStrategyManager with ordered fallback chain and per-publisher strategy persistence
- 16 new tests covering all fetcher behaviors, manager fallback/memory logic, and Publisher model field
- Full test suite: 45 tests passing (29 existing + 16 new), zero failures

## Task Commits

Each task was committed atomically:

1. **Task 1: RED -- Write failing tests** - `31ebce4` (test)
2. **Task 2: GREEN -- Implement fetchers, manager, migration** - `4037d22` (feat)

_TDD: Task 1 = RED (all tests fail with ModuleNotFoundError), Task 2 = GREEN (all 45 tests pass)_

## Files Created/Modified
- `scrapegrape/publishers/fetchers/__init__.py` - Package exports: FetchStrategyManager, FetchResult, FetchError, AllStrategiesExhausted
- `scrapegrape/publishers/fetchers/base.py` - FetchResult dataclass and BaseFetcher Protocol
- `scrapegrape/publishers/fetchers/exceptions.py` - FetchError (single strategy) and AllStrategiesExhausted (all failed)
- `scrapegrape/publishers/fetchers/curl_cffi_fetcher.py` - CurlCffiFetcher with WAF signature detection on 200/403 responses
- `scrapegrape/publishers/fetchers/zyte_fetcher.py` - ZyteFetcher wrapping Zyte API with b64 decode
- `scrapegrape/publishers/fetchers/manager.py` - FetchStrategyManager with fallback chain and publisher memory
- `scrapegrape/publishers/tests/test_fetchers.py` - 16 tests: CurlCffi (4), Zyte (3), Manager (7), Publisher field (2)
- `scrapegrape/publishers/migrations/0003_publisher_fetch_strategy.py` - Add fetch_strategy CharField to Publisher
- `scrapegrape/publishers/models.py` - Added FETCH_STRATEGY_CHOICES and fetch_strategy field
- `scrapegrape/publishers/factories.py` - Added fetch_strategy="" default to PublisherFactory
- `pyproject.toml` - Added curl-cffi dependency
- `uv.lock` - Updated lockfile with curl-cffi, cffi, pycparser

## Decisions Made
- Used `impersonate="chrome"` (latest) rather than pinning a specific Chrome version -- auto-updates with curl-cffi releases
- WAF detection uses 6 content-based signatures (cloudflare, checking your browser, access denied, just a moment, cf-browser-verification, ray id) -- no minimum length heuristic to avoid false positives
- `Publisher.fetch_strategy` saved only when strategy changes (guarded by `if publisher.fetch_strategy != strategy_name`) to avoid unnecessary DB writes
- AllStrategiesExhausted stores all collected FetchError instances for diagnostic logging
- ZyteFetcher reads ZYTE_API_KEY at call time (not init time) so missing key is caught per-request

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. ZYTE_API_KEY is expected to already be configured from existing ingestion service setup.

## Next Phase Readiness
- FetchStrategyManager is the single entry point for all page fetching in the pipeline
- Pipeline steps (Phase 8) can call `FetchStrategyManager().fetch(url, publisher=publisher)` to get HTML
- Publisher.fetch_strategy field enables per-publisher optimization over time
- All existing tests continue to pass -- no regressions

## Self-Check: PASSED

All 8 created files verified on disk. Both task commits (31ebce4, 4037d22) found in git log. 45/45 tests passing.

---
*Phase: 07-fetch-strategy*
*Completed: 2026-02-14*
