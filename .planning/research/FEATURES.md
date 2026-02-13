# Feature Landscape: Single-URL Analysis Workflow

**Domain:** Scraping feasibility assessment tool with streaming report card
**Researched:** 2026-02-13
**Confidence:** MEDIUM-HIGH (patterns verified across multiple real-world tools; RSL spec verified against official standard)

## Context

This is a **NEW FEATURE MILESTONE** building on an existing Django-Inertia app. The existing app already handles bulk publisher ingestion, WAF detection (wafw00f), ToS discovery/evaluation (pydantic-ai), HTML fetching (Zyte proxy), interactive data table (TanStack), and async task pipeline (django-tasks). This research focuses ONLY on what the single-URL analysis workflow, streaming progress UX, report card presentation, and metadata profiling need.

**Existing pipeline steps:** URL normalization, get-or-create publisher, WAF scan, terms discovery, terms evaluation.

**New capability:** User pastes a single URL, watches analysis happen in real time, gets a comprehensive "report card" for scraping feasibility, with both publisher-level (durable) and article-level (URL-specific) data.

---

## Table Stakes

Features users expect from a URL analysis / website assessment tool. Missing = product feels broken or incomplete.

| Feature | Why Expected | Complexity | Dependencies | Notes |
|---------|--------------|------------|--------------|-------|
| **Single URL input with "Analyze" action** | Core interaction pattern. Every tool from BuiltWith to Lighthouse starts here. Users paste a URL, press a button, get results. | Low | Existing Inertia form infrastructure (`useForm`) | Big input field, prominent button, URL validation on paste. Placeholder text like "https://example.com/article" |
| **Real-time progress indication** | Users waiting 15-60s for pipeline completion need feedback. Blank screen = perceived failure. Tools like Lighthouse, SecurityHeaders show progress. | High | SSE endpoint, Django async view or django-tasks integration | Stepwise: "Checking WAF..." -> "Discovering ToS..." -> "Evaluating permissions..." Each step shows status (pending/running/complete/error) |
| **WAF detection display** | Already exists in pipeline. Users need to know if a WAF will block their scraper. | Low | Existing `WAFReport` model, wafw00f | Display: firewall name, manufacturer, detected boolean. Color-coded: green (none), yellow (detected but permissive), red (aggressive WAF like Cloudflare Bot Management) |
| **ToS permissions display** | Already exists in pipeline. Core value: "Am I legally allowed to scrape this site?" | Low | Existing `TermsEvaluationResult` model | Display existing permissions array with activity/permission/notes. Traffic light per activity: green (explicitly_permitted), red (explicitly_prohibited), yellow (conditional_ambiguous) |
| **Overall scraping feasibility score/grade** | SecurityHeaders uses A+ to F. Lighthouse uses 0-100. Users expect a single at-a-glance indicator. This is the "report card" concept. | Medium | Computed from WAF, ToS, robots.txt, RSL findings | Letter grade (A-F) or traffic light (green/yellow/red) with a short label: "Favorable", "Proceed with Caution", "Hostile" |
| **Publisher-level data persistence** | Analysis of a publisher (WAF, ToS, robots.txt) should be cached and reused. Re-analyzing nytimes.com should not repeat expensive LLM calls if data is fresh. | Medium | Existing Publisher model + staleness check | TTL-based: publisher data valid for 7-30 days. Show "Last analyzed: 3 days ago" with manual re-analyze option |
| **robots.txt analysis** | First thing any scraping guide checks. "Does this site block scrapers via robots.txt?" | Medium | New: fetch and parse robots.txt, new model | Show: disallowed paths relevant to scraping, crawl-delay directives, sitemap references. Red/green per directive. Inspired by SE Ranking's robots.txt tester: highlight specific rules that match |
| **Link to publisher detail from data table** | Users browsing the table need to drill into individual publisher reports | Low | Inertia navigation, existing table | Add "View Report" link/action per row |

---

## Differentiators

Features that set this tool apart from generic SEO analyzers. Not expected by default, but provide real value for scraping feasibility assessment specifically.

| Feature | Value Proposition | Complexity | Dependencies | Notes |
|---------|-------------------|------------|--------------|-------|
| **RSL (Really Simple Licensing) detection** | RSL is the emerging standard (1.0 spec finalized Dec 2025, 1500+ publishers). No mainstream tool surfaces this yet. Detects machine-readable licensing terms for AI/scraping. | Medium | Fetch /.well-known/rsl.xml or check robots.txt/HTTP headers for RSL references, parse XML | Display: licensing model (free, attribution, pay-per-crawl, subscription), allowed activities, compensation terms. This is genuinely novel -- most scraping tools do not check RSL. |
| **RSS/Atom feed discovery** | RSS presence signals: structured content access, pagination-free article discovery, publication frequency. Huge value for monitoring use cases. | Low | Check common paths (/feed, /rss, /atom.xml), parse HTML `<link rel="alternate" type="application/rss+xml">` | Display: feed URL, feed type (RSS/Atom), item count if parseable. Value framing: "This site publishes an RSS feed with ~50 recent articles -- you can monitor new content without scraping." |
| **Sitemap discovery and summary** | Sitemaps = scraping goldmine. "50,000 URLs in sitemap" tells user they can enumerate content without crawling. | Low-Medium | Parse robots.txt Sitemap directives, fetch /sitemap.xml, parse XML index | Display: sitemap URL, total URL count, last modified dates, whether it's an index (nested sitemaps). Value framing: "Sitemap contains 12,847 article URLs -- direct enumeration possible." |
| **Article metadata profiling** | URL-specific: "What can I actually extract from this specific page?" Show what structured data is available before building a scraper. | High | Fetch article HTML (Zyte API), extract with trafilatura or newspaper4k, parse JSON-LD/OpenGraph/meta tags | Display: title, author(s), publish date, description, main image, canonical URL, language, paywall indicators. Show "available" vs "missing" per field. See Metadata Attributes section below. |
| **Streaming progressive reveal** | Rather than a loading spinner then full results, each pipeline section appears as it completes. Creates engagement during the 15-60s wait. Inspired by LLM streaming UX. | High | SSE from Django, React state management for incremental section rendering | Sections animate in: WAF card -> robots.txt card -> ToS card -> RSL card -> RSS/sitemap card -> metadata card. Each with its own pending/complete state. |
| **Paywall detection** | Critical for scraping feasibility. Uses `isAccessibleForFree` schema.org markup, meta tags, and content truncation signals. | Medium | Article HTML fetch (Zyte API), JSON-LD parsing, heuristic detection | Display: "Paywall detected" / "Free access" / "Metered (soft paywall)". Check `isAccessibleForFree` property in JSON-LD, look for paywall CSS selectors, detect truncated content patterns. |
| **Structured data inventory** | Show what JSON-LD, OpenGraph, and meta tag schemas the page uses. Tells scrapers exactly what machine-readable data is already available. | Medium | HTML parsing of `<script type="application/ld+json">`, OpenGraph meta tags, Twitter cards | Display: list of schema.org types found (Article, NewsArticle, Product, etc.), OpenGraph tags present, Twitter card type. Value framing: "This page provides NewsArticle JSON-LD -- structured extraction available without HTML parsing." |
| **Re-analyze with freshness indicator** | Show when each data point was last fetched. Allow selective re-analysis (e.g., "re-check robots.txt only"). | Medium | Timestamps per analysis component, selective task dispatch | Display: "WAF: checked 3 days ago" with refresh button per section. Avoids unnecessary API costs. |

---

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Automated scraper generation** | Scope creep. This is an assessment tool, not a scraper builder. Building scrapers is a fundamentally different product. | Show what data is available and how accessible it is. Let users decide how to scrape. |
| **Content extraction / full article display** | Legal risk. Displaying scraped article content creates copyright liability. Assessment is safe; reproduction is not. | Show metadata and field availability ("title: present, author: present") without displaying actual content. Exception: show title and first ~100 chars for identification only. |
| **Bulk URL analysis from this UI** | Already exists via CSV bulk upload. Single-URL flow should be focused on depth, not breadth. Adding bulk here creates UX confusion. | Keep existing bulk upload flow separate. Single-URL is for deep analysis of one target. |
| **Historical trend tracking** | Over-engineering for initial milestone. "WAF changed from Cloudflare to Akamai" is interesting but not core value. | Store latest results with timestamps. History can be added later if there is demand. |
| **Competitor comparison** | "Compare nytimes.com vs washingtonpost.com" is a different product. Adds complexity without core value. | One URL at a time. Users can analyze multiple URLs and compare manually via the data table. |
| **Bypass/evasion recommendations** | Ethical and legal minefield. "Here's how to bypass their WAF" is not what this tool should do. | Report what protections exist factually. Let users make their own decisions about approach. |
| **Browser rendering / JavaScript execution analysis** | Massively increases complexity (need headless browser). Zyte handles this transparently. | Note if Zyte API was needed (implies JS rendering required) but do not build a separate JS analysis pipeline. |
| **Per-article caching** | Articles are ephemeral. Caching metadata for a specific article URL adds storage complexity with little reuse value. | Fetch fresh each time for article-level data. Cache only publisher-level data (WAF, ToS, robots.txt, RSL, RSS/sitemap). |

---

## Feature Dependencies

```
Existing: Publisher model + WAF pipeline + ToS pipeline
    |
    v
Single URL input form (table stakes, foundation)
    |
    v
SSE streaming endpoint (enables all progressive reveal)
    |
    +---> WAF display card (existing data, new presentation)
    |
    +---> robots.txt analysis (NEW: fetch + parse + model)
    |         |
    |         +---> Sitemap discovery (reads Sitemap directives from robots.txt)
    |
    +---> ToS display card (existing data, new presentation)
    |
    +---> RSL detection (NEW: fetch + parse + model)
    |
    +---> RSS/Atom feed discovery (NEW: HTML link tag parsing + model)
    |
    +---> Article metadata profiling (NEW: HTML fetch + extraction + display)
    |         |
    |         +---> Paywall detection (part of metadata extraction)
    |         |
    |         +---> Structured data inventory (part of metadata extraction)
    |
    v
Overall feasibility grade (computed from all above)
    |
    v
Publisher report card page (renders all sections)
    |
    v
Re-analyze with freshness (requires timestamps on all models)
```

**Critical path:** SSE streaming endpoint must work before any progressive reveal is possible. This is the technical foundation that everything else builds on.

**Independence:** robots.txt, RSL, and RSS discovery are independent of each other and can be built in any order. Article metadata profiling is independent of publisher-level checks.

**Existing dependencies:** WAF and ToS display cards reuse existing models and pipeline steps. No new backend work needed for these -- just new frontend presentation.

---

## Metadata Attributes: What to Surface

Based on research into trafilatura, newspaper4k, Zyte API article extraction, and schema.org structured data, here are the metadata attributes prioritized by value for scraping feasibility assessment.

### Tier 1: Always Show (Core identification and feasibility)

| Attribute | Source(s) | Why It Matters | Display |
|-----------|-----------|----------------|---------|
| **Title** | `<title>`, `og:title`, JSON-LD `headline`, `<h1>` | Confirms correct page identified, shows extraction quality | Text value |
| **Author(s)** | `<meta name="author">`, JSON-LD `author`, byline extraction | Author presence signals structured content; absence signals scraping difficulty | Names or "Not found" |
| **Publish date** | JSON-LD `datePublished`, `<meta>` tags, `<time>` elements | Date extraction reliability is critical for content monitoring | Formatted date or "Not found" |
| **Paywall status** | `isAccessibleForFree` in JSON-LD, paywall CSS class detection, content truncation | Determines if content is actually accessible | "Free" / "Paywalled" / "Metered" / "Unknown" |
| **Language** | `<html lang>`, JSON-LD `inLanguage`, `<meta http-equiv="content-language">` | Affects extraction library choice and processing pipeline | ISO 639-1 code |
| **Canonical URL** | `<link rel="canonical">`, JSON-LD `url` | Deduplication signal; shows if URL is authoritative | URL or "Not specified" |

### Tier 2: Show When Available (Enrichment)

| Attribute | Source(s) | Why It Matters | Display |
|-----------|-----------|----------------|---------|
| **Main image** | `og:image`, JSON-LD `image`, first content image | Image availability for content aggregation use cases | Thumbnail preview |
| **Description/summary** | `<meta name="description">`, `og:description`, JSON-LD `description` | Pre-built summary availability saves extraction effort | Truncated text |
| **Schema.org type** | JSON-LD `@type` | "NewsArticle" vs "Product" vs "Recipe" tells scraper what extraction model to use | Type label |
| **Word count** | Computed from article body extraction | Content depth indicator | Number |
| **Content sections** | Heading structure (H1-H3 outline) | Structural complexity indicator for extraction | Count or outline |

### Tier 3: Show in Expanded/Detail View (Advanced)

| Attribute | Source(s) | Why It Matters | Display |
|-----------|-----------|----------------|---------|
| **OpenGraph tags inventory** | All `og:*` meta tags | Social sharing metadata = structured data already available | Tag list with values |
| **Twitter Card type** | `twitter:card`, `twitter:*` tags | Additional structured metadata source | Card type |
| **JSON-LD raw types** | All `<script type="application/ld+json">` blocks | Full schema.org coverage view | Type list |
| **Favicon** | `<link rel="icon">` | Publisher branding for display purposes | Icon preview |
| **RSS autodiscovery link** | `<link rel="alternate" type="application/rss+xml">` | Cross-reference with RSS discovery feature | URL |
| **AMP version** | `<link rel="amphtml">` | AMP pages often have cleaner structure for extraction | URL or "Not available" |

---

## UX Patterns: Research-Backed Recommendations

### 1. Single URL Input Pattern

**Inspired by:** SecurityHeaders.com, BuiltWith, Google Lighthouse, HubSpot Website Grader

**Pattern:** Large, centered input field with prominent action button. This is the hero interaction.

- Input field should accommodate full URLs (minimum 50+ characters visible)
- Placeholder text: "Paste any URL to analyze..."
- "Analyze" button to the right (convention for LTR interfaces)
- URL validation on paste/blur (is it a valid URL? Does it have a scheme?)
- Auto-prepend `https://` if scheme missing
- Show the publisher name/domain below the input after submission ("Analyzing: nytimes.com")
- If publisher already exists in database, show "Previously analyzed 3 days ago -- checking for updates" vs "New publisher -- running full analysis"

**Complexity:** Low. Existing `useForm` and `FormField` components handle this.

### 2. Streaming Progress UX Pattern

**Inspired by:** LLM token streaming (ChatGPT), CI/CD pipeline views (GitHub Actions), Lighthouse audit progress

**Pattern:** Stepwise checklist with status indicators that update in real time via SSE.

The pipeline has 6-8 steps. Display as a vertical checklist:

```
[completed]  WAF Detection          Cloudflare detected
[running]    robots.txt Analysis    Fetching...
[pending]    Terms of Service       Waiting...
[pending]    RSL Licensing          Waiting...
[pending]    RSS/Sitemap Discovery  Waiting...
[pending]    Article Metadata       Waiting...
```

Each step transitions: pending (gray) -> running (blue, with spinner) -> complete (green checkmark) -> error (red X with message).

**Key UX decisions:**
- Show estimated time remaining if possible ("~15 seconds remaining")
- Allow user to see partial results as they complete (progressive reveal)
- Do NOT block the entire UI on any single step failure -- show error for that step, continue others
- Independent steps (robots.txt, RSL, RSS) can run in parallel -- show them updating simultaneously

**Complexity:** High. Requires SSE endpoint, event schema, React state management for partial updates.

### 3. Report Card Presentation Pattern

**Inspired by:** SecurityHeaders (letter grades per category), Google Lighthouse (category scores with details), UpCity SEO Report Card (section grades)

**Pattern:** Card-based layout with section grades that expand into detail.

**Overall grade** at top: large, color-coded letter (A-F) or traffic light with label.

Grade computation (suggested weights):
- ToS permissions: 30% (legal risk is highest concern)
- WAF presence: 20% (technical barrier)
- robots.txt openness: 20% (explicit crawling policy)
- RSL licensing: 15% (emerging standard compliance)
- Metadata richness: 10% (extraction ease)
- RSS/Sitemap presence: 5% (content discovery ease)

Below the grade: individual section cards, each with:
- Section icon + title
- Mini-grade or status indicator (checkmark/warning/X)
- 1-line summary
- Expandable detail view

**Complexity:** Medium. Computation logic is straightforward; card layout uses existing Tailwind patterns.

### 4. robots.txt Analysis Presentation

**Inspired by:** SE Ranking Robots.txt Tester, TechnicalSEO.com validator, Google Search Console robots.txt report

**Pattern:** Rule-by-rule display with color-coded allow/disallow indicators.

- Show User-Agent groups separately (Googlebot, *, specific bot names)
- Highlight rules relevant to scrapers (User-agent: *, crawl-delay)
- Red for Disallow rules affecting common scraping paths (/api/, /search/, etc.)
- Green for Allow rules
- Yellow for Crawl-delay directives (with the delay value)
- Call out Sitemap directives separately (feeds into sitemap discovery)
- If no robots.txt exists: green indicator "No robots.txt found -- no crawling restrictions declared"

**Complexity:** Medium. Parsing is well-understood; presentation is straightforward.

### 5. RSL Licensing Presentation

**Inspired by:** Creative Commons license badges, software license indicators (GitHub repo license display)

**Pattern:** License badge + terms summary. Novel UX since no mainstream tool does this yet.

- Badge-style indicator: "RSL: Free", "RSL: Attribution Required", "RSL: Pay-per-Crawl", "RSL: Not Found"
- If RSL found: show allowed activities, compensation model, contact/negotiation URL
- If RSL not found: neutral indicator "No RSL licensing detected -- check ToS for scraping policy"
- Link to the actual RSL document for verification

**Complexity:** Medium. XML parsing of RSL spec, but the display is simple.

### 6. RSS/Sitemap Discovery Presentation

**Inspired by:** Wappalyzer technology detection (categorized results), BuiltWith (technology inventory)

**Pattern:** Discovery inventory with value assessment.

RSS section:
- Feed URL (clickable)
- Feed type (RSS 2.0, Atom)
- Item count ("~50 recent articles")
- Update frequency if detectable
- Value note: "RSS feed available -- content monitoring possible without scraping"

Sitemap section:
- Sitemap URL(s)
- Type (sitemap index vs single sitemap)
- Total URL count
- Last modified date range
- Value note: "12,847 URLs in sitemap -- direct enumeration available"

**Complexity:** Low-Medium. Standard HTTP fetches and XML parsing.

---

## MVP Recommendation

### Must Build (enables the core workflow):
1. **Single URL input form** -- the entry point for everything
2. **SSE streaming endpoint** -- technical foundation for progressive reveal
3. **Progress checklist UI** -- real-time feedback during analysis
4. **WAF display card** -- reuses existing data, new presentation only
5. **ToS display card** -- reuses existing data, new presentation only
6. **robots.txt analysis** -- new pipeline step, high value, moderate complexity
7. **Overall feasibility grade** -- the "report card" payoff
8. **Publisher report card page** -- the results destination

### Should Build (high value, can be phased):
9. **Article metadata profiling** -- the URL-specific differentiator
10. **RSS/Sitemap discovery** -- low complexity, high value
11. **Publisher data freshness/caching** -- prevents redundant API costs
12. **Paywall detection** -- part of metadata profiling

### Defer (valuable but not blocking):
13. **RSL detection** -- novel but RSL adoption is still early (check back in 6 months for broader adoption)
14. **Structured data inventory** -- detailed view, not core assessment
15. **Re-analyze selective sections** -- polish feature
16. **Estimated time remaining** -- nice UX but hard to predict accurately

**Reasoning:** The core workflow is "paste URL -> see progress -> get grade." Everything else enriches that loop. robots.txt is the highest-value new pipeline step because it is the most universally present crawling policy signal. Article metadata comes next because it answers "what can I extract?" at the URL level. RSS/sitemap is cheap to add and genuinely useful.

---

## Sources

**HIGH Confidence (Official Documentation, Verified Standards):**
- [RSL 1.0 Specification](https://rslstandard.org/rsl) -- Really Simple Licensing standard
- [RSL File Format Guide](https://rslstandard.org/guide/file-format) -- XML format details
- [Google Structured Data for Paywalled Content](https://developers.google.com/search/docs/appearance/structured-data/paywalled-content) -- isAccessibleForFree markup
- [Zyte API Article Extraction](https://docs.zyte.com/zyte-api/usage/extract/index.html) -- headline, datePublished, author, inLanguage, mainImage fields
- [Lighthouse Performance Scoring](https://developer.chrome.com/docs/lighthouse/performance/performance-scoring) -- 0-100 scoring methodology

**MEDIUM Confidence (Multiple Sources Agree, Verified Patterns):**
- [SecurityHeaders.com](https://securityheaders.com/) -- A+ to F grading UX pattern
- [SE Ranking Robots.txt Tester](https://seranking.com/free-tools/robots-txt-tester.html) -- robots.txt analysis UI pattern
- [Zyte Compliant Web Scraping Checklist](https://www.zyte.com/learn/compliant-web-scraping-checklist/) -- assessment checklist methodology
- [Zyte Solution Architecture: Technical Feasibility](https://www.zyte.com/blog/solution-architecture-part-4-accessing-the-technical-feasibility-of-your-web-scraping-project/) -- feasibility assessment framework
- [Trafilatura Metadata Module](https://trafilatura.readthedocs.io/en/latest/_modules/trafilatura/metadata.html) -- metadata extraction fields
- [Newspaper4k](https://github.com/AndyTheFactory/newspaper4k) -- article metadata extraction (active fork of newspaper3k)
- [SSE Progress Bar with Spring and React](https://code-specialist.com/sse-in-action) -- SSE streaming progress pattern
- [Smashing Magazine: UX Strategies for Real-Time Dashboards](https://www.smashingmagazine.com/2025/09/ux-strategies-real-time-dashboards/) -- real-time UX patterns
- [Progressive Disclosure - Nielsen Norman Group](https://www.nngroup.com/articles/progressive-disclosure/) -- progressive reveal UX theory

**LOW Confidence (Single Source, Needs Validation):**
- [Rapidseedbox Robots.txt Analyzer](https://www.rapidseedbox.com/blog/robots-txt-analyzer) -- risk assessment approach
- Grade computation weights (author's recommendation based on domain analysis, not established standard)

---

**Research Date:** 2026-02-13
**Overall Confidence:** MEDIUM-HIGH (UX patterns verified across multiple real tools; metadata fields verified against official docs; RSL spec verified against published standard; grade computation is opinionated recommendation requiring validation)
