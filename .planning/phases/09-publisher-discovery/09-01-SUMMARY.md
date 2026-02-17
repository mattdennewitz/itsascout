---
phase: 09-publisher-discovery
plan: 01
subsystem: pipeline
tags: [protego, robots.txt, sitemap, crawl-policy, sse]

# Dependency graph
requires:
  - phase: 08-core-pipeline-sse
    provides: pipeline supervisor, step pattern, ResolutionJob model with JSON fields
provides:
  - run_robots_step function for robots.txt fetching, parsing, and URL allowance checking
  - run_sitemap_step function for sitemap discovery via robots.txt and common path probing
  - _extract_license_directives helper for RSL License directives in robots.txt
  - Supervisor integration with robots and sitemap steps after ToS evaluation
affects: [09-02-PLAN, 10-report-card]

# Tech tracking
tech-stack:
  added: [protego 0.6.0]
  patterns: [content-type guard for WAF HTML challenges, HEAD-then-GET fallback for sitemap probing]

key-files:
  created: []
  modified:
    - scrapegrape/publishers/pipeline/steps.py
    - scrapegrape/publishers/pipeline/supervisor.py
    - scrapegrape/publishers/tests/test_pipeline.py
    - pyproject.toml

key-decisions:
  - "protego 0.6.0 for robots.txt parsing (Scrapy ecosystem, wildcard support, Sitemap extraction)"
  - "Content-Type text/html guard treats WAF challenge pages as robots.txt not found"
  - "Plain requests.get for robots.txt (no FetchStrategyManager needed for plain text)"
  - "HEAD-then-GET fallback for sitemap probing (handles servers that block HEAD requests)"

patterns-established:
  - "Content-type guard: check Content-Type before parsing to detect WAF HTML challenge pages"
  - "HEAD-then-GET fallback: try HEAD first for efficiency, fall back to streaming GET on 405 or ConnectionError"

# Metrics
duration: 3min
completed: 2026-02-14
---

# Phase 9 Plan 1: Robots.txt + Sitemap Discovery Summary

**robots.txt fetching/parsing with protego and sitemap discovery via robots.txt directives + common path probing, integrated into pipeline supervisor**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-14T22:03:28Z
- **Completed:** 2026-02-14T22:07:02Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- run_robots_step fetches robots.txt, guards against WAF HTML challenges, parses with protego, checks URL allowance, extracts sitemaps/crawl-delay/license directives
- run_sitemap_step combines robots.txt sitemaps with common path probing (HEAD/GET fallback), resolves relative URLs
- Supervisor runs both steps after ToS evaluation, saves to ResolutionJob, publishes SSE events, updates publisher flat fields
- 19 new tests covering all step behaviors plus 4 updated supervisor integration tests

## Task Commits

Each task was committed atomically:

1. **Task 1: Add protego dependency and implement robots.txt + sitemap step functions with tests** - `19e2d18` (feat)
2. **Task 2: Integrate robots and sitemap steps into pipeline supervisor** - `d570d0a` (feat)

## Files Created/Modified
- `scrapegrape/publishers/pipeline/steps.py` - Added run_robots_step, run_sitemap_step, _extract_license_directives, constants
- `scrapegrape/publishers/pipeline/supervisor.py` - Imported and integrated robots/sitemap steps, added skip events
- `scrapegrape/publishers/tests/test_pipeline.py` - 19 new tests (8 robots, 5 sitemap, 4 license, 1 supervisor field update, 1 import)
- `pyproject.toml` - Added protego dependency
- `uv.lock` - Updated lockfile

## Decisions Made
- Used protego 0.6.0 for robots.txt parsing (Scrapy ecosystem, wildcard support, Sitemap extraction built-in)
- Content-Type text/html guard treats WAF challenge pages as "robots.txt not found" rather than attempting parse
- Plain requests.get for robots.txt fetch (no FetchStrategyManager overhead needed for plain text file)
- HEAD-then-GET fallback pattern for sitemap probing (handles servers that return 405 for HEAD)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- robots.txt and sitemap steps fully integrated into pipeline
- robots_result available for RSL detection step (license_directives extracted)
- Publisher flat fields (robots_txt_found, robots_txt_url_allowed, sitemap_urls) populated
- Ready for Plan 2: RSS feed discovery and RSL detection

---
*Phase: 09-publisher-discovery*
*Completed: 2026-02-14*
