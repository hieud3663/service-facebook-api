from rest_framework import serializers


INSIGHT_METRIC_CHOICES = [
    "page_media_view",
    "post_media_view",
    "post_total_media_view_unique",
]


class PostCreateSerializer(serializers.Serializer):
    message = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=5000,
        help_text="Post content text shown on the Facebook Page feed.",
    )
    link = serializers.URLField(
        required=False,
        help_text="Optional URL to attach to the post.",
    )
    published = serializers.BooleanField(
        required=False,
        default=True,
        help_text="Set true to publish immediately.",
    )
    return_post_detail = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Set true to return created post detail right after successful creation.",
    )


class InsightsQuerySerializer(serializers.Serializer):
    metric = serializers.ChoiceField(
        choices=INSIGHT_METRIC_CHOICES,
        required=False,
        default="page_media_view",
        help_text="Use one of the safe metrics below to avoid invalid metric errors.",
    )
    period = serializers.ChoiceField(
        choices=["day", "week", "days_28", "lifetime"],
        required=False,
        default="day",
    )


class PaginationQuerySerializer(serializers.Serializer):
    limit = serializers.IntegerField(required=False, min_value=1, max_value=100, default=10)
