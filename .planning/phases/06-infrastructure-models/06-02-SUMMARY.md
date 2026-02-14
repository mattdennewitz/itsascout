---
phase: 06-infrastructure-models
plan: 02
subsystem: database
tags: [models, url-sanitizer, w3lib, factories, factory-boy, pytest, tdd, django-migration]

# Dependency graph
requires:
  - phase: 06-01
    provides: "pytest/factory-boy/w3lib packages installed, Django settings configured"
provides:
  - Publisher model with domain (unique), 10 discovery flat fields, last_checked_at
  - ResolutionJob model with UUID PK, canonical_url index, status choices, 7 JSON result columns
  - URL sanitizer (sanitize_url, extract_domain) using w3lib with 28-param tracking denylist
  - PublisherFactory and ResolutionJobFactory for test data generation
  - Shared pytest fixtures (publisher, resolution_job) in conftest.py
  - 29-test pytest suite covering URL sanitization edge cases and model behavior
affects: [07-pipeline, 08-vertical-slice, 09-frontend]

# Tech tracking
tech-stack:
  added: []
  patterns: ["w3lib canonicalize_url + url_query_cleaner for URL normalization", "factory_boy DjangoModelFactory with get_or_create", "conftest.py shared fixtures for model testing", "3-step migration pattern for adding unique fields to existing data"]

key-files:
  created:
    - scrapegrape/publishers/url_sanitizer.py
    - scrapegrape/publishers/factories.py
    - scrapegrape/publishers/tests/__init__.py
    - scrapegrape/publishers/tests/test_url_sanitizer.py
    - scrapegrape/publishers/tests/test_models.py
    - scrapegrape/conftest.py
    - scrapegrape/publishers/migrations/0002_publisher_domain_publisher_last_checked_at_and_more.py
  modified:
    - scrapegrape/publishers/models.py
    - scrapegrape/publishers/admin.py
    - scrapegrape/publishers/serializers.py

key-decisions:
  - "3-step migration pattern (add field, populate from URL, add unique) for domain field on existing data"
  - "Factory get_or_create on domain to prevent duplicate publishers in tests"
  - "28 tracking params in denylist covering all major ad/analytics platforms"

patterns-established:
  - "sanitize_url(url) -> canonical URL for deduplication across the pipeline"
  - "extract_domain(url) -> canonical domain for publisher lookup"
  - "PublisherFactory/ResolutionJobFactory for all test data creation"
  - "conftest.py fixtures (publisher, resolution_job) as shared test dependencies"

# Metrics
duration: 4min
completed: 2026-02-14
---

# Phase 6 Plan 2: Data Models & URL Sanitizer Summary

**Publisher/ResolutionJob models with w3lib URL sanitizer, factory_boy factories, and 29-test TDD suite covering URL normalization and model behavior**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-14T14:16:58Z
- **Completed:** 2026-02-14T14:21:14Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- Publisher model extended with domain (unique, auto-populated from URL), 10 discovery flat fields, and freshness tracking
- ResolutionJob model created with UUID PK, canonical_url index, status choices (pending/running/completed/failed), and 7 pipeline result JSONFields
- URL sanitizer using w3lib canonicalize_url + url_query_cleaner: strips www, enforces https, removes fragments, sorts query params, strips 28 tracking params
- TDD workflow: 29 tests written first (RED), then implementation (GREEN) -- all passing
- 3-step migration safely handles existing publisher data (add field, populate domain from URL, add unique constraint)

## Task Commits

Each task was committed atomically:

1. **Task 1: RED -- Write failing tests for URL sanitizer, models, and factories** - `db4d16d` (test)
2. **Task 2: GREEN -- Implement models, URL sanitizer, factories, and migration** - `2f775f9` (feat)

## Files Created/Modified
- `scrapegrape/publishers/url_sanitizer.py` - sanitize_url and extract_domain using w3lib
- `scrapegrape/publishers/models.py` - Extended Publisher + new ResolutionJob model
- `scrapegrape/publishers/factories.py` - PublisherFactory and ResolutionJobFactory
- `scrapegrape/conftest.py` - Shared pytest fixtures (publisher, resolution_job)
- `scrapegrape/publishers/tests/test_url_sanitizer.py` - 19 URL sanitization tests
- `scrapegrape/publishers/tests/test_models.py` - 10 model behavior tests
- `scrapegrape/publishers/tests/__init__.py` - Test package init
- `scrapegrape/publishers/migrations/0002_...` - Publisher extension + ResolutionJob migration
- `scrapegrape/publishers/admin.py` - domain in list_display/search, ResolutionJobAdmin registered
- `scrapegrape/publishers/serializers.py` - domain field added to PublisherSerializer

## Decisions Made
- Used 3-step migration pattern for domain field: add without unique, populate from existing URLs, then add unique constraint. This safely handles the existing Guardian publisher record.
- Factory uses `django_get_or_create = ("domain",)` to prevent duplicate publishers in test factories; unique constraint test uses direct model creation to bypass this.
- Comprehensive 28-param tracking denylist covers UTM variants, Facebook (fbclid), Google (gclid, gbraid, wbraid), Microsoft (msclkid), Twitter (twclid), Instagram (igshid), Mailchimp, and other ad platforms.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed unique constraint test bypassing factory get_or_create**
- **Found during:** Task 2 (GREEN phase, test verification)
- **Issue:** `test_publisher_domain_unique` used PublisherFactory for both creations, but factory's `django_get_or_create` silently returns existing record instead of raising IntegrityError
- **Fix:** Changed second creation to use `Publisher.objects.create()` directly to test the actual database constraint
- **Files modified:** scrapegrape/publishers/tests/test_models.py
- **Verification:** Test now correctly raises IntegrityError on duplicate domain
- **Committed in:** 2f775f9 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Essential fix for test correctness. No scope creep.

## Issues Encountered
- Migration initially failed with `DuplicateTable: relation "publishers_publisher_domain_812c56c6_like" already exists` because the 3-step migration created a db_index on Step 1 (CharField _like index) and Step 3's AlterField tried to recreate it. Fixed by removing db_index from Step 1, only applying it in Step 3 with the unique constraint.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Publisher and ResolutionJob models ready for pipeline orchestration in Phase 07
- URL sanitizer ready for URL submission endpoint deduplication
- Factories and fixtures ready for all future test writing
- `uv run pytest scrapegrape/ -v` runs 29 passing tests in <1s

## Self-Check: PASSED

All 10 files verified present. Both task commits (db4d16d, 2f775f9) verified in git log.

---
*Phase: 06-infrastructure-models*
*Completed: 2026-02-14*
