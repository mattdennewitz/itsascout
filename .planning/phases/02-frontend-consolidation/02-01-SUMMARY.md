---
phase: 02-frontend-consolidation
plan: 01
subsystem: infra
tags: [vite, react, django-vite, directory-structure, build-pipeline]

# Dependency graph
requires:
  - phase: 01-inertia-infrastructure
    provides: Inertia middleware, CSRF configuration, dual-path entry point, smoke test pattern
provides:
  - Consolidated frontend structure in scrapegrape/frontend/
  - Django settings pointing to new manifest path
  - Docker Compose volume mounts for new location
  - Inertia directory structure (Pages/, Components/, Layouts/)
  - Verified dev HMR and production build pipeline
affects: [03-view-migration, 04-optimization, 05-cleanup]

# Tech tracking
tech-stack:
  added: []
  patterns: [consolidated-monorepo-structure, inertia-directory-conventions]

key-files:
  created:
    - scrapegrape/frontend/src/Components/.gitkeep
    - scrapegrape/frontend/src/Layouts/.gitkeep
  modified:
    - scrapegrape/scrapegrape/settings.py
    - docker-compose.yml
    - scrapegrape/frontend/src/datatable/columns.tsx

key-decisions:
  - "Moved frontend from sgui/ to scrapegrape/frontend/ for monorepo consolidation"
  - "Established Inertia PascalCase directory structure (Pages/, Components/, Layouts/) alongside existing lowercase directories"
  - "Added STATICFILES_DIRS to Django settings for collectstatic support"
  - "Updated STATIC_URL to /static/ (added leading slash) for consistency with Vite base"

patterns-established:
  - "Monorepo structure: Django backend and React frontend co-located under scrapegrape/"
  - "Dual directory convention: PascalCase for Inertia components (Pages/, Components/, Layouts/), lowercase for existing shadcn/TanStack code"

# Metrics
duration: 1min
completed: 2026-02-12
---

# Phase 2 Plan 1: Frontend Consolidation Summary

**React frontend moved from sgui/ to scrapegrape/frontend/, Django settings and Docker Compose updated for new location, Inertia directory structure established, dev HMR and production build pipeline verified working**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-12T20:37:14Z
- **Completed:** 2026-02-12T20:38:05Z
- **Tasks:** 3 (2 auto, 1 checkpoint)
- **Files modified:** 30+

## Accomplishments
- Frontend consolidated from separate sgui/ directory into scrapegrape/frontend/ for monorepo structure
- Django settings updated with correct manifest_path and STATICFILES_DIRS for new location
- Docker Compose volume mounts updated for vite service
- Inertia directory structure established (Pages/, Components/, Layouts/)
- Dev server HMR and production build pipeline verified working from new location

## Task Commits

Each task was committed atomically:

1. **Task 1: Move sgui/ to scrapegrape/frontend/ and establish Inertia directory structure** - `d65dfcb` (feat)
2. **Task 2: Update Django settings, Docker Compose, and STATICFILES_DIRS** - `aac7745` (feat)
3. **Task 3: Verify dev server HMR and Django integration work from new location** - No commit (verification checkpoint approved by user)

## Files Created/Modified
- `scrapegrape/frontend/` - Entire frontend directory moved from sgui/ (27+ files)
- `scrapegrape/frontend/src/Components/.gitkeep` - Shared Inertia components directory placeholder
- `scrapegrape/frontend/src/Layouts/.gitkeep` - Inertia page layouts directory placeholder
- `scrapegrape/scrapegrape/settings.py` - Updated DJANGO_VITE manifest_path, added STATICFILES_DIRS, fixed STATIC_URL
- `docker-compose.yml` - Updated vite service volume mount from ./sgui to ./scrapegrape/frontend
- `scrapegrape/frontend/src/datatable/columns.tsx` - Added explicit ColumnDef type annotation (deviation fix)

## Decisions Made
- **Monorepo consolidation:** Moved frontend from separate sgui/ directory to scrapegrape/frontend/ to co-locate backend and frontend code. Simplifies development and deployment.
- **Dual directory convention:** Established PascalCase directories (Pages/, Components/, Layouts/) for Inertia components alongside existing lowercase directories (components/, datatable/, lib/) for shadcn/TanStack code. Prevents conflicts and maintains clarity.
- **STATICFILES_DIRS addition:** Added to Django settings for collectstatic support, required for production static file serving.
- **STATIC_URL consistency:** Updated from "static/" to "/static/" to match Vite's base: "/static/" configuration.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed TypeScript column type error during production build**
- **Found during:** Task 2 (running npm run build verification)
- **Issue:** TypeScript compiler failed with "Type 'ColumnDef<Publisher, unknown>[]' is not assignable to type 'ColumnDef<Publisher, any>[]'" in datatable/columns.tsx. Build error blocking verification.
- **Fix:** Added explicit type annotation `ColumnDef<Publisher, any>[]` to columns variable to satisfy TypeScript strict checking
- **Files modified:** scrapegrape/frontend/src/datatable/columns.tsx
- **Verification:** npm run build completed successfully, manifest.json generated
- **Committed in:** aac7745 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Type annotation required for build to succeed. Essential for correctness. No scope creep.

## Issues Encountered
None - move operation and path updates worked as planned after type error fix.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Frontend consolidated in scrapegrape/frontend/ with working build pipeline
- Inertia directory structure established for Phase 3 view migration
- Dev HMR verified working for rapid development
- Production build and static file serving verified
- All 4 Phase 2 requirements (CONS-01 through CONS-04) satisfied
- Ready to begin Phase 3 (View Migration) - converting publisher list view from JSON-in-template to Inertia

**Blockers:** None

**Phase 2 complete.** All 4 requirements delivered:
- CONS-01: React source in scrapegrape/frontend/src/ ✓
- CONS-02: Vite config has correct paths ✓
- CONS-03: Django settings point to correct manifest_path ✓
- CONS-04: Inertia directory structure established ✓

---
*Phase: 02-frontend-consolidation*
*Completed: 2026-02-12*

## Self-Check: PASSED

All claimed files and commits verified:
- ✓ scrapegrape/frontend/src/Components/.gitkeep exists
- ✓ scrapegrape/frontend/src/Layouts/.gitkeep exists
- ✓ scrapegrape/frontend/ directory exists
- ✓ sgui/ directory no longer exists
- ✓ Commit d65dfcb exists
- ✓ Commit aac7745 exists
