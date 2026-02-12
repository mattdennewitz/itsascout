---
phase: 04-interactive-features
plan: 02
subsystem: ui
tags: [inertia, partial-reloads, deferred-props, search, performance]
dependency_graph:
  requires:
    - phase: 04-01
      provides: Form submissions with useForm hook and session-based validation
    - phase: 03-02
      provides: Persistent AppLayout and Link navigation
    - phase: 03-01
      provides: Core view migration with Subquery optimization
  provides:
    - Server-side search filtering for publisher table
    - Deferred props for expensive publisher queries
    - Partial reloads with only: ['publishers']
    - Debounced search with preserved table state
  affects: [phase-05, admin-views]
tech_stack:
  added: []
  patterns: [deferred-props, partial-reloads, debounced-search, preserve-state]
key_files:
  created: []
  modified:
    - scrapegrape/publishers/views.py
    - scrapegrape/frontend/src/Pages/Publishers/Index.tsx
decisions:
  - "Wrapped expensive publisher query in defer() closure to delay loading until after initial page render"
  - "Used only: ['publishers'] for partial reload to avoid refetching all page props during filtering"
  - "Implemented 300ms debounce on search input to reduce server requests"
  - "Used preserveState and preserveScroll to maintain table sort/expansion and scroll position during filtering"
patterns_established:
  - "Deferred prop pattern: Wrap expensive queries in defer() closure, wrap component in <Deferred> with fallback"
  - "Partial reload pattern: Use router.get with only: ['prop'] + preserveState + preserveScroll for table filtering"
  - "Debounced search pattern: setTimeout with cleanup in useEffect, read search from URL params on mount"
metrics:
  duration_minutes: 2
  tasks_completed: 2
  files_created: 0
  files_modified: 2
  commits: 2
  requirements_delivered: [VIEW-03, VIEW-04]
  completed_date: 2026-02-12
---

# Phase 04 Plan 02: Partial Reloads and Deferred Props Summary

**Debounced search filtering with partial reloads (only: ['publishers']) and deferred props (defer()) for optimized table interactions**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-12T23:43:18Z
- **Completed:** 2026-02-12T23:45:04Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Expensive publisher query wrapped in defer() for deferred loading after initial page shell renders
- Search input triggers debounced partial reloads with only: ['publishers'] to prevent refetching all props
- Table sort order, expanded rows, and scroll position preserved during filtering via preserveState and preserveScroll
- Loading spinner shown during deferred prop loading

## Task Commits

Each task was committed atomically:

1. **Task 1: Add server-side search filtering and defer() wrapper to table view** - `2ab22bb` (feat)
2. **Task 2: Add debounced search input, Deferred wrapper, and partial reload to Index page** - `af36bb7` (feat)

## Files Created/Modified
- `scrapegrape/publishers/views.py` - Added defer() wrapper for expensive publisher query, search param filtering
- `scrapegrape/frontend/src/Pages/Publishers/Index.tsx` - Added debounced search input, Deferred wrapper, partial reload with only: ['publishers']

## Decisions Made

**1. Wrapped expensive publisher query in defer() closure**
- **Rationale:** Delay Subquery + in_bulk operations until after initial page shell renders, improving perceived load time
- **Implementation:** Entire load_publishers function passed to defer(), search variable captured by closure
- **Impact:** First page render is instant (empty table with spinner), publisher data loads in separate request

**2. Used only: ['publishers'] for partial reload**
- **Rationale:** Prevent refetching all page props (auth, flash messages) when only publishers list changes
- **Implementation:** router.get with only: ['publishers'] in debounced search effect
- **Impact:** Search requests only fetch/update publishers prop, reducing bandwidth and server work

**3. Implemented 300ms debounce on search input**
- **Rationale:** Reduce server requests while user is still typing
- **Implementation:** setTimeout with 300ms delay, cleanup function clears timeout on unmount or search change
- **Impact:** Search requests only fire 300ms after user stops typing

**4. Used preserveState and preserveScroll**
- **Rationale:** Maintain table sort order, expanded rows, and scroll position during filtering for better UX
- **Implementation:** preserveState: true preserves TanStack Table state, preserveScroll: true prevents scroll-to-top
- **Impact:** User's table configuration (sort, expansion) and scroll position remain intact during search

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Requirements Delivered

**VIEW-03: Lazy/deferred props** ✅
- Expensive publisher data loaded via defer() deferred props
- LoadingSpinner shown while deferred data loads
- Initial page shell renders instantly, publisher data fetched separately

**VIEW-04: Partial reloads** ✅
- Search input filters publishers server-side by name (case-insensitive)
- Partial reloads with only: ['publishers'] prevent refetching all props
- Table state (sort, expanded rows) preserved during filtering via preserveState
- Scroll position preserved via preserveScroll
- Debounced search (300ms) with replace:true avoids history spam

## Architecture Impact

**Pattern Established:**
This plan establishes the performance optimization patterns for Inertia views:

1. **Deferred Props Pattern:**
   - Backend: Wrap expensive queries in defer(callable)
   - Frontend: Wrap component in <Deferred data="prop" fallback={<Spinner />}>
   - Result: Instant initial render, deferred data loads separately

2. **Partial Reload Pattern:**
   - Backend: Accept search/filter params, return filtered data
   - Frontend: router.get with only: ['dataProps'] + preserveState + preserveScroll
   - Result: Table interactions don't refetch entire page, state preserved

3. **Debounced Search Pattern:**
   - Initialize search state from URL params on mount
   - useEffect with setTimeout and cleanup for debouncing
   - Pass search || undefined to avoid empty query params

**Future Views:**
All future table/list views should use this exact pattern for filtering, pagination, and sorting. The defer() + partial reload combination delivers optimal performance for data-heavy views.

## Next Phase Readiness

Phase 4 Plan 2 complete. VIEW-03 and VIEW-04 requirements delivered. Phase 4 now 100% complete (3/3 requirements: INRT-08, VIEW-03, VIEW-04).

Next: Phase 5 (Cleanup and Documentation) should remove debug routes, add production configuration, and document the refactor.

## Self-Check: PASSED

**Modified Files:**
- FOUND: scrapegrape/publishers/views.py
- FOUND: scrapegrape/frontend/src/Pages/Publishers/Index.tsx

**Commits:**
- FOUND: 2ab22bb
- FOUND: af36bb7

**Build Verification:**
- Django system check: ✅ No issues
- Frontend build: ✅ Successful (791 modules, 488.64 kB bundle)

---
*Phase: 04-interactive-features*
*Completed: 2026-02-12*
