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
