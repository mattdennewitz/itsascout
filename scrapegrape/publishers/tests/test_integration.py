"""End-to-end integration tests for the full pipeline flow.

TEST-04: Proves the entire system works from user input to rendered output.
Submit URL -> job created -> pipeline runs (mocked) -> results stored -> job page renderable.
"""

import uuid
from unittest.mock import MagicMock

import pytest

from publishers.factories import PublisherFactory
from publishers.models import Publisher, ResolutionJob


def _mock_pipeline_sync(job_id):
    """Synchronous mock that simulates a completed pipeline run.

    Gets the ResolutionJob by ID, creates a Publisher with realistic flat fields,
    populates ALL result fields with realistic mock data, and marks completed.
    """
    job = ResolutionJob.objects.get(id=job_id)
    publisher = job.publisher

    # Update publisher flat fields (as the real supervisor does)
    publisher.waf_detected = False
    publisher.tos_url = "https://example.com/terms"
    publisher.robots_txt_found = True
    publisher.sitemap_urls = ["https://example.com/sitemap.xml"]
    publisher.rss_urls = ["https://example.com/feed"]
    publisher.rsl_detected = False
    publisher.ai_bot_blocks = {"GPTBot": True, "ClaudeBot": False}
    publisher.save()

    # Populate all 9 result fields with realistic data shapes
    job.waf_result = {
        "waf_detected": False,
        "waf_type": "",
        "error": None,
    }
    job.tos_result = {
        "tos_url": "https://example.com/terms",
        "confidence": 0.9,
        "scraping_permitted": True,
        "permissions": [
            {
                "activity": "scraping",
                "permission": "explicitly_permitted",
                "notes": "Allowed for non-commercial use",
            }
        ],
        "document_type": "ToS",
    }
    job.robots_result = {
        "robots_found": True,
        "url_allowed": True,
        "sitemaps_from_robots": ["https://example.com/sitemap.xml"],
        "crawl_delay": None,
        "license_directives": [],
    }
    job.ai_bot_result = {
        "robots_found": True,
        "bots": {
            "GPTBot": {"company": "OpenAI", "blocked": True},
            "ClaudeBot": {"company": "Anthropic", "blocked": False},
        },
        "blocked_count": 1,
        "total_count": 2,
    }
    job.sitemap_result = {
        "sitemap_urls": ["https://example.com/sitemap.xml"],
        "source": "robots.txt",
        "count": 1,
    }
    job.rss_result = {
        "feeds": [
            {
                "url": "https://example.com/feed",
                "type": "application/rss+xml",
                "title": "Example Feed",
            }
        ],
        "count": 1,
    }
    job.rsl_result = {
        "rsl_detected": False,
        "indicators": [],
        "count": 0,
    }
    job.metadata_result = {
        "found": True,
        "source": "json-ld",
        "score": 85,
        "organization": {
            "name": "Example Corp",
            "type": "Organization",
            "url": "https://example.com",
            "id": None,
            "logo": None,
            "same_as": [],
        },
    }
    job.article_result = {
        "jsonld_fields": {"@type": "NewsArticle"},
        "opengraph_fields": {"og:title": "Test"},
        "microdata_fields": None,
        "twitter_cards": {"twitter:card": "summary"},
        "formats_found": ["json-ld", "opengraph", "twitter-cards"],
        "paywall": {
            "paywall_status": "free",
            "signals": [],
            "schema_accessible": True,
        },
        "profile": {
            "summary": "Well-structured article with JSON-LD and OpenGraph metadata.",
        },
    }

    job.status = "completed"
    job.save()


@pytest.mark.django_db
class TestFullPipelineIntegration:
    """End-to-end integration tests proving the full pipeline chain."""

    def test_submit_url_pipeline_completes_results_retrievable(self, client, monkeypatch):
        """TEST-04: Submit URL -> pipeline executes -> all results populated -> job page 200."""
        # Monkeypatch run_pipeline.delay to run synchronously
        mock_pipeline_obj = MagicMock()
        mock_pipeline_obj.delay.side_effect = _mock_pipeline_sync
        monkeypatch.setattr("publishers.views.run_pipeline", mock_pipeline_obj)

        # 1. POST to /submit
        response = client.post("/submit", {"url": "https://example.com/article-test"})

        # 2. Assert 302 redirect
        assert response.status_code == 302
        assert "/jobs/" in response.url

        # 3. Extract job ID from redirect URL
        job_id = response.url.split("/jobs/")[1].rstrip("/")

        # 4. GET /jobs/{job_id} -- assert 200
        job_response = client.get(f"/jobs/{job_id}")
        assert job_response.status_code == 200

        # 5. Verify pipeline was called
        mock_pipeline_obj.delay.assert_called_once_with(job_id)

        # 6. Refresh job from DB -- assert completed
        job = ResolutionJob.objects.get(id=job_id)
        assert job.status == "completed"

        # 7. Assert ALL 9 result fields are not None
        assert job.waf_result is not None
        assert job.tos_result is not None
        assert job.robots_result is not None
        assert job.sitemap_result is not None
        assert job.rss_result is not None
        assert job.rsl_result is not None
        assert job.ai_bot_result is not None
        assert job.metadata_result is not None
        assert job.article_result is not None

        # Verify data shapes are correct
        assert job.waf_result["waf_detected"] is False
        assert job.tos_result["tos_url"] == "https://example.com/terms"
        assert job.robots_result["robots_found"] is True
        assert job.ai_bot_result["blocked_count"] == 1
        assert job.sitemap_result["count"] == 1
        assert job.rss_result["count"] == 1
        assert job.rsl_result["rsl_detected"] is False
        assert job.metadata_result["found"] is True
        assert job.article_result["formats_found"] == ["json-ld", "opengraph", "twitter-cards"]

        # Verify publisher flat fields were updated
        publisher = job.publisher
        publisher.refresh_from_db()
        assert publisher.waf_detected is False
        assert publisher.tos_url == "https://example.com/terms"
        assert publisher.robots_txt_found is True

    def test_submit_url_deduplication_returns_existing_job(self, client, monkeypatch):
        """Submitting the same URL twice returns the existing job."""
        mock_pipeline_obj = MagicMock()
        mock_pipeline_obj.delay.side_effect = _mock_pipeline_sync
        monkeypatch.setattr("publishers.views.run_pipeline", mock_pipeline_obj)

        # Submit URL once
        response1 = client.post("/submit", {"url": "https://example.com/dedup-test"})
        assert response1.status_code == 302
        job_id_1 = response1.url.split("/jobs/")[1].rstrip("/")

        # Submit same URL again -- should redirect to same job
        response2 = client.post("/submit", {"url": "https://example.com/dedup-test"})
        assert response2.status_code == 302
        job_id_2 = response2.url.split("/jobs/")[1].rstrip("/")

        # Same job ID returned
        assert job_id_1 == job_id_2

        # Only 1 ResolutionJob exists
        assert ResolutionJob.objects.count() == 1

    def test_job_page_returns_404_for_nonexistent_job(self, client):
        """GET /jobs/{random_uuid} returns 404."""
        random_id = uuid.uuid4()
        response = client.get(f"/jobs/{random_id}")
        assert response.status_code == 404
