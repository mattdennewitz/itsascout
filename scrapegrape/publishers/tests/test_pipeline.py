"""Tests for the pipeline supervisor, step functions, and event publishing."""

import json
from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from django.utils import timezone

from publishers.factories import PublisherFactory, ResolutionJobFactory
from publishers.fetchers.base import FetchResult
from publishers.fetchers.exceptions import AllStrategiesExhausted
from publishers.models import ArticleMetadata


# ---------------------------------------------------------------------------
# TestPublishStepEvent
# ---------------------------------------------------------------------------


class TestPublishStepEvent:
    def test_publish_step_event_sends_to_redis_channel(self, monkeypatch):
        """publish_step_event publishes JSON payload to job:{id}:events channel."""
        mock_redis_instance = MagicMock()
        mock_redis_cls = MagicMock(return_value=mock_redis_instance)
        monkeypatch.setattr("publishers.pipeline.events.redis.Redis", mock_redis_cls)

        from publishers.pipeline.events import publish_step_event

        job_id = "abc-123"
        publish_step_event(job_id, "waf", "completed", {"waf_detected": True})

        mock_redis_instance.publish.assert_called_once()
        call_args = mock_redis_instance.publish.call_args
        channel = call_args[0][0]
        payload = json.loads(call_args[0][1])

        assert channel == "job:abc-123:events"
        assert payload["step"] == "waf"
        assert payload["status"] == "completed"
        assert payload["data"]["waf_detected"] is True


# ---------------------------------------------------------------------------
# TestShouldSkipPublisherSteps
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestShouldSkipPublisherSteps:
    def test_skip_when_recently_checked(self):
        """Publisher checked 1 hour ago should be skipped (within 24h TTL)."""
        from publishers.pipeline.steps import should_skip_publisher_steps

        publisher = PublisherFactory(
            last_checked_at=timezone.now() - timedelta(hours=1)
        )
        assert should_skip_publisher_steps(publisher) is True

    def test_no_skip_when_stale(self):
        """Publisher checked 25 hours ago should NOT be skipped."""
        from publishers.pipeline.steps import should_skip_publisher_steps

        publisher = PublisherFactory(
            last_checked_at=timezone.now() - timedelta(hours=25)
        )
        assert should_skip_publisher_steps(publisher) is False

    def test_no_skip_when_never_checked(self):
        """Publisher never checked (last_checked_at=None) should NOT be skipped."""
        from publishers.pipeline.steps import should_skip_publisher_steps

        publisher = PublisherFactory(last_checked_at=None)
        assert should_skip_publisher_steps(publisher) is False


# ---------------------------------------------------------------------------
# TestRunWafStep
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRunWafStep:
    def test_waf_step_detected(self, monkeypatch):
        """WAF step returns waf_detected=True when wafw00f detects a WAF."""
        from publishers.pipeline.steps import run_waf_step

        mock_scan = {
            "report": [
                {
                    "detected": True,
                    "firewall": "Cloudflare",
                    "manufacturer": "Cloudflare Inc.",
                    "url": "https://example.com",
                }
            ]
        }
        monkeypatch.setattr(
            "publishers.pipeline.steps.scan_url_with_wafw00f",
            lambda url: mock_scan,
        )
        publisher = PublisherFactory()
        result = run_waf_step(publisher)
        assert result["waf_detected"] is True
        assert result["waf_type"] == "Cloudflare"

    def test_waf_step_not_detected(self, monkeypatch):
        """WAF step returns waf_detected=False when no WAF found."""
        from publishers.pipeline.steps import run_waf_step

        mock_scan = {
            "report": [
                {
                    "detected": False,
                    "firewall": "None",
                    "manufacturer": "",
                    "url": "https://example.com",
                }
            ]
        }
        monkeypatch.setattr(
            "publishers.pipeline.steps.scan_url_with_wafw00f",
            lambda url: mock_scan,
        )
        publisher = PublisherFactory()
        result = run_waf_step(publisher)
        assert result["waf_detected"] is False

    def test_waf_step_scan_failure(self, monkeypatch):
        """WAF step returns error when scan returns None."""
        from publishers.pipeline.steps import run_waf_step

        monkeypatch.setattr(
            "publishers.pipeline.steps.scan_url_with_wafw00f",
            lambda url: None,
        )
        publisher = PublisherFactory()
        result = run_waf_step(publisher)
        assert result["waf_detected"] is False
        assert "error" in result


# ---------------------------------------------------------------------------
# TestRunTosDiscoveryStep
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRunTosDiscoveryStep:
    def test_tos_discovery_finds_url(self, monkeypatch):
        """ToS discovery returns tos_url and confidence when URL found."""
        from publishers.pipeline.steps import run_tos_discovery_step

        mock_result = MagicMock()
        mock_result.terms_of_service_url = "https://example.com/tos"
        mock_result.confidence_score = 0.9
        mock_result.notes = "Found via link"

        monkeypatch.setattr(
            "publishers.pipeline.steps.discover_terms_and_privacy",
            lambda url, publisher=None: mock_result,
        )
        publisher = PublisherFactory()
        result = run_tos_discovery_step(publisher)
        assert result["tos_url"] == "https://example.com/tos"
        assert result["confidence"] == 0.9

    def test_tos_discovery_no_url_found(self, monkeypatch):
        """ToS discovery returns tos_url=None when no URL found."""
        from publishers.pipeline.steps import run_tos_discovery_step

        mock_result = MagicMock()
        mock_result.terms_of_service_url = None
        mock_result.confidence_score = 0.1
        mock_result.notes = "No ToS link found"

        monkeypatch.setattr(
            "publishers.pipeline.steps.discover_terms_and_privacy",
            lambda url, publisher=None: mock_result,
        )
        publisher = PublisherFactory()
        result = run_tos_discovery_step(publisher)
        assert result["tos_url"] is None


# ---------------------------------------------------------------------------
# TestRunTosEvaluationStep
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRunTosEvaluationStep:
    def test_tos_evaluation_returns_permissions(self, monkeypatch):
        """ToS evaluation returns permissions list and document type."""
        from publishers.pipeline.steps import run_tos_evaluation_step

        mock_permission = MagicMock()
        mock_permission.activity = "scraping"
        mock_permission.permission = "allowed"
        mock_permission.notes = "Permitted under fair use"
        mock_permission.model_dump = MagicMock(
            return_value={
                "activity": "scraping",
                "permission": "allowed",
                "notes": "Permitted under fair use",
            }
        )

        mock_result = MagicMock()
        mock_result.permissions = [mock_permission]
        mock_result.confidence_score = 0.85
        mock_result.document_type = "Terms of Service"
        mock_result.territorial_exceptions = None
        mock_result.arbitration_clauses = None

        monkeypatch.setattr(
            "publishers.pipeline.steps.evaluate_terms_and_conditions",
            lambda url, publisher=None: mock_result,
        )
        publisher = PublisherFactory()
        result = run_tos_evaluation_step(publisher, tos_url="https://example.com/tos")
        assert len(result["permissions"]) == 1
        assert result["document_type"] == "Terms of Service"

    def test_tos_evaluation_no_tos_url(self):
        """ToS evaluation skips when tos_url is None."""
        from publishers.pipeline.steps import run_tos_evaluation_step

        publisher = PublisherFactory()
        result = run_tos_evaluation_step(publisher, tos_url=None)
        assert result["skipped"] is True


# ---------------------------------------------------------------------------
# TestRunAiBotBlockingStep
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRunAiBotBlockingStep:
    def test_ai_bot_blocking_all_blocked(self):
        """robots.txt with 'User-agent: * / Disallow: /' blocks all bots."""
        from publishers.pipeline.steps import run_ai_bot_blocking_step, AI_BOT_USER_AGENTS

        publisher = PublisherFactory(domain="example.com")
        robots_result = {
            "robots_found": True,
            "raw_text": "User-agent: *\nDisallow: /\n",
        }
        result = run_ai_bot_blocking_step(publisher, robots_result)
        assert result["robots_found"] is True
        assert result["blocked_count"] == len(AI_BOT_USER_AGENTS)
        assert result["total_count"] == len(AI_BOT_USER_AGENTS)
        for bot_info in result["bots"].values():
            assert bot_info["blocked"] is True

    def test_ai_bot_blocking_specific_bots(self):
        """robots.txt blocking only GPTBot and CCBot."""
        from publishers.pipeline.steps import run_ai_bot_blocking_step

        publisher = PublisherFactory(domain="example.com")
        robots_result = {
            "robots_found": True,
            "raw_text": (
                "User-agent: GPTBot\nDisallow: /\n\n"
                "User-agent: CCBot\nDisallow: /\n\n"
                "User-agent: *\nAllow: /\n"
            ),
        }
        result = run_ai_bot_blocking_step(publisher, robots_result)
        assert result["bots"]["GPTBot"]["blocked"] is True
        assert result["bots"]["CCBot"]["blocked"] is True
        assert result["bots"]["ClaudeBot"]["blocked"] is False
        assert result["blocked_count"] == 2

    def test_ai_bot_blocking_none_blocked(self):
        """Permissive robots.txt blocks no AI bots."""
        from publishers.pipeline.steps import run_ai_bot_blocking_step

        publisher = PublisherFactory(domain="example.com")
        robots_result = {
            "robots_found": True,
            "raw_text": "User-agent: *\nAllow: /\n",
        }
        result = run_ai_bot_blocking_step(publisher, robots_result)
        assert result["blocked_count"] == 0
        for bot_info in result["bots"].values():
            assert bot_info["blocked"] is False

    def test_ai_bot_blocking_no_robots(self):
        """robots_result with robots_found=False returns early."""
        from publishers.pipeline.steps import run_ai_bot_blocking_step

        publisher = PublisherFactory(domain="example.com")
        robots_result = {"robots_found": False}
        result = run_ai_bot_blocking_step(publisher, robots_result)
        assert result["robots_found"] is False
        assert result["bots"] == {}
        assert result["blocked_count"] == 0

    def test_ai_bot_blocking_wildcard_allow(self):
        """User-agent: * / Allow: / allows all bots."""
        from publishers.pipeline.steps import run_ai_bot_blocking_step

        publisher = PublisherFactory(domain="example.com")
        robots_result = {
            "robots_found": True,
            "raw_text": "User-agent: *\nAllow: /\n",
        }
        result = run_ai_bot_blocking_step(publisher, robots_result)
        assert result["blocked_count"] == 0
        assert result["total_count"] > 0


# ---------------------------------------------------------------------------
# TestRunPipeline
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRunPipeline:
    def test_pipeline_runs_all_steps(self, monkeypatch):
        """Pipeline runs all steps and sets job status to completed."""
        from publishers.pipeline.supervisor import run_pipeline

        job = ResolutionJobFactory(status="pending")
        events_published = []

        monkeypatch.setattr(
            "publishers.pipeline.supervisor.publish_step_event",
            lambda job_id, step, status, data=None: events_published.append(
                (step, status)
            ),
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_waf_step",
            lambda pub: {"waf_detected": False, "waf_type": ""},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_tos_discovery_step",
            lambda pub: {"tos_url": "https://example.com/tos", "confidence": 0.9},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_tos_evaluation_step",
            lambda pub, tos_url: {
                "permissions": [],
                "document_type": "Terms of Service",
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_robots_step",
            lambda pub, url: {"robots_found": True, "url_allowed": True},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_ai_bot_blocking_step",
            lambda pub, robots_result: {
                "robots_found": True,
                "bots": {},
                "blocked_count": 0,
                "total_count": 13,
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_sitemap_step",
            lambda pub, robots_result: {
                "sitemap_urls": [],
                "source": "none",
                "count": 0,
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor._fetch_homepage_html",
            lambda pub: ("<html></html>", {}),
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_rss_step",
            lambda pub, html: {"feeds": [], "count": 0},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_rsl_step",
            lambda pub, robots, html, headers=None: {
                "rsl_detected": False,
                "indicators": [],
                "count": 0,
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_publisher_details_step",
            lambda pub, html: {
                "found": False,
                "source": None,
                "score": 0,
                "organization": None,
                "candidate_count": 0,
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_article_extraction_step",
            lambda html, url: {
                "jsonld_fields": None,
                "opengraph_fields": None,
                "microdata_fields": None,
                "twitter_cards": None,
                "formats_found": [],
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_paywall_detection_step",
            lambda html, extraction: {
                "paywall_status": "free",
                "signals": [],
                "schema_accessible": None,
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_metadata_profile_step",
            lambda extraction, url: {"summary": "Test summary"},
        )

        run_pipeline(str(job.id))

        job.refresh_from_db()
        assert job.status == "completed"

        # Check that all steps and pipeline completion were signaled
        step_names = [s for s, _ in events_published]
        assert "waf" in step_names
        assert "tos_discovery" in step_names
        assert "tos_evaluation" in step_names
        assert "robots" in step_names
        assert "ai_bot_blocking" in step_names
        assert "sitemap" in step_names
        assert "rss" in step_names
        assert "rsl" in step_names
        assert "publisher_details" in step_names
        assert "article_extraction" in step_names
        assert "paywall_detection" in step_names
        assert "metadata_profile" in step_names
        assert "pipeline" in step_names
        assert ("pipeline", "completed") in events_published

    def test_pipeline_skips_fresh_publisher(self, monkeypatch):
        """Pipeline skips steps for publisher checked within freshness TTL
        and copies results from the most recent prior job."""
        from publishers.pipeline.supervisor import run_pipeline

        publisher = PublisherFactory(
            last_checked_at=timezone.now() - timedelta(hours=1)
        )

        # Create a prior completed job with cached results
        prior_job = ResolutionJobFactory(
            publisher=publisher,
            status="completed",
            waf_result={"waf_detected": False, "waf_type": ""},
            tos_result={"tos_url": "https://example.com/tos", "permissions": []},
            robots_result={
                "robots_found": True,
                "url_allowed": True,
                "raw_text": "User-agent: *\nAllow: /\n",
            },
            sitemap_result={"sitemap_urls": [], "count": 0},
            rss_result={"feeds": [], "count": 0},
            rsl_result={"rsl_detected": False},
            ai_bot_result={"bots": {}},
            metadata_result={"organization": None},
        )

        # Create a prior ArticleMetadata so article steps are also skipped
        ArticleMetadata.objects.create(
            resolution_job=prior_job,
            publisher=publisher,
            article_url=f"https://{publisher.domain}/article",
        )

        job = ResolutionJobFactory(
            publisher=publisher,
            status="pending",
            canonical_url=f"https://{publisher.domain}/article",
        )
        events_published = []

        monkeypatch.setattr(
            "publishers.pipeline.supervisor.publish_step_event",
            lambda job_id, step, status, data=None: events_published.append(
                (step, status)
            ),
        )

        waf_called = []
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_waf_step",
            lambda pub: waf_called.append(True) or {"waf_detected": False},
        )
        robots_called = []
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_robots_step",
            lambda pub, url: robots_called.append(True)
            or {"robots_found": False},
        )

        run_pipeline(str(job.id))

        # Step functions should NOT have been called
        assert len(waf_called) == 0
        assert len(robots_called) == 0

        # Skip events should have been published
        assert ("waf", "skipped") in events_published
        assert ("tos_discovery", "skipped") in events_published
        assert ("tos_evaluation", "skipped") in events_published
        assert ("robots", "skipped") in events_published
        assert ("ai_bot_blocking", "skipped") in events_published
        assert ("sitemap", "skipped") in events_published
        assert ("rss", "skipped") in events_published
        assert ("rsl", "skipped") in events_published
        assert ("publisher_details", "skipped") in events_published
        assert ("article_extraction", "skipped") in events_published
        assert ("paywall_detection", "skipped") in events_published
        assert ("metadata_profile", "skipped") in events_published

        # Results should have been copied from prior job
        job.refresh_from_db()
        assert job.waf_result == prior_job.waf_result
        assert job.tos_result == prior_job.tos_result
        assert job.robots_result["robots_found"] is True
        assert job.robots_result["url_allowed"] is True
        assert job.sitemap_result == prior_job.sitemap_result
        assert job.rss_result == prior_job.rss_result
        assert job.rsl_result == prior_job.rsl_result

    def test_pipeline_sets_failed_on_exception(self, monkeypatch):
        """Pipeline sets job status to failed on unhandled exception."""
        from publishers.pipeline.supervisor import run_pipeline

        job = ResolutionJobFactory(status="pending")
        events_published = []

        monkeypatch.setattr(
            "publishers.pipeline.supervisor.publish_step_event",
            lambda job_id, step, status, data=None: events_published.append(
                (step, status)
            ),
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_waf_step",
            lambda pub: (_ for _ in ()).throw(Exception("network error")),
        )

        with pytest.raises(Exception, match="network error"):
            run_pipeline(str(job.id))

        job.refresh_from_db()
        assert job.status == "failed"
        assert ("pipeline", "failed") in events_published

    def test_pipeline_saves_step_results(self, monkeypatch):
        """Pipeline saves step results to the ResolutionJob."""
        from publishers.pipeline.supervisor import run_pipeline

        job = ResolutionJobFactory(status="pending")

        monkeypatch.setattr(
            "publishers.pipeline.supervisor.publish_step_event",
            lambda job_id, step, status, data=None: None,
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_waf_step",
            lambda pub: {"waf_detected": True, "waf_type": "Cloudflare"},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_tos_discovery_step",
            lambda pub: {"tos_url": "https://example.com/tos", "confidence": 0.9},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_tos_evaluation_step",
            lambda pub, tos_url: {
                "permissions": [{"activity": "scraping", "permission": "allowed"}],
                "document_type": "Terms of Service",
                "confidence_score": 0.85,
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_robots_step",
            lambda pub, url: {
                "robots_found": True,
                "url_allowed": True,
                "sitemaps_from_robots": [],
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_ai_bot_blocking_step",
            lambda pub, robots_result: {
                "robots_found": True,
                "bots": {"GPTBot": {"company": "OpenAI", "blocked": True}},
                "blocked_count": 1,
                "total_count": 13,
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_sitemap_step",
            lambda pub, robots_result: {
                "sitemap_urls": ["https://example.com/sitemap.xml"],
                "source": "probe",
                "count": 1,
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor._fetch_homepage_html",
            lambda pub: ("<html></html>", {}),
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_rss_step",
            lambda pub, html: {
                "feeds": [{"url": "https://example.com/feed", "type": "application/rss+xml", "title": ""}],
                "count": 1,
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_rsl_step",
            lambda pub, robots, html, headers=None: {
                "rsl_detected": True,
                "indicators": [{"source": "robots.txt", "url": "https://example.com/license.xml"}],
                "count": 1,
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_publisher_details_step",
            lambda pub, html: {
                "found": True,
                "source": "json-ld",
                "score": 5,
                "organization": {"name": "Example News", "type": "Organization"},
                "candidate_count": 1,
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_article_extraction_step",
            lambda html, url: {
                "jsonld_fields": {"headline": "Test"},
                "opengraph_fields": None,
                "microdata_fields": None,
                "twitter_cards": None,
                "formats_found": ["json-ld"],
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_paywall_detection_step",
            lambda html, extraction: {
                "paywall_status": "free",
                "signals": [],
                "schema_accessible": None,
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_metadata_profile_step",
            lambda extraction, url: {"summary": "Test"},
        )

        run_pipeline(str(job.id))

        job.refresh_from_db()
        assert job.waf_result["waf_detected"] is True
        assert job.waf_result["waf_type"] == "Cloudflare"
        assert job.tos_result["tos_url"] == "https://example.com/tos"
        assert "permissions" in job.tos_result
        assert job.robots_result["robots_found"] is True
        assert job.ai_bot_result["blocked_count"] == 1
        assert job.ai_bot_result["bots"]["GPTBot"]["blocked"] is True
        assert job.sitemap_result["sitemap_urls"] == [
            "https://example.com/sitemap.xml"
        ]
        assert job.rss_result["count"] == 1
        assert job.rsl_result["rsl_detected"] is True
        assert job.metadata_result["found"] is True
        assert job.metadata_result["organization"]["name"] == "Example News"

    def test_pipeline_updates_publisher_robots_and_sitemap_fields(self, monkeypatch):
        """Pipeline updates publisher flat fields for robots and sitemap."""
        from publishers.pipeline.supervisor import run_pipeline

        job = ResolutionJobFactory(status="pending")

        monkeypatch.setattr(
            "publishers.pipeline.supervisor.publish_step_event",
            lambda job_id, step, status, data=None: None,
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_waf_step",
            lambda pub: {"waf_detected": False, "waf_type": ""},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_tos_discovery_step",
            lambda pub: {"tos_url": None},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_tos_evaluation_step",
            lambda pub, tos_url: {"skipped": True},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_robots_step",
            lambda pub, url: {
                "robots_found": True,
                "url_allowed": True,
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_ai_bot_blocking_step",
            lambda pub, robots_result: {
                "robots_found": True,
                "bots": {},
                "blocked_count": 0,
                "total_count": 13,
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_sitemap_step",
            lambda pub, robots_result: {
                "sitemap_urls": ["https://example.com/sitemap.xml"],
                "source": "probe",
                "count": 1,
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor._fetch_homepage_html",
            lambda pub: ("<html></html>", {}),
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_rss_step",
            lambda pub, html: {"feeds": [], "count": 0},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_rsl_step",
            lambda pub, robots, html, headers=None: {
                "rsl_detected": False,
                "indicators": [],
                "count": 0,
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_publisher_details_step",
            lambda pub, html: {
                "found": False,
                "source": None,
                "score": 0,
                "organization": None,
                "candidate_count": 0,
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_article_extraction_step",
            lambda html, url: {"jsonld_fields": None, "opengraph_fields": None, "microdata_fields": None, "twitter_cards": None, "formats_found": []},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_paywall_detection_step",
            lambda html, extraction: {"paywall_status": "free", "signals": [], "schema_accessible": None},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_metadata_profile_step",
            lambda extraction, url: {"summary": ""},
        )

        run_pipeline(str(job.id))

        publisher = job.publisher
        publisher.refresh_from_db()
        assert publisher.robots_txt_found is True
        assert publisher.sitemap_urls == ["https://example.com/sitemap.xml"]

    def test_pipeline_updates_publisher_rss_and_rsl_fields(self, monkeypatch):
        """Pipeline updates publisher flat fields for rss_urls and rsl_detected."""
        from publishers.pipeline.supervisor import run_pipeline

        job = ResolutionJobFactory(status="pending")

        monkeypatch.setattr(
            "publishers.pipeline.supervisor.publish_step_event",
            lambda job_id, step, status, data=None: None,
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_waf_step",
            lambda pub: {"waf_detected": False, "waf_type": ""},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_tos_discovery_step",
            lambda pub: {"tos_url": None},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_tos_evaluation_step",
            lambda pub, tos_url: {"skipped": True},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_robots_step",
            lambda pub, url: {"robots_found": True, "url_allowed": True},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_ai_bot_blocking_step",
            lambda pub, robots_result: {
                "robots_found": True,
                "bots": {},
                "blocked_count": 0,
                "total_count": 13,
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_sitemap_step",
            lambda pub, robots_result: {
                "sitemap_urls": [],
                "source": "none",
                "count": 0,
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor._fetch_homepage_html",
            lambda pub: ("<html></html>", {}),
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_rss_step",
            lambda pub, html: {
                "feeds": [
                    {"url": "https://example.com/feed", "type": "application/rss+xml", "title": ""},
                ],
                "count": 1,
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_rsl_step",
            lambda pub, robots, html, headers=None: {
                "rsl_detected": True,
                "indicators": [{"source": "robots.txt", "url": "https://example.com/license.xml"}],
                "count": 1,
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_publisher_details_step",
            lambda pub, html: {
                "found": False,
                "source": None,
                "score": 0,
                "organization": None,
                "candidate_count": 0,
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_article_extraction_step",
            lambda html, url: {"jsonld_fields": None, "opengraph_fields": None, "microdata_fields": None, "twitter_cards": None, "formats_found": []},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_paywall_detection_step",
            lambda html, extraction: {"paywall_status": "free", "signals": [], "schema_accessible": None},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_metadata_profile_step",
            lambda extraction, url: {"summary": ""},
        )

        run_pipeline(str(job.id))

        publisher = job.publisher
        publisher.refresh_from_db()
        assert publisher.rss_urls == ["https://example.com/feed"]
        assert publisher.rsl_detected is True

    def test_pipeline_updates_publisher_name_from_details(self, monkeypatch):
        """Pipeline updates publisher.name from structured data when name equals domain."""
        from publishers.pipeline.supervisor import run_pipeline

        publisher = PublisherFactory(
            domain="example.com", name="example.com", url="https://example.com"
        )
        job = ResolutionJobFactory(publisher=publisher, status="pending")

        monkeypatch.setattr(
            "publishers.pipeline.supervisor.publish_step_event",
            lambda job_id, step, status, data=None: None,
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_waf_step",
            lambda pub: {"waf_detected": False, "waf_type": ""},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_tos_discovery_step",
            lambda pub: {"tos_url": None},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_tos_evaluation_step",
            lambda pub, tos_url: {"skipped": True},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_robots_step",
            lambda pub, url: {"robots_found": False},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_ai_bot_blocking_step",
            lambda pub, robots_result: {
                "robots_found": False,
                "bots": {},
                "blocked_count": 0,
                "total_count": 0,
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_sitemap_step",
            lambda pub, robots_result: {
                "sitemap_urls": [],
                "source": "none",
                "count": 0,
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor._fetch_homepage_html",
            lambda pub: ("<html></html>", {}),
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_rss_step",
            lambda pub, html: {"feeds": [], "count": 0},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_rsl_step",
            lambda pub, robots, html, headers=None: {
                "rsl_detected": False,
                "indicators": [],
                "count": 0,
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_publisher_details_step",
            lambda pub, html: {
                "found": True,
                "source": "json-ld",
                "score": 5,
                "organization": {"name": "Example News", "type": "Organization"},
                "candidate_count": 1,
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_article_extraction_step",
            lambda html, url: {"jsonld_fields": None, "opengraph_fields": None, "microdata_fields": None, "twitter_cards": None, "formats_found": []},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_paywall_detection_step",
            lambda html, extraction: {"paywall_status": "free", "signals": [], "schema_accessible": None},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_metadata_profile_step",
            lambda extraction, url: {"summary": ""},
        )

        run_pipeline(str(job.id))

        publisher.refresh_from_db()
        assert publisher.name == "Example News"

    def test_pipeline_keeps_custom_publisher_name(self, monkeypatch):
        """Pipeline does NOT overwrite publisher.name when it differs from domain."""
        from publishers.pipeline.supervisor import run_pipeline

        publisher = PublisherFactory(
            domain="example.com", name="My Custom Name", url="https://example.com"
        )
        job = ResolutionJobFactory(publisher=publisher, status="pending")

        monkeypatch.setattr(
            "publishers.pipeline.supervisor.publish_step_event",
            lambda job_id, step, status, data=None: None,
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_waf_step",
            lambda pub: {"waf_detected": False, "waf_type": ""},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_tos_discovery_step",
            lambda pub: {"tos_url": None},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_tos_evaluation_step",
            lambda pub, tos_url: {"skipped": True},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_robots_step",
            lambda pub, url: {"robots_found": False},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_ai_bot_blocking_step",
            lambda pub, robots_result: {
                "robots_found": False,
                "bots": {},
                "blocked_count": 0,
                "total_count": 0,
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_sitemap_step",
            lambda pub, robots_result: {
                "sitemap_urls": [],
                "source": "none",
                "count": 0,
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor._fetch_homepage_html",
            lambda pub: ("<html></html>", {}),
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_rss_step",
            lambda pub, html: {"feeds": [], "count": 0},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_rsl_step",
            lambda pub, robots, html, headers=None: {
                "rsl_detected": False,
                "indicators": [],
                "count": 0,
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_publisher_details_step",
            lambda pub, html: {
                "found": True,
                "source": "json-ld",
                "score": 5,
                "organization": {"name": "Example News", "type": "Organization"},
                "candidate_count": 1,
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_article_extraction_step",
            lambda html, url: {"jsonld_fields": None, "opengraph_fields": None, "microdata_fields": None, "twitter_cards": None, "formats_found": []},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_paywall_detection_step",
            lambda html, extraction: {"paywall_status": "free", "signals": [], "schema_accessible": None},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_metadata_profile_step",
            lambda extraction, url: {"summary": ""},
        )

        run_pipeline(str(job.id))

        publisher.refresh_from_db()
        assert publisher.name == "My Custom Name"

    def test_pipeline_runs_article_steps(self, monkeypatch):
        """Pipeline runs article steps and creates ArticleMetadata record."""
        from publishers.pipeline.supervisor import run_pipeline

        job = ResolutionJobFactory(status="pending")
        events_published = []

        monkeypatch.setattr(
            "publishers.pipeline.supervisor.publish_step_event",
            lambda job_id, step, status, data=None: events_published.append(
                (step, status)
            ),
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_waf_step",
            lambda pub: {"waf_detected": False, "waf_type": ""},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_tos_discovery_step",
            lambda pub: {"tos_url": None},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_tos_evaluation_step",
            lambda pub, tos_url: {"skipped": True},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_robots_step",
            lambda pub, url: {"robots_found": False},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_ai_bot_blocking_step",
            lambda pub, robots_result: {"robots_found": False, "bots": {}, "blocked_count": 0, "total_count": 0},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_sitemap_step",
            lambda pub, robots_result: {"sitemap_urls": [], "source": "none", "count": 0},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor._fetch_homepage_html",
            lambda pub: ("<html></html>", {}),
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_rss_step",
            lambda pub, html: {"feeds": [], "count": 0},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_rsl_step",
            lambda pub, robots, html, headers=None: {"rsl_detected": False, "indicators": [], "count": 0},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_publisher_details_step",
            lambda pub, html: {"found": False, "source": None, "score": 0, "organization": None, "candidate_count": 0},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_article_extraction_step",
            lambda html, url: {
                "jsonld_fields": {"headline": "Test Article"},
                "opengraph_fields": {"headline": "OG Title"},
                "microdata_fields": None,
                "twitter_cards": {"twitter:card": "summary"},
                "formats_found": ["json-ld", "opengraph", "twitter-cards"],
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_paywall_detection_step",
            lambda html, extraction: {
                "paywall_status": "paywalled",
                "signals": [],
                "schema_accessible": False,
            },
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_metadata_profile_step",
            lambda extraction, url: {"summary": "Rich metadata profile"},
        )

        run_pipeline(str(job.id))

        # Verify events for article steps
        assert ("article_extraction", "started") in events_published
        assert ("article_extraction", "completed") in events_published
        assert ("paywall_detection", "started") in events_published
        assert ("paywall_detection", "completed") in events_published
        assert ("metadata_profile", "started") in events_published
        assert ("metadata_profile", "completed") in events_published

        # Verify article_result populated on job
        job.refresh_from_db()
        assert job.article_result is not None
        assert job.article_result["jsonld_fields"]["headline"] == "Test Article"
        assert job.article_result["paywall"]["paywall_status"] == "paywalled"
        assert job.article_result["profile"]["summary"] == "Rich metadata profile"

        # Verify ArticleMetadata record created
        am = ArticleMetadata.objects.filter(resolution_job=job).first()
        assert am is not None
        assert am.article_url == job.canonical_url
        assert am.has_jsonld is True
        assert am.has_opengraph is True
        assert am.has_twitter_cards is True
        assert am.paywall_status == "paywalled"

        # Verify publisher.has_paywall updated
        job.publisher.refresh_from_db()
        assert job.publisher.has_paywall is True

    def test_pipeline_skips_fresh_article(self, monkeypatch):
        """Pipeline skips article steps when article was recently analyzed."""
        from publishers.pipeline.supervisor import run_pipeline

        job = ResolutionJobFactory(status="pending")
        events_published = []

        # Create a recent ArticleMetadata for this URL
        ArticleMetadata.objects.create(
            resolution_job=job,
            publisher=job.publisher,
            article_url=job.canonical_url,
            paywall_status="free",
        )

        monkeypatch.setattr(
            "publishers.pipeline.supervisor.publish_step_event",
            lambda job_id, step, status, data=None: events_published.append(
                (step, status)
            ),
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_waf_step",
            lambda pub: {"waf_detected": False, "waf_type": ""},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_tos_discovery_step",
            lambda pub: {"tos_url": None},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_tos_evaluation_step",
            lambda pub, tos_url: {"skipped": True},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_robots_step",
            lambda pub, url: {"robots_found": False},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_ai_bot_blocking_step",
            lambda pub, robots_result: {"robots_found": False, "bots": {}, "blocked_count": 0, "total_count": 0},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_sitemap_step",
            lambda pub, robots_result: {"sitemap_urls": [], "source": "none", "count": 0},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor._fetch_homepage_html",
            lambda pub: ("", {}),
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_rss_step",
            lambda pub, html: {"feeds": [], "count": 0},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_rsl_step",
            lambda pub, robots, html, headers=None: {"rsl_detected": False, "indicators": [], "count": 0},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_publisher_details_step",
            lambda pub, html: {"found": False, "source": None, "score": 0, "organization": None, "candidate_count": 0},
        )

        extraction_called = []
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_article_extraction_step",
            lambda html, url: extraction_called.append(True) or {"jsonld_fields": None, "opengraph_fields": None, "microdata_fields": None, "twitter_cards": None, "formats_found": []},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_paywall_detection_step",
            lambda html, extraction: {"paywall_status": "free", "signals": [], "schema_accessible": None},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_metadata_profile_step",
            lambda extraction, url: {"summary": ""},
        )

        run_pipeline(str(job.id))

        # Article step functions should NOT have been called
        assert len(extraction_called) == 0

        # Article skip events should have been published
        assert ("article_extraction", "skipped") in events_published
        assert ("paywall_detection", "skipped") in events_published
        assert ("metadata_profile", "skipped") in events_published

    def test_pipeline_reuses_homepage_html_for_article(self, monkeypatch):
        """Pipeline reuses homepage HTML when article URL matches homepage."""
        from publishers.pipeline.supervisor import run_pipeline

        publisher = PublisherFactory(
            domain="example.com", name="example.com", url="https://example.com"
        )
        # canonical_url matches homepage
        job = ResolutionJobFactory(
            publisher=publisher,
            status="pending",
            canonical_url="https://example.com/",
        )

        fetch_calls = []

        monkeypatch.setattr(
            "publishers.pipeline.supervisor.publish_step_event",
            lambda job_id, step, status, data=None: None,
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_waf_step",
            lambda pub: {"waf_detected": False, "waf_type": ""},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_tos_discovery_step",
            lambda pub: {"tos_url": None},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_tos_evaluation_step",
            lambda pub, tos_url: {"skipped": True},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_robots_step",
            lambda pub, url: {"robots_found": False},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_ai_bot_blocking_step",
            lambda pub, robots_result: {"robots_found": False, "bots": {}, "blocked_count": 0, "total_count": 0},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_sitemap_step",
            lambda pub, robots_result: {"sitemap_urls": [], "source": "none", "count": 0},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor._fetch_homepage_html",
            lambda pub: ("<html>homepage</html>", {}),
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_rss_step",
            lambda pub, html: {"feeds": [], "count": 0},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_rsl_step",
            lambda pub, robots, html, headers=None: {"rsl_detected": False, "indicators": [], "count": 0},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_publisher_details_step",
            lambda pub, html: {"found": False, "source": None, "score": 0, "organization": None, "candidate_count": 0},
        )

        # Track fetch calls on the supervisor's _fetch_manager
        original_fetch_manager = MagicMock()
        original_fetch_manager.fetch.side_effect = lambda url, publisher=None: (
            fetch_calls.append(url) or FetchResult(html="<html>fetched</html>", status_code=200, strategy_used="curl_cffi", url=url)
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor._fetch_manager",
            original_fetch_manager,
        )

        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_article_extraction_step",
            lambda html, url: {"jsonld_fields": None, "opengraph_fields": None, "microdata_fields": None, "twitter_cards": None, "formats_found": []},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_paywall_detection_step",
            lambda html, extraction: {"paywall_status": "free", "signals": [], "schema_accessible": None},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_metadata_profile_step",
            lambda extraction, url: {"summary": ""},
        )

        run_pipeline(str(job.id))

        # _fetch_manager.fetch should NOT have been called for article HTML
        # (homepage_html reused because article_url matches homepage)
        article_fetches = [u for u in fetch_calls if "example.com/" in u and u != "https://example.com/"]
        assert len(article_fetches) == 0


# ---------------------------------------------------------------------------
# TestExtractLicenseDirectives
# ---------------------------------------------------------------------------


class TestExtractLicenseDirectives:
    def test_single_license(self):
        """Single License directive is extracted."""
        from publishers.pipeline.steps import _extract_license_directives

        text = "User-agent: *\nAllow: /\nLicense: https://example.com/license.xml"
        result = _extract_license_directives(text)
        assert result == ["https://example.com/license.xml"]

    def test_multiple_licenses(self):
        """Multiple License directives are extracted."""
        from publishers.pipeline.steps import _extract_license_directives

        text = (
            "License: https://example.com/license1.xml\n"
            "License: https://example.com/license2.xml"
        )
        result = _extract_license_directives(text)
        assert len(result) == 2
        assert "https://example.com/license1.xml" in result
        assert "https://example.com/license2.xml" in result

    def test_no_license(self):
        """No License directives returns empty list."""
        from publishers.pipeline.steps import _extract_license_directives

        text = "User-agent: *\nAllow: /"
        result = _extract_license_directives(text)
        assert result == []

    def test_case_insensitive(self):
        """Lowercase 'license:' is still extracted."""
        from publishers.pipeline.steps import _extract_license_directives

        text = "license: https://example.com/license.xml"
        result = _extract_license_directives(text)
        assert result == ["https://example.com/license.xml"]


# ---------------------------------------------------------------------------
# TestRunRobotsStep
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRunRobotsStep:
    def _patch_fetch(self, monkeypatch, text):
        """Helper: patch _fetch_manager.fetch to return a FetchResult with given text."""
        mock_manager = MagicMock()
        mock_manager.fetch.return_value = FetchResult(
            html=text, status_code=200, strategy_used="curl_cffi", url=""
        )
        monkeypatch.setattr("publishers.pipeline.steps._fetch_manager", mock_manager)
        return mock_manager

    def test_robots_found_url_allowed(self, monkeypatch):
        """robots step parses robots.txt and reports url_allowed=True."""
        from publishers.pipeline.steps import run_robots_step

        self._patch_fetch(
            monkeypatch,
            "User-agent: *\nAllow: /\nSitemap: https://example.com/sitemap.xml",
        )

        publisher = PublisherFactory(domain="example.com")
        result = run_robots_step(publisher, "https://example.com/article")
        assert result["robots_found"] is True
        assert result["url_allowed"] is True
        assert "https://example.com/sitemap.xml" in result["sitemaps_from_robots"]

    def test_robots_found_url_disallowed(self, monkeypatch):
        """robots step reports url_allowed=False for disallowed path."""
        from publishers.pipeline.steps import run_robots_step

        self._patch_fetch(monkeypatch, "User-agent: *\nDisallow: /private/")

        publisher = PublisherFactory(domain="example.com")
        result = run_robots_step(publisher, "https://example.com/private/secret")
        assert result["robots_found"] is True
        assert result["url_allowed"] is False

    def test_robots_not_found(self, monkeypatch):
        """robots step returns robots_found=False when fetch fails."""
        from publishers.pipeline.steps import run_robots_step

        mock_manager = MagicMock()
        mock_manager.fetch.side_effect = AllStrategiesExhausted("all failed")
        monkeypatch.setattr("publishers.pipeline.steps._fetch_manager", mock_manager)

        publisher = PublisherFactory(domain="example.com")
        result = run_robots_step(publisher, "https://example.com/article")
        assert result["robots_found"] is False
        assert "error" in result

    def test_robots_html_challenge_page(self, monkeypatch):
        """robots step treats HTML response as WAF challenge (not found)."""
        from publishers.pipeline.steps import run_robots_step

        self._patch_fetch(
            monkeypatch, "<html><body>Challenge</body></html>"
        )

        publisher = PublisherFactory(domain="example.com")
        result = run_robots_step(publisher, "https://example.com/article")
        assert result["robots_found"] is False

    def test_robots_network_error(self, monkeypatch):
        """robots step returns robots_found=False with error on network failure."""
        from publishers.pipeline.steps import run_robots_step

        mock_manager = MagicMock()
        mock_manager.fetch.side_effect = AllStrategiesExhausted("connection refused")
        monkeypatch.setattr("publishers.pipeline.steps._fetch_manager", mock_manager)

        publisher = PublisherFactory(domain="example.com")
        result = run_robots_step(publisher, "https://example.com/article")
        assert result["robots_found"] is False
        assert "error" in result

    def test_robots_malformed_content(self, monkeypatch):
        """robots step returns robots_found=False on malformed/binary content."""
        from publishers.pipeline.steps import run_robots_step

        self._patch_fetch(monkeypatch, "\x00\x01\x02binary garbage")
        monkeypatch.setattr(
            "publishers.pipeline.steps.Protego.parse",
            lambda text: (_ for _ in ()).throw(Exception("parse error")),
        )

        publisher = PublisherFactory(domain="example.com")
        result = run_robots_step(publisher, "https://example.com/article")
        assert result["robots_found"] is False
        assert result["error"] == "malformed robots.txt"

    def test_robots_extracts_license_directives(self, monkeypatch):
        """robots step extracts License: directives from robots.txt."""
        from publishers.pipeline.steps import run_robots_step

        self._patch_fetch(
            monkeypatch,
            "User-agent: *\nAllow: /\nLicense: https://example.com/license.xml",
        )

        publisher = PublisherFactory(domain="example.com")
        result = run_robots_step(publisher, "https://example.com/article")
        assert "https://example.com/license.xml" in result["license_directives"]

    def test_robots_extracts_crawl_delay(self, monkeypatch):
        """robots step extracts Crawl-delay value."""
        from publishers.pipeline.steps import run_robots_step

        self._patch_fetch(
            monkeypatch, "User-agent: itsascout\nCrawl-delay: 5\nAllow: /"
        )

        publisher = PublisherFactory(domain="example.com")
        result = run_robots_step(publisher, "https://example.com/article")
        assert result["crawl_delay"] == 5.0


# ---------------------------------------------------------------------------
# TestRunSitemapStep
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRunSitemapStep:
    def test_sitemaps_from_robots(self):
        """sitemap step returns sitemaps from robots_result, source='robots.txt'."""
        from publishers.pipeline.steps import run_sitemap_step

        publisher = PublisherFactory(domain="example.com")
        robots_result = {
            "sitemaps_from_robots": ["https://example.com/sitemap.xml"],
        }
        result = run_sitemap_step(publisher, robots_result)
        assert "https://example.com/sitemap.xml" in result["sitemap_urls"]
        assert result["source"] == "robots.txt"
        assert result["count"] == 1

    def test_sitemaps_from_probe(self, monkeypatch):
        """sitemap step probes common paths when robots has no sitemaps."""
        from publishers.pipeline.steps import run_sitemap_step

        mock_manager = MagicMock()
        mock_manager.fetch.return_value = FetchResult(
            html='<?xml version="1.0"?><urlset></urlset>',
            status_code=200,
            strategy_used="curl_cffi",
            url="",
        )
        monkeypatch.setattr("publishers.pipeline.steps._fetch_manager", mock_manager)

        publisher = PublisherFactory(domain="example.com")
        robots_result = {"sitemaps_from_robots": []}
        result = run_sitemap_step(publisher, robots_result)
        assert result["count"] >= 1
        assert result["source"] == "probe"

    def test_no_sitemaps_found(self, monkeypatch):
        """sitemap step returns count=0, source='none' when nothing found."""
        from publishers.pipeline.steps import run_sitemap_step

        mock_manager = MagicMock()
        mock_manager.fetch.side_effect = AllStrategiesExhausted("not found")
        monkeypatch.setattr("publishers.pipeline.steps._fetch_manager", mock_manager)

        publisher = PublisherFactory(domain="example.com")
        robots_result = {}
        result = run_sitemap_step(publisher, robots_result)
        assert result["count"] == 0
        assert result["source"] == "none"

    def test_probe_stops_at_first_success(self, monkeypatch):
        """sitemap step stops probing after first successful response."""
        from publishers.pipeline.steps import run_sitemap_step

        call_count = []

        def mock_fetch(url, publisher=None):
            call_count.append(1)
            return FetchResult(
                html='<?xml version="1.0"?><urlset></urlset>',
                status_code=200,
                strategy_used="curl_cffi",
                url=url,
            )

        mock_manager = MagicMock()
        mock_manager.fetch.side_effect = mock_fetch
        monkeypatch.setattr("publishers.pipeline.steps._fetch_manager", mock_manager)

        publisher = PublisherFactory(domain="example.com")
        robots_result = {"sitemaps_from_robots": []}
        result = run_sitemap_step(publisher, robots_result)
        assert result["count"] == 1
        assert len(call_count) == 1  # Only one probe was made

    def test_relative_sitemap_urls_resolved(self):
        """sitemap step resolves relative sitemap URLs from robots.txt."""
        from publishers.pipeline.steps import run_sitemap_step

        publisher = PublisherFactory(domain="example.com")
        robots_result = {
            "sitemaps_from_robots": ["/sitemap.xml"],
        }
        result = run_sitemap_step(publisher, robots_result)
        assert "https://example.com/sitemap.xml" in result["sitemap_urls"]
        assert result["source"] == "robots.txt"

    def test_non_xml_content_skipped(self, monkeypatch):
        """sitemap step skips non-XML responses during probing."""
        from publishers.pipeline.steps import run_sitemap_step

        mock_manager = MagicMock()
        mock_manager.fetch.return_value = FetchResult(
            html="<html><body>Not a sitemap</body></html>",
            status_code=200,
            strategy_used="curl_cffi",
            url="",
        )
        monkeypatch.setattr("publishers.pipeline.steps._fetch_manager", mock_manager)

        publisher = PublisherFactory(domain="example.com")
        robots_result = {"sitemaps_from_robots": []}
        result = run_sitemap_step(publisher, robots_result)
        assert result["count"] == 0
        assert result["source"] == "none"


# ---------------------------------------------------------------------------
# TestFeedLinkParser
# ---------------------------------------------------------------------------


class TestFeedLinkParser:
    def test_finds_rss_feed(self):
        """FeedLinkParser finds <link rel="alternate" type="application/rss+xml">."""
        from publishers.pipeline.steps import FeedLinkParser

        parser = FeedLinkParser()
        parser.feed('<html><head><link rel="alternate" type="application/rss+xml" href="/feed"></head></html>')
        assert len(parser.feeds) == 1
        assert parser.feeds[0]["url"] == "/feed"
        assert parser.feeds[0]["type"] == "application/rss+xml"

    def test_finds_atom_feed(self):
        """FeedLinkParser finds atom+xml type."""
        from publishers.pipeline.steps import FeedLinkParser

        parser = FeedLinkParser()
        parser.feed('<html><head><link rel="alternate" type="application/atom+xml" href="/atom.xml" title="Atom Feed"></head></html>')
        assert len(parser.feeds) == 1
        assert parser.feeds[0]["type"] == "application/atom+xml"

    def test_ignores_non_feed_links(self):
        """FeedLinkParser ignores <link rel="stylesheet">."""
        from publishers.pipeline.steps import FeedLinkParser

        parser = FeedLinkParser()
        parser.feed('<html><head><link rel="stylesheet" href="/style.css"></head></html>')
        assert len(parser.feeds) == 0

    def test_self_closing_link_tag(self):
        """FeedLinkParser handles self-closing <link ... />."""
        from publishers.pipeline.steps import FeedLinkParser

        parser = FeedLinkParser()
        parser.feed('<html><head><link rel="alternate" type="application/rss+xml" href="/feed" /></head></html>')
        assert len(parser.feeds) == 1


# ---------------------------------------------------------------------------
# TestRunRssStep
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRunRssStep:
    def test_rss_feeds_discovered(self):
        """run_rss_step discovers RSS feed from HTML link tag."""
        from publishers.pipeline.steps import run_rss_step

        publisher = PublisherFactory(domain="example.com")
        html = '<html><head><link rel="alternate" type="application/rss+xml" href="https://example.com/feed"></head></html>'
        result = run_rss_step(publisher, html)
        assert result["count"] == 1
        assert result["feeds"][0]["url"] == "https://example.com/feed"

    def test_relative_url_resolved(self):
        """run_rss_step resolves relative feed URLs to absolute."""
        from publishers.pipeline.steps import run_rss_step

        publisher = PublisherFactory(domain="example.com")
        html = '<html><head><link rel="alternate" type="application/rss+xml" href="/feed/rss"></head></html>'
        result = run_rss_step(publisher, html)
        assert result["feeds"][0]["url"] == "https://example.com/feed/rss"

    def test_empty_html(self):
        """run_rss_step returns count=0 and error for empty HTML."""
        from publishers.pipeline.steps import run_rss_step

        publisher = PublisherFactory(domain="example.com")
        result = run_rss_step(publisher, "")
        assert result["count"] == 0
        assert "error" in result

    def test_no_feeds_in_html(self):
        """run_rss_step returns count=0 for HTML without feed links."""
        from publishers.pipeline.steps import run_rss_step

        publisher = PublisherFactory(domain="example.com")
        html = "<html><head><title>Test</title></head><body></body></html>"
        result = run_rss_step(publisher, html)
        assert result["count"] == 0
        assert len(result["feeds"]) == 0

    def test_multiple_feeds(self):
        """run_rss_step finds both RSS and Atom feeds."""
        from publishers.pipeline.steps import run_rss_step

        publisher = PublisherFactory(domain="example.com")
        html = (
            '<html><head>'
            '<link rel="alternate" type="application/rss+xml" href="/rss">'
            '<link rel="alternate" type="application/atom+xml" href="/atom">'
            '</head></html>'
        )
        result = run_rss_step(publisher, html)
        assert result["count"] == 2


# ---------------------------------------------------------------------------
# TestRSLLinkParser
# ---------------------------------------------------------------------------


class TestRSLLinkParser:
    def test_finds_rsl_link(self):
        """RSLLinkParser finds <link rel="license" type="application/rsl+xml">."""
        from publishers.pipeline.steps import RSLLinkParser

        parser = RSLLinkParser()
        parser.feed('<html><head><link rel="license" type="application/rsl+xml" href="https://example.com/license.xml"></head></html>')
        assert len(parser.urls) == 1
        assert parser.urls[0] == "https://example.com/license.xml"

    def test_ignores_non_rsl_license(self):
        """RSLLinkParser ignores <link rel="license" type="text/html">."""
        from publishers.pipeline.steps import RSLLinkParser

        parser = RSLLinkParser()
        parser.feed('<html><head><link rel="license" type="text/html" href="/license.html"></head></html>')
        assert len(parser.urls) == 0


# ---------------------------------------------------------------------------
# TestRunRslStep
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRunRslStep:
    def test_rsl_from_robots_license(self):
        """run_rsl_step detects RSL from robots.txt License directive."""
        from publishers.pipeline.steps import run_rsl_step

        publisher = PublisherFactory(domain="example.com")
        robots_result = {"license_directives": ["https://example.com/license.xml"]}
        result = run_rsl_step(publisher, robots_result, "")
        assert result["rsl_detected"] is True
        assert result["indicators"][0]["source"] == "robots.txt"

    def test_rsl_from_html_link(self):
        """run_rsl_step detects RSL from HTML link tag."""
        from publishers.pipeline.steps import run_rsl_step

        publisher = PublisherFactory(domain="example.com")
        html = '<html><head><link rel="license" type="application/rsl+xml" href="https://example.com/license.xml"></head></html>'
        result = run_rsl_step(publisher, {}, html)
        assert result["rsl_detected"] is True
        assert result["indicators"][0]["source"] == "html_link"

    def test_rsl_from_http_header(self):
        """run_rsl_step detects RSL from HTTP Link header."""
        from publishers.pipeline.steps import run_rsl_step

        publisher = PublisherFactory(domain="example.com")
        headers = {"Link": '<https://example.com/license.xml>; rel="license"; type="application/rsl+xml"'}
        result = run_rsl_step(publisher, {}, "", headers)
        assert result["rsl_detected"] is True
        assert result["indicators"][0]["source"] == "http_header"

    def test_rsl_all_three_sources(self):
        """run_rsl_step finds indicators from all three sources."""
        from publishers.pipeline.steps import run_rsl_step

        publisher = PublisherFactory(domain="example.com")
        robots_result = {"license_directives": ["https://example.com/robots-license.xml"]}
        html = '<html><head><link rel="license" type="application/rsl+xml" href="https://example.com/html-license.xml"></head></html>'
        headers = {"Link": '<https://example.com/header-license.xml>; rel="license"; type="application/rsl+xml"'}
        result = run_rsl_step(publisher, robots_result, html, headers)
        assert result["rsl_detected"] is True
        assert result["count"] == 3

    def test_rsl_not_detected(self):
        """run_rsl_step returns rsl_detected=False when no indicators."""
        from publishers.pipeline.steps import run_rsl_step

        publisher = PublisherFactory(domain="example.com")
        result = run_rsl_step(publisher, {}, "<html></html>")
        assert result["rsl_detected"] is False
        assert result["count"] == 0

    def test_rsl_resolves_relative_urls(self):
        """run_rsl_step resolves relative URLs to absolute."""
        from publishers.pipeline.steps import run_rsl_step

        publisher = PublisherFactory(domain="example.com")
        robots_result = {"license_directives": ["/rsl/license.xml"]}
        html = '<html><head><link rel="license" type="application/rsl+xml" href="/license.xml"></head></html>'
        headers = {"Link": '</header-license.xml>; rel="license"; type="application/rsl+xml"'}
        result = run_rsl_step(publisher, robots_result, html, headers)
        urls = [i["url"] for i in result["indicators"]]
        assert urls[0] == "https://example.com/rsl/license.xml"
        assert urls[1] == "https://example.com/license.xml"
        assert urls[2] == "https://example.com/header-license.xml"

    def test_rsl_empty_html_with_robots_license(self):
        """run_rsl_step detects RSL from robots.txt even with empty HTML."""
        from publishers.pipeline.steps import run_rsl_step

        publisher = PublisherFactory(domain="example.com")
        robots_result = {"license_directives": ["https://example.com/license.xml"]}
        result = run_rsl_step(publisher, robots_result, "")
        assert result["rsl_detected"] is True
        assert result["indicators"][0]["source"] == "robots.txt"


# ---------------------------------------------------------------------------
# TestRunPublisherDetailsStep
# ---------------------------------------------------------------------------

JSONLD_ORG_HTML = """
<html><head>
<script type="application/ld+json">
{
    "@context": "https://schema.org",
    "@type": "Organization",
    "name": "Example News",
    "url": "https://example.com",
    "logo": "https://example.com/logo.png",
    "sameAs": ["https://twitter.com/example"]
}
</script>
</head><body></body></html>
"""

JSONLD_NEWS_MEDIA_HTML = """
<html><head>
<script type="application/ld+json">
[
    {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "Generic Org",
        "url": "https://example.com/about"
    },
    {
        "@context": "https://schema.org",
        "@type": "NewsMediaOrganization",
        "name": "Example News Media",
        "url": "https://example.com",
        "logo": "https://example.com/logo.png"
    }
]
</script>
</head><body></body></html>
"""

JSONLD_HOMEPAGE_ID_HTML = """
<html><head>
<script type="application/ld+json">
{
    "@context": "https://schema.org",
    "@graph": [
        {
            "@type": "Organization",
            "@id": "https://example.com/",
            "name": "Homepage Org",
            "url": "https://example.com"
        },
        {
            "@type": "Organization",
            "@id": "https://example.com/#other",
            "name": "Other Org"
        }
    ]
}
</script>
</head><body></body></html>
"""

JSONLD_ARTICLE_REF_HTML = """
<html><head>
<script type="application/ld+json">
{
    "@context": "https://schema.org",
    "@graph": [
        {
            "@type": "Organization",
            "@id": "https://example.com/#organization",
            "name": "Referenced Org",
            "logo": "https://example.com/logo.png"
        },
        {
            "@type": "Article",
            "headline": "Test Article",
            "publisher": {"@id": "https://example.com/#organization"}
        }
    ]
}
</script>
</head><body></body></html>
"""

MICRODATA_ORG_HTML = """
<html><body>
<div itemscope itemtype="https://schema.org/Organization">
    <span itemprop="name">Microdata Org</span>
    <a itemprop="url" href="https://example.com">Home</a>
</div>
</body></html>
"""


@pytest.mark.django_db
class TestRunPublisherDetailsStep:
    def test_publisher_details_jsonld_organization_found(self):
        """JSON-LD with Organization returns found=True, source='json-ld'."""
        from publishers.pipeline.steps import run_publisher_details_step

        publisher = PublisherFactory(domain="example.com", url="https://example.com")
        result = run_publisher_details_step(publisher, JSONLD_ORG_HTML)
        assert result["found"] is True
        assert result["source"] == "json-ld"
        assert result["organization"]["name"] == "Example News"
        assert result["organization"]["logo"] == "https://example.com/logo.png"
        assert "https://twitter.com/example" in result["organization"]["same_as"]

    def test_publisher_details_jsonld_news_media_org_preferred(self):
        """NewsMediaOrganization scores higher than plain Organization."""
        from publishers.pipeline.steps import run_publisher_details_step

        publisher = PublisherFactory(domain="example.com", url="https://example.com")
        result = run_publisher_details_step(publisher, JSONLD_NEWS_MEDIA_HTML)
        assert result["found"] is True
        assert result["organization"]["name"] == "Example News Media"
        assert result["organization"]["type"] == "NewsMediaOrganization"
        assert result["candidate_count"] == 2

    def test_publisher_details_jsonld_homepage_url_match_scores_highest(self):
        """@id matching homepage gets +4, winning over other candidates."""
        from publishers.pipeline.steps import run_publisher_details_step

        publisher = PublisherFactory(domain="example.com", url="https://example.com/")
        result = run_publisher_details_step(publisher, JSONLD_HOMEPAGE_ID_HTML)
        assert result["found"] is True
        assert result["organization"]["name"] == "Homepage Org"

    def test_publisher_details_jsonld_referenced_by_article(self):
        """Organization referenced by Article.publisher gets +2."""
        from publishers.pipeline.steps import run_publisher_details_step

        publisher = PublisherFactory(domain="example.com", url="https://example.com")
        result = run_publisher_details_step(publisher, JSONLD_ARTICLE_REF_HTML)
        assert result["found"] is True
        assert result["organization"]["name"] == "Referenced Org"
        assert result["score"] > 0

    def test_publisher_details_microdata_fallback(self):
        """No JSON-LD orgs falls back to microdata."""
        from publishers.pipeline.steps import run_publisher_details_step

        publisher = PublisherFactory(domain="example.com", url="https://example.com")
        result = run_publisher_details_step(publisher, MICRODATA_ORG_HTML)
        assert result["found"] is True
        assert result["source"] == "microdata"
        assert result["organization"]["name"] == "Microdata Org"

    def test_publisher_details_no_structured_data(self):
        """HTML without structured data returns found=False."""
        from publishers.pipeline.steps import run_publisher_details_step

        publisher = PublisherFactory(domain="example.com", url="https://example.com")
        result = run_publisher_details_step(publisher, "<html><body>Hello</body></html>")
        assert result["found"] is False
        assert result["organization"] is None

    def test_publisher_details_empty_html(self):
        """Empty string returns found=False with error."""
        from publishers.pipeline.steps import run_publisher_details_step

        publisher = PublisherFactory(domain="example.com", url="https://example.com")
        result = run_publisher_details_step(publisher, "")
        assert result["found"] is False
        assert "error" in result

    def test_publisher_details_discards_zero_score_no_url(self):
        """score==0 + no url/id candidate is discarded."""
        from publishers.pipeline.steps import run_publisher_details_step

        html = """
        <html><head>
        <script type="application/ld+json">
        {"@context": "https://schema.org", "@type": "Organization", "name": "No URL Org"}
        </script>
        </head><body></body></html>
        """
        publisher = PublisherFactory(domain="example.com", url="https://example.com")
        result = run_publisher_details_step(publisher, html)
        assert result["found"] is False


# ---------------------------------------------------------------------------
# TestTwitterCardParser
# ---------------------------------------------------------------------------


class TestTwitterCardParser:
    def test_finds_twitter_card_tags(self):
        """HTML with twitter:card, twitter:title, twitter:image -> all extracted."""
        from publishers.pipeline.steps import TwitterCardParser

        parser = TwitterCardParser()
        parser.feed(
            '<html><head>'
            '<meta name="twitter:card" content="summary_large_image">'
            '<meta name="twitter:title" content="Test Article">'
            '<meta name="twitter:image" content="https://example.com/img.jpg">'
            '</head></html>'
        )
        assert parser.cards["twitter:card"] == "summary_large_image"
        assert parser.cards["twitter:title"] == "Test Article"
        assert parser.cards["twitter:image"] == "https://example.com/img.jpg"

    def test_ignores_non_twitter_meta(self):
        """og:title meta tag not extracted."""
        from publishers.pipeline.steps import TwitterCardParser

        parser = TwitterCardParser()
        parser.feed(
            '<html><head>'
            '<meta property="og:title" content="OG Title">'
            '<meta name="twitter:card" content="summary">'
            '</head></html>'
        )
        assert "og:title" not in parser.cards
        assert parser.cards["twitter:card"] == "summary"

    def test_self_closing_meta_tag(self):
        """<meta ... /> self-closing works."""
        from publishers.pipeline.steps import TwitterCardParser

        parser = TwitterCardParser()
        parser.feed(
            '<html><head>'
            '<meta name="twitter:title" content="Self Close" />'
            '</head></html>'
        )
        assert parser.cards["twitter:title"] == "Self Close"


# ---------------------------------------------------------------------------
# TestRunArticleExtractionStep
# ---------------------------------------------------------------------------


JSONLD_ARTICLE_HTML = """
<html><head>
<script type="application/ld+json">
{
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    "headline": "Breaking News",
    "author": {"@type": "Person", "name": "John Doe"},
    "datePublished": "2026-01-15",
    "description": "A breaking news article",
    "publisher": {"@type": "Organization", "name": "Example News"}
}
</script>
</head><body></body></html>
"""

JSONLD_GRAPH_ARTICLE_HTML = """
<html><head>
<script type="application/ld+json">
{
    "@context": "https://schema.org",
    "@graph": [
        {
            "@type": "NewsArticle",
            "headline": "Graph Article",
            "author": "Jane Smith",
            "datePublished": "2026-02-01"
        },
        {
            "@type": "Organization",
            "name": "Graph News Org"
        }
    ]
}
</script>
</head><body></body></html>
"""

OG_ARTICLE_HTML = """
<html><head>
<meta property="og:title" content="OG Title">
<meta property="og:description" content="OG Description">
<meta property="og:image" content="https://example.com/image.jpg">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Example Site">
<meta property="article:published_time" content="2026-01-15T10:00:00Z">
<meta property="article:tag" content="tech">
<meta property="article:tag" content="news">
</head><body></body></html>
"""

TWITTER_CARD_ARTICLE_HTML = """
<html><head>
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Twitter Title">
<meta name="twitter:description" content="Twitter Description">
<meta name="twitter:image" content="https://example.com/twitter-img.jpg">
</head><body></body></html>
"""

MULTI_FORMAT_HTML = """
<html><head>
<script type="application/ld+json">
{
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "Multi Format Article",
    "author": "Test Author"
}
</script>
<meta property="og:title" content="Multi Format OG">
<meta property="og:description" content="OG Desc">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="Twitter Multi">
</head><body></body></html>
"""


class TestRunArticleExtractionStep:
    def test_extracts_jsonld_article(self):
        """HTML with JSON-LD NewsArticle -> jsonld_fields has headline, author, datePublished."""
        from publishers.pipeline.steps import run_article_extraction_step

        result = run_article_extraction_step(JSONLD_ARTICLE_HTML, "https://example.com/article")
        assert result["jsonld_fields"] is not None
        assert result["jsonld_fields"]["headline"] == "Breaking News"
        assert result["jsonld_fields"]["author"] == "John Doe"
        assert result["jsonld_fields"]["datePublished"] == "2026-01-15"
        assert "json-ld" in result["formats_found"]

    def test_extracts_opengraph(self):
        """HTML with og:title, og:description -> opengraph_fields has headline, description."""
        from publishers.pipeline.steps import run_article_extraction_step

        result = run_article_extraction_step(OG_ARTICLE_HTML, "https://example.com/article")
        assert result["opengraph_fields"] is not None
        assert result["opengraph_fields"]["headline"] == "OG Title"
        assert result["opengraph_fields"]["description"] == "OG Description"
        assert "opengraph" in result["formats_found"]

    def test_extracts_twitter_cards(self):
        """HTML with twitter:card, twitter:title -> twitter_cards dict populated."""
        from publishers.pipeline.steps import run_article_extraction_step

        result = run_article_extraction_step(TWITTER_CARD_ARTICLE_HTML, "https://example.com/article")
        assert result["twitter_cards"] is not None
        assert result["twitter_cards"]["twitter:card"] == "summary_large_image"
        assert result["twitter_cards"]["twitter:title"] == "Twitter Title"
        assert "twitter-cards" in result["formats_found"]

    def test_extracts_multiple_formats(self):
        """HTML with JSON-LD + OG + Twitter -> formats_found contains all."""
        from publishers.pipeline.steps import run_article_extraction_step

        result = run_article_extraction_step(MULTI_FORMAT_HTML, "https://example.com/article")
        assert "json-ld" in result["formats_found"]
        assert "opengraph" in result["formats_found"]
        assert "twitter-cards" in result["formats_found"]

    def test_jsonld_graph_nesting(self):
        """JSON-LD with @graph array containing Article -> correctly extracts."""
        from publishers.pipeline.steps import run_article_extraction_step

        result = run_article_extraction_step(JSONLD_GRAPH_ARTICLE_HTML, "https://example.com/article")
        assert result["jsonld_fields"] is not None
        assert result["jsonld_fields"]["headline"] == "Graph Article"

    def test_empty_html(self):
        """Empty string returns all None fields, empty formats_found."""
        from publishers.pipeline.steps import run_article_extraction_step

        result = run_article_extraction_step("", "https://example.com/article")
        assert result["jsonld_fields"] is None
        assert result["opengraph_fields"] is None
        assert result["microdata_fields"] is None
        assert result["twitter_cards"] is None
        assert result["formats_found"] == []

    def test_flattens_nested_author(self):
        """author: {name: "John"} -> fields["author"] == "John"."""
        from publishers.pipeline.steps import run_article_extraction_step

        result = run_article_extraction_step(JSONLD_ARTICLE_HTML, "https://example.com/article")
        # Author is nested as {"@type": "Person", "name": "John Doe"}
        assert result["jsonld_fields"]["author"] == "John Doe"


# ---------------------------------------------------------------------------
# TestRunPaywallDetectionStep
# ---------------------------------------------------------------------------


class TestRunPaywallDetectionStep:
    def test_schema_accessible_free(self):
        """isAccessibleForFree: true -> 'free'."""
        from publishers.pipeline.steps import run_paywall_detection_step

        extraction = {"jsonld_fields": {"isAccessibleForFree": True}}
        result = run_paywall_detection_step("<html></html>", extraction)
        assert result["paywall_status"] == "free"
        assert result["schema_accessible"] is True

    def test_schema_accessible_paywalled(self):
        """isAccessibleForFree: false -> 'paywalled'."""
        from publishers.pipeline.steps import run_paywall_detection_step

        extraction = {"jsonld_fields": {"isAccessibleForFree": False}}
        result = run_paywall_detection_step("<html></html>", extraction)
        assert result["paywall_status"] == "paywalled"
        assert result["schema_accessible"] is False

    def test_has_part_nested_accessible(self):
        """isAccessibleForFree nested in hasPart -> detected."""
        from publishers.pipeline.steps import run_paywall_detection_step

        extraction = {
            "jsonld_fields": {
                "hasPart": [
                    {"@type": "WebPageElement", "isAccessibleForFree": False}
                ]
            }
        }
        result = run_paywall_detection_step("<html></html>", extraction)
        assert result["paywall_status"] == "paywalled"

    def test_heuristic_multiple_signals_paywalled(self):
        """login wall + paywall class -> 'paywalled'."""
        from publishers.pipeline.steps import run_paywall_detection_step

        html = '<html><body><div class="paywall">Subscribe to continue reading</div></body></html>'
        extraction = {"jsonld_fields": None}
        result = run_paywall_detection_step(html, extraction)
        assert result["paywall_status"] == "paywalled"

    def test_heuristic_single_signal_unknown(self):
        """only login wall pattern -> 'unknown'."""
        from publishers.pipeline.steps import run_paywall_detection_step

        html = "<html><body><p>Subscribe to continue reading</p></body></html>"
        extraction = {"jsonld_fields": None}
        result = run_paywall_detection_step(html, extraction)
        assert result["paywall_status"] == "unknown"

    def test_heuristic_metered(self):
        """'articles remaining' -> 'metered'."""
        from publishers.pipeline.steps import run_paywall_detection_step

        html = "<html><body><div>You have 3 articles remaining this month</div></body></html>"
        extraction = {"jsonld_fields": None}
        result = run_paywall_detection_step(html, extraction)
        assert result["paywall_status"] == "metered"

    def test_no_signals_free(self):
        """Clean HTML with no schema -> 'free'."""
        from publishers.pipeline.steps import run_paywall_detection_step

        html = "<html><body><p>Normal article content here.</p></body></html>"
        extraction = {"jsonld_fields": None}
        result = run_paywall_detection_step(html, extraction)
        assert result["paywall_status"] == "free"


# ---------------------------------------------------------------------------
# TestRunMetadataProfileStep
# ---------------------------------------------------------------------------


class TestRunMetadataProfileStep:
    def test_metadata_profile_returns_summary(self, monkeypatch):
        """monkeypatch agent.run_sync, verify summary returned."""
        from publishers.pipeline import steps

        mock_output = MagicMock()
        mock_output.output = MagicMock()
        mock_output.output.model_dump.return_value = {
            "summary": "This article has JSON-LD and OpenGraph metadata.",
        }
        monkeypatch.setattr(
            steps, "metadata_profile_agent",
            MagicMock(run_sync=MagicMock(return_value=mock_output)),
        )

        result = steps.run_metadata_profile_step(
            {"jsonld_fields": {"headline": "Test"}, "formats_found": ["json-ld"]},
            "https://example.com/article",
        )
        assert result["summary"] == "This article has JSON-LD and OpenGraph metadata."

    def test_metadata_profile_handles_error(self, monkeypatch):
        """agent raises -> returns error dict."""
        from publishers.pipeline import steps

        mock_agent = MagicMock()
        mock_agent.run_sync.side_effect = Exception("LLM service down")
        monkeypatch.setattr(steps, "metadata_profile_agent", mock_agent)

        result = steps.run_metadata_profile_step(
            {"jsonld_fields": None, "formats_found": []},
            "https://example.com/article",
        )
        assert result["summary"] == ""
        assert "error" in result
