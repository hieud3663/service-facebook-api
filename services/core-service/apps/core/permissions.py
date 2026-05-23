"""Internal API-key permission for core-service admin/debug endpoints."""
from django.conf import settings
from rest_framework.permissions import BasePermission


class HasInternalApiKey(BasePermission):
    """Require X-Internal-Api-Key when CORE_INTERNAL_API_KEY is configured."""

    message = "Missing or invalid internal API key."

    def has_permission(self, request, view):
        configured_key = getattr(settings, "CORE_INTERNAL_API_KEY", "")
        if not configured_key:
            return True
        return request.headers.get("X-Internal-Api-Key") == configured_key
