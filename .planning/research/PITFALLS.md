# Domain Pitfalls: Django + Inertia.js Migration and Project Consolidation

**Domain:** Refactoring Django+React app from template-rendered JSON to Inertia.js with monorepo consolidation
**Researched:** 2026-02-12
**Confidence:** MEDIUM (verified with official docs and community issues, some LOW confidence areas flagged)

---

## Critical Pitfalls

Mistakes that cause rewrites, major bugs, or production incidents.

### Pitfall 1: CSRF Token Header Mismatch
**What goes wrong:** Django's default CSRF header names don't match Axios (Inertia's HTTP library), causing all POST/PUT/DELETE requests to fail with 403 Forbidden errors.

**Why it happens:** Django expects `X-CSRFToken` header, but Axios sends `X-XSRF-TOKEN` by default. The default configuration leaves this misconfigured.

**Consequences:**
- All form submissions fail silently or with cryptic CSRF errors
- Authentication flows break
- Data mutations impossible without manual workarounds
- Production deployment fails on first user interaction

**Prevention:**
```python
# settings.py - Option 1: Change Django to match Axios
CSRF_HEADER_NAME = 'HTTP_X_XSRF_TOKEN'
CSRF_COOKIE_NAME = 'XSRF-TOKEN'
```

OR

```javascript
// app.jsx - Option 2: Configure Axios to match Django
axios.defaults.xsrfHeaderName = "X-CSRFToken";
axios.defaults.xsrfCookieName = "csrftoken";
```

**Detection:**
- Browser console shows 403 errors on POST requests
- Django logs: "CSRF verification failed. Request aborted."
- Network tab shows missing or incorrect CSRF headers

**Phase:** Phase 1 (Inertia Setup) - Must be configured before any Inertia views work

**Sources:**
- [Inertia.js CSRF Protection](https://inertiajs.com/csrf-protection)
- [django-inertia Issue #8](https://github.com/inertiajs/inertia-django/issues/8)
- [django-inertia Issue #14](https://github.com/inertiajs/inertia-django/issues/14)

---

### Pitfall 2: Axios Version Conflicts
**What goes wrong:** Installing `@inertiajs/react` brings its own Axios version that conflicts with project's existing Axios, causing CSRF tokens to not be sent or version incompatibility errors.

**Why it happens:** Inertia bundles Axios as a dependency, and npm/yarn may install multiple versions causing the wrong instance to handle requests.

**Consequences:**
- CSRF tokens not attached to requests despite correct configuration
- Inconsistent behavior between dev and production
- Middleware not recognizing Inertia requests (missing `X-Inertia` header)

**Prevention:**
```json
// package.json - Force single Axios version
{
  "resolutions": {
    "axios": "^1.6.0"
  },
  "dependencies": {
    "@inertiajs/react": "^1.0.0",
    "axios": "^1.6.0"
  }
}
```

Then run `npm install` or `yarn install` to dedupe.

**Detection:**
- `npm ls axios` shows multiple versions
- CSRF errors despite correct header configuration
- `X-Inertia` header missing from requests

**Phase:** Phase 1 (Inertia Setup) - Check during initial installation

**Sources:**
- [django-inertia Issue #14 Comments](https://github.com/inertiajs/inertia-django/issues/14)
- MEDIUM confidence (community-reported issue, not official docs)

---

### Pitfall 3: Django Admin Routes Breaking After Consolidation
**What goes wrong:** Moving from separate `sgui/` frontend to `scrapegrape/frontend/` and changing URL routing causes Django admin at `/admin/` to stop rendering correctly or serve React app instead.

**Why it happens:**
- Catch-all Inertia routes override admin routes if placed incorrectly in `urls.py`
- Static file paths change, breaking admin CSS/JS
- Middleware applies Inertia logic to admin routes

**Consequences:**
- `/admin/` returns React root div instead of Django admin
- Admin loads but has no styling (CSS 404s)
- Attempting to login redirects to React app

**Prevention:**
```python
# urls.py - Admin MUST come before catch-all Inertia routes
urlpatterns = [
    path('admin/', admin.site.urls),  # FIRST
    # Other specific routes
    path('api/', include('publishers.api_urls')),
    # Inertia catch-all LAST
    path('<path:path>', inertia_view, name='inertia_catchall'),
    path('', inertia_view, name='home'),
]
```

```python
# middleware.py - Exclude admin from InertiaMiddleware
class ConditionalInertiaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/admin/'):
            return self.get_response(request)
        # Apply Inertia logic
        return InertiaMiddleware(self.get_response)(request)
```

**Detection:**
- `/admin/` shows `<div id="app"></div>` instead of admin interface
- Admin CSS returns 404s in network tab
- Admin redirects to React routes

**Phase:** Phase 2 (Frontend Consolidation) - Test admin immediately after URL changes

**Sources:**
- LOW confidence (extrapolated from URL routing best practices, not specifically documented for Inertia)

---

### Pitfall 4: JSON Serialization Failures with Related Models
**What goes wrong:** Django Rest Framework serializers (currently used in views.py) don't work with Inertia's default encoder, causing related models to not serialize or fields to be missing.

**Why it happens:**
- Inertia uses `model_to_dict()` which excludes `editable=False` fields (timestamps, auto-generated)
- `select_related()` and `prefetch_related()` objects don't convert to JSON
- DRF serializers expect `.data` attribute but Inertia expects raw dicts

**Consequences:**
- Missing `created_at`, `updated_at` timestamps in frontend
- Related models return object references instead of data
- Frontend receives incomplete data, causing undefined errors
- N+1 query problems when you add manual serialization workarounds

**Prevention:**

**Option 1: Use Inertia's InertiaMeta (Recommended for new code)**
```python
from inertia import InertiaMeta

class Publisher:
    # ... model fields ...

    class InertiaMeta:
        fields = ['id', 'name', 'url', 'detected_waf', 'created_at']
```

**Option 2: Convert DRF serializers to dicts**
```python
# views.py - Explicitly call .data
def table(request):
    # ... existing logic ...
    serialized = PublisherWithReportsSerializer(result, many=True)

    return render(request, {
        'publishers': serialized.data  # .data returns list of dicts
    })
```

**Option 3: Custom JSON Encoder**
```python
# settings.py
INERTIA = {
    'JSON_ENCODER': 'yourapp.encoders.CustomInertiaEncoder'
}

# encoders.py
from inertia.utils import InertiaJsonEncoder
from rest_framework.serializers import Serializer

class CustomInertiaEncoder(InertiaJsonEncoder):
    def default(self, obj):
        if isinstance(obj, Serializer):
            return obj.data
        return super().default(obj)
```

**Detection:**
- Frontend props missing expected fields
- Console errors: `Cannot read property 'created_at' of undefined`
- Related models show `[object Object]` or object references
- Inertia debug shows incomplete prop data

**Phase:** Phase 1 (Inertia Setup) - Surfaces immediately when migrating from DRF serializers

**Sources:**
- [django-inertia Issue #18](https://github.com/inertiajs/inertia-django/issues/18)
- [inertia-django README](https://github.com/inertiajs/inertia-django/blob/main/README.md)
- [inertia-django PyPI](https://pypi.org/project/inertia-django/)

---

### Pitfall 5: Vite Manifest Path Misalignment After Consolidation
**What goes wrong:** After moving from `sgui/` to `scrapegrape/frontend/`, Vite builds `manifest.json` to new location but Django still looks in old path, causing all assets to 404.

**Why it happens:**
- `django-vite` template tags reference old `DJANGO_VITE_ASSETS_PATH`
- Vite `build.outDir` points to new location
- `STATICFILES_DIRS` not updated to include new frontend dist
- `base` in `vite.config.ts` doesn't match Django's `STATIC_URL`

**Consequences:**
- Production build shows blank page (JS 404s)
- Dev server works but production fails
- Deployment fails silently (no errors, but app doesn't load)
- Browser console: "Failed to load resource: 404" for all JS/CSS

**Prevention:**

**Before consolidation - Current structure:**
```python
# settings.py
STATICFILES_DIRS = [
    BASE_DIR / "sgui" / "dist"
]
```

```typescript
// sgui/vite.config.ts
export default defineConfig({
  build: {
    outDir: "dist",
    manifest: "manifest.json",
  },
  base: "/static/",
})
```

**After consolidation - New structure:**
```python
# settings.py
STATICFILES_DIRS = [
    BASE_DIR / "scrapegrape" / "frontend" / "dist"  # CHANGED
]

DJANGO_VITE_ASSETS_PATH = BASE_DIR / "scrapegrape" / "frontend" / "dist"
```

```typescript
// scrapegrape/frontend/vite.config.ts
export default defineConfig({
  build: {
    outDir: "dist",  # Relative to scrapegrape/frontend/
    manifest: "manifest.json",
  },
  base: "/static/",  # Must match STATIC_URL
})
```

**Detection:**
- `python manage.py collectstatic` succeeds but files in wrong location
- Production shows blank page
- `curl http://localhost:8000/static/manifest.json` returns 404
- Django template `{% vite_asset 'src/main.tsx' %}` renders broken paths

**Phase:** Phase 2 (Frontend Consolidation) - Test build process before deployment

**Sources:**
- [django-vite PyPI](https://pypi.org/project/django-vite/)
- [django-vite Issue #161](https://github.com/MrBin99/django-vite/issues/161)
- [Using Vite with Django Gist](https://gist.github.com/lucianoratamero/7fc9737d24229ea9219f0987272896a2)

---

### Pitfall 6: Template Migration Leaves Zombie {% load %} Tags
**What goes wrong:** Migrating from `base.html` with `{% load django_vite %}` to Inertia root template, but forgetting to remove django-vite tags while adding Inertia tags causes asset duplication or load failures.

**Why it happens:**
- `base.html` currently has `{% vite_hmr_client %}`, `{% vite_react_refresh %}`, `{% vite_asset 'src/main.tsx' %}`
- Inertia requires different template structure with `{{ inertia }}` placeholder
- Old tags attempt to load React twice, causing hydration errors

**Consequences:**
- React renders twice (once from Vite, once from Inertia)
- Hydration mismatches: "Hydration failed because the initial UI does not match"
- Asset loaded twice, doubling bundle size
- State management breaks (two React instances)

**Prevention:**

**Before (current base.html):**
```django
{% load django_vite %}
<body>
    <div id="root"></div>
    {% block extra_body %}{% endblock %}

    {% vite_hmr_client %}
    {% vite_react_refresh %}
    {% vite_asset 'src/main.tsx' %}
</body>
```

**After (Inertia base.html):**
```django
{# NO django_vite tags! #}
<body>
    {{ inertia }}  {# Inertia handles all asset loading #}
</body>
```

**Note:** Remove `{% load django_vite %}` from template AND `django-vite` from `INSTALLED_APPS` once fully migrated.

**Detection:**
- Browser console: "Warning: Expected server HTML to contain a matching <div> in <div>"
- React DevTools shows two root instances
- Network tab shows duplicate JS bundle requests
- Hydration errors in console

**Phase:** Phase 1 (Inertia Setup) - During initial template conversion

**Sources:**
- LOW confidence (extrapolated from React hydration best practices and Inertia template requirements)

---

## Moderate Pitfalls

Cause bugs or performance issues, but recoverable.

### Pitfall 7: Partial Reload Performance Traps
**What goes wrong:** All props execute on the server even during partial reloads, causing expensive queries to run unnecessarily.

**Why it happens:** Inertia evaluates all props server-side before filtering to requested fields, unless you use lazy evaluation.

**Consequences:**
- Partial reload of one field still runs all 3 subqueries (WAF, discovery, evaluation)
- Slow response times (200ms becomes 1s+ on large datasets)
- Database connection pool exhaustion under load
- Frontend feels sluggish despite partial reload optimization

**Prevention:**
```python
# views.py - Wrap expensive queries in lambdas
def table(request):
    publishers = Publisher.objects.all()

    return render(request, 'index', {
        'publishers': publishers,
        # Lazy evaluation - only runs when requested
        'waf_reports': lambda: get_waf_reports(publishers),
        'discovery_results': lambda: get_discovery_results(publishers),
        'evaluation_results': lambda: get_evaluation_results(publishers),
    })
```

Frontend requests specific prop:
```javascript
router.reload({ only: ['waf_reports'] })  // Others not evaluated
```

**Detection:**
- Django Debug Toolbar shows all queries running on partial reload
- Slow response times for partial reloads
- Database query logs show unnecessary queries

**Phase:** Phase 3 (Optimization) - After basic functionality works

**Sources:**
- [Inertia.js Partial Reloads](https://inertiajs.com/partial-reloads)
- [Partial Reloads Documentation](https://inertiajs.com/docs/v2/data-props/partial-reloads)

---

### Pitfall 8: Shared Data Not Available on Initial Load
**What goes wrong:** Using Inertia's `share()` middleware for user authentication or CSRF tokens, but data is missing on first page load.

**Why it happens:**
- Shared data middleware runs after InertiaMiddleware in `MIDDLEWARE` stack
- Initial render doesn't trigger middleware in correct order
- CSRF token generated but not passed to frontend

**Consequences:**
- User prop is `null` on first page load, then appears on navigation
- CSRF token missing, first form submission fails
- Flash messages don't display
- Inconsistent behavior (works on reload, not initial visit)

**Prevention:**
```python
# settings.py - InertiaMiddleware MUST be last (or near-last)
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'yourapp.middleware.InertiaShareMiddleware',  # Custom share middleware
    'inertia.middleware.InertiaMiddleware',  # LAST (or before whitenoise)
]

# middleware.py - Share common data
from inertia import share

class InertiaShareMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        share(request,
            user=lambda: request.user.username if request.user.is_authenticated else None,
            csrf_token=lambda: request.META.get('CSRF_COOKIE'),
        )
        return self.get_response(request)
```

**Detection:**
- Props are `undefined` on initial load, defined after navigation
- First form submission fails, subsequent work
- Browser network tab shows shared props missing in initial response

**Phase:** Phase 1 (Inertia Setup) - When adding authentication or shared state

**Sources:**
- [inertia-django PyPI](https://pypi.org/project/inertia-django/)
- [Inertia Django README](https://github.com/inertiajs/inertia-django/blob/main/README.md)
- MEDIUM confidence

---

### Pitfall 9: Development Server CORS Issues After Consolidation
**What goes wrong:** Moving frontend from standalone `sgui/` dev server (port 5173) to `scrapegrape/frontend/` breaks HMR (Hot Module Reload) with CORS errors.

**Why it happens:**
- Vite dev server runs on `localhost:5173`, Django on `localhost:8000`
- Browser blocks HMR WebSocket connection
- `django-vite` expects dev server at specific URL

**Consequences:**
- HMR doesn't work (requires full page refresh)
- Dev experience degrades significantly
- CORS errors in console: "Access to XMLHttpRequest at 'http://localhost:5173' blocked"
- Vite overlay doesn't show errors

**Prevention:**
```typescript
// vite.config.ts
export default defineConfig({
  server: {
    host: '0.0.0.0',
    port: 5173,
    cors: true,  // Allow cross-origin requests
    strictPort: true,
  },
})
```

```python
# settings.py
DJANGO_VITE_DEV_MODE = DEBUG
DJANGO_VITE_DEV_SERVER_HOST = 'localhost'
DJANGO_VITE_DEV_SERVER_PORT = 5173
```

**Detection:**
- Changes to React components don't auto-reload
- Console: "WebSocket connection failed"
- `django-vite` tries to connect to wrong URL
- HMR overlay not appearing

**Phase:** Phase 2 (Frontend Consolidation) - Test dev server immediately after moving files

**Sources:**
- [django-vite GitHub](https://github.com/MrBin99/django-vite)
- LOW confidence (standard Vite+Django setup, not Inertia-specific)

---

### Pitfall 10: Asset Version Mismatch Causes Infinite Reloads
**What goes wrong:** Inertia's version checking triggers full page reload on every request, causing infinite reload loop.

**Why it happens:**
- `INERTIA_VERSION` changes on every request (e.g., using timestamp)
- Manifest hash changes but version not updated
- Deployment pushes new assets but backend still reports old version

**Consequences:**
- Browser stuck in reload loop
- Users can't access application
- "This page isn't working" errors
- High server load from reload requests

**Prevention:**
```python
# settings.py - Use manifest hash for versioning
import json
from pathlib import Path

def get_inertia_version():
    manifest_path = BASE_DIR / 'scrapegrape' / 'frontend' / 'dist' / 'manifest.json'
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)
            # Use manifest file hash or specific entry
            return manifest.get('src/main.tsx', {}).get('file', 'v1')
    return 'dev'  # Development fallback

INERTIA = {
    'VERSION': get_inertia_version(),  # Static per deployment
    # OR
    'VERSION': '1.0.0',  # Manual version bump
}
```

**Detection:**
- Browser console shows repeated page loads
- Network tab shows request → 409 → reload → request cycle
- Django logs show constant Inertia version mismatch warnings

**Phase:** Phase 4 (Production Deployment) - Test before deploying to production

**Sources:**
- [Inertia.js Upgrade Guide](https://inertiajs.com/upgrade-guide)
- MEDIUM confidence

---

## Minor Pitfalls

Annoying but easy to fix.

### Pitfall 11: TypeScript Path Aliases Break After Move
**What goes wrong:** Moving from `sgui/src/` to `scrapegrape/frontend/src/` breaks `@/` imports in React components.

**Why it happens:** `tsconfig.json` has `"@": "./src"` which is now at different relative path.

**Consequences:**
- TypeScript errors: "Cannot find module '@/components/Table'"
- Build fails with unresolved imports
- IDE auto-import inserts wrong paths

**Prevention:**
```json
// scrapegrape/frontend/tsconfig.json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]  // Verify this resolves correctly
    }
  }
}
```

```typescript
// vite.config.ts - Ensure alias matches
import path from 'path'

export default defineConfig({
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
```

**Detection:**
- Build errors: "Cannot resolve '@/components/...'"
- IDE shows red squiggles on `@/` imports

**Phase:** Phase 2 (Frontend Consolidation) - Immediately when moving files

**Sources:**
- Standard TypeScript/Vite configuration issue

---

### Pitfall 12: Forgetting to Remove json_script Template Filter
**What goes wrong:** Current implementation uses `{{ serialized|json_script:"publisher-data" }}` which leaves `<script id="publisher-data">` in DOM that React tries to parse.

**Why it happens:** Old pattern embeds JSON in template, new pattern passes via Inertia props, but old code remains.

**Consequences:**
- Data duplicated (in DOM script tag AND Inertia props)
- React might parse wrong data source
- Security: sensitive data exposed in HTML
- Larger page size (data serialized twice)

**Prevention:**
```django
{# OLD - Remove this #}
{% block extra_body %}
    {{ serialized|json_script:"publisher-data" }}
{% endblock extra_body %}

{# NEW - Inertia handles data passing #}
{# No extra_body block needed #}
```

```python
# views.py - Pass data via Inertia props, not context
def table(request):
    # OLD
    # return render(request, 'index.html', {'serialized': data})

    # NEW
    return render(request, 'index', {
        'publishers': data  # Available as props.publishers in React
    })
```

**Detection:**
- View source shows `<script id="publisher-data" type="application/json">`
- React DevTools shows props AND window.__INITIAL_STATE__ or similar
- Data visible in HTML source (security concern)

**Phase:** Phase 1 (Inertia Setup) - When converting first view

**Sources:**
- Current codebase pattern

---

### Pitfall 13: Missing Root Element After Template Change
**What goes wrong:** Inertia expects `<div id="app">` but current template has `<div id="root">`, causing "Target container is not a DOM element" error.

**Why it happens:** React traditionally uses `id="root"`, Inertia defaults to `id="app"` (configurable).

**Consequences:**
- Blank page
- Console error: "Application root element not found"
- Inertia can't mount React

**Prevention:**

**Option 1: Change template to match Inertia default**
```django
{# base.html #}
<body>
    <div id="app" data-page="{{ inertia }}"></div>
</body>
```

**Option 2: Configure Inertia to use existing root**
```javascript
// app.jsx
createInertiaApp({
  resolve: name => import(`./Pages/${name}.tsx`),
  setup({ el, App, props }) {
    createRoot(el).render(<App {...props} />)
  },
  id: 'root',  // Match existing template
})
```

**Detection:**
- Blank page after Inertia setup
- Console: "Target container is not a DOM element"

**Phase:** Phase 1 (Inertia Setup) - During initial app.jsx setup

**Sources:**
- Inertia.js documentation

---

### Pitfall 14: Docker Volume Mounts Don't Include New Frontend Path
**What goes wrong:** `docker-compose.yml` mounts `./sgui/` but not `./scrapegrape/frontend/`, breaking dev server in Docker.

**Why it happens:** Volume mounts not updated after consolidation.

**Consequences:**
- Docker dev server doesn't see frontend code changes
- HMR doesn't work in Docker
- Build fails due to missing files

**Prevention:**
```yaml
# docker-compose.yml - Update volume mounts
services:
  web:
    volumes:
      - ./scrapegrape:/app/scrapegrape  # Changed from ./sgui
      # OR more specific
      - ./scrapegrape/frontend:/app/scrapegrape/frontend
```

**Detection:**
- Changes to frontend don't reflect in Docker container
- `docker exec` into container shows old directory structure
- Build works locally, fails in Docker

**Phase:** Phase 2 (Frontend Consolidation) - Test Docker immediately after file moves

**Sources:**
- Standard Docker practices

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| **Phase 1: Inertia Setup** | CSRF header mismatch (Critical #1) | Configure CSRF settings before first Inertia view |
| **Phase 1: Inertia Setup** | Axios version conflict (Critical #2) | Check `npm ls axios` immediately after install |
| **Phase 1: Inertia Setup** | DRF serializer incompatibility (Critical #4) | Test serialization with simple view before migrating complex data |
| **Phase 2: Frontend Consolidation** | Vite manifest path misalignment (Critical #5) | Run production build test before committing path changes |
| **Phase 2: Frontend Consolidation** | Django admin routes breaking (Critical #3) | Test `/admin/` immediately after URL routing changes |
| **Phase 2: Frontend Consolidation** | TypeScript path aliases (Minor #11) | Run `npm run build` to catch import errors early |
| **Phase 3: Data Migration** | N+1 queries from manual serialization | Use Django Debug Toolbar to monitor query counts |
| **Phase 4: Production Deployment** | WhiteNoise cache-control misconfiguration | Test static file caching with production settings locally |
| **Phase 4: Production Deployment** | Asset version mismatch reload loop (Moderate #10) | Verify version stays constant across requests before deployment |

---

## Deployment-Specific Gotchas

### SSR Considerations
**Current status:** Not using SSR
**Future considerations:** If SSR added later:
- Requires separate Node.js server process (supervisor/pm2)
- `INERTIA_SSR_URL` must be accessible from Django server
- Build process must generate both client and server bundles
- SSR server must be restarted on deployments

**Recommendation:** Defer SSR until performance metrics show need (LOW confidence - no current requirement)

**Sources:**
- [Inertia.js SSR Documentation](https://inertiajs.com/server-side-rendering)
- [Server-Side Rendering Django](https://inertiajs.com/docs/v2/advanced/server-side-rendering)

---

### Monorepo Deployment Coordination
**Risk:** Coupling frontend and backend deployments

**Scenario:**
1. Backend changes pushed (Django migration)
2. Frontend not rebuilt
3. Old JS bundle expects old API response shape
4. Production errors

**Prevention:**
- Always build frontend before deploying backend
- Use atomic deployments (both or neither)
- Version API responses if breaking changes needed
- Consider blue-green deployment for zero-downtime

**Sources:**
- [Monorepos with Django and React](https://www.vintasoftware.com/blog/django-react-monorepo)
- [Frontend Backend Sync with Monorepo](https://www.highlight.io/blog/keeping-your-frontend-and-backend-in-sync-with-a-monorepo)

---

## Testing Strategy to Catch Pitfalls Early

### Phase 1 (Inertia Setup) Checklist
- [ ] POST request succeeds without CSRF errors
- [ ] `npm ls axios` shows single version
- [ ] Serialized data appears correctly in React DevTools props
- [ ] `/admin/` still loads correctly
- [ ] No duplicate React renders (check DevTools)

### Phase 2 (Frontend Consolidation) Checklist
- [ ] `npm run build` succeeds without path errors
- [ ] `python manage.py collectstatic` collects to correct location
- [ ] Dev server HMR works (make change, see instant update)
- [ ] `/static/manifest.json` accessible
- [ ] Docker build includes new paths

### Phase 3 (Optimization) Checklist
- [ ] Django Debug Toolbar shows expected query count
- [ ] Partial reload only fetches requested props
- [ ] Shared middleware provides user/CSRF on first load

### Phase 4 (Production) Checklist
- [ ] Asset version stays constant across requests
- [ ] Static files have correct cache headers
- [ ] Full deployment test (build → migrate → deploy)
- [ ] Rollback plan tested

---

## Sources Summary

**HIGH Confidence:**
- [Inertia.js Official Documentation](https://inertiajs.com/)
- [django-inertia GitHub Repository](https://github.com/inertiajs/inertia-django)
- [django-inertia PyPI](https://pypi.org/project/inertia-django/)
- [Django Official Documentation](https://docs.djangoproject.com/)

**MEDIUM Confidence:**
- [Building Modern Web App with Django, Inertia.js, Vite, and React](https://medium.com/@tanzid3/building-a-modern-web-app-with-django-inertia-js-vite-and-react-67979a981649)
- [Monorepos with Django and React](https://www.vintasoftware.com/blog/django-react-monorepo)
- [django-vite PyPI](https://pypi.org/project/django-vite/)
- Community GitHub Issues

**LOW Confidence (needs validation):**
- Admin route configuration (extrapolated from Django best practices)
- Template tag removal side effects (based on React hydration patterns)
- Docker-specific issues (standard Docker practices, not Inertia-specific)

---

## Research Gaps

Areas where additional research may be needed during implementation:

1. **SSR Setup:** If performance requires server-side rendering, need deeper research on Node.js process management in production
2. **WhiteNoise Configuration:** Specific immutable file patterns for Vite-generated hashes need verification
3. **django-tasks Integration:** How Inertia views interact with async task queue not researched
4. **Large Dataset Pagination:** Current research doesn't cover pagination with Inertia (may need phase-specific research)
5. **WebSocket/Real-time Updates:** If task status updates needed, Inertia polling vs WebSocket integration needs research

**Recommendation:** Address these gaps when specific phases require them, not upfront.
