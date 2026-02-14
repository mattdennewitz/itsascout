import csv
import json

from django.conf import settings
from django.db.models import Subquery, OuterRef
from django.http import HttpResponseNotFound, StreamingHttpResponse
from django.shortcuts import redirect, get_object_or_404
from inertia import render as inertia_render, defer

from ingestion.models import TermsDiscoveryResult, TermsEvaluationResult
from publishers.models import Publisher, ResolutionJob, WAFReport
from publishers.serializers import PublisherWithReportsSerializer
from publishers.forms import PublisherForm, BulkUploadForm
from publishers.tasks import analyze_url
from publishers.url_sanitizer import sanitize_url, extract_domain
from publishers.pipeline import run_pipeline


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


def submit_url(request):
    """Accept a URL submission, create a ResolutionJob, and redirect to the job page."""
    if request.method != "POST":
        return redirect("/")

    url = request.POST.get("url", "").strip()
    if not url:
        request.session["errors"] = {"url": "URL is required."}
        return redirect("/")

    try:
        canonical_url = sanitize_url(url)
        domain = extract_domain(url)
    except (ValueError, TypeError):
        request.session["errors"] = {"url": "Invalid URL."}
        return redirect("/")

    if not domain:
        request.session["errors"] = {"url": "Could not extract domain from URL."}
        return redirect("/")

    # Check for existing non-failed job with same canonical URL
    existing = ResolutionJob.objects.filter(
        canonical_url=canonical_url, status__in=("pending", "running", "completed")
    ).first()
    if existing:
        return redirect(f"/jobs/{existing.id}")

    # Get or create publisher for this domain
    publisher_url = f"https://{domain}"
    publisher, _created = Publisher.objects.get_or_create(
        domain=domain, defaults={"name": domain, "url": publisher_url}
    )

    # Create new resolution job
    job = ResolutionJob.objects.create(
        submitted_url=url,
        canonical_url=canonical_url,
        publisher=publisher,
    )

    # Queue pipeline
    run_pipeline.delay(str(job.id))

    return redirect(f"/jobs/{job.id}")


def job_show(request, job_id):
    """Render the Jobs/Show Inertia page with job data."""
    try:
        job = ResolutionJob.objects.select_related("publisher").get(id=job_id)
    except ResolutionJob.DoesNotExist:
        return HttpResponseNotFound()

    return inertia_render(
        request,
        "Jobs/Show",
        props={
            "job": {
                "id": str(job.id),
                "status": job.status,
                "canonical_url": job.canonical_url,
                "submitted_url": job.submitted_url,
                "publisher_name": job.publisher.name,
                "publisher_domain": job.publisher.domain,
                "waf_result": job.waf_result,
                "tos_result": job.tos_result,
                "created_at": job.created_at.isoformat(),
            },
        },
    )


async def job_stream(request, job_id):
    """SSE endpoint: stream Redis pub/sub events for a job.

    To avoid a race condition where the job completes between the status check
    and the Redis subscription, we subscribe first, then check status. If the
    job already completed, we send the terminal state and close.
    """
    import redis.asyncio as aioredis

    # Verify job exists
    exists = await ResolutionJob.objects.filter(id=job_id).aexists()
    if not exists:
        return HttpResponseNotFound()

    async def event_generator():
        r = None
        pubsub = None
        try:
            r = aioredis.Redis(
                host=settings.RQ_QUEUES["default"]["HOST"],
                port=settings.RQ_QUEUES["default"]["PORT"],
            )
            pubsub = r.pubsub()

            # Subscribe BEFORE checking status to avoid TOCTOU race.
            # Any events published after this point will be captured.
            await pubsub.subscribe(f"job:{job_id}:events")

            # Now check if job already completed (handles the fast-finish case)
            job_data = await ResolutionJob.objects.filter(id=job_id).values(
                "status", "waf_result", "tos_result"
            ).afirst()

            if job_data and job_data["status"] in ("completed", "failed"):
                event = json.dumps(
                    {"step": "pipeline", "status": job_data["status"], "data": {
                        "waf_result": job_data["waf_result"],
                        "tos_result": job_data["tos_result"],
                    }}
                )
                yield f"event: done\ndata: {event}\n\n"
                return

            # Live streaming from Redis pub/sub
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                # Check for terminal event
                try:
                    parsed = json.loads(data)
                    if parsed.get("step") == "pipeline" and parsed.get("status") in (
                        "completed",
                        "failed",
                    ):
                        yield f"event: done\ndata: {data}\n\n"
                        break
                except (json.JSONDecodeError, KeyError):
                    pass
                yield f"data: {data}\n\n"
        finally:
            if pubsub:
                await pubsub.unsubscribe(f"job:{job_id}:events")
                await pubsub.aclose()
            if r:
                await r.aclose()

    response = StreamingHttpResponse(
        streaming_content=event_generator(),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
