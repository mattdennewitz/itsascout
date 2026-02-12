# Technology Stack: Django-Inertia Integration

**Project:** itsascout - Django + Inertia.js + React Refactor
**Researched:** 2026-02-12
**Confidence:** MEDIUM (WebSearch + official docs verification needed for exact version constraints)

## Executive Summary

This refactor adds Inertia.js as a bridge between Django 5.2 and React 19, replacing the current JSON-embedded-in-HTML approach with a proper SPA-like architecture. The stack additions are minimal: one Python package (inertia-django), two npm packages (@inertiajs/react + @inertiajs/core), and configuration changes. **django-vite stays** - it works alongside inertia-django, not replaced by it.

## Stack Additions for Inertia Integration

### Backend: Python Packages

| Package | Version | Purpose | Why |
|---------|---------|---------|-----|
| **inertia-django** | 1.2.0+ | Official Django adapter for Inertia.js | Active maintenance (last release Mar 2025), supports Django 4.x (5.x likely works, needs verification). Only official Inertia.js Django adapter. |

**Installation:**
```bash
uv add inertia-django
# or
pip install inertia-django
```

**Dependencies:** None beyond Django. Optional `[ssr]` extra adds `requests` for server-side rendering.

**Django Version Compatibility:** Officially lists Django 4 support. Django 5.2 compatibility not explicitly documented but likely compatible (needs testing or version constraint check in pyproject.toml).

### Frontend: npm Packages

| Package | Version | Purpose | Why |
|---------|---------|---------|-----|
| **@inertiajs/react** | 2.3.8+ | React adapter for Inertia.js | Latest stable (published Feb 9, 2026). Provides `createInertiaApp`, `Link`, `Head`, hooks (`usePage`, `useForm`, etc.). |
| **@inertiajs/core** | 2.3.14+ | Core Inertia.js functionality | Dependency of @inertiajs/react. Handles routing, state management, Axios integration. Auto-installed as peer dependency. |

**Installation:**
```bash
npm install @inertiajs/react
# @inertiajs/core is auto-installed as dependency
```

**Peer Dependencies:**
- React 18+ (React 19.1 compatibility: MEDIUM confidence - no explicit docs, but actively maintained through Feb 2026)
- react-dom 18+ (same version as React)

**Note:** Axios is bundled with @inertiajs/core. Do NOT add axios separately unless needed for non-Inertia requests.

### Optional: Progress Indicator

| Package | Version | Purpose | Why |
|---------|---------|---------|-----|
| **@inertiajs/progress** | Latest | Loading bar for Inertia visits | Optional. Wrapper around NProgress. 250ms default delay. Only add if you want visual loading feedback. |

**Installation:**
```bash
npm install @inertiajs/progress
```

## Packages to KEEP (Not Remove)

| Package | Keep? | Why |
|---------|-------|-----|
| **django-vite** | YES | Works alongside inertia-django. Handles Vite manifest, HMR, asset serving. Inertia doesn't replace this. |
| **@vitejs/plugin-react** | YES | Still needed for React Fast Refresh and JSX transform in Vite. |
| **TanStack Table** | YES | Still used in React components. Inertia doesn't replace UI libraries. |
| **TailwindCSS** | YES | Still used for styling. Inertia is routing/state, not styling. |

## Packages to POTENTIALLY REMOVE

| Package | Remove? | Why |
|---------|---------|-----|
| **Django REST Framework** | MAYBE | If you're ONLY using DRF for API endpoints that serve the React frontend, Inertia replaces this pattern. If you have external API consumers (mobile apps, third-party integrations), KEEP DRF for those endpoints. Assess per-endpoint. |
| **react-router-dom** | YES (if installed) | Inertia replaces client-side routing. Using both causes conflicts (back button breaks, duplicate history entries). |

## Configuration Changes Required

### Django Settings (`scrapegrape/scrapegrape/settings.py`)

```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_vite",        # KEEP - works with Inertia
    "inertia",            # ADD - Inertia Django adapter
    "django_object_actions",
    "django_tasks",
    "django_tasks.backends.database",
    "rest_framework",     # ASSESS - remove if no external API needs
    "ingestion",
    "publishers",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "inertia.middleware.InertiaMiddleware",  # ADD - handles Inertia requests
]

# ADD - Inertia configuration
INERTIA_LAYOUT = "base.html"  # Template with {% block inertia %}
INERTIA_VERSION = "1.0"       # Optional: for asset versioning cache busting
```

### Template Changes (`scrapegrape/templates/base.html`)

**BEFORE (current):**
```html
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
</head>
<body>
    <div id="root">
    </div>
</body>
</html>
```

**AFTER (with Inertia):**
```html
{% load django_vite %}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="csrf-token" content="{{ csrf_token }}">  <!-- ADD for Axios CSRF -->
    <title>{% block title %}Scrapegrape{% endblock %}</title>

    {% vite_hmr_client %}
    {% vite_react_refresh %}
    {% vite_asset 'src/main.tsx' %}
</head>
<body>
    {% block inertia %}
        <div id="app" data-page="{{ page }}"></div>
    {% endblock %}
</body>
</html>
```

**Key Changes:**
1. Add `<meta name="csrf-token">` for Axios CSRF protection
2. Replace `<div id="root">` with `{% block inertia %}` containing `<div id="app" data-page="{{ page }}">`
3. Keep django_vite template tags (they work with Inertia)

### Vite Config (`sgui/vite.config.ts`)

**Current config works as-is.** No changes required. Inertia doesn't need special Vite plugins.

**Your existing config:**
```typescript
import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  base: "/static/",
  build: {
    manifest: "manifest.json",
    outDir: "dist",
    rollupOptions: {
      input: "src/main.tsx",
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    cors: true,
  },
})
```

**No changes needed.** Django-vite reads `manifest.json`, Inertia uses the same assets.

### Frontend Entry Point (`sgui/src/main.tsx`)

**BEFORE (current - assumed structure):**
```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

**AFTER (with Inertia):**
```tsx
import { createRoot } from 'react-dom/client'
import { createInertiaApp } from '@inertiajs/react'

createInertiaApp({
  resolve: (name) => {
    const pages = import.meta.glob('./pages/**/*.tsx', { eager: true })
    return pages[`./pages/${name}.tsx`]
  },
  setup({ el, App, props }) {
    createRoot(el).render(<App {...props} />)
  },
})
```

**With optional progress indicator:**
```tsx
import { createRoot } from 'react-dom/client'
import { createInertiaApp } from '@inertiajs/react'
import { InertiaProgress } from '@inertiajs/progress'

// Optional: Configure loading bar
InertiaProgress.init({
  delay: 250,
  color: '#4B5563',  // Tailwind gray-600 or your brand color
})

createInertiaApp({
  resolve: (name) => {
    const pages = import.meta.glob('./pages/**/*.tsx', { eager: true })
    return pages[`./pages/${name}.tsx`]
  },
  setup({ el, App, props }) {
    createRoot(el).render(<App {...props} />)
  },
})
```

**Directory structure required:**
```
sgui/src/
├── main.tsx           # Inertia entry point
└── pages/             # Inertia page components (matches Django view names)
    └── Publishers/
        └── Index.tsx  # Rendered by render(request, 'Publishers/Index', {...})
```

## Django View Pattern Changes

### Before (DRF API pattern):
```python
from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(['GET'])
def publishers_list(request):
    publishers = Publisher.objects.all()
    serializer = PublisherSerializer(publishers, many=True)
    return Response(serializer.data)
```

### After (Inertia pattern):
```python
from inertia import render

def publishers_list(request):
    publishers = Publisher.objects.all()
    return render(request, 'Publishers/Index', {
        'publishers': [
            {
                'id': p.id,
                'name': p.name,
                'domain': p.domain,
                # ... serialize fields manually or use serializer.data
            }
            for p in publishers
        ]
    })
```

**Notes:**
- `render()` is from `inertia` package, not `django.shortcuts`
- First arg: request
- Second arg: component name (relative to `sgui/src/pages/`)
- Third arg: props dict (becomes component props)
- Returns HTTP 200 with HTML on first load, JSON on XHR requests (Inertia handles this)

## CSRF Protection

Inertia uses Axios, which automatically reads XSRF-TOKEN cookie and sends X-XSRF-TOKEN header.

**Django setup (already configured):**
- CSRF middleware enabled ✓
- Add `<meta name="csrf-token" content="{{ csrf_token }}">` to base template

**No frontend CSRF code needed** - Axios handles it automatically when meta tag is present.

## Migration Path Summary

### Phase 1: Install packages
```bash
# Backend
uv add inertia-django

# Frontend
cd sgui
npm install @inertiajs/react
npm install @inertiajs/progress  # optional
```

### Phase 2: Configure Django
1. Add `inertia` to `INSTALLED_APPS`
2. Add `inertia.middleware.InertiaMiddleware` to `MIDDLEWARE`
3. Add `INERTIA_LAYOUT = "base.html"` to settings
4. Update `base.html` template (add CSRF meta tag, change root div to inertia block)

### Phase 3: Update frontend
1. Create `sgui/src/pages/` directory
2. Rewrite `main.tsx` to use `createInertiaApp`
3. Move components from current structure to `pages/` directory

### Phase 4: Convert views
1. Change imports from `rest_framework` to `inertia`
2. Replace `Response(serializer.data)` with `render(request, 'Component/Name', props)`
3. Update URL patterns (remove DRF routers if unused elsewhere)

### Phase 5: Clean up
1. Remove `react-router-dom` if installed
2. Assess DRF removal (only if no external API consumers)
3. Test all routes, verify HMR still works

## Anti-Patterns to Avoid

| Anti-Pattern | Why Bad | Correct Approach |
|--------------|---------|------------------|
| Installing `axios` separately | Inertia bundles Axios; installing separately causes version conflicts | Let @inertiajs/react provide Axios |
| Removing `django-vite` | django-vite handles asset serving, HMR, manifest reading. Inertia doesn't replace this. | Keep django-vite, configure both |
| Using React Router with Inertia | Causes back button bugs, duplicate history entries, routing conflicts | Use Inertia's `<Link>` component for navigation |
| Returning DRF `Response` in Inertia views | Inertia expects specific JSON format with component name + props | Use `inertia.render()` |
| Manual CSRF token handling in React | Axios auto-reads meta tag and sends header | Just add meta tag, no JS code needed |
| Lazy-loading pages with `import()` | Adds complexity for marginal benefit in small apps | Use `import.meta.glob(..., { eager: true })` |

## Package Versions Summary

**Python:**
```toml
dependencies = [
    "inertia-django>=1.2.0",  # Add
    "django-vite>=3.1.0",     # Keep (already installed)
    "django>=5.2.4",          # Keep
]
```

**npm:**
```json
{
  "dependencies": {
    "@inertiajs/react": "^2.3.8",
    "@tanstack/react-table": "^8.21.3",
    "react": "^19.1.0",
    "react-dom": "^19.1.0",
    "tailwindcss": "^4.1.11"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.6.0",
    "vite": "^7.0.4"
  }
}
```

**Optional npm:**
```json
{
  "dependencies": {
    "@inertiajs/progress": "latest"  // If loading indicators desired
  }
}
```

## Confidence Assessment

| Area | Confidence | Reason |
|------|------------|--------|
| Core packages (inertia-django, @inertiajs/react) | HIGH | Official packages, actively maintained, widely documented |
| Version compatibility (Django 5.2, React 19) | MEDIUM | Django 5.2 not explicitly listed in inertia-django PyPI classifier (shows Django 4). React 19 not explicitly documented but package updated Feb 2026. Both likely work, need verification. |
| django-vite integration | HIGH | Multiple community examples, official docs recommend it, confirmed working pattern |
| Configuration patterns | HIGH | Multiple verified sources, official documentation, working examples |
| Migration approach | MEDIUM | Based on community examples, not official migration guide |

## Sources

**Official Documentation:**
- [inertia-django PyPI](https://pypi.org/project/inertia-django/)
- [@inertiajs/react npm](https://www.npmjs.com/package/@inertiajs/react)
- [Inertia.js Client-Side Setup](https://inertiajs.com/docs/v2/installation/client-side-setup)
- [Inertia Django Server-Side Setup](https://inertiajs.github.io/inertia-django/guide/server-side-setup)

**Community Resources:**
- [Building a Modern Web App with Django, Inertia.js, Vite, and React](https://medium.com/@tanzid3/building-a-modern-web-app-with-django-inertia-js-vite-and-react-67979a981649)
- [django-vite-inertia Template](https://github.com/SarthakJariwala/django-vite-inertia)
- [inertia-django-vite-vue-minimal](https://github.com/mujahidfa/inertia-django-vite-vue-minimal)
- [How to setup Django with React using InertiaJS](https://anjanesh.dev/how-to-setup-django-with-react-using-inertiajs)

**Package References:**
- [inertia-django GitHub](https://github.com/inertiajs/inertia-django)
- [@inertiajs/core npm](https://www.npmjs.com/package/@inertiajs/core)
- [Inertia.js Routing Docs](https://inertiajs.com/routing) (explains why React Router not needed)
- [Inertia.js CSRF Protection](https://inertiajs.com/docs/v2/security/csrf-protection)
