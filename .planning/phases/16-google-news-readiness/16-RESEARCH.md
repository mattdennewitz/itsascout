# Phase 16: Google News Readiness - Research

**Researched:** 2026-02-18
**Domain:** Aggregation of existing pipeline data into Google News readiness signals (no new HTTP requests, no new dependencies)
**Confidence:** HIGH

## Summary

Phase 16 creates a single aggregation step that combines three signals already collected by earlier pipeline steps into a Google News readiness level. The three signals are: (1) news sitemap presence from Phase 15's `sitemap_analysis_result`, (2) NewsArticle schema type from the article extraction step's JSON-LD data, and (3) NewsMediaOrganization schema type from the publisher details step's organization type. The step produces a readiness level of strong / moderate / minimal / none -- never a binary "in Google News / not in Google News" assessment.

This phase requires no new HTTP requests because all input data is already available on the ResolutionJob by the time the aggregation step runs. The sitemap analysis step (Phase 15) detects `xmlns:news` and stores `has_news_sitemap` in `sitemap_analysis_result`. The publisher details step stores the organization `type` field in `metadata_result["organization"]["type"]`, which will be `"NewsMediaOrganization"` for news publishers. The article extraction step extracts JSON-LD data but currently does NOT preserve the `@type` field in `jsonld_fields` -- this is a gap that Phase 16 must address.

No new Python dependencies are needed. The step is pure Python logic: read existing result dicts, check for signal presence, compute readiness level, save to `news_signals_result` JSONField and `google_news_readiness` flat field (both already created by Phase 13's migration 0008).

**Primary recommendation:** Create `run_google_news_step()` in `steps.py` that takes the three existing result dicts (sitemap_analysis_result, article_result, metadata_result) and returns a signals dict with readiness level. Wire it into the supervisor after article-level steps complete (it needs article extraction data). Fix the article extraction step to include `@type` in `jsonld_fields` so NewsArticle detection works without re-parsing HTML.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib | 3.12 | Pure aggregation logic -- no external dependencies | The step is a pure function that reads dicts and returns a dict |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| No new dependencies | - | - | This step is pure aggregation of already-extracted data |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pure aggregation step | LLM-based assessment | Unnecessary complexity and cost for a deterministic signal aggregation; readiness levels are well-defined |
| Modifying article extraction to include @type | Re-running extruct in the news step | Would violate the "no new HTTP requests" constraint and add redundant parsing; better to fix extraction once |

**Installation:**
```bash
# No new packages needed
```

## Architecture Patterns

### Data Flow: Three Input Signals

```
Existing pipeline data:

  sitemap_analysis_result -----> has_news_sitemap (bool)
  (from Phase 15 step)                     |
                                           v
  article_result -----------> @type includes "NewsArticle" (bool)
  (from Phase 10 step)                    |
                                          v
  metadata_result ----------> org type == "NewsMediaOrganization" (bool)
  (from Phase 9 step)                    |
                                         v
                              run_google_news_step()
                                         |
                                         v
                              news_signals_result (JSONField)
                              + google_news_readiness (CharField)
```

### Signal Source Details

**Signal 1: News sitemap presence**
- Source: `sitemap_analysis_result["has_news_sitemap"]` (bool)
- Already available: YES -- populated by `run_sitemap_analysis_step()` in Phase 15
- Location in pipeline: set on ResolutionJob after sitemap analysis step completes

**Signal 2: NewsArticle schema type**
- Source: `article_result["jsonld_fields"]` needs to include `@type`
- Currently available: PARTIALLY -- article extraction stores JSON-LD fields but strips `@type`
- Gap: `_extract_jsonld_article_fields()` iterates KEY_FIELDS but `@type` is not in KEY_FIELDS
- Fix needed: The extraction function already checks `_normalize_types(node)` to find article nodes. It should store the matched type in the returned fields dict.

**Signal 3: NewsMediaOrganization schema type**
- Source: `metadata_result["organization"]["type"]`
- Already available: YES -- `_extract_organization()` at line 826 stores `_normalize_types(org)[0]`
- Check: `metadata_result.get("organization", {}).get("type") == "NewsMediaOrganization"`

### Pattern 1: Aggregation Step Function

**What:** A step that takes existing result dicts and produces a readiness assessment
**When to use:** When combining multiple signals into a summary metric
**Example:**
```python
# Following the established step function pattern
def run_google_news_step(
    sitemap_analysis_result: dict | None,
    article_result: dict | None,
    metadata_result: dict | None,
) -> dict:
    """Aggregate Google News readiness signals from existing pipeline data.

    No HTTP requests -- pure aggregation of already-collected signals.
    """
    signals = {}

    # Signal 1: News sitemap
    has_news_sitemap = (sitemap_analysis_result or {}).get("has_news_sitemap", False)
    signals["has_news_sitemap"] = has_news_sitemap

    # Signal 2: NewsArticle schema type on article
    jsonld_fields = (article_result or {}).get("jsonld_fields") or {}
    article_type = jsonld_fields.get("@type", "")
    # Check if type contains "NewsArticle" (including subtypes)
    has_news_article = "NewsArticle" in article_type if article_type else False
    signals["has_news_article_schema"] = has_news_article

    # Signal 3: NewsMediaOrganization schema on publisher
    org = (metadata_result or {}).get("organization") or {}
    org_type = org.get("type", "")
    has_news_org = org_type == "NewsMediaOrganization"
    signals["has_news_media_org"] = has_news_org

    # Compute readiness level
    signal_count = sum([has_news_sitemap, has_news_article, has_news_org])

    if signal_count >= 3:
        readiness = "strong"
    elif signal_count == 2:
        readiness = "moderate"
    elif signal_count == 1:
        readiness = "minimal"
    else:
        readiness = "none"

    return {
        "readiness": readiness,
        "signals": signals,
        "signal_count": signal_count,
        "error": None,
    }
```

### Pattern 2: Fixing Article Extraction to Preserve @type

**What:** Add `@type` to the fields stored by `_extract_jsonld_article_fields()`
**Why:** Without this, the Google News step cannot detect whether an article uses NewsArticle schema
**Example:**
```python
# In _extract_jsonld_article_fields(), after finding a matching article node:
def _extract_jsonld_article_fields(jsonld_items: list) -> dict | None:
    nodes = _flatten_jsonld_nodes(jsonld_items)
    for node in nodes:
        types = _normalize_types(node)
        if any(t.split("/")[-1] in ARTICLE_TYPES for t in types):
            fields: dict = {}
            # Preserve the @type for downstream consumers (e.g., Google News step)
            fields["@type"] = types[0].split("/")[-1] if types else None
            for field in KEY_FIELDS:
                # ... existing logic ...
```

### Pattern 3: Step Placement in Supervisor

**What:** The Google News step runs after article extraction (needs article @type data)
**Execution order:**
```
Existing pipeline steps (supervisor.py):
  Publisher-level steps:
    1. WAF check
    2. ToS discovery/evaluation
    3. robots.txt + AI bot blocking
    4. Sitemap discovery
    5. RSS discovery + RSL
    6. Common Crawl presence
    7. Sitemap analysis         <-- produces has_news_sitemap
    8. Frequency estimation
    9. Publisher details         <-- produces NewsMediaOrganization signal

  Article-level steps:
    10. Article extraction       <-- produces NewsArticle @type signal
    11. Paywall detection
    12. Metadata profile

  Phase 16 adds (after metadata profile, before pipeline completion):
    13. Google News readiness    <-- aggregates all three signals
```

**Why after article steps:** The Google News step needs the article extraction result to check for NewsArticle schema. It also needs metadata_result (publisher details) and sitemap_analysis_result, which are available from earlier publisher-level steps. So it must run last, after both publisher and article steps complete.

### Pattern 4: Supervisor Wiring (established pattern)

```python
# In supervisor.py, after metadata_profile step and before "Mark job complete":
# Step: Google News readiness aggregation
publish_step_event(job_id, "google_news", "started")
news_result = run_google_news_step(
    sitemap_analysis_result=resolution_job.sitemap_analysis_result,
    article_result=resolution_job.article_result,
    metadata_result=resolution_job.metadata_result,
)
resolution_job.news_signals_result = news_result
resolution_job.save(update_fields=["news_signals_result"])
publish_step_event(job_id, "google_news", "completed", news_result)

# Update publisher flat field
publisher.google_news_readiness = news_result.get("readiness", "")
publisher.save(update_fields=["google_news_readiness"])
```

### Anti-Patterns to Avoid
- **Making HTTP requests in the aggregation step:** All data is already available. No fetching.
- **Binary "in/not in" classification:** The requirement explicitly says readiness LEVELS, not binary.
- **Blocking the pipeline on errors:** This step must be non-critical. Wrap in try/except, return error dict.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Schema type detection | Custom HTML re-parsing | Read from existing article_result and metadata_result | Data is already extracted; re-parsing would be redundant and would violate "no new HTTP requests" |
| Readiness scoring | Complex weighted scoring | Simple signal count (0-3 signals = none/minimal/moderate/strong) | Requirements are explicit about four levels; signal count maps directly |

**Key insight:** This step is intentionally simple. It's a pure function that reads three booleans from existing data and maps them to a label. The complexity was already handled by the extraction steps in earlier phases.

## Common Pitfalls

### Pitfall 1: Article @type Not Preserved in Extraction

**What goes wrong:** The article extraction step (`_extract_jsonld_article_fields`) currently does NOT store `@type` in its returned fields dict. It uses `@type` internally to find article nodes, but strips it from the output. If Phase 16 tries to read `article_result["jsonld_fields"]["@type"]`, it will find nothing.
**Why it happens:** The original extraction step was designed for metadata quality assessment, not schema type detection. `@type` was filtering criteria, not output data.
**How to avoid:** Modify `_extract_jsonld_article_fields()` to include `@type` in the returned dict (see Pattern 2 above). This is a backward-compatible addition.
**Warning signs:** Tests that mock article_result with `@type` present will pass, but real pipeline runs will produce `has_news_article_schema: False` for all articles.

### Pitfall 2: NewsArticle Subtypes

**What goes wrong:** Only checking for exact string `"NewsArticle"` misses subtypes like `OpinionNewsArticle`, `AnalysisNewsArticle`, `ReportageNewsArticle`, `ReviewNewsArticle`.
**Why it happens:** schema.org has a type hierarchy; news article subtypes are all valid NewsArticle indicators.
**How to avoid:** Use substring check (`"NewsArticle" in type_string`) rather than equality check. All subtypes contain "NewsArticle" in their name.
**Warning signs:** Publishers using specific NewsArticle subtypes get `has_news_article_schema: False`.

### Pitfall 3: Step Must Handle All-None Inputs

**What goes wrong:** If publisher steps were skipped (TTL fresh) but article steps ran, or vice versa, some inputs may be None.
**Why it happens:** The TTL skip path copies publisher-level results from prior jobs, but the copy list doesn't yet include `sitemap_analysis_result` or `news_signals_result`.
**How to avoid:** Every input parameter to `run_google_news_step()` should default to `None` and be handled with `(x or {}).get(...)` pattern. Also: TTL skip path in supervisor needs updating (Phase 17 responsibility per prior decisions).
**Warning signs:** Pipeline crashes with AttributeError on NoneType when TTL skip is active.

### Pitfall 4: Step Placement vs Error Handling

**What goes wrong:** If the Google News step crashes, it could block pipeline completion since it runs after article steps but before the final "completed" status.
**Why it happens:** Uncaught exceptions in the try block propagate to the outer handler and mark the whole job as failed.
**How to avoid:** Wrap the step in its own try/except, similar to how non-critical steps should work. Return an error dict rather than crashing.
**Warning signs:** Pipeline jobs marked as "failed" when only the news readiness aggregation had an issue.

## Code Examples

### Signal Aggregation Step (verified against existing codebase patterns)

```python
# Source: follows pattern of run_cc_step, run_frequency_step in steps.py

NEWS_ARTICLE_TYPES = {
    "NewsArticle", "OpinionNewsArticle", "AnalysisNewsArticle",
    "ReportageNewsArticle", "ReviewNewsArticle",
}

def run_google_news_step(
    sitemap_analysis_result: dict | None,
    article_result: dict | None,
    metadata_result: dict | None,
) -> dict:
    """Aggregate Google News readiness signals from existing pipeline data."""
    signals = {}

    # Signal 1: News sitemap
    has_news_sitemap = bool(
        (sitemap_analysis_result or {}).get("has_news_sitemap")
    )
    signals["has_news_sitemap"] = has_news_sitemap

    # Signal 2: NewsArticle schema type on article
    jsonld_fields = (article_result or {}).get("jsonld_fields") or {}
    article_type = jsonld_fields.get("@type", "")
    has_news_article = any(
        t in article_type for t in NEWS_ARTICLE_TYPES
    ) if article_type else False
    signals["has_news_article_schema"] = has_news_article
    signals["article_schema_type"] = article_type

    # Signal 3: NewsMediaOrganization schema on publisher
    org = (metadata_result or {}).get("organization") or {}
    org_type = org.get("type", "")
    has_news_org = org_type == "NewsMediaOrganization"
    signals["has_news_media_org"] = has_news_org
    signals["org_schema_type"] = org_type

    # Compute readiness level
    signal_count = sum([has_news_sitemap, has_news_article, has_news_org])

    if signal_count >= 3:
        readiness = "strong"
    elif signal_count == 2:
        readiness = "moderate"
    elif signal_count == 1:
        readiness = "minimal"
    else:
        readiness = "none"

    return {
        "readiness": readiness,
        "signals": signals,
        "signal_count": signal_count,
        "error": None,
    }
```

### Fixing Article Extraction @type Gap

```python
# In _extract_jsonld_article_fields, add @type to returned fields
# Source: modification of existing code in steps.py lines 1095-1119

def _extract_jsonld_article_fields(jsonld_items: list) -> dict | None:
    """Extract key fields from the first article-type JSON-LD node."""
    nodes = _flatten_jsonld_nodes(jsonld_items)
    for node in nodes:
        types = _normalize_types(node)
        if any(t.split("/")[-1] in ARTICLE_TYPES for t in types):
            fields: dict = {}
            # Include @type for downstream consumers (Google News readiness)
            matched_type = next(
                (t.split("/")[-1] for t in types if t.split("/")[-1] in ARTICLE_TYPES),
                None,
            )
            if matched_type:
                fields["@type"] = matched_type
            for field in KEY_FIELDS:
                val = node.get(field)
                if val is not None:
                    # ... existing extraction logic unchanged ...
```

### Supervisor Wiring with Non-Critical Error Handling

```python
# Source: follows established pattern in supervisor.py

# Step: Google News readiness (non-critical)
publish_step_event(job_id, "google_news", "started")
try:
    news_result = run_google_news_step(
        sitemap_analysis_result=resolution_job.sitemap_analysis_result,
        article_result=resolution_job.article_result,
        metadata_result=resolution_job.metadata_result,
    )
except Exception as exc:
    logger.error(f"Google News step error for job {job_id}: {exc}")
    news_result = {
        "readiness": "",
        "signals": {},
        "signal_count": 0,
        "error": str(exc),
    }
resolution_job.news_signals_result = news_result
resolution_job.save(update_fields=["news_signals_result"])
publish_step_event(job_id, "google_news", "completed", news_result)

publisher.google_news_readiness = news_result.get("readiness", "")
publisher.save(update_fields=["google_news_readiness"])
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Apply to Google News via Publisher Center | Google auto-includes credible sites | 2025 | No application process; inclusion is algorithmic |
| Binary "in Google News / not in" | Readiness signals (heuristic) | v2.1 design decision | Our tool shows readiness level, not inclusion status |
| Required schema for news | Recommended schema (no required fields) | Google 2023 update | Article structured data has no required properties; all are recommended |

**Deprecated/outdated:**
- Google News Publisher Center application process: Shut down in 2025. Google now auto-indexes sites it considers credible news sources.
- Binary Google News inclusion checking: Not feasible or meaningful. Our approach (readiness signals) is correct.

## Open Questions

1. **Microdata article @type gap**
   - What we know: `_extract_microdata_article_fields()` has the same gap -- it doesn't store @type either
   - What's unclear: Should we fix microdata extraction too, or only JSON-LD?
   - Recommendation: Fix both for consistency. But JSON-LD is the primary path since it's checked first and most publishers use JSON-LD for structured data.

2. **TTL skip path for news_signals_result**
   - What we know: Per Phase 15-02 decision, "No TTL skip path for new steps -- Phase 17 responsibility"
   - What's unclear: Should Phase 16 proactively handle the TTL skip, or strictly defer to Phase 17?
   - Recommendation: Follow the established decision. Phase 16 only creates the step function and wires it. Phase 17 handles TTL skip paths for all new steps.

3. **Views/API exposure of news_signals_result**
   - What we know: The views.py `result_fields` list and Inertia props don't include sitemap_analysis_result, frequency_result, or news_signals_result yet
   - What's unclear: Should Phase 16 update views to expose the new data?
   - Recommendation: Defer to Phase 18 (UI integration) which is explicitly responsible for report card updates. Phase 16 focuses on backend step + data only.

## Sources

### Primary (HIGH confidence)
- Codebase: `scrapegrape/publishers/pipeline/steps.py` -- all existing step function patterns, ARTICLE_TYPES, ORG_TYPES, KEY_FIELDS, extraction logic
- Codebase: `scrapegrape/publishers/pipeline/supervisor.py` -- pipeline execution order, SSE event pattern, step wiring pattern
- Codebase: `scrapegrape/publishers/models.py` -- `news_signals_result` JSONField (line 136), `google_news_readiness` CharField (line 38), already created by Phase 13 migration 0008
- Codebase: `scrapegrape/publishers/pipeline/events.py` -- `publish_step_event()` function signature
- Planning: `.planning/phases/15-content-signals/15-02-SUMMARY.md` -- confirms sitemap analysis and frequency are wired into supervisor
- Planning: `.planning/phases/13-data-foundation/13-RESEARCH.md` -- confirms field schema for news_signals_result and google_news_readiness

### Secondary (MEDIUM confidence)
- [Google Article Structured Data docs](https://developers.google.com/search/docs/appearance/structured-data/article) -- No required properties; datePublished, dateModified, headline, image are recommended
- [Google News Publisher Center best practices](https://support.google.com/news/publisher-center/answer/9607104?hl=en) -- Article page requirements for Google News
- [Google News SEO guide 2025](https://blog.quintype.com/industry/google-news-seo-optimization-guide-for-digital-publishers-2025) -- Google shut down application process in 2025; auto-inclusion is now the norm

### Tertiary (LOW confidence)
- None. All findings verified against codebase or official docs.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies; pure aggregation of existing data
- Architecture: HIGH -- all three input signals verified to exist in codebase; step placement determined by data dependencies
- Pitfalls: HIGH -- @type gap verified by reading actual extraction code; all other pitfalls follow from codebase analysis

**Research date:** 2026-02-18
**Valid until:** 2026-03-18 (stable -- no external dependencies to go stale)
