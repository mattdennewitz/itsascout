"""Tests for the pipeline supervisor, step functions, and event publishing."""

import json
from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from django.utils import timezone

from publishers.factories import PublisherFactory, ResolutionJobFactory
from publishers.fetchers.base import FetchResult
from publishers.fetchers.exceptions import AllStrategiesExhausted


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

        run_pipeline(str(job.id))

        job.refresh_from_db()
        assert job.status == "completed"

        # Check that all steps and pipeline completion were signaled
        step_names = [s for s, _ in events_published]
        assert "waf" in step_names
        assert "tos_discovery" in step_names
        assert "tos_evaluation" in step_names
        assert "robots" in step_names
        assert "sitemap" in step_names
        assert "rss" in step_names
        assert "rsl" in step_names
        assert "pipeline" in step_names
        assert ("pipeline", "completed") in events_published

    def test_pipeline_skips_fresh_publisher(self, monkeypatch):
        """Pipeline skips steps for publisher checked within freshness TTL."""
        from publishers.pipeline.supervisor import run_pipeline

        publisher = PublisherFactory(
            last_checked_at=timezone.now() - timedelta(hours=1)
        )
        job = ResolutionJobFactory(publisher=publisher, status="pending")
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
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_tos_discovery_step",
            lambda pub: {"tos_url": None},
        )
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_tos_evaluation_step",
            lambda pub, tos_url: {"skipped": True},
        )
        robots_called = []
        monkeypatch.setattr(
            "publishers.pipeline.supervisor.run_robots_step",
            lambda pub, url: robots_called.append(True)
            or {"robots_found": False},
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
            lambda pub: ("", {}),
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

        run_pipeline(str(job.id))

        # Step functions should NOT have been called
        assert len(waf_called) == 0
        assert len(robots_called) == 0

        # Skip events should have been published
        assert ("waf", "skipped") in events_published
        assert ("tos_discovery", "skipped") in events_published
        assert ("tos_evaluation", "skipped") in events_published
        assert ("robots", "skipped") in events_published
        assert ("sitemap", "skipped") in events_published
        assert ("rss", "skipped") in events_published
        assert ("rsl", "skipped") in events_published

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

        run_pipeline(str(job.id))

        job.refresh_from_db()
        assert job.waf_result["waf_detected"] is True
        assert job.waf_result["waf_type"] == "Cloudflare"
        assert job.tos_result["tos_url"] == "https://example.com/tos"
        assert "permissions" in job.tos_result
        assert job.robots_result["robots_found"] is True
        assert job.sitemap_result["sitemap_urls"] == [
            "https://example.com/sitemap.xml"
        ]
        assert job.rss_result["count"] == 1
        assert job.rsl_result["rsl_detected"] is True

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

        run_pipeline(str(job.id))

        publisher = job.publisher
        publisher.refresh_from_db()
        assert publisher.robots_txt_found is True
        assert publisher.robots_txt_url_allowed is True
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

        run_pipeline(str(job.id))

        publisher = job.publisher
        publisher.refresh_from_db()
        assert publisher.rss_urls == ["https://example.com/feed"]
        assert publisher.rsl_detected is True


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
