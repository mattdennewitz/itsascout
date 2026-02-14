from django.db import models
from publishers.models import Publisher


class TermsDiscoveryResult(models.Model):
    publisher = models.OneToOneField(
        Publisher, on_delete=models.CASCADE, related_name="terms_discovery"
    )
    terms_of_service_url = models.URLField(blank=True, null=True)
    confidence_score = models.FloatField(default=0.0)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.publisher.name} - Terms Discovery (Confidence: {self.confidence_score})"


class TermsEvaluationResult(models.Model):
    publisher = models.OneToOneField(
        Publisher, on_delete=models.CASCADE, related_name="terms_evaluation"
    )
    permissions = models.JSONField(default=list)  # List of ActivityPermission objects
    territorial_exceptions = models.TextField(blank=True, null=True)
    arbitration_clauses = models.TextField(blank=True, null=True)
    document_type = models.CharField(max_length=255, blank=True, null=True)
    confidence_score = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.publisher.name} - Terms Evaluation (Confidence: {self.confidence_score})"
