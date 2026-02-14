"""Pipeline supervisor: single RQ job that runs all steps sequentially."""

from django.utils import timezone
from django_rq import job
from loguru import logger

from publishers.models import ResolutionJob
from publishers.pipeline.events import publish_step_event
from publishers.pipeline.steps import (
    run_robots_step,
    run_sitemap_step,
    run_tos_discovery_step,
    run_tos_evaluation_step,
    run_waf_step,
    should_skip_publisher_steps,
)


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
        # Step 0: Publisher resolution (already done at job creation)
        publish_step_event(
            job_id,
            "publisher_resolution",
            "completed",
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
            publish_step_event(job_id, "sitemap", "skipped", {"reason": "fresh"})
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
            publisher.robots_txt_url_allowed = robots_result.get("url_allowed")
            publisher.save(
                update_fields=["robots_txt_found", "robots_txt_url_allowed"]
            )

            # Step 5: Sitemap discovery
            publish_step_event(job_id, "sitemap", "started")
            sitemap_result = run_sitemap_step(publisher, robots_result)
            resolution_job.sitemap_result = sitemap_result
            resolution_job.save(update_fields=["sitemap_result"])
            publish_step_event(job_id, "sitemap", "completed", sitemap_result)

            publisher.sitemap_urls = sitemap_result.get("sitemap_urls", [])
            publisher.save(update_fields=["sitemap_urls"])

            # Update freshness timestamp
            publisher.last_checked_at = timezone.now()
            publisher.save(update_fields=["last_checked_at"])

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
