# Phase 1: Inertia Infrastructure - Context

**Gathered:** 2026-02-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Configure Django and the frontend for Inertia.js — middleware, CSRF, base template, frontend entry point — validated with a smoke test page. This is pure infrastructure setup. No existing views are changed; the current app continues working as-is.

</domain>

<decisions>
## Implementation Decisions

### Smoke test page
- Minimal render only — just prove Inertia loads a React component with props from Django
- No form POST or serializer validation on the test page (those are validated separately)
- Lives at `/_debug/inertia/` under a debug namespace
- No auth required — it's a dev tool on localhost
- Temporary scaffolding — remove in Phase 5 cleanup

### Route coexistence
- Explicit routes only — each Inertia view gets its own URL pattern, no catch-all
- Routes go in the main `urls.py` alongside existing ones
- Root route `/` stays untouched as the existing template view throughout Phase 1
- Unmatched URLs fall through to Django's normal 404

### Dev workflow
- Docker compose already handles Django + Vite — no changes needed to docker-compose.yml
- Errors display via Django's default debug error page; React errors in browser console
- Use whatever package manager the project already uses for frontend dependencies

### Claude's Discretion
- Exact middleware ordering in settings
- CSRF configuration details (meta tag format, Axios interceptor setup)
- createInertiaApp configuration and page resolution pattern
- Base template structure for Inertia root div placement

</decisions>

<specifics>
## Specific Ideas

- Debug namespace `/_debug/` suggests room for future debug tools at that prefix
- Smoke test should be clearly identifiable as temporary/scaffolding

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-inertia-infrastructure*
*Context gathered: 2026-02-12*
