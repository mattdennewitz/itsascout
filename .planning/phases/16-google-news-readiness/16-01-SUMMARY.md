---
phase: 16-google-news-readiness
plan: 01
subsystem: pipeline
tags: [google-news, jsonld, schema-org, aggregation, tdd]

# Dependency graph
requires:
  - phase: 15-content-signals
    provides: "sitemap_analysis_result with has_news_sitemap"
  - phase: 13-data-foundation
    provides: "news_signals_result JSONField and google_news_readiness CharField on models"
provides:
  - "run_google_news_step() aggregation function in steps.py"
  - "NEWS_ARTICLE_TYPES constant for subtype detection"
  - "@type preservation in _extract_jsonld_article_fields output"
affects: [16-02 supervisor wiring, 17 TTL skip paths, 18 UI integration]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Pure aggregation step: combine existing pipeline signals into readiness level"]

key-files:
  created: []
  modified:
    - scrapegrape/publishers/pipeline/steps.py
    - scrapegrape/publishers/tests/test_pipeline.py

key-decisions:
  - "Substring check for NewsArticle subtypes (all contain 'NewsArticle' in name)"
  - "matched_type extracted from first ARTICLE_TYPES match for @type field"

patterns-established:
  - "Aggregation step pattern: pure function reading existing result dicts, no HTTP requests"

# Metrics
duration: 2min
completed: 2026-02-18
---

# Phase 16 Plan 01: Google News Readiness Summary

**run_google_news_step aggregating 3 signals (news sitemap, NewsArticle schema, NewsMediaOrganization) into readiness levels, plus @type fix in article extraction**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-18T05:17:50Z
- **Completed:** 2026-02-18T05:19:39Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 2

## Accomplishments
- run_google_news_step returns readiness levels: strong (3 signals), moderate (2), minimal (1), none (0)
- Fixed _extract_jsonld_article_fields to preserve @type in output for downstream consumers
- Added NEWS_ARTICLE_TYPES constant detecting subtypes (OpinionNewsArticle, AnalysisNewsArticle, etc.)
- 9 new tests covering all signal combinations, None inputs, and subtype detection

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests for Google News step and @type extraction** - `56a0d8f` (test)
2. **Task 1 GREEN: Implement Google News readiness step and @type fix** - `cca387c` (feat)

_TDD task: RED commit (failing tests) followed by GREEN commit (implementation)_

## Files Created/Modified
- `scrapegrape/publishers/pipeline/steps.py` - Added NEWS_ARTICLE_TYPES constant, @type preservation in _extract_jsonld_article_fields, run_google_news_step function
- `scrapegrape/publishers/tests/test_pipeline.py` - 9 new tests: TestExtractJsonldArticleFieldsType (3) and TestGoogleNewsStep (6)

## Decisions Made
- Substring check (`any(t in article_type for t in NEWS_ARTICLE_TYPES)`) for detecting NewsArticle subtypes -- all subtypes contain "NewsArticle" in their name
- @type field populated from first matching ARTICLE_TYPES entry using `next()` iterator

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- run_google_news_step ready to be wired into supervisor (Plan 02)
- All three input signals verified available from existing pipeline steps
- Phase 17 will handle TTL skip paths for news_signals_result

## Self-Check: PASSED

- FOUND: scrapegrape/publishers/pipeline/steps.py (50136 bytes)
- FOUND: scrapegrape/publishers/tests/test_pipeline.py (114610 bytes)
- FOUND: .planning/phases/16-google-news-readiness/16-01-SUMMARY.md
- FOUND: 56a0d8f (RED commit)
- FOUND: cca387c (GREEN commit)
- VERIFIED: run_google_news_step importable (via pytest)

---
*Phase: 16-google-news-readiness*
*Completed: 2026-02-18*
