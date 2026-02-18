# Phase 15: Content Signals - Research

**Researched:** 2026-02-17
**Domain:** XML sitemap analysis (news namespace detection), RSS feed date parsing (feedparser), publishing frequency estimation
**Confidence:** HIGH

## Summary

Phase 15 adds two new pipeline step functions: (1) a sitemap analysis step that fetches discovered sitemap URLs and checks for the `xmlns:news` XML namespace, and (2) an update frequency step that parses RSS feed dates via feedparser to estimate publishing cadence, falling back to sitemap `<lastmod>` dates when RSS is unavailable. Both steps follow the exact same pattern established by the CC step in Phase 14: step function in `steps.py`, result dict returned, supervisor wires SSE events and saves to ResolutionJob fields.

The existing pipeline already provides all the input data these steps need. The sitemap discovery step (Phase 9) populates `publisher.sitemap_urls` with a list of discovered sitemap URLs. The RSS discovery step (Phase 9) populates `publisher.rss_urls` with a list of discovered feed URLs. Phase 15 steps consume these existing fields -- they do not do their own discovery.

One new dependency is required: `feedparser 6.0.12` for robust RSS/Atom date parsing. feedparser handles the diversity of date formats found in RSS feeds (RFC 822, W3C datetime, ISO 8601, and many non-standard formats) and normalizes them to UTC time tuples. For sitemap analysis, Python's built-in `xml.etree.ElementTree` is sufficient -- no external XML parsing library is needed.

**Primary recommendation:** Add `run_sitemap_analysis_step()` and `run_frequency_step()` to `steps.py`. The sitemap analysis step fetches each sitemap URL (reusing `_fetch_manager`), checks for `xmlns:news` via string search on the raw XML, and optionally extracts `<lastmod>` dates. The frequency step fetches the first RSS feed URL via feedparser, extracts `published_parsed` dates, computes the median interval, and formats a human-readable frequency string with confidence indicator. Both steps save results to the ResolutionJob JSONFields created in Phase 13.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| feedparser | 6.0.12 | Parse RSS/Atom feeds and extract publication dates | The standard Python RSS parser; handles all date format variations, normalizes to UTC, works with both RSS and Atom feeds |
| xml.etree.ElementTree | stdlib | Parse XML sitemaps for namespace detection and lastmod extraction | Built-in, no dependency; sufficient for reading sitemap XML |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | 0.28.1 (existing) | Fetch RSS feed content for feedparser | Already in project; feedparser.parse() can accept URLs directly but using httpx gives us timeout control |
| FetchStrategyManager | existing | Fetch sitemap XML content | Already in project; reuse for sitemap fetches since some publishers have WAF protection |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| feedparser | Raw XML parsing of RSS | feedparser handles hundreds of date format variations, broken feeds, character encoding issues; hand-rolling this would be fragile |
| xml.etree.ElementTree | lxml | lxml is faster but adds a C dependency; ElementTree is sufficient for the small amount of XML parsing needed (namespace detection + lastmod extraction) |
| String search for xmlns:news | Full XML namespace-aware parsing | String search (`xmlns:news` or `google.com/schemas/sitemap-news`) is faster and sufficient; we only need to detect presence, not parse news elements |

**Installation:**
```bash
uv add feedparser==6.0.12
```

## Architecture Patterns

### Step Placement in Pipeline
```
Existing pipeline steps (supervisor.py):
  1. WAF check
  2. ToS discovery
  3. ToS evaluation
  4. robots.txt
  5. AI bot blocking
  6. Sitemap discovery       <-- produces publisher.sitemap_urls
  7. RSS discovery            <-- produces publisher.rss_urls
  8. RSL detection
  9. Common Crawl presence
 10. Publisher details
 --- article-level steps ---
 11. Article extraction
 12. Paywall detection
 13. Metadata profile

Phase 15 adds (after CC, before Publisher details):
  9b. Sitemap analysis        <-- consumes publisher.sitemap_urls
  9c. Update frequency        <-- consumes publisher.rss_urls, sitemap analysis lastmods
```

**Rationale:** Sitemap analysis and frequency estimation are publisher-level steps (not article-level). They should run after sitemap/RSS discovery (they consume those results) and after CC (which is independent). They run before Publisher details since they don't depend on structured data extraction.

**Note:** Actually wiring these into the supervisor with SSE events and TTL skip is Phase 17's responsibility. Phase 15 only creates the step functions and their tests. However, the step functions should be designed to be called from the supervisor with the same pattern as all other steps.

### Pattern 1: Step Function Signature (established pattern)
**What:** Every step function takes a Publisher and optional context, returns a dict
**When to use:** All pipeline steps
**Example from existing code:**
```python
# From run_cc_step -- the most recent step addition
def run_cc_step(publisher: Publisher) -> dict:
    """Query Common Crawl CDX Index API for publisher domain presence."""
    try:
        # ... do work ...
        return {"available": True, "in_index": True, ...}
    except Exception as exc:
        logger.error(f"CC step error for {publisher.domain}: {exc}")
        return {"available": False, "error": str(exc)}
```

### Pattern 2: Sitemap Analysis Step
**What:** Fetches discovered sitemap URLs, checks for xmlns:news namespace, extracts lastmod dates
**When to use:** Phase 15 sitemap analysis
**Input:** `publisher.sitemap_urls` (list of URLs from Phase 9 sitemap discovery)
**Output shape:**
```python
{
    "has_news_sitemap": True,       # xmlns:news detected in any sitemap
    "news_sitemap_url": "https://example.com/sitemap-news.xml",  # first news sitemap found
    "sitemaps_checked": 3,          # how many sitemaps were fetched
    "lastmod_dates": ["2026-02-17", "2026-02-16", ...],  # extracted lastmod values (for frequency fallback)
    "error": None,                  # or error string
}
```

### Pattern 3: Update Frequency Step
**What:** Parses RSS feed dates, computes publishing interval, formats human-readable string
**When to use:** Phase 15 frequency estimation
**Input:** `publisher.rss_urls` (list of URLs from Phase 9), optional `lastmod_dates` from sitemap analysis
**Output shape:**
```python
{
    "source": "rss",                      # or "sitemap" or "none"
    "frequency_label": "~3 articles/day", # human-readable
    "frequency_hours": 8.0,               # numeric hours between posts
    "confidence": "high",                 # high/medium/low
    "sample_size": 25,                    # number of dates used
    "date_span_days": 14,                 # span of dates analyzed
    "error": None,
}
```

### Anti-Patterns to Avoid
- **Fetching ALL sitemaps in a sitemap index:** Sitemap indexes can reference hundreds of child sitemaps. Only fetch the first few (2-3) to check for news namespace. The goal is detection, not exhaustive analysis.
- **Parsing the full RSS feed content:** We only need dates. Do not extract article titles, descriptions, or content. feedparser gives us `entries[i].published_parsed` which is all we need.
- **Using feedparser.parse(url) directly:** feedparser can fetch URLs itself, but we lose timeout control. Use httpx to fetch with a timeout, then pass the response text to `feedparser.parse()`.
- **Computing mean instead of median for frequency:** Outliers (e.g., holiday gaps) skew the mean. Median is more robust for estimating typical publishing cadence.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| RSS date parsing | Manual datetime parsing from RSS pubDate strings | feedparser `entry.published_parsed` | RSS dates come in dozens of formats (RFC 822, ISO 8601, non-standard). feedparser handles them all and normalizes to UTC |
| Atom date parsing | Manual parsing of Atom `<updated>` elements | feedparser (handles both RSS and Atom) | Same library handles both feed types transparently |
| W3C datetime parsing | Manual regex for sitemap `<lastmod>` dates | `datetime.fromisoformat()` (Python 3.11+) | Sitemap lastmod uses W3C datetime which is a subset of ISO 8601; Python 3.12+ handles this natively |
| Feed type detection | Check if feed is RSS vs Atom | feedparser auto-detects | feedparser.parse() handles RSS 0.9x, RSS 1.0, RSS 2.0, Atom 0.3, Atom 1.0, CDF transparently |

**Key insight:** The date parsing problem is deceptively complex. RSS feeds in the wild use hundreds of date format variations, many of which are technically invalid but widespread. feedparser has 20+ years of battle-tested date parsing that handles these edge cases. Any hand-rolled solution will break on real-world feeds.

## Common Pitfalls

### Pitfall 1: Sitemap Index vs Sitemap URL
**What goes wrong:** The discovered sitemap URL might be a sitemap index (`<sitemapindex>`) containing `<sitemap>` entries, not a regular sitemap with `<url>` entries. A news sitemap namespace could be in child sitemaps, not the index itself.
**Why it happens:** Many publishers use sitemap indexes pointing to dozens of child sitemaps (e.g., `/sitemap-news.xml`, `/sitemap-posts-2026.xml`).
**How to avoid:** When fetching a sitemap URL, check if it contains `<sitemapindex>`. If so, extract the first few `<loc>` entries and fetch those too (limit to 2-3 child sitemaps to stay fast). Check each for xmlns:news.
**Warning signs:** `has_news_sitemap` is always False even for known news publishers.

### Pitfall 2: Empty RSS Feeds or Missing Dates
**What goes wrong:** Some RSS feeds exist but have no entries, or entries lack `published_parsed` dates.
**Why it happens:** Some feeds only include `<updated>` (Atom) or have no date at all. feedparser normalizes this, but `published_parsed` can still be None.
**How to avoid:** Check both `entry.published_parsed` and `entry.updated_parsed`. Filter out entries where both are None. If the remaining sample is too small (< 3 entries with dates), fall back to sitemap lastmod dates or report low confidence.
**Warning signs:** Frequency result shows `sample_size: 0` despite RSS feeds existing.

### Pitfall 3: Timeout on Large Sitemaps
**What goes wrong:** Some publishers have very large sitemaps (10MB+). Fetching and parsing them is slow.
**Why it happens:** Enterprise publishers with thousands of pages have large sitemap files.
**How to avoid:** Set a timeout on sitemap fetches (10 seconds). For xmlns:news detection, we can check the first few KB of the response -- the namespace declaration is always in the root `<urlset>` element at the top. For lastmod extraction, limit to the first 50 entries.
**Warning signs:** Sitemap analysis step takes >15 seconds.

### Pitfall 4: Frequency Estimation with Irregular Publishing
**What goes wrong:** A publisher that posts 5 articles on weekdays and 0 on weekends gets a misleading frequency like "~5 articles/day" when checked on Monday but "0 articles/day" when checked on Saturday.
**Why it happens:** Publishing patterns are bursty, not uniform.
**How to avoid:** Use the median interval across the full sample, not just recent posts. Report confidence based on both sample size AND date span. A sample of 25 posts over 14 days is high confidence; 3 posts over 2 days is low confidence.
**Warning signs:** Same publisher gets wildly different frequency estimates on different runs.

### Pitfall 5: Confidence Thresholds Too Generous
**What goes wrong:** Reporting "high confidence" with 5 data points makes the estimate unreliable.
**Why it happens:** Temptation to always show something useful.
**How to avoid:** Conservative thresholds:
- **High:** >= 10 items AND date span >= 7 days
- **Medium:** >= 5 items AND date span >= 3 days
- **Low:** < 5 items OR date span < 3 days
**Warning signs:** Users see "high confidence: ~1 article/month" based on 2 blog posts.

## Code Examples

### Sitemap Analysis Step
```python
def run_sitemap_analysis_step(publisher: Publisher) -> dict:
    """Fetch discovered sitemaps and detect xmlns:news XML namespace."""
    sitemap_urls = publisher.sitemap_urls or []
    if not sitemap_urls:
        return {
            "has_news_sitemap": False,
            "news_sitemap_url": None,
            "sitemaps_checked": 0,
            "lastmod_dates": [],
            "error": None,
        }

    has_news = False
    news_url = None
    lastmod_dates = []
    checked = 0

    for url in sitemap_urls[:3]:  # Limit to first 3 sitemaps
        try:
            result = _fetch_manager.fetch(url, publisher=publisher)
            xml_text = result.html
            checked += 1

            # Check for news namespace (string search is fastest)
            if "xmlns:news" in xml_text or "schemas/sitemap-news" in xml_text:
                has_news = True
                if not news_url:
                    news_url = url

            # Handle sitemap index: check child sitemaps
            if "<sitemapindex" in xml_text:
                child_urls = _extract_sitemap_locs(xml_text, limit=2)
                for child_url in child_urls:
                    try:
                        child_result = _fetch_manager.fetch(child_url, publisher=publisher)
                        child_xml = child_result.html
                        checked += 1
                        if "xmlns:news" in child_xml or "schemas/sitemap-news" in child_xml:
                            has_news = True
                            if not news_url:
                                news_url = child_url
                        lastmod_dates.extend(_extract_lastmod_dates(child_xml, limit=50))
                    except Exception:
                        continue
            else:
                lastmod_dates.extend(_extract_lastmod_dates(xml_text, limit=50))

        except Exception as exc:
            logger.error(f"Sitemap analysis error for {url}: {exc}")
            continue

    return {
        "has_news_sitemap": has_news,
        "news_sitemap_url": news_url,
        "sitemaps_checked": checked,
        "lastmod_dates": sorted(lastmod_dates, reverse=True)[:50],
        "error": None,
    }
```

### Helper: Extract Sitemap Index Child URLs
```python
import xml.etree.ElementTree as ET

def _extract_sitemap_locs(xml_text: str, limit: int = 2) -> list[str]:
    """Extract <loc> URLs from a sitemap index, limited to first N entries."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = []
    for sitemap in root.findall("sm:sitemap/sm:loc", ns):
        if sitemap.text:
            locs.append(sitemap.text.strip())
            if len(locs) >= limit:
                break
    return locs
```

### Helper: Extract Lastmod Dates from Sitemap
```python
from datetime import datetime

def _extract_lastmod_dates(xml_text: str, limit: int = 50) -> list[str]:
    """Extract <lastmod> date strings from a sitemap XML."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    dates = []
    for url_elem in root.findall("sm:url/sm:lastmod", ns):
        if url_elem.text:
            dates.append(url_elem.text.strip())
            if len(dates) >= limit:
                break
    return dates
```

### Update Frequency Step
```python
import feedparser
from datetime import datetime, timezone
from time import mktime
from statistics import median

def run_frequency_step(publisher: Publisher, sitemap_analysis_result: dict | None = None) -> dict:
    """Estimate publishing frequency from RSS dates, falling back to sitemap lastmod."""
    rss_urls = publisher.rss_urls or []

    # Try RSS first
    if rss_urls:
        dates = _extract_rss_dates(rss_urls[0])  # Use first discovered feed
        if len(dates) >= 2:
            return _compute_frequency(dates, source="rss")

    # Fallback to sitemap lastmod dates
    lastmod_dates = (sitemap_analysis_result or {}).get("lastmod_dates", [])
    if lastmod_dates:
        parsed = _parse_lastmod_dates(lastmod_dates)
        if len(parsed) >= 2:
            return _compute_frequency(parsed, source="sitemap")

    return {
        "source": "none",
        "frequency_label": "",
        "frequency_hours": None,
        "confidence": "low",
        "sample_size": 0,
        "date_span_days": 0,
        "error": None,
    }


def _extract_rss_dates(feed_url: str) -> list[datetime]:
    """Fetch RSS feed and extract publication dates as UTC datetimes."""
    try:
        resp = httpx.get(feed_url, timeout=10.0, follow_redirects=True)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
    except Exception:
        return []

    dates = []
    for entry in feed.entries:
        parsed = entry.get("published_parsed") or entry.get("updated_parsed")
        if parsed:
            try:
                dt = datetime.fromtimestamp(mktime(parsed), tz=timezone.utc)
                dates.append(dt)
            except (ValueError, OverflowError):
                continue
    return sorted(dates, reverse=True)


def _compute_frequency(dates: list[datetime], source: str) -> dict:
    """Compute frequency stats from sorted datetime list."""
    if len(dates) < 2:
        return {
            "source": source,
            "frequency_label": "",
            "frequency_hours": None,
            "confidence": "low",
            "sample_size": len(dates),
            "date_span_days": 0,
            "error": None,
        }

    # Compute intervals between consecutive dates
    intervals_hours = []
    for i in range(len(dates) - 1):
        delta = abs((dates[i] - dates[i + 1]).total_seconds()) / 3600
        if delta > 0:
            intervals_hours.append(delta)

    if not intervals_hours:
        return {
            "source": source,
            "frequency_label": "",
            "frequency_hours": None,
            "confidence": "low",
            "sample_size": len(dates),
            "date_span_days": 0,
            "error": None,
        }

    med_hours = median(intervals_hours)
    span_days = abs((dates[0] - dates[-1]).total_seconds()) / 86400

    # Confidence based on sample size and date span
    if len(dates) >= 10 and span_days >= 7:
        confidence = "high"
    elif len(dates) >= 5 and span_days >= 3:
        confidence = "medium"
    else:
        confidence = "low"

    # Format human-readable label
    label = _format_frequency_label(med_hours)

    return {
        "source": source,
        "frequency_label": label,
        "frequency_hours": round(med_hours, 1),
        "confidence": confidence,
        "sample_size": len(dates),
        "date_span_days": round(span_days, 1),
        "error": None,
    }


def _format_frequency_label(hours_between: float) -> str:
    """Convert hours between posts to human-readable label."""
    if hours_between <= 0:
        return "~multiple/hour"
    posts_per_day = 24 / hours_between
    if posts_per_day >= 2:
        return f"~{round(posts_per_day)} articles/day"
    elif posts_per_day >= 1:
        return "~1 article/day"
    elif posts_per_day >= 1/7:
        posts_per_week = round(posts_per_day * 7)
        return f"~{posts_per_week} articles/week"
    else:
        posts_per_month = round(posts_per_day * 30)
        if posts_per_month >= 1:
            return f"~{posts_per_month} articles/month"
        return "< 1 article/month"
```

### Supervisor Wiring Pattern (Phase 17, shown for context)
```python
# In supervisor.py (Phase 17 will wire this)
publish_step_event(job_id, "sitemap_analysis", "started")
sitemap_analysis_result = run_sitemap_analysis_step(publisher)
resolution_job.sitemap_analysis_result = sitemap_analysis_result
resolution_job.save(update_fields=["sitemap_analysis_result"])
publish_step_event(job_id, "sitemap_analysis", "completed", sitemap_analysis_result)

publisher.has_news_sitemap = sitemap_analysis_result.get("has_news_sitemap")
publisher.save(update_fields=["has_news_sitemap"])

publish_step_event(job_id, "frequency", "started")
frequency_result = run_frequency_step(publisher, sitemap_analysis_result)
resolution_job.frequency_result = frequency_result
resolution_job.save(update_fields=["frequency_result"])
publish_step_event(job_id, "frequency", "completed", frequency_result)

publisher.update_frequency = frequency_result.get("frequency_label", "")
publisher.update_frequency_hours = frequency_result.get("frequency_hours")
publisher.update_frequency_confidence = frequency_result.get("confidence", "")
publisher.save(update_fields=["update_frequency", "update_frequency_hours", "update_frequency_confidence"])
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Custom RSS date parsing | feedparser 6.x with UTC normalization | Stable since feedparser 5.x | Handles all date formats reliably |
| lxml for sitemap parsing | xml.etree.ElementTree (stdlib) | Python 3.8+ | No external dependency for basic XML parsing |
| Full sitemap crawling for analysis | Sample first 2-3 sitemaps, string-search for namespace | This design | Fast detection without exhaustive crawling |

**Deprecated/outdated:**
- feedparser 5.x: Replaced by 6.x; API is the same, 6.x has better Python 3 support
- `time.struct_time` from feedparser: Still works fine, convert to datetime via `mktime()`

## Open Questions

1. **Should the frequency step fetch more than one RSS feed?**
   - What we know: Most publishers have 1 RSS feed. Some have category-specific feeds (news, sports, opinion).
   - What's unclear: Whether combining dates from multiple feeds gives better estimates.
   - Recommendation: Use only the first RSS feed URL. Simpler, faster, and the primary feed is typically the most representative. If we need to improve later, it's easy to iterate.

2. **Should sitemap analysis extract `<news:publication_date>` for frequency?**
   - What we know: News sitemaps contain `<news:publication_date>` which is a more reliable date than `<lastmod>`.
   - What's unclear: Whether it's worth the extra XML parsing complexity.
   - Recommendation: If a news sitemap is detected, extract `<news:publication_date>` values as an additional date source for the frequency step. This is a natural fit since we're already parsing the news sitemap. However, this is optional -- the RSS dates should be the primary source per requirement UF-02.

3. **How many sitemap index children should we fetch?**
   - What we know: Some indexes have 100+ child sitemaps. We can't fetch them all.
   - What's unclear: Whether 2 is enough to reliably detect news sitemaps.
   - Recommendation: Fetch up to 2 child sitemaps from an index. Many publishers name their news sitemap explicitly (e.g., `/sitemap-news.xml`), so we could prioritize child URLs containing "news" in the name. If the first 2 children don't have xmlns:news, it's unlikely the publisher has a news sitemap.

## Sources

### Primary (HIGH confidence)
- `/Users/matt/src/itsascout/scrapegrape/publishers/pipeline/steps.py` - Existing step function patterns (CC step, sitemap step, RSS step)
- `/Users/matt/src/itsascout/scrapegrape/publishers/pipeline/supervisor.py` - Supervisor wiring pattern, SSE events, TTL skip path
- `/Users/matt/src/itsascout/scrapegrape/publishers/models.py` - Model fields from Phase 13 (has_news_sitemap, update_frequency*, sitemap_analysis_result, frequency_result)
- [Google News Sitemap docs](https://developers.google.com/search/docs/crawling-indexing/sitemaps/news-sitemap) - xmlns:news namespace structure and required elements
- [feedparser PyPI](https://pypi.org/project/feedparser/) - Latest version 6.0.12, September 2025
- [feedparser date parsing docs](https://feedparser.readthedocs.io/en/main/date-parsing/) - Date format handling, UTC normalization
- [feedparser common RSS elements](https://feedparser.readthedocs.io/en/latest/common-rss-elements/) - entry.published_parsed API
- [sitemaps.org protocol](https://www.sitemaps.org/protocol.html) - lastmod format (W3C datetime)

### Secondary (MEDIUM confidence)
- [Google News Sitemap namespace schema](https://www.google.com/schemas/sitemap-news/0.9/) - Canonical namespace URL
- [Python xml.etree.ElementTree docs](https://docs.python.org/3/library/xml.etree.elementtree.html) - Namespace-aware parsing

### Tertiary (LOW confidence)
- None. All findings are from official documentation and direct codebase inspection.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - feedparser is the undisputed standard for RSS parsing; xml.etree is stdlib
- Architecture: HIGH - Follows exact same step function pattern as 10+ existing steps in this codebase
- Pitfalls: HIGH - Based on real-world XML sitemap and RSS feed behavior documented in official specs
- Code examples: HIGH - Derived from actual codebase patterns with verified feedparser API

**Research date:** 2026-02-17
**Valid until:** 2026-03-17 (30 days -- feedparser and sitemap specs are stable)
