from rest_framework import serializers

from publishers.models import Publisher, WAFReport
from ingestion.models import TermsDiscoveryResult, TermsEvaluationResult


class WAFReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = WAFReport
        fields = ("firewall", "manufacturer", "detected")


class TermsDiscoveryResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = TermsDiscoveryResult
        fields = ("terms_of_service_url",)


class TermsEvaluationResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = TermsEvaluationResult
        fields = (
            "permissions",
            "territorial_exceptions",
            "arbitration_clauses",
            "document_type",
        )


class PublisherSerializer(serializers.ModelSerializer):
    class Meta:
        model = Publisher
        fields = ("id", "name", "domain", "url", "detected_waf")


class PublisherWithReportsSerializer(serializers.Serializer):
    publisher = PublisherSerializer()
    waf_report = WAFReportSerializer()
    terms_discovery = TermsDiscoveryResultSerializer()
    terms_evaluation = TermsEvaluationResultSerializer()
