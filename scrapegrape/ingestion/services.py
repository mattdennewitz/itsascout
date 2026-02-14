"""
Services for translating agent results into Django models.
"""

import os
import requests
from base64 import b64decode
from loguru import logger
from .models import TermsDiscoveryResult, TermsEvaluationResult
from .terms_discovery import discover_terms_and_privacy
from .terms_evaluation import evaluate_terms_and_conditions


def fetch_html_via_proxy(url: str) -> str:
    """
    Fetch HTML content from a given URL using Zyte API proxy.

    Args:
        url: The URL to fetch HTML content from

    Returns:
        HTML content as string

    Raises:
        ValueError: If ZYTE_API_KEY environment variable is not set
        requests.RequestException: If the request fails
    """
    zyte_api_key = os.getenv("ZYTE_API_KEY")
    if not zyte_api_key:
        raise ValueError("ZYTE_API_KEY environment variable is required")

    try:
        api_response = requests.post(
            "https://api.zyte.com/v1/extract",
            auth=(zyte_api_key, ""),
            json={
                "url": url,
                "httpResponseBody": True,
            },
            timeout=30.0,
        )
        api_response.raise_for_status()
        http_response_body: bytes = b64decode(api_response.json()["httpResponseBody"])
        return http_response_body.decode("utf-8")
    except requests.RequestException as e:
        logger.error(f"Failed to fetch HTML from {url} via Zyte API: {e}")
        raise


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
