import pytest
from publishers.factories import PublisherFactory, ResolutionJobFactory


@pytest.fixture
def publisher(db):
    return PublisherFactory()


@pytest.fixture
def resolution_job(db):
    return ResolutionJobFactory()
