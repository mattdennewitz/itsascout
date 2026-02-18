# Domain Pitfalls: Competitive Intelligence Features

**Domain:** Adding Common Crawl presence, Google News inclusion, and update frequency estimation to existing publisher analysis pipeline
**Researched:** 2026-02-17
**Confidence:** MEDIUM (CC Index API behavior verified via official docs and community reports; Google News detection is LOW confidence due to no official API; frequency estimation is MEDIUM based on sitemap/RSS standards)

---

## Critical Pitfalls

### Pitfall 1: Common Crawl Index API Timeouts Stalling the Entire Pipeline

**What goes wrong:**
The CC Index API (`index.commoncrawl.org`) is a single server that cannot be scaled up. Under load it returns HTTP 503 errors, and response times range from 2-15 seconds for a simple domain query. If the CC step is added as a blocking sequential step in the existing pipeline (like the other steps), a slow or failed CC query adds 15-30 seconds of latency to every analysis -- or worse, the step hangs until RQ's `job_timeout` kills the entire pipeline supervisor job.

**Why it happens:**
The CC Index server is a community resource with aggressive rate limiting. It is not designed for real-time interactive queries. Common Crawl's own documentation warns: "Please sleep between calls, don't run multiple threads at once on the same IP, and don't use proxy networks." If multiple users trigger analyses concurrently, your server makes parallel requests from the same IP, hitting rate limits and receiving 503s. Unlike the other pipeline steps (which hit the publisher's own infrastructure), CC is a shared third-party service with no SLA.

**Consequences:**
- Pipeline execution time increases by 5-30 seconds per analysis
- Under rate limiting, CC step fails for all concurrent analyses
- If CC step throws an unhandled exception, the existing `run_pipeline` supervisor catches it at the top level and marks the entire job as `failed` -- losing results from all previous steps (WAF, ToS, robots, sitemap, RSS, RSL, publisher details, article extraction)
- IP gets temporarily blocked (24-hour cooldown) if rate limits are exceeded repeatedly

**Prevention:**
1. **Never block the main pipeline on CC queries.** The CC step should be non-critical: wrap it in a try/except with a generous timeout (10 seconds), and treat failure as "data unavailable" rather than pipeline failure:
```python
def run_cc_presence_step(publisher: Publisher) -> dict:
    """Check Common Crawl index for domain presence. Non-critical step."""
    try:
        result = _query_cc_index(publisher.domain, timeout=10)
        return {"found": True, "crawl_count": result["count"], ...}
    except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
        logger.warning(f"CC Index unavailable for {publisher.domain}: {exc}")
        return {"found": None, "error": "CC Index unavailable", "skipped": True}
    except Exception as exc:
        logger.error(f"CC step error for {publisher.domain}: {exc}")
        return {"found": None, "error": str(exc), "skipped": True}
```
2. **Cache CC results aggressively.** CC Index data changes monthly (new crawl). Cache domain lookup results for 7 days minimum. Use a separate cache key from the publisher freshness TTL since CC data changes on a different cadence than the publisher's own signals.
3. **Query only the latest 1-2 crawl collections**, not all historical ones. Each collection query is a separate HTTP request. Querying `CC-MAIN-2026-06` is one call; querying the last 12 months is 12 calls. Start with the latest crawl only.
4. **Use `matchType=domain` and `limit=1`** to minimize response size. You only need to know IF the domain is present, not enumerate every URL. A full domain enumeration for a large publisher returns megabytes of data and times out.

**Detection:**
- Pipeline duration increases by 10+ seconds after adding CC step
- CC step shows "skipped" or "error" in >20% of analyses
- Server logs show 503 responses from `index.commoncrawl.org`

**Phase to address:**
First implementation of CC step. Must be designed as non-critical from day one.

---

### Pitfall 2: Google News Inclusion Detection Has No Reliable Programmatic Method

**What goes wrong:**
There is no Google News API for checking whether a publisher is included in Google News. Every detection method has significant false positive or false negative rates. Teams typically try one of these approaches, all of which are unreliable:

1. **Scraping `news.google.com/search?q=site:domain.com`**: Google actively blocks automated access. Returns CAPTCHAs, requires JavaScript rendering, changes HTML structure frequently. Even with a headless browser, this breaks every few weeks.
2. **Using Google Custom Search API with `tbm=nws`**: The `tbm` parameter is not officially supported in the Custom Search JSON API. It works intermittently but Google can remove it at any time. Results are also not identical to actual Google News inclusion.
3. **Checking for `news_keywords` meta tag or Google News sitemap**: These indicate the publisher *intends* to be in Google News, not that they *are* included. Many sites have these tags but are not in Google News, and many Google News sources lack these tags entirely.
4. **Checking Google Publisher Center registration**: No public API exists for this.

**Why it happens:**
Google News inclusion is algorithmically determined and not publicly queryable. Google deliberately does not expose a "is this site in Google News?" API. The inclusion process is opaque -- sites are automatically discovered based on editorial standards, E-E-A-T signals, and content quality. There is no binary "approved/not approved" status anymore (Google moved away from manual application in ~2019).

**Consequences:**
- Building a detection feature that returns confident YES/NO creates false trust in the data
- Scraping-based approaches break frequently, requiring ongoing maintenance
- False positives (saying a site IS in Google News when it isn't) damage credibility of the report card
- False negatives (missing legitimate Google News publishers) make the tool seem incomplete

**Prevention:**
1. **Use heuristic signals, not a binary detector.** Instead of "Is in Google News: YES/NO", report "Google News signals" as a collection of indicators:
```python
def run_google_news_signals_step(publisher: Publisher, homepage_html: str) -> dict:
    signals = []

    # Signal 1: Google News sitemap present
    # (Already have sitemap_result from earlier step)

    # Signal 2: news_keywords meta tag
    if 'name="news_keywords"' in homepage_html.lower():
        signals.append({"signal": "news_keywords_meta", "weight": 0.3})

    # Signal 3: NewsMediaOrganization schema.org type
    # (Already extracted in publisher_details step)

    # Signal 4: Google Publisher Center meta/link tag
    if 'googlenewspublisher' in homepage_html.lower():
        signals.append({"signal": "publisher_center_tag", "weight": 0.2})

    # Signal 5: Standout tag or editors-pick tag
    if 'standout' in homepage_html.lower():
        signals.append({"signal": "standout_tag", "weight": 0.2})

    return {
        "signals": signals,
        "signal_count": len(signals),
        "likelihood": "high" if len(signals) >= 3 else "medium" if len(signals) >= 1 else "low",
    }
```
2. **Label the output as "Google News Signals" or "Google News Likelihood", never "Google News Status: Approved/Not Approved."** This sets correct user expectations.
3. **Reuse data already collected.** The existing pipeline already fetches homepage HTML, parses structured data, and discovers sitemaps. Most Google News signals come from data you already have -- no additional external API calls needed.
4. **Do NOT scrape Google News directly.** It violates Google's ToS, is fragile, and adds an external dependency with no SLA. If you later want higher-confidence detection, use a SERP API (SerpAPI, HasData) as a paid service with proper rate limits.

**Detection:**
- Google News detection results contradicted by manual checks
- Feature returns "unknown" for >50% of publishers
- Scraping-based detection starts failing across all queries simultaneously

**Phase to address:**
Implementation phase. The key decision (heuristic signals vs. scraping) must be made before writing any code. Choose signals.

---

### Pitfall 3: Frequency Estimation from Sparse Sitemap/RSS Data Produces Misleading Results

**What goes wrong:**
The pipeline already discovers sitemaps and RSS feeds. The natural next step is to estimate publishing frequency from `<lastmod>` timestamps in sitemaps or `<pubDate>` in RSS items. But this data is severely limited:

- **RSS feeds typically contain only 10-20 most recent items.** If a publisher posts 50 articles/day, the RSS feed shows only the last few hours. If they post once a week, the RSS shows 10-20 weeks. The time window is inconsistent and not discoverable without parsing.
- **Sitemap `<lastmod>` values are unreliable.** Google ignores `<changefreq>` entirely. Many CMS platforms set `<lastmod>` to the current date on every sitemap regeneration (WordPress does this by default), making all URLs appear to have been updated "today."
- **Sitemap `<changefreq>` is meaningless.** The sitemaps.org protocol includes it, but Google and Bing both ignore it. Many sites set it to "daily" for all URLs regardless of actual update frequency.
- **Large sitemaps are paginated.** A publisher's sitemap index may reference 100+ sub-sitemaps. Fetching all of them to count URLs and extract dates adds significant latency (100 HTTP requests) and may trigger WAF rate limiting on the publisher's site.

**Why it happens:**
RSS and sitemaps were not designed as frequency estimation tools. RSS is a notification mechanism ("here are the latest items"), not a comprehensive publication log. Sitemaps are discovery aids ("here are URLs to crawl"), not a publication timeline. Using them for frequency estimation is an off-label use that works only when the data happens to be well-formed and representative.

**Consequences:**
- Reporting "publishes 3 articles/day" when the real number is 50 (RSS truncation)
- Reporting "updated today" for every URL because the CMS regenerates sitemaps with current timestamps
- Spending 30+ seconds fetching paginated sitemaps, doubling pipeline time
- Reporting "unknown" for publishers with dynamic sitemaps (generated on request, no static XML files)

**Prevention:**
1. **Use RSS dates as the primary signal, sitemap `<lastmod>` as secondary, and `<changefreq>` never.** RSS `<pubDate>` values are almost always accurate because feed readers depend on them. Sitemap `<lastmod>` is unreliable.
2. **Be honest about the data window.** If you have 15 RSS items spanning 3 days, report "approximately 5 articles/day (estimated from 15 items over 3 days)" -- not just "5 articles/day." The confidence interval matters:
```python
def estimate_frequency(items: list[dict]) -> dict:
    if not items or len(items) < 2:
        return {"frequency": None, "confidence": "insufficient_data"}

    dates = sorted([item["date"] for item in items if item.get("date")])
    if len(dates) < 2:
        return {"frequency": None, "confidence": "insufficient_data"}

    span = (dates[-1] - dates[0]).total_seconds()
    if span < 3600:  # Less than 1 hour of data
        return {"frequency": None, "confidence": "insufficient_span"}

    items_per_day = (len(dates) - 1) / (span / 86400) if span > 0 else None

    return {
        "items_per_day": round(items_per_day, 1) if items_per_day else None,
        "sample_size": len(dates),
        "sample_span_hours": round(span / 3600, 1),
        "confidence": "high" if len(dates) >= 10 and span > 86400 * 3 else
                      "medium" if len(dates) >= 5 and span > 86400 else "low",
        "source": "rss",
    }
```
3. **Do NOT fetch full sitemaps for frequency estimation.** Only fetch the first sitemap (or sitemap index) and parse the first page. If you need URL counts, use the sitemap index to count sub-sitemaps and estimate (e.g., "sitemap index has 47 sub-sitemaps, typical WordPress sub-sitemap has 1000 URLs, so approximately 47,000 URLs"). Do not enumerate all URLs.
4. **Fetch RSS feed content once, reuse for frequency.** The pipeline already discovers RSS feed URLs in `run_rss_step`. Add a follow-up step that fetches the actual feed content and parses dates. Do not re-discover the feed.
5. **Validate `<lastmod>` before using it.** If >80% of URLs in a sitemap have the same `<lastmod>` date, the dates are likely auto-generated and unreliable. Discard them:
```python
def validate_lastmod_dates(dates: list[datetime]) -> bool:
    """Return False if dates appear auto-generated (all same date)."""
    if not dates:
        return False
    unique_dates = set(d.date() for d in dates)
    # If >80% of dates fall on the same calendar day, they are likely bogus
    most_common_count = max(Counter(d.date() for d in dates).values())
    return most_common_count / len(dates) < 0.8
```

**Detection:**
- Frequency estimates wildly different from what manual inspection of the site suggests
- All sitemap URLs showing the same `<lastmod>` date
- Frequency step taking >10 seconds (fetching too many sitemaps)

**Phase to address:**
Frequency estimation implementation. The RSS parsing sub-step should be built and validated before attempting sitemap-based frequency estimation.

---

## Moderate Pitfalls

### Pitfall 4: CC Index API Query Format Gotchas

**What goes wrong:**
The CC Index API has non-obvious query semantics that produce wrong results:

- **Domain queries require `*.domain.com` wildcard prefix** to match subdomains. Querying `nytimes.com` only matches exactly `nytimes.com`, not `www.nytimes.com` or `cooking.nytimes.com`. Most real crawl data is under `www.` subdomains.
- **Each crawl collection is a separate API endpoint.** There is no "query across all crawls" endpoint. You must know the collection name (e.g., `CC-MAIN-2026-05`) and query it specifically. The list of available collections must be fetched from `https://index.commoncrawl.org/collinfo.json`.
- **Response format is NDJSON (newline-delimited JSON), not a JSON array.** Each line is a separate JSON object. Using `response.json()` will fail. You must parse line by line.
- **Pagination uses `page` and `pageSize` parameters measured in index blocks, not result count.** The default page size is 5 blocks. You cannot predict how many results are in a page without fetching it.

**Prevention:**
1. Always use `url=*.domain.com&matchType=domain` for domain presence checks
2. Fetch the collection list once and cache it (changes monthly)
3. Parse responses line-by-line: `[json.loads(line) for line in response.text.strip().split('\n') if line.strip()]`
4. Use `limit=1` for presence checks (you only need to know if ANY page was crawled)
5. Use `output=json` parameter explicitly -- default output is CDX text format, not JSON

**Phase to address:**
CC step implementation. Write integration tests against the real API with known domains.

---

### Pitfall 5: Adding 3 New Steps Breaks SSE Progress UX

**What goes wrong:**
The existing pipeline has ~12 steps with SSE progress events. Adding 3 new steps (CC presence, Google News signals, frequency estimation) means:
- The frontend progress indicators need updating (new step names, new step count)
- The `prior` job result copying in `should_skip_publisher_steps` must include the new result fields, or cached results will show "Not checked" for the new signals
- The freshness TTL skip logic must emit `"skipped"` events for the new steps, or the SSE stream will never send events for those steps and the frontend will show them as "pending" forever
- Total pipeline duration increases, potentially exceeding the RQ `job_timeout` of 600 seconds

**Prevention:**
1. **Update the `prior` results query in the supervisor** to include new result fields:
```python
# In supervisor.py, the .values() call for prior job copying:
.values(
    "waf_result", "tos_result", "robots_result",
    "sitemap_result", "rss_result", "rsl_result",
    "ai_bot_result", "metadata_result",
    "cc_result", "google_news_result", "frequency_result",  # NEW
)
```
2. **Add `"skipped"` events for all new steps** in the freshness TTL skip branch
3. **Add new JSONField columns to ResolutionJob** with a migration, and new flat fields on Publisher
4. **Position new steps wisely in the pipeline.** CC is an external API call -- place it after all local/fast steps. Frequency estimation depends on RSS data from `run_rss_step` -- place it after RSS. Google News signals reuse homepage HTML -- place it near other HTML-parsing steps.
5. **Update the frontend step list** to include new step names and descriptions

**Phase to address:**
Pipeline integration phase. The supervisor changes, model migration, and frontend updates must all ship together.

---

### Pitfall 6: RSS Feed Parsing for Frequency Requires Actual Feed Fetching (New HTTP Requests)

**What goes wrong:**
The existing `run_rss_step` only discovers RSS feed URLs from homepage `<link>` tags. It does NOT fetch the feed content. Frequency estimation requires actually fetching and parsing the RSS XML to extract `<pubDate>` values. This means:
- 1-3 additional HTTP requests per analysis (one per discovered feed)
- Feeds may be behind the same WAF/CDN as the main site
- Feed content may be large (some feeds include full article content, not just summaries)
- Feed parsing needs a proper XML parser (not regex), adding a dependency

**Prevention:**
1. **Fetch only the first discovered RSS feed**, not all of them. Multiple feeds usually contain overlapping content.
2. **Use `feedparser` library** for robust RSS/Atom parsing. It handles encoding issues, malformed XML, date format variations, and both RSS 2.0 and Atom formats. Do not write a custom XML parser.
3. **Set a response size limit** when fetching feeds. Some feeds are 5MB+ with full article content. Use `httpx` with a streaming response and stop reading after 500KB:
```python
async with httpx.AsyncClient() as client:
    async with client.stream("GET", feed_url, timeout=10) as response:
        content = b""
        async for chunk in response.aiter_bytes():
            content += chunk
            if len(content) > 500_000:  # 500KB limit
                break
```
4. **Reuse the existing `FetchStrategyManager`** for feed fetching so WAF-blocked sites use the Zyte fallback automatically.

**Phase to address:**
Frequency estimation phase. The feed fetching step is a prerequisite for frequency estimation.

---

### Pitfall 7: CC Crawl Data Shows Domain Presence, Not Current State

**What goes wrong:**
Common Crawl data is 1-6 months old. A domain present in the CC-MAIN-2025-51 crawl (December 2025) was crawled in December, but the site may have changed since then. The CC presence data tells you "Common Crawl has crawled this domain at some point in the last N months" -- it does not tell you "Common Crawl can currently access this domain."

This creates confusion when combined with real-time data from other steps. Example: the robots.txt step shows CCBot is blocked (real-time), but the CC presence step shows the domain IS in Common Crawl (from a crawl before the block was added). Users see contradictory information.

**Prevention:**
1. **Display the crawl date alongside CC presence data.** "Found in Common Crawl (December 2025 crawl)" is much more useful than "Found in Common Crawl: Yes."
2. **Cross-reference with the `ai_bot_blocking` step.** If CCBot is currently blocked in robots.txt but the domain is in CC, note: "Domain was in Common Crawl as of [date], but CCBot is currently blocked -- future crawls may be affected."
3. **Show multiple crawl timestamps if querying multiple collections.** This reveals trends: "Present in last 6 crawls" vs. "Present in 1 of last 6 crawls" tells a different story than just "present/not present."

**Phase to address:**
CC step UI/display phase. The cross-referencing logic should be in the frontend or in a synthesis step, not in the CC query step itself.

---

## Minor Pitfalls

### Pitfall 8: `feedparser` Date Parsing Edge Cases

**What goes wrong:**
RSS `<pubDate>` formats vary wildly. RFC 822 is the standard but many feeds use ISO 8601, Unix timestamps, or malformed dates. `feedparser` handles most of these, but edge cases remain:
- Dates without timezone (treated as UTC by some parsers, local time by others)
- Dates in non-English locales ("15 Fev 2026")
- Relative dates ("2 hours ago" -- yes, some feeds do this)

**Prevention:**
Use `feedparser`'s `published_parsed` attribute which returns a `time.struct_time`, then convert to datetime. For items where `published_parsed` is `None`, fall back to `updated_parsed`. Skip items with no parseable date rather than guessing.

---

### Pitfall 9: CC Index Returns Empty Results for New/Small Domains

**What goes wrong:**
Common Crawl does not crawl every domain. Small, new, or regional publishers may have zero presence in CC. Reporting "Not found in Common Crawl" for a small local news site is accurate but potentially alarming to users who do not understand CC's scope.

**Prevention:**
Frame CC absence as informational, not as a negative signal. "Not found in Common Crawl's most recent crawl. Common Crawl covers approximately 3 billion pages and may not include smaller or newer publishers." Avoid language like "Not indexed" which implies a problem.

---

### Pitfall 10: Google News Sitemap Detection Conflation

**What goes wrong:**
A publisher might have a `<sitemap>` entry in their sitemap index called `news-sitemap.xml` or `sitemap-news.xml`. This is a Google News sitemap (using the `<news:news>` XML namespace). The existing `run_sitemap_step` discovers these but does not distinguish them from regular sitemaps. If you use sitemap presence as a Google News signal, you need to actually check whether the sitemap uses the Google News XML namespace, not just match on the filename.

**Prevention:**
When checking for Google News sitemaps as a signal, fetch the first few KB of the sitemap and check for `xmlns:news="http://www.google.com/schemas/sitemap-news/0.9"` in the XML. A sitemap named "news-sitemap.xml" that uses the standard `<urlset>` namespace is just a regular sitemap for the /news/ section.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| CC Index integration | API timeout stalls pipeline (Critical #1) | Non-critical step with 10s timeout, 7-day cache, latest crawl only |
| CC Index integration | Wrong query format returns empty results (Moderate #4) | Use `*.domain.com` with `matchType=domain`, `output=json`, `limit=1` |
| CC Index integration | Stale data contradicts real-time signals (Moderate #7) | Display crawl date, cross-reference with CCBot blocking status |
| Google News detection | No reliable programmatic detection (Critical #2) | Use heuristic signals, not binary yes/no. Never scrape Google News. |
| Google News detection | News sitemap filename vs. namespace conflation (Minor #10) | Check XML namespace, not filename pattern |
| Frequency estimation | Sparse/misleading RSS data (Critical #3) | Report confidence levels, sample size, and data window alongside estimates |
| Frequency estimation | RSS feed fetching adds latency (Moderate #6) | Fetch only first feed, 500KB limit, reuse FetchStrategyManager |
| Frequency estimation | Sitemap `lastmod` unreliable (Critical #3) | Validate dates, discard if >80% same date, prefer RSS over sitemap |
| Pipeline integration | New steps break SSE progress and caching (Moderate #5) | Update prior-job copying, add skip events, update frontend step list |
| Pipeline integration | Total execution time exceeds RQ timeout | CC step timeout at 10s, frequency step timeout at 15s, monitor total time |

## Integration Gotchas Specific to This Milestone

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| CC step + existing pipeline | Adding CC as a blocking step between robots and sitemap steps | Place CC step after all critical steps. If it fails, all other results are still saved. |
| CC step + freshness TTL | Using the same 24-hour publisher freshness TTL for CC data that changes monthly | Use a separate CC cache TTL (7 days) stored on the Publisher model or in Redis |
| Frequency step + RSS step | Re-discovering RSS feeds in the frequency step | Pass `rss_result["feeds"]` from the existing RSS step into the frequency step. Fetch feed content in the frequency step only. |
| Frequency step + sitemap step | Fetching all sub-sitemaps to count URLs | Only fetch the sitemap index, count `<sitemap>` entries, estimate total URLs from sub-sitemap count |
| Google News signals + publisher details | Running a separate HTML parse for Google News meta tags | Reuse `homepage_html` already fetched. Add signal extraction to the existing HTML parsing flow. |
| New result fields + prior job copying | Forgetting to add new fields to the `prior` result copying `.values()` query | Add `cc_result`, `google_news_result`, `frequency_result` to both the `.values()` list and the field assignment block |
| New result fields + ResolutionJob model | Adding JSONField columns without a default | Use `null=True, blank=True` like existing result fields. Run migration before deploying new pipeline code. |

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| CC API rate limited / IP blocked | LOW | Wait 24 hours. Implement caching to prevent recurrence. Consider using CC's columnar index via Athena for bulk queries. |
| Google News detection giving false results | LOW | Reframe as "signals" in UI. No data correction needed since signals are honestly presented as heuristic. |
| Frequency estimates wildly wrong | LOW | Add confidence levels to UI. Re-run frequency estimation with fixed parsing logic. Old estimates can be overwritten on next analysis. |
| New steps breaking SSE progress | MEDIUM | Frontend fix to handle unknown step names gracefully (ignore, don't crash). Backend fix to add missing skip events. |
| Pipeline timeout from added steps | LOW | Increase RQ `job_timeout` from 600 to 900 seconds. Add per-step timeouts (CC: 10s, feed fetch: 10s). |
| Stale CC data confusing users | LOW | Add "as of [date]" to CC presence display. No data fix needed. |

## "Looks Done But Isn't" Checklist

- [ ] **CC Index query:** Works for `nytimes.com` but fails for domains with subdomains only (no `www.` prefix match). Test with `*.domain.com` wildcard.
- [ ] **CC Index caching:** Query works but hits the API on every analysis, even for the same domain within minutes. Verify caching layer actually prevents duplicate API calls.
- [ ] **Google News signals:** Detects signals on news sites but also fires for blog sites with `news_keywords` meta tags they copied from a template. Verify signal weighting produces reasonable "likelihood" values.
- [ ] **Frequency estimation:** Returns a number but it is based on 3 RSS items spanning 2 hours, extrapolated to a daily rate. Verify confidence level correctly reflects sample quality.
- [ ] **Frequency estimation:** Works on RSS 2.0 feeds but crashes on Atom feeds or RSS 1.0. Verify `feedparser` handles all three formats.
- [ ] **Prior job copying:** New fields added to model and supervisor, but the freshness TTL skip branch does not emit `"skipped"` events for new steps. Frontend shows new steps stuck at "pending" for cached analyses.
- [ ] **Pipeline timeout:** Individual steps have timeouts but total pipeline time is not monitored. Adding 3 steps that each take their maximum timeout (10s + 10s + 15s) adds 35 seconds worst case. Verify RQ `job_timeout` accommodates this.
- [ ] **RSS feed fetch:** Uses `_fetch_manager.fetch()` which falls back to Zyte for blocked sites. Verify Zyte credits are not burned on RSS feed fetches (feeds are rarely WAF-blocked; a direct `httpx.get()` is usually sufficient and cheaper).

## Sources

- [Common Crawl Index Server documentation](https://index.commoncrawl.org) -- HIGH confidence
- [Common Crawl FAQ: rate limiting and usage guidelines](https://commoncrawl.org/faq) -- HIGH confidence
- [Common Crawl blog: Oct/Nov 2023 performance issues](https://commoncrawl.org/blog/oct-nov-2023-performance-issues) -- HIGH confidence (describes 503 issues and rate limiting deployment)
- [Common Crawl community: Overloading index.commoncrawl.org](https://groups.google.com/g/common-crawl/c/3QmQjFA_3y4) -- MEDIUM confidence
- [Common Crawl community: 503 problem](https://groups.google.com/g/common-crawl/c/kEHzXZNu5To) -- MEDIUM confidence
- [Common Crawl CDXJ Index documentation](https://commoncrawl.org/cdxj-index) -- HIGH confidence
- [ikreymer/cdx-index-client (GitHub)](https://github.com/ikreymer/cdx-index-client) -- MEDIUM confidence
- [Google News inclusion FAQ (Publisher Center Community)](https://support.google.com/news/publisher-center/thread/71702189) -- MEDIUM confidence
- [Google: Answers to common questions about appearing in Google News](https://developers.google.com/search/blog/2021/07/google-news-top-questions) -- HIGH confidence
- [Google: Best practices for XML sitemaps and RSS/Atom feeds](https://developers.google.com/search/blog/2014/10/best-practices-for-xml-sitemaps-rssatom) -- HIGH confidence
- [sitemaps.org protocol specification](https://www.sitemaps.org/protocol.html) -- HIGH confidence
- [Skeptric: Searching 100 Billion Webpages with Capture Index](https://skeptric.com/searching-100b-pages-cdx/) -- MEDIUM confidence

---
*Pitfalls research for: Competitive intelligence features (Common Crawl, Google News, frequency estimation)*
*Researched: 2026-02-17*
