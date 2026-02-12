# Phase 1: Inertia Infrastructure - Research

**Researched:** 2026-02-12
**Domain:** Inertia.js with Django + React + Vite
**Confidence:** MEDIUM-HIGH

## Summary

Phase 1 integrates Inertia.js into an existing Django application with React and Vite already configured. The project currently uses django-vite 3.1.0 for asset management and has a working Vite + React setup in the `sgui/` directory. Inertia.js acts as the "glue" layer between Django's server-side routing and React's client-side rendering, enabling SPA-like navigation without requiring a separate REST API.

The core implementation involves installing the inertia-django Python adapter (latest: 1.2.0) and @inertiajs/react npm package (latest: 2.3.14), adding InertiaMiddleware to Django's middleware stack, configuring CSRF tokens for Axios compatibility, creating a base template with the Inertia root element, and setting up the React entry point with createInertiaApp and import.meta.glob for page resolution.

**Primary recommendation:** Use the manual setup approach since django-vite is already configured. Focus on middleware ordering (InertiaMiddleware after CSRF, before authentication), configure CSRF for Django/Axios compatibility using Axios defaults, and validate with a minimal smoke test at `/_debug/inertia/` before migrating any production views.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Smoke test page:**
- Minimal render only — just prove Inertia loads a React component with props from Django
- No form POST or serializer validation on the test page (those are validated separately)
- Lives at `/_debug/inertia/` under a debug namespace
- No auth required — it's a dev tool on localhost
- Temporary scaffolding — remove in Phase 5 cleanup

**Route coexistence:**
- Explicit routes only — each Inertia view gets its own URL pattern, no catch-all
- Routes go in the main `urls.py` alongside existing ones
- Root route `/` stays untouched as the existing template view throughout Phase 1
- Unmatched URLs fall through to Django's normal 404

**Dev workflow:**
- Docker compose already handles Django + Vite — no changes needed to docker-compose.yml
- Errors display via Django's default debug error page; React errors in browser console
- Use whatever package manager the project already uses for frontend dependencies

### Claude's Discretion

- Exact middleware ordering in settings
- CSRF configuration details (meta tag format, Axios interceptor setup)
- createInertiaApp configuration and page resolution pattern
- Base template structure for Inertia root div placement

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope

</user_constraints>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| inertia-django | 1.2.0 | Django server-side adapter | Official Inertia.js adapter for Django, actively maintained by core team |
| @inertiajs/react | 2.3.14 | React client-side adapter | Official React adapter with hooks, forms, and router support |
| django-vite | 3.1.0 (existing) | Asset bundling integration | Already configured, handles dev HMR and production manifest |
| axios | (peer dependency) | HTTP client | Built into @inertiajs/react, handles CSRF and XHR requests |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| djangorestframework | 3.16.0 (existing) | Serializer infrastructure | Already installed, use for complex prop serialization |
| React | 19.1.0 (existing) | Component framework | Already configured with TypeScript support |
| Vite | 7.0.4 (existing) | Build tool | Already configured with React plugin and HMR |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| inertia-django 1.2.0 | django-inertia 1.3.0 | Different fork with similar API, but inertia-django is the official adapter maintained by Inertia.js core team |
| Manual CSRF setup | Meta tag approach | Official docs recommend Axios defaults for cookie-based CSRF (cleaner, auto-refreshes) |

**Installation:**
```bash
# Python (backend)
uv pip install inertia-django

# JavaScript (frontend)
npm install @inertiajs/react axios
```

## Architecture Patterns

### Recommended Project Structure
```
scrapegrape/                  # Django project root
├── scrapegrape/
│   ├── settings.py          # Add InertiaMiddleware, INERTIA_LAYOUT
│   └── urls.py              # Add /_debug/ namespace
├── templates/
│   └── base.html            # Update with {% block inertia %}
└── publishers/              # Example app
    └── views.py             # Use render() or @inertia decorator

sgui/                        # Vite frontend root
├── src/
│   ├── main.tsx            # Replace with createInertiaApp setup
│   ├── Pages/              # NEW: Inertia page components
│   │   └── Debug/
│   │       └── InertiaTest.tsx
│   └── components/         # Existing UI components
└── vite.config.ts          # No changes needed (already configured)
```

### Pattern 1: Rendering Inertia Responses

**What:** Three ways to return Inertia responses from Django views
**When to use:** render() for explicit responses, @inertia decorator for simple views, InertiaResponse for full control

**Example:**
```python
# Source: https://github.com/inertiajs/inertia-django/blob/main/README.md

# Option 1: render function (explicit)
from inertia import render
from .models import Event

def index(request):
    return render(request, 'Event/Index', props={
        'events': Event.objects.all()
    })

# Option 2: @inertia decorator (cleanest)
from inertia import inertia

@inertia('Event/Index')
def index(request):
    return {
        'events': Event.objects.all(),
    }

# Option 3: InertiaResponse (full control)
from inertia import InertiaResponse

def index(request):
    return InertiaResponse(
        request,
        'Event/Index',
        props={'events': Event.objects.all()}
    )
```

### Pattern 2: Client-Side Setup with createInertiaApp

**What:** Initialize Inertia app with page resolution and React rendering
**When to use:** Required in main.tsx entry point

**Example:**
```tsx
// Source: https://inertiajs.com/docs/v2/installation/client-side-setup

import { createInertiaApp } from '@inertiajs/react'
import { createRoot } from 'react-dom/client'

createInertiaApp({
    resolve: name => {
        const pages = import.meta.glob('./Pages/**/*.tsx', { eager: true })
        return pages[`./Pages/${name}.tsx`]
    },
    setup({ el, App, props }) {
        createRoot(el).render(<App {...props} />)
    },
})
```

### Pattern 3: CSRF Configuration for Django + Axios

**What:** Configure Axios to use Django's CSRF cookie/header names
**When to use:** Required in main.tsx before createInertiaApp

**Example:**
```typescript
// Source: https://github.com/inertiajs/inertia-django/blob/main/README.md

import axios from 'axios'

// Configure Axios to match Django's CSRF naming
axios.defaults.xsrfHeaderName = "X-CSRFToken"
axios.defaults.xsrfCookieName = "csrftoken"

// Then initialize Inertia...
```

**Alternative (modify Django instead):**
```python
# settings.py - makes Django match Axios defaults
CSRF_HEADER_NAME = 'HTTP_X_XSRF_TOKEN'
CSRF_COOKIE_NAME = 'XSRF-TOKEN'
```

### Pattern 4: Base Template Structure

**What:** HTML template with Inertia root element and django-vite tags
**When to use:** INERTIA_LAYOUT template (e.g., base.html or inertia.html)

**Example:**
```html
{% load django_vite %}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}App{% endblock %}</title>

    {% vite_hmr_client %}
    {% vite_react_refresh %}
    {% vite_asset 'src/main.tsx' %}
</head>
<body>
    {% block inertia %}{% endblock %}
</body>
</html>
```

**Key points:**
- `{% block inertia %}` is where InertiaMiddleware injects the `<div id="app" data-page="...">` element
- django-vite tags handle dev HMR and production manifest references
- No CSRF meta tag needed (Axios uses cookies, not meta tags)

### Anti-Patterns to Avoid

- **Don't include CSRF meta tag in template:** Inertia uses cookie-based CSRF via Axios, meta tags prevent proper token refresh (Laravel-specific issue, but good practice for Django too)
- **Don't use catch-all routes:** Explicit URL patterns prevent conflicts with existing Django views and provide clearer debugging
- **Don't serialize everything:** Pass minimal props to pages, serialize only what the view needs (performance and security)
- **Don't hand-roll page resolution:** Use import.meta.glob with eager loading for predictable behavior and Vite tree-shaking

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON serialization | Custom encoder for models | InertiaJsonEncoder with InertiaMeta | Handles QuerySets, models, field exclusions; DRF serializers integrate naturally |
| CSRF token handling | Manual token extraction/injection | Axios defaults + InertiaMiddleware | Middleware auto-adds CSRF cookie, Axios auto-reads it, tokens refresh correctly |
| Page component loading | Dynamic imports with path logic | import.meta.glob('./Pages/**/*.tsx', { eager: true }) | Vite optimizes at build time, explicit errors for missing components |
| Form validation | Custom error prop mapping | Inertia's useForm hook | Auto-maps server errors to fields, handles progress state, prevents double-submit |

**Key insight:** Inertia provides tight integration points that break when replaced with custom solutions. InertiaMiddleware's CSRF handling, for example, ensures cookies refresh on each response—manual approaches often miss this and create "token expired" bugs.

## Common Pitfalls

### Pitfall 1: Middleware Ordering Conflicts

**What goes wrong:** CSRF errors, missing request data, or authentication failures when InertiaMiddleware is in the wrong position

**Why it happens:** Django processes middleware in order during request phase (top-down) and reverse order during response phase. InertiaMiddleware needs access to CSRF tokens (requires CsrfViewMiddleware) and may need request.user (requires AuthenticationMiddleware), but must process responses before debug toolbar or other interceptors.

**How to avoid:**
```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',      # BEFORE Inertia
    'inertia.middleware.InertiaMiddleware',            # AFTER CSRF
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
```

**Warning signs:**
- 403 Forbidden on POST requests
- InertiaMiddleware not visible in Django Debug Toolbar panels
- Props missing from page components

### Pitfall 2: CSRF Token Mismatch Between Django and Axios

**What goes wrong:** POST requests fail with 403 CSRF verification failed, even with middleware configured

**Why it happens:** Django uses `csrftoken` cookie and expects `X-CSRFToken` header. Axios uses `XSRF-TOKEN` cookie and sends `X-XSRF-TOKEN` header by default. Without configuration, they don't communicate.

**How to avoid:** Pick one approach and configure it in main.tsx before createInertiaApp:
```typescript
// RECOMMENDED: Make Axios use Django's names (no Django changes)
axios.defaults.xsrfHeaderName = "X-CSRFToken"
axios.defaults.xsrfCookieName = "csrftoken"

// ALTERNATIVE: Make Django use Axios's names (requires settings.py change)
// CSRF_HEADER_NAME = 'HTTP_X_XSRF_TOKEN'
// CSRF_COOKIE_NAME = 'XSRF-TOKEN'
```

**Warning signs:**
- Form submissions work in Postman/curl but fail from React
- CSRF token appears in cookies but not in request headers
- Error message: "CSRF token missing or incorrect"

### Pitfall 3: Page Resolution Path Mismatches

**What goes wrong:** "Component not found" or blank pages when navigating, even though the component file exists

**Why it happens:** The resolve callback in createInertiaApp must exactly match the component name passed from Django's render() function. Case sensitivity, file extensions, and path structure all matter.

**How to avoid:**
```typescript
// Django view passes: render(request, 'Debug/InertiaTest', props={...})
// Resolve callback must find: ./Pages/Debug/InertiaTest.tsx

resolve: name => {
    const pages = import.meta.glob('./Pages/**/*.tsx', { eager: true })
    return pages[`./Pages/${name}.tsx`]  // Must match exactly
}
```

**Warning signs:**
- Console error: "Cannot read properties of undefined"
- Network tab shows correct Inertia response but page doesn't render
- Changing the component name in Django fixes it

### Pitfall 4: Over-Serialization of Props

**What goes wrong:** Slow page loads, large payload sizes, or JSON serialization errors on complex objects

**Why it happens:** Django's model_to_dict (used by InertiaJsonEncoder) includes all fields and follows relationships. Passing a full QuerySet or model with foreign keys can serialize hundreds of unnecessary fields.

**How to avoid:**
```python
# BAD: Serializes everything
def index(request):
    return render(request, 'Event/Index', props={
        'events': Event.objects.all()  # All fields, all relationships
    })

# GOOD: Explicit fields only
def index(request):
    return render(request, 'Event/Index', props={
        'events': Event.objects.values('id', 'name', 'date')
    })

# BEST: Use DRF serializer for control
from rest_framework import serializers

class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ['id', 'name', 'date']

def index(request):
    events = EventSerializer(Event.objects.all(), many=True).data
    return render(request, 'Event/Index', props={'events': events})
```

**Warning signs:**
- Network payload > 100KB for simple pages
- JSON serialization errors on datetime/file fields
- Django Debug Toolbar shows high query counts

### Pitfall 5: Root Element ID Mismatch

**What goes wrong:** React app doesn't mount, page shows empty `<div id="app">` with no content

**Why it happens:** createInertiaApp defaults to mounting on `<div id="app">`, but if your base template uses a different ID or multiple root divs exist, React can't find the mount point.

**How to avoid:**
```html
<!-- base.html: Django sets the root element via {% block inertia %} -->
<body>
    {% block inertia %}{% endblock %}  <!-- This becomes <div id="app"> -->
</body>
```

```typescript
// main.tsx: Use default 'app' id (matches Django)
createInertiaApp({
    // id: 'app',  // Optional, this is the default
    resolve: name => { /* ... */ },
    setup({ el, App, props }) {
        createRoot(el).render(<App {...props} />)
    },
})
```

**Warning signs:**
- React DevTools shows no components
- "Target container is not a DOM element" error
- Page source shows `<div id="app" data-page="...">` but remains empty

## Code Examples

Verified patterns from official sources:

### Django Settings Configuration
```python
# scrapegrape/scrapegrape/settings.py
# Source: https://inertiajs.github.io/inertia-django/guide/server-side-setup

INSTALLED_APPS = [
    # ... existing apps
    'django_vite',      # Already installed
    'inertia',          # NEW: Add inertia-django
    # ... your apps
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'inertia.middleware.InertiaMiddleware',  # NEW: After CSRF, before Auth
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Inertia settings
INERTIA_LAYOUT = 'base.html'  # NEW: Required setting

# django-vite settings (already configured)
DJANGO_VITE = {
    "default": {
        "dev_mode": DEBUG,
        "manifest_path": BASE_DIR.parent / "sgui" / "dist" / "manifest.json",
    }
}
```

### Smoke Test View
```python
# scrapegrape/publishers/views.py or dedicated debug app
# Source: Official Inertia-Django documentation patterns

from inertia import render

def inertia_smoke_test(request):
    """
    Minimal smoke test: proves Inertia renders a React component.
    Lives at /_debug/inertia/ temporarily (remove in Phase 5).
    """
    return render(request, 'Debug/InertiaTest', props={
        'message': 'Inertia is working!',
        'timestamp': '2026-02-12',
    })
```

### URL Configuration
```python
# scrapegrape/scrapegrape/urls.py

from django.urls import path
from publishers.views import inertia_smoke_test  # or from debug app

urlpatterns = [
    # ... existing routes

    # Debug namespace (temporary, remove in Phase 5)
    path('_debug/inertia/', inertia_smoke_test, name='debug-inertia'),

    # Root route stays as existing template view
    # path('', existing_view, name='home'),
]
```

### React Entry Point (main.tsx)
```typescript
// sgui/src/main.tsx
// Source: https://inertiajs.com/docs/v2/installation/client-side-setup

import { createInertiaApp } from '@inertiajs/react'
import { createRoot } from 'react-dom/client'
import axios from 'axios'

// Configure CSRF for Django compatibility
axios.defaults.xsrfHeaderName = "X-CSRFToken"
axios.defaults.xsrfCookieName = "csrftoken"

createInertiaApp({
    resolve: name => {
        const pages = import.meta.glob('./Pages/**/*.tsx', { eager: true })
        return pages[`./Pages/${name}.tsx`]
    },
    setup({ el, App, props }) {
        createRoot(el).render(<App {...props} />)
    },
})
```

### Smoke Test React Component
```typescript
// sgui/src/Pages/Debug/InertiaTest.tsx

interface Props {
    message: string
    timestamp: string
}

export default function InertiaTest({ message, timestamp }: Props) {
    return (
        <div style={{ padding: '2rem', fontFamily: 'sans-serif' }}>
            <h1>Inertia Smoke Test</h1>
            <p><strong>Message from Django:</strong> {message}</p>
            <p><strong>Timestamp:</strong> {timestamp}</p>
            <p style={{ color: 'green' }}>✓ Inertia.js is correctly configured</p>
        </div>
    )
}
```

### Base Template Update
```html
<!-- scrapegrape/templates/base.html -->
{% load django_vite %}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Scrapegrape{% endblock %}</title>

    {% vite_hmr_client %}
    {% vite_react_refresh %}
    {% vite_asset 'src/main.tsx' %}

    {% block extra_head %}{% endblock %}
</head>
<body>
    {% block inertia %}{% endblock %}

    {% block extra_body %}{% endblock %}
</body>
</html>
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Meta tag CSRF | Cookie-based CSRF via Axios | Inertia v1.0+ | Automatic token refresh, no manual prop passing |
| Lazy loading pages | Eager loading with import.meta.glob | Vite 4+ | Better tree-shaking, build-time errors for missing pages |
| Manual JSON encoders | InertiaMeta class pattern | inertia-django 1.2+ | DRF-style serializer pattern, cleaner than model_to_dict |
| Separate API endpoints | Direct prop passing | Core Inertia concept | No REST API needed, server-side validation works naturally |

**Deprecated/outdated:**
- `@inertiajs/inertia-react` package (old namespace, use `@inertiajs/react` for v2+)
- Laravel-specific CSRF meta tag approach (Django never needed this, but some tutorials incorrectly suggest it)
- `router.visit()` without CSRF config (works for GET, fails for POST without Axios defaults)

## Open Questions

1. **Django Debug Toolbar Integration with Inertia Responses**
   - What we know: Debug toolbar works with AJAX requests since v1.8, middleware ordering matters
   - What's unclear: Does the toolbar appear on Inertia XHR responses, or only full page loads?
   - Recommendation: Test with `/_debug/inertia/` smoke test, validate toolbar appears in middleware panel

2. **DRF Serializer vs InertiaJsonEncoder for Complex Props**
   - What we know: InertiaMeta class supports fields specification, DRF serializers work as-is
   - What's unclear: Performance difference at scale, nested serializer handling
   - Recommendation: Start with InertiaJsonEncoder for simple cases, migrate to DRF serializers if InertiaMeta becomes complex (threshold: >3 related models)

3. **TypeScript Prop Types Generation**
   - What we know: Props are strongly typed in React components, serializers define structure in Python
   - What's unclear: Any tools to auto-generate TS interfaces from Django models/serializers?
   - Recommendation: Manually define TypeScript interfaces for Phase 1, research code generation in later phase if prop complexity grows

## Sources

### Primary (HIGH confidence)
- [Inertia.js Official Documentation](https://inertiajs.com/) - Core concepts and architecture
- [Inertia Django Documentation](https://inertiajs.github.io/inertia-django/guide/) - Server-side setup guide
- [inertia-django GitHub Repository](https://github.com/inertiajs/inertia-django) - Official adapter, README with examples
- [inertia-django PyPI](https://pypi.org/project/inertia-django/) - Version 1.2.0, March 2025
- [@inertiajs/react npm](https://www.npmjs.com/package/@inertiajs/react) - Version 2.3.14, React adapter
- [Inertia CSRF Protection Docs](https://inertiajs.com/docs/v2/security/csrf-protection) - Official CSRF configuration
- [Inertia Client-Side Setup](https://inertiajs.com/docs/v2/installation/client-side-setup) - createInertiaApp configuration

### Secondary (MEDIUM confidence)
- [Building Modern Web App with Django, Inertia.js, Vite, and React](https://medium.com/@tanzid3/building-a-modern-web-app-with-django-inertia-js-vite-and-react-67979a981649) - Practical integration example (2025)
- [How to setup Django with React using InertiaJS](https://anjanesh.dev/how-to-setup-django-with-react-using-inertiajs) - Community tutorial
- [Django Debug Toolbar Documentation](https://django-debug-toolbar.readthedocs.io/en/latest/installation.html) - Middleware ordering guidance
- [django-vite GitHub](https://github.com/MrBin99/django-vite) - Manifest and production build configuration

### Tertiary (LOW confidence)
- Various community blog posts on Inertia + Django (useful for pitfall identification but not authoritative)
- GitHub issue discussions about CSRF and middleware ordering (anecdotal, but reveal common problems)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Official packages with clear version numbers, actively maintained
- Architecture: MEDIUM-HIGH - Official docs provide patterns, but Django-specific guidance less detailed than Laravel
- Pitfalls: MEDIUM - Derived from official docs, GitHub issues, and community tutorials; needs validation in project context
- CSRF configuration: HIGH - Well-documented in official sources, clear Django + Axios pattern
- Testing approach: LOW - Official testing docs focus on Laravel/Rails, Django testing patterns less documented

**Research date:** 2026-02-12
**Valid until:** 2026-03-14 (30 days, stable ecosystem)

**Project-specific notes:**
- django-vite 3.1.0 already configured correctly (verified in settings.py)
- React 19.1.0 and TypeScript already set up (verified in package.json)
- DRF 3.16.0 available for serializer patterns (verified in pyproject.toml)
- Docker compose handles Vite dev server on port 5173 (verified in docker-compose.yml)
- Current frontend entry point at sgui/src/main.tsx needs replacement
- Base template at scrapegrape/templates/base.html has django-vite tags, needs {% block inertia %}
