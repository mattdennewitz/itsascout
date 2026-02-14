"""Individual pipeline step functions.

Each step function takes a Publisher (and optional context) and returns a
structured dict of results.  External services are called directly so that
tests can monkeypatch the module-level references.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from django.utils import timezone
from loguru import logger

from publishers.waf_check import scan_url_with_wafw00f
from ingestion.terms_discovery import discover_terms_and_privacy
from ingestion.terms_evaluation import evaluate_terms_and_conditions

if TYPE_CHECKING:
    from publishers.models import Publisher


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
