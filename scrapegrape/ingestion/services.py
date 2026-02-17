"""
Services for translating agent results into Django models.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import requests
from loguru import logger

from publishers.fetchers.exceptions import AllStrategiesExhausted
from publishers.fetchers.manager import FetchStrategyManager
from .models import TermsDiscoveryResult, TermsEvaluationResult
from .terms_discovery import discover_terms_and_privacy
from .terms_evaluation import evaluate_terms_and_conditions

if TYPE_CHECKING:
    from publishers.models import Publisher

_fetch_manager = FetchStrategyManager()


def fetch_html_via_proxy(url: str, publisher: Publisher | None = None) -> str:
    """
    Fetch HTML content from a given URL using FetchStrategyManager.

    Args:
        url: The URL to fetch HTML content from
        publisher: Optional publisher for per-publisher strategy memory

    Returns:
        HTML content as string

    Raises:
        requests.RequestException: If all fetch strategies fail
    """
    try:
        result = _fetch_manager.fetch(url, publisher=publisher)
        return result.html
    except AllStrategiesExhausted as e:
        logger.error(f"Failed to fetch HTML from {url}: {e}")
        raise requests.RequestException(str(e)) from e


def create_terms_discovery_from_url(publisher, url):
    """Create a TermsDiscoveryResult by running the discovery agent on a URL."""
    result = discover_terms_and_privacy(url)

    terms_discovery, created = TermsDiscoveryResult.objects.update_or_create(
        publisher=publisher,
        defaults={
            "terms_of_service_url": result.terms_of_service_url,
            "confidence_score": result.confidence_score,
            "notes": result.notes,
        },
    )

    return terms_discovery


def create_terms_evaluation_from_url(publisher, url):
    """Create a TermsEvaluationResult by running the evaluation agent on a URL."""
    result = evaluate_terms_and_conditions(url)

    # Convert ActivityPermission objects to dict for JSON storage
    permissions_data = [
        {"activity": perm.activity, "permission": perm.permission, "notes": perm.notes}
        for perm in result.permissions
    ]

    terms_evaluation, created = TermsEvaluationResult.objects.update_or_create(
        publisher=publisher,
        defaults={
            "permissions": permissions_data,
            "territorial_exceptions": result.territorial_exceptions,
            "arbitration_clauses": result.arbitration_clauses,
            "document_type": result.document_type,
            "confidence_score": result.confidence_score,
        },
    )

    return terms_evaluation


def discover_and_evaluate_terms(publisher, base_url):
    """Discover terms URL from a site and evaluate it."""
    # First, discover the terms and privacy policy URLs
    discovery_result = create_terms_discovery_from_url(publisher, base_url)

    evaluation_result = None

    # Evaluate Terms of Service if found
    if discovery_result.terms_of_service_url:
        try:
            evaluation_result = create_terms_evaluation_from_url(
                publisher, str(discovery_result.terms_of_service_url)
            )
        except Exception as e:
            print(f"Error evaluating ToS: {e}")

    return {"discovery": discovery_result, "evaluation": evaluation_result}
