"""Individual pipeline step functions.

Each step function takes a Publisher (and optional context) and returns a
structured dict of results.  External services are called directly so that
tests can monkeypatch the module-level references.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.utils import timezone
from loguru import logger
from protego import Protego

from publishers.waf_check import scan_url_with_wafw00f
from ingestion.terms_discovery import discover_terms_and_privacy
from ingestion.terms_evaluation import evaluate_terms_and_conditions

if TYPE_CHECKING:
    from publishers.models import Publisher

ITSASCOUT_USER_AGENT = "itsascout"

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
    try:
        result = scan_url_with_wafw00f(publisher.url)
        if result is None:
            return {"waf_detected": False, "waf_type": "", "error": "WAF scan failed"}

        report = result["report"][0]
        return {
            "waf_detected": bool(report.get("detected", False)),
            "waf_type": report.get("firewall", "") if report.get("detected") else "",
        }
    except Exception as exc:
        logger.error(f"WAF step error for {publisher.url}: {exc}")
        return {"waf_detected": False, "waf_type": "", "error": str(exc)}


# ---------------------------------------------------------------------------
# ToS discovery step
# ---------------------------------------------------------------------------


def run_tos_discovery_step(publisher: Publisher) -> dict:
    """Discover Terms of Service URL for the publisher."""
    try:
        discovery = discover_terms_and_privacy(publisher.url)
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
        logger.error(f"ToS discovery error for {publisher.url}: {exc}")
        return {"tos_url": None, "error": str(exc)}


# ---------------------------------------------------------------------------
# ToS evaluation step
# ---------------------------------------------------------------------------


def run_tos_evaluation_step(publisher: Publisher, tos_url: str | None) -> dict:
    """Evaluate Terms of Service permissions for the publisher."""
    if tos_url is None:
        return {"skipped": True, "reason": "No ToS URL found"}

    try:
        evaluation = evaluate_terms_and_conditions(tos_url)
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
        response = requests.get(
            robots_url, timeout=15, headers={"User-Agent": ITSASCOUT_USER_AGENT}
        )
        if response.status_code != 200:
            return {"robots_found": False, "status_code": response.status_code}

        # Content-type guard: HTML response means WAF challenge, not real robots.txt
        content_type = response.headers.get("Content-Type", "")
        if "text/html" in content_type:
            return {"robots_found": False, "error": "HTML response (likely WAF challenge)"}

        try:
            rp = Protego.parse(response.text)
        except Exception:
            return {"robots_found": False, "error": "malformed robots.txt"}

        url_allowed = rp.can_fetch(submitted_url, ITSASCOUT_USER_AGENT)
        sitemaps = list(rp.sitemaps)
        crawl_delay = rp.crawl_delay(ITSASCOUT_USER_AGENT)
        license_directives = _extract_license_directives(response.text)

        return {
            "robots_found": True,
            "url_allowed": url_allowed,
            "sitemaps_from_robots": sitemaps,
            "crawl_delay": crawl_delay,
            "license_directives": license_directives,
            "raw_length": len(response.text),
        }
    except requests.RequestException as exc:
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
                resp = requests.head(sitemap_url, timeout=10, allow_redirects=True)
                if resp.status_code == 200 and "xml" in resp.headers.get(
                    "content-type", ""
                ):
                    found_sitemaps.add(sitemap_url)
                    source = "probe"
                    break
                # Fall back to GET if HEAD returns 405
                if resp.status_code == 405:
                    resp = requests.get(
                        sitemap_url, timeout=10, stream=True
                    )
                    resp.close()
                    if resp.status_code == 200 and "xml" in resp.headers.get(
                        "content-type", ""
                    ):
                        found_sitemaps.add(sitemap_url)
                        source = "probe"
                        break
            except requests.ConnectionError:
                # Fall back to GET on connection error from HEAD
                try:
                    resp = requests.get(
                        sitemap_url, timeout=10, stream=True
                    )
                    resp.close()
                    if resp.status_code == 200 and "xml" in resp.headers.get(
                        "content-type", ""
                    ):
                        found_sitemaps.add(sitemap_url)
                        source = "probe"
                        break
                except requests.RequestException:
                    continue
            except requests.RequestException:
                continue

    return {
        "sitemap_urls": sorted(found_sitemaps),
        "source": source,
        "count": len(found_sitemaps),
    }
