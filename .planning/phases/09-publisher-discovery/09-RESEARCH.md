# Phase 9: Publisher Discovery - Research

**Researched:** 2026-02-14
**Domain:** robots.txt parsing, sitemap discovery, RSS/Atom feed detection, RSL (Really Simple Licensing) detection
**Confidence:** HIGH

## Summary

Phase 9 adds four new pipeline steps to the existing supervisor: robots.txt fetching/parsing, sitemap URL discovery, RSS/Atom feed discovery, and RSL licensing detection. The codebase is fully prepared -- the `ResolutionJob` model already has dedicated JSON fields for each step (`robots_result`, `sitemap_result`, `rss_result`, `rsl_result`), and the `Publisher` model already has corresponding flat fields (`robots_txt_found`, `robots_txt_url_allowed`, `sitemap_urls`, `rss_urls`, `rsl_detected`). The pipeline supervisor pattern is established in Phase 8: each step function lives in `steps.py`, saves its result to the ResolutionJob, publishes an SSE event, and updates Publisher flat fields.

The robots.txt step uses **protego** (v0.6.0, the Scrapy project's parser) to parse robots.txt content and check URL allowance. Protego also extracts `Sitemap:` directives, which feeds directly into sitemap discovery. For RSS/Atom feed discovery, we parse HTML `<link rel="alternate">` tags from the publisher's homepage HTML (already fetched or fetchable via `FetchStrategyManager`). RSL detection checks three locations: `License:` directives in robots.txt, `<link rel="license" type="application/rsl+xml">` tags in HTML, and `Link:` HTTP response headers with `rel="license"`. No heavy dependencies are needed beyond protego -- HTML parsing uses Python's built-in `html.parser` (or the lightweight `re`-based approach for targeted link tag extraction).

**Primary recommendation:** Add protego as the sole new dependency. Implement four new step functions in `steps.py` following the exact same pattern as existing steps. The robots.txt and sitemap steps share a fetch (robots.txt is fetched once, parsed for both URL rules and sitemap directives). RSS and RSL detection both operate on the publisher homepage HTML. Structure the supervisor to run these steps after the existing ToS evaluation step.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| protego | 0.6.0 | robots.txt parsing (rules, sitemaps, crawl-delay) | Scrapy's official parser; supports wildcards, length-based ordering, Sitemap directives; 350K+ weekly downloads |
| html.parser (stdlib) | Built-in | Parse HTML for `<link>` tags (RSS, RSL) | No extra dependency; sufficient for targeted tag extraction |
| requests (already installed) | 2.32.4 | Fetch robots.txt (plain text, no WAF concerns) | robots.txt is a plain text file at a well-known path; no browser impersonation needed |
| FetchStrategyManager (existing) | N/A | Fetch publisher homepage HTML for RSS/RSL detection | Already built in Phase 7; handles WAF bypass with curl-cffi/Zyte fallback |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| urllib.parse (stdlib) | Built-in | URL joining for relative sitemap/RSS paths | Resolving relative hrefs against publisher base URL |
| re (stdlib) | Built-in | Regex extraction of `License:` from robots.txt raw text | Protego does not parse non-standard directives like `License:` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| protego | urllib.robotparser (stdlib) | stdlib but lacks wildcard support, no Sitemap extraction, no crawl-delay parsing |
| protego | reppy (seomoz) | Faster (C extension) but less maintained, heavier install |
| html.parser | BeautifulSoup4 | More ergonomic API but adds a dependency; overkill for extracting 2-3 specific link tags |
| html.parser | lxml | Fastest HTML parser but C dependency; not needed for simple link tag extraction |
| requests for robots.txt | FetchStrategyManager | FetchStrategyManager adds WAF bypass overhead unnecessary for robots.txt (plain text file served without WAF protection) |
| Manual RSS detection | feedfinder2 / feedsearch | Extra dependencies for a simple task; we only need `<link rel="alternate">` tags, not deep crawling |

**Installation:**
```bash
uv add protego
```

## Architecture Patterns

### Recommended Project Structure
```
scrapegrape/publishers/pipeline/
    __init__.py          # (existing) exports run_pipeline
    supervisor.py        # (MODIFY) add 4 new steps after tos_evaluation
    steps.py             # (MODIFY) add 4 new step functions
    events.py            # (existing) no changes needed
```

No new files needed. All new code goes into existing `steps.py` and `supervisor.py`.

### Pattern 1: robots.txt Fetch and Parse
**What:** Fetch robots.txt using plain `requests.get()`, parse with protego, check URL allowance.
**When to use:** First of the new discovery steps; runs after ToS evaluation.
**Example:**
```python
# In steps.py
import requests
from protego import Protego
from urllib.parse import urljoin

ITSASCOUT_USER_AGENT = "itsascout"

def run_robots_step(publisher, submitted_url: str) -> dict:
    """Fetch and parse robots.txt, check if submitted URL is allowed."""
    robots_url = urljoin(f"https://{publisher.domain}/", "/robots.txt")
    try:
        response = requests.get(robots_url, timeout=15,
                                headers={"User-Agent": ITSASCOUT_USER_AGENT})
        if response.status_code != 200:
            return {"robots_found": False, "status_code": response.status_code}

        rp = Protego.parse(response.text)
        url_allowed = rp.can_fetch(submitted_url, ITSASCOUT_USER_AGENT)
        sitemaps = list(rp.sitemaps)
        crawl_delay = rp.crawl_delay(ITSASCOUT_USER_AGENT)

        # Extract RSL License directives from raw text (protego ignores them)
        license_urls = _extract_license_directives(response.text)

        return {
            "robots_found": True,
            "url_allowed": url_allowed,
            "sitemaps_from_robots": sitemaps,
            "crawl_delay": crawl_delay,
            "license_directives": license_urls,
            "raw_length": len(response.text),
        }
    except requests.RequestException as exc:
        return {"robots_found": False, "error": str(exc)}


def _extract_license_directives(robots_text: str) -> list[str]:
    """Extract License: directives from robots.txt (RSL standard)."""
    import re
    return re.findall(r'^License:\s*(.+)$', robots_text, re.MULTILINE | re.IGNORECASE)
```
Source: [protego GitHub](https://github.com/scrapy/protego), [RSL robots.txt guide](https://rslstandard.org/guide/robots-txt)

### Pattern 2: Sitemap Discovery (Combined with robots.txt)
**What:** Combine sitemaps found in robots.txt with common fallback paths.
**When to use:** Immediately after robots.txt parsing (uses its output).
**Example:**
```python
COMMON_SITEMAP_PATHS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap/sitemap.xml",
    "/wp-sitemap.xml",
]

def run_sitemap_step(publisher, robots_result: dict) -> dict:
    """Discover sitemap URLs from robots.txt directives and common paths."""
    found_sitemaps = set(robots_result.get("sitemaps_from_robots", []))

    # Probe common paths if robots.txt had none
    if not found_sitemaps:
        for path in COMMON_SITEMAP_PATHS:
            sitemap_url = f"https://{publisher.domain}{path}"
            try:
                resp = requests.head(sitemap_url, timeout=10, allow_redirects=True)
                if resp.status_code == 200 and "xml" in resp.headers.get("content-type", ""):
                    found_sitemaps.add(sitemap_url)
                    break  # One valid sitemap is sufficient
            except requests.RequestException:
                continue

    return {
        "sitemap_urls": sorted(found_sitemaps),
        "source": "robots.txt" if robots_result.get("sitemaps_from_robots") else "probe",
        "count": len(found_sitemaps),
    }
```
Source: [sitemaps.org protocol](https://www.sitemaps.org/protocol.html)

### Pattern 3: RSS/Atom Feed Discovery from HTML
**What:** Parse homepage HTML for `<link rel="alternate">` tags with RSS/Atom MIME types.
**When to use:** As a pipeline step; uses publisher homepage HTML.
**Example:**
```python
from html.parser import HTMLParser

RSS_MIME_TYPES = {
    "application/rss+xml",
    "application/atom+xml",
    "application/xml",
    "text/xml",
}

class FeedLinkParser(HTMLParser):
    """Extract RSS/Atom feed links from HTML <link> tags."""
    def __init__(self):
        super().__init__()
        self.feeds = []

    def handle_starttag(self, tag, attrs):
        if tag != "link":
            return
        attr_dict = dict(attrs)
        rel = attr_dict.get("rel", "")
        link_type = attr_dict.get("type", "")
        href = attr_dict.get("href", "")
        if "alternate" in rel and link_type in RSS_MIME_TYPES and href:
            self.feeds.append({
                "url": href,
                "type": link_type,
                "title": attr_dict.get("title", ""),
            })

def run_rss_step(publisher, homepage_html: str) -> dict:
    """Discover RSS/Atom feed URLs from HTML link tags."""
    parser = FeedLinkParser()
    try:
        parser.feed(homepage_html)
    except Exception:
        pass  # HTMLParser is lenient

    # Resolve relative URLs
    from urllib.parse import urljoin
    base_url = f"https://{publisher.domain}/"
    for feed in parser.feeds:
        if not feed["url"].startswith("http"):
            feed["url"] = urljoin(base_url, feed["url"])

    return {
        "feeds": parser.feeds,
        "count": len(parser.feeds),
    }
```
Source: [RSS autodiscovery via link tags](https://alexmiller.phd/posts/python-3-feedfinder-rss-detection-from-url/)

### Pattern 4: RSL Detection (Multi-Source)
**What:** Check three locations for RSL indicators: robots.txt `License:` directives, HTML `<link rel="license">` tags, and HTTP `Link` headers.
**When to use:** As a pipeline step; aggregates signals from robots.txt result and homepage HTML/headers.
**Example:**
```python
class RSLLinkParser(HTMLParser):
    """Extract RSL license links from HTML."""
    def __init__(self):
        super().__init__()
        self.rsl_links = []

    def handle_starttag(self, tag, attrs):
        if tag != "link":
            return
        attr_dict = dict(attrs)
        rel = attr_dict.get("rel", "")
        link_type = attr_dict.get("type", "")
        href = attr_dict.get("href", "")
        if "license" in rel and "application/rsl+xml" in link_type and href:
            self.rsl_links.append(href)

    def handle_startendtag(self, tag, attrs):
        # Self-closing <link ... /> tags
        self.handle_starttag(tag, attrs)

def run_rsl_step(publisher, robots_result: dict, homepage_html: str,
                 homepage_headers: dict | None = None) -> dict:
    """Detect RSL licensing indicators from multiple sources."""
    indicators = []

    # Source 1: robots.txt License: directives
    license_directives = robots_result.get("license_directives", [])
    for url in license_directives:
        indicators.append({"source": "robots.txt", "url": url.strip()})

    # Source 2: HTML <link rel="license" type="application/rsl+xml">
    parser = RSLLinkParser()
    try:
        parser.feed(homepage_html)
    except Exception:
        pass
    for url in parser.rsl_links:
        indicators.append({"source": "html_link", "url": url})

    # Source 3: HTTP Link header
    if homepage_headers:
        link_header = homepage_headers.get("link", "")
        if 'rel="license"' in link_header and "application/rsl+xml" in link_header:
            # Parse Link header value
            import re
            match = re.search(r'<([^>]+)>', link_header)
            if match:
                indicators.append({"source": "http_header", "url": match.group(1)})

    return {
        "rsl_detected": len(indicators) > 0,
        "indicators": indicators,
        "count": len(indicators),
    }
```
Source: [RSL 1.0 Specification](https://rslstandard.org/rsl), [RSL robots.txt guide](https://rslstandard.org/guide/robots-txt)

### Pattern 5: Supervisor Integration
**What:** Add the four new steps to the existing pipeline supervisor, after ToS evaluation.
**When to use:** Modifying supervisor.py.
**Example:**
```python
# In supervisor.py -- after the tos_evaluation block, before freshness update:

# Step 4: robots.txt + URL allowance
publish_step_event(job_id, "robots", "started")
robots_result = run_robots_step(publisher, resolution_job.canonical_url)
resolution_job.robots_result = robots_result
resolution_job.save(update_fields=["robots_result"])
publish_step_event(job_id, "robots", "completed", robots_result)

# Update publisher flat fields
publisher.robots_txt_found = robots_result.get("robots_found", False)
publisher.robots_txt_url_allowed = robots_result.get("url_allowed")
publisher.save(update_fields=["robots_txt_found", "robots_txt_url_allowed"])

# Step 5: Sitemap discovery
publish_step_event(job_id, "sitemap", "started")
sitemap_result = run_sitemap_step(publisher, robots_result)
resolution_job.sitemap_result = sitemap_result
resolution_job.save(update_fields=["sitemap_result"])
publish_step_event(job_id, "sitemap", "completed", sitemap_result)

publisher.sitemap_urls = sitemap_result.get("sitemap_urls", [])
publisher.save(update_fields=["sitemap_urls"])

# Step 6: RSS feed discovery (needs homepage HTML)
publish_step_event(job_id, "rss", "started")
homepage_html = _fetch_homepage_html(publisher)
rss_result = run_rss_step(publisher, homepage_html)
resolution_job.rss_result = rss_result
resolution_job.save(update_fields=["rss_result"])
publish_step_event(job_id, "rss", "completed", rss_result)

publisher.rss_urls = [f["url"] for f in rss_result.get("feeds", [])]
publisher.save(update_fields=["rss_urls"])

# Step 7: RSL detection
publish_step_event(job_id, "rsl", "started")
rsl_result = run_rsl_step(publisher, robots_result, homepage_html)
resolution_job.rsl_result = rsl_result
resolution_job.save(update_fields=["rsl_result"])
publish_step_event(job_id, "rsl", "completed", rsl_result)

publisher.rsl_detected = rsl_result.get("rsl_detected", False)
publisher.save(update_fields=["rsl_detected"])
```

### Pattern 6: Homepage HTML Caching Within Pipeline Run
**What:** Fetch the publisher homepage HTML once and reuse it for RSS discovery, RSL detection, and potentially ToS discovery.
**When to use:** Multiple steps need the same HTML.
**Example:**
```python
def _fetch_homepage_html(publisher) -> str:
    """Fetch publisher homepage HTML via FetchStrategyManager. Returns empty string on failure."""
    from publishers.fetchers.manager import FetchStrategyManager
    try:
        manager = FetchStrategyManager()
        result = manager.fetch(f"https://{publisher.domain}/", publisher=publisher)
        return result.html
    except Exception as exc:
        logger.warning(f"Could not fetch homepage for {publisher.domain}: {exc}")
        return ""
```

### Anti-Patterns to Avoid
- **Fetching robots.txt through FetchStrategyManager:** robots.txt is a plain text file explicitly designed for bots. Using curl-cffi browser impersonation or Zyte proxy for it is wasteful. Use plain `requests.get()`.
- **Parsing the entire RSL XML document:** Phase 9 only needs to DETECT RSL presence, not parse license terms. Fetching and parsing the RSL XML is out of scope (grade computation is deferred per roadmap).
- **Re-fetching homepage HTML for each step:** RSS and RSL detection both need the homepage HTML. Fetch once, pass to both step functions.
- **Adding BeautifulSoup as a dependency for link tag extraction:** Python's built-in `html.parser` is sufficient for extracting specific `<link>` tags. Adding bs4 for this is dependency bloat.
- **Treating sitemap probe failures as errors:** Many sites don't have sitemaps. A 404 on `/sitemap.xml` is a normal, expected result, not an error.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| robots.txt parsing | Custom regex parser | protego | Wildcard matching, length-based directive ordering, Sitemap extraction, crawl-delay -- all edge cases handled |
| URL allowance checking | Manual path matching | `protego.can_fetch()` | Handles wildcards (`*`, `$`), multiple User-agent blocks, precedence rules |
| Sitemap extraction from robots.txt | Regex for `Sitemap:` lines | `protego.sitemaps` property | Already parsed as part of robots.txt; handles multiple Sitemap directives |
| Feed MIME type detection | Manual string matching | Constant set of known MIME types | Only 4 MIME types to check; well-defined by RSS/Atom specs |

**Key insight:** The only truly complex parsing in this phase is robots.txt (which protego handles). Everything else -- RSS link tags, RSL link tags, RSL License directives, sitemap HEAD probes -- is straightforward string/tag matching that needs no external library.

## Common Pitfalls

### Pitfall 1: robots.txt Returns HTML Error Page Instead of 404
**What goes wrong:** Some WAF-protected sites return a 200 with an HTML challenge page instead of the actual robots.txt.
**Why it happens:** Cloudflare/Akamai WAFs intercept all requests, including /robots.txt.
**How to avoid:** Check `Content-Type` header -- robots.txt should be `text/plain`. If `text/html` is returned with status 200, treat it as "robots.txt not found" rather than trying to parse HTML as robots.txt rules.
**Warning signs:** Protego parsing succeeds but returns nonsensical rules; `can_fetch()` returns unexpected results.

### Pitfall 2: Relative Sitemap URLs in robots.txt
**What goes wrong:** Some robots.txt files reference sitemaps with relative paths (e.g., `Sitemap: /sitemap.xml` instead of `https://example.com/sitemap.xml`).
**Why it happens:** Non-standard robots.txt authoring.
**How to avoid:** After extracting sitemaps from protego, resolve any relative URLs against the publisher's base URL using `urllib.parse.urljoin()`.
**Warning signs:** Sitemap URLs stored without a scheme/host.

### Pitfall 3: RSL License Directive Confused with Creative Commons
**What goes wrong:** A `License:` line in robots.txt might point to a Creative Commons license rather than RSL.
**Why it happens:** The `License:` directive is not unique to RSL; other licensing standards may use it.
**How to avoid:** Check the URL or content type. RSL documents use `application/rsl+xml`. For Phase 9 (detection only), flag any `License:` directive as a potential RSL indicator and note the URL. Do NOT assume all `License:` directives are RSL.
**Warning signs:** `rsl_detected: true` for sites using Creative Commons.

### Pitfall 4: RSS Feed URLs That Are Relative
**What goes wrong:** HTML `<link>` tags with `href="/feed"` are stored as-is, without the domain.
**Why it happens:** Many CMSes use relative feed URLs.
**How to avoid:** Always resolve feed URLs with `urllib.parse.urljoin(base_url, href)` before storing.
**Warning signs:** RSS URLs without scheme/host in the database.

### Pitfall 5: Homepage Fetch Fails but Pipeline Continues
**What goes wrong:** If `FetchStrategyManager` raises `AllStrategiesExhausted` for the homepage, RSS and RSL steps have no HTML to work with.
**Why it happens:** Heavy WAF protection or site is down.
**How to avoid:** Catch the fetch failure gracefully. Return `{"feeds": [], "count": 0, "error": "homepage fetch failed"}` for RSS and `{"rsl_detected": False, "error": "homepage fetch failed"}` for RSL. Do NOT let the homepage fetch failure crash the pipeline -- robots.txt and sitemap steps should already have completed.
**Warning signs:** Pipeline failure at the RSS step; RSL step never reached.

### Pitfall 6: Protego Raises on Malformed robots.txt
**What goes wrong:** Some sites serve garbled or binary content as robots.txt.
**Why it happens:** Misconfigured servers or WAF interference.
**How to avoid:** Wrap `Protego.parse()` in a try/except. If parsing fails, treat as "robots.txt not found."
**Warning signs:** Uncaught exception in the robots step.

### Pitfall 7: HEAD Request for Sitemap Probe Gets Blocked
**What goes wrong:** Some servers block HEAD requests or return 405.
**Why it happens:** Server configuration or WAF rules that only allow GET.
**How to avoid:** If HEAD returns 405 or connection error, fall back to a GET request with a small timeout and `stream=True` (read only headers, then close).
**Warning signs:** Valid sitemaps not discovered because HEAD was blocked.

## Code Examples

### Protego robots.txt Parsing (Verified)
```python
# Source: https://github.com/scrapy/protego
from protego import Protego

robotstxt = """
User-agent: *
Disallow: /private/
Allow: /public/
Crawl-delay: 5

Sitemap: https://example.com/sitemap.xml
Sitemap: https://example.com/news-sitemap.xml
"""

rp = Protego.parse(robotstxt)
rp.can_fetch("https://example.com/public/article", "mybot")  # True
rp.can_fetch("https://example.com/private/secret", "mybot")   # False
list(rp.sitemaps)  # ['https://example.com/sitemap.xml', 'https://example.com/news-sitemap.xml']
rp.crawl_delay("mybot")  # 5.0
```

### RSS Link Tag in HTML (Standard Format)
```html
<!-- Standard RSS autodiscovery -->
<link rel="alternate" type="application/rss+xml" title="Site RSS Feed" href="/feed/rss" />
<link rel="alternate" type="application/atom+xml" title="Site Atom Feed" href="/feed/atom" />
```

### RSL Detection Locations (Verified Against Spec)
```
# 1. robots.txt License directive (RSL standard)
License: https://example.com/license.xml

# 2. HTML <link> tag
<link rel="license" type="application/rsl+xml" href="https://example.com/license.xml">

# 3. HTTP Link header
Link: <https://example.com/license.xml>; rel="license"; type="application/rsl+xml"
```

### Testing Pattern (Matches Existing Codebase Conventions)
```python
@pytest.mark.django_db
class TestRunRobotsStep:
    def test_robots_found_and_url_allowed(self, monkeypatch):
        """robots step parses robots.txt and checks URL allowance."""
        from publishers.pipeline.steps import run_robots_step

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "User-agent: *\nAllow: /\nSitemap: https://example.com/sitemap.xml"
        mock_response.headers = {"Content-Type": "text/plain"}
        monkeypatch.setattr("publishers.pipeline.steps.requests.get", lambda *a, **kw: mock_response)

        publisher = PublisherFactory(domain="example.com")
        result = run_robots_step(publisher, "https://example.com/article")
        assert result["robots_found"] is True
        assert result["url_allowed"] is True
        assert "https://example.com/sitemap.xml" in result["sitemaps_from_robots"]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| urllib.robotparser (stdlib) | protego (Scrapy ecosystem) | 2020+ | Wildcard support, Sitemap extraction, modern conventions |
| feedfinder2 for RSS discovery | Direct HTML `<link>` parsing | N/A | No dependency for a simple task; feedfinder2 is unmaintained |
| No RSL standard | RSL 1.0 finalized | Dec 2025 | New `License:` directive in robots.txt, HTML/HTTP header signals |
| Manual robots.txt regex | protego 0.6.0 | Jan 2026 | Latest release; stable API |

**Deprecated/outdated:**
- `urllib.robotparser`: Lacks wildcard matching and Sitemap extraction. Not suitable for modern robots.txt conventions.
- `feedfinder2`: Unmaintained since 2018. The core functionality (finding `<link rel="alternate">` tags) is trivial to implement directly.
- `reppy`: C-extension dependency, less actively maintained than protego.

## Open Questions

1. **User-agent string for robots.txt checking**
   - What we know: `can_fetch()` requires a user-agent string. The project doesn't have an established bot user-agent.
   - What's unclear: Whether to use a project-specific string like "itsascout" or a generic one like "*".
   - Recommendation: Use "itsascout" as the user-agent for `can_fetch()`. Also check against "*" (wildcard). Report both -- "allowed for itsascout" and "allowed for generic bots". This gives the user the most useful information.

2. **Should the homepage HTML be fetched once and shared across steps?**
   - What we know: RSS and RSL steps both need homepage HTML. The ToS discovery step in Phase 8 also fetches the homepage (through the ingestion agent).
   - What's unclear: Whether to refactor Phase 8 steps to share a single fetch, or only share between the new Phase 9 steps.
   - Recommendation: For Phase 9, fetch the homepage once in the supervisor and pass it to RSS and RSL steps. Do NOT refactor Phase 8 steps yet -- that's a separate optimization. The ToS discovery agent has its own fetching logic (via Zyte proxy) that would need a larger refactor.

3. **RSL detection: just presence, or parse the XML document?**
   - What we know: The roadmap says "detect RSL licensing indicators." Grade computation is deferred.
   - What's unclear: Whether to fetch and parse the RSL XML to extract license terms.
   - Recommendation: Phase 9 should only DETECT the presence of RSL indicators (find the URLs). Do not fetch or parse the RSL XML document. Store the indicator URLs so a future phase can parse them.

4. **Frontend: should new steps appear in the Jobs/Show page?**
   - What we know: The current `PIPELINE_STEPS` array in `Show.tsx` has 4 steps. Phase 9 adds 4 more.
   - What's unclear: Whether to update the frontend in this phase or defer to Phase 10 (report card).
   - Recommendation: Update the `PIPELINE_STEPS` array and `stepDataSummary` function in `Show.tsx` to display the new steps. This keeps the SSE pipeline and frontend in sync. The full report card presentation is Phase 10, but basic step visibility should match the pipeline.

5. **Sitemap probing: how many fallback paths to try?**
   - What we know: Common paths are `/sitemap.xml`, `/sitemap_index.xml`, `/wp-sitemap.xml`.
   - What's unclear: Whether to try many paths or stop at the first success.
   - Recommendation: Try 3-4 common paths with HEAD requests, stop at the first successful one. This is a discovery step, not an exhaustive audit. Prioritize: `/sitemap.xml` first (most common), then `/sitemap_index.xml`, then `/wp-sitemap.xml`.

## Sources

### Primary (HIGH confidence)
- [protego GitHub](https://github.com/scrapy/protego) - API reference, version 0.6.0 (Jan 2026), usage examples
- [RSL 1.0 Specification](https://rslstandard.org/rsl) - Detection mechanisms: robots.txt `License:` directive, HTML `<link>` tag, HTTP `Link` header
- [RSL robots.txt guide](https://rslstandard.org/guide/robots-txt) - Exact `License:` directive syntax and placement rules
- [sitemaps.org protocol](https://www.sitemaps.org/protocol.html) - Sitemap URL conventions, robots.txt `Sitemap:` directive
- Existing codebase: `publishers/pipeline/supervisor.py`, `publishers/pipeline/steps.py`, `publishers/models.py` - Established patterns, existing fields

### Secondary (MEDIUM confidence)
- [MDN link types](https://developer.mozilla.org/en-US/docs/Web/HTML/Link_types) - `rel="alternate"` for feed discovery
- [Python 3 Feedfinder: Detecting RSS Feeds](https://alexmiller.phd/posts/python-3-feedfinder-rss-detection-from-url/) - `<link rel="alternate" type="application/rss+xml">` pattern
- [SEOcrawl: How to Find a Sitemap](https://seocrawl.com/en/how-to-find-a-sitemap/) - Common sitemap paths and discovery methods

### Tertiary (LOW confidence)
- RSL adoption breadth: RSL 1.0 was finalized Dec 2025. Real-world adoption is still early. Most publishers will return `rsl_detected: false`. This is expected and not an error.
- `License:` directive specificity: The RSL spec defines `License:` for robots.txt, but this directive may also be used by non-RSL systems. Need to differentiate by checking the referenced document's content type in a future phase.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - protego is well-established (Scrapy ecosystem, 350K weekly downloads); all other tools are stdlib
- Architecture: HIGH - Follows exact same pattern as Phase 8 steps; model fields already exist; no schema changes needed
- Pitfalls: HIGH - robots.txt parsing and HTML link extraction are well-understood problems; pitfalls are documented from real-world scraping experience
- RSL detection: MEDIUM - RSL 1.0 spec is verified against official source, but real-world adoption is nascent; detection logic is straightforward but untested at scale

**Research date:** 2026-02-14
**Valid until:** 2026-03-14 (30 days -- protego and RSL spec are stable)
