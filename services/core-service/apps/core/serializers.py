"""REST API serializers for core-service (pymongo dict → JSON)."""
from rest_framework import serializers


class ProcessedEventSerializer(serializers.Serializer):
    event_id = serializers.CharField()
    platform_event_id = serializers.CharField(allow_blank=True, default="")
    source = serializers.CharField()
    event_type = serializers.CharField()
    channel = serializers.CharField()
    page_id = serializers.CharField()
    sender_id = serializers.CharField(allow_blank=True, default="")
    actor_name = serializers.CharField(allow_blank=True, default="")
    message_text = serializers.CharField(allow_blank=True, default="")
    message_hash = serializers.CharField(allow_blank=True, default="")
    intent = serializers.CharField(allow_blank=True, default="")
    sentiment = serializers.CharField(allow_blank=True, default="")
    is_spam = serializers.BooleanField(default=False)
    is_malicious_link = serializers.BooleanField(default=False)
    ai_confidence = serializers.FloatField(default=0.0)
    ai_reason = serializers.CharField(allow_blank=True, default="")
    ai_parse_error = serializers.CharField(allow_blank=True, default="")
    spam_score = serializers.IntegerField(default=0)
    spam_signals = serializers.ListField(child=serializers.CharField(), default=list)
    spam_reason = serializers.CharField(allow_blank=True, default="")
    detected_links = serializers.ListField(child=serializers.CharField(), default=list)
    status = serializers.CharField()
    decision = serializers.CharField(allow_blank=True, default="")
    decision_reason = serializers.CharField(allow_blank=True, default="")
    error_message = serializers.CharField(allow_blank=True, default="")
    retry_count = serializers.IntegerField(default=0)
    last_failed_at = serializers.DateTimeField(allow_null=True, required=False)
    occurred_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class ActionLogSerializer(serializers.Serializer):
    event_id = serializers.CharField()
    idempotency_key = serializers.CharField(allow_blank=True, default="")
    action_type = serializers.CharField()
    status = serializers.CharField()
    request_payload = serializers.DictField()
    response_payload = serializers.DictField()
    error_message = serializers.CharField(allow_blank=True, default="")
    attempt = serializers.IntegerField(default=0)
    created_at = serializers.DateTimeField()


class ManualReviewSerializer(serializers.Serializer):
    event_id = serializers.CharField()
    reason = serializers.CharField()
    status = serializers.CharField()
    reviewer_note = serializers.CharField(allow_blank=True, default="")
    created_at = serializers.DateTimeField()
