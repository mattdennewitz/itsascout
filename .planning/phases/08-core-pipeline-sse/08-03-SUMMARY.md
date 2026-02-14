---
phase: 08-core-pipeline-sse
plan: 03
subsystem: ui
tags: [react, inertia, eventsource, sse, tailwind, frontend, jobs]

# Dependency graph
requires:
  - phase: 08-01
    provides: "Pipeline supervisor with Redis pub/sub events (publish_step_event) and step result storage on ResolutionJob"
provides:
  - Jobs/Show.tsx page with EventSource-driven pipeline progress cards
  - URL submission form on Publishers/Index.tsx homepage
  - Frontend ready for SSE streaming from /api/jobs/<uuid>/stream endpoint
affects: [09-robots-sitemap, 11-report-card-polish]

# Tech tracking
tech-stack:
  added: []
  patterns: ["EventSource SSE client consuming Redis pub/sub events via /api/jobs/<uuid>/stream", "CSRF token from cookie for standard form POST", "Completed job renders from Inertia props without SSE", "StepCard component with status-based styling (pending/started/completed/failed/skipped)"]

key-files:
  created:
    - scrapegrape/frontend/src/Pages/Jobs/Show.tsx
  modified:
    - scrapegrape/frontend/src/Pages/Publishers/Index.tsx

key-decisions:
  - "Standard HTML form POST to /submit (not Inertia useForm) so Inertia intercepts the redirect as SPA transition"
  - "CSRF token read from document.cookie (csrftoken) matching Django's default cookie name"
  - "Completed jobs build stepStatuses from props (waf_result, tos_result) for immediate rendering without SSE"
  - "EventSource closes on 'done' event, then reloads via router.reload() after 500ms delay to get final server props"

patterns-established:
  - "Jobs/Show uses .layout pattern for AppLayout (same as Publishers/Index)"
  - "StepCard component renders pipeline steps with status-based border/bg colors and optional data summary"
  - "mergedStatuses pattern: initialStatuses from props merged with live SSE stepStatuses"

# Metrics
duration: 2min
completed: 2026-02-14
---

# Phase 8 Plan 3: Frontend Pages Summary

**Jobs/Show page with EventSource-driven progress cards and homepage URL submission form POSTing to /submit**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-14T15:44:19Z
- **Completed:** 2026-02-14T15:46:23Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Jobs/Show.tsx renders pipeline progress with 4 step cards that update in real time via EventSource
- EventSource connects to /api/jobs/<uuid>/stream for pending/running jobs, closes on terminal 'done' event
- Completed jobs render step results from Inertia props (waf_result, tos_result) without SSE connection
- Publishers/Index.tsx now has a prominent URL input form above the publisher table that POSTs to /submit with CSRF token
- Both Vite build and TypeScript compilation pass with zero errors

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Jobs/Show.tsx with EventSource progress cards** - `5eb1cc9` (feat)
2. **Task 2: Add URL input form to Publishers/Index.tsx** - `92a1e5a` (feat)

## Files Created/Modified
- `scrapegrape/frontend/src/Pages/Jobs/Show.tsx` - Streaming job results page with EventSource, step cards, status badges, and completed job rendering from props
- `scrapegrape/frontend/src/Pages/Publishers/Index.tsx` - Added URL submission form above existing publisher table with CSRF token support

## Decisions Made
- Standard HTML form POST to /submit (not Inertia useForm) because the submit endpoint redirects to /jobs/<uuid> and Inertia intercepts form submission redirects as SPA transitions
- CSRF token read from document.cookie matching Django's csrftoken cookie name
- Completed jobs build stepStatuses from waf_result and tos_result props for immediate rendering without SSE
- EventSource 'done' listener closes connection then reloads page via Inertia router.reload() after 500ms delay to fetch final server props

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Frontend pages ready to consume SSE events from /api/jobs/<uuid>/stream endpoint (Plan 02 provides this)
- URL form submits to /submit endpoint (needs backend view to be wired in Plan 02 or separate plan)
- Jobs/Show.tsx will be rendered by Inertia when backend routes /jobs/<uuid> to the Jobs/Show component
- Vite build clean, TypeScript strict mode passing

## Self-Check: PASSED

All 2 created/modified files verified present. Both task commits (5eb1cc9, 92a1e5a) verified in git log. Vite build and TypeScript compilation clean.

---
*Phase: 08-core-pipeline-sse*
*Completed: 2026-02-14*
