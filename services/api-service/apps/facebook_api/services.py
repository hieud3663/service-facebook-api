from dataclasses import dataclass
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings


@dataclass
class FacebookServiceError(Exception):
    message: str
    status_code: int = 400
    details: dict[str, Any] | None = None


class FacebookGraphService:
    def __init__(self, access_token: str | None = None):
        self.version = settings.FACEBOOK_GRAPH_API_VERSION
        self.base_url = f"https://graph.facebook.com/{self.version}"
        self.access_token = access_token or settings.FACEBOOK_PAGE_ACCESS_TOKEN

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.access_token:
            raise FacebookServiceError(
                message="Missing FACEBOOK_PAGE_ACCESS_TOKEN in environment.",
                status_code=500,
            )

        params = params or {}
        params["access_token"] = self.access_token

        if data:
            encoded_body = urlencode(data).encode("utf-8")
        else:
            encoded_body = None

        query_string = urlencode(params)
        url = f"{self.base_url}/{endpoint}?{query_string}"

        request = Request(url=url, data=encoded_body, method=method)

        try:
            with urlopen(request, timeout=30) as response:
                payload = response.read().decode("utf-8")
                return json.loads(payload) if payload else {}
        except HTTPError as exc:
            raw = exc.read().decode("utf-8")
            details = None
            try:
                details = json.loads(raw)
            except json.JSONDecodeError:
                details = {"raw": raw}
            message = details.get("error", {}).get("message", "Facebook API error")
            raise FacebookServiceError(message=message, status_code=exc.code, details=details) from exc
        except URLError as exc:
            raise FacebookServiceError(message=f"Connection error: {exc.reason}", status_code=503) from exc

    def get_page(self, page_id: str) -> dict[str, Any]:
        fields = "id,name,about,category,link,fan_count,followers_count,verification_status"
        return self._request("GET", page_id, params={"fields": fields})

    def get_page_posts(self, page_id: str, limit: int = 10) -> dict[str, Any]:
        fields = "id,message,created_time,permalink_url,full_picture"
        endpoint = f"{page_id}/posts"
        return self._request("GET", endpoint, params={"fields": fields, "limit": limit})

    def create_page_post(
        self,
        page_id: str,
        message: str,
        link: str | None = None,
        published: bool = True,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "message": message,
            "published": str(published).lower(),
        }
        if link:
            payload["link"] = link
        endpoint = f"{page_id}/feed"
        return self._request("POST", endpoint, data=payload)

    def get_post_detail(self, post_id: str) -> dict[str, Any]:
        fields = "id,message,created_time,permalink_url,full_picture,is_published,is_hidden"
        return self._request("GET", post_id, params={"fields": fields})

    def delete_post(self, post_id: str) -> dict[str, Any]:
        return self._request("DELETE", post_id)

    def get_post_comments(self, post_id: str, limit: int = 10) -> dict[str, Any]:
        endpoint = f"{post_id}/comments"
        fields = "id,from{id,name},message,created_time"
        return self._request("GET", endpoint, params={"fields": fields, "limit": limit})

    def get_post_likes(self, post_id: str, limit: int = 10) -> dict[str, Any]:
        endpoint = f"{post_id}/likes"
        fields = "id,name"
        return self._request("GET", endpoint, params={"fields": fields, "limit": limit, "summary": "true"})

    def get_page_insights(self, page_id: str, metric: str | None = None, period: str = "day") -> dict[str, Any]:
        endpoint = f"{page_id}/insights"
        default_metrics = "page_media_view"
        return self._request(
            "GET",
            endpoint,
            params={
                "metric": metric or default_metrics,
                "period": period,
            },
        )

    def hide_comment(self, comment_id: str, is_hidden: bool = True) -> dict[str, Any]:
        """Hide or unhide a comment via POST /{comment_id}?is_hidden=..."""
        return self._request("POST", comment_id, data={"is_hidden": str(is_hidden).lower()})

    def reply_comment(self, comment_id: str, message: str) -> dict[str, Any]:
        """Reply to a comment via POST /{comment_id}/comments"""
        endpoint = f"{comment_id}/comments"
        return self._request("POST", endpoint, data={"message": message})

    def send_message(self, recipient_id: str, message: str) -> dict[str, Any]:
        """Send a message via Messenger Send API: POST /me/messages"""
        endpoint = "me/messages"
        import json as _json
        data_payload = _json.dumps({
            "recipient": {"id": recipient_id},
            "messaging_type": "RESPONSE",
            "message": {"text": message},
        })
        # Send API requires JSON body, not form-encoded
        from urllib.request import Request
        from urllib.parse import urlencode
        import json as _json2

        params = {"access_token": self.access_token}
        url = f"{self.base_url}/{endpoint}?{urlencode(params)}"
        req = Request(url=url, data=data_payload.encode("utf-8"), method="POST")
        req.add_header("Content-Type", "application/json")

        try:
            from urllib.request import urlopen
            with urlopen(req, timeout=30) as response:
                payload = response.read().decode("utf-8")
                return _json2.loads(payload) if payload else {}
        except Exception as exc:
            raise FacebookServiceError(message=f"Send message failed: {exc}", status_code=502) from exc
