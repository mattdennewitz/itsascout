# Roadmap: itsascout v1.0

**Milestone:** v1.0 Inertia Refactor
**Depth:** Standard (research workflow enabled)
**Created:** 2026-02-12

## Overview

Refactor from JSON-in-template rendering to django-inertia while consolidating frontend structure. This is an architecture refactor—existing functionality (WAF detection, ToS discovery/evaluation, bulk CSV import, React data table) remains identical. The roadmap follows an incremental migration pattern: infrastructure setup, frontend consolidation, view conversion, optimization, then cleanup. Each phase delivers verifiable progress while allowing rollback to previous state.

## Phases

### Phase 1: Inertia Infrastructure

**Goal:** Django and frontend configured for Inertia with CSRF and serialization validated.

**Dependencies:** None (foundation phase)

**Plans:** 1 plan

Plans:
- [x] 01-01-PLAN.md -- Install and configure Inertia backend/frontend, validate with smoke test

**Requirements:**
- INRT-01: Django middleware and settings configured for Inertia
- INRT-02: Base template updated with CSRF meta tag and Inertia root div
- INRT-03: Frontend entry point uses createInertiaApp with import.meta.glob
- INRT-04: CSRF configured correctly for Axios/Inertia POST requests

**Success Criteria:**
1. User can load a simple Inertia-rendered test page without CSRF errors
2. POST request from Inertia form successfully processes with CSRF token validation
3. DRF serializers convert to JSON props when passed to render_inertia()
4. Django Debug Toolbar shows Inertia middleware in request/response cycle

**Research Flag:** Standard patterns (official Inertia Django docs cover setup)

---

### Phase 2: Frontend Consolidation

**Goal:** Frontend source moved from sgui/ to scrapegrape/frontend/ with working build pipeline.

**Dependencies:** Phase 1 (Inertia infrastructure must exist before moving frontend files)

**Plans:** 1 plan

Plans:
- [x] 02-01-PLAN.md -- Move sgui/ to scrapegrape/frontend/, update Django/Vite/Docker paths, verify build pipeline

**Requirements:**
- CONS-01: React source moved from sgui/ to scrapegrape/frontend/
- CONS-02: Vite config updated with correct paths for consolidated structure
- CONS-03: django-vite settings updated to serve from new build output location
- CONS-04: Pages/Components/Layouts directory structure established in frontend/

**Success Criteria:**
1. Production build completes and outputs manifest.json to scrapegrape/frontend/dist/
2. Development server starts and HMR updates components without full reload
3. Django admin accessible at /admin/ with correct styling (not intercepted by Inertia routes)
4. Static files served correctly in both development and production modes

**Research Flag:** Standard build tooling (test with checklist)

---

### Phase 3: Core View Migration

**Goal:** Publisher table view converted to Inertia with data flowing directly as props.

**Dependencies:** Phase 2 (consolidated frontend structure required for Pages/ components)

**Plans:** 2 plans

Plans:
- [x] 03-01-PLAN.md -- Convert publisher view to inertia_render() and create Publishers/Index page component
- [x] 03-02-PLAN.md -- Add shared data middleware, persistent AppLayout, and Inertia Link navigation

**Requirements:**
- VIEW-01: Publisher table view converted from template-embedded JSON to render_inertia()
- VIEW-02: Existing DRF serializers reused for Inertia prop serialization
- INRT-05: Navigation between pages uses Inertia Link component
- INRT-06: Shared data available across all pages
- INRT-07: Persistent layouts preserve component state across page navigation

**Success Criteria:**
1. User can load publisher table at / and see all columns with correct data
2. User can sort, filter, and expand table rows without full page reload
3. User navigates between pages using Inertia Link with SPA-like transition (no flash)
4. Flash messages and auth state display via shared data across all page loads

**Research Flag:** Standard Inertia view conversion (patterns in ARCHITECTURE.md)

---

### Phase 4: Interactive Features

**Goal:** Forms and performance optimizations implemented using Inertia patterns.

**Dependencies:** Phase 3 (core view must work before adding interactive features)

**Plans:** 2 plans

Plans:
- [x] 04-01-PLAN.md -- Implement form submissions (create/edit publisher, bulk CSV upload) with useForm and validation errors
- [x] 04-02-PLAN.md -- Add partial reloads for table filtering and deferred props for expensive data

**Requirements:**
- INRT-08: useForm hook used for form submissions with validation error display
- VIEW-03: Lazy props used for expensive data that isn't immediately needed
- VIEW-04: Partial reloads implemented where applicable

**Success Criteria:**
1. User can submit forms (create/edit publisher, bulk CSV import) with progress indicator and validation errors
2. User can filter table data and only publishers array refreshes (not entire page props)
3. Expensive queries (WAF reports, ToS evaluation) load on-demand via lazy props
4. Table pagination preserves scroll position using preserveScroll option

**Research Flag:** May need phase-specific research if CSV bulk upload has unique requirements

---

### Phase 5: Cleanup & Verification

**Goal:** Old template patterns removed and all existing functionality verified working.

**Dependencies:** Phase 4 (all new patterns implemented before removing old code)

**Plans:** 2 plans

Plans:
- [x] 05-01-PLAN.md -- Remove legacy template JSON embedding, dead frontend code, and debug smoke test routes
- [x] 05-02-PLAN.md -- Automated and manual verification of all application features after cleanup

**Requirements:**
- CLEN-01: Old template JSON embedding pattern removed
- CLEN-02: react-router-dom removed if present
- CLEN-03: Unused sgui/ directory removed after consolidation
- CLEN-04: All existing functionality verified working identically after refactor

**Success Criteria:**
1. No templates contain json_script filter or manual JSON parsing code
2. No frontend code imports from react-router-dom
3. sgui/ directory does not exist in repository
4. All features from pre-refactor checklist work identically (WAF scan, ToS discovery/evaluation, bulk import, admin actions, async tasks)

**Research Flag:** No research needed (verification checklist)

---

## Progress

| Phase | Status | Requirements | Completion |
|-------|--------|--------------|------------|
| 1 - Inertia Infrastructure | Complete (2026-02-12) | 4 | 100% |
| 2 - Frontend Consolidation | Complete (2026-02-12) | 4 | 100% |
| 3 - Core View Migration | Complete (2026-02-12) | 5 | 100% |
| 4 - Interactive Features | Complete (2026-02-12) | 3 | 100% |
| 5 - Cleanup & Verification | Complete (2026-02-13) | 4 | 100% |

**Overall:** 20/20 requirements complete (100%)

---

## Critical Path

The phases form a strict dependency chain:

```
Phase 1 (Infrastructure)
    ↓
Phase 2 (Consolidation)
    ↓
Phase 3 (View Migration)
    ↓
Phase 4 (Interactive Features)
    ↓
Phase 5 (Cleanup)
```

Each phase must complete before the next begins. This ordering minimizes risk by:
- Validating configuration early (Phase 1 catches CSRF/serialization issues)
- Separating file movement from logic changes (Phase 2 isolates build path problems)
- Proving approach with most complex view first (Phase 3 success validates pattern)
- Adding optimizations after correctness proven (Phase 4 enables measurement)
- Deferring cleanup until new patterns stable (Phase 5 safe after validation)

**Rollback points:** After each phase, can rollback to previous state if issues found.

---

## Key Risks

| Risk | Phase | Mitigation |
|------|-------|------------|
| CSRF header mismatch breaks all POST requests | 1 | Configure CSRF_HEADER_NAME in settings before smoke test |
| Vite manifest path misalignment causes 404s | 2 | Test production build immediately after consolidation |
| Django admin routes intercepted by Inertia | 2 | Admin routes before Inertia catch-all in urls.py |
| DRF serializers don't auto-convert for Inertia | 1 | Call .data explicitly in smoke test view |
| Expensive queries run during partial reloads | 4 | Wrap queries in lambdas for lazy evaluation |

---

*Roadmap created: 2026-02-12*
*Next: `/gsd:execute-phase 04-interactive-features`*
