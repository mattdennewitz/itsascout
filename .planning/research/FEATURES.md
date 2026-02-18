# Feature Landscape: Competitive Intelligence Features

**Domain:** Publisher competitive intelligence (Common Crawl presence, Google News signals, update frequency)
**Researched:** 2026-02-17
**Confidence:** HIGH (CC CDX API verified against official docs; Google News approach uses existing pipeline data; update frequency patterns well-established)

## Context

**SUBSEQUENT MILESTONE** adding competitive intelligence signals to an existing scraping report card. The report card already analyzes WAF, ToS, robots.txt, AI bot blocking, sitemaps, RSS feeds, RSL, article metadata, paywall detection, and LLM metadata profiling.

**Key architectural insight:** All three features build primarily on data already discovered by existing pipeline steps. Common Crawl is the only feature requiring a new external API call. Google News detection reuses already-discovered sitemap URLs. Update frequency reuses already-discovered RSS feeds and sitemap URLs. This minimizes new HTTP requests and pipeline latency.

---

## Table Stakes

Features that are core to the "competitive context" value proposition. Without these, the milestone delivers no value.

| Feature | Why Expected | Complexity | Dependencies | Notes |
|---------|--------------|------------|--------------|-------|
| **CC presence (yes/no)** | Binary signal answering "Is this domain in the largest open web corpus?" | Low | None (external API call) | Single HTTP GET to CC CDX Index API |
| **CC estimated page count** | Quantifies how much of the publisher CC has crawled | Low | CC presence step | Derived from showNumPages response |
| **CC crawl ID + recency** | Context for when the CC data is from | Low | CC presence step | From collinfo.json or latest crawl ID |
| **News sitemap detection** | Core Google News optimization signal | Medium | Existing sitemap_result (URLs) | Fetch discovered sitemaps, check for xmlns:news namespace |
| **NewsArticle schema presence** | Indicates publisher uses news-specific structured data | Low | Existing article_result | Already detected by extruct; just needs surfacing and aggregation |
| **Update frequency classification** | Human-readable label (daily, weekly, etc.) | Medium | Existing rss_result (URLs) | feedparser + interval math on feed entries |
| **Frequency confidence indicator** | Users need to know if estimate is reliable | Low | Frequency step output | Based on sample size and date range span |

---

## Feature Deep Dives

### 1. Common Crawl Presence Check

**What it does:** Queries the CC CDX Index API to determine if the publisher's domain has been crawled and how extensively.

**What to show users:**

| Data Point | Source | Display |
|------------|--------|---------|
| Present in Common Crawl | `pages > 0` from API | Yes/No badge |
| Approximate page count | `pages * pageSize` | "~2,500 pages captured" |
| Latest crawl checked | Crawl ID | "CC-MAIN-2025-51" |
| Sample captured URLs | `limit=5` query | List of 3-5 example URLs |

**Implementation:** Single HTTP GET to `https://index.commoncrawl.org/{crawl_id}-index?url=*.{domain}&output=json&showNumPages=true`. If `pages > 0`, domain is present. Second query with `limit=5` gets sample captures.

**Complexity: Low.** One HTTP GET, JSON parse, minimal logic.

### 2. Google News Signals Detection

**What it does:** Detects whether a publisher has optimized for Google News by checking for news sitemaps, NewsArticle schema, and NewsMediaOrganization markup.

**Important framing:** This is "Google News readiness" NOT "Google News inclusion." Only Google knows actual inclusion status. We detect optimization signals.

**Detection signals (ordered by strength):**

1. **News sitemap** -- sitemap XML with `xmlns:news="http://www.google.com/schemas/sitemap-news/0.9"` namespace (strongest signal)
2. **NewsArticle schema** -- JSON-LD `@type: "NewsArticle"` on articles (already detected by existing article extraction)
3. **NewsMediaOrganization** -- publisher structured data type (already detected by existing publisher details step)
4. **Common news sitemap paths** -- probe `/news-sitemap.xml`, `/sitemap-news.xml` if not found in discovered sitemaps

**What to show users:**

| Data Point | Source | Display |
|------------|--------|---------|
| News sitemap found | Sitemap XML parse | Yes/No badge |
| News entry count | news:news element count | "42 articles in news sitemap" |
| NewsArticle schema | Existing article_result | "Uses NewsArticle structured data" |
| NewsMediaOrganization | Existing publisher_details | "Identifies as news organization" |
| Overall readiness | Composite | "Strong / Moderate / Minimal Google News signals" |

**Complexity: Medium.** Requires fetching and XML-parsing discovered sitemaps (not just discovering URLs). News namespace detection with lxml is straightforward.

### 3. Update Frequency Estimation

**What it does:** Estimates publishing frequency from RSS feed entry dates and optionally validates against sitemap lastmod timestamps.

**Two-source approach:**

| Source | Reliability | Why |
|--------|------------|-----|
| RSS `published` dates | HIGH | Set at article creation time; hard to fake; feedparser normalizes date formats |
| Sitemap `<lastmod>` dates | LOW-MEDIUM | Many CMS set all lastmod to same date; must validate before using |

**Frequency classifications:**

| Median Interval | Label |
|----------------|-------|
| < 1 hour | "Multiple per hour" |
| 1-24 hours | "Multiple per day" |
| 24-48 hours | "Daily" |
| 2-7 days | "Several per week" |
| 7-14 days | "Weekly" |
| 14-60 days | "Several per month" |
| 60+ days | "Monthly or less" |

**What to show users:**

| Data Point | Source | Display |
|------------|--------|---------|
| Frequency label | Computed | "Multiple per day" |
| Median interval | Computed | "~4.2 hours between articles" |
| Sample size | Entry count | "Based on 47 articles" |
| Date range | Min/max dates | "Feb 1 - Feb 17, 2026" |
| Data source | RSS vs sitemap | "Based on RSS feed analysis" |
| Reliability | Source quality + validation | "High confidence" or "Low confidence (sitemap timestamps may be unreliable)" |

**Complexity: Medium.** feedparser handles the hard date-parsing work. Interval calculation is straightforward stdlib statistics. Edge cases: feeds with no dates, feeds with <2 entries, sitemap lastmod validation.

---

## Differentiators

Features beyond the core three that add competitive depth.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **CCBot blocking correlation** | "Publisher blocks CCBot but IS in Common Crawl" is a meaningful insight | Low | Cross-reference existing ai_bot_result with new cc_result |
| **News sitemap entry samples** | Shows actual news articles in the sitemap | Low | Already parsed during news detection |
| **Lastmod reliability assessment** | Flags publishers with fake/auto-generated lastmod | Medium | Statistical validation of date distribution |
| **Frequency trend** | "Speeding up" vs "slowing down" publishing | Medium | Compare first-half vs second-half intervals |
| **Google News readiness score** | Single numeric score from all signals | Medium | Weighted composite of news sitemap + NewsArticle + NewsMediaOrg |
| **CC capture sample with timestamps** | Shows WHAT CC captured and WHEN | Low | Already returned by CDX API query |

---

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Full CC WARC content retrieval** | Massive data transfer (multi-GB per site); not useful for report card | Show capture metadata only (URL, status, timestamp) |
| **Google News RSS endpoint querying** | `news.google.com/rss/search?q=site:{domain}` is undocumented, could break anytime, and results vary by locale | Detect optimization signals from already-fetched data (sitemaps, schema) |
| **Historical CC trend across crawls** | Requires querying 12+ crawl indices per domain; rate limit risk | Query only latest crawl; note as single-point-in-time check |
| **Real-time feed monitoring** | Continuous polling is a different product | Snapshot frequency from latest feed content |
| **Sitemap completeness audit** | Requires full site crawl to compare sitemap vs actual URLs | Report sitemap presence and basic stats only |
| **Multi-locale Google News checking** | 50+ locales, expensive and slow | Default to detecting optimization signals (sitemaps/schema) which are locale-independent |
| **Paid API dependencies** | SerpApi, NewsAPI add per-request cost and vendor lock-in | Use free public endpoints (CC CDX API) and already-fetched data |

---

## Feature Dependencies

```
publisher.domain ──────────────────────> cc_presence_step (independent, external API)

sitemap_result (existing) ────────────> sitemap_analysis_step (fetch XML, check news NS, extract lastmod)

rss_result (existing) ────────────────> rss_frequency_step (fetch feed, parse dates with feedparser)

sitemap_analysis_step ─┐
rss_frequency_step ────┤──────────────> frequency_estimation_step (merge + classify)
                       │
sitemap_analysis_step ─┤
article_result ────────┤──────────────> google_news_signals_step (aggregate all signals)
publisher_details ─────┘

ai_bot_result + cc_result ────────────> ccbot_correlation (cross-reference, optional)
```

**Key insight:** CC presence check is fully independent. Google News and frequency both depend on fetching sitemap/RSS content (which builds on existing URL discovery). A shared sitemap cache within the pipeline run avoids duplicate fetches.

---

## MVP Recommendation

Build in this order:

1. **Common Crawl presence check** -- Independent, simplest, most reliable (public API with documented behavior), highest signal-to-noise. Start here.
2. **News sitemap detection + NewsArticle aggregation** -- Builds on existing sitemap discovery. News namespace check is the highest-value Google News signal.
3. **Update frequency from RSS feeds** -- Leverages already-discovered RSS feed URLs. feedparser handles date normalization. High user value for scraping planning.
4. **Google News signals aggregation** -- Combines news sitemap + NewsArticle + NewsMediaOrg into a readiness score. Low effort once components exist.

**Defer to next iteration:**
- Lastmod reliability validation (adds complexity to frequency step)
- Frequency trend analysis (requires more sophisticated stats)
- CCBot blocking correlation (low effort but lower priority)
- CC historical trends across crawls (rate limit risk)

---

## Report Card Integration

These signals appear as a new "Competitive Intelligence" section in the report card, visually grouped and separate from existing scraping feasibility signals.

```
[Competitive Intelligence]
  Common Crawl:      YES  ~2,500 pages  (CC-MAIN-2025-51)
  Google News:       Strong signals  (news sitemap + NewsArticle schema)
  Update Frequency:  Multiple per day (~4.2 hours between articles, based on RSS)
```

Each line follows the existing report card pattern: label, status badge (green/yellow/gray), detail text.

---

## Sources

- [Common Crawl CDX Index API](https://index.commoncrawl.org) -- HIGH confidence, verified API behavior
- [Common Crawl FAQ](https://commoncrawl.org/faq) -- rate limiting guidance
- [Google News Sitemap Documentation](https://developers.google.com/search/docs/crawling-indexing/sitemaps/news-sitemap) -- official spec
- [Google News Schema (xmlns:news/0.9)](https://www.google.com/schemas/sitemap-news/0.9/) -- namespace definition
- [Google Article Structured Data](https://developers.google.com/search/docs/appearance/structured-data/article) -- NewsArticle requirements
- [feedparser PyPI](https://pypi.org/project/feedparser/) -- v6.0.12, Sep 2025
- [Bing lastmod Importance](https://blogs.bing.com/webmaster/february-2023/The-Importance-of-Setting-the-lastmod-Tag-in-Your-Sitemap) -- lastmod reliability caveats
- [Sitemaps.org Protocol](https://www.sitemaps.org/protocol.html) -- lastmod format specification
