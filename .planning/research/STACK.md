# Technology Stack: v2.0 URL Analysis Workflow

**Project:** itsascout (scrapegrape)
**Researched:** 2026-02-13
**Scope:** NEW stack additions for single-URL analysis with streaming progress, metadata extraction, and publisher report card

## Context: Existing Stack (validated in v1.0 -- DO NOT change)

- Django 5.2 + DRF + Inertia.js 1.2 + React 19.1 + Vite + TailwindCSS
- PostgreSQL 17 via `dj-database-url`
- `pydantic-ai-slim[openai]` for LLM tasks (GPT-4.1-nano)
- `wafw00f` for WAF detection
- `requests` for Zyte proxy API calls
- `django_tasks` with DatabaseBackend for async tasks
- `httpx` (in dependencies)
- `loguru` + `logfire` for logging/observability
- WSGI deployment (`WSGI_APPLICATION` in settings)

---

## Recommended Stack Additions

### 1. HTTP Client: curl-cffi (Primary Fetcher) + Zyte (Fallback)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| curl-cffi | >=0.14.0 | Primary HTTP client with browser TLS fingerprinting | Bypasses bot detection via JA3/TLS impersonation; 20-30% faster than httpx; async support; HTTP/2 and HTTP/3; reduces Zyte API costs |

**Why curl-cffi over httpx or requests:**

Publisher websites block automated HTTP clients via TLS fingerprinting. Neither `requests` nor `httpx` (both already in deps) can impersonate real browser TLS signatures. curl-cffi impersonates Chrome/Safari TLS fingerprints, achieving 15x higher evasion rates. This makes it the correct primary client for fetching arbitrary publisher pages without needing a proxy.

**Fetching strategy:** curl-cffi with `impersonate="chrome"` as first attempt. Fall back to existing Zyte proxy API (via `requests` in `ingestion/services.py`) only when curl-cffi gets a 403, captcha, or Cloudflare challenge. This significantly reduces Zyte API cost per analysis.

**Integration note:** curl-cffi requires C libraries (bundled in the PyPI wheel). The project Dockerfile uses `python:3.12-slim` -- the manylinux wheel should install cleanly via `uv sync`. No additional apt packages expected, but verify during Docker build.

**What NOT to do:** Do not replace `requests` in the existing Zyte `fetch_html_via_proxy()` function. Zyte does not need TLS impersonation. Keep `requests` for Zyte, use curl-cffi only for direct publisher fetching.

```python
# Sync usage
from curl_cffi.requests import Session

with Session(impersonate="chrome") as s:
    response = s.get(url, timeout=15)

# Async usage
from curl_cffi.requests import AsyncSession

async with AsyncSession(impersonate="chrome") as s:
    response = await s.get(url, timeout=15)
```

**Confidence:** HIGH -- v0.14.0 current on PyPI, actively maintained, Python 3.10+ required (project uses 3.12).

### 2. Task Queue: django-rq + Redis (replacing django_tasks for new pipeline)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| django-rq | >=3.0 | Django integration for RQ task queue | Simpler than Celery; built-in admin panel; management command workers; worker pool support; job status + meta tracking |
| rq | >=2.6.1 | Redis-backed job queue (pulled in by django-rq) | Lightweight; worker pool; job.meta for progress reporting |
| redis (Python client) | >=5.0 | Redis client library (pulled in by rq) | Required by rq |
| Redis (server) | 7.x (Docker image: redis:7-alpine) | Message broker | Single infrastructure addition; also usable as Django cache later |

**Why django-rq over Celery:**

Celery is overkill. It requires complex configuration (beat, flower, result backends, serializers), supports multiple brokers we do not need (RabbitMQ), and has a steep learning curve. The v2.0 pipeline processes one URL at a time through ~10 sequential steps. RQ's simplicity wins decisively.

**Why django-rq over the existing django_tasks DatabaseBackend:**

The current `django_tasks` with `DatabaseBackend` has critical limitations:
- No real worker process (polls the database)
- No job status tracking or progress reporting
- No retry logic
- No `job.meta` dict for storing pipeline step progress

The v2.0 pipeline needs real background workers that report per-step progress back to the frontend via SSE. RQ's `job.meta` dict is the mechanism: the worker updates `job.meta` with current step info, and the SSE endpoint reads it.

**Key django-rq 3.0+ features:**
- `python manage.py rqworker default` -- workers via Django management command
- `python manage.py rqworker-pool default --num-workers 2` -- worker pool
- Default `on_db_commit` mode -- jobs enqueue after DB transaction commits (safe with Django ORM)
- Built-in Django admin integration at `/admin/django-rq/`
- `job.get_status()` returns: queued, started, finished, failed, stopped
- `job.meta` dict persists arbitrary data (pipeline progress)

**Migration strategy:** Keep `django_tasks` for existing bulk ingestion. Use django-rq exclusively for the new v2.0 single-URL analysis pipeline. Migrate bulk ingestion to django-rq in a future milestone.

```python
# Enqueueing a job
import django_rq

queue = django_rq.get_queue("default")
job = queue.enqueue(analyze_single_url, url)
# job.id is the identifier for SSE progress tracking

# Inside the worker task -- updating progress
from rq import get_current_job

def analyze_single_url(url: str):
    job = get_current_job()
    job.meta["step"] = "fetching_html"
    job.meta["progress"] = 1
    job.meta["total_steps"] = 10
    job.save_meta()

    html = fetch_with_curl_cffi(url)

    job.meta["step"] = "extracting_metadata"
    job.meta["progress"] = 2
    job.save_meta()
    # ... etc
```

**Confidence:** HIGH -- django-rq 3.0+ supports Django 5.x, RQ 2.0+. Well-documented pattern.

### 3. Server-Sent Events: Django StreamingHttpResponse + Native EventSource

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Django StreamingHttpResponse | (built-in Django) | SSE endpoint for pipeline progress | No additional dependency needed; native streaming |
| EventSource API | (built-in browser) | Client-side SSE consumption | All modern browsers; automatic reconnection; zero npm packages needed |

**Why no django-eventstream, no WebSockets, no third-party library:**

The SSE use case is simple: one client watches one job progress through ~10 pipeline steps for 30-60 seconds. This does not need django-eventstream's channel abstraction, WebSocket bidirectionality, or ASGI migration.

**How SSE works alongside Inertia.js:**

SSE endpoints BYPASS Inertia entirely. They are separate Django URL routes that return `StreamingHttpResponse` (not Inertia page responses). The React frontend opens an `EventSource` connection to the SSE endpoint alongside the Inertia-rendered page.

```python
# urls.py -- SSE endpoint is a plain Django view, NOT an Inertia route
urlpatterns = [
    # Inertia routes (existing)
    path("", publishers.views.table, name="table"),
    # SSE route (new, separate)
    path("api/analysis/<str:job_id>/progress", analysis_views.progress_stream, name="analysis-progress"),
]
```

```python
# Django SSE view
from django.http import StreamingHttpResponse
import django_rq, json, time

def progress_stream(request, job_id):
    def event_stream():
        queue = django_rq.get_queue("default")
        while True:
            job = queue.fetch_job(job_id)
            if job is None:
                yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                return
            status = job.get_status()
            meta = job.meta or {}
            yield f"data: {json.dumps({'status': status, **meta})}\n\n"
            if status in ("finished", "failed"):
                return
            time.sleep(1)

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"  # Disable nginx buffering if fronted by nginx
    return response
```

```typescript
// React hook (inside Inertia page component)
useEffect(() => {
  const source = new EventSource(`/api/analysis/${jobId}/progress`);
  source.onmessage = (event) => {
    const data = JSON.parse(event.data);
    setProgress(data);
    if (data.status === "finished" || data.status === "failed") {
      source.close();
    }
  };
  source.onerror = () => source.close();
  return () => source.close();
}, [jobId]);
```

**WSGI compatibility:** Under WSGI (gunicorn), each SSE connection ties up one worker thread for its duration. For single-user-watching-single-job (30-60 seconds), this is acceptable with `gunicorn --worker-class gthread --threads 4`. Do NOT switch to ASGI/Daphne/Uvicorn just for this -- the complexity is not justified for the expected concurrent load.

**Gunicorn config adjustment:**
```bash
gunicorn scrapegrape.wsgi:application \
  --worker-class gthread \
  --workers 2 \
  --threads 4 \
  --timeout 120  # Allow SSE connections up to 2 minutes
```

**Confidence:** HIGH -- StreamingHttpResponse is core Django; EventSource is a W3C standard. Pattern is well-documented across multiple sources.

### 4. Metadata Extraction: extruct

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| extruct | >=0.18.0 | Extract JSON-LD, OpenGraph, Microdata, RDFa, Microformat from HTML | Single library covering all structured metadata formats; from Scrapinghub (Zyte's parent company); battle-tested at scale |

**What it extracts (all from a single HTML string):**
- **JSON-LD** -- Schema.org structured data (articles, organizations, breadcrumbs)
- **OpenGraph** -- Facebook/social metadata (og:title, og:type, og:image, og:description)
- **Microdata** -- HTML5 itemscope/itemprop attributes
- **RDFa** -- Semantic web annotations
- **Microformat** -- hCard, hEntry patterns (via mf2py)
- **Dublin Core** -- DC metadata

```python
import extruct

metadata = extruct.extract(
    html_string,
    base_url=url,
    syntaxes=["json-ld", "opengraph", "microdata"],  # Only extract what we need
    uniform=True,  # Normalize output format across syntaxes
)
# Returns: {"json-ld": [...], "opengraph": [...], "microdata": [...]}
```

**Transitive dependencies:** lxml, w3lib, rdflib, mf2py, html-text, jstyleson. The `lxml` C extension is the heaviest -- the manylinux wheel should install on `python:3.12-slim` without additional apt packages. Test during Docker build.

**Confidence:** HIGH -- v0.18.0 released Nov 2024, stable, Python 3.12 compatible.

### 5. Robots.txt Parsing: protego

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| protego | >=0.3.1 | Parse robots.txt files per RFC 9309 | Battle-tested in Scrapy; handles wildcards and $ anchors correctly; extracts Sitemap: directives |

**Why protego over stdlib urllib.robotparser:**

`urllib.robotparser` has known bugs and does not fully implement RFC 9309 (the current robots.txt standard). It mishandles wildcard patterns and `$` anchors. protego is the parser used by Scrapy, tested against millions of real-world robots.txt files.

**Why protego over robotspy:**

robotspy (v0.12.0) is RFC 9309 compliant but has a smaller user base. protego's Scrapy lineage gives more confidence for edge cases.

**Key capabilities needed:**
- Check if URL is allowed/disallowed for a user-agent
- Extract `Sitemap:` directives (feeds into sitemap discovery pipeline step)
- Read `Crawl-delay` values
- Handle wildcards (`*`) and end-of-string anchors (`$`)

**RSL integration note:** RSL 1.0 adds `License:` directives to robots.txt. protego does not parse these natively. Scan the raw robots.txt text for `License:` lines separately (simple string parsing, no library needed). See RSL section below.

```python
from protego import Protego

rp = Protego.parse(robots_txt_content)
allowed = rp.can_fetch("https://example.com/article/123", "itsascout-bot")
sitemaps = list(rp.sitemaps)  # Sitemap: directives
crawl_delay = rp.crawl_delay("itsascout-bot")
```

**Confidence:** MEDIUM -- protego is well-established in the Scrapy ecosystem. Exact latest version number should be verified at install time.

### 6. Sitemap Discovery: ultimate-sitemap-parser

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| ultimate-sitemap-parser | >=1.8.0 | Discover and parse sitemaps | All sitemap formats (XML, News, text, RSS, Atom); automatic discovery from robots.txt + common paths; memory-efficient streaming; pluggable HTTP client |

**Key capabilities:**
- Discovers sitemaps from robots.txt `Sitemap:` directives
- Falls back to common paths (`/sitemap.xml`, `/sitemap_index.xml`)
- Handles sitemap indexes (nested sitemaps)
- Parses all formats: XML, Google News, plain text, RSS 2.0, Atom
- `all_pages()` returns a generator (memory efficient for sites with millions of URLs)
- **Custom HTTP client support** via `AbstractWebClient` -- plug in curl-cffi for TLS fingerprinting

**Usage for report card:**
```python
from usp.tree import sitemap_tree_for_homepage
import itertools

tree = sitemap_tree_for_homepage("https://example.com")

# For the report card: check existence and sample
sub_sitemaps = [s for s in tree.sub_trees if s.url]
sitemap_count = len(sub_sitemaps)
page_sample = list(itertools.islice(tree.all_pages(), 100))  # Sample first 100
total_estimate = len(page_sample)  # Or iterate fully if needed
```

**Custom HTTP client integration (v1.8+):**
USP accepts a custom HTTP client implementing `AbstractWebClient`. This lets sitemap fetching use curl-cffi for TLS fingerprinting, consistent with the rest of the pipeline. The implementations in `usp.web_client.requests_client` serve as a reference for building a curl-cffi adapter.

**Confidence:** HIGH -- v1.8.0 released Jan 2026, actively maintained, field-tested on ~1M sitemaps (Media Cloud project).

### 7. RSL (Really Simple Licensing) Detection -- Custom Implementation

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| lxml | (transitive via extruct) | Parse HTML for RSL tags; parse RSL XML documents | Already installed; fast XML/HTML parser |
| No dedicated RSL Python library exists | N/A | Custom detection module required | RSL 1.0 finalized late 2025; too new for ecosystem libraries |

**What is RSL:**

RSL (Really Simple Licensing) is an open, XML-based standard that lets publishers define machine-readable licensing terms for digital content. It specifies what AI crawlers, search engines, and other automated systems are allowed to do with the content (indexing, training, inference) and what compensation is required.

**RSL 1.0 defines 4 discovery mechanisms to detect:**

**A. HTML `<head>` tags (page-level license):**
```html
<!-- Inline RSL license -->
<script type="application/rsl+xml">
  <rsl xmlns="https://rslstandard.org/rsl/1.0">
    <content url="https://example.com/article/123">
      <license>
        <terms>
          <use type="search-indexing" allowed="true" />
          <use type="ai-training" allowed="false" />
        </terms>
      </license>
    </content>
  </rsl>
</script>

<!-- External RSL license file reference -->
<link rel="license" type="application/rsl+xml"
      href="https://example.com/license.xml" />
```
**Detection:** Find `<script type="application/rsl+xml">` or `<link rel="license" type="application/rsl+xml">` in the `<head>`.

**B. HTTP `Link` response header:**
```
Link: <https://example.com/license.xml>; rel="license"; type="application/rsl+xml"
```
**Detection:** Parse the `Link` HTTP header for entries with `type="application/rsl+xml"`.

**C. robots.txt `License:` directive (site-level):**
```
License: https://example.com/license.xml
```
**Detection:** Scan robots.txt for lines starting with `License:`. This directive is global (not per user-agent).

**D. RSS feed `rsl:` namespace (feed-level):**
RSL elements can be embedded in RSS feeds using the `rsl:` XML namespace prefix on the root `<rss>` element. This ties into RSS feed discovery.

**License precedence rule:** When multiple licenses are discovered (e.g., site-wide in robots.txt and page-level in HTML), the most specific license (page-level) takes precedence.

**Implementation plan:** Build an `rsl_detector.py` module:
1. Check HTML `<head>` for `application/rsl+xml` script/link tags (lxml)
2. Check HTTP response `Link` headers (string parsing)
3. Check robots.txt for `License:` directives (string parsing)
4. If external RSL file URL found, fetch and parse the XML with lxml
5. Return structured result: `{found: bool, sources: ["html"|"header"|"robots"], license_urls: [...], terms: {...}}`

No third-party library needed -- RSL detection is HTML tag scanning + XML parsing, both handled by lxml (already installed via extruct).

**Confidence:** MEDIUM -- RSL 1.0 spec is published and stable, but the standard is brand new (finalized late 2025). Detection logic is straightforward. The spec may evolve, but the discovery mechanisms (HTML tags, HTTP headers, robots.txt) are well-defined and unlikely to change structurally.

### 8. URL Sanitization/Normalization: url-normalize

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| url-normalize | >=2.2.1 | Canonicalize and normalize URLs for consistent storage and deduplication | Handles IDN, percent-encoding, scheme defaulting, trailing slashes, query param sorting; 3.9M downloads/month; MIT license |

**Why url-normalize over w3lib.canonicalize_url or manual urllib.parse:**

The existing codebase has a bare-bones `normalize_url()` in `tasks.py` that only extracts `scheme://netloc`. This is insufficient for v2.0 where we need canonical URL comparison, deduplication, and consistent database storage.

`w3lib` is already a transitive dependency (via extruct) and has `canonicalize_url()`, but url-normalize is purpose-built for URL normalization with better IDN (internationalized domain name) handling and a cleaner API.

```python
from url_normalize import url_normalize

normalized = url_normalize("HTTP://Example.COM:80/foo/../bar?b=2&a=1")
# Returns: "http://example.com/bar?a=1&b=2"

# Handles: scheme lowering, host lowering, default port removal,
# path normalization (../ resolution), query param sorting,
# percent-encoding normalization, IDN domains
```

**Confidence:** HIGH -- v2.2.1 released April 2025, stable, MIT licensed, widely used.

### 9. RSS/Atom Feed Discovery: feedparser + BeautifulSoup

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| feedparser | >=6.0.12 | Validate and parse discovered RSS/Atom/JSON feeds | De facto standard; handles RSS 1.0/2.0, Atom, CDF; robust error handling for malformed feeds |
| beautifulsoup4 | (transitive via extruct -> mf2py) | Scan HTML `<link>` tags for feed URLs | Already installed; simpler than raw lxml for this tag-scanning task |

**Why no feedsearch-crawler or feedsearch library:**

Existing feed discovery libraries are either unmaintained or pull in heavy async dependencies (aiohttp). Feed discovery is simple enough to implement in ~30 lines:

1. Parse HTML `<link>` tags with `type="application/rss+xml"` or `type="application/atom+xml"`
2. Check common feed paths (`/feed`, `/rss`, `/atom.xml`, `/feed.xml`, `/rss.xml`, `/index.xml`)
3. Validate candidates with `feedparser.parse()` to confirm they are real feeds

```python
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import feedparser

COMMON_FEED_PATHS = ["/feed", "/rss", "/atom.xml", "/feed.xml", "/rss.xml", "/index.xml", "/feed/rss"]

def discover_feeds(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    candidates = []

    # 1. Check <link> tags in HTML
    for link in soup.find_all("link", type=["application/rss+xml", "application/atom+xml"]):
        href = link.get("href")
        if href:
            candidates.append({"url": urljoin(base_url, href), "title": link.get("title", "")})

    # 2. Check common paths (only if no <link> tags found)
    if not candidates:
        for path in COMMON_FEED_PATHS:
            candidates.append({"url": urljoin(base_url, path), "title": ""})

    # 3. Validate with feedparser
    validated = []
    for candidate in candidates:
        parsed = feedparser.parse(candidate["url"])
        if parsed.feed.get("title") or parsed.entries:
            validated.append({
                "url": candidate["url"],
                "title": parsed.feed.get("title", candidate["title"]),
                "type": parsed.version,  # e.g. "rss20", "atom10"
                "entry_count": len(parsed.entries),
            })

    return validated
```

**Note on RSL in RSS feeds:** feedparser does not understand RSL namespaced elements. If an RSS feed contains `rsl:` prefixed elements, extract the raw XML and parse RSL separately with lxml.

**Confidence:** HIGH -- feedparser 6.0.12 released Sep 2025. BeautifulSoup4 is a transitive dependency.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| HTTP Client | curl-cffi | httpx | No TLS fingerprinting; blocked by bot detection |
| HTTP Client | curl-cffi | requests | No TLS fingerprinting; no HTTP/2 |
| Task Queue | django-rq | Celery | Overkill config complexity; RabbitMQ not needed |
| Task Queue | django-rq | django_tasks DatabaseBackend | No real workers; no progress tracking; DB polling |
| Task Queue | django-rq | Huey | Less Django integration; django-rq admin panel wins |
| SSE | StreamingHttpResponse | django-eventstream | Extra dependency for simple use case |
| SSE | StreamingHttpResponse | WebSockets (channels) | Unidirectional is sufficient; ASGI migration too costly |
| SSE | StreamingHttpResponse | Polling from React | Higher latency; more frontend complexity; more server load |
| Metadata | extruct | Manual parsing per-format | extruct handles 6 formats; manual is error-prone |
| robots.txt | protego | urllib.robotparser | Known bugs; incomplete RFC 9309 |
| robots.txt | protego | robotspy | Less battle-tested than Scrapy-proven protego |
| Sitemap | ultimate-sitemap-parser | Manual XML parsing | USP handles all formats, indexes, discovery automatically |
| URL normalization | url-normalize | w3lib.canonicalize_url | url-normalize has better IDN handling, purpose-built API |
| URL normalization | url-normalize | Manual urllib.parse | Misses edge cases (IDN, encoding normalization) |
| Feed discovery | feedparser + BS4 | feedsearch-crawler | Unmaintained; heavy aiohttp dep; too simple to need a library |
| RSL detection | Custom (lxml) | N/A | No Python RSL library exists yet |

---

## Infrastructure Additions (Docker Compose)

### Redis Server

```yaml
redis:
  image: redis:7-alpine
  ports:
    - "6379:6379"
  volumes:
    - redis_data:/data
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 10s
    timeout: 5s
    retries: 3
```

### RQ Worker Service

```yaml
rqworker:
  build: .
  command: uv run python scrapegrape/manage.py rqworker default
  depends_on:
    redis:
      condition: service_healthy
    postgres:
      condition: service_started
  env_file: .env
  volumes:
    - .:/app
```

### Django Settings Additions

```python
INSTALLED_APPS += ["django_rq"]

RQ_QUEUES = {
    "default": {
        "HOST": os.getenv("REDIS_HOST", "redis"),
        "PORT": int(os.getenv("REDIS_PORT", 6379)),
        "DB": 0,
        "DEFAULT_TIMEOUT": 300,  # 5 min per job
    }
}
```

### URL Configuration Addition

```python
urlpatterns += [
    path("admin/django-rq/", include("django_rq.urls")),  # RQ admin dashboard
]
```

---

## Installation Summary

```bash
# Add new Python dependencies to pyproject.toml
uv add curl-cffi django-rq extruct protego ultimate-sitemap-parser url-normalize feedparser

# Transitive dependencies (no explicit add needed):
# - lxml (via extruct)
# - beautifulsoup4 (via extruct -> mf2py)
# - w3lib (via extruct)
# - redis (via rq -> django-rq)
# - rq (via django-rq)

# No new npm packages needed:
# - EventSource is a browser-native API
# - No SSE client library required
```

**Removals:** None. Keep all existing dependencies unchanged.

---

## Dependency Impact Summary

| New Dependency | Size Impact | C Extension? | Docker Concern |
|----------------|-------------|--------------|----------------|
| curl-cffi >=0.14.0 | ~15MB (bundled libcurl) | Yes (cffi + curl) | Verify linux/amd64 wheel on python:3.12-slim |
| django-rq >=3.0 | Small | No | None |
| extruct >=0.18.0 | Medium (pulls lxml, rdflib) | Yes (lxml) | lxml wheel may need libxml2; test `uv sync` in Docker |
| protego >=0.3.1 | Small | No | None |
| ultimate-sitemap-parser >=1.8.0 | Small | No | None |
| url-normalize >=2.2.1 | Tiny | No | None |
| feedparser >=6.0.12 | Small | No | None |

**Dockerfile note:** May need to add `libxml2-dev libxslt-dev` to apt-get if lxml's manylinux wheel does not cover `python:3.12-slim`. Test first -- the wheel usually works without system packages. If it fails:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2-dev libxslt-dev \
    && rm -rf /var/lib/apt/lists/*
```

---

## Integration Architecture Summary

```
React (Inertia page)
  |
  |-- POST /api/analyze (Django view) --> enqueue job to RQ --> return job_id
  |
  |-- EventSource /api/analysis/{job_id}/progress (SSE endpoint)
  |     |
  |     +-- reads job.meta from Redis (set by RQ worker)
  |
  RQ Worker (separate process):
    1. Normalize URL (url-normalize)
    2. Fetch robots.txt (curl-cffi) --> parse (protego) --> extract Sitemap: and License:
    3. Fetch HTML (curl-cffi, fallback Zyte) --> store for reuse
    4. Extract metadata (extruct on stored HTML)
    5. Detect RSL (custom lxml parsing on stored HTML + robots.txt License: + HTTP headers)
    6. Discover RSS feeds (BeautifulSoup on stored HTML + feedparser validation)
    7. Discover/parse sitemaps (ultimate-sitemap-parser using robots.txt Sitemap: directives)
    8. WAF detection (existing wafw00f)
    9. ToS discovery + evaluation (existing pydantic-ai agents)
    10. Compile report card --> save to PostgreSQL
    Each step updates job.meta for SSE progress
```

---

## Sources

### curl-cffi
- [curl-cffi PyPI](https://pypi.org/project/curl-cffi/) -- v0.14.0, Python 3.10+
- [curl-cffi GitHub](https://github.com/lexiforest/curl_cffi) -- browser TLS impersonation
- [curl-cffi vs httpx](https://webscraping.fyi/lib/compare/python-curl-cffi-vs-python-httpx/) -- performance comparison
- [curl-cffi documentation](https://curl-cffi.readthedocs.io/) -- AsyncSession, impersonation API

### django-rq / RQ
- [django-rq GitHub](https://github.com/rq/django-rq) -- v3.0+ changelog, Django 5.x support
- [django-rq PyPI](https://pypi.org/project/django-rq/) -- latest version
- [RQ PyPI](https://pypi.org/project/rq/) -- v2.6.1
- [Lightweight Django Task Queues 2025](https://medium.com/@g.suryawanshi/lightweight-django-task-queues-in-2025-beyond-celery-74a95e0548ec) -- comparison
- [django-rq Docker demo](https://github.com/ActionScripted/django-rq-demo/blob/master/docker-compose.yml) -- Docker pattern
- [Django 6.0 Tasks review](https://www.loopwerk.io/articles/2026/django-tasks-review/) -- django_tasks limitations

### Server-Sent Events
- [Django Streaming HTTP Responses](https://blog.pecar.me/django-streaming-responses) -- SSE pattern
- [SSE Minimalist Django](https://minimalistdjango.com/TIL/2024-04-21-server-sent-events/) -- WSGI considerations
- [EventSource MDN](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events) -- browser API
- [SSE in React 2026](https://oneuptime.com/blog/post/2026-01-15-server-sent-events-sse-react/view) -- React patterns
- [Django Forum SSE discussion](https://forum.djangoproject.com/t/server-sent-event-in-django/17205) -- WSGI vs ASGI

### extruct
- [extruct PyPI](https://pypi.org/project/extruct/) -- v0.18.0
- [extruct GitHub](https://github.com/scrapinghub/extruct) -- supported syntaxes

### protego / robots.txt
- [protego on PyPI](https://pypi.org/project/protego/) -- RFC 9309 compliant, Scrapy ecosystem
- [robotspy PyPI](https://pypi.org/project/robotspy/) -- v0.12.0, alternative considered
- [urllib.robotparser docs](https://docs.python.org/3/library/urllib.robotparser.html) -- stdlib, not recommended

### Sitemap Discovery
- [ultimate-sitemap-parser PyPI](https://pypi.org/project/ultimate-sitemap-parser/) -- v1.8.0
- [USP custom HTTP client docs](https://ultimate-sitemap-parser.readthedocs.io/en/latest/guides/http-client.html) -- AbstractWebClient
- [USP GitHub](https://github.com/GateNLP/ultimate-sitemap-parser) -- format support

### RSL (Really Simple Licensing)
- [RSL 1.0 Specification](https://rslstandard.org/rsl) -- full spec
- [Adding RSL to Web Pages](https://rslstandard.org/guide/web-pages) -- HTML script/link tags
- [Adding RSL to HTTP Headers](https://rslstandard.org/guide/http) -- Link header
- [Adding RSL to robots.txt](https://rslstandard.org/guide/robots-txt) -- License directive
- [RSL Crawler Authorization Protocol](https://rslstandard.org/guide/web-crawlers) -- CAP
- [RSL File Format](https://rslstandard.org/guide/file-format) -- XML structure
- [RSL WordPress Plugin](https://github.com/Jameswlepage/rsl-wp) -- reference implementation
- [The Register RSL coverage](https://www.theregister.com/2025/12/10/really_simple_licensing_spec_takes/) -- industry context
- [Fastly RSL blog](https://www.fastly.com/blog/control-and-monetize-your-content-with-the-rsl-standard) -- CDN integration context

### URL Normalization
- [url-normalize PyPI](https://pypi.org/project/url-normalize/) -- v2.2.1
- [url-normalize GitHub](https://github.com/niksite/url-normalize) -- IDN support

### Feed Discovery
- [feedparser PyPI](https://pypi.org/project/feedparser/) -- v6.0.12
- [feedparser GitHub](https://github.com/kurtmckee/feedparser) -- format support
- [Python 3 Feedfinder patterns](https://alexmiller.phd/posts/python-3-feedfinder-rss-detection-from-url/) -- discovery approach
