# Pitfalls Research

**Domain:** Adding URL analysis workflow (SSE streaming, RQ task pipeline, curl-cffi fetching, metadata extraction) to existing Django 5.2 + Inertia.js + React 19 app
**Researched:** 2026-02-13
**Confidence:** MEDIUM (verified across official docs, GitHub issues, and community sources; some curl-cffi specifics are LOW confidence)

## Critical Pitfalls

### Pitfall 1: InertiaMiddleware Interfering with SSE StreamingHttpResponse

**What goes wrong:**
SSE endpoints return `StreamingHttpResponse`, but the Inertia middleware runs on every request. While the current `InertiaMiddleware` checks for `X-Inertia` header and passes through non-Inertia requests, the custom `inertia_share` middleware in `scrapegrape/middleware.py` calls `share()` on every request -- including SSE endpoints. This attaches session-backed lazy props (auth, flash, errors) to SSE requests that never use them, causing unnecessary session reads and potential `session.pop()` side effects on SSE polling.

**Why it happens:**
The Inertia middleware stack was designed assuming all routes are Inertia page requests. SSE endpoints are a fundamentally different response type (long-lived, streaming) that the middleware was never designed to handle. The `InertiaMiddleware` itself is safe (it checks `X-Inertia` header), but custom share middleware and Django's own `CommonMiddleware`, `SessionMiddleware`, and especially `GZipMiddleware` can all interfere.

**How to avoid:**
1. SSE views must return `StreamingHttpResponse` with `Content-Type: text/event-stream`. The Inertia middleware will pass these through because the browser does not send `X-Inertia` headers on `EventSource` requests.
2. Modify `inertia_share` middleware to skip SSE routes:
```python
def inertia_share(get_response):
    def middleware(request):
        # Skip Inertia sharing for SSE/API endpoints
        if request.path.startswith('/api/') or request.path.startswith('/sse/'):
            return get_response(request)
        share(request, auth=lambda: {...}, flash=lambda: {...}, errors=lambda: {...})
        return get_response(request)
    return middleware
```
3. Do NOT add `GZipMiddleware` -- Django ticket #36655 confirms it buffers entire streaming responses, completely breaking SSE. If already present, exclude streaming responses.
4. Set `Cache-Control: no-cache` and `X-Accel-Buffering: no` headers on SSE responses to prevent nginx proxy buffering.

**Warning signs:**
- SSE events arrive in batches instead of one-at-a-time
- SSE connection succeeds but no events appear until connection closes
- Session data (flash messages) disappearing unexpectedly after SSE connections
- Browser DevTools EventStream tab shows nothing, then dumps everything at once

**Phase to address:**
Infrastructure phase (when adding SSE endpoint). Must be the first SSE integration test: verify a single event streams immediately to the browser.

---

### Pitfall 2: WSGI Worker Exhaustion from Long-Lived SSE Connections

**What goes wrong:**
Each SSE connection holds a WSGI worker process for its entire lifetime. The current setup uses `WSGI_APPLICATION = "scrapegrape.wsgi.application"` with Django's dev server (and presumably gunicorn in production). With even 3-5 concurrent URL analyses, all gunicorn workers are occupied by SSE connections, and the entire app becomes unresponsive -- no pages load, no API calls succeed.

**Why it happens:**
WSGI was designed for short-lived request/response cycles. SSE connections are long-lived (30 seconds to several minutes for a full analysis pipeline). A typical gunicorn deployment has 2-4 workers per CPU core. Each SSE connection permanently occupies one worker until the analysis completes or the client disconnects.

**How to avoid:**
1. Use a dedicated SSE approach that does not hold WSGI workers:
   - **Option A (Recommended):** Use Django's async view support with `StreamingHttpResponse` and an `async def` view, served via an ASGI server (uvicorn/daphne) for SSE routes only. The rest of the app stays WSGI.
   - **Option B:** Use a separate lightweight SSE service (e.g., a small FastAPI/Starlette app) that reads progress from Redis and streams to clients. Django RQ workers write progress to Redis; the SSE service reads and streams it.
   - **Option C:** Use polling instead of SSE. Client polls a `/api/job/<id>/status` endpoint every 2 seconds. Simpler but worse UX.
2. If using gunicorn with SSE, switch to `--worker-class gthread` with `--threads 4-8` so each worker handles multiple connections. But this still has limits.
3. Set aggressive SSE timeouts -- close the connection after the analysis completes (do not keep it open indefinitely).
4. gunicorn `--timeout` must be higher than the maximum analysis duration, or workers will be killed mid-stream. Default 30 seconds will kill most analyses.

**Warning signs:**
- App becomes unresponsive when multiple analyses run simultaneously
- gunicorn logs: `[CRITICAL] WORKER TIMEOUT`
- SSE connections terminate prematurely with no error
- CPU/memory usage stays low but requests queue up

**Phase to address:**
Infrastructure phase. This is an architectural decision that must be made before implementing SSE. Changing from WSGI to ASGI or adding a polling fallback after SSE is built is a significant rework.

---

### Pitfall 3: RQ Dependent Jobs Silently Abandoned on Parent Failure

**What goes wrong:**
The URL analysis pipeline is a chain: URL normalization -> robots.txt check -> page fetch -> metadata extraction -> LLM publisher resolution. If an early job fails (e.g., robots.txt fetch times out), dependent jobs are never enqueued by default. The SSE stream shows the pipeline "stuck" at a step forever -- no error, no completion, no progress update.

**Why it happens:**
RQ's default behavior is to only enqueue dependent jobs when the parent succeeds. Jobs that fail are moved to `FailedJobRegistry`, and dependents stay in `DeferredJobRegistry` forever. There is a `Dependency(allow_failure=True)` option, but it has a known bug (GitHub issue #2006): jobs moved to `FailedJobRegistry` due to `AbandonedJobError` (worker crash, OOM) never trigger dependent enqueueing even with `allow_failure=True`.

**How to avoid:**
1. Use `on_failure` callbacks on every job in the chain to update progress state in Redis:
```python
from rq import Callback

queue.enqueue(
    fetch_page,
    depends_on=Dependency(jobs=[robots_job], allow_failure=True),
    on_failure=Callback(handle_step_failure),
    on_success=Callback(handle_step_success),
)

def handle_step_failure(job, connection, type, value, traceback):
    # Update Redis progress key so SSE stream can report the failure
    redis_conn.hset(f"analysis:{job.meta['analysis_id']}", 'status', 'failed')
    redis_conn.hset(f"analysis:{job.meta['analysis_id']}", 'error', str(value))
    redis_conn.hset(f"analysis:{job.meta['analysis_id']}", 'failed_step', job.func_name)
```
2. Implement a "pipeline supervisor" pattern: a single parent job that orchestrates steps sequentially rather than chaining via `depends_on`. This gives you explicit error handling at each step:
```python
@job
def run_analysis_pipeline(url, analysis_id):
    update_progress(analysis_id, 'normalizing', 0)
    normalized = normalize_url(url)

    update_progress(analysis_id, 'checking_robots', 20)
    try:
        robots_ok = check_robots(normalized)
    except Exception as e:
        update_progress(analysis_id, 'robots_failed', 20, error=str(e))
        # Continue anyway or abort based on policy

    update_progress(analysis_id, 'fetching', 40)
    html = fetch_page(normalized)
    # ... etc
```
3. Set `job_timeout` on every job. Default RQ timeout is 180 seconds, but some steps (LLM calls, Zyte fetches) may need more. Without explicit timeouts, a stuck job holds the worker indefinitely.
4. Monitor `FailedJobRegistry` and `DeferredJobRegistry` sizes. Orphaned deferred jobs indicate broken chains.

**Warning signs:**
- Progress bar gets stuck at a specific percentage and never moves
- Redis `DeferredJobRegistry` grows over time
- `FailedJobRegistry` has jobs but no corresponding error shown to user
- Analysis jobs "complete" but some steps show no results

**Phase to address:**
Task pipeline phase. The decision between dependency chaining vs. supervisor pattern is architectural and must happen before implementing individual pipeline steps.

---

### Pitfall 4: curl-cffi Session Crashes Python Process When Closing Streaming Connections

**What goes wrong:**
curl-cffi has a documented bug (GitHub issue #675) where closing a `Session` or `Response` during an incomplete streaming request causes a segfault -- the Python process crashes without a Python exception. If curl-cffi is used to fetch pages that respond slowly or use chunked transfer encoding, and you implement a timeout that cancels the request, the entire RQ worker process dies.

**Why it happens:**
When `stream=True` is used and the response is not fully consumed before `close()` is called, curl-cffi's underlying C library (curl-impersonate) has a cleanup race condition. The Python interpreter exits abruptly (segfault from curl handle cleanup). Setting `keep_alive=False` reduces but does not eliminate the crash.

**How to avoid:**
1. Never use `stream=True` with curl-cffi for page fetching. Always consume the full response:
```python
from curl_cffi.requests import Session

with Session(impersonate="chrome") as s:
    response = s.get(url, timeout=30)  # NOT stream=True
    html = response.text
```
2. Always use curl-cffi `Session` as a context manager (`with Session() as s:`) to ensure proper cleanup.
3. Set explicit `timeout` on every request. curl-cffi's stream mode timeout has documented issues where timeout has no effect during streaming.
4. If you need to abort a long-running fetch, do it via `signal.alarm()` or RQ's `job_timeout` rather than trying to close the curl-cffi session mid-stream.
5. For the Zyte fallback path, continue using `requests` (as the existing `fetch_html_via_proxy` does) -- do not switch Zyte calls to curl-cffi.

**Warning signs:**
- RQ worker processes disappearing with no Python traceback
- `Segmentation fault` in Docker logs
- Workers constantly restarting
- Jobs marked as `lost` in RQ dashboard

**Phase to address:**
Page fetching phase. Must be validated early with a smoke test against slow/chunked-response sites before building the full pipeline on top of curl-cffi.

---

### Pitfall 5: URL Normalization Creating Duplicate Publishers

**What goes wrong:**
The existing `normalize_url()` in `tasks.py` strips to `scheme://netloc`, but URLs arrive in many forms: `https://www.nytimes.com`, `https://nytimes.com`, `https://NYTimes.com`, `https://www.nytimes.com/`, `http://nytimes.com`. Each creates a different `Publisher` record because `Publisher.objects.get_or_create(url=base_url)` does exact string matching. Over time, the database fills with duplicate publishers that should be the same entity.

**Why it happens:**
The current normalization is minimal: `f"{parsed_url.scheme}://{parsed_url.netloc}"`. It does not:
- Lowercase the hostname (`NYTimes.com` vs `nytimes.com`)
- Strip `www.` prefix consistently (name extraction does this, but URL storage does not)
- Normalize scheme (`http` vs `https`)
- Handle trailing slashes
- Handle IDN/punycode domains (`xn--...`)
- Handle port numbers (`:80` for HTTP, `:443` for HTTPS are default and should be stripped)

**How to avoid:**
1. Implement a proper normalization function:
```python
from urllib.parse import urlparse

def normalize_publisher_url(url: str) -> str:
    """Canonical publisher URL for deduplication."""
    parsed = urlparse(url.strip())

    # Default to https
    scheme = 'https'

    # Lowercase and strip www
    hostname = parsed.hostname.lower() if parsed.hostname else ''
    if hostname.startswith('www.'):
        hostname = hostname[4:]

    # Strip default ports
    port = parsed.port
    if port in (80, 443, None):
        port_str = ''
    else:
        port_str = f':{port}'

    return f'{scheme}://{hostname}{port_str}'
```
2. Add a database unique constraint or index on the normalized URL.
3. Migrate existing publisher URLs to normalized form before deploying the new pipeline.
4. Use the `url-normalize` library for comprehensive edge case handling (IDN, unicode NFC normalization, dot-segment removal) if you encounter international domains.

**Warning signs:**
- Publisher count grows faster than expected
- Same publisher name appears multiple times in the table
- WAF reports and terms results split across duplicate publisher records
- LLM publisher resolution returns different names for what should be the same publisher

**Phase to address:**
URL normalization phase (must be one of the first steps). This is a data model concern that affects everything downstream. Retroactive deduplication is painful.

---

### Pitfall 6: SSE Connection Not Cleaned Up on React Component Unmount

**What goes wrong:**
User starts a URL analysis, sees the progress stream, then navigates away (Inertia client-side navigation). The `EventSource` connection stays open because the component unmounted without closing it. The server-side SSE view keeps the WSGI/ASGI worker occupied, streaming events into the void. With Inertia's client-side navigation, this happens on every page change -- users accumulate zombie SSE connections.

**Why it happens:**
Inertia's `router.visit()` unmounts the current page component and mounts the new one. If the `EventSource` is created in a `useEffect` without a cleanup function, or if the cleanup function has a stale closure over the `EventSource` ref, the connection is never closed. Using `useState` to store the `EventSource` instance instead of `useRef` causes re-renders that can create duplicate connections.

**How to avoid:**
```typescript
function AnalysisProgress({ analysisId }: { analysisId: string }) {
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const es = new EventSource(`/sse/analysis/${analysisId}/`);
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      const data = JSON.parse(event.data);
      // update state...
    };

    es.addEventListener('complete', () => {
      es.close(); // Close when pipeline finishes
      eventSourceRef.current = null;
    });

    es.onerror = () => {
      // Only reconnect if not intentionally closed
      if (es.readyState === EventSource.CLOSED) {
        reconnectTimeoutRef.current = setTimeout(() => {
          // reconnect logic with backoff
        }, 3000);
      }
    };

    // CRITICAL: cleanup on unmount
    return () => {
      es.close();
      eventSourceRef.current = null;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [analysisId]); // Only re-run if analysisId changes
}
```
Key rules:
1. Store `EventSource` in `useRef`, not `useState`.
2. Always return a cleanup function from `useEffect` that calls `es.close()`.
3. Clear any reconnection timeouts in the cleanup function.
4. Send a `complete` event type from the server when the pipeline finishes so the client closes proactively.
5. Do not put the `EventSource` creation in a function that's called on user interaction without tracking and closing previous connections.

**Warning signs:**
- Server-side worker count climbs over time even when users are idle
- Multiple SSE connections visible in browser DevTools Network tab for the same analysis
- Memory usage on the server grows steadily
- "Max connections" errors in Redis or gunicorn

**Phase to address:**
SSE frontend integration phase. Must be tested specifically with Inertia page navigation -- not just unmounting the component in isolation.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Polling instead of SSE | No ASGI server needed, simpler architecture | 2-second latency on progress, more server load from polling requests, worse UX | Acceptable for MVP if SSE architecture is too complex to add now. Easy to replace later since the progress-in-Redis pattern is the same. |
| Single supervisor job instead of RQ dependency chains | Simpler error handling, sequential progress updates | One long-running job blocks a worker for entire pipeline duration (2-5 min); no parallelism between independent steps | Acceptable initially. Refactor to parallel steps (WAF + robots.txt simultaneously) when pipeline performance matters. |
| Storing progress in `job.meta` instead of Redis hash | No extra Redis key management | `job.meta` requires `job.save_meta()` which does a full Redis write of the entire meta dict. Polling progress requires fetching the full job object. Cannot be read from the SSE service without importing RQ. | Never for SSE integration. Use a dedicated Redis hash from the start -- it is barely more code and far more flexible. |
| Using `urllib.robotparser` instead of Protego | Zero dependencies, stdlib | No wildcard pattern support, buggy with malformed robots.txt, no crawl-delay support | Never. Protego is a small, well-maintained library that handles real-world robots.txt correctly. The stdlib parser will silently give wrong answers. |
| Skipping `extruct` error handling, letting it crash | Faster implementation | Any malformed JSON-LD, missing schema, or trailing semicolon crashes the entire pipeline for that URL | Never. Extruct extraction must always be wrapped in try/except with graceful degradation to partial results. |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| SSE + Inertia CSRF | SSE `EventSource` cannot send custom headers (no CSRF token). If the SSE endpoint is behind CSRF middleware, all connections fail with 403. | Exempt SSE views from CSRF using `@csrf_exempt` or use `CsrfViewMiddleware` exclusion. SSE is GET-only and read-only, so CSRF protection is not needed. |
| RQ + Django ORM | RQ worker runs in a separate process. If you pass Django model instances as job arguments, they become stale -- the worker has a different database connection and may see outdated data. | Pass IDs (integers) as job arguments, not model instances. Re-fetch from the database inside the job function. |
| RQ + Django settings | RQ worker process does not automatically load Django settings. Importing models or using ORM in job functions fails with `django.core.exceptions.ImproperlyConfigured`. | Use `django-rq` which handles Django setup, or call `django.setup()` in worker initialization. Configure via `RQ_QUEUES` in Django settings. |
| curl-cffi + Zyte fallback | Using different HTTP clients for primary vs. fallback means different cookie handling, redirect behavior, timeout semantics, and error types. Error handling code assumes one response format. | Define a `FetchResult` dataclass that both fetchers return. Normalize errors to a common exception type. Test the fallback path explicitly -- it will have different failure modes. |
| curl-cffi TLS impersonation + target site | Choosing wrong browser impersonation profile. Some CDNs/WAFs fingerprint specific browser versions and block outdated ones. Using `impersonate="chrome110"` when the site expects Chrome 120+ JA3 fingerprint. | Use recent browser versions: `impersonate="chrome"` (latest), not a specific version. Rotate impersonation profiles if you hit blocks. Check curl-cffi release notes for supported browser versions. |
| Redis + Django `runserver` | Django dev server is single-threaded. If an SSE view blocks waiting for Redis pub/sub, the entire dev server hangs. No other requests can be served. | In development, use polling or a separate process for SSE. Or use `runserver --nothreading=False` (Django 4.1+) to enable threading. Better: use uvicorn for dev when SSE routes exist. |
| extruct + Zyte-fetched HTML | Zyte returns base64-encoded HTTP response body, decoded as UTF-8. Some pages return Shift_JIS, ISO-8859-1, or other encodings. The current `b64decode(...).decode("utf-8")` will throw `UnicodeDecodeError` on non-UTF-8 pages. | Use `chardet` or `charset-normalizer` to detect encoding, or use Zyte's `browserHtml` option which always returns UTF-8. Wrap decode in try/except with fallback to `latin-1`. |
| SSE + nginx (production) | nginx's default `proxy_buffering on` buffers the entire response before forwarding to the client. SSE events do not reach the browser until the connection closes. | Add `X-Accel-Buffering: no` header on SSE responses, or set `proxy_buffering off` in the nginx location block for SSE routes. Also set `proxy_read_timeout` high enough for the analysis duration. |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Opening a new curl-cffi `Session` per request instead of reusing | Works fine for 1-10 requests, then connection establishment adds 200-500ms per fetch and TLS handshakes pile up | Create one `Session` per worker process (module-level or singleton). Reuse across requests. `Session` handles connection pooling internally. | > 50 concurrent analyses. Each new session = new TCP + TLS handshake. |
| SSE endpoint doing database queries to check progress | Each SSE poll iteration queries PostgreSQL for job status. Under load, this creates sustained query pressure on the database. | Store progress in Redis (fast, in-memory). SSE endpoint reads only from Redis, never from PostgreSQL. Database is written to only when pipeline steps complete. | > 20 concurrent SSE connections polling at 1-second intervals = 20 QPS sustained on PostgreSQL just for status checks. |
| Not setting `maxmemory` on Redis in Docker | Redis grows unbounded. Analysis progress keys, RQ job data, and failed job registries accumulate. Eventually Redis uses all available container memory and starts OOM-killing or swapping. | Set `maxmemory 256mb` (or appropriate limit) with `maxmemory-policy allkeys-lru`. Set TTL on all progress keys (e.g., 1 hour). Clean up completed analysis keys after the SSE stream closes. | After hundreds of analyses without cleanup, or if a bug causes keys to never expire. |
| Synchronous LLM calls in the RQ worker blocking on API latency | LLM publisher resolution takes 2-10 seconds per call. The worker is blocked during this time, unable to process other jobs. With 1-2 workers, this creates a bottleneck. | Use pydantic-ai's async support if running in an async context, or ensure enough RQ workers to handle concurrent LLM calls. Consider a dedicated queue for LLM tasks with its own worker pool. | > 5 concurrent analyses, each making 1-2 LLM calls. Workers spend most of their time waiting on API responses. |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| SSE endpoint returns analysis data without authentication check | Any user can watch any analysis progress by guessing the analysis ID. Could leak publisher intelligence data. | SSE endpoint must verify the requesting user owns the analysis. Use session authentication (cookies are sent with EventSource automatically). Generate analysis IDs as UUIDs, not sequential integers. |
| Passing user-supplied URLs directly to curl-cffi without validation | SSRF (Server-Side Request Forgery). User submits `http://169.254.169.254/latest/meta-data/` and the server fetches AWS metadata. Or `http://localhost:6379/` to probe internal Redis. | Validate URL scheme (only `http`/`https`), resolve hostname to IP and reject private/internal ranges (10.x, 172.16-31.x, 192.168.x, 127.x, 169.254.x, ::1). Use `ipaddress` module for range checking. |
| Storing raw LLM responses without sanitization | LLM might return unexpected content (hallucinated HTML, markdown injection, or XSS payloads) that gets rendered in the React frontend. | Treat all LLM output as untrusted. Use Pydantic models to validate structure. React's JSX auto-escapes by default, but avoid `dangerouslySetInnerHTML` with LLM output. Validate publisher names against a reasonable character set. |
| Redis connection string with password exposed in Docker logs | Docker compose `command: redis-server --requirepass mypassword` appears in `docker-compose.yml` and process listing. | Use environment variables for Redis password. Store in `.env` file (already gitignored). Use `REDIS_URL` connection string pattern. |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Progress bar shows percentage but no context | User sees "45%" but has no idea what is happening. Feels slow and opaque. | Show step names with status: "Checking robots.txt... done", "Fetching page... in progress", "Extracting metadata... waiting". Progress bar + step list. |
| SSE connection fails silently | User stares at spinner forever. No error message, no retry indication. | Implement client-side reconnection with exponential backoff (1s, 2s, 4s, max 30s). After 3 failures, show "Connection lost. Retrying..." message. After max retries, show error with manual retry button. |
| Analysis fails mid-pipeline, only shows "Error" | User has no idea what went wrong or whether partial results were saved. They do not know if retrying will help. | Show which step failed and why: "Page fetch failed: site returned 403 Forbidden. WAF detection and robots.txt results are still available." Partial results should be visible and saved. |
| Starting duplicate analyses for the same URL | User clicks "Analyze" twice, or submits the same URL from different tabs. Two pipelines run simultaneously, racing to create/update the same publisher. | Check for in-progress analyses for the same normalized URL before starting a new one. Show existing in-progress analysis if one exists. Use a Redis lock keyed by normalized URL. |

## "Looks Done But Isn't" Checklist

- [ ] **SSE streaming:** Works in dev with `runserver` but SSE events batch in production behind nginx -- verify `X-Accel-Buffering: no` header is set and nginx config has `proxy_buffering off` for SSE routes
- [ ] **RQ pipeline:** Happy path works but failure handling is untested -- verify that a failure at each individual step produces a visible error in the SSE stream and does not leave the pipeline stuck
- [ ] **robots.txt:** Parses clean robots.txt but not malformed ones -- verify with real-world robots.txt from sites like facebook.com (empty), bloomberg.com (wildcard patterns), and a site returning 403 for robots.txt
- [ ] **URL normalization:** Works for common URLs but not edge cases -- verify with IDN domains, URLs with port numbers, URLs with authentication credentials, URLs with fragments, and uppercase hostnames
- [ ] **Publisher resolution:** LLM returns a name for common domains but hallucinates for obscure ones -- verify with subdomains (blog.example.com vs example.com), CDN domains (d1234.cloudfront.net), and URL shorteners (bit.ly/abc)
- [ ] **extruct extraction:** Works on pages with clean schema.org markup but crashes on malformed JSON-LD -- verify with pages that have: no structured data, malformed JSON in script tags, multiple conflicting schemas, and HTML entities in JSON-LD
- [ ] **SSE cleanup:** Works when user stays on the page but leaks connections on navigation -- verify by starting an analysis, navigating away with Inertia, and checking server-side connection count
- [ ] **Redis progress keys:** Written during analysis but never cleaned up -- verify TTL is set on all keys and completed analysis keys are deleted after the SSE stream closes
- [ ] **curl-cffi fallback to Zyte:** Primary fetcher works but fallback path is untested -- verify by making curl-cffi fail (block a domain) and confirming Zyte fallback activates and returns the same `FetchResult` format

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Duplicate publishers from poor normalization | MEDIUM | Write a migration script that normalizes all publisher URLs, merges duplicates (keeping the one with most data), and re-points WAFReport/TermsDiscovery foreign keys. Run once, add unique constraint. |
| Zombie SSE connections exhausting workers | LOW | Restart gunicorn/uvicorn workers. Add connection timeout on server side (close SSE after max duration). Fix cleanup code in React component. |
| Orphaned RQ jobs in DeferredJobRegistry | LOW | Use `rq` CLI: `rq requeue --all -q default`. Add monitoring for deferred job count. Fix dependency chain to use `allow_failure=True`. |
| curl-cffi segfault crashing workers | HIGH | Audit all curl-cffi usage for `stream=True`. Replace with non-streaming calls. Add process-level monitoring to auto-restart crashed workers (supervisord or Docker restart policy). |
| Redis OOM from progress key accumulation | LOW | Flush expired keys with `redis-cli --scan --pattern "analysis:*"`. Add TTL to all keys. Set `maxmemory-policy allkeys-lru`. |
| LLM hallucinating publisher names | LOW | Add manual override UI for publisher names. Store LLM confidence score. Flag low-confidence results for human review. Compare against existing publisher database before creating new records. |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Inertia middleware interfering with SSE (Critical #1) | Infrastructure (SSE endpoint setup) | Single SSE event streams to browser immediately, not batched |
| WSGI worker exhaustion (Critical #2) | Infrastructure (server architecture) | 5 concurrent SSE connections do not block normal page loads |
| RQ dependent job abandonment (Critical #3) | Task pipeline (job chain design) | Intentionally fail each pipeline step; verify error appears in SSE stream within 5 seconds |
| curl-cffi streaming crash (Critical #4) | Page fetching (fetcher implementation) | Fetch 10 slow/chunked-response URLs; zero worker crashes |
| URL normalization duplicates (Critical #5) | URL normalization (first pipeline step) | Submit `http://WWW.Example.Com:80/` and `https://example.com` -- same publisher record created |
| SSE cleanup on unmount (Critical #6) | SSE frontend (React component) | Start analysis, navigate away via Inertia, verify server connection count drops to 0 |
| robots.txt malformed parsing | Pipeline step (robots.txt check) | Parse robots.txt from 20 real-world sites including known edge cases (empty, 403, wildcards) |
| extruct crash on malformed JSON-LD | Pipeline step (metadata extraction) | Run extruct on 20 real-world pages; zero unhandled exceptions |
| LLM publisher hallucination | Pipeline step (publisher resolution) | Test with 10 ambiguous domains (CDN, subdomains, URL shorteners); all return "unknown" or correct name, never fabricated names |
| Redis memory unbounded growth | Infrastructure (Redis setup) | Run 100 analyses; verify Redis memory stays under `maxmemory` limit; all progress keys have TTL |
| SSE CORS / nginx buffering | Infrastructure (deployment config) | SSE works end-to-end through nginx reverse proxy in staging |

## Sources

- [Django ticket #36655: GZipMiddleware buffers streaming responses](https://code.djangoproject.com/ticket/36655) -- HIGH confidence
- [Django ticket #36656: GZipMiddleware drops async streaming content](https://code.djangoproject.com/ticket/36656) -- HIGH confidence
- [gunicorn worker timeout with streaming (issue #1186)](https://github.com/benoitc/gunicorn/issues/1186) -- HIGH confidence
- [Django StreamingHttpResponse blog (Anze Pecar)](https://blog.pecar.me/django-streaming-responses) -- MEDIUM confidence
- [RQ Dependency class and allow_failure (issue #2006)](https://github.com/rq/rq/issues/2006) -- HIGH confidence
- [RQ dependent job failure handling (issue #1224)](https://github.com/rq/rq/issues/1224) -- HIGH confidence
- [RQ job chaining (issue #1503)](https://github.com/rq/rq/issues/1503) -- HIGH confidence
- [curl-cffi crash on session close during streaming (issue #675)](https://github.com/lexiforest/curl_cffi/issues/675) -- HIGH confidence
- [curl-cffi timeout issues in stream mode (issue #215)](https://github.com/lexiforest/curl_cffi/issues/215) -- HIGH confidence
- [curl-cffi documentation: quick start](https://curl-cffi.readthedocs.io/en/latest/quick_start.html) -- HIGH confidence
- [extruct: Accept JSON parsing errors in JSON-LD (issue #45)](https://github.com/scrapinghub/extruct/issues/45) -- HIGH confidence
- [extruct: Handle badly formatted JSON-LD (issue #87)](https://github.com/scrapinghub/extruct/issues/87) -- HIGH confidence
- [Protego robots.txt parser (GitHub)](https://github.com/scrapy/protego) -- HIGH confidence
- [Python robotparser crawl-delay bug (cpython issue #60303)](https://github.com/python/cpython/issues/60303) -- HIGH confidence
- [url-normalize library (GitHub)](https://github.com/niksite/url-normalize) -- MEDIUM confidence
- [React SSE implementation guide (OneUpTime)](https://oneuptime.com/blog/post/2026-01-15-server-sent-events-sse-react/view) -- MEDIUM confidence
- [SSE practical guide (Tiger Abrodi)](https://tigerabrodi.blog/server-sent-events-a-practical-guide-for-the-real-world) -- MEDIUM confidence
- [MDN: Using server-sent events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events) -- HIGH confidence
- [Redis memory limits in Docker Compose (Peter Kellner)](https://peterkellner.net/2023/09/24/Managing-Redis-Memory-Limits-with-Docker-Compose/) -- MEDIUM confidence
- [Browser SSE connection limit (6 per domain over HTTP/1.1)](https://blog.pranshu-raj.me/posts/exploring-sse/) -- MEDIUM confidence
- [Inertia middleware source code (inertia-django)](https://github.com/inertiajs/inertia-django) -- HIGH confidence (verified against installed package)

---
*Pitfalls research for: URL analysis workflow addition to Django-Inertia app*
*Researched: 2026-02-13*
