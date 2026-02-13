# Architecture: URL Analysis Workflow Integration

**Domain:** Single-URL analysis workflow with streaming progress, integrated into existing Django-Inertia app
**Researched:** 2026-02-13
**Confidence:** HIGH (existing codebase well-understood, SSE/RQ patterns verified with multiple sources)

## Executive Summary

The new URL analysis workflow integrates with the existing Django-Inertia architecture through a hybrid approach: Inertia handles page navigation and initial data loading (job creation, results page), while a separate Django async SSE endpoint streams real-time progress updates outside the Inertia protocol. The task pipeline moves from `django_tasks` (database backend) to `django-rq` (Redis backend) for the progress reporting capabilities needed by SSE -- specifically `job.meta` / `save_meta()` for step-level progress and Redis pub/sub for pushing updates to the SSE stream. The ResolutionJob model acts as the central orchestration record, tracking the multi-step pipeline and storing accumulated results. The Publisher model gets extended with discovery fields (robots.txt, sitemap, RSS, RSL, fetch strategy, metadata capabilities) that accumulate intelligence over repeated analyses.

## System Overview

```
                                    EXISTING (unchanged)
                                    +------------------+
                                    | Publishers Table  |
                                    | (Index page)      |
                                    | Django Admin      |
                                    +------------------+

    NEW FLOW
    +----------+     +----------------+     +-----------+     +-------------+
    | URL Entry| --> | ResolutionJob  | --> | RQ Worker | --> | SSE Stream  |
    | (Inertia |     | (Django model) |     | (pipeline)|     | (async view)|
    |  page)   |     |                |     |           |     |             |
    +----------+     +----------------+     +-----------+     +-------------+
         |                  |                    |                   |
         |   POST /analyze  |   enqueue job      |  Redis pub/sub   |
         +----------------->+                    +------------------>+
                            |                    |                   |
                            |   redirect to      |  job.meta for    |  EventSource
                            |   /jobs/<uuid>     |  step progress   |  in browser
                            +--------------------+-------------------+
```

## Component Architecture

### 1. ResolutionJob Model Design

**Relationship to Publisher:** A ResolutionJob is created per URL submission. It has an optional FK to Publisher (null until publisher resolution succeeds). Multiple ResolutionJobs can reference the same Publisher (repeat lookups).

```python
# publishers/models.py (or new app: resolution/)

import uuid
from django.db import models

class ResolutionJob(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        RUNNING = "running"
        COMPLETED = "completed"
        FAILED = "failed"

    # Identity
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submitted_url = models.URLField()           # Raw URL as entered by user
    canonical_url = models.URLField()            # After sanitization
    domain = models.CharField(max_length=255)    # Extracted domain for Publisher lookup

    # Relationships
    publisher = models.ForeignKey(
        "Publisher", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="resolution_jobs"
    )

    # Status tracking
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    current_step = models.CharField(max_length=50, blank=True)  # e.g., "waf_check"
    steps_completed = models.JSONField(default=list)             # ["publisher_resolution", "waf_check", ...]
    progress_pct = models.IntegerField(default=0)                # 0-100

    # Results (accumulated as pipeline progresses)
    results = models.JSONField(default=dict)    # Full structured results
    error = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # RQ job tracking
    rq_job_id = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["domain"]),
            models.Index(fields=["status"]),
        ]
```

**Key design decisions:**
- UUID primary key because the job ID appears in URLs (`/jobs/<uuid>`) and should not be guessable
- `results` JSONField accumulates step results incrementally -- each pipeline step adds its section
- `steps_completed` list tracks which steps finished for the SSE stream to report
- `publisher` FK is nullable because publisher resolution is itself a pipeline step
- `domain` field enables fast lookup for freshness checks without joining Publisher table

### 2. Publisher Model Extensions

The Publisher model gets new fields for intelligence that accumulates over analyses. These fields are populated by pipeline steps and cached per-publisher so repeat lookups are instant.

```python
# Publishers/models.py -- additions to existing Publisher model

class Publisher(models.Model):
    # EXISTING fields
    name = models.CharField(max_length=255)
    url = models.URLField()                                      # homepage URL
    detected_waf = models.CharField(max_length=255, blank=True, null=True)

    # NEW: Fetch strategy
    fetch_strategy = models.CharField(
        max_length=20, choices=[("curl_cffi", "curl-cffi"), ("zyte", "Zyte")],
        default="curl_cffi"
    )
    fetch_strategy_updated_at = models.DateTimeField(null=True, blank=True)

    # NEW: Freshness tracking
    last_checked_at = models.DateTimeField(null=True, blank=True)
    freshness_ttl_hours = models.IntegerField(default=168)  # 7 days default

    # NEW: Discovery results (cached per-publisher)
    robots_txt_content = models.TextField(blank=True)           # Raw robots.txt
    robots_txt_updated_at = models.DateTimeField(null=True, blank=True)
    sitemap_urls = models.JSONField(default=list)               # List of sitemap URLs found
    rss_urls = models.JSONField(default=list)                   # List of RSS feed URLs found
    rsl_status = models.JSONField(default=dict)                 # RSL detection results

    # NEW: Metadata capabilities (what structured data this publisher provides)
    metadata_capabilities = models.JSONField(default=dict)
    # Structure: {
    #   "json_ld": true/false,
    #   "opengraph": true/false,
    #   "microdata": true/false,
    #   "byline": true/false,
    #   "publish_date": true/false,
    #   "thumbnail": true/false,
    #   "paywall_indicator": true/false,
    #   "word_count_available": true/false,
    # }
```

**Freshness logic:** When a new ResolutionJob arrives for a domain that already has a Publisher with `last_checked_at` within `freshness_ttl_hours`, the pipeline skips publisher-level discovery steps and reuses cached data. Only article-level extraction runs fresh.

### 3. SSE Endpoint Design -- Critical Architectural Question

**Answer: SSE bypasses Inertia. It is a separate Django async view.**

Inertia's protocol is request-response: the client makes XHR requests, the server returns JSON page data. SSE is a long-lived HTTP connection streaming events. These are fundamentally different protocols and must coexist as separate endpoints.

**The pattern:**

1. User submits URL on the Inertia page (`POST /analyze`)
2. Django view creates ResolutionJob, enqueues RQ task, redirects to `/jobs/<uuid>` (Inertia page)
3. Inertia loads the results page with initial job state (status, any cached publisher data)
4. React component opens EventSource to `/api/jobs/<uuid>/stream` (separate SSE endpoint, NOT Inertia)
5. SSE endpoint subscribes to Redis pub/sub channel `job:<uuid>` and streams events
6. RQ worker publishes progress events to Redis pub/sub as each step completes
7. When pipeline completes, SSE sends final event and closes; React updates UI from accumulated state

**Why raw `StreamingHttpResponse` (not Django Channels, not django-eventstream):**

- **Not Django Channels:** Channels adds WebSocket infrastructure (ASGI routing layers, channel layers) that is overkill for unidirectional server-to-client streaming. SSE is simpler and sufficient.
- **Not django-eventstream:** Adds Fanout/Pushpin proxy dependencies. Over-engineered for per-job streams that live for 30-120 seconds.
- **StreamingHttpResponse with async generator:** Django 5.2 supports async views natively. An async generator that subscribes to Redis pub/sub and yields SSE-formatted events is the right level of abstraction. No extra dependencies beyond `redis[hiredis]` (which RQ already requires).

**Server requirement:** The SSE endpoint requires an ASGI server because it is a long-lived async response. The existing `asgi.py` is already configured. Add `daphne` or `uvicorn` as the dev server. In production, run under `uvicorn` or `daphne`. Critically, sync Inertia views work fine under ASGI -- Django handles sync-in-async context switching automatically.

```python
# resolution/views.py -- SSE endpoint

import asyncio
import json
from django.http import StreamingHttpResponse
from redis import asyncio as aioredis

async def job_stream(request, job_id):
    """SSE endpoint for streaming job progress. NOT an Inertia view."""

    async def event_generator():
        redis = aioredis.from_url("redis://localhost:6379", decode_responses=True)
        pubsub = redis.pubsub()
        await pubsub.subscribe(f"job:{job_id}")

        try:
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=30.0  # Send keepalive if no message in 30s
                )
                if message is None:
                    # Keepalive to prevent connection timeout
                    yield ": keepalive\n\n"
                    continue

                data = json.loads(message["data"])
                event_type = data.get("type", "progress")
                yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

                if event_type == "complete" or event_type == "error":
                    break
        finally:
            await pubsub.unsubscribe(f"job:{job_id}")
            await pubsub.close()
            await redis.close()

    response = StreamingHttpResponse(
        event_generator(),
        content_type="text/event-stream"
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"  # Disable nginx buffering
    return response
```

**URL configuration:**

```python
# scrapegrape/urls.py

urlpatterns = [
    # Existing Inertia routes
    path("", publishers.views.table, name="table"),
    path("publishers/create", publishers.views.create),
    # ...

    # NEW: Inertia pages for job flow
    path("analyze", resolution.views.analyze, name="analyze"),        # URL entry page
    path("jobs/<uuid:job_id>", resolution.views.job_detail, name="job-detail"),  # Results page

    # NEW: SSE endpoint (NOT Inertia -- separate API namespace)
    path("api/jobs/<uuid:job_id>/stream", resolution.views.job_stream, name="job-stream"),

    path("admin/", admin.site.urls),
]
```

### 4. RQ Task Pipeline Design

**Migration from django_tasks to django-rq:**

The existing `@task` decorator from `django_tasks` must be replaced with `@job` from `django_rq`. The key reason for switching: `django_tasks` with its database backend has no mechanism for real-time progress updates -- you would need to poll the database. RQ stores job metadata in Redis, enabling sub-second progress updates via `job.meta` + Redis pub/sub.

**Pipeline architecture -- single orchestrator task, not chained jobs:**

Use a single RQ job that executes steps sequentially and publishes progress after each step. This is simpler than RQ's `depends_on` chaining because:
- Steps share state (publisher object, fetched HTML, etc.)
- Progress reporting needs a single channel
- Error handling is centralized
- No need to pass results between separate jobs (RQ's `depends_on` does not pass results)

```python
# resolution/tasks.py

import django_rq
import redis
import json
from rq import get_current_job
from django.utils import timezone

def publish_progress(redis_conn, job_id, step, progress_pct, data=None):
    """Publish progress event to Redis pub/sub for SSE stream."""
    event = {
        "type": "progress",
        "step": step,
        "progress": progress_pct,
        "timestamp": timezone.now().isoformat(),
    }
    if data:
        event["data"] = data
    redis_conn.publish(f"job:{job_id}", json.dumps(event))

def publish_complete(redis_conn, job_id, results):
    """Publish completion event."""
    event = {
        "type": "complete",
        "results": results,
        "timestamp": timezone.now().isoformat(),
    }
    redis_conn.publish(f"job:{job_id}", json.dumps(event))

def publish_error(redis_conn, job_id, error, step):
    """Publish error event."""
    event = {
        "type": "error",
        "step": step,
        "error": str(error),
        "timestamp": timezone.now().isoformat(),
    }
    redis_conn.publish(f"job:{job_id}", json.dumps(event))

@django_rq.job("default")
def run_resolution_pipeline(job_uuid):
    """
    Execute the full URL analysis pipeline for a ResolutionJob.

    Pipeline steps (in order):
    1. Publisher resolution (domain lookup or LLM web search)
    2. Fetch strategy discovery (curl-cffi test, Zyte fallback)
    3. WAF detection
    4. robots.txt fetch and parse
    5. Sitemap discovery
    6. RSS feed discovery
    7. RSL (Really Simple Licensing) check
    8. ToS discovery
    9. ToS evaluation
    10. Article metadata extraction (if URL is an article)
    11. Metadata profiling (LLM-powered capability assessment)
    """
    from resolution.models import ResolutionJob
    from publishers.models import Publisher

    rq_job = get_current_job()
    r = rq_job.connection  # Redis connection from RQ

    resolution_job = ResolutionJob.objects.get(id=job_uuid)
    resolution_job.status = ResolutionJob.Status.RUNNING
    resolution_job.started_at = timezone.now()
    resolution_job.rq_job_id = rq_job.id
    resolution_job.save()

    results = {}
    steps = [
        ("publisher_resolution", step_resolve_publisher, 10),
        ("fetch_strategy",       step_discover_fetch_strategy, 18),
        ("waf_check",            step_waf_check, 25),
        ("robots_txt",           step_robots_txt, 35),
        ("sitemap_discovery",    step_sitemap_discovery, 42),
        ("rss_discovery",        step_rss_discovery, 50),
        ("rsl_check",            step_rsl_check, 58),
        ("tos_discovery",        step_tos_discovery, 68),
        ("tos_evaluation",       step_tos_evaluation, 78),
        ("metadata_extraction",  step_metadata_extraction, 88),
        ("metadata_profiling",   step_metadata_profiling, 100),
    ]

    try:
        for step_name, step_fn, progress_pct in steps:
            resolution_job.current_step = step_name
            resolution_job.save(update_fields=["current_step"])

            publish_progress(r, str(job_uuid), step_name, progress_pct)

            # Update RQ job meta for admin monitoring
            rq_job.meta["step"] = step_name
            rq_job.meta["progress"] = progress_pct
            rq_job.save_meta()

            # Execute step -- each step receives and mutates context
            step_result = step_fn(resolution_job, results)
            if step_result:
                results[step_name] = step_result

            # Publish step completion with result data
            publish_progress(r, str(job_uuid), step_name, progress_pct, data=step_result)

            resolution_job.steps_completed = list(results.keys())
            resolution_job.results = results
            resolution_job.progress_pct = progress_pct
            resolution_job.save(update_fields=[
                "steps_completed", "results", "progress_pct"
            ])

        # Pipeline complete
        resolution_job.status = ResolutionJob.Status.COMPLETED
        resolution_job.completed_at = timezone.now()
        resolution_job.save()

        publish_complete(r, str(job_uuid), results)

    except Exception as e:
        resolution_job.status = ResolutionJob.Status.FAILED
        resolution_job.error = str(e)
        resolution_job.completed_at = timezone.now()
        resolution_job.save()

        publish_error(r, str(job_uuid), e, resolution_job.current_step)
```

**Step functions receive the ResolutionJob and accumulated results dict.** Each step checks if cached publisher data is fresh enough to skip re-execution. Example:

```python
def step_resolve_publisher(resolution_job, results):
    """Find or create Publisher for this domain."""
    from publishers.models import Publisher

    publisher, created = Publisher.objects.get_or_create(
        url__contains=resolution_job.domain,
        defaults={"name": resolution_job.domain, "url": f"https://{resolution_job.domain}"}
    )

    # Check freshness
    if not created and publisher.is_fresh():
        resolution_job.publisher = publisher
        resolution_job.save(update_fields=["publisher"])
        return {"publisher_id": publisher.id, "name": publisher.name, "cached": True}

    # Publisher resolution logic (homepage fetch or LLM search)
    # ...update publisher fields...
    resolution_job.publisher = publisher
    resolution_job.save(update_fields=["publisher"])
    return {"publisher_id": publisher.id, "name": publisher.name, "cached": False}
```

### 5. URL Sanitization Service

A pure function service that normalizes URLs before job creation. Prevents duplicate jobs and ensures consistent domain extraction.

```python
# resolution/services/url_sanitizer.py

from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
import re

class URLSanitizer:
    """
    Normalize user-submitted URLs to canonical form.

    Rules:
    1. Add https:// if no scheme
    2. Lowercase the hostname
    3. Remove www. prefix (optional, configurable)
    4. Remove trailing slashes from path
    5. Remove tracking parameters (utm_*, fbclid, gclid, etc.)
    6. Remove fragment (#section)
    7. Sort remaining query parameters
    8. Validate URL structure
    """

    TRACKING_PARAMS = {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "fbclid", "gclid", "dclid", "msclkid", "ref", "source",
    }

    @classmethod
    def sanitize(cls, raw_url: str) -> tuple[str, str]:
        """
        Returns (canonical_url, domain).
        Raises ValueError if URL is invalid.
        """
        url = raw_url.strip()

        # Add scheme if missing
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        parsed = urlparse(url)

        if not parsed.netloc:
            raise ValueError(f"Invalid URL: no hostname found in '{raw_url}'")

        # Lowercase hostname, remove www.
        hostname = parsed.netloc.lower()
        if hostname.startswith("www."):
            hostname = hostname[4:]

        # Clean path
        path = parsed.path.rstrip("/") or ""

        # Clean query params
        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=False)
            cleaned = {k: v for k, v in params.items() if k.lower() not in cls.TRACKING_PARAMS}
            query = urlencode(sorted(cleaned.items()), doseq=True) if cleaned else ""
        else:
            query = ""

        canonical = urlunparse((
            "https",     # Always HTTPS
            hostname,
            path,
            "",          # params (deprecated)
            query,
            "",          # No fragment
        ))

        domain = hostname
        return canonical, domain
```

**Integration point:** Called in the `analyze` view before creating a ResolutionJob. Also used for duplicate detection -- if a ResolutionJob with the same `canonical_url` is still RUNNING, return that job's UUID instead of creating a new one.

### 6. Fetch Strategy Manager

Encapsulates the "try curl-cffi first, fall back to Zyte" logic. Remembers which strategy works per publisher domain.

```python
# resolution/services/fetch_strategy.py

from publishers.models import Publisher
from django.utils import timezone

class FetchStrategyManager:
    """
    Manages HTML fetching with automatic strategy selection.

    Strategy:
    1. If publisher has a known working strategy, use it
    2. Otherwise, try curl-cffi first (free, fast)
    3. If curl-cffi fails (403, WAF block, timeout), try Zyte (paid, reliable)
    4. Remember which strategy worked for this publisher
    """

    @classmethod
    def fetch(cls, url: str, publisher: Publisher | None = None) -> tuple[str, str]:
        """
        Fetch HTML content from URL.
        Returns (html_content, strategy_used).
        """
        preferred = publisher.fetch_strategy if publisher else "curl_cffi"

        if preferred == "curl_cffi":
            html = cls._try_curl_cffi(url)
            if html:
                return html, "curl_cffi"
            # Fallback to Zyte
            html = cls._try_zyte(url)
            if html:
                cls._remember_strategy(publisher, "zyte")
                return html, "zyte"
        else:  # zyte
            html = cls._try_zyte(url)
            if html:
                return html, "zyte"

        raise FetchError(f"All fetch strategies failed for {url}")

    @classmethod
    def _try_curl_cffi(cls, url: str) -> str | None:
        """Attempt fetch with curl-cffi browser impersonation."""
        try:
            from curl_cffi.requests import Session
            with Session(impersonate="chrome") as s:
                resp = s.get(url, timeout=15)
                if resp.status_code == 200:
                    return resp.text
                return None
        except Exception:
            return None

    @classmethod
    def _try_zyte(cls, url: str) -> str | None:
        """Attempt fetch via Zyte proxy API."""
        from ingestion.services import fetch_html_via_proxy
        try:
            return fetch_html_via_proxy(url)
        except Exception:
            return None

    @classmethod
    def _remember_strategy(cls, publisher: Publisher | None, strategy: str):
        """Update publisher's preferred fetch strategy."""
        if publisher:
            publisher.fetch_strategy = strategy
            publisher.fetch_strategy_updated_at = timezone.now()
            publisher.save(update_fields=["fetch_strategy", "fetch_strategy_updated_at"])
```

### 7. Frontend Architecture for Streaming Results Page

**Page structure:** Two new Inertia page components.

```
frontend/src/Pages/
  Analyze/
    Index.tsx       # URL entry form
  Jobs/
    Show.tsx        # Streaming results / report card
```

**How the job results page works with Inertia:**

1. **Initial load via Inertia** (`GET /jobs/<uuid>`): Django view fetches ResolutionJob from database, serializes current state (may be pending, running, or completed), passes as Inertia props.

2. **If job is still running**, React component opens EventSource to `/api/jobs/<uuid>/stream` for real-time updates.

3. **If job is already completed** (user refreshes, shares link), Inertia props contain full results. No SSE needed.

This is the critical insight: the results page is a **standard Inertia page** that optionally enhances with SSE when the job is still in progress.

```python
# resolution/views.py -- Inertia views

from inertia import render as inertia_render
from django.shortcuts import redirect
from .models import ResolutionJob
from .services.url_sanitizer import URLSanitizer
from .serializers import ResolutionJobSerializer

def analyze(request):
    """URL entry page."""
    if request.method == "POST":
        raw_url = request.POST.get("url", "")
        try:
            canonical_url, domain = URLSanitizer.sanitize(raw_url)
        except ValueError as e:
            request.session["errors"] = {"url": str(e)}
            return redirect("/analyze")

        # Check for existing running job with same canonical URL
        existing = ResolutionJob.objects.filter(
            canonical_url=canonical_url,
            status__in=[ResolutionJob.Status.PENDING, ResolutionJob.Status.RUNNING]
        ).first()
        if existing:
            return redirect(f"/jobs/{existing.id}")

        # Create job and enqueue
        job = ResolutionJob.objects.create(
            submitted_url=raw_url,
            canonical_url=canonical_url,
            domain=domain,
        )
        import django_rq
        django_rq.enqueue(run_resolution_pipeline, str(job.id))

        return redirect(f"/jobs/{job.id}")

    return inertia_render(request, "Analyze/Index")


def job_detail(request, job_id):
    """Job results page. Inertia renders initial state; SSE enhances if running."""
    job = ResolutionJob.objects.select_related("publisher").get(id=job_id)
    serialized = ResolutionJobSerializer(job)

    return inertia_render(request, "Jobs/Show", props={
        "job": serialized.data,
        "sseUrl": f"/api/jobs/{job_id}/stream" if job.status in ["pending", "running"] else None,
    })
```

**Frontend React component with SSE:**

```tsx
// frontend/src/Pages/Jobs/Show.tsx
import { useState, useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import AppLayout from '@/Layouts/AppLayout'

interface JobProps {
    job: {
        id: string
        submitted_url: string
        canonical_url: string
        status: 'pending' | 'running' | 'completed' | 'failed'
        current_step: string
        steps_completed: string[]
        progress_pct: number
        results: Record<string, any>
        error: string
        publisher: { id: number; name: string } | null
    }
    sseUrl: string | null  // null when job is already complete
}

// Pipeline step definitions for display
const PIPELINE_STEPS = [
    { key: 'publisher_resolution', label: 'Resolving Publisher', icon: 'building' },
    { key: 'fetch_strategy',       label: 'Testing Fetch Strategy', icon: 'globe' },
    { key: 'waf_check',            label: 'WAF Detection', icon: 'shield' },
    { key: 'robots_txt',           label: 'Checking robots.txt', icon: 'file-text' },
    { key: 'sitemap_discovery',    label: 'Finding Sitemaps', icon: 'map' },
    { key: 'rss_discovery',        label: 'Finding RSS Feeds', icon: 'rss' },
    { key: 'rsl_check',            label: 'RSL License Check', icon: 'scale' },
    { key: 'tos_discovery',        label: 'Finding Terms of Service', icon: 'scroll' },
    { key: 'tos_evaluation',       label: 'Evaluating Permissions', icon: 'check-circle' },
    { key: 'metadata_extraction',  label: 'Extracting Metadata', icon: 'database' },
    { key: 'metadata_profiling',   label: 'Profiling Capabilities', icon: 'bar-chart' },
]

function Show({ job: initialJob, sseUrl }: JobProps) {
    const [job, setJob] = useState(initialJob)
    const eventSourceRef = useRef<EventSource | null>(null)

    useEffect(() => {
        if (!sseUrl) return  // Job already complete, no SSE needed

        const es = new EventSource(sseUrl)
        eventSourceRef.current = es

        es.addEventListener('progress', (event) => {
            const data = JSON.parse(event.data)
            setJob(prev => ({
                ...prev,
                current_step: data.step,
                progress_pct: data.progress,
                steps_completed: [...prev.steps_completed, data.step],
                results: data.data
                    ? { ...prev.results, [data.step]: data.data }
                    : prev.results,
                status: 'running',
            }))
        })

        es.addEventListener('complete', (event) => {
            const data = JSON.parse(event.data)
            setJob(prev => ({
                ...prev,
                status: 'completed',
                results: data.results,
                progress_pct: 100,
            }))
            es.close()
        })

        es.addEventListener('error', (event) => {
            // EventSource auto-reconnects on network errors.
            // For application-level errors, the server sends an "error" event type.
            try {
                const data = JSON.parse((event as MessageEvent).data)
                setJob(prev => ({
                    ...prev,
                    status: 'failed',
                    error: data.error,
                }))
                es.close()
            } catch {
                // Network error -- EventSource will auto-reconnect
            }
        })

        return () => {
            es.close()
            eventSourceRef.current = null
        }
    }, [sseUrl])

    return (
        <div className="container mx-auto py-10 max-w-4xl">
            <h1 className="text-2xl mb-2">Analysis: {job.canonical_url}</h1>

            {/* Progress stepper */}
            <div className="space-y-2 mb-8">
                {PIPELINE_STEPS.map(step => {
                    const isCompleted = job.steps_completed.includes(step.key)
                    const isCurrent = job.current_step === step.key
                    return (
                        <StepRow
                            key={step.key}
                            step={step}
                            isCompleted={isCompleted}
                            isCurrent={isCurrent}
                            result={job.results[step.key]}
                        />
                    )
                })}
            </div>

            {/* Results cards -- render progressively as steps complete */}
            {job.results.publisher_resolution && <PublisherCard data={job.results.publisher_resolution} />}
            {job.results.waf_check && <WAFCard data={job.results.waf_check} />}
            {job.results.robots_txt && <RobotsTxtCard data={job.results.robots_txt} />}
            {job.results.tos_evaluation && <PermissionsCard data={job.results.tos_evaluation} />}
            {/* ... more result cards ... */}
        </div>
    )
}

Show.layout = (page: ReactNode) => <AppLayout>{page}</AppLayout>
export default Show
```

**Key pattern -- progressive component rendering:** Result cards render conditionally based on which keys exist in `job.results`. As SSE events arrive and state updates, new cards appear smoothly. Each card component handles its own data shape.

### 8. SSE + Inertia Coexistence Summary

| Concern | How It Works |
|---------|-------------|
| **Page navigation** | Inertia handles all page-to-page navigation (URL entry -> results page, back to publisher table) |
| **Initial data load** | Inertia props contain full job state from database. Works for completed jobs without SSE. |
| **Real-time updates** | Separate `/api/jobs/<uuid>/stream` async endpoint. Not Inertia. EventSource in React. |
| **CSRF** | SSE GET requests do not need CSRF. The endpoint is read-only. |
| **Authentication** | SSE endpoint can check `request.user` like any Django view. Middleware still runs. |
| **Layout persistence** | Results page uses same AppLayout as other Inertia pages. SSE updates only affect inner content. |
| **URL sharing** | `/jobs/<uuid>` is a real URL. Refreshing works because Inertia loads from DB. SSE reconnects if job still running. |
| **Connection management** | EventSource auto-reconnects on network failure. Server sends keepalives every 30s. |

## Data Flow: Full Pipeline

```
User enters URL
    |
    v
[Inertia POST /analyze]
    |
    v
URLSanitizer.sanitize(raw_url) --> (canonical_url, domain)
    |
    v
Check for existing running job with same canonical_url
    |   (found) --> redirect to /jobs/<existing.id>
    v   (not found)
Create ResolutionJob(submitted_url, canonical_url, domain)
    |
    v
django_rq.enqueue(run_resolution_pipeline, job.id)
    |
    v
[Inertia REDIRECT /jobs/<uuid>]
    |
    v
Inertia loads Jobs/Show page with job props
    |
    v
React opens EventSource(/api/jobs/<uuid>/stream)
    |                                              |
    v                                              v
[RQ Worker picks up job]              [SSE endpoint subscribes to
    |                                   Redis channel job:<uuid>]
    v
Step 1: Publisher Resolution
    - Lookup Publisher by domain
    - If fresh, skip (use cached data)
    - If new/stale, fetch homepage, extract name
    - Set resolution_job.publisher FK
    |
    v  (publish progress to Redis)  -----> SSE yields event -----> React updates UI
    |
Step 2: Fetch Strategy Discovery
    - Try curl-cffi GET on homepage
    - If blocked/failed, try Zyte
    - Remember working strategy on Publisher
    |
    v  (publish progress) -----> SSE -----> React
    |
Step 3: WAF Detection
    - Run wafw00f scan
    - Create WAFReport record
    |
    v  (publish) -----> SSE -----> React renders WAF card
    |
Step 4: robots.txt
    - Fetch /robots.txt
    - Parse with urllib.robotparser
    - Cache content on Publisher
    - Check if submitted URL is allowed
    |
    v  (publish) -----> SSE -----> React renders robots.txt card
    |
Step 5: Sitemap Discovery
    - Check robots.txt for Sitemap: directives
    - Try common paths (/sitemap.xml, /sitemap_index.xml)
    - Store discovered URLs on Publisher
    |
    v  (publish) -----> SSE -----> React
    |
Step 6: RSS Discovery
    - Parse homepage HTML for <link rel="alternate" type="application/rss+xml">
    - Try common paths (/feed, /rss, /atom.xml)
    - Store discovered URLs on Publisher
    |
    v  (publish) -----> SSE -----> React
    |
Step 7: RSL Check
    - Fetch /.well-known/rsl.json or check homepage for RSL link
    - Parse RSL data if found
    |
    v  (publish) -----> SSE -----> React
    |
Step 8: ToS Discovery (reuses existing agent)
    - discover_terms_and_privacy(homepage_url)
    - Create/update TermsDiscoveryResult
    |
    v  (publish) -----> SSE -----> React
    |
Step 9: ToS Evaluation (reuses existing agent)
    - evaluate_terms_and_conditions(tos_url)
    - Create/update TermsEvaluationResult
    |
    v  (publish) -----> SSE -----> React renders permissions card
    |
Step 10: Article Metadata Extraction
    - If submitted URL is an article (not homepage):
    -   Fetch article HTML (using publisher's fetch strategy)
    -   Run extruct to extract json-ld, opengraph, microdata
    -   Extract title, author, date, thumbnail, word count
    |
    v  (publish) -----> SSE -----> React renders article card
    |
Step 11: Metadata Profiling
    - LLM assessment of what structured data this publisher provides
    - Update Publisher.metadata_capabilities
    |
    v  (publish complete) -----> SSE sends "complete" event -----> React shows final state
    |
    v
Update ResolutionJob.status = COMPLETED
Update Publisher.last_checked_at
```

## New vs Modified Components

### New Components (to be created)

| Component | Location | Type | Purpose |
|-----------|----------|------|---------|
| ResolutionJob model | `resolution/models.py` | Django model | Job tracking with UUID, status, results |
| URL sanitizer | `resolution/services/url_sanitizer.py` | Service | URL normalization and dedup |
| Fetch strategy manager | `resolution/services/fetch_strategy.py` | Service | curl-cffi/Zyte with per-publisher memory |
| Resolution pipeline task | `resolution/tasks.py` | RQ job | Orchestrates all analysis steps |
| SSE stream endpoint | `resolution/views.py` | Async Django view | Redis pub/sub to EventSource |
| Analyze page (Inertia) | `resolution/views.py` | Django view | URL entry form |
| Job detail page (Inertia) | `resolution/views.py` | Django view | Results with SSE props |
| Pipeline step functions | `resolution/steps/` | Python modules | Individual analysis steps |
| Analyze/Index.tsx | `frontend/src/Pages/Analyze/Index.tsx` | React component | URL entry form |
| Jobs/Show.tsx | `frontend/src/Pages/Jobs/Show.tsx` | React component | Streaming results page |
| Result card components | `frontend/src/components/results/` | React components | WAFCard, PermissionsCard, etc. |
| ResolutionJob serializer | `resolution/serializers.py` | DRF serializer | Job data for Inertia props |
| useSSE hook (optional) | `frontend/src/hooks/useSSE.ts` | React hook | EventSource management |

### Modified Components (existing, to be extended)

| Component | Location | Change |
|-----------|----------|--------|
| Publisher model | `publishers/models.py` | Add new fields (fetch_strategy, robots_txt, etc.) |
| Docker Compose | `scrapegrape/docker-compose.yml` | Add Redis service and RQ worker |
| Django settings | `scrapegrape/scrapegrape/settings.py` | Add django-rq config, Redis URL, ASGI server |
| URL config | `scrapegrape/scrapegrape/urls.py` | Add /analyze, /jobs/<uuid>, /api/jobs/<uuid>/stream |
| ASGI config | `scrapegrape/scrapegrape/asgi.py` | No changes needed (already configured) |
| AppLayout | `frontend/src/Layouts/AppLayout.tsx` | Add "Analyze" link to nav |

### Unchanged Components

| Component | Why Unchanged |
|-----------|---------------|
| Publisher Index/Create/Edit/BulkUpload pages | Existing admin/management UI stays as-is |
| PublisherWithReportsSerializer | Still used for publisher table |
| WAFReport model | Still created by pipeline, schema unchanged |
| TermsDiscovery/Evaluation models | Still created by pipeline, schema unchanged |
| ingestion/ app | Agents reused by pipeline steps, no changes to agent code |
| publishers/admin.py | Admin actions continue to work |

## Infrastructure Changes

### Docker Compose additions

```yaml
# scrapegrape/docker-compose.yml (additions)

services:
  postgres:
    # ... existing ...

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  rq-worker:
    build: ..
    command: uv run python manage.py rqworker default
    depends_on:
      - redis
      - postgres
    environment:
      - DATABASE_URL=postgres://postgres:postgres@postgres:5432/scrapegrape
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - .:/app

volumes:
  postgres_data:
  redis_data:
```

### Django settings additions

```python
# RQ configuration (replaces TASKS setting)
RQ_QUEUES = {
    "default": {
        "URL": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        "DEFAULT_TIMEOUT": 600,  # 10 minutes for full pipeline
    },
}

# Redis URL for SSE pub/sub
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

INSTALLED_APPS = [
    "daphne",  # MUST be first -- hooks into runserver for ASGI
    # ... existing apps ...
    "django_rq",
    "resolution",  # New app
]
```

## Build Order (Dependency-Aware)

Phase ordering based on what blocks what:

1. **Infrastructure first** (Redis + RQ + ASGI server) -- everything else depends on this
2. **Models** (ResolutionJob, Publisher extensions) -- tasks and views need these
3. **URL sanitizer** -- needed by analyze view
4. **Fetch strategy manager** -- needed by pipeline steps
5. **Pipeline task + step functions** -- core business logic
6. **SSE endpoint** -- needs Redis pub/sub from pipeline
7. **Inertia views** (analyze, job_detail) -- needs models and pipeline
8. **Frontend pages** -- needs backend views
9. **Result card components** -- can be built incrementally

## Anti-Patterns to Avoid

### Anti-Pattern 1: SSE Through Inertia

**What:** Trying to stream SSE events through Inertia's response protocol
**Why bad:** Inertia expects JSON responses with `{component, props, url, version}`. SSE is a different protocol entirely. Inertia middleware would corrupt the stream.
**Instead:** Separate `/api/` endpoint for SSE, outside Inertia's routing.

### Anti-Pattern 2: Chained RQ Jobs for Pipeline

**What:** Using `depends_on` to chain 11 separate RQ jobs
**Why bad:** Cannot pass results between jobs easily. Each job needs its own progress channel. Error handling fragmented across 11 jobs. Recovery/retry complexity.
**Instead:** Single orchestrator job with step functions. Progress published after each step.

### Anti-Pattern 3: Polling Job Status from Database

**What:** React component polling `GET /api/jobs/<uuid>/status` every N seconds
**Why bad:** Wastes requests, adds latency (1-5s between updates), puts load on database for every poll.
**Instead:** Redis pub/sub to SSE stream. Sub-second updates, no polling overhead.

### Anti-Pattern 4: Storing Full HTML in ResolutionJob

**What:** Saving fetched HTML content in the ResolutionJob.results JSON field
**Why bad:** HTML can be 500KB-5MB. Bloats database, slows serialization for Inertia props.
**Instead:** Fetched HTML is ephemeral -- used within the pipeline and discarded. Only extracted data is stored.

### Anti-Pattern 5: Running SSE Under WSGI

**What:** Trying to use `StreamingHttpResponse` with async generator under Gunicorn/WSGI
**Why bad:** WSGI does not support async generators. Each SSE connection ties up a sync worker for the entire job duration (30-120s). With 10 concurrent users, all workers are consumed.
**Instead:** Run under ASGI (Daphne or Uvicorn). Async views handle SSE connections efficiently with cooperative multitasking.

## Scalability Considerations

| Concern | At 10 users | At 100 users | At 1000 users |
|---------|-------------|--------------|---------------|
| SSE connections | 10 async connections, trivial | 100 async connections, fine under ASGI | Need connection limits, consider nginx proxy |
| RQ workers | 1 worker, sequential jobs | 2-4 workers, parallel jobs | Scale workers horizontally, separate queue priorities |
| Redis pub/sub | Negligible load | Fine | Fine (pub/sub is lightweight) |
| Database writes | ResolutionJob updates per step (11 per job) | ~1100 writes/batch | Batch updates, reduce save frequency |
| Publisher cache hits | Low (new publishers) | Higher (repeat domains) | Most lookups cached, pipeline skips stale checks |

## Sources

### SSE + Django
- [Server-Sent Events - Minimalist Django](https://minimalistdjango.com/TIL/2024-04-21-server-sent-events/) -- Async SSE with StreamingHttpResponse
- [SSE with Django DRF and Redis](https://plainenglish.io/blog/server-sent-event-feature-in-django-rest-framework) -- Redis pub/sub to SSE pattern
- [Django SSE with PostgreSQL LISTEN/NOTIFY](https://valberg.dk/django-sse-postgresql-listen-notify.html) -- Async generator pattern
- [Django Streaming HTTP Responses](https://blog.pecar.me/django-streaming-responses) -- StreamingHttpResponse internals
- [Tom Dekan - SSE with Daphne](https://tomdekan.com/articles/server-sent-events-daphne) -- ASGI server requirements

### RQ / django-rq
- [RQ Jobs Documentation](https://python-rq.org/docs/jobs/) -- job.meta, save_meta(), callbacks
- [Advanced Django-RQ Example](https://stuartm.com/2020/05/advanced-django-rq-example/) -- Progress tracking pattern
- [django-rq GitHub](https://github.com/rq/django-rq) -- Django integration, admin monitoring
- [RQ Chains](https://pypi.org/project/rq-chains/) -- Alternative job chaining (not recommended for this use case)

### ASGI / Server Architecture
- [Django Forum - ASGI Migration](https://forum.djangoproject.com/t/what-does-switching-to-asgi-entail/26857) -- Sync/async coexistence
- [Django ASGI Deployment Docs](https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/) -- Official ASGI documentation

### Fetch Strategy
- [curl-cffi GitHub](https://github.com/lexiforest/curl_cffi) -- Browser impersonation library
- [Web Scraping with curl-cffi 2025](https://brightdata.com/blog/web-data/web-scraping-with-curl-cffi) -- Usage patterns and anti-bot bypass

### Metadata Extraction
- [extruct GitHub](https://github.com/scrapinghub/extruct) -- JSON-LD, OpenGraph, Microdata extraction
- [urllib.robotparser](https://docs.python.org/3/library/urllib.robotparser.html) -- Standard library robots.txt parser

### React SSE Patterns
- [SSE in React (OneUptime)](https://oneuptime.com/blog/post/2026-01-15-server-sent-events-sse-react/view) -- EventSource + useEffect pattern
- [React SSE Implementation (Tokopedia)](https://medium.com/tokopedia-engineering/implementing-server-sent-events-in-reactjs-c36661d89468) -- Production patterns
- [MDN EventSource API](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events) -- Official specification
