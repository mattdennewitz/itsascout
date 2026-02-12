---
phase: 01-inertia-infrastructure
plan: 01
subsystem: infra
tags: [inertia-django, inertiajs, react, django-middleware, csrf, vite]

# Dependency graph
requires:
  - phase: 00-research
    provides: "Stack validation and pitfall identification for django-inertia"
provides:
  - "Django backend configured with inertia-django middleware and settings"
  - "React frontend configured with @inertiajs/react and createInertiaApp"
  - "CSRF configured for Django/Axios compatibility (cookie-based)"
  - "Smoke test infrastructure validating Django-to-React prop flow"
  - "Dual-path entry point supporting Inertia + legacy views simultaneously"
affects: [02-frontend-consolidation, 03-view-migration, all-subsequent-phases]

# Tech tracking
tech-stack:
  added: [inertia-django@1.2.0, @inertiajs/react@2.3.8, axios]
  patterns: ["Django render_inertia() → InertiaMiddleware → React page components", "Dual-path main.tsx for gradual migration", "Cookie-based CSRF via Axios defaults"]

key-files:
  created:
    - scrapegrape/publishers/views.py (inertia_smoke_test)
    - sgui/src/Pages/Debug/InertiaTest.tsx
    - sgui/src/main.tsx (createInertiaApp entry point)
  modified:
    - scrapegrape/scrapegrape/settings.py (middleware, INSTALLED_APPS, INERTIA_LAYOUT)
    - scrapegrape/scrapegrape/urls.py (debug route)
    - scrapegrape/templates/base.html ({% block inertia %} + #root dual mount)
    - pyproject.toml (inertia-django dependency)
    - sgui/package.json (@inertiajs/react, axios)

key-decisions:
  - "Dual-path entry point in main.tsx: Inertia routes render via createInertiaApp, legacy routes preserve existing App.tsx mounting on #root"
  - "Cookie-based CSRF via Axios defaults (xsrfHeaderName/xsrfCookieName) instead of meta tag pattern"
  - "InertiaMiddleware positioned after CsrfViewMiddleware in Django middleware stack"
  - "Eager page loading (import.meta.glob eager:true) for better tree-shaking and build-time error detection"
  - "Smoke test lives at /_debug/inertia/ for explicit testing without touching production routes"

patterns-established:
  - "Pattern 1: Django views use inertia.render(request, 'Path/Component', props={...}) to render React components"
  - "Pattern 2: React page components live in sgui/src/Pages/**/*.tsx with default exports and typed Props interfaces"
  - "Pattern 3: Base template provides {% block inertia %} for Inertia injection + #root for legacy path"
  - "Pattern 4: CSRF configured at frontend entry point (main.tsx) via Axios global defaults"

# Metrics
duration: 33min
completed: 2026-02-12
---

# Phase 1 Plan 1: Inertia Infrastructure Summary

**Django backend with inertia-django middleware and React frontend with @inertiajs/react successfully configured, validated with smoke test showing prop flow from Django views to React components**

## Performance

- **Duration:** 33 min
- **Started:** 2026-02-12T14:00:40-05:00
- **Completed:** 2026-02-12T14:33:42-05:00
- **Tasks:** 3 (2 auto, 1 checkpoint:human-verify)
- **Files modified:** 10

## Accomplishments
- Inertia.js infrastructure installed and configured on both Django backend and React frontend
- CSRF properly configured for Django/Axios compatibility using cookie-based approach
- Smoke test at /_debug/inertia/ validates Django-to-React prop flow through Inertia
- Dual-path entry point preserves existing legacy table view while enabling Inertia routes
- All existing functionality preserved (root route, Django admin, publisher table)

## Task Commits

Each task was committed atomically:

1. **Task 1: Install Inertia packages and configure Django backend** - `8b54d0e` (feat)
   - Installed inertia-django 1.2.0
   - Configured middleware, INSTALLED_APPS, INERTIA_LAYOUT
   - Created inertia_smoke_test view
   - Registered /_debug/inertia/ route

2. **Task 2: Install frontend packages, configure createInertiaApp, and update base template** - `47af001` (feat)
   - Installed @inertiajs/react and axios
   - Replaced main.tsx with createInertiaApp + legacy fallback
   - Configured CSRF via Axios defaults
   - Created Pages/Debug/InertiaTest.tsx component
   - Updated base.html with {% block inertia %} and preserved #root

3. **Task 3: Verify Inertia smoke test renders and existing view still works** - (checkpoint:human-verify)
   - User validated all 4 verification tests passed
   - Smoke test renders correctly at /_debug/inertia/
   - Legacy table view at / works identically
   - Django admin at /admin/ loads normally
   - Network tab shows correct Inertia HTML response

**Plan metadata:** (pending - will be committed with STATE.md updates)

## Files Created/Modified

**Created:**
- `sgui/src/Pages/Debug/InertiaTest.tsx` - Smoke test React component displaying Django props
- `scrapegrape/publishers/views.py::inertia_smoke_test()` - Debug view proving Inertia renders React with props

**Modified:**
- `scrapegrape/scrapegrape/settings.py` - Added 'inertia' to INSTALLED_APPS, InertiaMiddleware to MIDDLEWARE (after CsrfViewMiddleware), INERTIA_LAYOUT='base.html'
- `scrapegrape/scrapegrape/urls.py` - Added /_debug/inertia/ route before existing routes
- `scrapegrape/templates/base.html` - Added {% block inertia %} for Inertia injection, preserved <div id="root"> for legacy path
- `sgui/src/main.tsx` - Replaced with createInertiaApp setup (Inertia path) + dynamic App.tsx import (legacy path), CSRF configured via Axios defaults
- `pyproject.toml` - Added inertia-django dependency
- `sgui/package.json` - Added @inertiajs/react and axios dependencies
- `uv.lock` - Updated Python dependency lock
- `sgui/package-lock.json` - Updated npm dependency lock

## Decisions Made

**1. Dual-path entry point architecture**
- **Rationale:** Preserves existing table view at "/" during gradual migration. main.tsx detects Inertia context (presence of #app[data-page]) and routes to createInertiaApp, otherwise dynamically imports legacy App.tsx for #root mounting.
- **Impact:** Enables Phase 1 to validate Inertia without breaking existing functionality. Phase 3 will migrate "/" to Inertia, Phase 5 will remove legacy branch.

**2. Cookie-based CSRF via Axios defaults (not meta tag)**
- **Rationale:** Research (01-RESEARCH.md) identified meta tag approach as anti-pattern for Inertia+Django. Axios already reads csrftoken cookie, just needs correct header name configured.
- **Configuration:** `axios.defaults.xsrfHeaderName = "X-CSRFToken"`, `axios.defaults.xsrfCookieName = "csrftoken"` set at app initialization in main.tsx
- **Impact:** All future Axios POST/PUT/DELETE requests automatically include CSRF token without per-request configuration

**3. InertiaMiddleware position in Django middleware stack**
- **Rationale:** Must run after CsrfViewMiddleware (CSRF token must be validated before Inertia processes request) and before AuthenticationMiddleware (Inertia needs to intercept response before auth redirects)
- **Impact:** Prevents CSRF failures and auth middleware conflicts

**4. Eager page loading for import.meta.glob**
- **Rationale:** Research recommended eager loading over lazy loading — better tree-shaking, build-time error detection, simpler debugging
- **Trade-off:** Slightly larger initial bundle vs lazy loading, but accepted for better DX and build validation

**5. Smoke test lives at /_debug/inertia/ (not /test/ or /inertia/)**
- **Rationale:** Explicit debug namespace avoids production route collisions, clearly temporary
- **Impact:** Phase 5 cleanup will remove /_debug/* routes

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. All installations, configurations, and verifications completed successfully on first attempt.

## User Setup Required

None - no external service configuration required. All changes are code-only (dependencies, middleware, templates).

## Next Phase Readiness

**Ready for Phase 2 (Frontend Consolidation):**
- Inertia infrastructure validated and working
- CSRF configured correctly for future POST requests
- Smoke test proves Django → Inertia → React component prop flow
- Dual-path entry point supports gradual migration

**Validated Assumptions:**
- Django 5.2 compatibility with inertia-django 1.2.0: ✅ Confirmed (manage.py check passes, smoke test renders)
- React 19.1 compatibility with @inertiajs/react 2.3.8: ✅ Confirmed (smoke test component renders correctly)

**No blockers for Phase 2.** Frontend consolidation (sgui/ → scrapegrape/frontend/) can proceed with confidence that Inertia infrastructure works correctly.

## Self-Check

Verifying all claimed artifacts exist:

**Files created:**
- sgui/src/Pages/Debug/InertiaTest.tsx: ✅ FOUND
- scrapegrape/publishers/views.py (contains inertia_smoke_test): ✅ FOUND

**Files modified:**
- scrapegrape/scrapegrape/settings.py (contains InertiaMiddleware): ✅ FOUND
- scrapegrape/scrapegrape/urls.py (contains _debug/inertia): ✅ FOUND
- scrapegrape/templates/base.html (contains block inertia): ✅ FOUND
- sgui/src/main.tsx (contains createInertiaApp): ✅ FOUND
- pyproject.toml (contains inertia-django): ✅ FOUND
- sgui/package.json (contains @inertiajs/react): ✅ FOUND

**Commits:**
- 8b54d0e: ✅ FOUND
- 47af001: ✅ FOUND

## Self-Check: PASSED

All files exist, all commits exist, all claims verified.

---
*Phase: 01-inertia-infrastructure*
*Completed: 2026-02-12*
