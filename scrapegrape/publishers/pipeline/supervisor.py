"""Pipeline supervisor: single RQ job that runs all steps sequentially."""

from django.utils import timezone
from django_rq import job
from loguru import logger

from publishers.fetchers.exceptions import AllStrategiesExhausted
from publishers.fetchers.manager import FetchStrategyManager
from publishers.models import ArticleMetadata, ResolutionJob
from publishers.pipeline.events import publish_step_event
from publishers.pipeline.steps import (
    run_ai_bot_blocking_step,
    run_article_extraction_step,
    run_metadata_profile_step,
    run_paywall_detection_step,
    run_publisher_details_step,
    run_robots_step,
    run_rss_step,
    run_rsl_step,
    run_sitemap_step,
    run_tos_discovery_step,
    run_tos_evaluation_step,
    run_waf_step,
    should_skip_publisher_steps,
)


_fetch_manager = FetchStrategyManager()


def _fetch_homepage_html(publisher):
    """Fetch publisher homepage HTML. Returns (html, headers) tuple."""
    try:
        result = _fetch_manager.fetch(
            f"https://{publisher.domain}/", publisher=publisher
        )
        return result.html, {}
    except AllStrategiesExhausted as exc:
        logger.warning(f"Could not fetch homepage for {publisher.domain}: {exc}")
        return "", {}


def _should_skip_article_steps(article_url: str) -> bool:
    """Return True if this article URL was analyzed within ARTICLE_FRESHNESS_TTL."""
    from django.conf import settings

    recent = ArticleMetadata.objects.filter(
        article_url=article_url,
        created_at__gte=timezone.now() - settings.ARTICLE_FRESHNESS_TTL,
    ).first()
    return recent is not None


@job("default", timeout=600)
def run_pipeline(job_id: str):
    """Pipeline supervisor: runs all steps sequentially for a ResolutionJob.

    1. Loads the job and sets status to 'running'.
    2. Publishes publisher_resolution completed event.
    3. Checks freshness TTL -- skips steps if publisher was recently checked.
    4. Runs WAF, ToS discovery, ToS evaluation steps sequentially.
    5. Saves each step result on the ResolutionJob and publishes events.
    6. Updates publisher flat fields and freshness timestamp.
    7. Sets status to 'completed' (or 'failed' on exception).
    """
    resolution_job = ResolutionJob.objects.select_related("publisher").get(id=job_id)
    resolution_job.status = "running"
    resolution_job.save(update_fields=["status"])
    publisher = resolution_job.publisher

    try:
        # homepage_html is set by publisher steps; initialise for the
        # article-steps branch that may run even when publisher steps are skipped.
        homepage_html = ""

        # Step 0: Publisher details starts (resolution data available immediately)
        publish_step_event(
            job_id,
            "publisher_details",
            "started",
            {"publisher_name": publisher.name, "domain": publisher.domain},
        )

        # Check freshness TTL
        if should_skip_publisher_steps(publisher):
            logger.info(
                f"Skipping publisher steps for {publisher.domain} (fresh)"
            )
            publish_step_event(job_id, "waf", "skipped", {"reason": "fresh"})
            publish_step_event(
                job_id, "tos_discovery", "skipped", {"reason": "fresh"}
            )
            publish_step_event(
                job_id, "tos_evaluation", "skipped", {"reason": "fresh"}
            )
            publish_step_event(job_id, "robots", "skipped", {"reason": "fresh"})
            publish_step_event(job_id, "ai_bot_blocking", "skipped", {"reason": "fresh"})
            publish_step_event(job_id, "sitemap", "skipped", {"reason": "fresh"})
            publish_step_event(job_id, "rss", "skipped", {"reason": "fresh"})
            publish_step_event(job_id, "rsl", "skipped", {"reason": "fresh"})
            publish_step_event(job_id, "publisher_details", "skipped", {"reason": "fresh"})
        else:
            # Step 1: WAF check
            publish_step_event(job_id, "waf", "started")
            waf_result = run_waf_step(publisher)
            resolution_job.waf_result = waf_result
            resolution_job.save(update_fields=["waf_result"])
            publish_step_event(job_id, "waf", "completed", waf_result)

            # Update publisher flat fields
            publisher.waf_detected = waf_result.get("waf_detected", False)
            publisher.waf_type = waf_result.get("waf_type", "")
            publisher.save(update_fields=["waf_detected", "waf_type"])

            # Step 2: ToS discovery
            publish_step_event(job_id, "tos_discovery", "started")
            tos_discovery_result = run_tos_discovery_step(publisher)
            resolution_job.tos_result = tos_discovery_result
            resolution_job.save(update_fields=["tos_result"])
            publish_step_event(
                job_id, "tos_discovery", "completed", tos_discovery_result
            )

            # Update publisher flat field
            tos_url = tos_discovery_result.get("tos_url")
            if tos_url:
                publisher.tos_url = tos_url
                publisher.save(update_fields=["tos_url"])

            # Step 3: ToS evaluation
            publish_step_event(job_id, "tos_evaluation", "started")
            tos_eval_result = run_tos_evaluation_step(publisher, tos_url)

            # Merge evaluation data into existing tos_result
            if resolution_job.tos_result:
                resolution_job.tos_result.update(tos_eval_result)
            else:
                resolution_job.tos_result = tos_eval_result
            resolution_job.save(update_fields=["tos_result"])
            publish_step_event(
                job_id, "tos_evaluation", "completed", tos_eval_result
            )

            # Update publisher flat fields
            permissions = tos_eval_result.get("permissions")
            if permissions is not None:
                publisher.tos_permissions = permissions
                publisher.save(update_fields=["tos_permissions"])

            # Step 4: robots.txt + URL allowance
            publish_step_event(job_id, "robots", "started")
            robots_result = run_robots_step(publisher, resolution_job.canonical_url)
            resolution_job.robots_result = robots_result
            resolution_job.save(update_fields=["robots_result"])
            publish_step_event(job_id, "robots", "completed", robots_result)

            # Update publisher flat fields
            publisher.robots_txt_found = robots_result.get("robots_found", False)
            publisher.save(update_fields=["robots_txt_found"])

            # Step 5: AI bot blocking detection
            publish_step_event(job_id, "ai_bot_blocking", "started")
            ai_bot_result = run_ai_bot_blocking_step(publisher, robots_result)
            resolution_job.ai_bot_result = ai_bot_result
            resolution_job.save(update_fields=["ai_bot_result"])
            publish_step_event(job_id, "ai_bot_blocking", "completed", ai_bot_result)

            publisher.ai_bot_blocks = ai_bot_result.get("bots")
            publisher.save(update_fields=["ai_bot_blocks"])

            # Step 6: Sitemap discovery
            publish_step_event(job_id, "sitemap", "started")
            sitemap_result = run_sitemap_step(publisher, robots_result)
            resolution_job.sitemap_result = sitemap_result
            resolution_job.save(update_fields=["sitemap_result"])
            publish_step_event(job_id, "sitemap", "completed", sitemap_result)

            publisher.sitemap_urls = sitemap_result.get("sitemap_urls", [])
            publisher.save(update_fields=["sitemap_urls"])

            # Fetch homepage HTML once for RSS and RSL steps
            homepage_html, homepage_headers = _fetch_homepage_html(publisher)

            # Step 6: RSS feed discovery
            publish_step_event(job_id, "rss", "started")
            rss_result = run_rss_step(publisher, homepage_html)
            resolution_job.rss_result = rss_result
            resolution_job.save(update_fields=["rss_result"])
            publish_step_event(job_id, "rss", "completed", rss_result)

            publisher.rss_urls = [f["url"] for f in rss_result.get("feeds", [])]
            publisher.save(update_fields=["rss_urls"])

            # Step 7: RSL detection
            publish_step_event(job_id, "rsl", "started")
            rsl_result = run_rsl_step(
                publisher, robots_result, homepage_html, homepage_headers
            )
            resolution_job.rsl_result = rsl_result
            resolution_job.save(update_fields=["rsl_result"])
            publish_step_event(job_id, "rsl", "completed", rsl_result)

            publisher.rsl_detected = rsl_result.get("rsl_detected", False)
            publisher.save(update_fields=["rsl_detected"])

            # Step 8: Publisher details (structured data — already "started" at pipeline begin)
            details_result = run_publisher_details_step(publisher, homepage_html)
            resolution_job.metadata_result = details_result
            resolution_job.save(update_fields=["metadata_result"])
            publish_step_event(job_id, "publisher_details", "completed", details_result)

            publisher.publisher_details = details_result.get("organization")
            update_fields = ["publisher_details"]

            # Update publisher name from structured data if still set to domain
            org = details_result.get("organization")
            if org and org.get("name") and publisher.name == publisher.domain:
                publisher.name = org["name"]
                update_fields.append("name")

            publisher.save(update_fields=update_fields)

            # Update freshness timestamp
            publisher.last_checked_at = timezone.now()
            publisher.save(update_fields=["last_checked_at"])

        # --- Article-level steps ---
        article_url = resolution_job.canonical_url

        if _should_skip_article_steps(article_url):
            publish_step_event(job_id, "article_extraction", "skipped", {"reason": "fresh"})
            publish_step_event(job_id, "paywall_detection", "skipped", {"reason": "fresh"})
            publish_step_event(job_id, "metadata_profile", "skipped", {"reason": "fresh"})
        else:
            # Fetch article HTML (reuse homepage_html if article URL matches homepage)
            homepage_url = publisher.url or f"https://{publisher.domain}/"
            if article_url.rstrip("/") == homepage_url.rstrip("/"):
                article_html = homepage_html  # Already fetched above
            else:
                try:
                    fetch_result = _fetch_manager.fetch(article_url, publisher=publisher)
                    article_html = fetch_result.html
                except AllStrategiesExhausted as exc:
                    logger.warning(f"Could not fetch article {article_url}: {exc}")
                    article_html = ""

            # Step 10: Article extraction
            publish_step_event(job_id, "article_extraction", "started")
            extraction_result = run_article_extraction_step(article_html, article_url)

            # Step 11: Paywall detection
            publish_step_event(job_id, "paywall_detection", "started")
            paywall_result = run_paywall_detection_step(article_html, extraction_result)

            # Step 12: Metadata profile
            publish_step_event(job_id, "metadata_profile", "started")
            profile_result = run_metadata_profile_step(extraction_result, article_url)

            # Combine into article_result
            article_result = {
                **extraction_result,
                "paywall": paywall_result,
                "profile": profile_result,
            }
            resolution_job.article_result = article_result
            resolution_job.save(update_fields=["article_result"])

            # Create ArticleMetadata record
            ArticleMetadata.objects.create(
                resolution_job=resolution_job,
                publisher=publisher,
                article_url=article_url,
                jsonld_fields=extraction_result.get("jsonld_fields"),
                opengraph_fields=extraction_result.get("opengraph_fields"),
                microdata_fields=extraction_result.get("microdata_fields"),
                twitter_cards=extraction_result.get("twitter_cards"),
                has_jsonld=bool(extraction_result.get("jsonld_fields")),
                has_opengraph=bool(extraction_result.get("opengraph_fields")),
                has_microdata=bool(extraction_result.get("microdata_fields")),
                has_twitter_cards=bool(extraction_result.get("twitter_cards")),
                paywall_status=paywall_result.get("paywall_status", "unknown"),
                paywall_signals=paywall_result.get("signals", []),
                metadata_profile=profile_result.get("summary", ""),
            )

            # Update publisher-level paywall signal (latest article's status)
            publisher.has_paywall = paywall_result.get("paywall_status") in ("paywalled", "metered")
            publisher.save(update_fields=["has_paywall"])

            # Publish completion events with summaries
            fields_found = extraction_result.get("formats_found", [])
            extraction_summary = f"{len(fields_found)} format(s): {', '.join(fields_found)}" if fields_found else "No structured data found"
            publish_step_event(job_id, "article_extraction", "completed", {**extraction_result, "summary": extraction_summary})

            paywall_summary = f"Status: {paywall_result.get('paywall_status', 'unknown')}"
            if paywall_result.get("schema_accessible") is not None:
                paywall_summary += f" (isAccessibleForFree: {paywall_result['schema_accessible']})"
            publish_step_event(job_id, "paywall_detection", "completed", {**paywall_result, "summary": paywall_summary})

            profile_summary_text = profile_result.get("summary", "")[:50]
            if len(profile_result.get("summary", "")) > 50:
                profile_summary_text += "..."
            publish_step_event(job_id, "metadata_profile", "completed", {**profile_result, "summary": profile_summary_text})

        # Mark job complete
        resolution_job.status = "completed"
        resolution_job.save(update_fields=["status"])
        publish_step_event(job_id, "pipeline", "completed")

    except Exception as exc:
        logger.error(f"Pipeline failed for job {job_id}: {exc}")
        resolution_job.status = "failed"
        resolution_job.save(update_fields=["status"])
        publish_step_event(job_id, "pipeline", "failed", {"error": str(exc)})
        raise
