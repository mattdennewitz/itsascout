# Phase 3: Core View Migration - Research

**Researched:** 2026-02-12
**Domain:** Django template view to Inertia.js conversion with DRF serializer reuse
**Confidence:** HIGH

## Summary

Phase 3 converts the existing publisher table view from a Django template with JSON-embedded data to a native Inertia.js response that passes data directly as props. The current implementation uses `django.shortcuts.render()` with a serialized JSON payload embedded in a `<script>` tag, which React parses on mount. The Inertia approach eliminates this indirection: Django views use `inertia.render()` to return props directly, and React components receive them as typed props.

The project has Inertia infrastructure already in place from Phase 1 (middleware, CSRF config, dual-path entry point) and consolidated frontend structure from Phase 2 (scrapegrape/frontend/ with Pages/ directory). The existing view in `publishers/views.py` already performs optimized queries using Subquery annotations and bulk fetching to avoid N+1 queries, and existing DRF serializers in `publishers/serializers.py` are designed for exactly this prop serialization use case.

The migration preserves all existing functionality: TanStack Table with sorting, filtering, and expandable rows; the DataTable component and column definitions remain unchanged. Only the data flow mechanism changes: from JSON parsing in React to direct prop passing via Inertia. Shared data enables flash messages and auth state across all pages, persistent layouts preserve component state during navigation, and Link components provide SPA-like transitions.

**Primary recommendation:** Replace `render(request, "index.html", {...})` with `inertia.render(request, 'Publishers/Index', props={...})`, create `Publishers/Index.tsx` page component that wraps the existing DataTable, verify the dual-path entry point in main.tsx correctly detects Inertia context, and test navigation using Link components for future multi-page support.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| inertia-django | 1.2.0 | Django server adapter | Official adapter, already installed and configured in Phase 1 |
| @inertiajs/react | 2.3.14 | React client adapter | Official adapter with Link, useForm, router hooks, already installed |
| djangorestframework | 3.16.0 (existing) | Serializer infrastructure | Already in use for PublisherWithReportsSerializer, perfect for Inertia props |
| @tanstack/react-table | 8.21.3 (existing) | Interactive table component | Already powering DataTable, no changes needed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| axios | 1.13.5 (existing) | HTTP client | Already configured with Django CSRF, handles Inertia navigation requests |
| React | 19.1.0 (existing) | UI framework | All Inertia page components are React components |
| Tailwind CSS | 4.1.11 (existing) | Styling | Already styling DataTable, continues unchanged |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| DRF serializers for props | InertiaJsonEncoder with InertiaMeta | DRF gives more control, existing serializers already written, InertiaMeta would require rewriting |
| Inertia Link for navigation | Manual router.visit() | Link component handles preserve-scroll, active states, method props automatically |
| Shared data middleware | Manual prop passing | Shared data avoids prop repetition, scales better as app grows |

**Installation:**
```bash
# Already installed in Phase 1
# No additional dependencies needed
```

## Architecture Patterns

### Recommended Project Structure
```
scrapegrape/
├── publishers/
│   ├── views.py                     # MODIFY: Replace render() with inertia.render()
│   ├── serializers.py               # REUSE: Existing DRF serializers for props
│   └── models.py                    # UNCHANGED
├── scrapegrape/
│   ├── settings.py                  # OPTIONAL: Add shared data middleware
│   └── urls.py                      # UNCHANGED: "/" route already exists
└── frontend/
    └── src/
        ├── Pages/
        │   └── Publishers/
        │       └── Index.tsx        # NEW: Wraps existing DataTable
        ├── Components/              # FUTURE: Shared components
        ├── Layouts/                 # FUTURE: Page layouts
        ├── datatable/
        │   ├── table.tsx            # UNCHANGED: Existing DataTable
        │   └── columns.tsx          # UNCHANGED: Column definitions
        └── main.tsx                 # UNCHANGED: Dual-path already configured
```

### Pattern 1: Converting Django View from Template to Inertia

**What:** Replace `django.shortcuts.render()` with `inertia.render()` to pass props directly instead of embedding JSON
**When to use:** Migrating any Django template view to Inertia
**Example:**
```python
# Source: Phase 1 research + official Inertia Django docs
# https://github.com/inertiajs/inertia-django/blob/main/README.md

# BEFORE (current publishers/views.py)
from django.shortcuts import render
from publishers.serializers import PublisherWithReportsSerializer

def table(request):
    # ... existing Subquery logic, bulk fetching ...
    serialized = PublisherWithReportsSerializer(result, many=True)
    return render(request, "index.html", {"serialized": serialized.data})

# AFTER (Phase 3 target)
from inertia import render as inertia_render
from publishers.serializers import PublisherWithReportsSerializer

def table(request):
    # ... existing Subquery logic, bulk fetching UNCHANGED ...
    serialized = PublisherWithReportsSerializer(result, many=True)
    return inertia_render(request, 'Publishers/Index', props={
        'publishers': serialized.data
    })
```

**Key changes:**
- Import `inertia.render` (aliased to avoid conflict with django.shortcuts.render)
- Change template path to Inertia component name: "Publishers/Index" (maps to Pages/Publishers/Index.tsx)
- Rename context key "serialized" to "publishers" for clarity (component receives props.publishers)
- Remove index.html template dependency

### Pattern 2: Creating Inertia Page Component

**What:** Page component that receives props from Django and renders existing React components
**When to use:** Every Inertia view needs a corresponding page component in Pages/ directory
**Example:**
```typescript
// Source: Existing App.tsx pattern + Inertia page component pattern
// scrapegrape/frontend/src/Pages/Publishers/Index.tsx

import { DataTable } from '@/datatable/table'
import { columns, type Publisher } from '@/datatable/columns'

interface Props {
    publishers: Publisher[]
}

export default function Index({ publishers }: Props) {
    return (
        <div className="container mx-auto py-10">
            <h1 className="text-2xl mb-4">Publishers</h1>
            <DataTable columns={columns} data={publishers} />
        </div>
    )
}
```

**Key points:**
- TypeScript interface defines expected props from Django
- Default export required for Inertia page resolution
- Reuses existing DataTable and columns without changes
- No useEffect or JSON parsing needed — props arrive directly

### Pattern 3: Shared Data Middleware for Flash Messages and Auth

**What:** Middleware that injects common props (user, messages) into every Inertia response
**When to use:** Data needed across all pages (authentication state, flash messages, app config)
**Example:**
```python
# Source: https://github.com/inertiajs/inertia-django/blob/main/README.md
# scrapegrape/scrapegrape/middleware.py (NEW FILE)

from inertia import share

def inertia_share(get_response):
    def middleware(request):
        # Shared data available to all Inertia page components
        share(request,
            user=lambda: {
                'id': request.user.id,
                'name': request.user.username,
                'is_authenticated': request.user.is_authenticated,
            } if request.user.is_authenticated else None,
            flash=lambda: {
                'success': request.session.pop('success', None),
                'error': request.session.pop('error', None),
                'info': request.session.pop('info', None),
            },
        )
        return get_response(request)
    return middleware
```

**Configuration in settings.py:**
```python
MIDDLEWARE = [
    # ... existing middleware ...
    'django.contrib.messages.middleware.MessageMiddleware',
    'scrapegrape.middleware.inertia_share',  # ADD: After messages middleware
    # ...
]
```

**Key points:**
- Lambda functions enable lazy evaluation (only computed when needed)
- Flash messages auto-clear from session (pop vs get)
- All page components receive these props automatically
- No need to pass user/messages in every view

### Pattern 4: Persistent Layouts for Shared UI

**What:** Layout component that wraps pages and persists across navigation
**When to use:** Shared navigation, headers, or stateful UI that shouldn't remount
**Example:**
```typescript
// Source: https://inertiajs.com/docs/v2/the-basics/pages
// scrapegrape/frontend/src/Layouts/AppLayout.tsx (FUTURE)

import { Link } from '@inertiajs/react'
import { ReactNode } from 'react'

interface Props {
    children: ReactNode
}

export default function AppLayout({ children }: Props) {
    return (
        <div className="min-h-screen bg-gray-50">
            <nav className="bg-white shadow">
                <div className="container mx-auto px-4 py-3">
                    <Link href="/" className="text-lg font-bold">
                        Scrapegrape
                    </Link>
                </div>
            </nav>
            <main>
                {children}
            </main>
        </div>
    )
}
```

**Assigning layout to page:**
```typescript
// scrapegrape/frontend/src/Pages/Publishers/Index.tsx
import AppLayout from '@/Layouts/AppLayout'

function Index({ publishers }: Props) {
    return (
        <div className="container mx-auto py-10">
            <h1 className="text-2xl mb-4">Publishers</h1>
            <DataTable columns={columns} data={publishers} />
        </div>
    )
}

// Persistent layout: component instance preserved across navigation
Index.layout = (page: ReactNode) => <AppLayout>{page}</AppLayout>

export default Index
```

**Key points:**
- Layout persists across page navigations (no remount)
- Useful for audio players, scroll position preservation, stateful sidebars
- Can nest multiple layouts for complex hierarchies
- Optional: pages without .layout property render directly

### Pattern 5: Navigation with Link Component

**What:** Link component for SPA-like navigation without full page reload
**When to use:** All internal navigation links
**Example:**
```typescript
// Source: https://inertiajs.com/docs/v2/the-basics/links
import { Link } from '@inertiajs/react'

// Basic navigation
<Link href="/publishers">Publishers</Link>

// Active state detection
const isActive = (href: string) => {
    return window.location.pathname.startsWith(href)
}

<Link
    href="/publishers"
    className={isActive('/publishers') ? 'text-blue-600 font-bold' : 'text-gray-600'}
>
    Publishers
</Link>

// Preserve scroll position on navigation
<Link href="/publishers/create" preserveScroll>
    Create Publisher
</Link>

// POST request (for logout, delete actions)
<Link href="/logout" method="post" as="button">
    Logout
</Link>
```

**Key points:**
- Intercepts clicks, makes XHR request, updates page without reload
- Preserves scroll position with preserveScroll prop
- Supports GET, POST, PUT, PATCH, DELETE via method prop
- Can render as button with as="button"

### Anti-Patterns to Avoid

- **Don't remove the dual-path entry point in main.tsx:** Phase 3 only migrates "/", smoke test at "/_debug/inertia/" must still work, legacy detection needed until Phase 5 cleanup
- **Don't manually parse JSON in page components:** If you find yourself doing `JSON.parse()` or reading from script tags in an Inertia page, the view isn't properly converted
- **Don't serialize entire QuerySets without field specification:** Pass serialized data from DRF serializers, not raw QuerySets (prevents exposing sensitive fields, controls payload size)
- **Don't break existing Subquery optimizations:** The current view's N+1 prevention is critical, preserve the Subquery annotations and in_bulk() patterns
- **Don't add layouts prematurely:** Start with unstyled pages, add layouts when multiple pages exist and shared UI emerges (Phase 4+)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Active link detection | Custom route matching logic | Link component + page.url comparison | Official pattern, handles edge cases like query params, trailing slashes |
| Flash message display | Custom session/cookie reading | Shared data middleware + toast component | Centralized, auto-clears from session, available to all pages |
| Form submission with validation errors | Manual Axios POST + error mapping | Inertia's useForm hook (Phase 4) | Auto-maps server errors to fields, handles submit state, prevents double-submit |
| Page transitions / loading indicators | Custom loading state management | Inertia progress indicators (Phase 4) | Built-in NProgress integration, triggers on navigation automatically |

**Key insight:** Inertia provides integration points that handle subtle edge cases (CSRF refresh, history state, scroll restoration). Custom implementations often miss these, creating bugs that only appear in production or specific navigation flows.

## Common Pitfalls

### Pitfall 1: Template Coexistence Breaking Dual-Path Detection

**What goes wrong:** After converting "/" to Inertia, navigating directly to "/" shows blank page or throws "page component not found" error

**Why it happens:** The dual-path entry point in main.tsx checks for `data-page` attribute to detect Inertia context. If base.html still has `<div id="root">` below `{% block inertia %}`, React tries to mount legacy App on root instead of Inertia app on #app element.

**How to avoid:**
```html
<!-- BEFORE (current base.html) -->
<body>
    {% block inertia %}{% endblock %}
    <div id="root"></div>  <!-- PROBLEM: Triggers legacy path -->
    {% block extra_body %}{% endblock %}
</body>

<!-- AFTER (Phase 3 migration) -->
<body>
    {% block inertia %}{% endblock %}
    <!-- <div id="root"></div> removed — Inertia creates #app -->
    {% block extra_body %}{% endblock %}
</body>
```

**Warning signs:**
- Blank page when loading "/"
- Console error: "Page not found: Publishers/Index"
- React DevTools shows App component instead of Inertia page component
- Network tab shows correct Inertia JSON response but page doesn't render

### Pitfall 2: Stale Data on Navigation Without Reloads

**What goes wrong:** User navigates from Publishers page to another page and back, sees old data even though database changed

**Why it happens:** React component state persists across navigations if layout is persistent. If DataTable maintains sorting/filtering state, stale publishers array remains in props.

**How to avoid:**
```typescript
// Publishers/Index.tsx

import { router } from '@inertiajs/react'
import { useEffect } from 'react'

export default function Index({ publishers }: Props) {
    // Force reload on manual refresh gesture
    useEffect(() => {
        const handleReload = () => router.reload()
        window.addEventListener('publishers:reload', handleReload)
        return () => window.removeEventListener('publishers:reload', handleReload)
    }, [])

    return <DataTable columns={columns} data={publishers} />
}
```

**Better approach (Phase 4):** Use router.reload({ only: ['publishers'] }) to refresh specific props without full page reload

**Warning signs:**
- User reports "data not updating" when navigating back to page
- Database changes don't reflect in table until hard refresh
- Stale counts or missing new records

### Pitfall 3: Serializer Performance Degradation with Related Objects

**What goes wrong:** Page load becomes slow (2-5 seconds) after converting to Inertia, even though template version was fast

**Why it happens:** Existing view uses Subquery and in_bulk() to avoid N+1 queries. If serializer changes or props include un-optimized relationships, database queries explode.

**How to avoid:**
```python
# publishers/views.py — PRESERVE existing optimization pattern

def table(request):
    # CRITICAL: Keep Subquery annotations
    latest_waf = Subquery(WAFReport.objects.filter(...).values("id")[:1])
    publishers = Publisher.objects.annotate(latest_waf_id=latest_waf, ...)

    # CRITICAL: Keep bulk fetching
    waf_reports = WAFReport.objects.in_bulk(publishers.values_list("latest_waf_id", flat=True))

    # CRITICAL: Construct result dict manually, don't just serialize QuerySet
    result = [
        {
            "publisher": publisher,
            "waf_report": waf_reports.get(publisher.latest_waf_id),
            # ...
        }
        for publisher in publishers
    ]

    serialized = PublisherWithReportsSerializer(result, many=True)
    return inertia_render(request, 'Publishers/Index', props={'publishers': serialized.data})
```

**Verify with Django Debug Toolbar:** Query count should remain ~4 queries regardless of number of publishers

**Warning signs:**
- Query count increases with number of publishers (N+1 detected)
- Page load >500ms for <100 records
- Django Debug Toolbar shows duplicate queries for related objects

### Pitfall 4: TypeScript Type Mismatch Between Serializer and Component

**What goes wrong:** TypeScript compilation passes but runtime errors occur because props don't match interface

**Why it happens:** DRF serializer fields change (field added/removed) but TypeScript interface in columns.tsx not updated

**How to avoid:**
```typescript
// scrapegrape/frontend/src/datatable/columns.tsx
// Keep in sync with publishers/serializers.py

// 1. Define types matching serializer output EXACTLY
export type Publisher = {
    publisher: {
        id: number
        name: string
        url: string
        detected_waf: string
    }
    waf_report: {  // Matches WAFReportSerializer fields
        firewall: string
        manufacturer: string
        detected: boolean
    } | null  // IMPORTANT: Can be null if no report exists
    terms_discovery: {
        terms_of_service_url: string
    } | null
    terms_evaluation: {
        permissions: ActivityPermission[]
        territorial_exceptions: string | null
        arbitration_clauses: string | null
        document_type: string | null
    } | null
}
```

**Verification checklist:**
1. Run Django shell: `PublisherWithReportsSerializer(result[0]).data` → compare output to TypeScript type
2. Add null checks in column accessors: `row.original.waf_report?.firewall ?? 'N/A'`
3. Test with publisher that has no reports (null case)

**Warning signs:**
- Runtime error: "Cannot read properties of null"
- Table cells show "undefined" instead of data
- TypeScript shows no errors but data doesn't render

### Pitfall 5: CSRF Token Expiration on Long-Running Sessions

**What goes wrong:** User loads page, leaves tab open for hours, clicks link → 403 Forbidden error

**Why it happens:** Inertia uses Axios which reads CSRF token from cookie on page load. If cookie expires or rotates, subsequent requests fail.

**How to avoid:** Already handled by Phase 1 configuration. Axios is configured to read token from cookie on EVERY request, not just initial page load:

```typescript
// scrapegrape/frontend/src/main.tsx (already configured in Phase 1)
axios.defaults.xsrfHeaderName = "X-CSRFToken"
axios.defaults.xsrfCookieName = "csrftoken"
// Axios reads cookie on each request, not just once
```

**Verification:**
1. Load page, wait 30 minutes
2. Click Link to another page
3. Verify network tab shows X-CSRFToken header in request
4. No 403 error

**Warning signs:**
- 403 errors on navigation after long idle period
- CSRF token errors in console
- Link clicks failing but hard refresh works

## Code Examples

Verified patterns from official sources and existing codebase:

### Complete View Conversion
```python
# scrapegrape/publishers/views.py
# Source: Existing optimized view + Inertia pattern from Phase 1 research

from django.db.models import Subquery, OuterRef
from inertia import render as inertia_render
from ingestion.models import TermsDiscoveryResult, TermsEvaluationResult
from publishers.models import Publisher, WAFReport
from publishers.serializers import PublisherWithReportsSerializer

def table(request):
    """
    Publisher table view with Inertia response.
    Reuses existing Subquery optimization and DRF serializers.
    """
    # Subqueries to get the latest related object IDs (UNCHANGED)
    latest_waf = Subquery(
        WAFReport.objects.filter(publisher=OuterRef("pk"))
        .order_by("-created_at")
        .values("id")[:1]
    )
    latest_discovery = Subquery(
        TermsDiscoveryResult.objects.filter(publisher=OuterRef("pk"))
        .order_by("-created_at")
        .values("id")[:1]
    )
    latest_evaluation = Subquery(
        TermsEvaluationResult.objects.filter(publisher=OuterRef("pk"))
        .order_by("-created_at")
        .values("id")[:1]
    )

    # Annotate publishers with those latest IDs (UNCHANGED)
    publishers = Publisher.objects.annotate(
        latest_waf_id=latest_waf,
        latest_discovery_id=latest_discovery,
        latest_evaluation_id=latest_evaluation,
    )

    # Get all needed related objects in bulk (UNCHANGED)
    waf_reports = WAFReport.objects.in_bulk(
        publishers.values_list("latest_waf_id", flat=True)
    )
    discovery_results = TermsDiscoveryResult.objects.in_bulk(
        publishers.values_list("latest_discovery_id", flat=True)
    )
    evaluation_results = TermsEvaluationResult.objects.in_bulk(
        publishers.values_list("latest_evaluation_id", flat=True)
    )

    # Build final result (UNCHANGED)
    result = []
    for publisher in publishers:
        result.append(
            {
                "publisher": publisher,
                "waf_report": waf_reports.get(publisher.latest_waf_id),
                "terms_discovery": discovery_results.get(publisher.latest_discovery_id),
                "terms_evaluation": evaluation_results.get(
                    publisher.latest_evaluation_id
                ),
            }
        )

    serialized = PublisherWithReportsSerializer(result, many=True)

    # CHANGED: Return Inertia response instead of template render
    return inertia_render(request, 'Publishers/Index', props={
        'publishers': serialized.data
    })
```

### Page Component Implementation
```typescript
// scrapegrape/frontend/src/Pages/Publishers/Index.tsx
// Source: Derived from existing App.tsx pattern

import { DataTable } from '@/datatable/table'
import { columns, type Publisher } from '@/datatable/columns'

interface Props {
    publishers: Publisher[]
}

export default function Index({ publishers }: Props) {
    return (
        <div className="container mx-auto py-10">
            <h1 className="text-2xl mb-4">Publishers</h1>
            <DataTable columns={columns} data={publishers} />
        </div>
    )
}
```

**Key changes from App.tsx:**
- Removed useState and useEffect (no JSON parsing)
- Props received directly from Django via Inertia
- DataTable and columns imported unchanged

### Shared Data Middleware (Optional for Phase 3)
```python
# scrapegrape/scrapegrape/middleware.py (NEW)
# Source: https://github.com/inertiajs/inertia-django/blob/main/README.md

from inertia import share

def inertia_share(get_response):
    def middleware(request):
        share(request,
            # User authentication state
            user=lambda: {
                'id': request.user.id,
                'username': request.user.username,
                'is_authenticated': request.user.is_authenticated,
            } if request.user.is_authenticated else None,

            # Flash messages (from Django messages framework)
            flash=lambda: {
                'success': request.session.pop('success', None),
                'error': request.session.pop('error', None),
            },
        )
        return get_response(request)
    return middleware
```

```python
# scrapegrape/scrapegrape/settings.py
MIDDLEWARE = [
    # ... existing middleware ...
    'django.contrib.messages.middleware.MessageMiddleware',
    'scrapegrape.middleware.inertia_share',  # ADD AFTER MessageMiddleware
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
```

### Navigation with Link Component (Future Multi-Page)
```typescript
// Example for future pages (Phase 4+)
import { Link } from '@inertiajs/react'

function Navigation() {
    return (
        <nav>
            <Link href="/" className="text-blue-600">
                Publishers
            </Link>
            <Link href="/settings" className="text-gray-600">
                Settings
            </Link>
        </nav>
    )
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| JSON in script tag | Direct props from Inertia | Inertia v1.0+ (2020) | Eliminates parsing overhead, type safety, cleaner data flow |
| Template inheritance for layouts | Persistent layouts with .layout property | Inertia v0.8+ | Preserves component state across navigation, enables stateful UI |
| Full page reload on navigation | XHR requests with page swap | Core Inertia feature | SPA-like experience without client-side routing complexity |
| Manual CSRF token in forms | Automatic CSRF via Axios defaults | Configured in Phase 1 | No manual token passing, auto-refreshes on each response |
| Separate API for frontend | Props from server-side render | Core Inertia concept | No API layer, server-side validation, simpler architecture |

**Deprecated/outdated:**
- Embedding serialized JSON in `<script id="data">` tags (pre-Inertia pattern, still works but defeats purpose)
- Using `<a href>` instead of Link component for internal navigation (causes full page reload, loses SPA benefits)
- Manual prop passing for flash messages (shared data middleware is standard pattern)

## Open Questions

1. **Should Phase 3 include shared data middleware or defer to Phase 4?**
   - What we know: Middleware enables flash messages and auth state across pages, Phase 3 only migrates one page
   - What's unclear: Does single-page migration benefit from shared data, or is it overhead?
   - Recommendation: Defer to Phase 4. Single page doesn't need shared data, add when multi-page navigation exists.

2. **Should persistent layouts be implemented in Phase 3 or Phase 4?**
   - What we know: Layouts preserve state across navigation, useful for multi-page apps
   - What's unclear: Does single "/" page need layout wrapper?
   - Recommendation: Defer to Phase 4. Phase 3 pages render directly without layout (Index.layout not assigned). Add layouts when navigation between pages exists.

3. **Does removing `<div id="root">` from base.html break anything?**
   - What we know: Dual-path entry point checks for `#app` (Inertia) vs `#root` (legacy)
   - What's unclear: Are there other templates or views that depend on `#root`?
   - Recommendation: Verify only index.html extends base.html. If other templates exist and use #root, keep it and conditionally remove in Phase 5 cleanup. If index.html is only user, safe to remove in Phase 3.

## Sources

### Primary (HIGH confidence)
- [Inertia Django GitHub Repository](https://github.com/inertiajs/inertia-django) - Official adapter, shared data middleware pattern
- [Inertia.js Pages Documentation](https://inertiajs.com/docs/v2/the-basics/pages) - Persistent layouts implementation
- [Inertia.js Links Documentation](https://inertiajs.com/docs/v2/the-basics/links) - Link component usage and navigation
- [Django REST Framework Documentation](https://www.django-rest-framework.org/) - Serializer patterns
- Existing codebase analysis:
  - `scrapegrape/publishers/views.py` - Subquery optimization pattern
  - `scrapegrape/publishers/serializers.py` - DRF serializers for props
  - `scrapegrape/frontend/src/App.tsx` - Existing JSON parsing pattern to replace
  - `scrapegrape/frontend/src/main.tsx` - Dual-path entry point (Phase 1)
  - `.planning/phases/01-inertia-infrastructure/01-RESEARCH.md` - Inertia setup patterns

### Secondary (MEDIUM confidence)
- [Building Modern Web App with Django, Inertia.js, Vite, and React](https://medium.com/@tanzid3/building-a-modern-web-app-with-django-inertia-js-vite-and-react-67979a981649) - Migration patterns
- [TanStack Table with React Inertia](https://laracasts.com/discuss/channels/laravel/tanstack-table-with-react-inertia-laravel) - Data flow patterns
- [Advanced Inertia: Persistent Layouts](https://advanced-inertia.com/blog/persistent-layouts) - Layout preservation strategies

### Tertiary (LOW confidence)
- Community blog posts on Django template to Inertia migration (useful for pitfall identification but lack official verification)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already installed and configured, versions verified
- Architecture: HIGH - Existing codebase provides clear template, official docs provide patterns
- Pitfalls: MEDIUM-HIGH - Derived from Phase 1 research, official docs, and codebase analysis; dual-path coexistence is project-specific risk
- Serializer performance: HIGH - Existing Subquery optimization proven working, DRF serializers designed for this use case
- TypeScript integration: MEDIUM - Type matching requires manual verification, no auto-generation tools identified

**Research date:** 2026-02-12
**Valid until:** 2026-03-14 (30 days, stable ecosystem)

**Project-specific notes:**
- Inertia infrastructure already in place (Phase 1: middleware, CSRF, dual-path entry)
- Frontend consolidated (Phase 2: scrapegrape/frontend/ structure, Pages/ directory exists)
- Existing view uses Subquery optimization that MUST be preserved
- DRF serializers already written and tested, perfect for Inertia props
- DataTable and columns.tsx work unchanged, just change data source
- base.html has both `{% block inertia %}` and `<div id="root">` — Phase 3 removes #root after verifying no dependencies
- main.tsx dual-path entry point handles Inertia vs legacy detection automatically
