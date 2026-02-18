# Phase 14 Research: Common Crawl Presence

**Researched:** 2026-02-17
**Domain:** Common Crawl CDX Index API, pipeline step integration, error handling
**Confidence:** HIGH

Phase 14 adds a single new pipeline step that queries the Common Crawl CDX Index API for domain presence. The codebase has a well-established pattern for adding pipeline steps: create a step function in `steps.py`, wire it into `supervisor.py` with SSE events, save results to `ResolutionJob.cc_result` (JSONField, already exists from Phase 13), and update Publisher flat fields (`cc_in_index`, `cc_page_count`, `cc_last_crawl` — all already exist).

**Primary recommendation:** Add `run_cc_step()` to `steps.py` using Python's `httpx` (already a project dependency via pydantic-ai) to query the CC CDX API. Wire into supervisor between article-level steps and the freshness TTL skip path. No new dependencies needed.

## Common Crawl CDX Index API

### Endpoint Format
```
https://index.commoncrawl.org/CC-MAIN-{YYYY}-{WW}-index?url=*.{domain}&output=json&limit=N
```

### Key Details
- **Latest collection:** CC-MAIN-2026-04 (January 2026)
- **Wildcard search:** `*.example.com` returns all captures for example.com and subdomains (matchType=domain)
- **Response format:** Newline-delimited JSON when `output=json`
- **Pagination:** `showNumPages=true` returns `{"pages": N, "pageSize": 5, "blocks": N}`
- **Fields available:** `url`, `timestamp`, `status`, `mime`, `filename`, `offset`, `length`
- **Field selection:** `fl=url,timestamp,status` to reduce response size
- **Rate limiting:** No explicit limits documented, but bulk downloads discouraged

### Query Strategy for Presence Check
1. Use `showNumPages=true` first to get page count — this tells us if domain is present and roughly how many pages
2. If pages > 0, fetch first page with `limit=1&fl=url,timestamp` to get the latest crawl timestamp
3. Estimate page count from `blocks` field (each block ≈ 3000 records)

**Why two requests:** `showNumPages` is fast (metadata only, no record scanning) and gives us the page count. One record fetch gets the timestamp. Total: 2 lightweight API calls.

**Alternative considered:** Single request with `limit=5` — but this scans records and is slower for large domains. The two-request approach is more efficient and gives better data.

### Error Handling
- CC API returns HTTP 404 for unknown collections
- HTTP 503 during maintenance
- Timeout: API can be slow for large domains (>30s)
- No results: empty response (not an error)
- **Recommendation:** 15-second timeout per request, catch all exceptions, return `{"available": False, "error": "..."}` — never crash the pipeline

## Codebase Integration Points

### Step Function Pattern (from `steps.py`)
Every step function:
1. Takes `publisher: Publisher` (and optional context)
2. Returns a structured `dict` of results
3. Catches all exceptions internally → returns error dict
4. Is called from `supervisor.py` which handles SSE events and saves to ResolutionJob

### Supervisor Pattern (from `supervisor.py`)
For each step:
```python
publish_step_event(job_id, "step_name", "started")
result = run_step(publisher, ...)
resolution_job.result_field = result
resolution_job.save(update_fields=["result_field"])
publish_step_event(job_id, "step_name", "completed", result)
publisher.flat_field = result.get("key")
publisher.save(update_fields=["flat_field"])
```

### TTL Skip Path
The freshness skip path in supervisor copies prior results:
- Must add `"cc_result"` to the `.values()` query and copy it
- Must add `publish_step_event(job_id, "cc", "skipped", {"reason": "fresh"})` to the skip block

### Existing Model Fields (from Phase 13)
**Publisher flat fields:**
- `cc_in_index` — BooleanField(null=True)
- `cc_page_count` — IntegerField(null=True, blank=True)
- `cc_last_crawl` — CharField(max_length=20, blank=True, default="")

**ResolutionJob:**
- `cc_result` — JSONField(null=True, blank=True)

### Result Dict Shape
```python
{
    "available": True,        # or False
    "in_index": True,         # domain found in CC
    "page_count": 45000,      # estimated from blocks * 3000
    "latest_crawl": "2026-01",  # YYYY-MM from latest timestamp
    "collection": "CC-MAIN-2026-04",
    "error": None,            # or error string
}
```

## Where to Place CC Step in Pipeline

The CC step should run as a **publisher-level step** (not article-level) because it checks domain presence, not article-specific data. It should be placed after the existing publisher steps (after RSL, before publisher_details) since it's an independent HTTP call that doesn't depend on any other step's output.

**Placement in supervisor:** After Step 7 (RSL) and before Step 8 (Publisher details). The CC step makes its own HTTP call (not to the publisher site) so it doesn't need homepage_html or any other step's output.

## Testing Strategy

- Mock `httpx.get` to test CC step function
- Test: domain found → returns page count and latest crawl
- Test: domain not found → returns `in_index: False`
- Test: API timeout → returns error dict, no crash
- Test: malformed response → returns error dict
- Test: supervisor integration with CC step (existing monkeypatch pattern)

## No New Dependencies

- `httpx` is already available (transitive dependency of pydantic-ai)
- No new packages needed
