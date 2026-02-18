# Technology Stack: Competitive Intelligence Features

**Project:** itsascout (scrapegrape)
**Researched:** 2026-02-17
**Scope:** NEW stack additions for Common Crawl presence checking, Google News inclusion detection, and publisher update frequency estimation

## Context: Existing Stack (DO NOT change)

Already in place and validated:

- Django 5.2 + DRF + Inertia.js + React 19.1 + Vite + TailwindCSS
- RQ for task queue, Redis for queue + SSE pub/sub
- curl-cffi + Zyte for fetching (FetchStrategyManager)
- protego for robots.txt parsing
- extruct for structured data extraction (JSON-LD, OpenGraph, Microdata)
- pydantic-ai with GPT-4.1-nano for LLM steps
- polars (in deps, not yet used in app code)
- httpx (in deps)
- lxml (transitive via extruct)
- w3lib (in deps)

**Already handled by existing pipeline steps:**
- Sitemap URL discovery (from robots.txt Sitemap: directives + common path probing)
- RSS feed URL discovery (from homepage HTML `<link>` tags)
- NewsArticle schema.org type detection (extruct already extracts JSON-LD with `ARTICLE_TYPES` including `NewsArticle`)
- Homepage HTML fetching (reusable for new steps)

---

## Recommended Stack Additions

### 1. Common Crawl Index: Direct HTTP API (NO new library needed)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| httpx (existing) | >=0.28.1 | Query CC CDX API at index.commoncrawl.org | Already in deps; CC Index API is a simple HTTP JSON endpoint; no library overhead needed |

**Why NOT cdx-toolkit:**

cdx-toolkit (v0.9.38, Nov 2025) is the official Common Crawl Python client. However, it is overkill for our use case. We need exactly one thing: "does this domain appear in Common Crawl?" cdx-toolkit pulls in additional dependencies, implements WARC extraction, multi-index stitching, and pagination abstractions we do not need. The CC Index API is a single HTTP GET that returns JSON.

**How the CC Index API works:**

```
GET https://index.commoncrawl.org/CC-MAIN-2025-51-index?url=*.example.com&output=json&showNumPages=true
```

Returns: `{"pages": 5, "pageSize": 5, "blocks": 25}` -- if pages > 0, the domain is in Common Crawl.

For richer data (capture count, status codes, timestamps):
```
GET https://index.commoncrawl.org/CC-MAIN-2025-51-index?url=*.example.com&output=json&limit=10
```

Returns NDJSON lines with `url`, `status`, `timestamp`, `mime`, `length` per capture.

**Implementation approach:**

```python
import httpx

CC_INDEX_URL = "https://index.commoncrawl.org"
CC_LATEST_CRAWL = "CC-MAIN-2025-51"  # Update periodically or fetch from collinfo.json

def check_cc_presence(domain: str) -> dict:
    """Check if domain appears in Common Crawl's latest index."""
    # Step 1: Quick page count check
    resp = httpx.get(
        f"{CC_INDEX_URL}/{CC_LATEST_CRAWL}-index",
        params={"url": f"*.{domain}", "output": "json", "showNumPages": "true"},
        timeout=30,
    )
    if resp.status_code == 404:
        return {"in_common_crawl": False, "captures": 0}

    data = resp.json()
    page_count = data.get("pages", 0)

    if page_count == 0:
        return {"in_common_crawl": False, "captures": 0}

    # Step 2: Fetch a sample of captures for metadata
    resp2 = httpx.get(
        f"{CC_INDEX_URL}/{CC_LATEST_CRAWL}-index",
        params={"url": f"*.{domain}", "output": "json", "limit": "10"},
        timeout=30,
    )
    captures = [json.loads(line) for line in resp2.text.strip().split("\n") if line]

    return {
        "in_common_crawl": True,
        "estimated_pages": page_count * data.get("pageSize", 5),
        "sample_captures": captures[:5],
        "latest_crawl": CC_LATEST_CRAWL,
    }
```

**Rate limiting considerations:**
- CC Index API is heavily rate limited. Single-threaded, serial requests only.
- Include proper User-Agent header.
- Sleep between requests if querying multiple domains.
- If IP gets blocked (HTTP 503), wait 24 hours.
- For our use case (one domain per pipeline run), rate limits are not a concern.

**Discovering the latest crawl ID:**
```python
resp = httpx.get(f"{CC_INDEX_URL}/collinfo.json", timeout=15)
crawls = resp.json()
latest = crawls[0]["cdx-api"]  # Most recent crawl's API endpoint
```

**Confidence:** HIGH -- CC Index API is well-documented, stable, and our use case (single domain lookup) is trivially within rate limits. httpx is already in deps.

### 2. Google News Inclusion Detection: No new library needed

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| lxml (existing, transitive) | N/A | Parse sitemap XML for news namespace | Already installed via extruct; handles XML namespace queries |
| extruct (existing) | >=0.18.0 | Detect NewsArticle schema.org types | Already in pipeline; `ARTICLE_TYPES` already includes `NewsArticle` |

**What "Google News inclusion" means for the report card:**

Google News inclusion cannot be definitively confirmed programmatically (only Google knows). What we CAN detect are the **signals that a publisher has optimized for Google News**:

1. **News sitemap presence** -- sitemap XML with `xmlns:news="http://www.google.com/schemas/sitemap-news/0.9"` namespace
2. **NewsArticle schema.org markup** -- JSON-LD with `@type: "NewsArticle"` (already detected by existing article extraction step)
3. **NewsMediaOrganization schema.org markup** -- publisher identifies as news org (already scored in `_score_jsonld_candidate`)
4. **Google Publisher Center signals** -- presence of `<meta name="google-news-link-text">` or `<link rel="dns-prefetch" href="//news.google.com">`

**News sitemap detection approach:**

The existing `run_sitemap_step` already discovers sitemap URLs. The new step fetches each discovered sitemap and checks for the Google News XML namespace:

```python
from lxml import etree

NEWS_NS = "http://www.google.com/schemas/sitemap-news/0.9"

def detect_news_sitemap(sitemap_xml: str) -> dict:
    """Check if a sitemap contains Google News namespace elements."""
    try:
        root = etree.fromstring(sitemap_xml.encode("utf-8"))
    except etree.XMLSyntaxError:
        return {"is_news_sitemap": False, "error": "invalid XML"}

    # Check namespace declaration
    nsmap = root.nsmap
    has_news_ns = NEWS_NS in nsmap.values()

    # Check for actual news:news elements
    news_elements = root.findall(f".//{{{NEWS_NS}}}news")

    if news_elements:
        # Extract sample data
        sample = []
        for elem in news_elements[:5]:
            pub_name = elem.findtext(f"{{{NEWS_NS}}}publication/{{{NEWS_NS}}}name")
            title = elem.findtext(f"{{{NEWS_NS}}}title")
            pub_date = elem.findtext(f"{{{NEWS_NS}}}publication_date")
            sample.append({"name": pub_name, "title": title, "date": pub_date})

        return {
            "is_news_sitemap": True,
            "news_entry_count": len(news_elements),
            "sample_entries": sample,
        }

    return {"is_news_sitemap": has_news_ns, "news_entry_count": 0}
```

**Integration point:** This step runs AFTER `run_sitemap_step` (which provides sitemap URLs). It fetches each sitemap URL and checks for news namespace. The existing `FetchStrategyManager` handles the HTTP fetching.

**NewsArticle detection is already built:**
- `ARTICLE_TYPES` in `steps.py` already includes `NewsArticle`, `OpinionNewsArticle`, `AnalysisNewsArticle`, `ReportageNewsArticle`, `ReviewNewsArticle`
- `ORG_TYPES` already includes `NewsMediaOrganization`
- The existing article extraction step already captures the `@type` field

The new step merely needs to aggregate these existing signals into a "Google News readiness" score.

**Confidence:** HIGH -- lxml namespace parsing is well-documented. News sitemap schema (xmlns:news/0.9) is stable since 2014. Existing pipeline already captures most signals.

### 3. Update Frequency Estimation: feedparser + stdlib statistics

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| feedparser | 6.0.12 | Parse RSS/Atom feed entries with dates | De facto standard; handles all feed formats; robust date parsing across dozens of date formats |
| statistics (stdlib) | N/A | Calculate median/mean of publication intervals | No dependency; stdlib `statistics.median` and `statistics.mean` are sufficient |
| datetime (stdlib) | N/A | Date arithmetic for interval calculation | Standard library |

**Why feedparser for update frequency (not just sitemap lastmod):**

Sitemap `<lastmod>` values are unreliable. Google has publicly stated they verify lastmod accuracy before trusting it. Many CMS platforms set lastmod to the current date on every sitemap regeneration, making it useless for frequency estimation.

RSS/Atom feeds are MORE reliable for frequency estimation because:
- Feed entries have `published` dates set at article creation time (harder to fake)
- Feeds are ordered chronologically by nature
- feedparser normalizes dozens of date formats into Python time tuples

**Two-source approach for robustness:**

1. **RSS/Atom feeds** (primary): Parse feed entries, extract `published_parsed` dates, calculate intervals
2. **Sitemap lastmod** (secondary, with validation): Parse sitemap XML `<lastmod>` values, but validate by checking if dates are all identical or suspiciously regular

```python
import feedparser
from datetime import datetime, timezone
from statistics import median, mean

def estimate_frequency_from_feed(feed_url: str, feed_content: str) -> dict:
    """Estimate publishing frequency from RSS/Atom feed entries."""
    parsed = feedparser.parse(feed_content)

    if not parsed.entries:
        return {"source": "rss", "estimable": False, "reason": "no entries"}

    # Extract dates
    dates = []
    for entry in parsed.entries:
        if entry.get("published_parsed"):
            dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            dates.append(dt)

    if len(dates) < 2:
        return {"source": "rss", "estimable": False, "reason": "insufficient dates"}

    dates.sort(reverse=True)

    # Calculate intervals between consecutive articles
    intervals = []
    for i in range(len(dates) - 1):
        delta = dates[i] - dates[i + 1]
        intervals.append(delta.total_seconds() / 3600)  # hours

    median_hours = median(intervals)
    mean_hours = mean(intervals)

    # Classify frequency
    if median_hours < 1:
        frequency = "multiple_per_hour"
    elif median_hours < 24:
        frequency = "multiple_per_day"
    elif median_hours < 48:
        frequency = "daily"
    elif median_hours < 168:
        frequency = "several_per_week"
    elif median_hours < 336:
        frequency = "weekly"
    elif median_hours < 1440:
        frequency = "several_per_month"
    else:
        frequency = "monthly_or_less"

    return {
        "source": "rss",
        "estimable": True,
        "frequency": frequency,
        "median_interval_hours": round(median_hours, 1),
        "mean_interval_hours": round(mean_hours, 1),
        "sample_size": len(dates),
        "date_range_days": round((dates[0] - dates[-1]).total_seconds() / 86400, 1),
    }
```

**Sitemap lastmod validation:**

```python
from lxml import etree
from datetime import datetime

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

def extract_sitemap_lastmod_dates(sitemap_xml: str) -> list[datetime]:
    """Extract and validate lastmod dates from sitemap XML."""
    root = etree.fromstring(sitemap_xml.encode("utf-8"))
    dates = []
    for lastmod in root.findall(f".//{{{SITEMAP_NS}}}lastmod"):
        text = lastmod.text
        if text:
            # Parse ISO 8601 dates (W3C Datetime format)
            try:
                dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
                dates.append(dt)
            except ValueError:
                continue
    return dates

def validate_lastmod_reliability(dates: list[datetime]) -> bool:
    """Check if lastmod dates appear genuine (not all identical)."""
    if len(dates) < 3:
        return False
    unique_dates = set(d.date() for d in dates)
    # If >80% of dates are the same day, lastmod is likely auto-generated
    most_common_count = max(dates.count(d) for d in set(dates))
    return most_common_count / len(dates) < 0.5
```

**Why NOT polars for frequency calculation:**

Polars is already in deps and has excellent time-series support, but using it for ~20-50 date intervals is overkill. stdlib `statistics.median` and `statistics.mean` on a list of floats is clearer and has zero overhead. If the project later needs to analyze thousands of timestamps across many publishers, polars would be appropriate then.

**Confidence:** HIGH -- feedparser 6.0.12 (Sep 2025) is current. Date parsing and interval calculation are straightforward stdlib operations.

### 4. Sitemap Content Fetching: Existing FetchStrategyManager

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| FetchStrategyManager (existing) | N/A | Fetch sitemap XML content for parsing | Already handles curl-cffi + Zyte fallback; consistent with pipeline pattern |

**Current gap:** The existing `run_sitemap_step` discovers sitemap URLs but does NOT fetch their content. It only validates that a response looks like XML (`<?xml` or `<urlset>` check). The new features need to actually parse sitemap content for:
- News namespace detection
- lastmod date extraction

**Approach:** Add a `run_sitemap_analysis_step` that takes the sitemap URLs from `run_sitemap_step` output, fetches each one via `FetchStrategyManager`, and parses the XML with lxml.

**Confidence:** HIGH -- pure integration of existing components.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| CC Index query | httpx (direct API) | cdx-toolkit | Overkill for single-domain presence check; adds dep + WARC/pagination abstractions we don't need |
| CC Index query | httpx (direct API) | comcrawl | Unmaintained; limited filtering; intended for small projects only |
| News sitemap parsing | lxml (existing) | BeautifulSoup4 | lxml handles XML namespaces natively; BS4 is for HTML not XML |
| News sitemap parsing | lxml (existing) | ultimate-sitemap-parser | USP discovers sitemaps but doesn't expose news namespace metadata; we already have discovery |
| Feed parsing | feedparser | atoma | feedparser is more battle-tested; broader format support |
| Feed parsing | feedparser | Raw XML parsing with lxml | feedparser handles dozens of date formats automatically; not worth reimplementing |
| Frequency stats | stdlib statistics | polars | Overkill for 20-50 data points; stdlib is clearer |
| Frequency stats | stdlib statistics | numpy | Unnecessary dependency addition for simple median/mean |

---

## Installation

```bash
# Single new dependency
uv add feedparser

# Everything else is already in deps:
# - httpx (for CC Index API)
# - lxml (transitive via extruct, for sitemap XML parsing)
# - extruct (for NewsArticle schema detection -- already used)
# - protego (for robots.txt -- already used)
# - statistics (stdlib)
# - datetime (stdlib)
```

**That's it.** One new package. The rest leverages the existing stack.

---

## What NOT to Add (Already Have It)

| Capability | Already Covered By | Location |
|------------|--------------------|----------|
| Sitemap URL discovery | `run_sitemap_step` | `steps.py` |
| RSS feed URL discovery | `run_rss_step` | `steps.py` |
| NewsArticle type detection | `ARTICLE_TYPES` set + extruct | `steps.py` |
| NewsMediaOrganization detection | `ORG_TYPES` set + extruct | `steps.py` |
| HTTP fetching with TLS fingerprinting | `FetchStrategyManager` | `fetchers/manager.py` |
| robots.txt parsing | protego | `steps.py` |
| JSON-LD/OpenGraph/Microdata extraction | extruct | `steps.py` |
| XML parsing (lxml) | Transitive via extruct | Already installed |

---

## Integration Points with Existing Pipeline

### New Pipeline Steps (added to supervisor.py)

| Step | Depends On | New Library | Placement |
|------|-----------|-------------|-----------|
| Common Crawl presence check | publisher.domain | httpx (existing) | After robots step (independent, can run early) |
| Sitemap content analysis (news detection + lastmod) | sitemap_result (URLs) | lxml (existing) | After sitemap step |
| RSS feed content analysis (update frequency) | rss_result (URLs) | feedparser (NEW) | After RSS step |
| Google News signals aggregation | article_result + sitemap_analysis + publisher_details | None (aggregation only) | After article extraction |

### New Model Fields (on ResolutionJob and/or Publisher)

```python
# ResolutionJob -- per-job results
cc_result = models.JSONField(null=True, blank=True)       # Common Crawl presence
news_result = models.JSONField(null=True, blank=True)      # Google News signals
frequency_result = models.JSONField(null=True, blank=True)  # Update frequency

# Publisher -- flat fields
in_common_crawl = models.BooleanField(null=True)
cc_estimated_pages = models.IntegerField(null=True)
has_news_sitemap = models.BooleanField(null=True)
google_news_signals = models.JSONField(null=True, blank=True)
update_frequency = models.CharField(max_length=30, blank=True, default="")
update_frequency_hours = models.FloatField(null=True)
```

### Data Flow

```
Existing pipeline steps:
  robots_step --> sitemap_step --> rss_step --> [existing steps]

New steps inserted after their dependencies:
  robots_step
    |
    +--> cc_presence_step (parallel-safe, no deps on other steps)
    |
    +--> sitemap_step
    |      |
    |      +--> sitemap_analysis_step (news detection + lastmod dates)
    |
    +--> rss_step
    |      |
    |      +--> rss_frequency_step (feedparser date extraction)
    |
    +--> [existing steps: RSL, publisher_details, article_extraction...]
    |
    +--> google_news_signals_step (aggregates: news sitemap + NewsArticle type + NewsMediaOrg)
    |
    +--> frequency_estimation_step (merges: RSS dates + sitemap lastmod dates)
```

---

## Dependency Impact Summary

| New Dependency | Size Impact | C Extension? | Docker Concern |
|----------------|-------------|--------------|----------------|
| feedparser >=6.0.12 | Small (~200KB) | No | None |

All other capabilities use existing dependencies. Zero new C extensions. Zero Docker changes.

---

## Sources

### Common Crawl CDX API
- [CC Index Server](https://index.commoncrawl.org) -- API documentation and endpoint listing
- [cdx-toolkit GitHub](https://github.com/commoncrawl/cdx_toolkit) -- reference for API patterns (decided against using as library)
- [cdx-toolkit PyPI](https://pypi.org/project/cdx-toolkit/) -- v0.9.38, Nov 2025, Python >=3.9
- [CC FAQ](https://commoncrawl.org/faq) -- rate limiting guidance
- [Searching 100B Pages with CDX](https://skeptric.com/searching-100b-pages-cdx/) -- practical CC Index API usage patterns

### Google News Sitemaps
- [Google News Sitemap Documentation](https://developers.google.com/search/docs/crawling-indexing/sitemaps/news-sitemap) -- official spec
- [Google News Schema (xmlns:news/0.9)](https://www.google.com/schemas/sitemap-news/0.9/) -- namespace definition
- [lxml Namespace Handling](https://lxml.de/parsing.html) -- XPath with namespaces
- [Google Article Structured Data](https://developers.google.com/search/docs/appearance/structured-data/article) -- NewsArticle schema requirements
- [schema.org NewsArticle](https://schema.org/NewsArticle) -- type definition

### Feed Parsing and Update Frequency
- [feedparser PyPI](https://pypi.org/project/feedparser/) -- v6.0.12, Sep 2025
- [feedparser GitHub](https://github.com/kurtmckee/feedparser) -- date parsing capabilities
- [feedparser Date Parsing docs](https://pythonhosted.org/feedparser/date-parsing.html) -- format handling
- [Bing lastmod Importance](https://blogs.bing.com/webmaster/february-2023/The-Importance-of-Setting-the-lastmod-Tag-in-Your-Sitemap) -- lastmod reliability context
- [sitemaps.org Protocol](https://www.sitemaps.org/protocol.html) -- lastmod W3C Datetime format spec
