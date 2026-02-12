---
phase: 03-core-view-migration
plan: 02
subsystem: ui
tags: [inertia, react, django-middleware, spa-navigation, shared-props]

# Dependency graph
requires:
  - phase: 03-01
    provides: Base Inertia page component pattern (Publishers/Index.tsx) and inertia_render view
provides:
  - Shared data middleware for auth and flash messages across all Inertia pages (INRT-06)
  - Persistent AppLayout component with Inertia Link navigation (INRT-05, INRT-07)
  - Pattern for .layout property assignment on page components
affects: [04-bulk-operations-migration, 05-optimization-and-cleanup]

# Tech tracking
tech-stack:
  added: [inertia.share for middleware-level props injection]
  patterns: [persistent-layout-pattern, shared-data-middleware, inertia-link-navigation]

key-files:
  created:
    - scrapegrape/scrapegrape/middleware.py
    - scrapegrape/frontend/src/Layouts/AppLayout.tsx
  modified:
    - scrapegrape/scrapegrape/settings.py
    - scrapegrape/frontend/src/Pages/Publishers/Index.tsx

key-decisions:
  - "Positioned shared data middleware after AuthenticationMiddleware and MessageMiddleware to ensure request.user and session messages are available"
  - "Used lambda functions in inertia.share() for lazy evaluation to avoid computing shared props on non-Inertia requests (admin, static files)"
  - "Implemented auto-dismissing flash messages with 5-second timeout using React useEffect"
  - "Used .layout property pattern for persistent layout assignment to prevent layout remounting on navigation"

patterns-established:
  - "Shared data pattern: middleware injects auth and flash props via inertia.share(), available on all pages via usePage().props"
  - "Persistent layout pattern: PageComponent.layout = (page) => <AppLayout>{page}</AppLayout>"
  - "SPA navigation pattern: Use Inertia Link component instead of <a> tags for internal routes"

# Metrics
duration: 4min
completed: 2026-02-12
---

# Phase 3 Plan 2: Inertia Shared Data and Persistent Layouts Summary

**Shared data middleware with auth/flash props injection, persistent AppLayout with Inertia Link navigation, enabling multi-page SPA foundation**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-12T21:36:00Z
- **Completed:** 2026-02-12T21:40:25Z
- **Tasks:** 3 (2 automated + 1 human verification checkpoint)
- **Files modified:** 4

## Accomplishments
- Shared data middleware injects user authentication state and flash messages on every Inertia response (INRT-06)
- Created persistent AppLayout component that preserves state across page navigations (INRT-07)
- Implemented Inertia Link navigation for SPA-like transitions without full page reloads (INRT-05)
- Flash messages display and auto-dismiss after 5 seconds
- Auth state shows username in nav when logged in

## Task Commits

Each task was committed atomically:

1. **Task 1: Create shared data middleware and register in Django settings** - `71f74da` (feat)
2. **Task 2: Create persistent AppLayout with Link navigation and assign to Publishers/Index** - `9dd2ed2` (feat)
3. **Task 3: Verify complete Inertia migration with layout and shared data** - APPROVED by user (checkpoint)

## Files Created/Modified
- `scrapegrape/scrapegrape/middleware.py` - Shared data middleware injecting auth state and flash messages via inertia.share()
- `scrapegrape/frontend/src/Layouts/AppLayout.tsx` - Persistent layout with nav bar, flash message display, and Inertia Link navigation
- `scrapegrape/scrapegrape/settings.py` - Added shared data middleware to MIDDLEWARE list after MessageMiddleware
- `scrapegrape/frontend/src/Pages/Publishers/Index.tsx` - Added .layout property to assign persistent AppLayout

## Decisions Made

**Middleware positioning:** Placed inertia_share middleware after AuthenticationMiddleware and MessageMiddleware in settings.py to ensure request.user and session messages are available when share() executes. Positioned before XFrameOptionsMiddleware (non-critical middleware).

**Lazy evaluation with lambdas:** Used lambda functions in inertia.share() to wrap auth and flash data. This ensures shared props are only computed when Inertia actually renders a response, avoiding unnecessary work on non-Inertia requests like /admin/, /static/, or API calls.

**Flash message auto-dismiss:** Implemented 5-second auto-dismiss using React useEffect with cleanup. Flash messages use session.pop() in middleware so they're automatically cleared after being read, preventing re-display on subsequent requests.

**Persistent layout pattern:** Used the .layout property on page components rather than wrapping in render_inertia(). This tells Inertia to preserve the layout component instance across navigations, preventing remounting and preserving any layout state (like open menus or animations).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. All tasks completed successfully without blockers or errors.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Phase 3 complete.** All core Inertia requirements delivered:
- INRT-01 to INRT-04: Infrastructure (Phase 1)
- INRT-05 to INRT-07: Shared data, layouts, Link navigation (Phase 2)
- VIEW-01 to VIEW-02: Core publisher view migration (Phase 1)

Ready for Phase 4 (bulk operations migration) which will convert table actions (create, update, delete) to Inertia forms and optimize complex views.

**Foundation in place:**
- Middleware pattern for shared data injection
- Persistent layout pattern for consistent UI
- Page component pattern for Inertia views
- DRF serializer reuse for data transformation
- Link component for SPA navigation

**No blockers.** All verification passed - publisher table renders with nav layout, SPA transitions work, shared data present in props.

## Self-Check: PASSED

All files verified:
- FOUND: scrapegrape/scrapegrape/middleware.py
- FOUND: scrapegrape/frontend/src/Layouts/AppLayout.tsx
- FOUND: scrapegrape/scrapegrape/settings.py
- FOUND: scrapegrape/frontend/src/Pages/Publishers/Index.tsx

All commits verified:
- FOUND: 71f74da
- FOUND: 9dd2ed2

---
*Phase: 03-core-view-migration*
*Completed: 2026-02-12*
