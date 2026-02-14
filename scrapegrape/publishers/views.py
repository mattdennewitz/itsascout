import csv
from django.db.models import Subquery, OuterRef
from django.shortcuts import redirect, get_object_or_404
from inertia import render as inertia_render, defer

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
    search = request.GET.get('search', '')

    def load_publishers():
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

        # Apply search filter if search param exists
        if search:
            publishers = publishers.filter(name__icontains=search)

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
        return serialized.data

    return inertia_render(request, 'Publishers/Index', props={
        'publishers': defer(load_publishers),
    })


def create(request):
    """Create a new publisher with form validation."""
    if request.method == 'POST':
        form = PublisherForm(request.POST)
        if form.is_valid():
            publisher = form.save()
            # Enqueue background analysis task
            analyze_url.delay(publisher.url)
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
                    analyze_url.delay(row['URL'])
                    count += 1

            request.session['success'] = f'{count} URLs queued for analysis'
            return redirect('/')
        else:
            _flash_errors(request, form)
            return redirect('/publishers/bulk-upload')

    # GET request
    return inertia_render(request, 'Publishers/BulkUpload')
