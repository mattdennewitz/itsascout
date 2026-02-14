"""Tests for URL submission, job show, SSE stream, and backward compatibility."""

import uuid
from unittest.mock import MagicMock

import pytest

from publishers.factories import PublisherFactory, ResolutionJobFactory
from publishers.models import Publisher, ResolutionJob


# ---------------------------------------------------------------------------
# TestSubmitUrl
# ---------------------------------------------------------------------------


class TestSubmitUrl:
    def test_submit_url_creates_job_and_redirects(self, client, db, monkeypatch):
        mock_pipeline = MagicMock()
        monkeypatch.setattr("publishers.views.run_pipeline", mock_pipeline)

        response = client.post("/submit", {"url": "https://example.com/article"})

        assert response.status_code == 302
        assert "/jobs/" in response.url

        job = ResolutionJob.objects.first()
        assert job is not None
        mock_pipeline.delay.assert_called_once_with(str(job.id))

    def test_submit_duplicate_url_redirects_to_existing(self, client, db, monkeypatch):
        mock_pipeline = MagicMock()
        monkeypatch.setattr("publishers.views.run_pipeline", mock_pipeline)

        existing = ResolutionJobFactory(
            canonical_url="https://example.com/article",
            status="completed",
        )

        response = client.post("/submit", {"url": "https://example.com/article"})

        assert response.status_code == 302
        assert str(existing.id) in response.url
        # No new job should be created (only the existing one)
        assert ResolutionJob.objects.count() == 1

    def test_submit_empty_url_redirects_with_error(self, client, db):
        response = client.post("/submit", {"url": ""})

        assert response.status_code == 302
        assert response.url == "/"
        # Error should be stored in session
        session = client.session
        assert "errors" in session
        assert "url" in session["errors"]

    def test_submit_url_get_redirects_to_home(self, client):
        response = client.get("/submit")

        assert response.status_code == 302
        assert response.url == "/"

    def test_submit_url_creates_publisher_from_domain(self, client, db, monkeypatch):
        mock_pipeline = MagicMock()
        monkeypatch.setattr("publishers.views.run_pipeline", mock_pipeline)

        response = client.post("/submit", {"url": "https://www.example.com/page"})

        assert response.status_code == 302
        publisher = Publisher.objects.get(domain="example.com")
        assert publisher is not None
        assert publisher.name == "example.com"


# ---------------------------------------------------------------------------
# TestJobShow
# ---------------------------------------------------------------------------


class TestJobShow:
    def test_job_show_returns_200(self, client, db):
        job = ResolutionJobFactory()

        response = client.get(f"/jobs/{job.id}")

        assert response.status_code == 200

    def test_job_show_404_for_nonexistent(self, client, db):
        random_id = uuid.uuid4()

        response = client.get(f"/jobs/{random_id}")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# TestJobStream
# ---------------------------------------------------------------------------


class TestJobStream:
    @pytest.mark.asyncio
    async def test_job_stream_returns_event_stream_content_type(self, db):
        """Completed job SSE endpoint returns text/event-stream and terminal state."""
        from django.test import AsyncClient

        job = await ResolutionJob.objects.acreate(
            submitted_url="https://example.com/article",
            canonical_url="https://example.com/article",
            publisher=await Publisher.objects.acreate(
                name="example.com",
                url="https://example.com",
                domain="example-stream.com",
            ),
            status="completed",
        )

        async_client = AsyncClient()
        response = await async_client.get(f"/api/jobs/{job.id}/stream")

        assert response.status_code == 200
        assert response["Content-Type"] == "text/event-stream"

    @pytest.mark.asyncio
    async def test_job_stream_404_for_nonexistent(self, db):
        from django.test import AsyncClient

        random_id = uuid.uuid4()
        async_client = AsyncClient()

        response = await async_client.get(f"/api/jobs/{random_id}/stream")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# TestExistingViewsUnchanged
# ---------------------------------------------------------------------------


class TestExistingViewsUnchanged:
    def test_publisher_table_still_works(self, client, db):
        response = client.get("/")

        assert response.status_code == 200

    def test_publisher_create_still_works(self, client, db):
        response = client.get("/publishers/create")

        assert response.status_code == 200
