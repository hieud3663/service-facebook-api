from rest_framework import serializers


class RetryAttemptSerializer(serializers.Serializer):
    command_id = serializers.CharField()
    event_id = serializers.CharField(allow_blank=True, default="")
    action_type = serializers.CharField(allow_blank=True, default="")
    target_id = serializers.CharField(allow_blank=True, default="")
    status = serializers.CharField()
    retry_count = serializers.IntegerField(default=0)
    last_failure_type = serializers.CharField(allow_blank=True, default="")
    last_reason = serializers.CharField(allow_blank=True, default="")
    next_retry_at = serializers.DateTimeField(allow_null=True, required=False)
    dead_lettered_at = serializers.DateTimeField(allow_null=True, required=False)
    created_at = serializers.DateTimeField(required=False)
    updated_at = serializers.DateTimeField(required=False)

