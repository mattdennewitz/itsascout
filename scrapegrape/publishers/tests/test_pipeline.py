"""Tests for the pipeline supervisor, step functions, and event publishing."""

import json
from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from django.utils import timezone

from publishers.factories import PublisherFactory, ResolutionJobFactory


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
            lambda url: mock_result,
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
            lambda url: mock_result,
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
            lambda url: mock_result,
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

        run_pipeline(str(job.id))

        job.refresh_from_db()
        assert job.status == "completed"

        # Check that all steps and pipeline completion were signaled
        step_names = [s for s, _ in events_published]
        assert "waf" in step_names
        assert "tos_discovery" in step_names
        assert "tos_evaluation" in step_names
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

        run_pipeline(str(job.id))

        # Step functions should NOT have been called
        assert len(waf_called) == 0

        # Skip events should have been published
        assert ("waf", "skipped") in events_published
        assert ("tos_discovery", "skipped") in events_published
        assert ("tos_evaluation", "skipped") in events_published

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

        run_pipeline(str(job.id))

        job.refresh_from_db()
        assert job.waf_result["waf_detected"] is True
        assert job.waf_result["waf_type"] == "Cloudflare"
        assert job.tos_result["tos_url"] == "https://example.com/tos"
        assert "permissions" in job.tos_result
