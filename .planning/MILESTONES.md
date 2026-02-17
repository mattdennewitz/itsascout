# Project Milestones: itsascout

## v1.0 Inertia Refactor (Shipped: 2026-02-13)

**Delivered:** Complete architecture refactor from JSON-in-template rendering to django-inertia with SPA-like navigation, form handling, and consolidated project structure.

**Phases completed:** 1-5 (8 plans total)

**Key accomplishments:**
- Django-Inertia integration with cookie-based CSRF, shared data middleware, and persistent layouts
- Frontend consolidated from sgui/ to scrapegrape/frontend/ with Pages/Components/Layouts structure
- Publisher table view converted to Inertia props with deferred loading and partial reloads
- Form submissions (create/edit/bulk upload) using useForm with session-based validation
- Debounced search with partial reloads preserving table state and scroll position
- Full cleanup of legacy patterns and verified all features working identically

**Stats:**
- 65 files created/modified
- 13,775 lines added
- 5 phases, 8 plans, ~18 tasks
- 2 days from start to ship

**Git range:** `feat(01-01)` → `feat(05-01)`

**What's next:** Project complete for current scope. Future milestones may add dedicated detail pages, SSR, or prefetching.

---

*No prior milestones — existing codebase predates milestone tracking.*

## v2.0 Core Workflow (Shipped: 2026-02-17)

**Delivered:** End-to-end URL analysis workflow — paste a URL, watch real-time SSE progress as 10+ pipeline steps execute, get a comprehensive report card with publisher-level and article-level findings.

**Phases completed:** 6-11 (13 plans, 50 commits)

**Key accomplishments:**
- End-to-end URL analysis pipeline with sequential step execution and publisher intelligence caching
- Real-time SSE progress updates via Daphne ASGI with EventSource-driven frontend
- Fetch strategy manager (curl-cffi with Zyte fallback, remembered per publisher)
- Publisher discovery: robots.txt parsing, sitemap probing, RSS feed discovery, RSL detection
- Article metadata extraction via extruct (JSON-LD, OpenGraph, Microdata), paywall detection, LLM metadata profiling
- Report card UI with field-presence comparison table (11 fields × 4 formats)
- TDD throughout: every pipeline step built test-first, full integration test proves the chain

**Stats:**
- 50 commits
- 7,646 LOC Python + 2,950 LOC TypeScript
- 6 phases, 13 plans
- 4 days from start to ship (2026-02-14 → 2026-02-17)

**Git range:** `feat(06-01)` → `feat(11-03)`

**What's next:** Authentication, grade computation, batch analysis.

---

