import uuid

from django.db import models

from .waf_check import scan_url_with_wafw00f


class Publisher(models.Model):
    # Existing fields
    name = models.CharField(max_length=255)
    url = models.URLField()
    # NEW: Canonical domain for publisher lookup (one domain = one publisher)
    domain = models.CharField(max_length=255, unique=True, db_index=True, default="")

    # NEW: Discovery result flat fields (populated by pipeline in later phases)
    waf_type = models.CharField(max_length=255, blank=True, default="")
    waf_detected = models.BooleanField(default=False)
    tos_url = models.URLField(blank=True, default="")
    tos_permissions = models.JSONField(null=True, blank=True)
    robots_txt_found = models.BooleanField(null=True)
    sitemap_urls = models.JSONField(default=list, blank=True)
    rss_urls = models.JSONField(default=list, blank=True)
    rsl_detected = models.BooleanField(null=True)
    ai_bot_blocks = models.JSONField(null=True, blank=True)
    publisher_details = models.JSONField(null=True, blank=True)
    has_paywall = models.BooleanField(null=True)

    # NEW: Remembered fetch strategy (populated by FetchStrategyManager)
    FETCH_STRATEGY_CHOICES = [
        ("", "Auto (no preference)"),
        ("curl_cffi", "curl-cffi"),
        ("zyte", "Zyte API"),
    ]
    fetch_strategy = models.CharField(
        max_length=20,
        blank=True,
        default="",
        choices=FETCH_STRATEGY_CHOICES,
    )

    # NEW: Freshness tracking
    last_checked_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name


class WAFReport(models.Model):
    publisher = models.ForeignKey(
        Publisher, on_delete=models.CASCADE, related_name="waf_reports"
    )
    detected = models.BooleanField()
    firewall = models.CharField(max_length=255)
    manufacturer = models.CharField(max_length=255)
    url = models.URLField()
    trigger_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.publisher.name} - {self.firewall} ({'Detected' if self.detected else 'Not Detected'})"

    @classmethod
    def create_from_url_scan(cls, publisher, url):
        """Create a WAFReport instance by scanning a URL with wafw00f."""
        scan_result = scan_url_with_wafw00f(url)

        if not scan_result or not scan_result.get("report"):
            return None

        report_data = scan_result["report"][0]  # wafw00f returns a list with one item

        waf_report = cls.objects.create(
            publisher=publisher,
            detected=report_data.get("detected", False),
            firewall=report_data.get("firewall", "Unknown"),
            manufacturer=report_data.get("manufacturer", "Unknown"),
            url=report_data.get("url", url),
            trigger_url=report_data.get("trigger_url"),
        )

        return waf_report


class ResolutionJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submitted_url = models.URLField()
    canonical_url = models.URLField(db_index=True)
    publisher = models.ForeignKey(
        "Publisher", on_delete=models.CASCADE, related_name="resolution_jobs"
    )
    status = models.CharField(
        max_length=20,
        default="pending",
        choices=[
            ("pending", "Pending"),
            ("running", "Running"),
            ("completed", "Completed"),
            ("failed", "Failed"),
        ],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Pipeline step results stored directly on the job (locked decision)
    waf_result = models.JSONField(null=True, blank=True)
    tos_result = models.JSONField(null=True, blank=True)
    robots_result = models.JSONField(null=True, blank=True)
    sitemap_result = models.JSONField(null=True, blank=True)
    rss_result = models.JSONField(null=True, blank=True)
    rsl_result = models.JSONField(null=True, blank=True)
    ai_bot_result = models.JSONField(null=True, blank=True)
    metadata_result = models.JSONField(null=True, blank=True)
    article_result = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["canonical_url"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Job {self.id} - {self.canonical_url} ({self.status})"


class ArticleMetadata(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    resolution_job = models.ForeignKey(
        "ResolutionJob", on_delete=models.CASCADE, related_name="article_metadata"
    )
    publisher = models.ForeignKey(
        "Publisher", on_delete=models.CASCADE, related_name="article_metadata"
    )
    article_url = models.URLField(db_index=True)

    # Per-format extracted fields
    jsonld_fields = models.JSONField(null=True, blank=True)
    opengraph_fields = models.JSONField(null=True, blank=True)
    microdata_fields = models.JSONField(null=True, blank=True)
    twitter_cards = models.JSONField(null=True, blank=True)

    # Format presence booleans
    has_jsonld = models.BooleanField(default=False)
    has_opengraph = models.BooleanField(default=False)
    has_microdata = models.BooleanField(default=False)
    has_twitter_cards = models.BooleanField(default=False)

    # Paywall status
    PAYWALL_CHOICES = [
        ("free", "Free"),
        ("paywalled", "Paywalled (hard)"),
        ("metered", "Metered"),
        ("unknown", "Unknown"),
    ]
    paywall_status = models.CharField(
        max_length=20, choices=PAYWALL_CHOICES, default="unknown"
    )
    paywall_signals = models.JSONField(default=list, blank=True)

    # LLM metadata profile
    metadata_profile = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["article_url"]),
            models.Index(fields=["publisher", "created_at"]),
        ]

    def __str__(self):
        return f"ArticleMetadata {self.article_url} ({self.paywall_status})"
