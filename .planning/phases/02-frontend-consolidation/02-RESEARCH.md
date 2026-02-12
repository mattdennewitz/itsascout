# Phase 2: Frontend Consolidation - Research

**Researched:** 2026-02-12
**Domain:** Vite build pipeline with Django integration, directory structure consolidation
**Confidence:** HIGH

## Summary

Phase 2 moves the React frontend from the standalone `sgui/` directory into `scrapegrape/frontend/` to consolidate the project structure. This involves updating Vite's configuration to work from the new location, reconfiguring django-vite to serve assets from the new build output path, and ensuring both development HMR and production builds continue to work seamlessly.

The core technical challenge is coordinating path updates across three systems: Vite's build configuration (outDir, root), django-vite's asset loading (manifest_path, dev_server settings), and the Inertia page resolution glob pattern. Since Phase 1 already established working Inertia infrastructure with a dual-path entry point, Phase 2's changes are purely structural—no runtime behavior changes, just different file locations.

**Primary recommendation:** Update paths in a specific order (Vite config → Django settings → import.meta.glob), use relative paths in Vite config, absolute paths in Django settings, and verify HMR reconnects correctly after the move. Test both development and production modes before committing.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Vite | 7.0.4 (existing) | Build tool and dev server | Already configured, handles HMR and production builds |
| django-vite | 3.1.0 (existing) | Django/Vite integration | Already configured, manages dev/prod asset serving |
| @inertiajs/react | 2.3.14 (existing) | Inertia client adapter | Already installed in Phase 1 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| React | 19.1.0 (existing) | Component framework | Already configured with TypeScript |
| Tailwind CSS | 4.1.11 (existing) | Styling framework | Already configured with @tailwindcss/vite |

### No New Dependencies Required

This phase only reorganizes existing code—no new libraries needed.

**Installation:**
```bash
# No installation needed
```

## Architecture Patterns

### Recommended Project Structure

```
scrapegrape/                      # Django project root
├── scrapegrape/
│   └── settings.py              # Update DJANGO_VITE manifest_path
├── templates/
│   └── base.html                # No changes (still references src/main.tsx)
├── frontend/                    # NEW: Consolidated frontend (moved from sgui/)
│   ├── src/
│   │   ├── main.tsx            # Update import.meta.glob path if needed
│   │   ├── Pages/              # Inertia page components
│   │   │   ├── Debug/
│   │   │   │   └── InertiaTest.tsx
│   │   │   └── (future pages)
│   │   ├── Components/         # NEW: Shared UI components
│   │   ├── Layouts/            # NEW: Page layouts
│   │   ├── components/         # Existing shadcn components
│   │   ├── datatable/          # Existing datatable components
│   │   ├── lib/                # Existing utilities
│   │   ├── App.tsx             # Legacy app (Phase 1 coexistence)
│   │   └── index.css           # Global styles
│   ├── dist/                   # Build output (generated)
│   │   ├── manifest.json       # NEW: Build manifest for Django
│   │   └── assets/             # Hashed JS/CSS files
│   ├── vite.config.ts          # Update paths: no root change needed
│   ├── package.json            # No changes
│   └── tsconfig.json           # No changes
└── (sgui/ directory removed after migration)
```

### Pattern 1: Vite Configuration for Nested Directory

**What:** Configure Vite to work from `scrapegrape/frontend/` instead of `sgui/`
**When to use:** Required for Phase 2 consolidation
**Example:**
```typescript
// scrapegrape/frontend/vite.config.ts
// Source: https://vite.dev/config/build-options

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
  base: "/static/",  // Matches STATIC_URL
  build: {
    manifest: true,  // CRITICAL: Generate manifest.json for django-vite
    outDir: "dist",  // Relative to vite.config.ts location
    rollupOptions: {
      input: "src/main.tsx",  // Relative to vite.config.ts location
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    cors: true,
  },
})
```

**Key changes from current config:**
- Add `manifest: true` to generate manifest.json for production
- `outDir` stays `"dist"` (relative to config file, now creates `scrapegrape/frontend/dist/`)
- `base: "/static/"` matches Django's STATIC_URL setting

### Pattern 2: Django-Vite Path Configuration

**What:** Update django-vite settings to reference new frontend location
**When to use:** Required whenever frontend directory moves
**Example:**
```python
# scrapegrape/scrapegrape/settings.py
# Source: https://github.com/MrBin99/django-vite/blob/master/README.md

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Django Vite configuration
DJANGO_VITE = {
    "default": {
        "dev_mode": DEBUG,
        "manifest_path": BASE_DIR / "frontend" / "dist" / "manifest.json",
        # Optional: Explicitly set dev server URL if different
        # "dev_server_protocol": "http",
        # "dev_server_host": "localhost",
        # "dev_server_port": 5173,
    }
}
```

**Key changes from current config:**
- `manifest_path` changes from `BASE_DIR.parent / "sgui" / "dist" / "manifest.json"` to `BASE_DIR / "frontend" / "dist" / "manifest.json"`
- Dev server settings remain the same (5173 is Vite default)

### Pattern 3: Inertia Page Resolution After Move

**What:** import.meta.glob path stays the same (relative to main.tsx)
**When to use:** Only update if src/ directory structure changes
**Example:**
```typescript
// scrapegrape/frontend/src/main.tsx
// No changes needed to glob pattern

createInertiaApp({
    resolve: name => {
        const pages = import.meta.glob('./Pages/**/*.tsx', { eager: true })
        const page = pages[`./Pages/${name}.tsx`]
        if (!page) {
            throw new Error(
                `Page not found: ${name}. Available: ${Object.keys(pages).join(', ')}`
            )
        }
        return page
    },
    setup({ el, App, props }) {
        createRoot(el).render(<App {...props} />)
    },
})
```

**Why no changes:** Glob pattern is relative to `main.tsx` location, which doesn't move relative to `Pages/` directory.

### Pattern 4: Directory Structure for Inertia Pages/Components/Layouts

**What:** Organize frontend code by type and scope
**When to use:** Phase 2 establishes this structure for Phase 3+ to use
**Recommended structure:**
```
frontend/src/
├── Pages/              # Inertia page components (export default only)
│   ├── Debug/
│   │   └── InertiaTest.tsx
│   ├── Publishers/     # Example: future pages
│   │   ├── Index.tsx
│   │   └── Show.tsx
│   └── (mirrors URL structure)
├── Components/         # Shared components (named exports)
│   ├── ui/            # Generic UI components
│   ├── forms/         # Form components
│   └── (domain components)
├── Layouts/           # Page layouts (named exports)
│   ├── AppLayout.tsx  # Main app layout
│   └── AuthLayout.tsx # Auth pages layout
├── components/        # Existing shadcn components (keep as-is)
├── datatable/         # Existing datatable (keep as-is)
├── lib/               # Existing utilities (keep as-is)
├── App.tsx            # Legacy app (Phase 1 coexistence, remove in Phase 5)
├── main.tsx           # Entry point
└── index.css          # Global styles
```

**Naming conventions (from Spatie best practices):**
- **Page components:** PascalCase, suffix with "Page" (e.g., `PublishersIndexPage.tsx`)
- **Shared components:** PascalCase, named exports (e.g., `Button.tsx`)
- **Layouts:** PascalCase, suffix with "Layout" (e.g., `AppLayout.tsx`)
- **Files (non-components):** camelCase (e.g., `formatDate.ts`)
- **Directories:** kebab-case (e.g., `user-settings/`)

### Anti-Patterns to Avoid

- **Don't move vite.config.ts location without updating paths:** Vite resolves paths relative to config file location—if you move the config, update all relative paths
- **Don't use absolute paths in Vite config:** Use relative paths for `outDir`, `input`, etc. so the config is portable
- **Don't forget build.manifest: true:** Without this, Vite won't generate manifest.json and django-vite can't serve production assets
- **Don't mix path separators:** Use forward slashes in glob patterns (`./Pages/**/*.tsx`), not backslashes
- **Don't create barrel files (index.ts):** Export components directly—barrel files create indirection and slow HMR

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Path resolution | Custom path mapping logic | Vite's `resolve.alias` and `path.resolve(__dirname, ...)` | Vite optimizes at build time, handles symlinks correctly |
| Manifest parsing | Custom manifest reader | django-vite's DjangoViteAppClient | Handles dev/prod switching, asset dependencies, hashing |
| HMR client injection | Manual script tags | django-vite's `{% vite_hmr_client %}` | Handles WebSocket URL, protocol, reconnection logic |
| Page component loading | Custom dynamic imports | import.meta.glob with eager: true | Vite optimizes at build time, provides better error messages |
| Static file serving | Custom Django views | django.contrib.staticfiles + WhiteNoise (if needed) | Handles cache headers, compression, immutable file detection |

**Key insight:** Vite and django-vite have tight integration that breaks when you try to replace parts of the pipeline. For example, manually parsing manifest.json misses critical fields like `css` dependencies and `imports` chains—django-vite handles these correctly.

## Common Pitfalls

### Pitfall 1: Manifest Path Mismatch Between Vite and Django

**What goes wrong:** Production build completes but Django can't find manifest.json, resulting in missing CSS/JS assets

**Why it happens:** Vite generates manifest at `<outDir>/manifest.json` (by default `.vite/manifest.json` if `manifest: true`, or `manifest.json` if `manifest: "manifest.json"`). Django looks for it at `manifest_path` setting. If these don't align, production assets fail to load.

**How to avoid:**
```typescript
// vite.config.ts
build: {
  manifest: true,  // Creates .vite/manifest.json
  outDir: "dist",
}

// settings.py
DJANGO_VITE = {
    "default": {
        "manifest_path": BASE_DIR / "frontend" / "dist" / ".vite" / "manifest.json",
    }
}
```

**CORRECTION:** Setting `manifest: true` creates `.vite/manifest.json`, BUT for django-vite compatibility, use `manifest: "manifest.json"` to create it at the root of outDir.

**Recommended configuration:**
```typescript
// vite.config.ts
build: {
  manifest: "manifest.json",  // Creates dist/manifest.json (not .vite/)
  outDir: "dist",
}

// settings.py
DJANGO_VITE = {
    "default": {
        "manifest_path": BASE_DIR / "frontend" / "dist" / "manifest.json",
    }
}
```

**Warning signs:**
- `python manage.py runserver` works but production build shows unstyled pages
- Console error: "Failed to load resource: manifest.json"
- Django error: "FileNotFoundError: manifest.json"

### Pitfall 2: HMR WebSocket Connection Fails After Directory Move

**What goes wrong:** Development server starts but changes to React components don't trigger browser updates—full page reload required

**Why it happens:** Vite's HMR client connects via WebSocket to the dev server. If the dev server host/port changes or CORS isn't configured, the WebSocket handshake fails and HMR breaks.

**How to avoid:**
```typescript
// vite.config.ts
server: {
  host: "0.0.0.0",  // Listen on all interfaces (Docker requirement)
  port: 5173,        // Must match django-vite dev_server_port
  cors: true,        // Allow Django domain to connect
}
```

```python
# settings.py
DJANGO_VITE = {
    "default": {
        "dev_server_host": "localhost",  # Where Django connects to Vite
        "dev_server_port": 5173,         # Must match Vite server.port
    }
}
```

**Docker-specific consideration:** If running in Docker, `host: "0.0.0.0"` is required so the server binds to all interfaces, not just localhost.

**Warning signs:**
- Browser console: "[vite] connecting..."
- Browser console: "[vite] failed to connect"
- Changes require manual refresh instead of HMR update

### Pitfall 3: Import Paths Break After Directory Move

**What goes wrong:** TypeScript errors like "Cannot find module '@/components/Button'" even though the file exists

**Why it happens:** The `@` alias is configured in `vite.config.ts` using `path.resolve(__dirname, "./src")`. When you move the config file, `__dirname` changes, and the alias breaks if the path isn't updated.

**How to avoid:**
```typescript
// vite.config.ts (after move to scrapegrape/frontend/)
import path from "path"

export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),  // Still correct: relative to config file
    },
  },
})
```

**Why this works:** `__dirname` is always the directory containing `vite.config.ts`, so `./src` is always relative to the config file location, regardless of where the file is moved.

**Additional step:** Update `tsconfig.json` baseUrl/paths if they exist:
```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]  // Relative to tsconfig.json location
    }
  }
}
```

**Warning signs:**
- TypeScript errors in IDE but file exists at the path
- Build fails with "Cannot resolve '@/...' from ..."
- Imports work in some files but not others

### Pitfall 4: Static Files Not Served After collectstatic

**What goes wrong:** `python manage.py collectstatic` runs successfully, but browser shows 404 for CSS/JS assets in production

**Why it happens:** Django's `collectstatic` only copies files from `STATICFILES_DIRS` and app `static/` directories. Vite's build output isn't automatically included unless configured.

**How to avoid:**
```python
# settings.py
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR.parent / "staticfiles"  # Where collectstatic outputs

# Include Vite's build output in static files collection
STATICFILES_DIRS = [
    BASE_DIR / "frontend" / "dist",
]
```

**Production workflow:**
```bash
# 1. Build frontend assets
cd scrapegrape/frontend
npm run build  # Creates frontend/dist/

# 2. Collect all static files
cd ../..
python manage.py collectstatic --noinput

# 3. Serve with Gunicorn + WhiteNoise (or Nginx)
gunicorn scrapegrape.wsgi:application
```

**WhiteNoise configuration (recommended):**
```python
# settings.py
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Must be after SecurityMiddleware
    # ... other middleware
]

# Optimize WhiteNoise for Vite's hashed filenames
WHITENOISE_IMMUTABLE_FILE_TEST = lambda path, url: (
    # Match Vite's hash pattern: [name].[hash].[ext]
    import re
    re.match(r"^.+[.-][0-9a-zA-Z_-]{8,12}\..+$", url)
)
```

**Warning signs:**
- `collectstatic` completes with 0 files copied from frontend
- Browser console: "Failed to load resource: 404 (Not Found)" for main.tsx
- Static admin files load correctly, but Vite assets don't

### Pitfall 5: import.meta.glob Doesn't Find Pages After Move

**What goes wrong:** Inertia page renders blank, console error: "Page not found: Debug/InertiaTest"

**Why it happens:** `import.meta.glob` uses static analysis—the pattern is locked at build time. If the pattern is wrong or uses dynamic variables, Vite can't resolve it.

**How to avoid:**
```typescript
// CORRECT: Static literal pattern
const pages = import.meta.glob('./Pages/**/*.tsx', { eager: true })

// WRONG: Dynamic pattern (Vite error: "Could only use literals")
const baseDir = './Pages'
const pages = import.meta.glob(`${baseDir}/**/*.tsx`, { eager: true })

// WRONG: Absolute path (won't match after move)
const pages = import.meta.glob('/Users/matt/src/itsascout/sgui/src/Pages/**/*.tsx', { eager: true })
```

**Verification after move:**
```typescript
// Add debug logging in development
resolve: name => {
    const pages = import.meta.glob('./Pages/**/*.tsx', { eager: true })
    console.log('Available pages:', Object.keys(pages))  // Check what Vite found
    const page = pages[`./Pages/${name}.tsx`]
    if (!page) {
        throw new Error(
            `Page not found: ${name}. Available: ${Object.keys(pages).join(', ')}`
        )
    }
    return page
}
```

**Warning signs:**
- Console error: "Page not found: Debug/InertiaTest"
- Error message shows "Available: []" (empty array)
- Page worked before directory move, broke after

### Pitfall 6: Django Admin Loses Styling (Route Conflict)

**What goes wrong:** Navigating to `/admin/` shows Django admin but without CSS styling—just plain HTML

**Why it happens:** If Inertia or static file serving is misconfigured, requests to `/admin/` might bypass Django's static file handling, or admin static files might not be collected.

**How to avoid:**
```python
# urls.py (ensure admin routes come BEFORE any catch-all patterns)
from django.contrib import admin
from django.urls import path

urlpatterns = [
    path('admin/', admin.site.urls),  # MUST come first
    path('_debug/inertia/', inertia_smoke_test, name='debug-inertia'),
    # ... other explicit routes
    # NO catch-all patterns like path('', TemplateView.as_view(...)) that would intercept /admin/
]

# settings.py (ensure admin static files are collected)
INSTALLED_APPS = [
    'django.contrib.admin',  # Provides admin static files
    'django.contrib.staticfiles',  # Handles static file collection
    # ...
]

# Ensure collectstatic includes admin files
python manage.py collectstatic  # Should show "Copying '...' from django/contrib/admin/static/"
```

**Verification:**
```bash
# Check that admin static files exist
ls staticfiles/admin/css/base.css  # Should exist after collectstatic
```

**Warning signs:**
- `/admin/` loads but shows unstyled HTML (Times New Roman font)
- Browser console: "Failed to load resource: /static/admin/css/base.css"
- Other Django pages load correctly, only admin is broken

## Code Examples

Verified patterns from official sources:

### Complete Vite Config for Consolidated Frontend

```typescript
// scrapegrape/frontend/vite.config.ts
// Source: https://vite.dev/config/build-options, https://vite.dev/guide/backend-integration

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
  base: "/static/",  // Matches Django STATIC_URL
  build: {
    manifest: "manifest.json",  // Generate manifest.json at dist root
    outDir: "dist",             // Output to frontend/dist/
    rollupOptions: {
      input: "src/main.tsx",    // Entry point
    },
  },
  server: {
    host: "0.0.0.0",  // Docker compatibility
    port: 5173,
    cors: true,       // Allow Django domain
  },
})
```

### Complete Django-Vite Settings

```python
# scrapegrape/scrapegrape/settings.py
# Source: https://github.com/MrBin99/django-vite/blob/master/README.md

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Static files configuration
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR.parent / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "frontend" / "dist",  # Include Vite build output
]

# Django Vite configuration
DJANGO_VITE = {
    "default": {
        "dev_mode": DEBUG,
        "manifest_path": BASE_DIR / "frontend" / "dist" / "manifest.json",
        "dev_server_protocol": "http",
        "dev_server_host": "localhost",
        "dev_server_port": 5173,
    }
}

# WhiteNoise configuration (optional, for production static file serving)
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Add after SecurityMiddleware
    # ... other middleware
]

# Optimize WhiteNoise for Vite's hashed filenames
WHITENOISE_IMMUTABLE_FILE_TEST = lambda path, url: (
    import re
    re.match(r"^.+[.-][0-9a-zA-Z_-]{8,12}\..+$", url)
)
```

### Directory Move Checklist

```bash
# Step 1: Move frontend directory
cd /Users/matt/src/itsascout
mv sgui scrapegrape/frontend

# Step 2: Update Vite config (add manifest: "manifest.json" if not present)
cd scrapegrape/frontend
# Edit vite.config.ts: ensure build.manifest is set

# Step 3: Update Django settings
cd ../scrapegrape
# Edit settings.py: update manifest_path to BASE_DIR / "frontend" / "dist" / "manifest.json"

# Step 4: Update package.json scripts if needed
cd ../frontend
# Verify scripts still work from new location

# Step 5: Test development mode
npm run dev  # Should start on :5173
# In another terminal:
cd ../..
python manage.py runserver  # Visit /_debug/inertia/ and verify HMR works

# Step 6: Test production mode
npm run build  # Should create dist/manifest.json
python manage.py collectstatic --noinput  # Should collect Vite assets
# Temporarily set DEBUG=False and verify /_debug/inertia/ loads with hashed assets

# Step 7: Verify Django admin
# Visit /admin/ and verify styling loads correctly
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Separate frontend repo | Monorepo with frontend/ | 2020+ | Easier deployment, single source of truth, shared types |
| Webpack | Vite | 2020+ | 10-100x faster dev server, simpler config, better HMR |
| Manual manifest parsing | django-vite | 2021+ | Handles CSS dependencies, legacy polyfills, dev/prod switching |
| npm link for shared code | Workspace monorepo | 2018+ | No symlink issues, faster installs, single lockfile |
| build.manifest: true | build.manifest: "manifest.json" | N/A | Control manifest location for backend integration |

**Deprecated/outdated:**
- `build.manifest: true` generates `.vite/manifest.json` (works but requires updating Django path)
- Serving Vite dev server on different domain than Django (CORS issues, complicates deployment)
- Separate `vite build --watch` process (unnecessary—django-vite handles dev/prod switching)

## Open Questions

1. **Docker Volume Mounting After Directory Move**
   - What we know: Current setup mounts `sgui/` as a volume in docker-compose.yml
   - What's unclear: Does the mount path need updating to `scrapegrape/frontend/`?
   - Recommendation: Check docker-compose.yml, update volume mounts if they reference sgui/, verify `npm run dev` works inside container after move

2. **TypeScript Config Path Resolution**
   - What we know: `tsconfig.json` has `baseUrl` and `paths` configuration
   - What's unclear: Does tsconfig.json need updating after directory move, or is it all relative?
   - Recommendation: Verify TypeScript paths after move—if `@/*` imports break, update `tsconfig.json` baseUrl/paths

3. **Existing Component Imports (App.tsx Legacy Path)**
   - What we know: Phase 1 preserves legacy App.tsx for "/" route coexistence
   - What's unclear: Does App.tsx import components from `./components/` or `@/components/`?
   - Recommendation: After move, search for any import paths that might have broken, especially in App.tsx and existing components

## Sources

### Primary (HIGH confidence)
- [Vite Build Options Documentation](https://vite.dev/config/build-options) - build.manifest, outDir configuration
- [Vite Backend Integration Guide](https://vite.dev/guide/backend-integration) - Manifest structure, dev/prod asset serving
- [django-vite GitHub README](https://github.com/MrBin99/django-vite/blob/master/README.md) - Configuration options, path settings
- [django-vite PyPI](https://pypi.org/project/django-vite/) - Official package, version 3.1.0
- [Vite Shared Options](https://vite.dev/config/shared-options) - root option, base configuration
- [Vite Server Options](https://vite.dev/config/server-options) - host, port, CORS settings

### Secondary (MEDIUM confidence)
- [Spatie: How to structure the frontend of a Laravel Inertia React application](https://spatie.be/blog/how-to-structure-the-frontend-of-a-laravel-inertia-react-application) - Directory structure best practices (2024)
- [Inertia.js Pages Documentation](https://inertiajs.com/docs/v2/the-basics/pages) - Page resolution, naming conventions
- [Vite Guide: Building for Production](https://vite.dev/guide/build) - Build output structure
- [The Complete Guide to Mastering vite.config.js (Medium)](https://new2026.medium.com/the-complete-guide-to-mastering-vite-config-js-325319d0071d) - Configuration best practices (2025)
- [GitHub Issue #167: Clarify required settings and file structure](https://github.com/MrBin99/django-vite/issues/167) - Common configuration issues

### Tertiary (LOW confidence)
- [Vite Build Tool Redefining Frontend Architecture (Feature-Sliced Design)](https://feature-sliced.design/blog/vite-build-tool-architecture) - Architectural patterns (2024)
- Community blog posts on Django + Vite integration (useful for pitfall identification)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already installed and configured in Phase 1
- Vite configuration: HIGH - Official documentation, well-established patterns
- django-vite path settings: HIGH - Official README, clear configuration options
- Directory structure: MEDIUM-HIGH - Based on Spatie best practices (Laravel/Inertia), adapted for Django
- Common pitfalls: MEDIUM - Derived from official docs, GitHub issues, and Phase 1 implementation

**Research date:** 2026-02-12
**Valid until:** 2026-03-14 (30 days, stable ecosystem)

**Project-specific notes:**
- Phase 1 already configured Inertia with dual-path entry point (verified in sgui/src/main.tsx)
- Current structure: `sgui/` is standalone directory at project root
- Target structure: `scrapegrape/frontend/` nested inside Django project
- Vite config already has correct plugins (React, Tailwind), just needs manifest: "manifest.json" added
- django-vite already configured with correct dev server settings (5173, localhost)
- No changes needed to base.html template (still references src/main.tsx, django-vite handles path resolution)
- import.meta.glob pattern in main.tsx is already correct (relative path, no changes needed)
