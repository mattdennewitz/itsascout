# Phase 17: Pipeline Integration - Research

**Researched:** 2026-02-18
**Domain:** Django pipeline orchestration, SSE progress events, TTL skip-path correctness
**Confidence:** HIGH

## Summary

Phase 17 is a pure integration/wiring phase. All new step functions (CC, sitemap analysis, frequency, Google News) already exist and are already wired into the supervisor's fresh-execution path. The remaining work is strictly about three gaps that were intentionally deferred from Phases 14-16:

1. **TTL skip path** -- The `should_skip_publisher_steps()` branch in `supervisor.py` copies results from prior completed jobs but does NOT yet include the four new result fields (`cc_result`, `sitemap_analysis_result`, `frequency_result`, `news_signals_result`). The `values()` query, field-copy block, `save(update_fields=)` call, and skip events all need the new fields added.

2. **SSE progress stream** -- The frontend `PIPELINE_STEPS` array in `Show.tsx` is missing entries for `sitemap_analysis`, `frequency`, and `google_news`. Without these, the step cards do not appear during live runs, and the `stepDataSummary()` function has no branch for these step keys.

3. **View fallback** -- The `job_show` view in `views.py` has a `result_fields` list for null-fallback from prior jobs that does not include the new fields. The props dict also does not pass the new fields to the frontend.

**Primary recommendation:** This phase requires no new libraries, no new models, and no new step functions. It is purely about adding field names to existing enumerations in `supervisor.py`, `views.py`, `Show.tsx`, and `serializers.py`, then verifying the end-to-end flow with tests.

## Standard Stack

### Core

No new libraries needed. This phase modifies existing files only.

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django | existing | Models, views, ORM queries | Already in use |
| Redis pub/sub | existing | SSE event publishing | Already in use |
| React + Inertia | existing | Frontend step cards | Already in use |

### Supporting

N/A -- no new dependencies.

### Alternatives Considered

N/A -- no choices to make. This is mechanical integration.

## Architecture Patterns

### Pattern 1: Result Field Enumeration

The codebase uses an explicit-enumeration pattern for result fields. Every time a new result field is added to `ResolutionJob`, it must be added to **four places**:

1. **`supervisor.py` TTL skip path** -- `values()` query (line ~106), field copy block (lines ~113-121), `save(update_fields=)` (line ~134), and skip events (lines ~140-165)
2. **`views.py` job_show** -- `result_fields` list (line ~186-189) and props dict (lines ~219-228)
3. **`Show.tsx` PIPELINE_STEPS** -- array of step definitions (lines 79-93)
4. **`Show.tsx` stepDataSummary** -- function branches for summary display (lines 122-228)

**Confidence: HIGH** -- verified by reading all four files directly.

### Pattern 2: SSE Event Publishing

Each pipeline step follows the same event pattern:
```python
publish_step_event(job_id, "step_name", "started")
result = run_step_function(...)
resolution_job.result_field = result
resolution_job.save(update_fields=["result_field"])
publish_step_event(job_id, "step_name", "completed", result)
```

For skipped steps:
```python
publish_step_event(job_id, "step_name", "skipped", {"reason": "fresh"})
```

**Confidence: HIGH** -- this pattern is already used consistently across all existing steps.

### Pattern 3: TTL Skip Path Result Copying

The fresh-publisher skip path:
1. Queries the most recent completed job for this publisher using `.values()` with explicit field names
2. Copies each field individually from the prior job dict
3. Saves with explicit `update_fields`
4. Publishes "skipped" events for each step

The CC step has a special case: if `cc_result` is null on the prior job (predating CC step), it runs the CC step even in the skip path. The new fields (`sitemap_analysis_result`, `frequency_result`, `news_signals_result`) should follow the same pattern -- if the prior job predates these steps, run them fresh even during a skip.

**Confidence: HIGH** -- the CC special-case pattern at supervisor.py lines 152-164 is the exact model.

### Pattern 4: Google News Step Position (Post-Article)

The Google News step runs AFTER article-level steps and OUTSIDE the publisher skip guard. It uses `resolution_job.sitemap_analysis_result`, `resolution_job.article_result`, and `resolution_job.metadata_result` as inputs. This means:
- When publisher steps are skipped, Google News still runs (using copied results)
- When article steps are skipped, Google News still runs (but `article_result` will be null on the resolution_job unless copied from a prior job)

**Important:** Currently, when article steps are skipped, `article_result` is NOT copied from a prior job. The Google News step handles null inputs gracefully, but for full correctness, `article_result` should also be considered for the fallback path in `views.py`.

**Confidence: HIGH** -- verified in supervisor.py lines 406-428.

### Anti-Patterns to Avoid

- **Partial field enumeration:** Forgetting to add a field to one of the four enumeration sites creates subtle bugs where cached runs show "Not checked" for new sections.
- **Skipping the "predates step" special case:** New steps added in Phases 14-16 may not have results on older completed jobs. The skip path must handle this like the CC step does.

## Exact Gaps to Fill

### Gap 1: supervisor.py TTL Skip Path

**File:** `/Users/matt/src/itsascout/scrapegrape/publishers/pipeline/supervisor.py`

The `values()` call at line ~106 needs three new fields:
```python
.values(
    "waf_result", "tos_result", "robots_result",
    "sitemap_result", "rss_result", "rsl_result",
    "ai_bot_result", "metadata_result", "cc_result",
    "sitemap_analysis_result", "frequency_result", "news_signals_result",  # NEW
)
```

Field copy block (lines ~113-121) needs:
```python
resolution_job.sitemap_analysis_result = prior["sitemap_analysis_result"]
resolution_job.frequency_result = prior["frequency_result"]
resolution_job.news_signals_result = prior["news_signals_result"]
```

Save call (line ~134) needs the three new fields in `update_fields`.

Skip events needed (after line ~153):
```python
publish_step_event(job_id, "sitemap_analysis", "skipped", {"reason": "fresh"})
publish_step_event(job_id, "frequency", "skipped", {"reason": "fresh"})
```

The Google News step already runs unconditionally after the skip path (lines 406-428), so it does not need a skip event -- it will always execute.

**Special case:** Like CC, if `sitemap_analysis_result` or `frequency_result` is null on the prior job (predating these steps), they should run fresh. This requires the same pattern as CC (lines 152-164). For `news_signals_result`, since Google News already always runs, no special case is needed.

**Publisher flat field updates for skipped path:** When sitemap_analysis/frequency results are copied from prior, the publisher flat fields (`has_news_sitemap`, `update_frequency`, `update_frequency_hours`, `update_frequency_confidence`) are already set from the prior run and don't need re-setting. However, `google_news_readiness` gets set by the always-running Google News step.

**Confidence: HIGH**

### Gap 2: views.py job_show Fallback

**File:** `/Users/matt/src/itsascout/scrapegrape/publishers/views.py`

The `result_fields` list at line ~186 needs:
```python
result_fields = [
    "waf_result", "tos_result", "robots_result", "sitemap_result",
    "rss_result", "rsl_result", "ai_bot_result", "metadata_result",
    "cc_result",
    "sitemap_analysis_result", "frequency_result", "news_signals_result",  # NEW
]
```

The props dict at line ~207 needs:
```python
"sitemap_analysis_result": job.sitemap_analysis_result,
"frequency_result": job.frequency_result,
"news_signals_result": job.news_signals_result,
```

**Confidence: HIGH**

### Gap 3: Show.tsx PIPELINE_STEPS

**File:** `/Users/matt/src/itsascout/scrapegrape/frontend/src/Pages/Jobs/Show.tsx`

The `PIPELINE_STEPS` array (line 79) needs three new entries. Based on execution order in the supervisor:

```typescript
const PIPELINE_STEPS = [
    // ... existing 10 publisher-level steps ...
    { key: 'cc', label: 'Common Crawl Presence', icon: '10' },
    { key: 'sitemap_analysis', label: 'Sitemap Analysis', icon: '11' },  // NEW
    { key: 'frequency', label: 'Update Frequency', icon: '12' },          // NEW
    // ... article-level steps (renumbered) ...
    { key: 'article_extraction', label: 'Article Metadata', icon: '13' },
    { key: 'paywall_detection', label: 'Paywall Detection', icon: '14' },
    { key: 'metadata_profile', label: 'Metadata Profile', icon: '15' },
    { key: 'google_news', label: 'Google News Readiness', icon: '16' },  // NEW
] as const
```

The `stepDataSummary()` function needs branches for the three new step keys:
```typescript
if (step === 'sitemap_analysis') {
    if (data.has_news_sitemap) return `News sitemap detected`
    return 'No news sitemap found'
}
if (step === 'frequency') {
    if (data.frequency_label) return `${data.frequency_label} (${data.confidence} confidence)`
    return 'Could not estimate frequency'
}
if (step === 'google_news') {
    if (data.readiness) return `Readiness: ${data.readiness} (${data.signal_count}/3 signals)`
    return 'Could not assess readiness'
}
```

The `JobProps` interface needs:
```typescript
sitemap_analysis_result: Record<string, unknown> | null
frequency_result: Record<string, unknown> | null
news_signals_result: Record<string, unknown> | null
```

The `initialStatuses` useMemo needs to build completed events from these new result fields for page-reload scenarios.

The step card divider ("Article Analysis" heading) currently splits at index 10. With new steps before article steps, this index needs adjusting.

**Confidence: HIGH**

### Gap 4: serializers.py (Optional but Documented)

**File:** `/Users/matt/src/itsascout/scrapegrape/publishers/serializers.py`

The `PublisherListSerializer` fields tuple does not include the new Publisher flat fields. These should be added for completeness:
```python
fields = (
    ...,
    "has_paywall",
    "cc_in_index", "cc_page_count", "cc_last_crawl",
    "has_news_sitemap", "google_news_readiness",
    "update_frequency", "update_frequency_hours", "update_frequency_confidence",
)
```

**Confidence: HIGH** -- these fields exist on the model but are not serialized.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Event name mapping | Custom event name registry | Follow existing `publish_step_event` pattern with literal strings | The step names are already used as Redis channel event keys -- consistency matters more than abstraction |
| Result field registry | DRY field enumeration system | Explicit field lists in each location | The four locations have different structures (Python list, Django values(), JS array, JS switch). A registry would be over-engineering for ~5 fields |

**Key insight:** The temptation is to DRY up the field enumerations. Resist this. The existing codebase uses explicit lists, and each location has its own shape. A registry adds complexity without reducing bugs.

## Common Pitfalls

### Pitfall 1: Forgetting a Field in One Enumeration Site
**What goes wrong:** New step shows "Not checked" on cached runs, or step card doesn't appear during live runs.
**Why it happens:** Four separate locations must be updated in sync.
**How to avoid:** Use the exact gap list above as a checklist. Test both fresh and cached pipeline runs.
**Warning signs:** Report card sections show "Not checked" for recently analyzed publishers.

### Pitfall 2: Step Card Divider Index Shift
**What goes wrong:** "Article Analysis" heading appears in the wrong place, or step cards are misaligned.
**Why it happens:** The `PIPELINE_STEPS.slice(0, 10)` / `PIPELINE_STEPS.slice(10)` split assumes exactly 10 publisher-level steps.
**How to avoid:** Update the slice indices when adding new publisher-level steps. Count: the new steps bring publisher-level to 12 (adding sitemap_analysis and frequency), article-level starts at index 12.
**Warning signs:** Visual misalignment in the step card UI.

### Pitfall 3: Google News Step Running with Null Inputs After Full Skip
**What goes wrong:** When both publisher AND article steps are skipped, Google News runs with null `sitemap_analysis_result` and null `article_result` on the resolution job (because these aren't copied in the skip path yet).
**Why it happens:** Google News is outside the skip guard, but its inputs are inside.
**How to avoid:** The TTL skip path must copy `sitemap_analysis_result` and `news_signals_result` to the job. The Google News step already handles null inputs gracefully, but copying ensures consistency.
**Warning signs:** Google News readiness shows "none" for cached runs of publishers that previously had signals.

### Pitfall 4: "Predates Step" Edge Case for Sitemap Analysis and Frequency
**What goes wrong:** Prior completed job was created before Phases 15-16, so `sitemap_analysis_result` and `frequency_result` are null. Skip path copies null, and these steps never run.
**Why it happens:** The basic skip path copies whatever the prior job has, even null.
**How to avoid:** Follow the CC step pattern: check if the copied result is null, and if so, run the step fresh even during the skip path.
**Warning signs:** New fields are perpetually null for publishers that were first analyzed before these steps existed.

### Pitfall 5: RQ Job Timeout
**What goes wrong:** Full pipeline with all new steps exceeds the 600-second RQ timeout.
**Why it happens:** Adding more HTTP-dependent steps increases total wall-clock time.
**How to avoid:** The new steps (sitemap analysis, frequency, Google News) are lightweight -- sitemap analysis reuses already-fetched data, frequency makes at most one RSS request, and Google News is pure aggregation. The timeout is unlikely to be hit, but should be verified end-to-end.
**Warning signs:** Jobs fail with `JobTimeoutException`.

## Code Examples

### TTL Skip Path Extension Pattern (from existing CC special case)

```python
# Existing pattern at supervisor.py lines 152-164:
if resolution_job.cc_result:
    publish_step_event(job_id, "cc", "skipped", {"reason": "fresh"})
else:
    # Prior job predates CC step -- run it now
    publish_step_event(job_id, "cc", "started")
    cc_result = run_cc_step(publisher)
    resolution_job.cc_result = cc_result
    resolution_job.save(update_fields=["cc_result"])
    publish_step_event(job_id, "cc", "completed", cc_result)
    # Update publisher flat fields...
```

Apply this same pattern for `sitemap_analysis_result` and `frequency_result`.

### Frontend Step Card Pattern (from existing steps)

```typescript
// Existing pattern in PIPELINE_STEPS:
{ key: 'cc', label: 'Common Crawl Presence', icon: '10' },

// Existing pattern in stepDataSummary:
if (step === 'cc') {
    if (data.available === false) return `Data unavailable: ${data.error ?? 'API error'}`
    if (data.in_index) { /* ... */ }
    return null
}
```

### initialStatuses Pattern for New Fields

```typescript
// Existing pattern for cc_result:
if (job.cc_result) {
    statuses['cc'] = { step: 'cc', status: 'completed', data: job.cc_result }
}

// Same pattern for new fields:
if (job.sitemap_analysis_result) {
    statuses['sitemap_analysis'] = { step: 'sitemap_analysis', status: 'completed', data: job.sitemap_analysis_result }
}
```

## State of the Art

N/A -- this phase involves no new technology choices. It is pure integration of existing patterns.

## Open Questions

1. **Should `news_signals_result` be skipped or always re-run for cached publishers?**
   - What we know: Google News step is pure aggregation (no HTTP), runs in <1ms. Currently always runs even in skip path.
   - What's unclear: Should it skip and copy prior result, or always re-run?
   - Recommendation: Always re-run. It's cheap and ensures fresh aggregation from whatever data is available. The skip event should NOT be emitted for google_news. This matches current behavior.

2. **Should the "predates step" special case apply to all three new fields or just sitemap_analysis and frequency?**
   - What we know: CC already has this pattern. Google News always runs.
   - What's unclear: Whether to run sitemap_analysis and frequency fresh during skip if prior job lacks them.
   - Recommendation: YES, apply the CC pattern. Sitemap analysis requires HTTP fetches (accessing sitemaps), frequency requires RSS fetch -- both are worth running to populate the data. Without this, publishers first analyzed before Phase 15-16 would permanently lack these fields.

3. **Step card index split for Article Analysis heading**
   - What we know: Currently splits at index 10 (10 publisher steps, then article steps)
   - What's unclear: Where exactly to put sitemap_analysis and frequency in the visual grouping
   - Recommendation: These are publisher-level steps, so they go before the article divider. The split becomes index 12 (12 publisher steps including the 2 new ones). Google News goes after article steps (last step).

## Sources

### Primary (HIGH confidence)
- Direct code reading: `supervisor.py` (full file, 441 lines)
- Direct code reading: `steps.py` (full file, 1467 lines)
- Direct code reading: `events.py` (full file, 40 lines)
- Direct code reading: `views.py` (lines 38-310)
- Direct code reading: `Show.tsx` (full file, 1018 lines)
- Direct code reading: `models.py` (lines 1-160)
- Direct code reading: `serializers.py` (full file, 17 lines)
- Direct code reading: `test_pipeline.py` (TTL skip test, lines 559-675)

### Secondary (MEDIUM confidence)
- Phase 13 research: `.planning/phases/13-data-foundation/13-RESEARCH.md` (downstream impact analysis)
- Phase 15-02 summary: `.planning/phases/15-content-signals/15-02-SUMMARY.md` (TTL deferred to Phase 17)
- Phase 16-02 summary: `.planning/phases/16-google-news-readiness/16-02-SUMMARY.md` (Google News TTL deferred)
- Requirements: `.planning/REQUIREMENTS.md` (PIPE-01, PIPE-03, PIPE-04)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new libraries, purely existing code modification
- Architecture: HIGH -- all patterns verified by reading current source
- Pitfalls: HIGH -- gaps identified by comparing field lists across files

**Research date:** 2026-02-18
**Valid until:** 2026-03-18 (stable -- no external dependencies changing)
