# Feature Landscape: Django-Inertia Refactor

**Domain:** Django + React with Inertia.js integration
**Researched:** 2026-02-12
**Confidence:** MEDIUM (WebSearch verified with official sources)

## Context

This is a **REFACTOR** of an existing Django+React app. Existing features (WAF detection, ToS discovery, ToS evaluation, bulk CSV import, interactive React data table, Django admin with custom actions, async task pipeline) are already built. This research focuses ONLY on what Inertia.js enables and what the consolidation from `sgui/` to `scrapegrape/frontend/` changes.

**Current state:** Django renders `index.html` template with embedded JSON (`{{ serialized|json_script:"publisher-data" }}`), React parses it from DOM via `document.getElementById('publisher-data')`.

**Target state:** Django views return Inertia responses, React components receive props directly via Inertia.

---

## Table Stakes

Features that Inertia.js users expect. Missing = refactor feels incomplete or broken.

| Feature | Why Expected | Complexity | Dependencies | Notes |
|---------|--------------|------------|--------------|-------|
| **Direct prop passing** | Core Inertia value prop - eliminates DOM JSON parsing | Low | `inertia-django`, `@inertiajs/react` | Replaces `{{ serialized\|json_script:"publisher-data" }}` pattern |
| **SPA-like navigation** | Inertia's primary benefit - no full page reloads | Low | `@inertiajs/react` router | Automatic on all internal links |
| **Shared data** | Global data (user, app name) available to all pages | Low | Inertia middleware with `share()` method | Typical: authenticated user, CSRF token, flash messages |
| **Form validation errors** | Server-side validation errors passed to frontend | Medium | `InertiaValidationError` exception in Django views | Django doesn't auto-redirect like Laravel - need HTTP Referer or `next=` param |
| **CSRF handling** | Django CSRF tokens work with Inertia | Low | `inertia.middleware.InertiaMiddleware` | Auto-adds CSRF cookie; may need to configure Axios defaults |
| **Asset versioning** | Auto-reload on frontend asset changes | Low | `INERTIA_VERSION` in settings or middleware | Vite hash in manifest.json recommended |
| **Progress indicators** | Visual feedback during navigation | Low | `@inertiajs/react` built-in | Default trickling bar; customizable with NProgress |
| **Layout persistence** | Persistent layouts across page transitions | Medium | Inertia layout prop in React components | Avoids re-mounting shared UI (nav, sidebar) |
| **History state management** | Browser back/forward works correctly | Low | Built into Inertia | Automatic; preserves component state in history |

---

## Differentiators

Features that make an Inertia refactor valuable beyond "just works." Not expected, but high-impact.

| Feature | Value Proposition | Complexity | Dependencies | Notes |
|---------|-------------------|------------|--------------|-------|
| **Partial reloads** | Refresh subset of data without full page visit | Medium | `only` prop in `router.visit()`, lazy props in Django | Perf optimization for expensive data lookups |
| **Optional props** | Props excluded by default, loaded only when requested | Medium | `Inertia::optional()` method in Django views | v2 replacement for lazy props (v1) |
| **Deferred props** | Defer prop loading until after initial page render | High | `Inertia::defer()` method, `<Deferred>` component | Improves perceived performance; props fetched in parallel after render |
| **Prefetching** | Preload page data on hover/focus | Medium | `router.prefetch()`, `cacheFor` option | Default 30s cache; great for dashboards |
| **Form helper (`useForm`)** | Progress tracking, error handling, recent success state | Low | `@inertiajs/react` `useForm` hook | Built-in `form.progress.percentage` for uploads |
| **File upload progress** | Real-time upload progress indicator | Low | `useForm` helper auto-detects files, converts to FormData | Automatic FormData conversion when files present |
| **preserveState** | Maintain component state across visits | Medium | `preserveState: true` in `router.visit()` | Useful for form repopulation, tab state |
| **preserveScroll** | Maintain scroll position across visits | Low | `preserveScroll: true` in `router.visit()` | Essential for infinite scroll, paginated tables |
| **History encryption** | Encrypt sensitive data in browser history | High | Inertia v2+, requires HTTPS (uses `window.crypto.subtle`) | Prevents sensitive data in plain text in history state |
| **Custom error pages** | Inertia-rendered error pages (404, 500, 403) | Medium | Django exception handler override, Inertia render | Maintains SPA feel during errors |
| **Grouped deferred props** | Fetch multiple deferred props in one request | High | `Inertia::defer('key', callback, 'groupName')` | Reduces parallel requests for related data |

---

## Anti-Features

Features to explicitly NOT build or enable during the refactor.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Building a JSON API** | Inertia eliminates API need - defeats the purpose | Use Inertia responses directly from Django views |
| **Frontend routing (React Router)** | Inertia handles routing; adding React Router creates conflicts | Use Inertia's `router.visit()` and Django URL patterns |
| **Passing model instances** | Inertia serializes to JSON - models become dicts | Serialize explicitly in Django views before passing |
| **Importing backend code into frontend** | Backend code ends up in frontend bundle | Strict separation: Django logic stays in views |
| **Treating Inertia like an API client** | Inertia is a "views protocol," not a data fetcher | Think "server-side rendered React" not "API consumer" |
| **Manual JSON parsing from DOM** | What we're replacing - defeats Inertia value prop | Use Inertia props exclusively |
| **Separate frontend build server in production** | Vite builds to static assets; Django serves them | Build frontend once, serve via Django staticfiles |
| **Global state management (Redux, Zustand)** | Inertia provides state via props; server is source of truth | Use shared data + props; avoid client-side state duplication |
| **Over-using deferred props** | Adds request waterfall; use sparingly | Only defer truly expensive queries; prefer optional props |

---

## Feature Dependencies

```
CSRF handling → Form validation errors (requires CSRF token)
Direct prop passing → All features (foundation)
Shared data → Form validation errors (flash messages)
Optional props → Partial reloads (subset specification)
Deferred props → Grouped deferred props (grouping mechanism)
Asset versioning → History state management (ensures correct assets on back/forward)
Layout persistence → preserveState (maintains state in persistent layouts)
useForm helper → File upload progress (auto-detects files)
```

---

## Consolidated Project Structure

### Current Structure (sgui/ separate)
```
itsascout/
├── scrapegrape/                  # Django project
│   ├── manage.py
│   ├── scrapegrape/              # Django settings
│   ├── publishers/               # Django app
│   ├── templates/
│   │   ├── base.html
│   │   └── index.html            # Embeds {{ serialized|json_script }}
│   └── docker-compose.yml
└── sgui/                          # Separate React project
    ├── src/
    │   ├── main.tsx              # Entry point
    │   ├── App.tsx               # Parses JSON from DOM
    │   └── datatable/
    ├── package.json
    ├── vite.config.ts
    └── node_modules/
```

### Target Structure (Consolidated with Inertia)
```
itsascout/
└── scrapegrape/                  # Django project root
    ├── manage.py
    ├── scrapegrape/              # Django settings
    │   ├── settings.py           # + INERTIA_LAYOUT, django_vite config
    │   └── urls.py
    ├── publishers/               # Django app
    │   └── views.py              # Returns Inertia responses
    ├── frontend/                 # React + Vite (consolidated from sgui/)
    │   ├── src/
    │   │   ├── main.tsx          # Inertia app setup
    │   │   ├── Pages/            # Inertia page components
    │   │   │   ├── Publishers/
    │   │   │   │   └── Index.tsx # Receives props directly
    │   │   │   └── Error.tsx     # Custom error page
    │   │   ├── Components/       # Shared components (DataTable)
    │   │   └── Layouts/
    │   │       └── App.tsx       # Persistent layout
    │   ├── package.json
    │   ├── vite.config.ts        # Output to ../static/dist/
    │   └── tsconfig.json
    ├── templates/
    │   └── base.html             # Inertia layout with {% block inertia %}
    └── static/
        └── dist/                 # Vite build output
            ├── manifest.json     # Asset hashes for versioning
            └── assets/
```

### Key Structure Changes

| Change | Reason | Impact |
|--------|--------|--------|
| `sgui/` → `scrapegrape/frontend/` | Co-locate frontend with Django app | Simplified deployment, single project root |
| `src/App.tsx` → `Pages/Publishers/Index.tsx` | Inertia page components pattern | Clear separation of pages vs components |
| Add `Layouts/App.tsx` | Persistent layout for nav/header | Avoid re-mounting shared UI |
| Add `Pages/Error.tsx` | Custom error handling | Maintain SPA feel during errors |
| Vite output → `../static/dist/` | Django staticfiles integration | Django serves Vite-built assets |
| `templates/index.html` → `templates/base.html` | Single Inertia layout template | `{% block inertia %}` replaces JSON embedding |

---

## MVP Recommendation

**Prioritize (Phase 1 - Core Refactor):**
1. **Direct prop passing** - Core migration from DOM JSON parsing
2. **CSRF handling** - Security requirement
3. **SPA-like navigation** - Primary Inertia benefit
4. **Shared data** - Global state (user, flash messages)
5. **Form validation errors** - Critical for interactive features
6. **Progress indicators** - Basic UX feedback
7. **Asset versioning** - Development workflow essential

**Add incrementally (Phase 2 - Enhancements):**
8. **useForm helper** - Simplify form handling
9. **Layout persistence** - Optimize re-renders
10. **preserveState / preserveScroll** - Enhanced navigation UX

**Defer (Phase 3 - Optimizations):**
11. **Partial reloads** - Performance optimization for specific pages
12. **Optional props** - Data-specific optimization
13. **Prefetching** - Advanced UX enhancement
14. **Deferred props** - Complex perf optimization
15. **Custom error pages** - Polish
16. **History encryption** - Only if sensitive data in URLs

---

## Complexity Notes

### Low Complexity (Quick wins)
- Direct prop passing, CSRF handling, SPA navigation, asset versioning, progress indicators, preserveScroll
- **Reason:** Built-in Inertia features, minimal configuration

### Medium Complexity (Requires planning)
- Shared data, form validation errors, layout persistence, partial reloads, optional props, custom error pages
- **Reason:** Requires view refactoring, Django middleware understanding, or component architecture changes

### High Complexity (Deep integration)
- Deferred props, history encryption, grouped deferred props
- **Reason:** Multiple request cycles, security considerations, or advanced Inertia patterns

---

## Django-Specific Inertia Patterns

### Inertia Response (replaces `render()`)
```python
from inertia import render as inertia_render

def index(request):
    publishers = Publisher.objects.all()
    return inertia_render(request, 'Publishers/Index', {
        'publishers': PublisherSerializer(publishers, many=True).data,
        'filters': request.GET.dict(),
    })
```

### Shared Data (middleware or views)
```python
# In custom middleware or view
from inertia import share

share(request,
    app_name='ItsAScout',
    user=request.user.username if request.user.is_authenticated else None,
)
```

### Form Validation Errors
```python
from inertia.http import InertiaValidationError

def create_publisher(request):
    form = PublisherForm(request.POST)
    if not form.is_valid():
        raise InertiaValidationError(
            errors=form.errors.get_json_data(),
            redirect_to=request.META.get('HTTP_REFERER', '/publishers')
        )
    # ... save form
```

### Optional Props (lazy evaluation)
```python
from inertia import lazy

def dashboard(request):
    return inertia_render(request, 'Dashboard/Index', {
        'stats': {'total': Publisher.objects.count()},  # Always loaded
        'expensive_data': lazy(lambda: expensive_computation()),  # Only on partial reload
    })
```

### Asset Versioning
```python
# settings.py
import json
from pathlib import Path

def get_asset_version():
    manifest_path = BASE_DIR / 'static' / 'dist' / 'manifest.json'
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)
            return manifest.get('main.tsx', {}).get('file', 'dev')
    return 'dev'

INERTIA_VERSION = get_asset_version()
```

---

## Sources

**HIGH Confidence (Official Documentation):**
- [Inertia Django - GitHub](https://github.com/inertiajs/inertia-django)
- [Partial Reloads - Inertia.js Documentation](https://inertiajs.com/docs/v2/data-props/partial-reloads)
- [Forms - Inertia.js Documentation](https://inertiajs.com/docs/v2/the-basics/forms)
- [File Uploads - Inertia.js Documentation](https://inertiajs.com/docs/v2/the-basics/file-uploads)
- [Manual Visits - Inertia.js Documentation](https://inertiajs.com/docs/v2/the-basics/manual-visits)
- [Deferred Props - Inertia.js Documentation](https://inertiajs.com/docs/v2/data-props/deferred-props)
- [Asset Versioning - Inertia.js Documentation](https://inertiajs.com/docs/v2/advanced/asset-versioning)
- [Error Handling - Inertia.js Documentation](https://inertiajs.com/docs/v2/advanced/error-handling)

**MEDIUM Confidence (Tutorials & Community):**
- [Building a Modern Web App with Django, Inertia.js, Vite, and React - Medium](https://medium.com/@tanzid3/building-a-modern-web-app-with-django-inertia-js-vite-and-react-67979a981649)
- [How to setup Django with React using InertiaJS - Anjanesh](https://anjanesh.dev/how-to-setup-django-with-react-using-inertiajs)
- [django-vite-inertia - GitHub Template](https://github.com/SarthakJariwala/django-vite-inertia)
- [Django Breeze - Django Starter](https://github.com/Louxsdon/django-breeze)

**LOW Confidence (Search Results, Single Sources):**
- [Validation & Error Bags - Issue #30](https://github.com/inertiajs/inertia-django/issues/30)
- [Inertia.js adoption guide - LogRocket](https://blog.logrocket.com/inertia-js-adoption-guide/)

---

**Research Date:** 2026-02-12
**Overall Confidence:** MEDIUM (WebSearch verified with official Inertia.js docs; Django-specific implementation details require validation during implementation)
