from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse, path
from django_object_actions import DjangoObjectActions, action
from django import forms
import json
from .models import Publisher, ResolutionJob, WAFReport
from .tasks import analyze_url
from ingestion.services import (
    create_terms_discovery_from_url,
    create_terms_evaluation_from_url,
    discover_and_evaluate_terms,
)
from ingestion.models import TermsDiscoveryResult, TermsEvaluationResult


class URLAnalysisForm(forms.Form):
    """Form for submitting URLs for analysis."""

    url = forms.URLField(
        label="URL to Analyze",
        widget=forms.URLInput(
            attrs={
                "placeholder": "https://example.com",
                "class": "form-control",
                "style": "width: 400px;",
            }
        ),
        help_text="Enter the URL you want to analyze (WAF scan, terms discovery, and evaluation)",
    )


def perform_waf_scan(modeladmin, request, queryset):
    """Django admin action to perform WAF scan on selected publishers."""
    for publisher in queryset:
        try:
            waf_report = WAFReport.create_from_url_scan(publisher, publisher.url)
            if waf_report:
                messages.success(
                    request,
                    f"WAF scan completed for {publisher.name}. "
                    f"{'WAF detected' if waf_report.detected else 'No WAF detected'}",
                )
            else:
                messages.error(
                    request,
                    f"WAF scan failed for {publisher.name}. Check the URL and try again.",
                )
        except Exception as e:
            messages.error(request, f"Error scanning {publisher.name}: {str(e)}")


perform_waf_scan.short_description = "Perform WAF scan on selected publishers"


def discover_terms(modeladmin, request, queryset):
    """Django admin action to discover terms of service and privacy policy URLs for selected publishers."""
    for publisher in queryset:
        try:
            discovery_result = create_terms_discovery_from_url(publisher, publisher.url)
            if discovery_result:
                messages.success(
                    request,
                    f"Terms discovery completed for {publisher.name}. "
                    f"Confidence: {discovery_result.confidence_score:.2f}",
                )
            else:
                messages.error(
                    request,
                    f"Terms discovery failed for {publisher.name}. Check the URL and try again.",
                )
        except Exception as e:
            messages.error(
                request, f"Error discovering terms for {publisher.name}: {str(e)}"
            )


discover_terms.short_description = "Discover terms of service and privacy policy URLs"


def evaluate_terms(modeladmin, request, queryset):
    """Django admin action to evaluate terms of service for selected publishers."""
    for publisher in queryset:
        try:
            # Check if we have a terms discovery result first
            if (
                hasattr(publisher, "terms_discovery")
                and publisher.terms_discovery.terms_of_service_url
            ):
                evaluation_result = create_terms_evaluation_from_url(
                    publisher, publisher.terms_discovery.terms_of_service_url
                )
                if evaluation_result:
                    messages.success(
                        request,
                        f"Terms evaluation completed for {publisher.name}. "
                        f"Confidence: {evaluation_result.confidence_score:.2f}",
                    )
                else:
                    messages.error(
                        request, f"Terms evaluation failed for {publisher.name}."
                    )
            else:
                messages.warning(
                    request,
                    f"No terms of service URL found for {publisher.name}. "
                    f"Run terms discovery first.",
                )
        except Exception as e:
            messages.error(
                request, f"Error evaluating terms for {publisher.name}: {str(e)}"
            )


evaluate_terms.short_description = "Evaluate terms of service for selected publishers"


def discover_and_evaluate_terms_action(modeladmin, request, queryset):
    """Django admin action to discover and evaluate terms for selected publishers in one step."""
    for publisher in queryset:
        try:
            discovery_result, evaluation_result = discover_and_evaluate_terms(
                publisher, publisher.url
            )

            if discovery_result and evaluation_result:
                messages.success(
                    request,
                    f"Complete terms analysis for {publisher.name}. "
                    f"Discovery confidence: {discovery_result.confidence_score:.2f}, "
                    f"Evaluation confidence: {evaluation_result.confidence_score:.2f}",
                )
            elif discovery_result:
                messages.warning(
                    request,
                    f"Terms discovery completed for {publisher.name}, but evaluation failed. "
                    f"Discovery confidence: {discovery_result.confidence_score:.2f}",
                )
            else:
                messages.error(request, f"Terms analysis failed for {publisher.name}.")
        except Exception as e:
            messages.error(
                request, f"Error analyzing terms for {publisher.name}: {str(e)}"
            )


discover_and_evaluate_terms_action.short_description = (
    "Discover and evaluate terms (complete analysis)"
)


def queue_url_analysis(modeladmin, request, queryset):
    """Django admin action to queue URL analysis tasks for selected publishers."""
    queued_count = 0
    for publisher in queryset:
        try:
            analyze_url.delay(publisher.url)
            queued_count += 1
            messages.success(request, f"URL analysis task queued for {publisher.name}")
        except Exception as e:
            messages.error(
                request, f"Error queueing analysis for {publisher.name}: {str(e)}"
            )

    if queued_count > 0:
        messages.success(
            request,
            f"Successfully queued {queued_count} URL analysis task{'s' if queued_count != 1 else ''}",
        )


queue_url_analysis.short_description = "Queue URL analysis tasks (async)"


class TermsDiscoveryResultInline(admin.StackedInline):
    model = TermsDiscoveryResult
    extra = 0
    fields = ["terms_of_service_url", "confidence_score", "notes", "created_at"]
    readonly_fields = [
        "terms_of_service_url",
        "confidence_score",
        "notes",
        "created_at",
    ]


class TermsEvaluationResultInline(admin.StackedInline):
    model = TermsEvaluationResult
    extra = 0
    fields = [
        "formatted_permissions",
        "territorial_exceptions",
        "arbitration_clauses",
        "document_type",
        "confidence_score",
        "created_at",
    ]
    readonly_fields = [
        "formatted_permissions",
        "territorial_exceptions",
        "arbitration_clauses",
        "document_type",
        "confidence_score",
        "created_at",
    ]

    def formatted_permissions(self, obj):
        """Display permissions as formatted JSON with monospace font and 2-space indentation."""
        if not obj.permissions:
            return "No permissions data"

        try:
            # Format JSON with 2-space indentation
            formatted_json = json.dumps(obj.permissions, indent=2, ensure_ascii=False)
            # Wrap in <pre> tag for monospace font and preserve formatting
            return format_html(
                '<pre style="font-family: monospace; font-size: 12px; background-color: #f8f9fa; padding: 10px; border-radius: 4px; white-space: pre-wrap;">{}</pre>',
                formatted_json,
            )
        except (TypeError, ValueError):
            return "Invalid JSON data"

    formatted_permissions.short_description = "Permissions"


class WAFReportInline(admin.TabularInline):
    model = WAFReport
    extra = 0
    fields = [
        "detected",
        "firewall",
        "manufacturer",
        "url",
        "trigger_url",
        "created_at",
    ]
    readonly_fields = [
        "detected",
        "firewall",
        "manufacturer",
        "url",
        "trigger_url",
        "created_at",
    ]


@admin.register(Publisher)
class PublisherAdmin(DjangoObjectActions, admin.ModelAdmin):
    list_display = ["name", "domain", "url", "detected_waf", "waf_reports_count"]
    list_filter = ["detected_waf"]
    search_fields = ["name", "domain", "url"]
    actions = [
        perform_waf_scan,
        discover_terms,
        evaluate_terms,
        discover_and_evaluate_terms_action,
        queue_url_analysis,
    ]
    inlines = [TermsDiscoveryResultInline, TermsEvaluationResultInline, WAFReportInline]

    def waf_reports_count(self, obj):
        return obj.waf_reports.count()

    waf_reports_count.short_description = "WAF Reports"

    @action(label="Scan WAF", description="Perform WAF scan on this publisher")
    def scan_waf(self, request, obj):
        try:
            waf_report = WAFReport.create_from_url_scan(obj, obj.url)
            if waf_report:
                messages.success(
                    request,
                    f"WAF scan completed for {obj.name}. "
                    f"{'WAF detected' if waf_report.detected else 'No WAF detected'}",
                )
            else:
                messages.error(
                    request,
                    f"WAF scan failed for {obj.name}. Check the URL and try again.",
                )
        except Exception as e:
            messages.error(request, f"Error scanning {obj.name}: {str(e)}")
        return redirect(
            request.META.get(
                "HTTP_REFERER", reverse("admin:publishers_publisher_changelist")
            )
        )

    @action(
        label="Discover Terms",
        description="Discover terms of service and privacy policy URLs",
    )
    def discover_terms_action(self, request, obj):
        try:
            discovery_result = create_terms_discovery_from_url(obj, obj.url)
            if discovery_result:
                messages.success(
                    request,
                    f"Terms discovery completed for {obj.name}. "
                    f"Confidence: {discovery_result.confidence_score:.2f}",
                )
            else:
                messages.error(
                    request,
                    f"Terms discovery failed for {obj.name}. Check the URL and try again.",
                )
        except Exception as e:
            messages.error(request, f"Error discovering terms for {obj.name}: {str(e)}")
        return redirect(
            request.META.get(
                "HTTP_REFERER", reverse("admin:publishers_publisher_changelist")
            )
        )

    @action(
        label="Evaluate Terms",
        description="Evaluate terms of service for this publisher",
    )
    def evaluate_terms_action(self, request, obj):
        try:
            if (
                hasattr(obj, "terms_discovery")
                and obj.terms_discovery.terms_of_service_url
            ):
                evaluation_result = create_terms_evaluation_from_url(
                    obj, obj.terms_discovery.terms_of_service_url
                )
                if evaluation_result:
                    messages.success(
                        request,
                        f"Terms evaluation completed for {obj.name}. "
                        f"Confidence: {evaluation_result.confidence_score:.2f}",
                    )
                else:
                    messages.error(request, f"Terms evaluation failed for {obj.name}.")
            else:
                messages.warning(
                    request,
                    f"No terms of service URL found for {obj.name}. "
                    f"Run terms discovery first.",
                )
        except Exception as e:
            messages.error(request, f"Error evaluating terms for {obj.name}: {str(e)}")
        return redirect(
            request.META.get(
                "HTTP_REFERER", reverse("admin:publishers_publisher_changelist")
            )
        )

    @action(
        label="Complete Analysis", description="Discover and evaluate terms in one step"
    )
    def complete_analysis_action(self, request, obj):
        try:
            discovery_result, evaluation_result = discover_and_evaluate_terms(
                obj, obj.url
            )

            if discovery_result and evaluation_result:
                messages.success(
                    request,
                    f"Complete terms analysis for {obj.name}. "
                    f"Discovery confidence: {discovery_result.confidence_score:.2f}, "
                    f"Evaluation confidence: {evaluation_result.confidence_score:.2f}",
                )
            elif discovery_result:
                messages.warning(
                    request,
                    f"Terms discovery completed for {obj.name}, but evaluation failed. "
                    f"Discovery confidence: {discovery_result.confidence_score:.2f}",
                )
            else:
                messages.error(request, f"Terms analysis failed for {obj.name}.")
        except Exception as e:
            messages.error(request, f"Error analyzing terms for {obj.name}: {str(e)}")
        return redirect(
            request.META.get(
                "HTTP_REFERER", reverse("admin:publishers_publisher_changelist")
            )
        )

    @action(label="Queue Analysis", description="Queue URL analysis task (async)")
    def queue_analysis_action(self, request, obj):
        try:
            analyze_url.delay(obj.url)
            messages.success(
                request,
                f"URL analysis task queued for {obj.name}. The task will run asynchronously.",
            )
        except Exception as e:
            messages.error(request, f"Error queueing analysis for {obj.name}: {str(e)}")
        return redirect(
            request.META.get(
                "HTTP_REFERER", reverse("admin:publishers_publisher_changelist")
            )
        )

    change_actions = [
        "scan_waf",
        "discover_terms_action",
        "evaluate_terms_action",
        "complete_analysis_action",
        "queue_analysis_action",
    ]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "analyze-url/",
                self.analyze_url_view,
                name="publishers_publisher_analyze_url",
            ),
        ]
        return custom_urls + urls

    def analyze_url_view(self, request):
        """Custom admin view to accept URLs and queue analysis tasks."""
        if request.method == "POST":
            form = URLAnalysisForm(request.POST)
            if form.is_valid():
                url = form.cleaned_data["url"]
                try:
                    analyze_url.delay(url)
                    messages.success(
                        request,
                        f"URL analysis task queued for {url}. The task will run asynchronously.",
                    )
                    return redirect("admin:publishers_publisher_analyze_url")
                except Exception as e:
                    messages.error(
                        request, f"Error queueing analysis for {url}: {str(e)}"
                    )
        else:
            form = URLAnalysisForm()

        context = {
            "form": form,
            "title": "Analyze URL",
            "opts": self.model._meta,
            "has_change_permission": self.has_change_permission(request),
        }
        return render(request, "admin/publishers/analyze_url.html", context)


@admin.register(WAFReport)
class WAFReportAdmin(admin.ModelAdmin):
    list_display = ["publisher", "firewall", "manufacturer", "detected", "created_at"]
    list_filter = ["detected", "firewall", "manufacturer", "created_at"]
    search_fields = ["publisher__name", "firewall", "manufacturer"]
    readonly_fields = ["created_at"]
    date_hierarchy = "created_at"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("publisher")


@admin.register(ResolutionJob)
class ResolutionJobAdmin(admin.ModelAdmin):
    list_display = ["id", "canonical_url", "publisher", "status", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["canonical_url", "submitted_url", "publisher__name"]
    readonly_fields = ["id", "created_at", "updated_at"]
    date_hierarchy = "created_at"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("publisher")
