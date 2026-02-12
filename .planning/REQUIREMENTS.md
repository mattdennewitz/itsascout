# Requirements: itsascout

**Defined:** 2026-02-12
**Core Value:** Automated analysis of publisher websites to determine scraping permissions and restrictions

## v1.0 Requirements

Requirements for Inertia refactor milestone. Each maps to roadmap phases.

### Inertia Integration

- [ ] **INRT-01**: Django middleware and settings configured for Inertia (InertiaMiddleware, INERTIA_LAYOUT)
- [ ] **INRT-02**: Base template updated with CSRF meta tag and Inertia root div
- [ ] **INRT-03**: Frontend entry point uses `createInertiaApp` with `import.meta.glob` page resolution
- [ ] **INRT-04**: CSRF configured correctly for Axios/Inertia POST requests
- [ ] **INRT-05**: Navigation between pages uses Inertia `<Link>` component (no React Router)
- [ ] **INRT-06**: Shared data available across all pages (flash messages, global context)
- [ ] **INRT-07**: Persistent layouts preserve component state across page navigation
- [ ] **INRT-08**: `useForm` hook used for form submissions with validation error display

### Project Consolidation

- [ ] **CONS-01**: React source moved from sgui/ to scrapegrape/frontend/
- [ ] **CONS-02**: Vite config updated with correct paths for consolidated structure
- [ ] **CONS-03**: django-vite settings updated to serve from new build output location
- [ ] **CONS-04**: Pages/Components/Layouts directory structure established in frontend/

### View Migration

- [ ] **VIEW-01**: Publisher table view converted from template-embedded JSON to `render_inertia()` response
- [ ] **VIEW-02**: Existing DRF serializers reused for Inertia prop serialization
- [ ] **VIEW-03**: Lazy props used for expensive data that isn't immediately needed
- [ ] **VIEW-04**: Partial reloads implemented where applicable

### Cleanup

- [ ] **CLEN-01**: Old template JSON embedding pattern removed (index.html json_script)
- [ ] **CLEN-02**: react-router-dom removed if present
- [ ] **CLEN-03**: Unused sgui/ directory removed after consolidation
- [ ] **CLEN-04**: All existing functionality verified working identically after refactor

## Future Requirements

Deferred to future milestones. Tracked but not in current roadmap.

### Additional Pages

- **PAGE-01**: Dedicated publisher detail page with full analysis history
- **PAGE-02**: Bulk import page with progress tracking
- **PAGE-03**: Dashboard with aggregate statistics

### Advanced Inertia Features

- **ADVN-01**: Server-side rendering (SSR) for SEO/performance
- **ADVN-02**: Prefetching for anticipated navigation
- **ADVN-03**: Deferred props for progressive page loading

## Out of Scope

| Feature | Reason |
|---------|--------|
| New analysis types | This milestone is purely refactoring architecture |
| UI redesign | Keep existing table view, just change how it's served |
| Authentication system | No auth on public view currently, not adding now |
| DRF API endpoints | Inertia replaces need for separate API layer for frontend |
| SSR setup | Adds Node.js process complexity, defer until needed |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INRT-01 | — | Pending |
| INRT-02 | — | Pending |
| INRT-03 | — | Pending |
| INRT-04 | — | Pending |
| INRT-05 | — | Pending |
| INRT-06 | — | Pending |
| INRT-07 | — | Pending |
| INRT-08 | — | Pending |
| CONS-01 | — | Pending |
| CONS-02 | — | Pending |
| CONS-03 | — | Pending |
| CONS-04 | — | Pending |
| VIEW-01 | — | Pending |
| VIEW-02 | — | Pending |
| VIEW-03 | — | Pending |
| VIEW-04 | — | Pending |
| CLEN-01 | — | Pending |
| CLEN-02 | — | Pending |
| CLEN-03 | — | Pending |
| CLEN-04 | — | Pending |

**Coverage:**
- v1.0 requirements: 20 total
- Mapped to phases: 0
- Unmapped: 20 ⚠️

---
*Requirements defined: 2026-02-12*
*Last updated: 2026-02-12 after initial definition*
