# Phase 6: Infrastructure & Models - Research

**Researched:** 2026-02-14
**Domain:** Django infrastructure (Redis/RQ, data models, pytest, URL normalization)
**Confidence:** HIGH

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Data modeling -- Publisher
- Extend the existing Publisher model in place (preserve existing data and admin functionality)
- One domain = one publisher (keyed by canonical domain, not a multi-domain publisher group)
- Publisher-level discovery results (WAF, ToS, robots.txt, etc.) stored as flat fields on Publisher, not separate models or JSON
- Freshness TTL configured as a single Django setting (`PUBLISHER_FRESHNESS_TTL`), same for all publishers

#### Data modeling -- ResolutionJob
- Every URL always resolves to a publisher (create on the fly if it doesn't exist)
- Job identified by UUID (e.g., `/jobs/550e8400-e29b...`)
- Pipeline step results (waf_result, tos_result, etc.) stored on the job itself -- job is the complete record of what happened for that URL submission
- Duplicate URL submissions redirect to the existing job's results (no new job created)

#### URL normalization
- Use a well-established third-party package -- don't hand-roll normalization logic
- Strip known tracking parameters (utm_*, fbclid, etc.) but keep other query params
- www and bare domain treated as same publisher (strip www)
- Strip URL fragments (#section)
- Preserve trailing slashes as-is

### Claude's Discretion
- Docker/services topology and docker-compose structure
- Test conventions, factory patterns, fixture strategy
- Choice of URL normalization package
- Exact fields and types on Publisher and ResolutionJob models

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

## Summary

Phase 6 establishes the developer foundation for v2.0: Redis/RQ task infrastructure in Docker, extended data models (Publisher + new ResolutionJob), pytest with factory_boy, and a URL normalization utility. The existing codebase uses `django_tasks` with a database backend, which will be replaced by `django-rq` backed by Redis. The existing Publisher model has three fields (name, url, detected_waf) and needs extension with discovery result fields. No ResolutionJob model exists yet.

The standard stack for this phase is well-established and stable: `django-rq` 3.2.2 for task queuing, `w3lib` 2.3.1 for URL canonicalization (from the Scrapy ecosystem), `pytest-django` 4.11.1 + `factory-boy` 3.3.3 for testing, and Redis 7 in Docker. All libraries are production-stable with active maintenance.

**Primary recommendation:** Use w3lib's `canonicalize_url` + `url_query_cleaner` for URL normalization (handles query sorting, fragment stripping, percent-encoding), with a thin wrapper for www-stripping and tracking param removal. Use django-rq 3.2.2 with Redis 7-alpine in Docker. Configure pytest-django in pyproject.toml with factory_boy DjangoModelFactory for test data.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| django-rq | 3.2.2 | Django integration for RQ (Redis Queue) | Standard Django task queue; replaces django_tasks; built-in admin dashboard |
| rq | 2.6.1 | Redis-backed job queue | Dependency of django-rq; simple, reliable job processing |
| redis (Python) | 7.1.1 | Redis client for Python | Required by rq/django-rq for Redis connection |
| w3lib | 2.3.1 | URL canonicalization and query cleaning | Battle-tested in Scrapy ecosystem; handles sorting, encoding, fragments |
| pytest | latest | Python test runner | Standard for modern Python projects |
| pytest-django | 4.11.1 | Django integration for pytest | Standard pytest plugin for Django; provides db fixtures |
| factory-boy | 3.3.3 | Test data factories | Standard for Django test data; DjangoModelFactory with ORM integration |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-cov | latest | Test coverage reporting | Run with `--cov` flag to measure coverage |
| Redis 7 (Docker) | 7-alpine | In-memory data store for job queue | Docker service; persistent volume for job durability |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| w3lib | url-normalize 2.2.1 | url-normalize does NOT sort query params, does NOT strip fragments by default, and its `filter_params` mode is an allowlist (strips everything not whitelisted) rather than a denylist. w3lib is better suited. |
| w3lib | hand-rolled urllib.parse | Misses edge cases: percent-encoding normalization, IDN handling, consistent query sorting. User decision explicitly says don't hand-roll. |
| factory-boy | pytest-factoryboy | pytest-factoryboy wraps factory-boy with auto-fixture registration. Adds complexity; plain factory-boy + conftest fixtures is simpler and sufficient. |
| django-rq | celery | Celery is much heavier; RQ is simpler, sufficient for this project's needs, and the user's roadmap already specifies RQ. |

**Installation:**
```bash
uv add django-rq w3lib pytest pytest-django factory-boy pytest-cov
```

## Architecture Patterns

### Recommended Project Structure
```
scrapegrape/
├── publishers/
│   ├── models.py          # Publisher (extended), ResolutionJob (new)
│   ├── admin.py           # Updated admin with django-rq dashboard link
│   ├── factories.py       # factory_boy factories for Publisher, ResolutionJob
│   ├── urls.py            # URL normalization utility module
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_models.py
│   │   ├── test_url_sanitizer.py
│   │   └── test_factories.py
│   └── ...
├── conftest.py            # Root conftest with shared fixtures
└── scrapegrape/
    └── settings.py        # RQ_QUEUES config, PUBLISHER_FRESHNESS_TTL
```

### Pattern 1: django-rq Configuration
**What:** Configure RQ queues in Django settings pointing to Redis Docker service
**When to use:** All task queue configuration
**Example:**
```python
# scrapegrape/scrapegrape/settings.py
# Source: https://github.com/rq/django-rq

INSTALLED_APPS = [
    # ... existing apps ...
    "django_rq",
    # REMOVE: "django_tasks",
    # REMOVE: "django_tasks.backends.database",
]

RQ_QUEUES = {
    "default": {
        "HOST": "redis",  # Docker service name
        "PORT": 6379,
        "DB": 0,
        "DEFAULT_TIMEOUT": 600,  # 10 minutes for pipeline jobs
    },
}

# Remove the old TASKS setting
# TASKS = {"default": {"BACKEND": "django_tasks.backends.database.DatabaseBackend"}}

# Freshness TTL for publisher-level discovery (locked decision)
from datetime import timedelta
PUBLISHER_FRESHNESS_TTL = timedelta(hours=24)
```

### Pattern 2: django-rq Admin Integration
**What:** django-rq 3.2.2 auto-registers admin views at `/admin/django_rq/`
**When to use:** No URL configuration needed; just add `django_rq` to INSTALLED_APPS
**Example:**
```python
# urls.py -- NO changes needed for admin integration
# django-rq auto-registers its dashboard in Django admin since v3.x
# Dashboard accessible at /admin/django_rq/dashboard/

# If standalone URL is desired (optional):
# urlpatterns += [path("django-rq/", include("django_rq.urls"))]
```

### Pattern 3: Job Definition with @job Decorator
**What:** Define RQ jobs using django-rq's `@job` decorator
**When to use:** All background task definitions
**Example:**
```python
# Source: https://github.com/rq/django-rq
from django_rq import job

@job("default", timeout=600)
def run_pipeline(job_id: str) -> dict:
    """Pipeline supervisor job -- implemented in Phase 8."""
    pass
```

### Pattern 4: URL Normalization with w3lib
**What:** Canonicalize URLs and strip tracking params using w3lib utilities
**When to use:** Every URL submission, publisher domain extraction
**Example:**
```python
# Source: https://w3lib.readthedocs.io/en/latest/w3lib.html
from urllib.parse import urlparse, urlunparse
from w3lib.url import canonicalize_url, url_query_cleaner

# Tracking parameters to strip (denylist approach)
TRACKING_PARAMS = [
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "gclsrc", "dclid", "gbraid", "wbraid",
    "msclkid", "twclid", "igshid", "mc_cid", "mc_eid",
    "oly_anon_id", "oly_enc_id", "_openstat",
    "vero_id", "wickedid", "yclid", "rb_clickid",
    "s_cid", "mkt_tok", "trk", "trkCampaign", "trkInfo",
]

def sanitize_url(url: str) -> str:
    """Normalize a URL to its canonical form.

    Steps:
    1. Canonicalize (sort query params, strip fragments, normalize encoding)
    2. Strip tracking parameters
    3. Strip www. from hostname
    4. Enforce https scheme
    """
    # Step 1: w3lib canonicalization (sorts query params, strips fragments,
    # normalizes percent-encoding)
    canonical = canonicalize_url(url, keep_fragments=False)

    # Step 2: Strip tracking params (denylist -- keep everything else)
    cleaned = url_query_cleaner(canonical, TRACKING_PARAMS, remove=True)

    # Step 3: Strip www. from hostname
    parsed = urlparse(cleaned)
    hostname = parsed.hostname or ""
    if hostname.startswith("www."):
        hostname = hostname[4:]
    cleaned = urlunparse(parsed._replace(netloc=hostname + (
        f":{parsed.port}" if parsed.port and parsed.port not in (80, 443) else ""
    )))

    # Step 4: Enforce https
    if cleaned.startswith("http://"):
        cleaned = "https://" + cleaned[7:]

    return cleaned


def extract_domain(url: str) -> str:
    """Extract the canonical domain from a URL for publisher lookup."""
    sanitized = sanitize_url(url)
    parsed = urlparse(sanitized)
    return parsed.hostname or ""
```

### Pattern 5: ResolutionJob with UUID Primary Key
**What:** Use Django UUIDField as primary key for job identification
**When to use:** ResolutionJob model
**Example:**
```python
import uuid
from django.db import models

class ResolutionJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # URL that was submitted
    submitted_url = models.URLField()
    # Canonical form after sanitization
    canonical_url = models.URLField(db_index=True)
    # Link to publisher (always exists)
    publisher = models.ForeignKey("Publisher", on_delete=models.CASCADE, related_name="resolution_jobs")
    # Job lifecycle
    status = models.CharField(max_length=20, default="pending",
        choices=[
            ("pending", "Pending"),
            ("running", "Running"),
            ("completed", "Completed"),
            ("failed", "Failed"),
        ])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Pipeline step results stored directly on the job (locked decision)
    waf_result = models.JSONField(null=True, blank=True)
    tos_result = models.JSONField(null=True, blank=True)
    robots_result = models.JSONField(null=True, blank=True)
    sitemap_result = models.JSONField(null=True, blank=True)
    rss_result = models.JSONField(null=True, blank=True)
    rsl_result = models.JSONField(null=True, blank=True)
    metadata_result = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["canonical_url"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Job {self.id} - {self.canonical_url} ({self.status})"
```

### Pattern 6: Extended Publisher Model
**What:** Add discovery result fields as flat fields on Publisher
**When to use:** Publisher model extension (locked decision)
**Example:**
```python
class Publisher(models.Model):
    # Existing fields (preserved)
    name = models.CharField(max_length=255)
    url = models.URLField()
    detected_waf = models.CharField(max_length=255, blank=True, null=True)

    # NEW: Canonical domain for publisher lookup
    domain = models.CharField(max_length=255, unique=True, db_index=True)

    # NEW: Discovery result flat fields (populated by pipeline)
    waf_type = models.CharField(max_length=255, blank=True, default="")
    waf_detected = models.BooleanField(default=False)
    tos_url = models.URLField(blank=True, default="")
    tos_permissions = models.JSONField(null=True, blank=True)
    robots_txt_found = models.BooleanField(null=True)
    robots_txt_url_allowed = models.BooleanField(null=True)
    sitemap_urls = models.JSONField(default=list, blank=True)
    rss_urls = models.JSONField(default=list, blank=True)
    rsl_detected = models.BooleanField(null=True)

    # NEW: Freshness tracking
    last_checked_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name
```

### Pattern 7: pytest-django Configuration in pyproject.toml
**What:** Configure pytest with Django settings module
**When to use:** Project-level test configuration
**Example:**
```toml
# pyproject.toml
[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "scrapegrape.settings"
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
# Run pytest from the scrapegrape/ directory where manage.py lives
pythonpath = ["scrapegrape"]
```

### Pattern 8: factory_boy DjangoModelFactory
**What:** Create test data factories for models
**When to use:** All test files needing model instances
**Example:**
```python
# scrapegrape/publishers/factories.py
# Source: https://factoryboy.readthedocs.io/en/stable/orms.html
import uuid
import factory
from publishers.models import Publisher, ResolutionJob


class PublisherFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Publisher
        django_get_or_create = ("domain",)

    name = factory.Sequence(lambda n: f"publisher-{n}.com")
    url = factory.LazyAttribute(lambda o: f"https://{o.name}")
    domain = factory.LazyAttribute(lambda o: o.name)


class ResolutionJobFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ResolutionJob

    id = factory.LazyFunction(uuid.uuid4)
    submitted_url = factory.Sequence(lambda n: f"https://example-{n}.com/article")
    canonical_url = factory.LazyAttribute(lambda o: o.submitted_url)
    publisher = factory.SubFactory(PublisherFactory)
    status = "pending"
```

### Anti-Patterns to Avoid
- **Using `django_tasks` alongside `django-rq`:** Remove `django_tasks` and `django_tasks.backends.database` from INSTALLED_APPS. They cannot coexist gracefully.
- **UUID as string field:** Use `models.UUIDField`, not `CharField`. Django handles UUID natively with PostgreSQL's `uuid` type.
- **Hand-rolling URL normalization:** Use w3lib. Edge cases in URL parsing (IDN, percent-encoding, unicode) are deceptively complex.
- **Putting factories in conftest.py:** Keep factories in `factories.py` per app. Import them in conftest or test files. This keeps factories reusable across test files.
- **Using `is_async=False` globally in settings for tests:** Instead, use `is_async=False` only when getting queues in test code, or use `get_worker().work(burst=True)` pattern.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| URL normalization | Custom urllib.parse logic | `w3lib.url.canonicalize_url` + `url_query_cleaner` | Percent-encoding edge cases, IDN domains, query param sorting -- hundreds of edge cases |
| Tracking param detection | Regex-based URL param parser | `url_query_cleaner` with TRACKING_PARAMS denylist | Robust query string parsing handles encoding, duplicate params |
| Task queue | Custom Redis pub/sub | django-rq / RQ | Job serialization, retry logic, failure handling, admin monitoring |
| Test data creation | Manual `Model.objects.create()` | factory_boy `DjangoModelFactory` | Handles relationships, sequences, defaults; keeps tests DRY |
| UUID generation | Random string IDs | `models.UUIDField(default=uuid.uuid4)` | PostgreSQL native UUID type; proper indexing; Django admin support |
| Redis healthcheck | Custom ping scripts | Docker Compose healthcheck with `redis-cli ping` | Standard Docker pattern; `depends_on: condition: service_healthy` |

**Key insight:** URL normalization is the most deceptive trap in this phase. RFC 3986 normalization has dozens of edge cases (unicode normalization, IDN punycode, percent-encoding case, default port removal, path dot-segment removal). w3lib handles these because it has been battle-tested in the Scrapy web scraping framework processing millions of URLs.

## Common Pitfalls

### Pitfall 1: django_tasks Removal Breaks Existing Code
**What goes wrong:** The existing `tasks.py` uses `@task` from `django_tasks` and `.enqueue()`. Admin actions call `analyze_url.enqueue()`. Simply removing django_tasks breaks all of these.
**Why it happens:** The `@task` decorator and `.enqueue()` API are django_tasks-specific.
**How to avoid:** Replace `from django_tasks import task` with `from django_rq import job`. Replace `analyze_url.enqueue(url)` with `analyze_url.delay(url)`. Update all admin action code that calls `.enqueue()`.
**Warning signs:** `ImportError: No module named 'django_tasks'` or AttributeError on `.enqueue()`.

### Pitfall 2: Redis Connection Refused in Django Container
**What goes wrong:** Django container starts before Redis is ready, RQ connections fail.
**Why it happens:** Docker Compose `depends_on` without `condition: service_healthy` only waits for container start, not service readiness.
**How to avoid:** Add Redis healthcheck (`redis-cli ping`) and use `depends_on: redis: condition: service_healthy` on both django and worker services.
**Warning signs:** `redis.exceptions.ConnectionError: Error 111 connecting to redis:6379. Connection refused.`

### Pitfall 3: Worker Service Uses Wrong Working Directory
**What goes wrong:** RQ worker can't find Django settings or app modules.
**Why it happens:** The worker runs `manage.py rqworker` but the working directory or PYTHONPATH isn't set correctly in Docker.
**How to avoid:** Worker service should use the same image, volumes, and env_file as the Django service. The command should be: `uv run scrapegrape/manage.py rqworker default`.
**Warning signs:** `ModuleNotFoundError` or `django.core.exceptions.ImproperlyConfigured`.

### Pitfall 4: Publisher Migration Destroys Existing Data
**What goes wrong:** Adding a `unique` constraint on a new `domain` field fails if existing publishers have no domain value.
**Why it happens:** Django migration tries to add unique+non-null field to existing rows.
**How to avoid:** Use a multi-step migration: (1) add field as nullable, (2) run data migration to populate domain from existing url field, (3) add unique constraint. Or add with `default=""` first, populate, then add unique.
**Warning signs:** `django.db.utils.IntegrityError: UNIQUE constraint failed` or `NOT NULL constraint failed`.

### Pitfall 5: pytest Can't Find Django Settings
**What goes wrong:** `uv run pytest` fails with Django configuration error.
**Why it happens:** pytest needs to know where the Django settings module is. The scrapegrape project has a nested structure: `scrapegrape/scrapegrape/settings.py`.
**How to avoid:** Set `DJANGO_SETTINGS_MODULE = "scrapegrape.settings"` in pyproject.toml `[tool.pytest.ini_options]` AND set `pythonpath = ["scrapegrape"]` so Python can find the module.
**Warning signs:** `django.core.exceptions.ImproperlyConfigured: Requested setting...` or `ModuleNotFoundError: No module named 'scrapegrape.settings'`.

### Pitfall 6: url_query_cleaner with remove=True Removes All Params
**What goes wrong:** Passing the wrong value for `remove` parameter strips wanted params or keeps unwanted ones.
**Why it happens:** `url_query_cleaner(url, params)` KEEPS only listed params by default. You must pass `remove=True` to REMOVE the listed params instead.
**How to avoid:** Always use `url_query_cleaner(url, TRACKING_PARAMS, remove=True)` -- the `remove=True` flag inverts the behavior to strip the listed params.
**Warning signs:** URLs losing all query parameters, or tracking params surviving sanitization.

### Pitfall 7: Duplicate canonical_url Index on ResolutionJob
**What goes wrong:** Looking up existing jobs by canonical_url is slow without an index.
**Why it happens:** The duplicate-detection logic (`Duplicate URL submissions redirect to the existing job's results`) needs fast lookups by canonical_url.
**How to avoid:** Add `db_index=True` on `canonical_url` field, or add an explicit index in Meta.indexes.
**Warning signs:** Slow duplicate detection as job count grows.

## Code Examples

Verified patterns from official sources:

### Docker Compose with Redis, Worker, and Healthchecks
```yaml
# docker-compose.yml (updated from existing)
# Source: https://github.com/rq/django-rq, Redis Docker Hub
services:
  postgres:
    image: postgres:17
    environment:
      POSTGRES_DB: scrapegrape
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  django:
    build: .
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    env_file: scrapegrape/.env
    environment:
      DATABASE_URL: postgres://postgres:postgres@postgres:5432/scrapegrape
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: uv run scrapegrape/manage.py runserver 0.0.0.0:8000

  worker:
    build: .
    volumes:
      - .:/app
    env_file: scrapegrape/.env
    environment:
      DATABASE_URL: postgres://postgres:postgres@postgres:5432/scrapegrape
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: uv run scrapegrape/manage.py rqworker default

  vite:
    image: node:24-slim
    working_dir: /app
    volumes:
      - ./scrapegrape/frontend:/app
      - vite_node_modules:/app/node_modules
    ports:
      - "5173:5173"
    command: sh -c "npm install && npm run dev"

volumes:
  postgres_data:
  redis_data:
  vite_node_modules:
```

### RQ_QUEUES Settings Configuration
```python
# scrapegrape/scrapegrape/settings.py
# Source: https://github.com/rq/django-rq

RQ_QUEUES = {
    "default": {
        "HOST": os.environ.get("REDIS_HOST", "redis"),
        "PORT": int(os.environ.get("REDIS_PORT", 6379)),
        "DB": 0,
        "DEFAULT_TIMEOUT": 600,
    },
}
```

### pytest conftest.py with Shared Fixtures
```python
# scrapegrape/conftest.py
import pytest
from publishers.factories import PublisherFactory, ResolutionJobFactory


@pytest.fixture
def publisher(db):
    """Create a test publisher."""
    return PublisherFactory()


@pytest.fixture
def resolution_job(db):
    """Create a test resolution job with associated publisher."""
    return ResolutionJobFactory()
```

### Testing django-rq Jobs
```python
# Source: https://github.com/rq/django-rq
from django.test import TestCase, override_settings
from django_rq import get_queue

# For tests, use synchronous mode (no Redis needed)
@pytest.mark.django_db
def test_job_execution():
    queue = get_queue("default", is_async=False)
    result = queue.enqueue(my_job_function, arg1, arg2)
    # Job executes immediately in sync mode
    assert result.return_value == expected_value
```

### URL Sanitization Test Examples
```python
# scrapegrape/publishers/tests/test_url_sanitizer.py
import pytest
from publishers.url_sanitizer import sanitize_url, extract_domain


class TestSanitizeUrl:
    def test_strips_www(self):
        assert sanitize_url("https://www.example.com/page") == "https://example.com/page"

    def test_bare_domain_matches_www(self):
        assert sanitize_url("https://www.example.com/page") == sanitize_url("https://example.com/page")

    def test_strips_fragments(self):
        assert sanitize_url("https://example.com/page#section") == "https://example.com/page"

    def test_sorts_query_params(self):
        assert sanitize_url("https://example.com/?z=1&a=2") == "https://example.com/?a=2&z=1"

    def test_strips_utm_params(self):
        result = sanitize_url("https://example.com/page?id=1&utm_source=fb&utm_medium=social")
        assert result == "https://example.com/page?id=1"

    def test_strips_fbclid(self):
        result = sanitize_url("https://example.com/page?id=1&fbclid=abc123")
        assert result == "https://example.com/page?id=1"

    def test_lowercase_hostname(self):
        assert sanitize_url("https://EXAMPLE.COM/Page") == "https://example.com/Page"

    def test_preserves_trailing_slash(self):
        assert sanitize_url("https://example.com/page/") == "https://example.com/page/"

    def test_normalizes_http_to_https(self):
        assert sanitize_url("http://example.com/page") == "https://example.com/page"

    def test_unicode_url(self):
        # w3lib handles unicode percent-encoding
        result = sanitize_url("https://example.com/r\u00e9sum\u00e9")
        assert "example.com" in result

    def test_preserves_non_tracking_query_params(self):
        result = sanitize_url("https://example.com/search?q=test&page=2")
        assert "q=test" in result
        assert "page=2" in result

    def test_mixed_case_scheme(self):
        assert sanitize_url("HTTP://example.com") == "https://example.com/"


class TestExtractDomain:
    def test_extracts_domain(self):
        assert extract_domain("https://www.nytimes.com/article/123") == "nytimes.com"

    def test_strips_www_from_domain(self):
        assert extract_domain("https://www.bbc.co.uk/news") == "bbc.co.uk"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| django_tasks (database backend) | django-rq (Redis backend) | Phase 6 migration | Real worker processes; admin dashboard; production-grade job queue |
| No test framework | pytest + pytest-django + factory_boy | Phase 6 setup | TDD-ready; factory-based test data; Django db fixtures |
| Manual URL parsing in tasks.py | w3lib canonicalize_url | Phase 6 setup | Consistent URL normalization across entire application |
| BigAutoField PKs only | UUIDField PK for ResolutionJob | Phase 6 setup | URL-safe job identifiers; no sequential ID exposure |

**Deprecated/outdated:**
- `django_tasks.backends.database.DatabaseBackend`: Being replaced by django-rq. Remove from INSTALLED_APPS and delete TASKS setting.
- The existing `normalize_url()` function in `publishers/tasks.py`: Primitive; only extracts netloc. Will be replaced by the w3lib-based sanitizer.

## Open Questions

1. **Publisher data migration strategy**
   - What we know: Publisher model needs new `domain` field (unique). Existing publishers have `url` field but no `domain`.
   - What's unclear: How many existing publishers exist in production? Are there any with duplicate domains?
   - Recommendation: Write a data migration that populates `domain` from existing `url` field using the same `extract_domain()` logic. Handle duplicates by keeping the first and logging warnings.

2. **RQ_QUEUES HOST for local development without Docker**
   - What we know: Docker worker connects to `redis` (service name). Local `uv run pytest` needs `localhost`.
   - What's unclear: Whether tests should use real Redis or mock it.
   - Recommendation: Use `os.environ.get("REDIS_HOST", "localhost")` in settings. For tests, use `is_async=False` queue mode which bypasses Redis entirely. This way tests don't need Redis running.

3. **ResolutionJob result field types**
   - What we know: Pipeline step results stored on job as JSONField (locked decision).
   - What's unclear: Exact schema of each result field -- this will be defined in Phase 8.
   - Recommendation: Use `models.JSONField(null=True, blank=True)` for all result fields now. Schema validation can be added later with Pydantic models when pipeline steps are implemented.

## Sources

### Primary (HIGH confidence)
- [django-rq GitHub](https://github.com/rq/django-rq) - Setup, configuration, job decorator, testing, admin integration
- [django-rq PyPI](https://pypi.org/project/django-rq/) - Version 3.2.2, released Dec 24, 2025
- [w3lib docs](https://w3lib.readthedocs.io/en/latest/w3lib.html) - canonicalize_url API, url_query_cleaner API, normalization steps
- [w3lib PyPI](https://pypi.org/project/w3lib/) - Version 2.3.1, released Jan 27, 2025
- [factory_boy docs](https://factoryboy.readthedocs.io/en/stable/orms.html) - DjangoModelFactory, Meta options, SubFactory
- [factory-boy PyPI](https://pypi.org/project/factory-boy/) - Version 3.3.3, released Feb 3, 2025
- [pytest-django docs](https://pytest-django.readthedocs.io/en/latest/configuring_django.html) - DJANGO_SETTINGS_MODULE configuration
- [pytest-django PyPI](https://pypi.org/project/pytest-django/) - Version 4.11.1
- [RQ PyPI](https://pypi.org/project/rq/) - Version 2.6.1 (requires Redis >= 5)
- [redis-py PyPI](https://pypi.org/project/redis/) - Version 7.1.1, released Feb 9, 2026

### Secondary (MEDIUM confidence)
- [url-normalize GitHub](https://github.com/niksite/url-normalize) - Investigated and rejected; allowlist-based param filtering, no query sorting, no fragment stripping
- [Redis Docker healthcheck guide](https://bobcares.com/blog/redis-docker-compose-healthcheck/) - Healthcheck configuration patterns
- [django-rq Docker demo](https://github.com/ActionScripted/django-rq-demo) - Docker Compose service topology

### Tertiary (LOW confidence)
- None. All critical claims verified with primary sources.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All versions verified on PyPI with release dates; APIs verified in official docs
- Architecture: HIGH - Docker Compose patterns are well-established; django-rq configuration is straightforward
- URL normalization: HIGH - w3lib canonicalize_url behavior verified in official docs; url_query_cleaner `remove=True` semantics confirmed; url-normalize limitations confirmed by reading source code
- Pitfalls: HIGH - Based on analysis of actual existing codebase (django_tasks usage, Docker Compose structure, nested Django project layout)
- Model design: MEDIUM - Exact field choices for Publisher extension are reasonable but will evolve as pipeline steps are implemented in later phases

**Research date:** 2026-02-14
**Valid until:** 2026-03-14 (30 days -- all libraries are stable/mature)
