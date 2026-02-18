"""Individual pipeline step functions.

Each step function takes a Publisher (and optional context) and returns a
structured dict of results.  External services are called directly so that
tests can monkeypatch the module-level references.
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlparse

from django.conf import settings
from django.utils import timezone
from loguru import logger
from protego import Protego

from publishers.fetchers.exceptions import AllStrategiesExhausted
from publishers.fetchers.manager import FetchStrategyManager
from publishers.waf_check import scan_url_with_wafw00f
from ingestion.terms_discovery import discover_terms_and_privacy
from ingestion.terms_evaluation import evaluate_terms_and_conditions

if TYPE_CHECKING:
    from publishers.models import Publisher

ITSASCOUT_USER_AGENT = "itsascout"

_fetch_manager = FetchStrategyManager()

COMMON_SITEMAP_PATHS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap/sitemap.xml",
    "/wp-sitemap.xml",
]


# ---------------------------------------------------------------------------
# Freshness TTL check
# ---------------------------------------------------------------------------


def should_skip_publisher_steps(publisher: Publisher) -> bool:
    """Return True if publisher was checked within PUBLISHER_FRESHNESS_TTL."""
    if not publisher.last_checked_at:
        return False
    age = timezone.now() - publisher.last_checked_at
    return age < settings.PUBLISHER_FRESHNESS_TTL


# ---------------------------------------------------------------------------
# WAF step
# ---------------------------------------------------------------------------


def run_waf_step(publisher: Publisher) -> dict:
    """Run wafw00f against the publisher URL and return structured result."""
    publisher_url = publisher.url or f"https://{publisher.domain}/"
    try:
        result = scan_url_with_wafw00f(publisher_url)
        if result is None:
            return {"waf_detected": False, "waf_type": "", "error": "WAF scan failed"}

        report = result["report"][0]
        return {
            "waf_detected": bool(report.get("detected", False)),
            "waf_type": report.get("firewall", "") if report.get("detected") else "",
        }
    except Exception as exc:
        logger.error(f"WAF step error for {publisher_url}: {exc}")
        return {"waf_detected": False, "waf_type": "", "error": str(exc)}


# ---------------------------------------------------------------------------
# ToS discovery step
# ---------------------------------------------------------------------------


def run_tos_discovery_step(publisher: Publisher) -> dict:
    """Discover Terms of Service URL for the publisher."""
    publisher_url = publisher.url or f"https://{publisher.domain}/"
    try:
        discovery = discover_terms_and_privacy(publisher_url, publisher=publisher)
        tos_url = (
            str(discovery.terms_of_service_url)
            if discovery.terms_of_service_url
            else None
        )
        return {
            "tos_url": tos_url,
            "confidence": discovery.confidence_score,
            "notes": discovery.notes or "",
        }
    except Exception as exc:
        logger.error(f"ToS discovery error for {publisher_url}: {exc}")
        return {"tos_url": None, "error": str(exc)}


# ---------------------------------------------------------------------------
# ToS evaluation step
# ---------------------------------------------------------------------------


def run_tos_evaluation_step(publisher: Publisher, tos_url: str | None) -> dict:
    """Evaluate Terms of Service permissions for the publisher."""
    if tos_url is None:
        return {"skipped": True, "reason": "No ToS URL found"}

    try:
        evaluation = evaluate_terms_and_conditions(tos_url, publisher=publisher)
        return {
            "permissions": [p.model_dump() for p in evaluation.permissions],
            "document_type": evaluation.document_type,
            "confidence_score": evaluation.confidence_score,
            "territorial_exceptions": evaluation.territorial_exceptions,
            "arbitration_clauses": evaluation.arbitration_clauses,
        }
    except Exception as exc:
        logger.error(f"ToS evaluation error for {tos_url}: {exc}")
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Helper: extract License directives from robots.txt
# ---------------------------------------------------------------------------


def _extract_license_directives(robots_text: str) -> list[str]:
    """Extract License: directive values from raw robots.txt text (RSL standard)."""
    return re.findall(r"^License:\s*(.+)$", robots_text, re.MULTILINE | re.IGNORECASE)


# ---------------------------------------------------------------------------
# robots.txt step
# ---------------------------------------------------------------------------


def run_robots_step(publisher: Publisher, submitted_url: str) -> dict:
    """Fetch and parse robots.txt, check if submitted URL is allowed."""
    robots_url = urljoin(f"https://{publisher.domain}/", "/robots.txt")
    try:
        result = _fetch_manager.fetch(robots_url, publisher=publisher)
        text = result.html

        # Content guard: HTML response means WAF challenge, not real robots.txt
        lower = text.strip().lower()
        if lower.startswith("<html") or lower.startswith("<!doctype"):
            return {"robots_found": False, "error": "HTML response (likely WAF challenge)"}

        try:
            rp = Protego.parse(text)
        except Exception:
            return {"robots_found": False, "error": "malformed robots.txt"}

        url_allowed = rp.can_fetch(submitted_url, ITSASCOUT_USER_AGENT)
        sitemaps = list(rp.sitemaps)
        crawl_delay = rp.crawl_delay(ITSASCOUT_USER_AGENT)
        license_directives = _extract_license_directives(text)

        return {
            "robots_found": True,
            "url_allowed": url_allowed,
            "sitemaps_from_robots": sitemaps,
            "crawl_delay": crawl_delay,
            "license_directives": license_directives,
            "raw_length": len(text),
            "raw_text": text,
        }
    except AllStrategiesExhausted as exc:
        logger.error(f"robots.txt fetch error for {publisher.domain}: {exc}")
        return {"robots_found": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# AI bot blocking detection step
# ---------------------------------------------------------------------------


AI_BOT_USER_AGENTS = {
    "GPTBot": "OpenAI",
    "ChatGPT-User": "OpenAI",
    "Google-Extended": "Google",
    "anthropic-ai": "Anthropic",
    "ClaudeBot": "Anthropic",
    "CCBot": "Common Crawl",
    "Bytespider": "ByteDance",
    "Amazonbot": "Amazon",
    "FacebookBot": "Meta",
    "Meta-ExternalAgent": "Meta",
    "cohere-ai": "Cohere",
    "PerplexityBot": "Perplexity",
    "Applebot-Extended": "Apple",
}


def run_ai_bot_blocking_step(publisher: Publisher, robots_result: dict) -> dict:
    """Check which AI crawler bots are blocked by robots.txt."""
    if not robots_result.get("robots_found") or not robots_result.get("raw_text"):
        return {
            "robots_found": False,
            "bots": {},
            "blocked_count": 0,
            "total_count": 0,
        }

    raw_text = robots_result["raw_text"]
    try:
        rp = Protego.parse(raw_text)
    except Exception:
        return {
            "robots_found": True,
            "bots": {},
            "blocked_count": 0,
            "total_count": 0,
            "error": "malformed robots.txt",
        }

    bots = {}
    blocked_count = 0
    for user_agent, company in AI_BOT_USER_AGENTS.items():
        allowed = rp.can_fetch("/", user_agent)
        blocked = not allowed
        bots[user_agent] = {"company": company, "blocked": blocked}
        if blocked:
            blocked_count += 1

    return {
        "robots_found": True,
        "bots": bots,
        "blocked_count": blocked_count,
        "total_count": len(AI_BOT_USER_AGENTS),
    }


# ---------------------------------------------------------------------------
# Sitemap discovery step
# ---------------------------------------------------------------------------


def run_sitemap_step(publisher: Publisher, robots_result: dict) -> dict:
    """Discover sitemap URLs from robots.txt directives and common path probing."""
    base_url = f"https://{publisher.domain}/"
    found_sitemaps = set()

    # Start with sitemaps from robots.txt, resolving any relative URLs
    for url in robots_result.get("sitemaps_from_robots", []):
        found_sitemaps.add(urljoin(base_url, url))

    source = "robots.txt" if found_sitemaps else "none"

    # Probe common paths only if robots.txt had no sitemaps
    if not found_sitemaps:
        for path in COMMON_SITEMAP_PATHS:
            sitemap_url = urljoin(base_url, path)
            try:
                result = _fetch_manager.fetch(sitemap_url, publisher=publisher)
                text = result.html.strip()
                # Verify content looks like XML sitemap
                if text.startswith("<?xml") or "<urlset" in text or "<sitemapindex" in text:
                    found_sitemaps.add(sitemap_url)
                    source = "probe"
                    break
            except AllStrategiesExhausted:
                continue

    return {
        "sitemap_urls": sorted(found_sitemaps),
        "source": source,
        "count": len(found_sitemaps),
    }


# ---------------------------------------------------------------------------
# RSS feed discovery step
# ---------------------------------------------------------------------------

_FEED_MIME_TYPES = {
    "application/rss+xml",
    "application/atom+xml",
    "application/xml",
    "text/xml",
}


class FeedLinkParser(HTMLParser):
    """Extract <link rel="alternate"> tags pointing to RSS/Atom feeds."""

    def __init__(self) -> None:
        super().__init__()
        self.feeds: list[dict] = []

    def _handle_link(self, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = {k.lower(): (v or "") for k, v in attrs}
        rel = attr_dict.get("rel", "")
        link_type = attr_dict.get("type", "")
        href = attr_dict.get("href", "")
        if "alternate" in rel and link_type in _FEED_MIME_TYPES and href:
            self.feeds.append({
                "url": href,
                "type": link_type,
                "title": attr_dict.get("title", ""),
            })

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "link":
            self._handle_link(attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "link":
            self._handle_link(attrs)


def run_rss_step(publisher: Publisher, homepage_html: str) -> dict:
    """Discover RSS/Atom feed URLs from homepage HTML <link> tags."""
    if not homepage_html:
        return {"feeds": [], "count": 0, "error": "homepage fetch failed"}

    parser = FeedLinkParser()
    try:
        parser.feed(homepage_html)
    except Exception:
        return {"feeds": [], "count": 0, "error": "HTML parse error"}

    base_url = f"https://{publisher.domain}/"
    feeds = []
    for feed in parser.feeds:
        feeds.append({
            "url": urljoin(base_url, feed["url"]),
            "type": feed["type"],
            "title": feed["title"],
        })

    return {"feeds": feeds, "count": len(feeds)}


# ---------------------------------------------------------------------------
# RSL detection step
# ---------------------------------------------------------------------------


class RSLLinkParser(HTMLParser):
    """Extract <link rel="license" type="application/rsl+xml"> tags."""

    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []

    def _handle_link(self, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = {k.lower(): (v or "") for k, v in attrs}
        rel = attr_dict.get("rel", "")
        link_type = attr_dict.get("type", "")
        href = attr_dict.get("href", "")
        if "license" in rel and "application/rsl+xml" in link_type and href:
            self.urls.append(href)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "link":
            self._handle_link(attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "link":
            self._handle_link(attrs)


def run_rsl_step(
    publisher: Publisher,
    robots_result: dict,
    homepage_html: str,
    homepage_headers: dict | None = None,
) -> dict:
    """Detect RSL licensing indicators from robots.txt, HTML, and HTTP headers."""
    base_url = f"https://{publisher.domain}/"
    indicators: list[dict] = []

    # Source 1: License directives from robots.txt
    for url in robots_result.get("license_directives", []):
        indicators.append({"source": "robots.txt", "url": urljoin(base_url, url)})

    # Source 2: <link rel="license" type="application/rsl+xml"> in HTML
    if homepage_html:
        parser = RSLLinkParser()
        try:
            parser.feed(homepage_html)
        except Exception:
            pass
        for url in parser.urls:
            indicators.append({"source": "html_link", "url": urljoin(base_url, url)})

    # Source 3: Link HTTP header with rel="license" and application/rsl+xml
    if homepage_headers:
        link_header = homepage_headers.get("Link", homepage_headers.get("link", ""))
        if "application/rsl+xml" in link_header and 'rel="license"' in link_header:
            match = re.search(r"<([^>]+)>", link_header)
            if match:
                indicators.append({"source": "http_header", "url": urljoin(base_url, match.group(1))})

    return {
        "rsl_detected": len(indicators) > 0,
        "indicators": indicators,
        "count": len(indicators),
    }


# ---------------------------------------------------------------------------
# Publisher details (structured data extraction) step
# ---------------------------------------------------------------------------

ORG_TYPES = {
    "Organization",
    "NewsMediaOrganization",
    "Corporation",
    "LocalBusiness",
    "NGO",
    "EducationalOrganization",
}


def _is_org_type(t: str) -> bool:
    """Check if a schema.org type string matches an Organization type."""
    if t in ORG_TYPES:
        return True
    # Handle full URL form like "https://schema.org/Organization"
    parsed = urlparse(t)
    if parsed.scheme and parsed.path:
        segment = parsed.path.rstrip("/").rsplit("/", 1)[-1]
        return segment in ORG_TYPES
    return False


def _flatten_jsonld_nodes(items: list) -> list[dict]:
    """Flatten JSON-LD items, expanding nested @graph arrays."""
    nodes = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if "@graph" in item:
            graph = item["@graph"]
            if isinstance(graph, list):
                nodes.extend(d for d in graph if isinstance(d, dict))
        if "@type" in item:
            nodes.append(item)
    return nodes


def _normalize_types(node: dict) -> list[str]:
    """Return list of @type values from a node."""
    t = node.get("@type", [])
    if isinstance(t, str):
        return [t]
    if isinstance(t, list):
        return [str(x) for x in t]
    return []


def _urls_match(a: str | None, b: str | None) -> bool:
    """Compare two URLs, ignoring trailing slashes."""
    if not a or not b:
        return False
    return a.rstrip("/") == b.rstrip("/")


def _extract_organization(org: dict, source: str, score: int) -> dict:
    """Build the return dict from a candidate organization node."""
    # Extract logo URL
    logo = org.get("logo")
    if isinstance(logo, dict):
        logo = logo.get("url") or logo.get("@id")
    elif isinstance(logo, list) and logo:
        first = logo[0]
        logo = first.get("url") if isinstance(first, dict) else str(first)

    same_as = org.get("sameAs", [])
    if isinstance(same_as, str):
        same_as = [same_as]

    return {
        "found": True,
        "source": source,
        "score": score,
        "organization": {
            "name": org.get("name"),
            "type": _normalize_types(org)[0] if _normalize_types(org) else None,
            "url": org.get("url"),
            "id": org.get("@id"),
            "logo": str(logo) if logo else None,
            "same_as": [str(u) for u in same_as] if isinstance(same_as, list) else [],
        },
        "candidate_count": 0,  # filled by caller
    }


def _score_jsonld_candidate(
    node: dict, homepage_url: str, reference_map: set[str]
) -> int:
    """Score a JSON-LD Organization candidate."""
    score = 0
    node_id = node.get("@id", "")
    node_url = node.get("url", "")
    types = _normalize_types(node)

    # @id URL == homepage URL → +4
    if _urls_match(node_id, homepage_url):
        score += 4

    # url == homepage URL → +3
    if _urls_match(node_url, homepage_url):
        score += 3

    # @id contains #organization / #publisher / #brand → +2
    if node_id:
        id_lower = node_id.lower()
        if any(frag in id_lower for frag in ("#organization", "#publisher", "#brand")):
            score += 2

    # @type includes NewsMediaOrganization → +3
    if any(_is_org_type(t) and "NewsMediaOrganization" in t for t in types):
        score += 3

    # Has logo → +1
    if node.get("logo"):
        score += 1

    # Has sameAs with items → +1
    same_as = node.get("sameAs", [])
    if isinstance(same_as, str):
        same_as = [same_as]
    if same_as:
        score += 1

    # Has contactPoint or address → +1
    if node.get("contactPoint") or node.get("address"):
        score += 1

    # Referenced by Article/WebPage publisher/author/isPartOf → +2
    identifiers = {node_id, node_url} - {""}
    if identifiers & reference_map:
        score += 2

    return score


def _build_reference_map(all_nodes: list[dict]) -> set[str]:
    """Build set of @id/@url values that are referenced by publisher/author/isPartOf."""
    refs: set[str] = set()
    for node in all_nodes:
        for field in ("publisher", "author", "isPartOf"):
            val = node.get(field)
            if isinstance(val, dict):
                ref_id = val.get("@id") or val.get("url")
                if ref_id:
                    refs.add(ref_id)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        ref_id = item.get("@id") or item.get("url")
                        if ref_id:
                            refs.add(ref_id)
    return refs


def run_publisher_details_step(publisher: Publisher, homepage_html: str) -> dict:
    """Extract structured Organization data from homepage HTML using extruct."""
    import extruct

    homepage_url = publisher.url or f"https://{publisher.domain}/"
    empty_result = {
        "found": False,
        "source": None,
        "score": 0,
        "organization": None,
        "candidate_count": 0,
    }

    if not homepage_html or not homepage_html.strip():
        return {**empty_result, "error": "empty HTML"}

    # Extract JSON-LD first (fast: just parses <script> tags, no DOM needed).
    # Only fall back to microdata (slow: full lxml DOM parse) if JSON-LD has
    # no Organization candidates.
    try:
        extracted = extruct.extract(
            homepage_html, syntaxes=["json-ld"], uniform=True
        )
    except Exception as exc:
        logger.error(f"extruct JSON-LD extraction failed for {publisher.domain}: {exc}")
        return {**empty_result, "error": str(exc)}

    # --- JSON-LD path ---
    jsonld_items = extracted.get("json-ld", [])
    all_nodes = _flatten_jsonld_nodes(jsonld_items)

    org_candidates = [
        n for n in all_nodes if any(_is_org_type(t) for t in _normalize_types(n))
    ]

    if org_candidates:
        reference_map = _build_reference_map(all_nodes)
        scored = []
        for i, node in enumerate(org_candidates):
            s = _score_jsonld_candidate(node, homepage_url, reference_map)
            node_id = node.get("@id", "")
            node_url = node.get("url", "")
            scored.append((
                -s,  # primary: score desc
                0 if _urls_match(node_url, homepage_url) else 1,  # tie-break: url==homepage
                0 if any(frag in node_id.lower() for frag in ("#organization", "#publisher")) else 1,
                i,  # document order
                node,
                s,
            ))
        scored.sort()

        # Discard score==0 nodes with no url or @id
        for entry in scored:
            node = entry[4]
            s = entry[5]
            if s == 0 and not node.get("url") and not node.get("@id"):
                continue
            result = _extract_organization(node, "json-ld", s)
            result["candidate_count"] = len(org_candidates)
            return result

    # --- Microdata fallback (lazy: only parse DOM if JSON-LD had nothing) ---
    try:
        micro_extracted = extruct.extract(
            homepage_html, syntaxes=["microdata"], uniform=True
        )
    except Exception as exc:
        logger.error(f"extruct microdata extraction failed for {publisher.domain}: {exc}")
        return {**empty_result, "error": str(exc)}

    microdata_items = micro_extracted.get("microdata", [])
    micro_candidates = [
        item
        for item in microdata_items
        if isinstance(item, dict)
        and any(_is_org_type(t) for t in _normalize_types(item))
    ]

    if micro_candidates:
        scored_micro = []
        for i, item in enumerate(micro_candidates):
            s = 0
            item_url = item.get("url", "")
            item_id = item.get("itemid", item.get("@id", ""))

            # url == homepage → +3
            if _urls_match(item_url, homepage_url):
                s += 3

            # itemid matches → +2
            if _urls_match(item_id, homepage_url):
                s += 2

            # logo/sameAs → +1 each
            if item.get("logo"):
                s += 1
            same_as = item.get("sameAs", [])
            if isinstance(same_as, str):
                same_as = [same_as]
            if same_as:
                s += 1

            # Nested in WebPage/WebSite publisher → +2
            for other in microdata_items:
                if not isinstance(other, dict):
                    continue
                other_types = _normalize_types(other)
                if any("WebPage" in t or "WebSite" in t for t in other_types):
                    pub = other.get("publisher")
                    if isinstance(pub, dict) and pub.get("@type") and pub.get("name") == item.get("name"):
                        s += 2
                        break

            scored_micro.append((-s, i, item, s))

        scored_micro.sort()

        for entry in scored_micro:
            item = entry[2]
            s = entry[3]
            if s == 0 and not item.get("url") and not item.get("@id") and not item.get("itemid"):
                continue
            result = _extract_organization(item, "microdata", s)
            result["candidate_count"] = len(micro_candidates)
            return result

    return {**empty_result, "candidate_count": len(org_candidates) + len(micro_candidates)}


# ---------------------------------------------------------------------------
# Twitter Card parser (HTMLParser, following FeedLinkParser/RSLLinkParser pattern)
# ---------------------------------------------------------------------------


class TwitterCardParser(HTMLParser):
    """Extract <meta name="twitter:*" content="..."> tags."""

    def __init__(self) -> None:
        super().__init__()
        self.cards: dict[str, str] = {}

    def _handle_meta(self, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = {k.lower(): (v or "") for k, v in attrs}
        name = attr_dict.get("name", "")
        content = attr_dict.get("content", "")
        if name.startswith("twitter:") and content:
            self.cards[name] = content

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "meta":
            self._handle_meta(attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "meta":
            self._handle_meta(attrs)


# ---------------------------------------------------------------------------
# Article extraction step
# ---------------------------------------------------------------------------

ARTICLE_TYPES = {
    "Article", "NewsArticle", "BlogPosting", "TechArticle",
    "ScholarlyArticle", "OpinionNewsArticle", "AnalysisNewsArticle",
    "ReportageNewsArticle", "ReviewNewsArticle", "LiveBlogPosting",
    "SocialMediaPosting", "WebPage", "CreativeWork",
}

KEY_FIELDS = [
    "headline", "author", "datePublished", "dateModified",
    "image", "description", "isAccessibleForFree",
    "wordCount", "articleSection", "inLanguage", "keywords",
]

OG_FIELD_MAP = {
    "og:title": "headline",
    "og:description": "description",
    "og:image": "image",
    "og:type": "type",
    "og:site_name": "publisher_name",
    "og:locale": "inLanguage",
    "article:published_time": "datePublished",
    "article:modified_time": "dateModified",
    "article:author": "author",
    "article:section": "articleSection",
    "article:tag": "keywords",
}


def _extract_jsonld_article_fields(jsonld_items: list) -> dict | None:
    """Extract key fields from the first article-type JSON-LD node."""
    nodes = _flatten_jsonld_nodes(jsonld_items)
    for node in nodes:
        types = _normalize_types(node)
        if any(t.split("/")[-1] in ARTICLE_TYPES for t in types):
            fields: dict = {}
            for field in KEY_FIELDS:
                val = node.get(field)
                if val is not None:
                    if isinstance(val, dict):
                        fields[field] = val.get("name") or val.get("@id") or str(val)
                    elif isinstance(val, list):
                        fields[field] = [
                            item.get("name") if isinstance(item, dict) else str(item)
                            for item in val
                        ]
                    else:
                        fields[field] = val
            # Extract publisher name if present
            pub = node.get("publisher")
            if isinstance(pub, dict):
                fields["publisher_name"] = pub.get("name")
            return fields
    return None


def _extract_opengraph_fields(og_items: list) -> dict | None:
    """Extract key fields from OpenGraph metadata."""
    if not og_items:
        return None
    props: dict = {}
    for item in og_items:
        for key, val in item.get("properties", []):
            if key in OG_FIELD_MAP:
                mapped = OG_FIELD_MAP[key]
                if mapped == "keywords":
                    props.setdefault(mapped, []).append(val)
                else:
                    props[mapped] = val
    return props if props else None


def _extract_microdata_article_fields(microdata_items: list) -> dict | None:
    """Extract key fields from Microdata article-type items."""
    for item in microdata_items:
        if not isinstance(item, dict):
            continue
        types = _normalize_types(item)
        if any(t.split("/")[-1] in ARTICLE_TYPES for t in types):
            fields: dict = {}
            for field in KEY_FIELDS:
                val = item.get(field)
                if val is not None:
                    if isinstance(val, dict):
                        fields[field] = val.get("name") or val.get("@id") or str(val)
                    elif isinstance(val, list):
                        fields[field] = [
                            v.get("name") if isinstance(v, dict) else str(v)
                            for v in val
                        ]
                    else:
                        fields[field] = val
            pub = item.get("publisher")
            if isinstance(pub, dict):
                fields["publisher_name"] = pub.get("name")
            return fields
    return None


def _extract_twitter_cards(html: str) -> dict | None:
    """Extract Twitter Card meta tags from HTML."""
    parser = TwitterCardParser()
    try:
        parser.feed(html)
    except Exception:
        return None
    return parser.cards if parser.cards else None


def run_article_extraction_step(article_html: str, article_url: str) -> dict:
    """Extract structured metadata from article HTML into per-format sections."""
    import extruct

    formats_found: list[str] = []

    if not article_html or not article_html.strip():
        return {
            "jsonld_fields": None,
            "opengraph_fields": None,
            "microdata_fields": None,
            "twitter_cards": None,
            "formats_found": [],
        }

    # Extract using extruct (JSON-LD, OpenGraph, Microdata)
    try:
        extracted = extruct.extract(
            article_html,
            base_url=article_url,
            syntaxes=["json-ld", "opengraph", "microdata"],
            uniform=False,
        )
    except Exception as exc:
        logger.error(f"extruct extraction failed for {article_url}: {exc}")
        return {
            "jsonld_fields": None,
            "opengraph_fields": None,
            "microdata_fields": None,
            "twitter_cards": None,
            "formats_found": [],
        }

    # JSON-LD
    jsonld_fields = _extract_jsonld_article_fields(extracted.get("json-ld", []))
    if jsonld_fields:
        formats_found.append("json-ld")

    # OpenGraph
    opengraph_fields = _extract_opengraph_fields(extracted.get("opengraph", []))
    if opengraph_fields:
        formats_found.append("opengraph")

    # Microdata
    microdata_fields = _extract_microdata_article_fields(extracted.get("microdata", []))
    if microdata_fields:
        formats_found.append("microdata")

    # Twitter Cards (via HTMLParser, not extruct)
    twitter_cards = _extract_twitter_cards(article_html)
    if twitter_cards:
        formats_found.append("twitter-cards")

    return {
        "jsonld_fields": jsonld_fields,
        "opengraph_fields": opengraph_fields,
        "microdata_fields": microdata_fields,
        "twitter_cards": twitter_cards,
        "formats_found": formats_found,
    }


# ---------------------------------------------------------------------------
# Paywall detection step
# ---------------------------------------------------------------------------


def _check_schema_accessible(extraction_result: dict) -> bool | None:
    """Check isAccessibleForFree from JSON-LD fields, including hasPart nesting."""
    jsonld = extraction_result.get("jsonld_fields")
    if not jsonld:
        return None

    # Top-level check
    accessible = jsonld.get("isAccessibleForFree")
    if accessible is not None:
        if isinstance(accessible, str):
            return accessible.lower() in ("true", "yes", "1")
        return bool(accessible)

    # hasPart nesting (Google's recommended pattern)
    has_part = jsonld.get("hasPart")
    if isinstance(has_part, list):
        for part in has_part:
            if isinstance(part, dict):
                part_accessible = part.get("isAccessibleForFree")
                if part_accessible is not None:
                    if isinstance(part_accessible, str):
                        return part_accessible.lower() in ("true", "yes", "1")
                    return bool(part_accessible)
    elif isinstance(has_part, dict):
        part_accessible = has_part.get("isAccessibleForFree")
        if part_accessible is not None:
            if isinstance(part_accessible, str):
                return part_accessible.lower() in ("true", "yes", "1")
            return bool(part_accessible)

    return None


def _detect_paywall_heuristics(html: str) -> tuple[str, list[str]]:
    """Detect paywall signals from HTML content. Returns (status, signals)."""
    signals: list[str] = []
    html_lower = html.lower()

    # Signal: Login/subscribe wall patterns
    login_patterns = [
        "subscribe to continue reading",
        "sign in to read",
        "create an account to continue",
        "already a subscriber?",
        "subscription required",
        "members only",
    ]
    for pattern in login_patterns:
        if pattern in html_lower:
            signals.append(f"login_wall:{pattern[:30]}")

    # Signal: Paywall CSS classes
    paywall_classes = [
        "paywall", "subscriber-only", "premium-content",
        "gated-content", "meter-", "regwall",
    ]
    for cls in paywall_classes:
        if cls in html_lower:
            signals.append(f"paywall_class:{cls}")

    # Signal: Metered access patterns
    meter_patterns = [
        "articles remaining", "free articles",
        "monthly limit", "article limit",
    ]
    for pattern in meter_patterns:
        if pattern in html_lower:
            signals.append(f"metered:{pattern[:20]}")

    # Decision logic: high confidence bar
    has_login = any(s.startswith("login_wall:") for s in signals)
    has_paywall_class = any(s.startswith("paywall_class:") for s in signals)
    has_meter = any(s.startswith("metered:") for s in signals)

    if has_meter:
        return "metered", signals
    if has_login and has_paywall_class:
        return "paywalled", signals
    if len(signals) == 0:
        return "free", signals
    return "unknown", signals


def run_paywall_detection_step(article_html: str, extraction_result: dict) -> dict:
    """Detect paywall status from schema.org markup and heuristic signals."""
    schema_accessible = _check_schema_accessible(extraction_result)

    if schema_accessible is True:
        return {
            "paywall_status": "free",
            "signals": [],
            "schema_accessible": True,
        }
    if schema_accessible is False:
        return {
            "paywall_status": "paywalled",
            "signals": [],
            "schema_accessible": False,
        }

    # Fallback to heuristics
    status, signals = _detect_paywall_heuristics(article_html)
    return {
        "paywall_status": status,
        "signals": signals,
        "schema_accessible": None,
    }


# ---------------------------------------------------------------------------
# Metadata profile step (LLM-based)
# ---------------------------------------------------------------------------

from pydantic import BaseModel, Field
from pydantic_ai import Agent


class MetadataProfileResult(BaseModel):
    summary: str = Field(
        ...,
        description="Human-readable 2-4 sentence summary of what metadata formats "
        "are present, what key fields are populated, and overall metadata quality",
    )


METADATA_PROFILE_PROMPT = """You are a structured data analyst. Given the extracted metadata
from a news article page, write a concise human-readable summary of what metadata is available.

Focus on:
1. Which formats are present (JSON-LD, OpenGraph, Microdata, Twitter Cards)
2. Key fields populated vs missing (headline, author, dates, images)
3. Whether the metadata is well-structured or minimal
4. Paywall status if detected

Be factual and concise. 2-4 sentences maximum."""

metadata_profile_agent = Agent(
    "openai:gpt-4.1-nano",
    output_type=MetadataProfileResult,
    system_prompt=METADATA_PROFILE_PROMPT,
)


def run_metadata_profile_step(extraction_result: dict, article_url: str) -> dict:
    """Generate LLM-based metadata profile summary."""
    try:
        result = metadata_profile_agent.run_sync(
            f"Analyze metadata for {article_url}:\n{json.dumps(extraction_result, default=str)}"
        )
        return result.output.model_dump()
    except Exception as exc:
        logger.error(f"Metadata profile step error for {article_url}: {exc}")
        return {"summary": "", "error": str(exc)}
