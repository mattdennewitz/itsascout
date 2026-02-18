# Architecture: Competitive Intelligence Features Integration

**Domain:** Common Crawl presence, Google News signals, update frequency estimation -- integrated into existing publisher analysis pipeline
**Researched:** 2026-02-17
**Confidence:** HIGH (existing codebase fully read, external APIs verified, integration points identified)

## Executive Summary

Three new competitive intelligence features integrate into the existing sequential pipeline as **four new step functions** plus **one aggregation step**. All follow the established pattern: step function in `steps.py`, JSON result field on `ResolutionJob`, flat cached fields on `Publisher`, SSE events for live progress, and a report card UI section.

The key insight is that these features build on already-discovered data. The existing `run_sitemap_step` discovers sitemap URLs; the new `run_sitemap_analysis_step` fetches those URLs and parses their XML content. The existing `run_rss_step` discovers RSS feed URLs; the new `run_rss_frequency_step` fetches those feeds and extracts publication dates. Only the Common Crawl step makes a genuinely new external request.

One new dependency: `feedparser`. Everything else uses httpx (existing), lxml (existing transitive), and stdlib.

## Current Pipeline (Steps 1-12)

```
Step 0:  Publisher resolution (implicit)
Step 1:  WAF detection
Step 2:  ToS discovery
Step 3:  ToS evaluation
Step 4:  robots.txt + URL allowance
Step 5:  AI bot blocking detection
Step 6:  Sitemap discovery          <-- provides sitemap_urls
Step 7:  RSS feed discovery         <-- provides feed URLs
Step 8:  RSL detection
Step 9:  Publisher details (structured data)
--- Article-level steps ---
Step 10: Article extraction         <-- already detects NewsArticle type
Step 11: Paywall detection
Step 12: Metadata profile
```

## Proposed Pipeline (Steps 1-15)

```
Step 0:  Publisher resolution (implicit)
Step 1:  WAF detection
Step 2:  ToS discovery
Step 3:  ToS evaluation
Step 4:  robots.txt + URL allowance
Step 5:  AI bot blocking detection
Step 6:  Sitemap discovery
Step 7:  RSS feed discovery
Step 8:  RSL detection
Step 9:  Publisher details (structured data)
Step 10: Common Crawl presence       <-- NEW (independent, external API)
Step 11: Sitemap analysis            <-- NEW (fetch sitemaps, check news NS, extract lastmod)
Step 12: Update frequency            <-- NEW (parse RSS dates + sitemap lastmod, compute intervals)
--- Article-level steps ---
Step 13: Article extraction
Step 14: Paywall detection
Step 15: Metadata profile
--- Aggregation (after article steps) ---
Step 16: Google News signals          <-- NEW (aggregate: news sitemap + NewsArticle + NewsMediaOrg)
```

### Why This Ordering

1. **CC presence (Step 10) after publisher details:** Independent of other new steps. Makes one external API call to CC Index. Runs in the publisher-level section so it benefits from freshness TTL skip.

2. **Sitemap analysis (Step 11) after sitemap discovery (Step 6):** Must have sitemap URLs before it can fetch and parse their content. Placed after publisher details to keep sitemap-related steps close together.

3. **Update frequency (Step 12) after RSS and sitemap analysis:** Needs RSS feed URLs from Step 7 and optionally sitemap lastmod dates from Step 11. Fetches RSS feed content via FetchStrategyManager, parses with feedparser.

4. **Google News signals (Step 16) AFTER article steps:** Aggregation step that combines news sitemap detection from Step 11, NewsArticle type from article extraction (Step 13), and NewsMediaOrganization from publisher details (Step 9). Must run after article extraction to access the article's schema type.

## Component Architecture

### New Step Functions (`publishers/pipeline/steps.py`)

#### `run_common_crawl_step(publisher)`

```python
def run_common_crawl_step(publisher: Publisher) -> dict:
    """Query CC CDX Index API for domain presence."""
    # 1. Get latest crawl ID from collinfo.json (cache per pipeline run)
    # 2. Query: GET /CC-MAIN-{id}-index?url=*.{domain}&output=json&showNumPages=true
    # 3. If pages > 0, query again with limit=5 for sample captures
    # Uses: httpx (existing in deps)

    return {
        "in_common_crawl": True,
        "estimated_pages": 2500,
        "latest_crawl": "CC-MAIN-2025-51",
        "sample_captures": [...],  # up to 5 capture records
    }
```

**Key details:**
- Uses `httpx.get()` with 30-second timeout (CC API can be slow)
- Include User-Agent header: `itsascout/1.0 (+https://itsascout.com)`
- CC returns NDJSON (newline-delimited JSON), not a JSON array -- parse line by line
- HTTP 404 = no records found (not an error)
- Cache `collinfo.json` response for duration of pipeline run (changes monthly)

#### `run_sitemap_analysis_step(publisher, sitemap_result, sitemap_cache)`

```python
def run_sitemap_analysis_step(
    publisher: Publisher,
    sitemap_result: dict,
    sitemap_cache: dict,  # shared cache: url -> xml_text
) -> dict:
    """Fetch discovered sitemaps, check for news namespace, extract lastmod dates."""
    # 1. For each sitemap URL in sitemap_result["sitemap_urls"] (limit to 5):
    #    a. Fetch via FetchStrategyManager, store in sitemap_cache
    #    b. Parse XML with lxml
    #    c. Check for xmlns:news namespace and news:news elements
    #    d. Extract <lastmod> timestamps
    # 2. If sitemap index, also probe first 3 child sitemaps
    # 3. Probe common news sitemap paths if no news NS found

    return {
        "has_news_sitemap": True,
        "news_sitemap_url": "https://example.com/news-sitemap.xml",
        "news_entry_count": 42,
        "news_sample_entries": [...],  # up to 5 entries with title, date, pub name
        "lastmod_dates": [...],  # ISO 8601 date strings from all parsed sitemaps
        "lastmod_reliable": True,  # False if dates look auto-generated
        "sitemaps_analyzed": 3,
    }
```

**Key details:**
- Limit sitemap fetching to 5 URLs max (avoid large sitemap indexes)
- Limit URL parsing to first 500 `<url>` entries per sitemap (memory guard)
- `sitemap_cache` is a plain dict passed between steps within one `run_pipeline()` call
- Use `lxml.etree.fromstring()` with namespace dict for XPath queries
- News namespace: `http://www.google.com/schemas/sitemap-news/0.9`
- Sitemap namespace: `http://www.sitemaps.org/schemas/sitemap/0.9`
- Common news sitemap paths to probe: `/news-sitemap.xml`, `/sitemap-news.xml`, `/google-news-sitemap.xml`

#### `run_update_frequency_step(publisher, rss_result, sitemap_analysis_result)`

```python
def run_update_frequency_step(
    publisher: Publisher,
    rss_result: dict,
    sitemap_analysis_result: dict,
) -> dict:
    """Estimate publishing frequency from RSS dates + sitemap lastmod."""
    # 1. Fetch each RSS feed URL from rss_result["feeds"][].url
    # 2. Parse with feedparser, extract published_parsed dates
    # 3. Sort, calculate intervals with stdlib statistics
    # 4. Optionally validate against sitemap lastmod dates
    # 5. Classify frequency

    return {
        "frequency": "multiple_per_day",  # classification label
        "median_interval_hours": 4.2,
        "mean_interval_hours": 5.1,
        "sample_size": 47,
        "date_range_days": 16.5,
        "data_source": "rss",  # or "sitemap" or "combined"
        "estimable": True,
        "most_recent": "2026-02-17T10:30:00Z",
    }
```

**Key details:**
- feedparser (new dep) handles RSS/Atom date normalization
- Use first RSS feed only (most sites have one primary feed)
- If RSS has no entries with dates, fall back to sitemap lastmod
- Validate sitemap lastmod reliability: if >50% of dates are identical, flag as unreliable
- `statistics.median` and `statistics.mean` for interval computation
- Guard against feeds with <2 dated entries: return `{"estimable": False, "reason": "insufficient dates"}`

#### `run_google_news_signals_step(sitemap_analysis_result, article_result, metadata_result)`

```python
def run_google_news_signals_step(
    sitemap_analysis_result: dict,
    article_result: dict | None,
    metadata_result: dict | None,
) -> dict:
    """Aggregate Google News readiness signals from multiple sources."""
    # 1. Check sitemap_analysis_result for news sitemap presence
    # 2. Check article_result for NewsArticle @type
    # 3. Check metadata_result for NewsMediaOrganization @type
    # 4. Compute readiness level: strong/moderate/minimal/none

    return {
        "has_news_sitemap": True,
        "has_newsarticle_schema": True,
        "has_newsmediaorg": False,
        "signals": ["news_sitemap", "newsarticle_schema"],
        "readiness": "strong",  # strong (2+ signals), moderate (1), minimal (0)
    }
```

**Key details:**
- Pure aggregation step -- no HTTP requests, no new parsing
- Reads from already-computed step results
- NewsArticle detection: check `article_result.jsonld_fields` for `@type` containing "NewsArticle" (or subtype)
- NewsMediaOrganization: check `metadata_result.organization.type` for "NewsMediaOrganization"
- Readiness levels: "strong" (news sitemap + at least one more signal), "moderate" (any one signal), "none" (no signals)

### New Model Fields

#### Publisher Model

```python
# Common Crawl
in_common_crawl = models.BooleanField(null=True)
cc_estimated_pages = models.IntegerField(null=True)

# Google News
has_news_sitemap = models.BooleanField(null=True)
google_news_readiness = models.CharField(max_length=20, blank=True, default="")

# Update frequency
update_frequency = models.CharField(max_length=30, blank=True, default="")
update_frequency_hours = models.FloatField(null=True)
```

#### ResolutionJob Model

```python
cc_result = models.JSONField(null=True, blank=True)
sitemap_analysis_result = models.JSONField(null=True, blank=True)
frequency_result = models.JSONField(null=True, blank=True)
news_signals_result = models.JSONField(null=True, blank=True)
```

### Supervisor Changes (`supervisor.py`)

Insert new steps into the publisher-level section:

```python
# After Step 9 (publisher details):

# Step 10: Common Crawl presence
publish_step_event(job_id, "common_crawl", "started")
cc_result = run_common_crawl_step(publisher)
resolution_job.cc_result = cc_result
resolution_job.save(update_fields=["cc_result"])
publish_step_event(job_id, "common_crawl", "completed", cc_result)
publisher.in_common_crawl = cc_result.get("in_common_crawl")
publisher.cc_estimated_pages = cc_result.get("estimated_pages")
publisher.save(update_fields=["in_common_crawl", "cc_estimated_pages"])

# Step 11: Sitemap analysis (shared cache for efficiency)
sitemap_cache = {}
publish_step_event(job_id, "sitemap_analysis", "started")
sitemap_analysis_result = run_sitemap_analysis_step(publisher, sitemap_result, sitemap_cache)
resolution_job.sitemap_analysis_result = sitemap_analysis_result
resolution_job.save(update_fields=["sitemap_analysis_result"])
publish_step_event(job_id, "sitemap_analysis", "completed", sitemap_analysis_result)
publisher.has_news_sitemap = sitemap_analysis_result.get("has_news_sitemap")
publisher.save(update_fields=["has_news_sitemap"])

# Step 12: Update frequency
publish_step_event(job_id, "update_frequency", "started")
freq_result = run_update_frequency_step(publisher, rss_result, sitemap_analysis_result)
resolution_job.frequency_result = freq_result
resolution_job.save(update_fields=["frequency_result"])
publish_step_event(job_id, "update_frequency", "completed", freq_result)
publisher.update_frequency = freq_result.get("frequency", "")
publisher.update_frequency_hours = freq_result.get("median_interval_hours")
publisher.save(update_fields=["update_frequency", "update_frequency_hours"])
```

Google News signals aggregation runs after article-level steps:

```python
# After Step 15 (metadata profile), before marking job complete:

publish_step_event(job_id, "google_news_signals", "started")
news_signals = run_google_news_signals_step(
    sitemap_analysis_result, article_result, resolution_job.metadata_result
)
resolution_job.news_signals_result = news_signals
resolution_job.save(update_fields=["news_signals_result"])
publish_step_event(job_id, "google_news_signals", "completed", news_signals)
publisher.google_news_readiness = news_signals.get("readiness", "")
publisher.save(update_fields=["google_news_readiness"])
```

**TTL skip path:** Add four new fields to the `prior` query and copy in the skip branch.

### Shared Sitemap Cache

Both sitemap analysis and update frequency may need the same sitemap XML. To avoid duplicate fetches:

```python
# In supervisor.py, create a shared dict:
sitemap_cache = {}  # url -> xml_text

# Sitemap analysis step populates the cache
sitemap_analysis_result = run_sitemap_analysis_step(publisher, sitemap_result, sitemap_cache)

# Update frequency step can use cached content if it needs sitemap lastmod
freq_result = run_update_frequency_step(publisher, rss_result, sitemap_analysis_result)
# Note: sitemap lastmod dates are already extracted in sitemap_analysis_result,
# so the frequency step reads them from the result dict, not from raw XML.
```

In practice, the sitemap_analysis step extracts lastmod dates and passes them in its result dict. The frequency step reads `sitemap_analysis_result["lastmod_dates"]` directly. The cache is more relevant if we later add other steps that need raw sitemap XML.

## Data Flow Diagram

```
                    EXISTING PIPELINE DATA
                    (from prior steps)
                        |
        +---------------+------------------+------------------+
        |               |                  |                  |
sitemap_result     rss_result      publisher.domain   article_result
(sitemap_urls)     (feeds[].url)        |             (schema types)
        |               |                |                  |
        v               |                v                  |
+------------------+    |     +------------------+          |
| Sitemap Analysis |    |     | Common Crawl     |          |
| - fetch XML      |    |     | - HTTP GET to    |          |
| - news namespace |    |     |   CDX Index API  |          |
| - extract lastmod|    |     +--------+---------+          |
+--------+---------+    |              |                    |
         |              |              v                    |
         |    +---------+     cc_result (JSONField)         |
         |    |                                             |
         v    v                                             |
+------------------+                                        |
| Update Frequency |                                        |
| - feedparser on  |                                        |
|   RSS content    |                                        |
| - interval math  |                                        |
+--------+---------+                                        |
         |                                                  |
         v                                                  |
frequency_result (JSONField)                                |
                                                            |
sitemap_analysis_result ──┐                                 |
                          ├─> Google News Signals (aggregation)
article_result ───────────┤
metadata_result ──────────┘
                          |
                          v
                   news_signals_result (JSONField)
                          |
                          v
              Publisher flat fields updated
              Report Card UI rendered
```

## Build Order

1. **Migration + model fields** -- Publisher + ResolutionJob additions (4 + 4 new fields)
2. **Common Crawl step** -- Independent, simplest, validates pipeline extension pattern
3. **Sitemap analysis step** -- Fetch and parse sitemaps for news NS + lastmod
4. **Update frequency step** -- feedparser dependency, interval math
5. **Google News signals step** -- Aggregation of prior steps
6. **Frontend "Competitive Intelligence" card** -- Report card UI section
7. **TTL skip path update** -- Copy new result fields in freshness skip branch

Each step can be shipped independently. The pipeline handles null results gracefully. The frontend handles missing data with "Not checked" placeholders.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Parsing Entire Sitemap Trees
**What:** Recursively fetching all sitemaps in a sitemap index (some sites have thousands)
**Why bad:** Triggers rate limiting, takes minutes, consumes excessive memory
**Instead:** Limit to first 5 sitemaps from index. Limit URL parsing to 500 entries per sitemap.

### Anti-Pattern 2: Storing Raw Sitemap XML in Database
**What:** Persisting fetched sitemap XML in ResolutionJob JSON fields
**Why bad:** Sitemaps can be 10MB+. Bloats the database and slows JSON serialization.
**Instead:** Parse in-memory, extract only timestamps and metadata. Discard raw XML.

### Anti-Pattern 3: Treating Missing News Sitemap as "Not in Google News"
**What:** Reporting "Publisher is NOT in Google News" when no news sitemap is found
**Why bad:** Many publishers appear in Google News without a news sitemap. Google auto-discovers articles.
**Instead:** Report "Google News readiness: minimal signals" and note that the publisher may still appear via auto-discovery.

### Anti-Pattern 4: Downloading CC WARC Records
**What:** Fetching actual crawled page content from CC S3 buckets
**Why bad:** Massive data transfer. We only need presence/count metadata.
**Instead:** Query CDX Index API with `showNumPages=true` and `limit=5`. Metadata only.

### Anti-Pattern 5: Using feedparser to Fetch URLs
**What:** Passing URLs directly to `feedparser.parse(url)` which fetches via urllib
**Why bad:** Bypasses FetchStrategyManager's TLS fingerprinting and publisher-aware strategy
**Instead:** Fetch RSS content via FetchStrategyManager first, then pass content string to `feedparser.parse(content_string)`

## Sources

- [Common Crawl CDX Index API](https://index.commoncrawl.org) -- API documentation
- [CC FAQ - Rate Limits](https://commoncrawl.org/faq) -- Throttling guidance
- [Google News Sitemap Documentation](https://developers.google.com/search/docs/crawling-indexing/sitemaps/news-sitemap) -- News sitemap spec
- [Google News Schema](https://www.google.com/schemas/sitemap-news/0.9/) -- xmlns:news namespace
- [lxml Namespace Handling](https://lxml.de/parsing.html) -- XPath with namespaces
- [feedparser Documentation](https://pythonhosted.org/feedparser/date-parsing.html) -- Date parsing
- [sitemaps.org Protocol](https://www.sitemaps.org/protocol.html) -- lastmod format
