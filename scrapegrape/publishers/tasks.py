from typing import Dict, Any
from urllib.parse import urlparse
from django.db import transaction
from django.utils import timezone
from django_rq import job
from loguru import logger

from .models import Publisher, WAFReport
from ingestion.models import TermsDiscoveryResult, TermsEvaluationResult
from ingestion.terms_discovery import discover_terms_and_privacy
from ingestion.terms_evaluation import evaluate_terms_and_conditions


def normalize_url(url: str) -> tuple[str, str]:
    """Extract base URL and publisher name from URL."""
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    publisher_name = parsed_url.netloc.replace("www.", "")
    return base_url, publisher_name


def create_waf_report(publisher: Publisher, base_url: str) -> Dict[str, Any]:
    """Create WAF report for publisher."""
    try:
        waf_report = WAFReport.create_from_url_scan(publisher, base_url)
        if waf_report:
            logger.info(
                f"WAF scan completed - Detected: {waf_report.detected}, Firewall: {waf_report.firewall}"
            )
            return {
                "waf_detected": waf_report.detected,
                "waf_firewall": waf_report.firewall,
            }

        logger.warning(f"WAF scan failed for {base_url}")
        return {"waf_detected": False, "waf_firewall": None}

    except Exception as e:
        logger.error(f"WAF scan error for {base_url}: {e}")
        return {"waf_detected": False, "waf_firewall": None, "waf_error": str(e)}


def create_terms_discovery(publisher: Publisher, base_url: str) -> Dict[str, Any]:
    """Create terms discovery result for publisher."""
    try:
        logger.info(f"Starting terms discovery for {base_url}")
        terms_discovery = discover_terms_and_privacy(base_url)

        # Save to database
        TermsDiscoveryResult.objects.update_or_create(
            publisher=publisher,
            defaults={
                "terms_of_service_url": str(terms_discovery.terms_of_service_url)
                if terms_discovery.terms_of_service_url
                else None,
                "confidence_score": terms_discovery.confidence_score,
                "notes": terms_discovery.notes,
            },
        )

        logger.info(
            f"Terms discovery completed - ToS: {terms_discovery.terms_of_service_url}"
        )

        return {
            "terms_of_service_url": str(terms_discovery.terms_of_service_url)
            if terms_discovery.terms_of_service_url
            else None,
            "confidence_score": terms_discovery.confidence_score,
            "notes": terms_discovery.notes,
        }

    except Exception as e:
        logger.error(f"Terms discovery error for {base_url}: {e}")
        return {"terms_discovery_error": str(e)}


def create_terms_evaluation(
    publisher: Publisher, terms_discovery_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Create terms evaluation result for publisher."""
    try:
        # Get terms URLs from discovery data
        terms_urls = []
        if terms_discovery_data.get("terms_of_service_url"):
            terms_urls.append(terms_discovery_data["terms_of_service_url"])

        if not terms_urls:
            logger.warning("No terms URLs found for evaluation")
            return {"terms_evaluation_error": "No terms URLs found for evaluation"}

        # Evaluate the first terms URL (prioritize ToS over Privacy Policy)
        terms_url = terms_urls[0]
        logger.info(f"Evaluating terms at: {terms_url}")

        terms_evaluation = evaluate_terms_and_conditions(terms_url)

        # Save to database
        TermsEvaluationResult.objects.update_or_create(
            publisher=publisher,
            defaults={
                "permissions": [
                    perm.model_dump() for perm in terms_evaluation.permissions
                ],
                "territorial_exceptions": terms_evaluation.territorial_exceptions,
                "arbitration_clauses": terms_evaluation.arbitration_clauses,
                "document_type": terms_evaluation.document_type,
                "confidence_score": terms_evaluation.confidence_score,
            },
        )

        logger.info(
            f"Terms evaluation completed - {len(terms_evaluation.permissions)} permissions analyzed"
        )

        return {
            "permissions": [perm.model_dump() for perm in terms_evaluation.permissions],
            "territorial_exceptions": terms_evaluation.territorial_exceptions,
            "arbitration_clauses": terms_evaluation.arbitration_clauses,
            "document_type": terms_evaluation.document_type,
            "confidence_score": terms_evaluation.confidence_score,
        }

    except Exception as e:
        logger.error(f"Terms evaluation error: {e}")
        return {"terms_evaluation_error": str(e)}


@job("default", timeout=600)
def analyze_url(url: str) -> Dict[str, Any]:
    """
    Analyze a URL to create/update publisher information including WAF detection,
    terms discovery, and terms evaluation.

    Args:
        url: The URL to analyze

    Returns:
        Dict containing analysis results including publisher info and success status
    """
    logger.info(f"Starting analysis for URL: {url}")

    try:
        # Normalize URL
        base_url, publisher_name = normalize_url(url)
        logger.debug(f"Base URL extracted: {base_url}")

        # Database operations in transaction
        with transaction.atomic():
            # Get or create publisher
            publisher, created = Publisher.objects.get_or_create(
                url=base_url, defaults={"name": publisher_name}
            )

            if created:
                logger.info(f"Created new publisher: {publisher.name}")
            else:
                logger.info(f"Found existing publisher: {publisher.name}")

            # Initialize results
            results = {
                "publisher_id": publisher.id,
                "publisher_name": publisher.name,
                "base_url": base_url,
                "created": created,
                "timestamp": timezone.now().isoformat(),
            }

            # Process WAF scan
            waf_results = create_waf_report(publisher, base_url)
            results.update(waf_results)

            # Process terms discovery
            terms_discovery_data = create_terms_discovery(publisher, base_url)
            if "terms_discovery_error" not in terms_discovery_data:
                results["terms_discovery"] = terms_discovery_data

                # Process terms evaluation (depends on discovery results)
                terms_evaluation_data = create_terms_evaluation(
                    publisher, terms_discovery_data
                )
                if "terms_evaluation_error" not in terms_evaluation_data:
                    results["terms_evaluation"] = terms_evaluation_data
                else:
                    results.update(terms_evaluation_data)
            else:
                results.update(terms_discovery_data)

            results["success"] = True
            logger.info(f"Analysis completed successfully for {url}")
            return results

    except Exception as e:
        logger.error(f"Analysis failed for {url}: {e}")
        return {
            "success": False,
            "error": str(e),
            "url": url,
            "timestamp": timezone.now().isoformat(),
        }
