# Phase 8: Core Pipeline & SSE - Research

**Researched:** 2026-02-14
**Domain:** Django SSE (Server-Sent Events), pipeline orchestration, Redis pub/sub, Inertia.js + EventSource
**Confidence:** HIGH

## Summary

Phase 8 is the core vertical slice of v2.0: a user pastes a URL on the homepage, a ResolutionJob is created, an RQ worker runs the pipeline sequentially (publisher resolution, WAF check, ToS discovery, ToS evaluation), and the user watches real-time progress via SSE at a shareable `/jobs/<uuid>` URL. The codebase already has all the building blocks: ResolutionJob model with UUID PK and step result JSONFields (Phase 6), FetchStrategyManager with curl-cffi/Zyte fallback (Phase 7), existing WAF scan (`waf_check.py`), terms discovery/evaluation agents (`ingestion/terms_discovery.py`, `ingestion/terms_evaluation.py`), django-rq task infrastructure, and Redis 7.

The SSE endpoint requires Daphne (ASGI server) to avoid tying a WSGI worker per streaming connection. Daphne integrates cleanly with Django 5.2 -- adding `"daphne"` as the first entry in `INSTALLED_APPS` and setting `ASGI_APPLICATION` causes `manage.py runserver` to use Daphne automatically. The existing Inertia middleware is compatible with ASGI (it checks `X-Inertia` header and passes non-Inertia requests through unchanged). The pipeline worker communicates progress to the SSE endpoint via Redis pub/sub: the worker PUBLISHes to a `job:{uuid}:events` channel after each step, and the async SSE view SUBSCRIBEs to that channel and yields formatted SSE events. The SSE endpoint is a plain Django async view (not an Inertia view) -- the frontend navigates to the Inertia Jobs/Show page, which creates an `EventSource` connection to the separate `/api/jobs/<uuid>/stream` SSE endpoint.

**Primary recommendation:** Use Daphne for ASGI, Redis pub/sub for worker-to-SSE communication, an async Django view for the SSE endpoint, and an Inertia page (`Jobs/Show.tsx`) with native `EventSource` for the frontend. The pipeline runs as a single RQ supervisor job that calls each step sequentially, publishing events to Redis between steps.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| daphne | latest | ASGI server for Django | Official Django ASGI server; enables async views for SSE without tying workers |
| redis (python) | 7.1.1 (already installed) | Redis pub/sub for event communication | Worker PUBLISHes step events; SSE view SUBSCRIBEs. Already a dependency of django-rq |
| django-rq | 3.2.2 (already installed) | RQ job queue | Pipeline supervisor job runs via `@job` decorator |
| EventSource (browser API) | Built-in | Client-side SSE consumer | Native browser API; automatic reconnection; no library needed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-asyncio | latest | Async test support for pytest | Testing the async SSE view and generator |
| @inertiajs/react | 2.3.14 (already installed) | Inertia.js frontend | Jobs/Show page rendered via Inertia; separate EventSource for SSE |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Daphne | Uvicorn | Uvicorn is faster but Daphne is the official Django ASGI server and integrates with `runserver`; simpler setup |
| Redis pub/sub | Polling ResolutionJob from DB | DB polling works but adds latency (1s+ intervals) and DB load; pub/sub is immediate and Redis is already running |
| Redis pub/sub | django-eventstream | django-eventstream adds a dependency and requires its own middleware; raw Redis pub/sub with `redis.asyncio` is simpler for this use case |
| Native EventSource | reconnecting-eventsource | Not needed; native EventSource already auto-reconnects. The pipeline is short-lived (< 2 min), so reconnection edge cases are rare |
| Async SSE view | Synchronous polling SSE on WSGI | Ties a worker thread per connection; unacceptable for concurrent users. Daphne handles hundreds of async SSE connections per process |

**Installation:**
```bash
uv add daphne pytest-asyncio
```

## Architecture Patterns

### Recommended Project Structure
```
scrapegrape/
    publishers/
        pipeline/                # NEW: Pipeline module
            __init__.py
            supervisor.py        # Pipeline supervisor RQ job
            steps.py             # Individual pipeline step functions
            events.py            # Redis pub/sub event publishing helper
        views.py                 # Extended with URL submission + job redirect
        tests/
            test_pipeline.py     # Pipeline step unit tests
            test_sse.py          # SSE endpoint tests
    jobs/                        # NEW: Jobs app (or views within publishers)
        views.py                 # SSE stream view + Inertia show view
    frontend/src/
        Pages/
            Jobs/
                Show.tsx         # NEW: Streaming results page with EventSource
            Home.tsx             # NEW: Homepage with URL input (or extend Index)
```

### Pattern 1: Daphne ASGI Configuration
**What:** Enable Daphne as the ASGI server for Django development and async SSE views.
**When to use:** Required for SSE streaming responses.
**Example:**
```python
# scrapegrape/scrapegrape/settings.py
INSTALLED_APPS = [
    "daphne",  # MUST be first -- hooks into runserver
    "django.contrib.admin",
    # ... rest unchanged ...
]

ASGI_APPLICATION = "scrapegrape.asgi.application"
```
Source: [Django Daphne docs](https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/daphne/)

### Pattern 2: Redis Pub/Sub Event Publishing (Worker Side)
**What:** The pipeline worker PUBLISHes progress events to a job-specific Redis channel after each step completes.
**When to use:** Every pipeline step completion or failure.
**Example:**
```python
# scrapegrape/publishers/pipeline/events.py
import json
import redis

def get_redis_client():
    """Get a synchronous Redis client (for use in RQ workers)."""
    import os
    host = os.environ.get("REDIS_HOST", "localhost")
    port = int(os.environ.get("REDIS_PORT", 6379))
    return redis.Redis(host=host, port=port, db=0)

def publish_step_event(job_id: str, step: str, status: str, data: dict | None = None):
    """Publish a pipeline step event to the job's Redis channel."""
    r = get_redis_client()
    event = {
        "step": step,
        "status": status,  # "started", "completed", "failed", "skipped"
        "data": data or {},
    }
    r.publish(f"job:{job_id}:events", json.dumps(event))
```

### Pattern 3: Async SSE View with Redis Subscription
**What:** An async Django view that subscribes to the job's Redis channel and yields SSE-formatted events.
**When to use:** The `/api/jobs/<uuid>/stream` endpoint.
**Example:**
```python
# scrapegrape/jobs/views.py
import json
import redis.asyncio as aioredis
from django.http import StreamingHttpResponse

async def job_stream(request, job_id):
    """SSE endpoint: streams pipeline progress events for a job."""
    async def event_generator():
        r = aioredis.Redis(
            host=settings.RQ_QUEUES["default"]["HOST"],
            port=settings.RQ_QUEUES["default"]["PORT"],
        )
        pubsub = r.pubsub()
        await pubsub.subscribe(f"job:{job_id}:events")

        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                yield f"data: {data}\n\n"

                # Check if this is a terminal event
                parsed = json.loads(data)
                if parsed.get("status") in ("completed", "failed") and parsed.get("step") == "pipeline":
                    yield f"event: done\ndata: {data}\n\n"
                    break
        finally:
            await pubsub.unsubscribe(f"job:{job_id}:events")
            await pubsub.close()
            await r.close()

    response = StreamingHttpResponse(
        streaming_content=event_generator(),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
```
Sources: [Django SSE patterns](https://minimalistdjango.com/TIL/2024-04-21-server-sent-events/), [Redis pub/sub async](https://saktidwicahyono.name/blogs/async-and-sync-python-pubsub-with-redis/)

### Pattern 4: Pipeline Supervisor Job
**What:** A single RQ job that runs all pipeline steps sequentially, publishing events between steps.
**When to use:** Queued when a URL is submitted.
**Example:**
```python
# scrapegrape/publishers/pipeline/supervisor.py
from django_rq import job
from django.utils import timezone
from publishers.models import Publisher, ResolutionJob
from publishers.pipeline.events import publish_step_event

@job("default", timeout=600)
def run_pipeline(job_id: str):
    """Pipeline supervisor: runs all steps sequentially for a ResolutionJob."""
    resolution_job = ResolutionJob.objects.select_related("publisher").get(id=job_id)
    resolution_job.status = "running"
    resolution_job.save(update_fields=["status"])
    publisher = resolution_job.publisher

    try:
        # Step 1: Publisher resolution (already done at job creation)
        publish_step_event(job_id, "publisher_resolution", "completed",
                           {"publisher_name": publisher.name, "domain": publisher.domain})

        # Check freshness TTL
        if should_skip_publisher_steps(publisher):
            publish_step_event(job_id, "waf", "skipped", {"reason": "fresh"})
            publish_step_event(job_id, "tos_discovery", "skipped", {"reason": "fresh"})
            publish_step_event(job_id, "tos_evaluation", "skipped", {"reason": "fresh"})
        else:
            # Step 2: WAF check
            publish_step_event(job_id, "waf", "started")
            waf_result = run_waf_step(publisher)
            resolution_job.waf_result = waf_result
            resolution_job.save(update_fields=["waf_result"])
            publish_step_event(job_id, "waf", "completed", waf_result)

            # Step 3: ToS discovery
            publish_step_event(job_id, "tos_discovery", "started")
            tos_result = run_tos_discovery_step(publisher)
            resolution_job.tos_result = tos_result
            resolution_job.save(update_fields=["tos_result"])
            publish_step_event(job_id, "tos_discovery", "completed", tos_result)

            # Step 4: ToS evaluation
            publish_step_event(job_id, "tos_evaluation", "started")
            # ... evaluate ToS ...

            # Update publisher freshness
            publisher.last_checked_at = timezone.now()
            publisher.save(update_fields=["last_checked_at"])

        # Mark job complete
        resolution_job.status = "completed"
        resolution_job.save(update_fields=["status", "updated_at"])
        publish_step_event(job_id, "pipeline", "completed")

    except Exception as e:
        resolution_job.status = "failed"
        resolution_job.save(update_fields=["status"])
        publish_step_event(job_id, "pipeline", "failed", {"error": str(e)})
        raise
```

### Pattern 5: URL Submission with Duplicate Detection
**What:** POST endpoint that sanitizes URL, checks for existing job, creates ResolutionJob, and redirects.
**When to use:** Homepage form submission.
**Example:**
```python
# In publishers/views.py or a new jobs/views.py
from publishers.url_sanitizer import sanitize_url, extract_domain

def submit_url(request):
    """Handle URL submission: deduplicate, create job, redirect to results."""
    if request.method == "POST":
        raw_url = request.POST.get("url", "").strip()
        canonical_url = sanitize_url(raw_url)

        # Check for existing completed job with this canonical URL
        existing = ResolutionJob.objects.filter(
            canonical_url=canonical_url,
            status="completed",
        ).first()
        if existing:
            return redirect(f"/jobs/{existing.id}")

        # Get or create publisher
        domain = extract_domain(raw_url)
        publisher, _ = Publisher.objects.get_or_create(
            domain=domain,
            defaults={"name": domain, "url": canonical_url},
        )

        # Create new job
        job = ResolutionJob.objects.create(
            submitted_url=raw_url,
            canonical_url=canonical_url,
            publisher=publisher,
        )

        # Queue pipeline
        run_pipeline.delay(str(job.id))

        return redirect(f"/jobs/{job.id}")
```

### Pattern 6: Frontend EventSource Integration
**What:** React component that opens an EventSource connection and updates state as events arrive.
**When to use:** Jobs/Show.tsx page.
**Example:**
```tsx
// Pages/Jobs/Show.tsx
import { useEffect, useState } from 'react'

interface PipelineEvent {
    step: string
    status: 'started' | 'completed' | 'failed' | 'skipped'
    data: Record<string, unknown>
}

interface Props {
    job: {
        id: string
        status: string
        canonical_url: string
        publisher_name: string
        waf_result: Record<string, unknown> | null
        tos_result: Record<string, unknown> | null
    }
}

function Show({ job }: Props) {
    const [events, setEvents] = useState<PipelineEvent[]>([])
    const [connected, setConnected] = useState(false)

    useEffect(() => {
        if (job.status === 'completed' || job.status === 'failed') return

        const es = new EventSource(`/api/jobs/${job.id}/stream`)

        es.onopen = () => setConnected(true)

        es.onmessage = (event) => {
            const data: PipelineEvent = JSON.parse(event.data)
            setEvents(prev => [...prev, data])
        }

        es.addEventListener('done', () => {
            es.close()
            setConnected(false)
            // Optionally reload via Inertia to get final data
        })

        es.onerror = () => {
            // EventSource will auto-reconnect
            setConnected(false)
        }

        return () => es.close()
    }, [job.id, job.status])

    // Render progress cards based on events...
}
```

### Pattern 7: Inertia Page for Job Results (Non-SSE Data)
**What:** Inertia view that renders the Jobs/Show page with initial job data. SSE is handled by a separate endpoint.
**When to use:** `/jobs/<uuid>` route.
**Example:**
```python
# jobs/views.py (Inertia view)
from inertia import render as inertia_render
from publishers.models import ResolutionJob

def job_show(request, job_id):
    """Render the job results page via Inertia."""
    job = ResolutionJob.objects.select_related("publisher").get(id=job_id)
    return inertia_render(request, "Jobs/Show", props={
        "job": {
            "id": str(job.id),
            "status": job.status,
            "canonical_url": job.canonical_url,
            "submitted_url": job.submitted_url,
            "publisher_name": job.publisher.name,
            "publisher_domain": job.publisher.domain,
            "waf_result": job.waf_result,
            "tos_result": job.tos_result,
            "created_at": job.created_at.isoformat(),
        },
    })
```

### Anti-Patterns to Avoid
- **SSE on WSGI:** Never use synchronous `StreamingHttpResponse` with `time.sleep()` for SSE -- it ties a worker thread per connection and cannot scale. Use Daphne (ASGI).
- **Polling the database for step progress:** Adds latency and DB load. Use Redis pub/sub for immediate event delivery.
- **Running pipeline steps as separate RQ jobs:** Creates coordination complexity (job chaining, failure handling, partial state). A single supervisor job is simpler and matches PIPE-02.
- **Putting SSE logic in an Inertia view:** Inertia views return JSON props. SSE needs `text/event-stream` content type. Use a separate plain Django view for the SSE endpoint.
- **Creating EventSource before the RQ job starts:** The SSE subscriber might miss early events. The publisher side should also replay the current state on subscription, or the Inertia page should render initial state from the DB.
- **Not closing the EventSource on terminal events:** The browser will auto-reconnect to a closed stream. Send a `done` event and call `es.close()` client-side.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ASGI server | Custom async HTTP server | Daphne | Production-grade; integrates with Django's runserver; handles connection lifecycle |
| Event pub/sub | Custom WebSocket or long-polling | Redis pub/sub via `redis.asyncio` | Already have Redis; immediate delivery; built-in channel management |
| SSE protocol formatting | Custom event framing | Standard `data: ...\n\n` format | Browser EventSource expects exactly this format |
| Client-side SSE | Custom XHR polling | Native `EventSource` API | Built into all browsers; auto-reconnection; standard API |
| Pipeline step coordination | Custom job chaining with multiple RQ jobs | Single supervisor job | Simpler error handling; sequential execution matches requirements |
| URL deduplication | Custom duplicate checking | Query `ResolutionJob.objects.filter(canonical_url=...)` | Index already exists on `canonical_url`; simple query |

**Key insight:** The pipeline is a single RQ job that runs steps sequentially and PUBLISHes events to Redis. The SSE view SUBSCRIBEs to those events. The two are decoupled via Redis pub/sub -- the worker doesn't know about SSE, and the SSE view doesn't know about pipeline logic.

## Common Pitfalls

### Pitfall 1: SSE Events Missed Due to Race Condition
**What goes wrong:** The EventSource connects after the pipeline has already started, missing early events (e.g., "publisher_resolution completed").
**Why it happens:** The redirect to `/jobs/<uuid>` happens after `run_pipeline.delay()`, and by the time the browser connects the EventSource, the first step may already be done.
**How to avoid:** Two complementary strategies: (1) The Inertia `job_show` view reads current state from the DB (already-completed steps) and passes it as initial props. (2) The EventSource picks up from where the page left off. The frontend renders initial state from props AND appends SSE events.
**Warning signs:** "publisher_resolution" card never appears but later steps do.

### Pitfall 2: Daphne Not Serving Inertia Views Correctly
**What goes wrong:** Existing Inertia pages break after adding Daphne.
**Why it happens:** Daphne serves all requests (including WSGI-style synchronous views) via ASGI. Most Django middleware is compatible, but some custom middleware may not handle the ASGI call pattern.
**How to avoid:** The InertiaMiddleware in this project is a simple synchronous middleware (no `MiddlewareMixin` needed) that just checks headers. It works under both WSGI and ASGI. The custom `inertia_share` middleware is also a simple callable -- compatible. Test all existing pages after adding Daphne.
**Warning signs:** 500 errors on existing pages after Daphne is enabled.

### Pitfall 3: Redis Pub/Sub Message Lost if No Subscriber
**What goes wrong:** If the SSE view hasn't subscribed yet when the worker publishes an event, the event is lost (Redis pub/sub has no persistence).
**Why it happens:** Redis pub/sub is fire-and-forget -- messages are only delivered to current subscribers.
**How to avoid:** This is handled by Pattern 1 of Pitfall 1 above: read initial state from DB. Additionally, the pipeline steps save results to the ResolutionJob model *before* publishing events. If the SSE subscriber misses an event, the data is still in the DB and visible on page reload.
**Warning signs:** Intermittent missing step cards, especially on fast publishers.

### Pitfall 4: StreamingHttpResponse on WSGI Instead of ASGI
**What goes wrong:** `StreamingHttpResponse` with an async generator raises `TypeError: async_generator object is not iterable` under WSGI.
**Why it happens:** Django's WSGI handler cannot consume async iterators.
**How to avoid:** Ensure Daphne is installed, added as first in `INSTALLED_APPS`, and `ASGI_APPLICATION` is set. Verify with `manage.py runserver` -- Daphne prints its own startup message.
**Warning signs:** TypeError on the SSE endpoint; "Starting Daphne" message missing from server startup.

### Pitfall 5: EventSource Auto-Reconnect on Terminal Events
**What goes wrong:** After the pipeline completes, EventSource auto-reconnects to the SSE endpoint, causing unnecessary Redis subscriptions and server load.
**Why it happens:** EventSource reconnects by default when the connection closes.
**How to avoid:** Send a custom `event: done` event from the server. Handle it client-side with `es.addEventListener('done', () => es.close())`. Alternatively, the SSE view can check the job status in the DB before subscribing -- if already completed, yield the final state and close.
**Warning signs:** Redis subscriber count keeps growing; SSE connections to completed jobs.

### Pitfall 6: Pipeline Job Fails but ResolutionJob Stays "Running"
**What goes wrong:** An unhandled exception in the pipeline worker leaves the job in "running" status forever.
**Why it happens:** Exception occurs before the `status = "failed"` save.
**How to avoid:** Wrap the entire pipeline in try/except. Always set status to "failed" in the except block before re-raising. The SSE view should also handle the case where it never receives a terminal event (timeout after a reasonable period).
**Warning signs:** Jobs stuck in "running" status; SSE connections that never close.

### Pitfall 7: Forgetting `X-Accel-Buffering: no` Header
**What goes wrong:** Nginx (or similar reverse proxy) buffers the SSE response, so the client receives all events at once when the connection closes instead of progressively.
**Why it happens:** Nginx buffers upstream responses by default.
**How to avoid:** Set `response["X-Accel-Buffering"] = "no"` on the SSE StreamingHttpResponse. Also set `Cache-Control: no-cache`.
**Warning signs:** Events appear all at once instead of progressively.

### Pitfall 8: Existing `analyze_url` Task Conflicts with New Pipeline
**What goes wrong:** The old `analyze_url` task in `publishers/tasks.py` conflicts with the new pipeline supervisor.
**Why it happens:** Both try to do similar work (WAF, terms discovery, evaluation) but with different patterns.
**How to avoid:** Keep the existing `analyze_url` task for admin actions (backward compatibility, per RPRT-05). The new pipeline supervisor is a separate function. They share step logic but are invoked differently.
**Warning signs:** Duplicate analysis runs; inconsistent results between admin actions and URL submission.

## Code Examples

Verified patterns from official sources and codebase analysis:

### Daphne Configuration
```python
# scrapegrape/scrapegrape/settings.py
# Source: https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/daphne/
INSTALLED_APPS = [
    "daphne",  # Must be first
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_vite",
    "django_object_actions",
    "django_rq",
    "rest_framework",
    "inertia",
    "ingestion",
    "publishers",
]

ASGI_APPLICATION = "scrapegrape.asgi.application"
```

### Redis Pub/Sub Event Format
```python
# SSE event format for each pipeline step
# Published to Redis channel: job:{uuid}:events
{
    "step": "waf",                    # Step name
    "status": "completed",            # started | completed | failed | skipped
    "data": {                         # Step-specific data
        "waf_detected": true,
        "waf_type": "Cloudflare"
    }
}

# Terminal event format
{
    "step": "pipeline",
    "status": "completed",           # or "failed"
    "data": {}
}
```

### URL Configuration
```python
# scrapegrape/scrapegrape/urls.py
from django.urls import path
import publishers.views
import jobs.views  # or publishers.pipeline.views

urlpatterns = [
    # Existing routes
    path("admin/", admin.site.urls),
    path("django-rq/", include("django_rq.urls")),
    path("", publishers.views.table, name="table"),
    # ... existing publisher routes ...

    # NEW: URL submission
    path("submit", jobs.views.submit_url, name="submit-url"),

    # NEW: Job views
    path("jobs/<uuid:job_id>", jobs.views.job_show, name="job-show"),

    # NEW: SSE stream endpoint (non-Inertia, plain Django async view)
    path("api/jobs/<uuid:job_id>/stream", jobs.views.job_stream, name="job-stream"),
]
```

### Testing SSE Endpoint
```python
# Source: pytest-asyncio + Django async test client
import pytest
import json
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_sse_endpoint_streams_events(async_client, resolution_job):
    """Verify SSE endpoint returns text/event-stream and streams events."""
    # The SSE view should return streaming response
    response = await async_client.get(f"/api/jobs/{resolution_job.id}/stream")
    assert response.status_code == 200
    assert response["Content-Type"] == "text/event-stream"

@pytest.mark.django_db
def test_submit_url_creates_job(client):
    """Verify URL submission creates a ResolutionJob and redirects."""
    response = client.post("/submit", {"url": "https://example.com/article"})
    assert response.status_code == 302
    assert "/jobs/" in response.url

@pytest.mark.django_db
def test_duplicate_url_redirects_to_existing(client, db):
    """Verify duplicate URL submission redirects to existing job."""
    # Create a completed job first
    from publishers.factories import ResolutionJobFactory
    existing = ResolutionJobFactory(
        canonical_url="https://example.com/article",
        status="completed",
    )
    response = client.post("/submit", {"url": "https://example.com/article"})
    assert response.status_code == 302
    assert str(existing.id) in response.url
```

### Testing Pipeline Steps with Mocked External Services
```python
# Source: Project test conventions (monkeypatch, factory_boy)
@pytest.mark.django_db
class TestPipelineSteps:
    def test_waf_step_stores_result(self, monkeypatch, publisher):
        """WAF step runs wafw00f and returns structured result."""
        mock_scan = {"report": [{"detected": True, "firewall": "Cloudflare",
                                  "manufacturer": "Cloudflare Inc.", "url": publisher.url}]}
        monkeypatch.setattr(
            "publishers.pipeline.steps.scan_url_with_wafw00f",
            lambda url: mock_scan,
        )
        result = run_waf_step(publisher)
        assert result["waf_detected"] is True
        assert result["waf_type"] == "Cloudflare"

    def test_tos_discovery_step_uses_fetch_strategy(self, monkeypatch, publisher):
        """ToS discovery uses FetchStrategyManager, not direct Zyte call."""
        # Mock FetchStrategyManager to return test HTML
        mock_result = FetchResult(html="<html><a href='/tos'>Terms</a></html>",
                                   status_code=200, strategy_used="curl_cffi",
                                   url=publisher.url)
        monkeypatch.setattr(
            "publishers.pipeline.steps.FetchStrategyManager.fetch",
            lambda self, url, publisher=None: mock_result,
        )
        # Mock the LLM agent
        monkeypatch.setattr(
            "publishers.pipeline.steps.terms_discovery_agent.run_sync",
            lambda prompt: MockAgentResult(terms_url="https://example.com/tos"),
        )
        result = run_tos_discovery_step(publisher)
        assert "tos_url" in result
```

### Freshness TTL Check
```python
# Source: Codebase settings.py (PUBLISHER_FRESHNESS_TTL = timedelta(hours=24))
from django.conf import settings
from django.utils import timezone

def should_skip_publisher_steps(publisher) -> bool:
    """Check if publisher was analyzed within the configured TTL."""
    if not publisher.last_checked_at:
        return False
    age = timezone.now() - publisher.last_checked_at
    return age < settings.PUBLISHER_FRESHNESS_TTL
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| WSGI-only Django | ASGI via Daphne for async views | Django 4.2+ (2023) | Enables SSE without tying worker threads |
| Synchronous SSE with `time.sleep()` | Async SSE with Redis pub/sub | N/A (architecture) | Scalable to many concurrent SSE connections |
| Multiple RQ jobs per pipeline | Single supervisor job (PIPE-02) | v2.0 decision | Simpler error handling; sequential execution |
| Direct Zyte API calls in terms discovery | FetchStrategyManager with fallback | Phase 7 | All fetching goes through strategy manager |
| `analyze_url` monolithic task | Modular pipeline steps in supervisor | Phase 8 | Reusable steps; progress events; step-level results |

**Deprecated/outdated:**
- Using `time.sleep()` in a synchronous `StreamingHttpResponse` for SSE: Ties a WSGI worker thread. Use async views with Daphne instead.
- `django-sse` (niwinz): Unmaintained since 2013. Use raw `StreamingHttpResponse` with async generator.
- `cloudscraper` for WAF bypass: Cannot pass modern Cloudflare. Already replaced by curl-cffi in Phase 7.

## Open Questions

1. **Homepage design: separate page vs. modified Index**
   - What we know: ENTRY-01 requires "a prominent input on the homepage." Current homepage (`/`) is the publisher table (admin/management view). RPRT-05 says publisher table continues working.
   - What's unclear: Whether to add the URL input to the existing publisher table page or create a new homepage.
   - Recommendation: Add a URL input form above the publisher table on the existing Index page. This satisfies both ENTRY-01 and RPRT-05 without URL restructuring. The form POSTs to `/submit` which redirects to `/jobs/<uuid>`.

2. **SSE endpoint: authentication required?**
   - What we know: The app currently has no login requirement for any views. Admin is separate.
   - What's unclear: Whether SSE endpoints should require authentication.
   - Recommendation: No authentication for Phase 8. The SSE endpoint is read-only and keyed by UUID (unguessable). Authentication can be added later.

3. **Pipeline step failures: retry or fail-fast?**
   - What we know: PIPE-02 specifies sequential execution. Current `analyze_url` continues on step failure.
   - What's unclear: Whether a WAF step failure should prevent ToS discovery.
   - Recommendation: Fail-fast for hard errors (network failures), continue for soft failures (WAF detected but page still fetchable). Each step should report its result even if the result is "error." The pipeline should only set status="failed" on unrecoverable errors.

4. **Redis connection management in async SSE view**
   - What we know: `redis.asyncio` is available (bundled with redis-py 7.1.1). PubSub objects should not be shared between tasks.
   - What's unclear: Whether to use connection pooling or create per-request connections.
   - Recommendation: Create a new `redis.asyncio.Redis` connection per SSE request. Connection count is bounded by concurrent viewers. Close connection in the generator's `finally` block.

5. **Pipeline steps: reuse existing `ingestion/` code or rewrite?**
   - What we know: Existing `terms_discovery.py` and `terms_evaluation.py` use `fetch_html_via_proxy` (raw Zyte). Phase 7 introduced `FetchStrategyManager`.
   - What's unclear: Whether to refactor existing ingestion code to use FetchStrategyManager or wrap it.
   - Recommendation: Create new pipeline step functions in `publishers/pipeline/steps.py` that use `FetchStrategyManager` for fetching and call the existing pydantic-ai agents for analysis. This keeps the existing ingestion code working (for admin actions) while the new pipeline uses the strategy manager.

## Sources

### Primary (HIGH confidence)
- [Django Daphne deployment docs](https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/daphne/) - Daphne configuration, INSTALLED_APPS, ASGI_APPLICATION
- [Django StreamingHttpResponse docs](https://docs.djangoproject.com/en/5.2/ref/request-response/#streaminghttpresponse-objects) - Async iterator support, content_type
- [Redis pub/sub docs](https://redis.io/docs/latest/develop/pubsub/) - PUBLISH, SUBSCRIBE, channel patterns
- [MDN EventSource docs](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events) - SSE protocol format, auto-reconnection
- Existing codebase analysis: `publishers/models.py`, `publishers/tasks.py`, `publishers/fetchers/`, `ingestion/terms_discovery.py`, `ingestion/terms_evaluation.py`, `scrapegrape/settings.py`

### Secondary (MEDIUM confidence)
- [Django SSE with Daphne](https://tomdekan.com/articles/server-sent-events-daphne) - Practical async SSE view pattern with Daphne
- [Django StreamingHttpResponse internals](https://blog.pecar.me/django-streaming-responses) - WSGI vs ASGI chunked response handling, concurrency implications
- [Django SSE with PostgreSQL LISTEN/NOTIFY](https://valberg.dk/django-sse-postgresql-listen-notify.html) - Async SSE view pattern, Last-Event-ID handling
- [Django REST Framework SSE](https://plainenglish.io/blog/server-sent-event-feature-in-django-rest-framework) - Redis pub/sub async generator pattern, X-Accel-Buffering header
- [SSE in React](https://oneuptime.com/blog/post/2026-01-15-server-sent-events-sse-react/view) - EventSource hooks pattern

### Tertiary (LOW confidence)
- InertiaMiddleware ASGI compatibility: verified by reading source code (`inertia/middleware.py`), but no official documentation confirms ASGI support. The middleware is simple enough that it should work, but needs testing.
- pytest-asyncio with Django async test client: [pytest-django issue #864](https://github.com/pytest-dev/pytest-django/issues/864) discusses async_client fixture -- needs verification that streaming responses work in tests.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Daphne is official Django ASGI server; Redis pub/sub is well-documented; EventSource is a browser standard
- Architecture: HIGH - Pattern (RQ worker -> Redis pub/sub -> async SSE view -> EventSource) is well-established in Django ecosystem
- Pipeline design: HIGH - Single supervisor job with step functions matches PIPE-02; all building blocks exist in codebase
- SSE implementation: MEDIUM - Async SSE views with Daphne are documented but less commonly tested at scale; connection lifecycle management needs care
- Testing: MEDIUM - Async SSE testing with pytest-asyncio + Django is less established; may need creative approaches for streaming response verification
- Inertia + SSE coexistence: MEDIUM - Verified by reading InertiaMiddleware source, but no official docs confirm ASGI compatibility

**Research date:** 2026-02-14
**Valid until:** 2026-03-14 (30 days -- Django 5.2, Daphne, redis-py are all stable)
