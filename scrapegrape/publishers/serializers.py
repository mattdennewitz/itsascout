from rest_framework import serializers

from publishers.models import Publisher


class PublisherListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Publisher
        fields = (
            "id", "name", "domain", "url",
            "waf_detected", "waf_type",
            "tos_url", "tos_permissions",
            "robots_txt_found",
            "sitemap_urls", "rss_urls", "rsl_detected", "ai_bot_blocks",
            "fetch_strategy", "last_checked_at",
        )
