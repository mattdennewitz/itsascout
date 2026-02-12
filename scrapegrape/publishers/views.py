import csv
from django.db.models import Subquery, OuterRef
from django.shortcuts import redirect, get_object_or_404
from inertia import render as inertia_render

from ingestion.models import TermsDiscoveryResult, TermsEvaluationResult
from publishers.models import Publisher, WAFReport
from publishers.serializers import PublisherWithReportsSerializer
from publishers.forms import PublisherForm, BulkUploadForm
from publishers.tasks import analyze_url


def _flash_errors(request, form):
    """Flatten Django form errors to {field: first_message} and store in session for Inertia useForm."""
    request.session['errors'] = {
        field: messages[0] for field, messages in form.errors.items()
    }


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

    return inertia_render(request, 'Publishers/Index', props={
        'publishers': serialized.data
    })


def inertia_smoke_test(request):
    """
    Temporary smoke test: proves Inertia renders a React component with Django props.
    Lives at /_debug/inertia/ — remove in Phase 5 cleanup.
    """
    return inertia_render(request, 'Debug/InertiaTest', props={
        'message': 'Inertia is working!',
        'timestamp': '2026-02-12',
    })


def create(request):
    """Create a new publisher with form validation."""
    if request.method == 'POST':
        form = PublisherForm(request.POST)
        if form.is_valid():
            publisher = form.save()
            # Enqueue background analysis task
            analyze_url.enqueue(publisher.url)
            request.session['success'] = f'Publisher "{publisher.name}" created and analysis queued!'
            return redirect('/')
        else:
            _flash_errors(request, form)
            return redirect('/publishers/create')

    # GET request
    return inertia_render(request, 'Publishers/Create')


def update(request, publisher_id):
    """Update an existing publisher with form validation."""
    publisher = get_object_or_404(Publisher, id=publisher_id)

    if request.method == 'POST':
        form = PublisherForm(request.POST, instance=publisher)
        if form.is_valid():
            form.save()
            request.session['success'] = f'Publisher "{publisher.name}" updated successfully!'
            return redirect('/')
        else:
            _flash_errors(request, form)
            return redirect(f'/publishers/{publisher_id}/edit')

    # GET request
    return inertia_render(request, 'Publishers/Edit', props={
        'publisher': {
            'id': publisher.id,
            'name': publisher.name,
            'url': publisher.url
        }
    })


def bulk_upload(request):
    """Bulk upload publishers from CSV file."""
    if request.method == 'POST':
        form = BulkUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            # Decode and parse CSV
            decoded_file = csv_file.read().decode('utf-8')
            reader = csv.DictReader(decoded_file.splitlines())

            count = 0
            for row in reader:
                if 'URL' in row and row['URL']:
                    analyze_url.enqueue(row['URL'])
                    count += 1

            request.session['success'] = f'{count} URLs queued for analysis'
            return redirect('/')
        else:
            _flash_errors(request, form)
            return redirect('/publishers/bulk-upload')

    # GET request
    return inertia_render(request, 'Publishers/BulkUpload')
