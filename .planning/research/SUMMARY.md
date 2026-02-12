# Project Research Summary

**Project:** itsascout - Django + Inertia.js + React Refactor
**Domain:** Web Application Refactoring (Django + React SPA)
**Researched:** 2026-02-12
**Confidence:** MEDIUM

## Executive Summary

This project refactors an existing Django+React application to replace template-rendered JSON parsing with Inertia.js, while consolidating the separate frontend (`sgui/`) into the main Django project (`scrapegrape/frontend/`). The recommended approach treats Inertia as a "views protocol" that eliminates the need for a separate API layer while enabling SPA-like navigation. The stack additions are minimal (one Python package, two npm packages), and existing infrastructure (django-vite, DRF serializers, React components) remains largely intact.

The key recommendation is an incremental migration approach: set up Inertia infrastructure first, convert views one-by-one while keeping the data layer unchanged, then optimize with lazy props and partial reloads. This de-risks the refactor by allowing rollback at any point. The main risk is CSRF configuration mismatch causing all POST requests to fail silently—this must be addressed in Phase 1 before converting any views.

Critical success factors: configure CSRF headers before first Inertia view, keep Django Admin routes isolated from Inertia routing, maintain correct Vite manifest paths during consolidation, and use existing DRF serializers rather than rewriting serialization logic.

## Key Findings

### Recommended Stack

The refactor adds Inertia.js as a bridge between Django 5.2 and React 19, eliminating the current JSON-embedded-in-HTML approach. Stack additions are minimal: `inertia-django` (1.2.0+), `@inertiajs/react` (2.3.8+), and `@inertiajs/core` (auto-installed dependency). Critically, django-vite stays—it works alongside Inertia, not replaced by it.

**Core technologies:**
- **inertia-django (1.2.0+)**: Official Django adapter — only maintained Django-Inertia bridge, handles CSRF/middleware/shared data
- **@inertiajs/react (2.3.8+)**: React adapter for Inertia.js — provides `createInertiaApp`, `Link`, `useForm`, and routing
- **@inertiajs/core (2.3.14+)**: Core Inertia functionality — bundles Axios, handles state management and navigation
- **django-vite (keep)**: Asset bundling and HMR — manages Vite manifest, dev server integration, essential for both current and Inertia setup
- **DRF serializers (keep)**: Data formatting — existing serializers work with Inertia via `.data` attribute

**Version compatibility:** Django 5.2 not explicitly listed in inertia-django docs (shows Django 4.x). React 19.1 not explicitly documented but package actively maintained through Feb 2026. Both likely compatible, needs verification during Phase 1.

**Remove:** `react-router-dom` (if installed) causes routing conflicts. Consider removing DRF if ONLY used for frontend API (assess per-endpoint).

### Expected Features

This is a refactor, not greenfield—existing features (WAF detection, ToS discovery/evaluation, bulk CSV import, React data table, Django admin, async tasks) are already built. Research focuses on what Inertia enables and what the consolidation changes.

**Must have (table stakes):**
- **Direct prop passing** — core Inertia value prop, eliminates DOM JSON parsing
- **SPA-like navigation** — no full page reloads on internal links
- **CSRF handling** — Django CSRF tokens work automatically via Axios
- **Shared data** — global state (auth user, flash messages) available to all pages
- **Form validation errors** — server-side validation passed to frontend
- **Asset versioning** — auto-reload on frontend changes
- **Progress indicators** — visual feedback during navigation
- **Layout persistence** — persistent layouts avoid re-mounting shared UI

**Should have (competitive):**
- **useForm helper** — built-in progress tracking, error handling, file uploads
- **Partial reloads** — refresh subset of data without full page visit
- **Optional props** — expensive props excluded by default, loaded on request
- **preserveState/preserveScroll** — maintain component state and scroll position across navigation
- **Prefetching** — preload page data on hover/focus (30s cache)

**Defer (v2+):**
- **Deferred props** — defer prop loading until after initial render (complex optimization)
- **Grouped deferred props** — fetch multiple deferred props in one request
- **History encryption** — encrypt sensitive data in browser history (requires HTTPS)
- **Custom error pages** — Inertia-rendered 404/500 pages (polish, not essential)

**Anti-features (explicitly avoid):**
- Building a JSON API (defeats Inertia purpose)
- Frontend routing with React Router (conflicts with Inertia)
- Passing Django model instances (must serialize explicitly)
- Manual JSON parsing from DOM (what we're replacing)
- Global state management libs like Redux/Zustand (server is source of truth)

### Architecture Approach

The migration replaces template-rendered JSON with direct prop passing via Inertia middleware. Current flow: Django view → template with `{{ serialized|json_script }}` → React parses DOM. New flow: Django view → `render_inertia()` → Inertia middleware → React props. No intermediate template or DOM parsing—data flows directly.

**Major components:**
1. **Django Views** — query data, call serializers, return `render_inertia(request, 'Component/Name', props)` instead of `render(request, 'template.html', context)`
2. **Inertia Middleware** — handles CSRF, shares global props (auth, flash messages), manages page responses
3. **DRF Serializers** — keep existing serializers, use `.data` attribute to pass JSON-serializable dicts to Inertia props
4. **Inertia App Entry** (`frontend/app.tsx`) — replaces current `main.tsx`, uses `createInertiaApp` with `import.meta.glob` to resolve page components
5. **Page Components** (`frontend/Pages/`) — receive props directly as function parameters, no `useEffect` parsing
6. **Persistent Layouts** (`frontend/Layouts/`) — wrap pages with shared UI (nav, footer) that persists across navigation
7. **Shared Data Middleware** — custom middleware using `inertia.share()` to inject auth user, CSRF token, flash messages into every response

**Key patterns:**
- Use existing DRF serializers by calling `.data` before passing to Inertia
- Wrap expensive queries in lambdas for lazy evaluation during partial reloads
- Apply layouts via `Page.layout = (page) => <Layout children={page} />`
- Use `<Link>` from `@inertiajs/react` for all navigation (not `<a>` tags)
- Configure CSRF to match Axios defaults: `CSRF_HEADER_NAME = 'HTTP_X_XSRF_TOKEN'`

**Project structure change:** Move `sgui/` → `scrapegrape/frontend/`. Vite builds to `scrapegrape/frontend/dist/`, django-vite reads manifest from new location. Update `DJANGO_VITE_ASSETS_PATH` and `STATICFILES_DIRS` in settings.

### Critical Pitfalls

Research identified 14 pitfalls across Critical (6), Moderate (4), and Minor (4) severity. Top pitfalls with prevention strategies:

1. **CSRF Token Header Mismatch** (Critical, Phase 1)
   - Django expects `X-CSRFToken`, Axios sends `X-XSRF-TOKEN` by default
   - All POST/PUT/DELETE fail with 403 Forbidden
   - Fix: `CSRF_HEADER_NAME = 'HTTP_X_XSRF_TOKEN'` in settings OR configure Axios in `app.tsx`
   - Must configure before any Inertia views work

2. **Vite Manifest Path Misalignment** (Critical, Phase 2)
   - After consolidation, django-vite looks in old path, all assets 404
   - Production build shows blank page despite no errors
   - Fix: Update `STATICFILES_DIRS` and `DJANGO_VITE_ASSETS_PATH` to point to `scrapegrape/frontend/dist/`
   - Test build process before deployment

3. **Django Admin Routes Breaking** (Critical, Phase 2)
   - Catch-all Inertia routes override admin routes if placed incorrectly
   - `/admin/` returns React root div or has no CSS
   - Fix: Admin routes MUST come before Inertia catch-all in `urls.py`, consider excluding `/admin/` from Inertia middleware

4. **JSON Serialization Failures with Related Models** (Critical, Phase 1)
   - DRF serializers don't auto-convert for Inertia, related models don't serialize
   - Missing `created_at`, `updated_at`, related objects show `[object Object]`
   - Fix: Call `.data` on DRF serializers explicitly: `render_inertia(request, 'Page', {'publishers': serializer.data})`

5. **Partial Reload Performance Traps** (Moderate, Phase 3)
   - All props execute server-side even during partial reloads unless lazy
   - Expensive queries run unnecessarily, slow response times
   - Fix: Wrap expensive queries in lambdas: `'stats': lambda: calculate_stats()`

## Implications for Roadmap

Based on research, suggested phase structure follows incremental migration pattern: infrastructure → single view conversion → rollout → optimization. This allows rollback at any point and validates approach early.

### Phase 1: Inertia Infrastructure Setup
**Rationale:** Establish foundation without changing functionality. Validates configuration (CSRF, django-vite, serializers) before converting views. Catches Critical Pitfalls #1 and #4 early.

**Delivers:**
- Inertia packages installed (inertia-django, @inertiajs/react)
- Django configured (middleware, settings, CSRF headers)
- Base template updated (from `{% block extra_body %}` to `{% block inertia %}`)
- Inertia app entry point (`frontend/app.tsx` with `createInertiaApp`)
- Smoke test: one simple view converted to validate setup

**Addresses features:**
- Direct prop passing (table stakes)
- CSRF handling (table stakes)
- Asset versioning (table stakes)

**Avoids pitfalls:**
- Pitfall #1: CSRF header mismatch (configure in this phase)
- Pitfall #4: DRF serializer compatibility (test with smoke test view)
- Pitfall #2: Axios version conflicts (check `npm ls axios`)

**Research flag:** Standard patterns, skip phase-specific research. Follow official Inertia Django docs.

### Phase 2: Frontend Consolidation
**Rationale:** Move `sgui/` → `scrapegrape/frontend/` before converting remaining views. Isolates path/build changes from view logic changes. Critical for catching Pitfalls #3 and #5.

**Delivers:**
- Frontend directory moved to `scrapegrape/frontend/`
- Vite config updated (output paths, manifest location)
- Django settings updated (STATICFILES_DIRS, DJANGO_VITE_ASSETS_PATH)
- TypeScript path aliases fixed (`@/` imports)
- Production build tested (manifest.json accessible)
- Dev server HMR verified
- Docker volumes updated

**Uses:**
- django-vite (kept from STACK.md)
- Vite configuration patterns (from ARCHITECTURE.md)

**Avoids pitfalls:**
- Pitfall #5: Vite manifest path misalignment (test build immediately)
- Pitfall #3: Django admin routes breaking (test `/admin/` after URL changes)
- Pitfall #11: TypeScript path aliases (verify `@/` imports resolve)
- Pitfall #14: Docker volume mounts (update docker-compose.yml)

**Research flag:** Standard build tooling, skip research. Test checklist: build succeeds, collectstatic works, HMR functions, admin loads.

### Phase 3: View Migration (Publishers Table)
**Rationale:** Convert primary view (publishers table) to validate full data flow. This is the heaviest view (optimized queries with select_related/prefetch, complex serialization), so success here proves approach works.

**Delivers:**
- `publishers/views.py` table view converted to `render_inertia()`
- `frontend/Pages/Publishers/Index.tsx` created
- DataTable component receives props directly (no DOM parsing)
- Shared data middleware (auth user, flash messages)
- App layout (`frontend/Layouts/AppLayout.tsx`)
- Old template (`templates/index.html`) removed
- Old React entry (`sgui/src/main.tsx`, `App.tsx`) removed

**Addresses features:**
- SPA-like navigation (table stakes)
- Shared data (table stakes)
- Layout persistence (table stakes)
- Progress indicators (table stakes)

**Implements architecture:**
- Django Views → Inertia Middleware → Page Components flow
- DRF Serializers → `.data` → Inertia props pattern
- Persistent layouts pattern

**Avoids pitfalls:**
- Pitfall #12: Remove `json_script` template filter
- Pitfall #8: Shared data middleware ordering (after auth, before Inertia)
- Pitfall #13: Root element ID mismatch (verify `<div id="app">`)

**Research flag:** Skip research—standard Inertia view conversion, patterns documented in ARCHITECTURE.md.

### Phase 4: Forms and Validation
**Rationale:** Add interactive features (create/edit publishers, bulk CSV import) using Inertia form patterns. Validates form validation errors and CSRF protection work correctly.

**Delivers:**
- Form views converted to `render_inertia()` with `InertiaValidationError` on failure
- Form components using `useForm` hook (built-in error handling, progress tracking)
- File upload progress for CSV bulk import
- Flash messages displayed via shared data

**Addresses features:**
- Form validation errors (table stakes)
- useForm helper (should have)
- File upload progress (should have)

**Avoids pitfalls:**
- Pitfall #1: CSRF already configured in Phase 1, but validate POST requests work

**Research flag:** Standard Inertia forms, follow official docs. May need phase-specific research if CSV bulk upload has unique requirements.

### Phase 5: Performance Optimization
**Rationale:** Add lazy props, partial reloads, and prefetching after core functionality works. These are optimizations that don't affect correctness.

**Delivers:**
- Lazy props for expensive queries (WAF reports, ToS discovery/evaluation)
- Partial reloads for table filtering (only refetch publishers, not related data)
- Prefetching on table row hover
- preserveScroll for table pagination

**Addresses features:**
- Partial reloads (should have)
- Optional props (should have)
- Prefetching (should have)
- preserveScroll (should have)

**Avoids pitfalls:**
- Pitfall #7: Partial reload performance traps (wrap expensive queries in lambdas)

**Research flag:** Standard Inertia optimizations, patterns in ARCHITECTURE.md. Monitor with Django Debug Toolbar to validate query counts.

### Phase 6: Production Hardening
**Rationale:** Address deployment-specific concerns before production release. Validates asset versioning, caching, and rollback procedures.

**Delivers:**
- Asset version function using manifest hash
- Static file cache headers configured
- Production build test in staging environment
- Rollback plan documented and tested

**Avoids pitfalls:**
- Pitfall #10: Asset version mismatch reload loop (use manifest hash, not timestamp)
- Pitfall #5: Vite manifest path (final verification)

**Research flag:** May need phase-specific research for deployment infrastructure (Docker, nginx, CDN) if not already documented.

### Phase Ordering Rationale

- **Infrastructure first (Phase 1):** Validates CSRF, serialization, django-vite integration before any view changes. De-risks by catching config issues early.
- **Consolidation before migration (Phase 2):** Separates file movement from logic changes. Isolates build path issues from Inertia routing issues.
- **Single view migration (Phase 3):** Proves approach with most complex view (publishers table). Success here means remaining views are straightforward.
- **Forms next (Phase 4):** Adds interactivity after read-only table works. Validates bidirectional data flow.
- **Optimization deferred (Phase 5):** Performance improvements after correctness proven. Enables measurement of actual benefit.
- **Production last (Phase 6):** Deployment concerns addressed after functionality complete.

This ordering minimizes risk by allowing rollback at each phase boundary. If Phase 3 fails, rollback to Phase 2 with frontend consolidated but views unchanged. If Phase 1 fails, rollback to pre-Inertia state.

### Research Flags

**Phases with standard patterns (skip phase-specific research):**
- **Phase 1 (Infrastructure):** Official Inertia Django docs cover setup completely
- **Phase 2 (Consolidation):** Standard build tooling, test with checklist
- **Phase 3 (View Migration):** Patterns documented in ARCHITECTURE.md
- **Phase 5 (Optimization):** Standard Inertia patterns, monitor with Django Debug Toolbar

**Phases that MAY need phase-specific research:**
- **Phase 4 (Forms):** If CSV bulk upload has unique requirements (large files, progress tracking, error handling), may need research on Inertia file upload best practices. Start with official docs, escalate if needed.
- **Phase 6 (Production):** If deployment infrastructure (Docker, nginx, CDN) not already documented, may need research on django-vite + WhiteNoise + static file caching. Start with official docs.

**Gaps requiring validation during implementation:**
- Django 5.2 compatibility with inertia-django (shows Django 4.x in docs)
- React 19.1 compatibility with @inertiajs/react (no explicit docs)
- django-tasks integration with Inertia views (not researched)
- WhiteNoise cache-control configuration for Vite-generated hashes

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM | Core packages (inertia-django, @inertiajs/react) are official and well-documented (HIGH). Version compatibility (Django 5.2, React 19) not explicitly documented but packages actively maintained (MEDIUM). django-vite integration confirmed working pattern (HIGH). |
| Features | MEDIUM | Table stakes features documented in official Inertia docs (HIGH). Django-specific implementation details (form validation, shared data) have community examples but not official Django-Inertia guide (MEDIUM). Advanced features (deferred props, history encryption) documented but not validated in Django context (LOW). |
| Architecture | HIGH | Inertia's architecture well-documented with multiple Django examples. DRF serializer compatibility confirmed via `.data` attribute. Data flow patterns proven in community projects (django-vite-inertia template, multiple tutorials). Migration strategy incremental and reversible. |
| Pitfalls | MEDIUM | CSRF header mismatch, Axios version conflicts, serialization failures documented in GitHub issues (HIGH). Vite manifest path misalignment and admin route breaking extrapolated from best practices (MEDIUM). SSR considerations and monorepo deployment coordination not validated (LOW—not needed for MVP). |

**Overall confidence:** MEDIUM

Research is sufficient to start Phase 1 with low risk. Confidence gaps (Django 5.2/React 19 compatibility) can be validated during Phase 1 smoke test. Critical pitfalls have clear prevention strategies. Architecture patterns proven in multiple community projects.

**Recommendation:** Proceed to requirements definition and roadmap creation. Use suggested phase structure as starting point. Flag Phase 4 and Phase 6 for optional phase-specific research if complexity emerges during planning.

### Gaps to Address

**During Phase 1 (Infrastructure Setup):**
- Validate Django 5.2 compatibility with inertia-django 1.2.0 (test in smoke test view)
- Validate React 19.1 compatibility with @inertiajs/react 2.3.8 (test in smoke test view)
- Confirm Axios version after install (`npm ls axios`), resolve conflicts if found

**During Phase 4 (Forms):**
- Research Inertia file upload best practices if CSV bulk upload needs special handling
- Validate `InertiaValidationError` with Django form errors (may differ from Laravel examples)

**During Phase 6 (Production):**
- Research WhiteNoise cache-control configuration for Vite-generated hashed filenames
- Validate deployment coordination (build frontend before deploying backend)
- Document rollback procedure

**Not blocking (defer to later):**
- SSR setup (only if performance requires server-side rendering)
- WebSocket/real-time updates (only if task status updates needed)
- Large dataset pagination patterns with Inertia (only if current table pagination insufficient)

## Sources

### Primary (HIGH confidence)

**Official Documentation:**
- [Inertia.js Documentation](https://inertiajs.com/) — core concepts, routing, forms, partial reloads
- [Inertia Django Official Docs](https://inertiajs.github.io/inertia-django/guide/) — server-side setup, middleware, shared data
- [inertia-django GitHub](https://github.com/inertiajs/inertia-django) — official Python adapter, InertiaMeta patterns
- [inertia-django PyPI](https://pypi.org/project/inertia-django/) — version info, dependencies
- [@inertiajs/react npm](https://www.npmjs.com/package/@inertiajs/react) — React adapter, version history
- [Django REST Framework Serializers](https://www.django-rest-framework.org/api-guide/serializers/) — serializer `.data` attribute

**Official Inertia.js Feature Docs:**
- [CSRF Protection](https://inertiajs.com/docs/v2/security/csrf-protection)
- [Client-Side Setup](https://inertiajs.com/docs/v2/installation/client-side-setup)
- [Forms](https://inertiajs.com/docs/v2/the-basics/forms)
- [File Uploads](https://inertiajs.com/docs/v2/the-basics/file-uploads)
- [Partial Reloads](https://inertiajs.com/docs/v2/data-props/partial-reloads)
- [Deferred Props](https://inertiajs.com/docs/v2/data-props/deferred-props)
- [Asset Versioning](https://inertiajs.com/docs/v2/advanced/asset-versioning)
- [Error Handling](https://inertiajs.com/docs/v2/advanced/error-handling)
- [Server-Side Rendering](https://inertiajs.com/docs/v2/advanced/server-side-rendering)

### Secondary (MEDIUM confidence)

**Tutorials and Community Examples:**
- [Building a Modern Web App with Django, Inertia.js, Vite, and React](https://medium.com/@tanzid3/building-a-modern-web-app-with-django-inertia-js-vite-and-react-67979a981649) — complete setup walkthrough
- [How to setup Django with React using InertiaJS](https://anjanesh.dev/how-to-setup-django-with-react-using-inertiajs) — configuration examples
- [django-vite-inertia Template](https://github.com/SarthakJariwala/django-vite-inertia) — working example repository
- [django-inertia-vite (React + TypeScript)](https://github.com/JiaWeiXie/django-inertia-vite) — TypeScript patterns
- [django-vite PyPI](https://pypi.org/project/django-vite/) — django-vite documentation
- [django-vite GitHub](https://github.com/MrBin99/django-vite) — HMR configuration

**GitHub Issues (Pitfall Research):**
- [inertia-django Issue #8](https://github.com/inertiajs/inertia-django/issues/8) — CSRF configuration
- [inertia-django Issue #14](https://github.com/inertiajs/inertia-django/issues/14) — Axios version conflicts
- [inertia-django Issue #18](https://github.com/inertiajs/inertia-django/issues/18) — related model serialization
- [inertia-django Issue #30](https://github.com/inertiajs/inertia-django/issues/30) — validation error bags
- [django-vite Issue #161](https://github.com/MrBin99/django-vite/issues/161) — manifest path issues

**Deployment Resources:**
- [Monorepos with Django and React](https://www.vintasoftware.com/blog/django-react-monorepo) — deployment coordination
- [Using Vite with Django Gist](https://gist.github.com/lucianoratamero/7fc9737d24229ea9219f0987272896a2) — static file configuration

### Tertiary (LOW confidence, needs validation)

- Admin route configuration patterns — extrapolated from Django URL routing best practices, not Inertia-specific
- Template hydration errors — based on React hydration patterns, not validated for Django+Inertia
- Docker volume mount issues — standard Docker practices, not Inertia-specific
- SSR deployment patterns — documented in official Inertia docs but not validated in production Django setup

---
*Research completed: 2026-02-12*
*Ready for roadmap: yes*
