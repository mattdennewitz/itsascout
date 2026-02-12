# Architecture Patterns: Django + Inertia.js + React + Vite

**Domain:** Django-Inertia Refactor and Consolidation
**Researched:** 2026-02-12
**Confidence:** HIGH

## Current Architecture

### Existing Components

```
itsascout/
├── scrapegrape/                    # Django project
│   ├── publishers/                 # Django app
│   │   ├── views.py                # Traditional Django views
│   │   ├── serializers.py          # DRF serializers
│   │   └── models.py
│   ├── templates/
│   │   ├── base.html               # Loads Vite assets, renders #root
│   │   └── index.html              # Embeds JSON in DOM via json_script
│   └── scrapegrape/
│       └── settings.py             # django_vite configured
└── sgui/                           # Separate React frontend
    ├── src/
    │   ├── main.tsx                # React entry, reads JSON from DOM
    │   ├── App.tsx                 # Parses JSON, passes to DataTable
    │   └── datatable/
    ├── dist/                       # Vite build output
    └── vite.config.ts              # Base: /static/, builds manifest.json
```

### Current Data Flow

1. **Django View** (`publishers/views.py`)
   - Queries database with optimized select_related/prefetch
   - Constructs dict with `{publisher, waf_report, terms_discovery, terms_evaluation}`
   - Serializes via DRF `PublisherWithReportsSerializer`
   - Passes to template: `render(request, "index.html", {"serialized": serialized.data})`

2. **Template** (`index.html`)
   - Embeds JSON: `{{ serialized|json_script:"publisher-data" }}`
   - Django-vite loads React bundle

3. **React** (`App.tsx`)
   - `useEffect` reads `#publisher-data` from DOM
   - Parses JSON
   - Passes to DataTable component

### Current Integration Points

- **django_vite**: Bridges Django templates and Vite builds
  - Dev mode: HMR client, React refresh
  - Prod mode: Reads manifest.json, loads hashed assets
- **DRF Serializers**: Data formatting layer
- **JSON in DOM**: Data transport mechanism

## Recommended Inertia Architecture

### New Project Structure

```
scrapegrape/                        # Django project (root)
├── publishers/                     # Django app
│   ├── views.py                    # Inertia views (render_inertia)
│   ├── serializers.py              # Keep DRF serializers OR InertiaMeta
│   └── models.py
├── frontend/                       # Consolidated React app (was sgui/)
│   ├── Pages/                      # Inertia page components
│   │   ├── Publishers/
│   │   │   └── Index.tsx           # PublishersTable page
│   │   └── Auth/                   # Future pages
│   ├── Components/                 # Reusable components
│   │   ├── DataTable/              # From sgui/src/datatable
│   │   │   ├── table.tsx
│   │   │   └── columns.tsx
│   │   └── ui/                     # shadcn components
│   ├── Layouts/                    # Shared layouts
│   │   └── AppLayout.tsx
│   ├── app.tsx                     # Inertia entry point (createInertiaApp)
│   └── vite.config.ts              # Modified for Inertia
├── templates/
│   └── base.html                   # Inertia layout ({% block inertia %})
└── scrapegrape/
    └── settings.py                 # Add inertia to INSTALLED_APPS/MIDDLEWARE
```

### Inertia Data Flow

1. **Django View** (`publishers/views.py`)
   ```python
   from inertia import render as render_inertia

   def table(request):
       # Same query logic
       publishers = Publisher.objects.annotate(...)

       # Same serialization
       serialized = PublisherWithReportsSerializer(result, many=True)

       # Inertia response instead of template render
       return render_inertia(
           request,
           'Publishers/Index',  # Component name (no extension)
           {
               'publishers': serialized.data  # Props
           }
       )
   ```

2. **No Template Data Passing** - `index.html` goes away entirely

3. **React Component** receives props directly
   ```tsx
   // frontend/Pages/Publishers/Index.tsx
   import { DataTable } from '@/Components/DataTable/table'

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

4. **Inertia App Entry** (`frontend/app.tsx`)
   ```tsx
   import { createInertiaApp } from '@inertiajs/react'
   import { createRoot } from 'react-dom/client'

   createInertiaApp({
     resolve: (name) => {
       const pages = import.meta.glob('./Pages/**/*.tsx', { eager: true })
       return pages[`./Pages/${name}.tsx`]
     },
     setup({ el, App, props }) {
       createRoot(el).render(<App {...props} />)
     },
   })
   ```

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| **Django Views** | Query data, call serializers, return Inertia responses | Models, Serializers, Inertia |
| **DRF Serializers** | Format model data for JSON transport | Views, Models |
| **Inertia Middleware** | Handle CSRF, share global props, manage page responses | Django, Frontend |
| **Inertia App** (`app.tsx`) | Initialize React app, resolve page components | Django backend, Page components |
| **Page Components** | Receive props, render UI, handle interactions | Layouts, Reusable components |
| **Layouts** | Wrap pages with persistent UI (nav, footer) | Page components |
| **Reusable Components** | UI building blocks (DataTable, buttons, etc.) | Page components |

## Integration Changes from Current to Inertia

### What Stays the Same

| Component | Current | Inertia | Notes |
|-----------|---------|---------|-------|
| Database queries | `Publisher.objects.annotate(...)` | Same | No change |
| DRF Serializers | `PublisherWithReportsSerializer` | Same or InertiaMeta | Can keep existing serializers |
| React components | `DataTable`, `columns` | Same | Move location, change imports |
| Vite config | `base: "/static/"`, manifest | Same base structure | Adjust input path |
| django_vite | `DJANGO_VITE` settings | Keep | Still needed for asset loading |

### What Changes

| Component | Current | Inertia | Migration Step |
|-----------|---------|---------|----------------|
| **View response** | `render(request, "index.html", {...})` | `render_inertia(request, "Publishers/Index", {...})` | Replace render calls |
| **Data passing** | `{{ serialized\|json_script }}` in template | Direct props to component | Remove template |
| **React entry** | `main.tsx` reads DOM, renders `<App />` | `app.tsx` uses `createInertiaApp` | Rewrite entry point |
| **Component props** | `useEffect` + JSON.parse | Direct from function params | Simplify components |
| **Routing** | Django URLs only | Django URLs + Inertia Link | Add `<Link>` components |
| **Frontend location** | `sgui/` separate directory | `scrapegrape/frontend/` | Move and restructure |

### New Components Needed

| Component | Purpose | Example |
|-----------|---------|---------|
| **InertiaMiddleware** | Auto-handle CSRF, share global data | Add to `MIDDLEWARE` |
| **Shared data middleware** | Inject auth user, flash messages into every page | Custom middleware using `inertia.share()` |
| **Base layout template** | Single Django template with `{% block inertia %}` | Replace current base.html |
| **AppLayout.tsx** | Persistent React layout (nav, footer) | Wraps page content |
| **Link components** | Inertia `<Link>` for SPA navigation | Replace `<a>` tags |

## Patterns to Follow

### Pattern 1: Inertia View Responses

**What:** Replace `render()` with `render_inertia()` for all views that should be SPA pages

**When:** Every view that returns HTML to users (not APIs)

**Example:**
```python
from inertia import render as render_inertia

def table(request):
    # Query and serialize
    publishers = Publisher.objects.annotate(...)
    serialized = PublisherWithReportsSerializer(result, many=True)

    # Return Inertia response
    return render_inertia(
        request,
        'Publishers/Index',  # Maps to frontend/Pages/Publishers/Index.tsx
        {
            'publishers': serialized.data,
            'filters': request.GET.dict()  # Additional props
        }
    )
```

### Pattern 2: DRF Serializers for Props

**What:** Continue using DRF serializers to format data before passing to Inertia

**Why:**
- Already have serializers (`PublisherWithReportsSerializer`)
- DRF handles nested relationships, custom fields
- Familiar pattern for Django developers

**Example:**
```python
# Keep existing serializer
class PublisherWithReportsSerializer(serializers.Serializer):
    publisher = PublisherSerializer()
    waf_report = WAFReportSerializer()
    terms_discovery = TermsDiscoveryResultSerializer()
    terms_evaluation = TermsEvaluationResultSerializer()

# Use in Inertia view
serialized = PublisherWithReportsSerializer(result, many=True)
return render_inertia(request, 'Publishers/Index', {
    'publishers': serialized.data  # .data gives JSON-serializable dict
})
```

**Alternative:** InertiaMeta class (v1.2+) for simpler cases
```python
class Publisher(models.Model):
    name = models.CharField(max_length=255)
    url = models.URLField()

    class InertiaMeta:
        fields = ['id', 'name', 'url']  # Control JSON output
```

### Pattern 3: Shared Data via Middleware

**What:** Inject global data (auth user, flash messages) into every Inertia response

**When:** Data needed on all pages (user info, notifications, CSRF)

**Example:**
```python
# scrapegrape/middleware.py
from inertia import share

class InertiaShareMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Share data with all Inertia responses
        share(request,
            auth={
                'user': {
                    'id': request.user.id,
                    'name': request.user.username
                } if request.user.is_authenticated else None
            },
            flash=request.session.get('flash', {}),
            csrf_token=request.META.get('CSRF_COOKIE')
        )
        return self.get_response(request)
```

### Pattern 4: Page Components Receive Props

**What:** Inertia page components receive data as TypeScript props, not via DOM parsing

**Example:**
```tsx
// frontend/Pages/Publishers/Index.tsx
interface Publisher {
  publisher: {
    id: number
    name: string
    url: string
  }
  waf_report: { firewall: string, detected: boolean }
  terms_discovery: { terms_of_service_url: string }
  terms_evaluation: { permissions: string }
}

interface Props {
  publishers: Publisher[]
  auth: { user: { id: number, name: string } }  // From shared data
}

export default function Index({ publishers, auth }: Props) {
  return (
    <div className="container mx-auto py-10">
      <h1>Publishers ({auth.user.name})</h1>
      <DataTable data={publishers} columns={columns} />
    </div>
  )
}
```

### Pattern 5: Persistent Layouts

**What:** Wrap pages in layouts that persist across navigation (avoid re-render)

**When:** Shared UI like navigation, sidebar, footer

**Example:**
```tsx
// frontend/Layouts/AppLayout.tsx
export default function AppLayout({ children }) {
  return (
    <div className="min-h-screen">
      <nav className="bg-gray-800 text-white p-4">
        <Link href="/">Publishers</Link>
      </nav>
      <main>{children}</main>
    </div>
  )
}

// frontend/Pages/Publishers/Index.tsx
import AppLayout from '@/Layouts/AppLayout'

function Index({ publishers }) {
  return (
    <div className="container mx-auto py-10">
      <DataTable data={publishers} columns={columns} />
    </div>
  )
}

Index.layout = (page) => <AppLayout children={page} />

export default Index
```

### Pattern 6: Inertia Links for SPA Navigation

**What:** Use `<Link>` component from `@inertiajs/react` instead of `<a>` tags

**Why:** Enables SPA-style navigation without full page reloads

**Example:**
```tsx
import { Link } from '@inertiajs/react'

export default function Index({ publishers }) {
  return (
    <div>
      {publishers.map(pub => (
        <Link
          href={`/publishers/${pub.publisher.id}`}
          className="text-blue-600 hover:underline"
        >
          {pub.publisher.name}
        </Link>
      ))}
    </div>
  )
}
```

### Pattern 7: Form Handling with Validation

**What:** Use `useForm` hook for forms, Django raises `InertiaValidationError` on failure

**Example:**
```tsx
// Frontend
import { useForm } from '@inertiajs/react'

export default function CreatePublisher() {
  const { data, setData, post, processing, errors } = useForm({
    name: '',
    url: ''
  })

  function handleSubmit(e) {
    e.preventDefault()
    post('/publishers/create')
  }

  return (
    <form onSubmit={handleSubmit}>
      <input
        value={data.name}
        onChange={e => setData('name', e.target.value)}
      />
      {errors.name && <div>{errors.name}</div>}
      <button disabled={processing}>Create</button>
    </form>
  )
}
```

```python
# Backend
from inertia import render as render_inertia
from inertia.exceptions import InertiaValidationError

def create_publisher(request):
    if request.method == 'POST':
        form = PublisherForm(request.POST)
        if not form.is_valid():
            raise InertiaValidationError(
                errors=form.errors,
                redirect_url=request.META.get('HTTP_REFERER', '/')
            )
        form.save()
        return redirect('publishers.index')

    return render_inertia(request, 'Publishers/Create', {})
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Mixing Template Rendering and Inertia

**What:** Using both `render(request, 'template.html')` and `render_inertia()` for different pages

**Why bad:** Creates two different frontend paradigms, confusing DX, breaks SPA navigation

**Instead:** Commit to Inertia for all user-facing pages. Keep traditional templates only for:
- Django admin (uses own templates)
- Email templates
- PDF generation

### Anti-Pattern 2: Using React Router with Inertia

**What:** Installing `react-router-dom` and defining frontend routes

**Why bad:** Inertia uses server-side routing (Django URLs). React Router conflicts with Inertia's navigation.

**Instead:** Define all routes in Django `urls.py`, use `<Link>` from `@inertiajs/react`

### Anti-Pattern 3: Reading Data from DOM

**What:** Embedding JSON in templates and reading with `document.getElementById()`

**Why bad:** Defeats purpose of Inertia (direct props), adds unnecessary parsing step

**Instead:** Pass data as Inertia props, receive in component parameters

### Anti-Pattern 4: Separate API Endpoints

**What:** Creating DRF ViewSets/APIViews and fetching from React with axios/fetch

**Why bad:** Inertia eliminates need for separate API layer for SSR pages

**Instead:** Return Inertia responses from views, data flows as props. Only create APIs for:
- Mobile apps
- Third-party integrations
- Public API

### Anti-Pattern 5: Not Using Lazy Props

**What:** Always evaluating expensive queries even for partial reloads

**Why bad:** Performance penalty when only subset of data needed

**Instead:** Wrap expensive props in lambda for lazy evaluation
```python
return render_inertia(request, 'Publishers/Index', {
    'publishers': serialized.data,  # Always included
    'expensive_stats': lambda: calculate_expensive_stats()  # Only when requested
})
```

## Vite Configuration Changes

### Current Vite Config (`sgui/vite.config.ts`)

```typescript
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: "/static/",
  build: {
    manifest: "manifest.json",
    outDir: "dist",
    rollupOptions: {
      input: "src/main.tsx",
    },
  },
})
```

### Inertia Vite Config (`scrapegrape/frontend/vite.config.ts`)

```typescript
import path from "path"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],

  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./"),  // Changed: points to frontend/
    },
  },

  base: "/static/",  // Same: matches STATIC_URL

  build: {
    manifest: "manifest.json",  // Same
    outDir: "dist",  // Same: but now in scrapegrape/frontend/dist/
    rollupOptions: {
      input: "app.tsx",  // Changed: Inertia entry point
    },
  },

  server: {
    host: "0.0.0.0",
    port: 5173,
    cors: true,
    // Optional: proxy API requests in dev
    proxy: {
      '/api': 'http://localhost:8000'
    }
  },
})
```

### Django Settings Changes

```python
# scrapegrape/scrapegrape/settings.py

INSTALLED_APPS = [
    # ... existing apps
    "django_vite",
    "inertia",  # Add
    "rest_framework",
    "publishers",
]

MIDDLEWARE = [
    # ... existing middleware
    "inertia.middleware.InertiaMiddleware",  # Add before views execute
    # Custom middleware for shared data
    "scrapegrape.middleware.InertiaShareMiddleware",
]

# Django Vite (updated path)
DJANGO_VITE = {
    "default": {
        "dev_mode": DEBUG,
        "manifest_path": BASE_DIR / "frontend" / "dist" / "manifest.json",  # Changed
        "dev_server_port": 5173,
    }
}

# Inertia configuration
INERTIA_LAYOUT = 'base.html'  # Required: root template
INERTIA_VERSION = '1.0'  # Optional: cache busting
INERTIA_JSON_ENCODER = 'django.core.serializers.json.DjangoJSONEncoder'  # Optional

# CSRF configuration for Inertia/Axios
# Option 1: Modify Django's CSRF header names to match Axios
CSRF_HEADER_NAME = 'HTTP_X_XSRF_TOKEN'
CSRF_COOKIE_NAME = 'XSRF-TOKEN'

# Option 2: OR configure Axios in frontend (see frontend/app.tsx)
```

### Base Template Changes

**Current:** `scrapegrape/templates/base.html`
```django
{% load django_vite %}
<!DOCTYPE html>
<html>
<head>
    <title>{% block title %}Scrapegrape{% endblock %}</title>
    {% vite_hmr_client %}
    {% vite_react_refresh %}
    {% vite_asset 'src/main.tsx' %}
</head>
<body>
    <div id="root"></div>
    {% block extra_body %}{% endblock %}
</body>
</html>
```

**Inertia:** `scrapegrape/templates/base.html`
```django
{% load django_vite %}
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Scrapegrape</title>

    {% vite_hmr_client %}
    {% vite_react_refresh %}
    {% vite_asset 'app.tsx' %}  {# Changed: Inertia entry point #}
</head>
<body>
    {% block inertia %}{% endblock %}  {# Changed: Inertia renders here #}
</body>
</html>
```

## Data Flow Comparison

### Current: Django -> JSON in DOM -> React

```
┌─────────────┐
│ Django View │ Query DB, serialize with DRF
└──────┬──────┘
       │
       v
┌──────────────┐
│   Template   │ {{ serialized|json_script:"publisher-data" }}
└──────┬───────┘
       │
       v
┌──────────────┐
│  React App   │ useEffect reads #publisher-data, JSON.parse
└──────┬───────┘
       │
       v
┌──────────────┐
│  DataTable   │ Receives parsed data as prop
└──────────────┘
```

### Inertia: Django -> Inertia Response -> React Props

```
┌─────────────┐
│ Django View │ Query DB, serialize with DRF
└──────┬──────┘
       │
       v
┌──────────────┐
│   Inertia    │ render_inertia('Publishers/Index', {publishers: data})
│  Middleware  │ Adds shared data (auth, flash), CSRF
└──────┬───────┘
       │
       v
┌──────────────┐
│ Inertia App  │ createInertiaApp resolves component, passes props
└──────┬───────┘
       │
       v
┌──────────────┐
│ Page Component│ function Index({ publishers }) {...}
│ (Index.tsx)  │
└──────┬───────┘
       │
       v
┌──────────────┐
│  DataTable   │ Receives publishers directly
└──────────────┘
```

**Key Difference:** No intermediate template or DOM parsing. Data flows directly from Django -> Inertia -> React props.

## Migration Build Order

### Phase 1: Setup Inertia Infrastructure (No Feature Changes)

1. **Install packages**
   ```bash
   pip install inertia-django
   npm install @inertiajs/react
   ```

2. **Configure Django**
   - Add `inertia` to `INSTALLED_APPS`
   - Add `InertiaMiddleware` to `MIDDLEWARE`
   - Set `INERTIA_LAYOUT = 'base.html'`
   - Configure CSRF for Axios

3. **Update base template**
   - Change `{% block extra_body %}` to `{% block inertia %}`
   - Update Vite asset reference to `app.tsx`

4. **Move frontend directory**
   ```bash
   mkdir scrapegrape/frontend
   mv sgui/src/* scrapegrape/frontend/
   mv sgui/vite.config.ts scrapegrape/frontend/
   mv sgui/package.json scrapegrape/frontend/
   ```

5. **Restructure frontend**
   ```bash
   cd scrapegrape/frontend
   mkdir -p Pages/Publishers Components/DataTable Layouts
   mv datatable/* Components/DataTable/
   ```

6. **Create Inertia entry point** (`frontend/app.tsx`)
   ```tsx
   import { createInertiaApp } from '@inertiajs/react'
   import { createRoot } from 'react-dom/client'
   import axios from 'axios'

   // Configure Axios for Django CSRF
   axios.defaults.xsrfHeaderName = 'X-CSRFToken'
   axios.defaults.xsrfCookieName = 'csrftoken'

   createInertiaApp({
     resolve: (name) => {
       const pages = import.meta.glob('./Pages/**/*.tsx', { eager: true })
       return pages[`./Pages/${name}.tsx`]
     },
     setup({ el, App, props }) {
       createRoot(el).render(<App {...props} />)
     },
   })
   ```

7. **Update Vite config**
   - Change `input` to `"app.tsx"`
   - Update `manifest_path` in Django settings

8. **Test:** Run Vite dev server, ensure no errors

### Phase 2: Convert First View (Publishers Table)

1. **Create page component** (`frontend/Pages/Publishers/Index.tsx`)
   ```tsx
   import { DataTable } from '@/Components/DataTable/table'
   import { columns, type Publisher } from '@/Components/DataTable/columns'

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

2. **Update view** (`publishers/views.py`)
   ```python
   from inertia import render as render_inertia

   def table(request):
       # Keep existing query and serialization
       serialized = PublisherWithReportsSerializer(result, many=True)

       # Change only the return
       return render_inertia(request, 'Publishers/Index', {
           'publishers': serialized.data
       })
   ```

3. **Remove old files**
   - Delete `templates/index.html`
   - Delete `sgui/src/App.tsx`
   - Delete `sgui/src/main.tsx`

4. **Test:** Navigate to table view, verify data displays

### Phase 3: Add Shared Data Middleware

1. **Create middleware** (`scrapegrape/middleware.py`)
   ```python
   from inertia import share

   class InertiaShareMiddleware:
       def __init__(self, get_response):
           self.get_response = get_response

       def __call__(self, request):
           share(request,
               auth={
                   'user': {
                       'id': request.user.id,
                       'username': request.user.username,
                       'email': request.user.email
                   } if request.user.is_authenticated else None
               },
               flash=request.session.pop('flash', {})
           )
           return self.get_response(request)
   ```

2. **Register middleware** in settings

3. **Create app layout** (`frontend/Layouts/AppLayout.tsx`)
   ```tsx
   import { Link, usePage } from '@inertiajs/react'

   export default function AppLayout({ children }) {
     const { auth } = usePage().props

     return (
       <div className="min-h-screen bg-gray-100">
         <nav className="bg-white shadow">
           <div className="container mx-auto px-4 py-3">
             <Link href="/" className="font-bold">Scrapegrape</Link>
             {auth.user && <span>Welcome, {auth.user.username}</span>}
           </div>
         </nav>
         <main className="py-6">{children}</main>
       </div>
     )
   }
   ```

4. **Apply layout to pages**
   ```tsx
   // frontend/Pages/Publishers/Index.tsx
   import AppLayout from '@/Layouts/AppLayout'

   function Index({ publishers }) { /* ... */ }

   Index.layout = (page) => <AppLayout children={page} />

   export default Index
   ```

### Phase 4: Clean Up and Optimize

1. **Remove sgui directory**
   ```bash
   rm -rf sgui/
   ```

2. **Update .gitignore**
   ```
   scrapegrape/frontend/dist/
   scrapegrape/frontend/node_modules/
   ```

3. **Add lazy props** for expensive queries
   ```python
   return render_inertia(request, 'Publishers/Index', {
       'publishers': serialized.data,
       'stats': lambda: calculate_stats()  # Only evaluated if requested
   })
   ```

4. **Test partial reloads**
   ```tsx
   import { router } from '@inertiajs/react'

   function refresh() {
     router.reload({ only: ['publishers'] })  // Only refetch publishers
   }
   ```

5. **Document TypeScript types** for shared props
   ```tsx
   // frontend/types/index.d.ts
   export interface User {
     id: number
     username: string
     email: string
   }

   export interface SharedProps {
     auth: {
       user: User | null
     }
     flash: {
       success?: string
       error?: string
     }
   }
   ```

## Scalability Considerations

| Concern | Current (100 users) | Inertia (100 users) | At 10K users | At 1M users |
|---------|---------------------|---------------------|--------------|-------------|
| **Data serialization** | DRF on every request | Same (no change) | Cache serialized data | Background jobs + Redis |
| **Asset serving** | Vite dev server | Same | Nginx serves static | CDN (CloudFront, Cloudflare) |
| **Initial page load** | Full React bundle | Same | Code splitting by route | Lazy-load components |
| **Navigation** | Full page reload | Inertia SPA navigation (faster) | Same | Add prefetching |
| **Database queries** | N+1 possible | Same risk | select_related, prefetch_related | Read replicas, materialized views |
| **Prop size** | JSON in DOM (~100KB) | JSON in XHR (~100KB, same) | Pagination, lazy props | Cursor pagination, CDN |

**Key Insight:** Inertia doesn't fundamentally change scaling concerns. Same database, same serialization, same bundle size. Improves UX (SPA navigation) without adding API complexity.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Django-Inertia integration | HIGH | Official docs, multiple tutorials, active community |
| Vite configuration | HIGH | Already using django-vite, minimal changes needed |
| DRF serializer compatibility | HIGH | Can continue using existing serializers, InertiaMeta optional |
| Migration strategy | HIGH | Clear path from current to Inertia, incremental migration possible |
| Performance implications | MEDIUM | Inertia improves UX, but serialization/query optimizations still needed |

## Sources

### Official Documentation
- [Inertia Django Official Docs](https://inertiajs.github.io/inertia-django/guide/)
- [Inertia Django GitHub Repository](https://github.com/inertiajs/inertia-django)
- [Inertia.js Documentation](https://inertiajs.com/)
- [Inertia.js Links](https://inertiajs.com/docs/v2/the-basics/links)
- [Inertia.js Forms](https://inertiajs.com/docs/v2/the-basics/forms)
- [Inertia.js Pages](https://inertiajs.com/docs/v2/the-basics/pages)
- [Inertia.js Partial Reloads](https://inertiajs.com/docs/v2/data-props/partial-reloads)
- [Django REST Framework Serializers](https://www.django-rest-framework.org/api-guide/serializers/)

### Package Documentation
- [inertia-django on PyPI](https://pypi.org/project/inertia-django/)
- [django-vite on PyPI](https://pypi.org/project/django-vite/)
- [django-vite GitHub](https://github.com/MrBin99/django-vite)

### Tutorials and Articles
- [Building a Modern Web App with Django, Inertia.js, Vite, and React](https://medium.com/@tanzid3/building-a-modern-web-app-with-django-inertia-js-vite-and-react-67979a981649)
- [How to setup Django with React using InertiaJS](https://anjanesh.dev/how-to-setup-django-with-react-using-inertiajs)
- [Building SPA-like Apps with Django and Inertia.js](https://docs.djangoeasystart.com/modules/django-inertia-integration)

### Example Repositories
- [django-vite-inertia Template](https://github.com/SarthakJariwala/django-vite-inertia)
- [django-inertia-vite (React + TypeScript)](https://github.com/JiaWeiXie/django-inertia-vite)
- [django-inertia-react Minimal Example](https://github.com/fertek/django-inertia-react)
- [inertia-django-vite-vue-minimal](https://github.com/mujahidfa/inertia-django-vite-vue-minimal)

### Community Resources
- [Inertia Django Form Validation PR](https://github.com/inertiajs/inertia-django/pull/32)
- [Inertia Django Validation Issue](https://github.com/inertiajs/inertia-django/issues/30)
- [Related Models Serialization Issue](https://github.com/inertiajs/inertia-django/issues/18)
- [django-rest-inertia Adapter](https://github.com/rojoca/django-rest-inertia)
