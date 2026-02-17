"""Individual pipeline step functions.

Each step function takes a Publisher (and optional context) and returns a
structured dict of results.  External services are called directly so that
tests can monkeypatch the module-level references.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import TYPE_CHECKING
from urllib.parse import urljoin

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
        }
    except AllStrategiesExhausted as exc:
        logger.error(f"robots.txt fetch error for {publisher.domain}: {exc}")
        return {"robots_found": False, "error": str(exc)}


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
