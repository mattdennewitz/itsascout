# Phase 4: Interactive Features - Research

**Researched:** 2026-02-12
**Domain:** Inertia.js interactive patterns (forms, partial reloads, lazy props) in Django + React
**Confidence:** HIGH

## Summary

Phase 4 adds interactivity to the Inertia application established in Phases 1-3: form submissions with validation, partial reloads for table filtering, lazy/deferred props for expensive queries, and scroll preservation for pagination. The core pattern is Inertia's `useForm` hook, which manages form state, handles submissions, displays server validation errors, and tracks upload progress without manual state management.

Partial reloads enable filtering the publisher table without refreshing the entire page—only the `publishers` prop reloads while preserving sort state, scroll position, and expensive related data (WAF reports, ToS evaluation). Deferred props delay loading heavy computations until after initial render, improving perceived performance. The `preserveScroll` option maintains scroll position during pagination, preventing the jarring jump-to-top behavior.

Django validation integrates via `InertiaValidationError` exception (from django-inertia), which flashes errors to session and returns them as props. The `useForm` hook automatically maps these to field-level errors displayed inline. File uploads (CSV bulk import) track progress via `form.progress.percentage` and handle multipart form data automatically. The existing `analyze_url` task from Phase 1-3 remains the backend for publisher ingestion, with a new view wrapper that accepts CSV uploads and enqueues batch processing.

**Primary recommendation:** Implement useForm for create/edit publisher forms with validation error display, add CSV upload with Papa Parse client-side validation and progress tracking, implement partial reloads with `only: ['publishers']` for table filtering, defer WAF/ToS data using `defer()` backend wrapper and `<Deferred>` component, and use `preserveScroll: true` for pagination links.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| @inertiajs/react | 2.3.14 (existing) | useForm hook, Deferred component, router | Official React adapter with all interactive features needed |
| inertia-django | 1.2.0 (existing) | defer(), optional(), InertiaValidationError | Official Django adapter with deferred props support |
| axios | 1.13.5 (existing) | HTTP client for Inertia | Auto-configured for Django CSRF, handles all Inertia requests |
| @tanstack/react-table | 8.21.3 (existing) | Table filtering/sorting state | Already powering DataTable, supports client-side filtering |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| react-papaparse | 4.x | CSV parsing and validation | CSV bulk import with type checking and error reporting |
| Django Forms | 5.2 (built-in) | Server-side validation | Validate create/edit publisher, bulk CSV upload |
| django-tasks | existing | Background job queue | Existing analyze_url task for bulk CSV processing |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| useForm hook | Manual axios + useState | useForm handles errors, loading state, file uploads automatically; manual approach requires ~50 lines of boilerplate |
| react-papaparse | csv-parse, PapaParse vanilla | react-papaparse provides React-specific hooks and components; vanilla requires more integration code |
| Django Forms validation | DRF serializers only | Django Forms have built-in field validation and error messages; DRF serializers require custom error formatting |
| Deferred props | Lazy props (deprecated) | Deferred props are Inertia v2 pattern with automatic loading; lazy props required manual reload triggers |

**Installation:**
```bash
cd scrapegrape/frontend
npm install react-papaparse
```

## Architecture Patterns

### Recommended Project Structure
```
scrapegrape/
├── publishers/
│   ├── views.py                     # ADD: create, update, bulk_upload views
│   ├── forms.py                     # NEW: PublisherForm, BulkUploadForm
│   ├── serializers.py               # UNCHANGED: Existing serializers
│   └── tasks.py                     # REUSE: analyze_url task
├── scrapegrape/
│   ├── middleware.py                # UNCHANGED: Shared data already configured
│   └── urls.py                      # ADD: POST routes for forms
└── frontend/
    └── src/
        ├── Pages/
        │   └── Publishers/
        │       ├── Index.tsx        # MODIFY: Add filters, pagination
        │       ├── Create.tsx       # NEW: Publisher creation form
        │       ├── Edit.tsx         # NEW: Publisher edit form
        │       └── BulkUpload.tsx   # NEW: CSV upload form
        ├── Components/
        │   ├── FormField.tsx        # NEW: Reusable field with error display
        │   └── ProgressBar.tsx      # NEW: File upload progress
        └── datatable/
            └── table.tsx            # MODIFY: Add filter controls
```

### Pattern 1: Form Submission with Validation Errors

**What:** Use useForm hook to handle form state, submission, and automatic validation error mapping
**When to use:** Any form that requires server-side validation (create, edit, settings)
**Example:**
```typescript
// Source: https://inertiajs.com/docs/v2/the-basics/forms
// scrapegrape/frontend/src/Pages/Publishers/Create.tsx

import { useForm } from '@inertiajs/react'
import { FormEventHandler } from 'react'

interface Publisher {
    name: string
    url: string
}

export default function Create() {
    const { data, setData, post, processing, errors, reset } = useForm<Publisher>({
        name: '',
        url: '',
    })

    const submit: FormEventHandler = (e) => {
        e.preventDefault()
        post('/publishers', {
            onSuccess: () => reset(),
        })
    }

    return (
        <form onSubmit={submit}>
            <div>
                <label>Name</label>
                <input
                    value={data.name}
                    onChange={e => setData('name', e.target.value)}
                />
                {errors.name && <div className="text-red-600">{errors.name}</div>}
            </div>

            <div>
                <label>URL</label>
                <input
                    value={data.url}
                    onChange={e => setData('url', e.target.value)}
                />
                {errors.url && <div className="text-red-600">{errors.url}</div>}
            </div>

            <button type="submit" disabled={processing}>
                {processing ? 'Creating...' : 'Create Publisher'}
            </button>
        </form>
    )
}
```

**Django view with validation:**
```python
# Source: https://github.com/inertiajs/inertia-django/pull/32
# scrapegrape/publishers/views.py

from inertia import render as inertia_render
from publishers.forms import PublisherForm

def create(request):
    if request.method == 'POST':
        form = PublisherForm(request.POST)
        if form.is_valid():
            publisher = form.save()
            request.session['success'] = f'Publisher "{publisher.name}" created!'
            return redirect('/')
        else:
            # Errors automatically passed as props to frontend
            raise InertiaValidationError(form.errors, redirect('/publishers/create'))

    return inertia_render(request, 'Publishers/Create')
```

**Django form definition:**
```python
# scrapegrape/publishers/forms.py (NEW)
from django import forms
from publishers.models import Publisher

class PublisherForm(forms.ModelForm):
    class Meta:
        model = Publisher
        fields = ['name', 'url']

    def clean_url(self):
        url = self.cleaned_data['url']
        if not url.startswith(('http://', 'https://')):
            raise forms.ValidationError('URL must start with http:// or https://')
        return url
```

**Key points:**
- useForm manages all form state (data, errors, processing)
- Errors automatically populate from Django form validation
- Processing flag prevents double-submit
- onSuccess callback resets form after successful submission

### Pattern 2: File Upload with Progress Tracking

**What:** Handle CSV file upload with progress indicator using form.progress
**When to use:** Any file upload that could take >1 second
**Example:**
```typescript
// Source: https://inertiajs.com/docs/v2/the-basics/file-uploads
// scrapegrape/frontend/src/Pages/Publishers/BulkUpload.tsx

import { useForm } from '@inertiajs/react'
import { FormEventHandler, ChangeEvent } from 'react'
import { usePapaParse } from 'react-papaparse'

export default function BulkUpload() {
    const { readString } = usePapaParse()
    const { data, setData, post, processing, progress, errors } = useForm({
        csv_file: null as File | null,
    })

    const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (!file) return

        // Client-side validation with Papa Parse
        const reader = new FileReader()
        reader.onload = (event) => {
            readString(event.target?.result as string, {
                header: true,
                complete: (results) => {
                    // Check for required 'URL' column
                    if (!results.meta.fields?.includes('URL')) {
                        alert('CSV must have a "URL" column')
                        return
                    }
                    setData('csv_file', file)
                },
                error: (error) => {
                    alert(`CSV parsing error: ${error.message}`)
                },
            })
        }
        reader.readAsText(file)
    }

    const submit: FormEventHandler = (e) => {
        e.preventDefault()
        post('/publishers/bulk-upload', {
            onSuccess: () => {
                setData('csv_file', null)
            },
        })
    }

    return (
        <form onSubmit={submit}>
            <div>
                <label>CSV File</label>
                <input
                    type="file"
                    accept=".csv"
                    onChange={handleFileChange}
                />
                {errors.csv_file && <div className="text-red-600">{errors.csv_file}</div>}
            </div>

            {progress && (
                <div className="mt-4">
                    <div className="text-sm text-gray-600 mb-1">
                        Uploading... {progress.percentage}%
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2.5">
                        <div
                            className="bg-blue-600 h-2.5 rounded-full"
                            style={{ width: `${progress.percentage}%` }}
                        />
                    </div>
                </div>
            )}

            <button type="submit" disabled={processing || !data.csv_file}>
                {processing ? 'Uploading...' : 'Upload CSV'}
            </button>
        </form>
    )
}
```

**Django view with file handling:**
```python
# scrapegrape/publishers/views.py

from django.core.files.uploadedfile import UploadedFile
from publishers.forms import BulkUploadForm
from publishers.tasks import analyze_url
import csv

def bulk_upload(request):
    if request.method == 'POST':
        form = BulkUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            decoded_file = csv_file.read().decode('utf-8').splitlines()
            reader = csv.DictReader(decoded_file)

            count = 0
            for row in reader:
                if 'URL' in row:
                    analyze_url.enqueue(row['URL'])
                    count += 1

            request.session['success'] = f'{count} URLs queued for analysis'
            return redirect('/')
        else:
            raise InertiaValidationError(form.errors, redirect('/publishers/bulk-upload'))

    return inertia_render(request, 'Publishers/BulkUpload')
```

**Key points:**
- Papa Parse validates CSV client-side before upload
- form.progress tracks upload percentage automatically
- File automatically converted to FormData by Inertia
- Reuse existing analyze_url task for background processing

### Pattern 3: Partial Reloads for Filtering

**What:** Reload only publishers array when filtering, preserving expensive WAF/ToS data
**When to use:** Table filtering, search, pagination—any operation that changes subset of data
**Example:**
```typescript
// Source: https://inertiajs.com/docs/v2/data-props/partial-reloads
// scrapegrape/frontend/src/Pages/Publishers/Index.tsx

import { router } from '@inertiajs/react'
import { DataTable } from '@/datatable/table'
import { columns, type Publisher } from '@/datatable/columns'
import { useState } from 'react'

interface Props {
    publishers: Publisher[]
}

export default function Index({ publishers }: Props) {
    const [search, setSearch] = useState('')

    const handleFilter = (value: string) => {
        setSearch(value)

        // Partial reload: only fetch publishers, preserve other props
        router.get('/',
            { search: value },
            {
                only: ['publishers'],
                preserveScroll: true,
                preserveState: true,
            }
        )
    }

    return (
        <div className="container mx-auto py-10">
            <div className="mb-4">
                <input
                    type="text"
                    placeholder="Filter publishers..."
                    value={search}
                    onChange={e => handleFilter(e.target.value)}
                    className="px-4 py-2 border rounded"
                />
            </div>
            <DataTable columns={columns} data={publishers} />
        </div>
    )
}
```

**Django view with filtering:**
```python
# scrapegrape/publishers/views.py

def table(request):
    search = request.GET.get('search', '')

    # ... existing Subquery logic ...

    publishers = Publisher.objects.annotate(
        latest_waf_id=latest_waf,
        latest_discovery_id=latest_discovery,
        latest_evaluation_id=latest_evaluation,
    )

    # Apply filter if search param exists
    if search:
        publishers = publishers.filter(name__icontains=search)

    # ... existing bulk fetching and serialization ...

    return inertia_render(request, 'Publishers/Index', props={
        'publishers': serialized.data,
    })
```

**Key points:**
- `only: ['publishers']` tells server to only return publishers prop
- `preserveScroll: true` maintains scroll position during reload
- `preserveState: true` keeps component state (sort, expanded rows)
- Server sees partial reload header and skips expensive computations

### Pattern 4: Deferred Props for Expensive Data

**What:** Defer loading of WAF reports and ToS evaluation until after initial render
**When to use:** Expensive queries that aren't needed immediately, data below the fold
**Example:**
```python
# Source: https://inertiajs.com/docs/v2/data-props/deferred-props
# https://github.com/inertiajs/inertia-django (defer support)
# scrapegrape/publishers/views.py

from inertia import defer

def table(request):
    publishers = Publisher.objects.all()

    # Defer expensive related data loading
    def load_publishers_with_reports():
        # ... existing Subquery logic, bulk fetching ...
        return PublisherWithReportsSerializer(result, many=True).data

    return inertia_render(request, 'Publishers/Index', props={
        'publishers': defer(load_publishers_with_reports),
        # Could group multiple deferred props together
        # 'waf_stats': defer(calculate_waf_statistics, group='analytics'),
    })
```

**React component with Deferred wrapper:**
```typescript
// Source: https://inertiajs.com/docs/v2/data-props/deferred-props
// scrapegrape/frontend/src/Pages/Publishers/Index.tsx

import { Deferred } from '@inertiajs/react'
import { DataTable } from '@/datatable/table'
import { columns, type Publisher } from '@/datatable/columns'

interface Props {
    publishers: Publisher[]
}

export default function Index({ publishers }: Props) {
    return (
        <div className="container mx-auto py-10">
            <h1 className="text-2xl mb-4">Publishers</h1>

            <Deferred data="publishers" fallback={<LoadingSpinner />}>
                <DataTable columns={columns} data={publishers} />
            </Deferred>
        </div>
    )
}

function LoadingSpinner() {
    return (
        <div className="flex justify-center items-center h-64">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
        </div>
    )
}
```

**Key points:**
- `defer()` wraps expensive function on backend
- Initial page load returns placeholder, triggers second request for deferred data
- `<Deferred>` component shows fallback while loading
- Can group multiple deferred props for parallel loading

### Pattern 5: Pagination with Scroll Preservation

**What:** Maintain scroll position when navigating between pages
**When to use:** Pagination links, infinite scroll triggers
**Example:**
```typescript
// Source: https://inertiajs.com/docs/v2/advanced/scroll-management
// scrapegrape/frontend/src/Pages/Publishers/Index.tsx

import { Link } from '@inertiajs/react'

interface Props {
    publishers: Publisher[]
    pagination: {
        current_page: number
        total_pages: number
        has_next: boolean
        has_previous: boolean
    }
}

export default function Index({ publishers, pagination }: Props) {
    return (
        <div>
            <DataTable columns={columns} data={publishers} />

            <div className="mt-4 flex gap-2">
                {pagination.has_previous && (
                    <Link
                        href={`/?page=${pagination.current_page - 1}`}
                        preserveScroll
                        className="px-4 py-2 bg-blue-600 text-white rounded"
                    >
                        Previous
                    </Link>
                )}

                {pagination.has_next && (
                    <Link
                        href={`/?page=${pagination.current_page + 1}`}
                        preserveScroll
                        className="px-4 py-2 bg-blue-600 text-white rounded"
                    >
                        Next
                    </Link>
                )}
            </div>
        </div>
    )
}
```

**Django view with pagination:**
```python
# scrapegrape/publishers/views.py

from django.core.paginator import Paginator

def table(request):
    page_num = request.GET.get('page', 1)

    # ... existing query logic ...

    publishers_queryset = Publisher.objects.annotate(...)
    paginator = Paginator(publishers_queryset, 25)
    page = paginator.get_page(page_num)

    # Build result for current page only
    result = [/* ... */]
    serialized = PublisherWithReportsSerializer(result, many=True)

    return inertia_render(request, 'Publishers/Index', props={
        'publishers': serialized.data,
        'pagination': {
            'current_page': page.number,
            'total_pages': paginator.num_pages,
            'has_next': page.has_next(),
            'has_previous': page.has_previous(),
        },
    })
```

**Key points:**
- `preserveScroll` prop on Link prevents scroll-to-top
- Pagination implemented server-side with Django Paginator
- Can combine with partial reloads: `only: ['publishers', 'pagination']`
- Conditional rendering based on has_next/has_previous

### Anti-Patterns to Avoid

- **Don't use manual axios for form submissions:** useForm handles CSRF, validation errors, loading state automatically
- **Don't parse CSV on the server without client-side validation:** Papa Parse client-side prevents unnecessary uploads of invalid files
- **Don't reload entire page when filtering:** Use partial reloads with `only` option to preserve expensive data
- **Don't defer props that are needed immediately:** Deferred props cause loading flash; only defer below-the-fold or on-demand data
- **Don't forget preserveScroll on pagination:** Users expect scroll position to stay put when paging through results
- **Don't hand-roll progress indicators:** form.progress tracks upload automatically, no manual XHR needed

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Form state management | useState for each field + errors object | useForm hook | Handles data, errors, processing, file uploads, progress tracking—~50 lines of boilerplate eliminated |
| CSV parsing/validation | String splitting + regex | react-papaparse | Handles quoted fields, newlines in data, encoding issues, provides typed output |
| Upload progress tracking | Manual XMLHttpRequest with onprogress | form.progress from useForm | Inertia tracks automatically, works with axios interceptors, no manual wiring |
| Validation error mapping | Manual error object to field matching | InertiaValidationError + useForm | Django form errors automatically map to useForm errors object by field name |
| Partial prop updates | Manual state merging + conditional fetching | Partial reloads with only/except | Server-side optimization, prevents over-fetching, handles edge cases |
| Loading states for deferred data | useState + useEffect fetching | Deferred component | Automatic request grouping, built-in loading states, integrates with Inertia page cache |

**Key insight:** Inertia's interactive features integrate tightly with Django patterns (forms, validation, file uploads). Hand-rolling these loses automatic CSRF handling, error mapping, progress tracking, and optimistic updates. The complexity isn't in the happy path—it's in edge cases like CSRF token refresh, partial failures, concurrent requests, and history state management.

## Common Pitfalls

### Pitfall 1: Form Errors Not Displaying After Submission

**What goes wrong:** Form submits, validation fails on server, but no error messages appear in UI

**Why it happens:** InertiaValidationError not raised, or Django form errors not structured correctly for Inertia

**How to avoid:**
```python
# CORRECT: Raise InertiaValidationError with form.errors
from inertia import InertiaValidationError

def create(request):
    form = PublisherForm(request.POST)
    if not form.is_valid():
        raise InertiaValidationError(form.errors, redirect('/publishers/create'))
    # ...

# INCORRECT: Return errors as props manually
def create(request):
    form = PublisherForm(request.POST)
    if not form.is_valid():
        return inertia_render(request, 'Publishers/Create', props={
            'errors': form.errors  # Won't map to useForm errors object
        })
```

**Verification:**
1. Submit invalid form
2. Check browser console for errors prop in Inertia page data
3. Verify errors object has field names matching form fields
4. Check useForm destructured errors: `const { errors } = useForm(...)`

**Warning signs:**
- Form submits but no error messages appear
- Console shows errors prop but it's nested incorrectly
- Errors appear after hard refresh but not after XHR submission

### Pitfall 2: CSV Upload Hangs Without Progress Indicator

**What goes wrong:** Large CSV upload shows no progress, user clicks submit multiple times, creates duplicate jobs

**Why it happens:** form.progress is null initially and only appears after upload starts; UI doesn't show loading state

**How to avoid:**
```typescript
// CORRECT: Show processing state AND progress
const { processing, progress } = useForm({ csv_file: null })

return (
    <>
        {processing && !progress && <div>Preparing upload...</div>}
        {progress && <ProgressBar percentage={progress.percentage} />}
        <button disabled={processing}>
            {processing ? 'Uploading...' : 'Upload'}
        </button>
    </>
)

// INCORRECT: Only check progress
return (
    <>
        {progress && <ProgressBar percentage={progress.percentage} />}
        <button>Upload</button>  {/* Not disabled during processing */}
    </>
)
```

**Warning signs:**
- No visual feedback when upload starts
- Button stays enabled during upload
- Multiple task queue entries for same CSV

### Pitfall 3: Partial Reload Wipes Out Unrelated State

**What goes wrong:** User expands table row to view permissions, filters table, expanded row collapses

**Why it happens:** TanStack Table `expanded` state lives in component, partial reload triggers re-render, state resets

**How to avoid:**
```typescript
// CORRECT: Preserve component state during partial reload
router.get('/',
    { search: value },
    {
        only: ['publishers'],
        preserveState: true,  // Keeps TanStack Table state
        preserveScroll: true,
    }
)

// INCORRECT: Missing preserveState
router.get('/',
    { search: value },
    { only: ['publishers'] }  // Table state resets
)
```

**Alternative approach:** Store expanded state in URL params
```typescript
const [expanded, setExpanded] = useState(new URLSearchParams(window.location.search).get('expanded')?.split(',') || [])

// Update URL when expanding
router.get('/',
    { expanded: [...expanded, rowId].join(',') },
    { preserveScroll: true }
)
```

**Warning signs:**
- Filters work but table sorting resets
- Expanded rows collapse after search
- Scroll position jumps even with preserveScroll

### Pitfall 4: Deferred Props Cause Infinite Loading Spinner

**What goes wrong:** Page loads, shows spinner for deferred data, spinner never resolves

**Why it happens:** Backend defer() function has error or incorrect prop name mismatch between backend and `<Deferred>` component

**How to avoid:**
```python
# CORRECT: Match prop name exactly
return inertia_render(request, 'Publishers/Index', props={
    'publishers': defer(load_publishers),  # Prop name: 'publishers'
})
```

```typescript
// CORRECT: Match prop name from backend
<Deferred data="publishers" fallback={<Loading />}>
    <DataTable data={publishers} />
</Deferred>

// INCORRECT: Mismatched name
<Deferred data="publisherList" fallback={<Loading />}>
    {/* Never resolves—backend sends 'publishers', expects 'publisherList' */}
</Deferred>
```

**Debugging:**
1. Check Network tab for deferred prop request (separate XHR after initial load)
2. Verify response contains expected prop name
3. Check Django logs for exceptions in deferred function
4. Verify `<Deferred>` data prop matches backend key exactly

**Warning signs:**
- Spinner shows indefinitely
- Network tab shows failed request to same URL
- Console error: "Property 'publishers' is undefined"

### Pitfall 5: CSRF Token Missing on File Upload

**What goes wrong:** CSV upload returns 403 Forbidden CSRF verification failed

**Why it happens:** Axios CSRF configuration from Phase 1 works for JSON requests but not multipart/form-data

**How to avoid:** Already handled by Phase 1 configuration, but verify:
```typescript
// scrapegrape/frontend/src/main.tsx (from Phase 1)
axios.defaults.xsrfHeaderName = "X-CSRFToken"
axios.defaults.xsrfCookieName = "csrftoken"
// Axios reads cookie on EVERY request, including multipart
```

**Additional verification:**
```python
# Django settings.py - ensure CSRF cookie is accessible
CSRF_COOKIE_HTTPONLY = False  # Allows JavaScript to read cookie
CSRF_COOKIE_SAMESITE = 'Lax'
```

**Warning signs:**
- JSON form submissions work, file uploads fail with 403
- Browser console shows CSRF token cookie but header is missing
- Works in development but fails in production

### Pitfall 6: Pagination Breaks Filtering

**What goes wrong:** User filters table, clicks next page, filter resets and shows all results

**Why it happens:** Pagination link doesn't include filter params, server sees no filter on page 2

**How to avoid:**
```typescript
// CORRECT: Preserve filter params in pagination links
import { router, usePage } from '@inertiajs/react'

export default function Index({ publishers, pagination }: Props) {
    const { url } = usePage()
    const currentParams = new URLSearchParams(url.split('?')[1])

    const goToPage = (pageNum: number) => {
        currentParams.set('page', pageNum.toString())
        router.get(`/?${currentParams.toString()}`, undefined, {
            only: ['publishers', 'pagination'],
            preserveScroll: true,
        })
    }

    return (
        <>
            <DataTable data={publishers} />
            <button onClick={() => goToPage(pagination.current_page + 1)}>
                Next
            </button>
        </>
    )
}

// INCORRECT: Hardcoded page param loses filters
<Link href={`/?page=${pagination.current_page + 1}`}>Next</Link>
```

**Warning signs:**
- Search works on page 1, breaks on page 2
- URL shows `?page=2` but missing `?search=term&page=2`
- User complains "filter disappears when clicking next"

## Code Examples

Verified patterns from official sources:

### Complete Create Form with Validation

```typescript
// scrapegrape/frontend/src/Pages/Publishers/Create.tsx
// Source: https://inertiajs.com/docs/v2/the-basics/forms

import { useForm } from '@inertiajs/react'
import { FormEventHandler } from 'react'
import AppLayout from '@/Layouts/AppLayout'

interface FormData {
    name: string
    url: string
}

function Create() {
    const { data, setData, post, processing, errors, wasSuccessful } = useForm<FormData>({
        name: '',
        url: '',
    })

    const submit: FormEventHandler = (e) => {
        e.preventDefault()
        post('/publishers', {
            onSuccess: () => {
                // Form resets automatically on success if using reset()
            },
        })
    }

    return (
        <div className="container mx-auto py-10 max-w-2xl">
            <h1 className="text-2xl font-bold mb-6">Create Publisher</h1>

            {wasSuccessful && (
                <div className="mb-4 p-4 bg-green-100 text-green-800 rounded">
                    Publisher created successfully!
                </div>
            )}

            <form onSubmit={submit} className="space-y-6">
                <div>
                    <label className="block text-sm font-medium mb-2">
                        Publisher Name
                    </label>
                    <input
                        type="text"
                        value={data.name}
                        onChange={e => setData('name', e.target.value)}
                        className={`w-full px-4 py-2 border rounded ${
                            errors.name ? 'border-red-500' : 'border-gray-300'
                        }`}
                    />
                    {errors.name && (
                        <div className="mt-1 text-sm text-red-600">{errors.name}</div>
                    )}
                </div>

                <div>
                    <label className="block text-sm font-medium mb-2">
                        URL
                    </label>
                    <input
                        type="url"
                        value={data.url}
                        onChange={e => setData('url', e.target.value)}
                        placeholder="https://example.com"
                        className={`w-full px-4 py-2 border rounded ${
                            errors.url ? 'border-red-500' : 'border-gray-300'
                        }`}
                    />
                    {errors.url && (
                        <div className="mt-1 text-sm text-red-600">{errors.url}</div>
                    )}
                </div>

                <div className="flex gap-4">
                    <button
                        type="submit"
                        disabled={processing}
                        className="px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                    >
                        {processing ? 'Creating...' : 'Create Publisher'}
                    </button>

                    <Link href="/" className="px-6 py-2 border rounded hover:bg-gray-50">
                        Cancel
                    </Link>
                </div>
            </form>
        </div>
    )
}

Create.layout = (page) => <AppLayout>{page}</AppLayout>

export default Create
```

### Backend View with InertiaValidationError

```python
# scrapegrape/publishers/views.py
# Source: https://github.com/inertiajs/inertia-django/pull/32

from django.shortcuts import redirect
from inertia import render as inertia_render, InertiaValidationError
from publishers.forms import PublisherForm
from publishers.tasks import analyze_url

def create(request):
    if request.method == 'POST':
        form = PublisherForm(request.POST)
        if form.is_valid():
            publisher = form.save()

            # Trigger background analysis
            analyze_url.enqueue(publisher.url)

            # Flash success message (available via shared data middleware)
            request.session['success'] = f'Publisher "{publisher.name}" created and analysis queued!'

            return redirect('/')
        else:
            # Raise validation error—middleware handles redirect with errors
            raise InertiaValidationError(form.errors, redirect('/publishers/create'))

    # GET request—show empty form
    return inertia_render(request, 'Publishers/Create')


def update(request, publisher_id):
    publisher = get_object_or_404(Publisher, id=publisher_id)

    if request.method == 'POST':
        form = PublisherForm(request.POST, instance=publisher)
        if form.is_valid():
            form.save()
            request.session['success'] = f'Publisher "{publisher.name}" updated!'
            return redirect('/')
        else:
            raise InertiaValidationError(
                form.errors,
                redirect(f'/publishers/{publisher_id}/edit')
            )

    # GET request—show form with existing data
    return inertia_render(request, 'Publishers/Edit', props={
        'publisher': {
            'id': publisher.id,
            'name': publisher.name,
            'url': publisher.url,
        }
    })
```

### Table with Filtering and Partial Reloads

```typescript
// scrapegrape/frontend/src/Pages/Publishers/Index.tsx
// Source: https://inertiajs.com/docs/v2/data-props/partial-reloads

import { router, usePage } from '@inertiajs/react'
import { DataTable } from '@/datatable/table'
import { columns, type Publisher } from '@/datatable/columns'
import { useState, useEffect } from 'react'
import AppLayout from '@/Layouts/AppLayout'

interface Props {
    publishers: Publisher[]
}

function Index({ publishers }: Props) {
    const { url } = usePage()
    const [search, setSearch] = useState(() => {
        const params = new URLSearchParams(url.split('?')[1])
        return params.get('search') || ''
    })

    // Debounced filter
    useEffect(() => {
        const timeout = setTimeout(() => {
            router.get('/',
                { search },
                {
                    only: ['publishers'],
                    preserveScroll: true,
                    preserveState: true,
                    replace: true,  // Don't add to history for each keystroke
                }
            )
        }, 300)

        return () => clearTimeout(timeout)
    }, [search])

    return (
        <div className="container mx-auto py-10">
            <div className="flex justify-between items-center mb-6">
                <h1 className="text-2xl font-bold">Publishers</h1>
                <Link
                    href="/publishers/create"
                    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                >
                    Add Publisher
                </Link>
            </div>

            <div className="mb-4">
                <input
                    type="text"
                    placeholder="Filter by name..."
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    className="px-4 py-2 border rounded w-full max-w-md"
                />
            </div>

            <DataTable columns={columns} data={publishers} />
        </div>
    )
}

Index.layout = (page) => <AppLayout>{page}</AppLayout>

export default Index
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual form state with useState | useForm hook | Inertia v1.0+ | Eliminates 50+ lines of boilerplate, automatic error handling |
| Lazy props (deprecated) | Deferred props with `<Deferred>` | Inertia v2.0 (2024) | Automatic loading, request grouping, better DX |
| Full page reload for filters | Partial reloads with `only` | Inertia v0.8+ | Faster, preserves state, reduces server load |
| XMLHttpRequest for file uploads | useForm with progress | Inertia v1.0+ | Automatic progress tracking, CSRF handling, simpler API |
| Manual scroll position management | preserveScroll option | Inertia v0.9+ | Built-in scroll restoration, works with browser history |
| Papa Parse vanilla | react-papaparse | 2020+ | React hooks, TypeScript support, cleaner integration |

**Deprecated/outdated:**
- `Inertia::lazy()` (Inertia v1) → use `defer()` in v2
- Manual `router.reload()` for updates → use partial reloads with `only`
- `remembering` form state manually → useForm handles via browser history automatically

## Open Questions

1. **Should table filtering be server-side or client-side?**
   - What we know: TanStack Table supports both, current codebase has ~50-200 publishers
   - What's unclear: Will publisher count grow to thousands? Performance threshold?
   - Recommendation: Start client-side (simpler, no partial reload needed). If publishers exceed ~500 rows, migrate to server-side filtering with partial reloads.

2. **Should WAF/ToS data be deferred or always loaded?**
   - What we know: Subquery optimization makes current query fast (~4 queries total)
   - What's unclear: Does deferred loading improve perceived performance enough to justify complexity?
   - Recommendation: Don't defer initially. If table load >1s, profile with Django Debug Toolbar and defer only the slowest queries (likely ToS evaluation).

3. **Should bulk CSV upload process synchronously or async?**
   - What we know: Existing analyze_url task uses django-tasks queue
   - What's unclear: User expectation—wait for completion or background processing?
   - Recommendation: Background processing with task queue (already implemented). Return immediate success with "X URLs queued" message. Add task status page in future phase if needed.

4. **Should pagination preserve filters in URL or component state?**
   - What we know: URL params enable shareable links, component state simpler
   - What's unclear: Does user need to share filtered/paginated views?
   - Recommendation: Store in URL params (search, page, sort). Enables bookmark/share, browser back button works correctly, matches user expectations from traditional web apps.

## Sources

### Primary (HIGH confidence)
- [Inertia.js Forms Documentation](https://inertiajs.com/docs/v2/the-basics/forms) - useForm API, validation, file uploads
- [Inertia.js Partial Reloads](https://inertiajs.com/docs/v2/data-props/partial-reloads) - only/except options
- [Inertia.js Deferred Props](https://inertiajs.com/docs/v2/data-props/deferred-props) - defer() pattern, Deferred component
- [Inertia.js Scroll Management](https://inertiajs.com/docs/v2/advanced/scroll-management) - preserveScroll option
- [Inertia.js File Uploads](https://inertiajs.com/docs/v2/the-basics/file-uploads) - progress tracking
- [django-inertia GitHub](https://github.com/inertiajs/inertia-django) - defer(), InertiaValidationError
- [django-inertia PR #32](https://github.com/inertiajs/inertia-django/pull/32) - InertiaValidationError implementation
- [react-papaparse Documentation](https://react-papaparse.js.org/) - CSV parsing API
- [TanStack Table Filtering Guide](https://tanstack.com/table/latest/docs/guide/column-filtering) - Client-side filtering
- Existing codebase:
  - `.planning/phases/03-core-view-migration/03-RESEARCH.md` - Prior Inertia patterns
  - `scrapegrape/frontend/src/main.tsx` - CSRF configuration
  - `scrapegrape/publishers/tasks.py` - analyze_url task
  - `scrapegrape/scrapegrape/middleware.py` - Shared data for flash messages

### Secondary (MEDIUM confidence)
- [Medium: Server-side Pagination with TanStack Table](https://medium.com/@aylo.srd/server-side-pagination-and-sorting-with-tanstack-table-and-react-bd493170125e) - Pagination patterns
- [LogRocket: Working with CSV files in React](https://blog.logrocket.com/working-csv-files-react-papaparse/) - Papa Parse validation
- [Inertia Rails Validation Guide](https://inertia-rails.dev/guide/validation) - Similar patterns for validation (Rails adapter)

### Tertiary (LOW confidence)
- WebSearch results on CSV upload best practices (general React patterns, not Inertia-specific)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already installed or well-documented, versions verified
- Architecture: HIGH - Official Inertia docs provide complete patterns, existing Phase 3 established foundation
- Pitfalls: MEDIUM-HIGH - Derived from official docs and GitHub issues, some project-specific inference
- CSV upload: MEDIUM - Papa Parse well-documented, integration with useForm straightforward but project-specific
- Deferred props: MEDIUM - Feature documented but django-inertia implementation less mature than Laravel adapter

**Research date:** 2026-02-12
**Valid until:** 2026-03-14 (30 days, stable ecosystem)

**Project-specific notes:**
- Existing analyze_url task perfect for bulk CSV processing (no new infrastructure needed)
- Subquery optimization from Phase 3 MUST be preserved in pagination/filtering views
- CSRF already configured correctly in Phase 1 (axios.defaults)
- Shared data middleware already in place (flash messages ready for form success)
- TanStack Table already supports filtering client-side (no backend changes needed initially)
- Existing serializers work unchanged for partial reloads (PublisherWithReportsSerializer)
