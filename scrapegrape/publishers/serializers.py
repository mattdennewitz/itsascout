from rest_framework import serializers

from publishers.models import Publisher


class PublisherListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Publisher
        fields = (
            "id", "name", "domain", "url",
            "waf_detected", "waf_type",
            "tos_url", "tos_permissions",
            "robots_txt_found", "robots_txt_url_allowed",
            "sitemap_urls", "rss_urls", "rsl_detected",
            "fetch_strategy", "last_checked_at",
        )
