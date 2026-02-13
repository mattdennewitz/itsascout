# Project State: itsascout

**Last Updated:** 2026-02-13
**Milestone:** v2.0 Core Workflow
**Status:** Defining requirements

---

## Project Reference

**Core Value:** Paste a URL, get a comprehensive scraping report card — what's allowed, what's blocked, and what structured data is available — with real-time progress as each check completes.

**Current Focus:** Build the end-to-end URL analysis workflow with streaming progress, durable publisher intelligence, and a report card UI.

**Key Constraints:**
- Stack: Django + React + Vite + TailwindCSS + Inertia.js (established in v1.0)
- Async: RQ for task execution, needs Docker setup
- Fetching: curl-cffi preferred, Zyte as fallback
- Backwards compatibility: Existing publisher table and admin must continue working

---

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-02-13 — Milestone v2.0 started

---

## Performance Metrics

### Velocity

- **Requirements completed:** 0
- **Estimated remaining:** TBD (requirements not yet defined)

### Quality

- **Blockers encountered:** 0
- **Plans revised:** 0
- **Rollbacks performed:** 0

### Milestone

- **Started:** 2026-02-13
- **Phases completed:** 0

---

## Accumulated Context

### Key Decisions (from v1.0)

| Date | Decision | Rationale | Impact |
|------|----------|-----------|--------|
| 2026-02-12 | Use django-inertia for refactor | Keeps Django as source of truth, avoids building separate API layer | Foundation for all phases |
| 2026-02-12 | Consolidate sgui/ into scrapegrape/frontend/ | Single project, simpler DX, co-located code | Established frontend structure |
| 2026-02-12 | Cookie-based CSRF via Axios defaults | Avoids anti-pattern; cleaner integration | All POST requests auto-include CSRF |
| 2026-02-12 | Session-based validation pattern | InertiaValidationError doesn't exist in inertia-django 1.2.0 | Reliable form validation pattern |
| 2026-02-12 | defer() + partial reloads pattern | Instant initial render, only refetch what changed | Established performance patterns |

### Research Notes (from v1.0)

- Stack validated: inertia-django 1.2.0+, @inertiajs/react 2.3.8+
- Architecture: Django views → render_inertia() → Inertia middleware → React props
- DRF serializers compatible via .data attribute

### Active Todos

- [ ] Complete research (if selected)
- [ ] Define v2.0 requirements with REQ-IDs
- [ ] Create v2.0 roadmap

### Known Blockers

None currently.

---

## Session Continuity

### What Just Happened

Started milestone v2.0 Core Workflow. Updated PROJECT.md with new vision: single-URL entry → streaming pipeline → report card. Publisher data is durable, job data is URL-specific. Existing table stays as admin view.

### What's Next

Research (if selected) → define requirements → create roadmap.

### Context for Next Session

**v2.0 Vision:** User pastes a URL, gets real-time SSE progress as pipeline runs (WAF → publisher resolution → ToS → robots.txt → sitemap → RSS → RSL → metadata profiling → article extraction). Results shown as streaming report card at unique URL. Publisher intelligence accumulates over time.

---

### Last Session

- **Date:** 2026-02-13
- **Stopped at:** Milestone v2.0 started, moving to research/requirements
- **Next action:** Research decision → requirements → roadmap

---

*State initialized: 2026-02-12*
*Last updated: 2026-02-13*
*Milestone: v2.0 Core Workflow (started)*
