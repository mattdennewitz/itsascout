from django.contrib import admin
from django.utils.html import format_html
import json
from .models import TermsDiscoveryResult, TermsEvaluationResult


@admin.register(TermsDiscoveryResult)
class TermsDiscoveryResultAdmin(admin.ModelAdmin):
    list_display = ["publisher", "confidence_score", "has_terms_url", "created_at"]
    list_filter = ["confidence_score", "created_at"]
    search_fields = ["publisher__name", "notes"]
    readonly_fields = ["created_at"]
    date_hierarchy = "created_at"

    def has_terms_url(self, obj):
        return bool(obj.terms_of_service_url)

    has_terms_url.boolean = True
    has_terms_url.short_description = "Has Terms URL"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("publisher")


@admin.register(TermsEvaluationResult)
class TermsEvaluationResultAdmin(admin.ModelAdmin):
    list_display = [
        "publisher",
        "confidence_score",
        "document_type",
        "permissions_count",
        "created_at",
    ]
    list_filter = ["confidence_score", "document_type", "created_at"]
    search_fields = [
        "publisher__name",
        "document_type",
        "territorial_exceptions",
        "arbitration_clauses",
    ]
    readonly_fields = ["created_at", "formatted_permissions"]
    date_hierarchy = "created_at"

    def permissions_count(self, obj):
        return len(obj.permissions) if obj.permissions else 0

    permissions_count.short_description = "Permissions Count"

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

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("publisher")
