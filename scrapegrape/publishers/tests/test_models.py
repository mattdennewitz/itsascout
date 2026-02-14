import uuid

import pytest
from django.db import IntegrityError

from publishers.factories import PublisherFactory, ResolutionJobFactory
from publishers.models import Publisher


@pytest.mark.django_db
class TestPublisherModel:
    def test_factory_creates_publisher(self, publisher):
        assert publisher.name
        assert publisher.domain
        assert publisher.pk is not None

    def test_publisher_domain_unique(self, db):
        PublisherFactory(domain="example.com")
        with pytest.raises(IntegrityError):
            # Use model directly to bypass factory's get_or_create
            Publisher.objects.create(
                name="duplicate", url="https://example.com", domain="example.com"
            )

    def test_publisher_str(self, publisher):
        assert str(publisher) == publisher.name

    def test_publisher_default_field_values(self, publisher):
        assert publisher.waf_detected is False
        assert publisher.tos_url == ""
        assert publisher.robots_txt_found is None
        assert publisher.sitemap_urls == []
        assert publisher.rss_urls == []
        assert publisher.rsl_detected is None
        assert publisher.last_checked_at is None


@pytest.mark.django_db
class TestResolutionJobModel:
    def test_factory_creates_job(self, resolution_job):
        assert resolution_job.pk is not None
        assert resolution_job.publisher is not None
        assert resolution_job.status == "pending"

    def test_job_uuid_pk(self, resolution_job):
        assert isinstance(resolution_job.pk, uuid.UUID)

    def test_job_str(self, resolution_job):
        result = str(resolution_job)
        assert "Job" in result
        assert resolution_job.status in result

    def test_job_default_results_null(self, resolution_job):
        assert resolution_job.waf_result is None
        assert resolution_job.tos_result is None
        assert resolution_job.robots_result is None
        assert resolution_job.sitemap_result is None
        assert resolution_job.rss_result is None
        assert resolution_job.rsl_result is None
        assert resolution_job.metadata_result is None

    def test_job_publisher_relationship(self, resolution_job):
        assert resolution_job.publisher.resolution_jobs.count() == 1

    def test_job_status_choices(self, db):
        for status in ["pending", "running", "completed", "failed"]:
            job = ResolutionJobFactory(status=status)
            job.full_clean()
            assert job.status == status
