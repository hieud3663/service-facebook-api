from django.conf import settings
from rest_framework.permissions import BasePermission


class HasRetryInternalApiKey(BasePermission):
    message = "Missing or invalid internal API key."

    def has_permission(self, request, view):
        configured_key = getattr(settings, "RETRY_INTERNAL_API_KEY", "")
        if not configured_key:
            return True
        return request.headers.get("X-Internal-Api-Key") == configured_key

