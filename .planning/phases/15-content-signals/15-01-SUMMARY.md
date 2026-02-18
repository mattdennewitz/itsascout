---
phase: 15-content-signals
plan: 01
subsystem: pipeline
tags: [feedparser, rss, sitemap, xml, frequency-estimation, news-sitemap]

# Dependency graph
requires:
  - phase: 13-data-foundation
    provides: "Publisher model fields (sitemap_urls, rss_urls, has_news_sitemap, update_frequency*)"
  - phase: 14-common-crawl-presence
    provides: "CC step pattern for new pipeline steps"
provides:
  - "run_sitemap_analysis_step: detects xmlns:news namespace, follows sitemap indexes, extracts lastmod dates"
  - "run_frequency_step: computes publishing frequency from RSS dates with sitemap lastmod fallback"
  - "_format_frequency_label: human-readable frequency strings"
affects: [17-pipeline-wiring, 18-report-card-ui]

# Tech tracking
tech-stack:
  added: [feedparser 6.0.12, sgmllib3k 1.0.0]
  patterns: [sitemap-xml-namespace-detection, rss-date-frequency-estimation, confidence-thresholds]

key-files:
  created: []
  modified:
    - scrapegrape/publishers/pipeline/steps.py
    - scrapegrape/publishers/tests/test_pipeline.py
    - pyproject.toml

key-decisions:
  - "String search for xmlns:news instead of full XML namespace parsing -- faster and sufficient for detection"
  - "Median interval for frequency estimation -- robust against outliers from holiday gaps"
  - "Conservative confidence thresholds: high >= 10 items + 7 days, medium >= 5 + 3 days"

patterns-established:
  - "Sitemap analysis pattern: fetch sitemap URLs, check for sitemapindex, follow children (limit 2), prioritize URLs with 'news' in name"
  - "Frequency estimation pattern: RSS first (feedparser), sitemap lastmod fallback, confidence indicator"

# Metrics
duration: 2min
completed: 2026-02-18
---

# Phase 15 Plan 01: Content Signals Summary

**Sitemap news namespace detection and RSS-based publishing frequency estimation with feedparser, including sitemap lastmod fallback and confidence indicators**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-18T04:44:07Z
- **Completed:** 2026-02-18T04:46:40Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Added run_sitemap_analysis_step that detects xmlns:news namespace, follows sitemap index children, and extracts lastmod dates
- Added run_frequency_step that computes publishing frequency from RSS dates via feedparser with sitemap lastmod fallback
- Installed feedparser 6.0.12 dependency for robust RSS/Atom date parsing
- 11 new tests covering both step functions with no regressions (105 total tests pass)

## Task Commits

Each task was committed atomically:

1. **Task 1: Install feedparser and add step functions** - `3bee75f` (feat)
2. **Task 2: Add unit tests for both step functions** - `6c3655b` (test)

## Files Created/Modified
- `scrapegrape/publishers/pipeline/steps.py` - Added run_sitemap_analysis_step, run_frequency_step, and 7 helper functions
- `scrapegrape/publishers/tests/test_pipeline.py` - Added TestSitemapAnalysisStep (5 tests) and TestFrequencyStep (6 tests)
- `pyproject.toml` - Added feedparser 6.0.12 dependency
- `uv.lock` - Updated lockfile

## Decisions Made
- Used string search for xmlns:news detection instead of full XML namespace parsing -- faster and sufficient for presence detection
- Median interval for frequency estimation rather than mean -- robust against outliers from publishing gaps
- Conservative confidence thresholds (high: >= 10 items + 7 days span) to avoid misleading estimates

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed FetchResult constructor in tests**
- **Found during:** Task 2 (unit tests)
- **Issue:** Tests used `strategy="direct"` but FetchResult expects `strategy_used="direct"`
- **Fix:** Changed all FetchResult instantiations to use correct keyword `strategy_used`
- **Files modified:** scrapegrape/publishers/tests/test_pipeline.py
- **Verification:** All 11 new tests pass
- **Committed in:** 6c3655b (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Trivial keyword naming fix. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Both step functions ready for supervisor wiring in Phase 17
- Step functions follow established pattern (take Publisher, return dict, catch exceptions)
- Phase 15 Plan 02 can proceed with any remaining content signal work

---
*Phase: 15-content-signals*
*Completed: 2026-02-18*
