from django.db.models import Subquery, OuterRef
from django.shortcuts import render
from inertia import render as inertia_render

from ingestion.models import TermsDiscoveryResult, TermsEvaluationResult
from publishers.models import Publisher, WAFReport
from publishers.serializers import PublisherWithReportsSerializer


def table(request):
    # Subqueries to get the latest related object IDs
    latest_waf = Subquery(
        WAFReport.objects.filter(publisher=OuterRef("pk"))
        .order_by("-created_at")
        .values("id")[:1]
    )
    latest_discovery = Subquery(
        TermsDiscoveryResult.objects.filter(publisher=OuterRef("pk"))
        .order_by("-created_at")
        .values("id")[:1]
    )
    latest_evaluation = Subquery(
        TermsEvaluationResult.objects.filter(publisher=OuterRef("pk"))
        .order_by("-created_at")
        .values("id")[:1]
    )

    # Annotate publishers with those latest IDs
    publishers = Publisher.objects.annotate(
        latest_waf_id=latest_waf,
        latest_discovery_id=latest_discovery,
        latest_evaluation_id=latest_evaluation,
    )

    # Get all needed related objects in bulk
    waf_reports = WAFReport.objects.in_bulk(
        publishers.values_list("latest_waf_id", flat=True)
    )
    discovery_results = TermsDiscoveryResult.objects.in_bulk(
        publishers.values_list("latest_discovery_id", flat=True)
    )
    evaluation_results = TermsEvaluationResult.objects.in_bulk(
        publishers.values_list("latest_evaluation_id", flat=True)
    )

    # Build final result
    result = []
    for publisher in publishers:
        result.append(
            {
                "publisher": publisher,
                "waf_report": waf_reports.get(publisher.latest_waf_id),
                "terms_discovery": discovery_results.get(publisher.latest_discovery_id),
                "terms_evaluation": evaluation_results.get(
                    publisher.latest_evaluation_id
                ),
            }
        )

    serialized = PublisherWithReportsSerializer(result, many=True)

    return render(request, "index.html", {"serialized": serialized.data})


def inertia_smoke_test(request):
    """
    Temporary smoke test: proves Inertia renders a React component with Django props.
    Lives at /_debug/inertia/ — remove in Phase 5 cleanup.
    """
    return inertia_render(request, 'Debug/InertiaTest', props={
        'message': 'Inertia is working!',
        'timestamp': '2026-02-12',
    })
