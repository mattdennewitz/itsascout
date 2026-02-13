# itsascout

## What This Is

A publisher website analysis tool that ingests publisher URLs, runs a 3-stage AI pipeline (WAF detection, Terms of Service discovery, permissions evaluation), and displays results in an interactive SPA powered by Django-Inertia. Built for assessing scraping feasibility and legal permissions across publisher sites at scale.

## Core Value

Automated analysis of publisher websites to determine scraping permissions and restrictions — WAF detection, ToS discovery, and permission evaluation in a single pipeline.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- Publisher URL ingestion from CSV (bulk import)
- WAF detection via wafw00f integration
- ToS URL discovery via pydantic-ai agent (GPT-4.1-nano)
- ToS permissions evaluation via pydantic-ai agent
- HTML fetching through Zyte proxy API
- Interactive React data table with sorting, filtering, expandable rows
- Django admin with custom actions (WAF scan, discover terms, evaluate, queue analysis)
- Async task pipeline (WAF → discovery → evaluation)
- PostgreSQL data persistence
- ✓ Django-Inertia SPA architecture with cookie-based CSRF — v1.0
- ✓ Consolidated frontend in scrapegrape/frontend/ with Pages/Components/Layouts — v1.0
- ✓ Shared data middleware for auth and flash messages — v1.0
- ✓ Persistent layouts with SPA-like navigation — v1.0
- ✓ Form submissions with useForm and session-based validation — v1.0
- ✓ Deferred props and partial reloads for performance — v1.0
- ✓ Debounced search with preserved table state — v1.0

### Active

<!-- Current scope. Building toward these. -->

(No active requirements — next milestone not yet defined)

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- New analysis types — separate concern from architecture
- UI redesign — current table view serves the use case well
- Tech debt cleanup (hardcoded secrets, etc.) — separate concern
- SSR setup — adds Node.js process complexity, defer until needed
- Mobile app — web-first approach, PWA potential later

## Context

**Current state (post v1.0):**
- Stack: Django 5.2 + React 19.1 + Inertia.js + Vite + TailwindCSS
- Architecture: Django views → inertia_render() → React page components (no DOM JSON parsing)
- Frontend: scrapegrape/frontend/ with 4 page components (Index, Create, Edit, BulkUpload)
- Build: Vite production build (467 kB gzip: 149 kB), dev server with HMR
- All features verified working: table, CRUD forms, bulk upload, admin, SPA navigation

## Constraints

- **Stack**: Django + React + Vite + TailwindCSS + Inertia.js
- **Functionality**: All existing features must work identically
- **Data**: No database schema changes needed

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| django-inertia over other SPA approaches | Keeps Django as source of truth, avoids building separate API layer | ✓ Good — clean integration, no API layer needed |
| Consolidate into scrapegrape/frontend/ | Single project, simpler DX, co-located code | ✓ Good — simplified build and deployment |
| Cookie-based CSRF via Axios defaults | Avoids anti-pattern (meta tag); cleaner integration | ✓ Good — zero CSRF issues across all forms |
| Session-based validation (not InertiaValidationError) | InertiaValidationError doesn't exist in inertia-django 1.2.0 | ✓ Good — reliable pattern using Django sessions |
| Incremental migration (5 phases) | Allows rollback at each boundary, validates early | ✓ Good — zero blockers, zero rollbacks |
| defer() for expensive queries | Instant initial render with loading spinner | ✓ Good — perceived performance improvement |
| Partial reloads with only: ['publishers'] | Only refetch what changed during search | ✓ Good — reduced bandwidth, preserved state |

---
*Last updated: 2026-02-13 after v1.0 milestone*
