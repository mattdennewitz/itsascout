import uuid

import factory

from publishers.models import Publisher, ResolutionJob


class PublisherFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Publisher
        django_get_or_create = ("domain",)

    name = factory.Sequence(lambda n: f"publisher-{n}.com")
    url = factory.LazyAttribute(lambda o: f"https://{o.name}")
    domain = factory.LazyAttribute(lambda o: o.name)
    fetch_strategy = ""


class ResolutionJobFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ResolutionJob

    id = factory.LazyFunction(uuid.uuid4)
    submitted_url = factory.Sequence(lambda n: f"https://example-{n}.com/article")
    canonical_url = factory.LazyAttribute(lambda o: o.submitted_url)
    publisher = factory.SubFactory(PublisherFactory)
    status = "pending"
