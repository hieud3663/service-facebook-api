from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import OpenApiResponse, extend_schema

from .serializers import InsightsQuerySerializer, PaginationQuerySerializer, PostCreateSerializer
from .services import FacebookGraphService, FacebookServiceError


class FacebookBaseAPIView(APIView):
    service_class = FacebookGraphService

    def get_service(self) -> FacebookGraphService:
        return self.service_class()

    @staticmethod
    def handle_error(exc: FacebookServiceError) -> Response:
        payload = {"detail": exc.message}
        if exc.details:
            payload["facebook_error"] = exc.details
        return Response(payload, status=exc.status_code)


class PageDetailAPIView(FacebookBaseAPIView):
    @extend_schema(
        summary="Get page information",
        responses={200: OpenApiResponse(description="Facebook page detail")},
    )
    def get(self, request, page_id: str):
        service = self.get_service()
        try:
            data = service.get_page(page_id)
        except FacebookServiceError as exc:
            return self.handle_error(exc)
        return Response(data)


class PagePostsAPIView(FacebookBaseAPIView):
    @extend_schema(
        summary="Get page posts",
        parameters=[PaginationQuerySerializer],
        responses={200: OpenApiResponse(description="List posts from a Facebook page")},
    )
    def get(self, request, page_id: str):
        query = PaginationQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        service = self.get_service()
        try:
            data = service.get_page_posts(page_id, limit=query.validated_data["limit"])
        except FacebookServiceError as exc:
            return self.handle_error(exc)
        return Response(data)

    @extend_schema(
        summary="Create a page post",
        request=PostCreateSerializer,
        responses={
            201: OpenApiResponse(description="Post created successfully"),
            400: OpenApiResponse(description="Validation error or Facebook API error"),
        },
    )
    def post(self, request, page_id: str):
        serializer = PostCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = self.get_service()
        try:
            create_result = service.create_page_post(
                page_id=page_id,
                message=serializer.validated_data["message"],
                link=serializer.validated_data.get("link"),
                published=serializer.validated_data.get("published", True),
            )

            if serializer.validated_data.get("return_post_detail", False):
                post_id = create_result.get("id")
                if post_id:
                    post_detail = service.get_post_detail(post_id)
                    data = {
                        "create_result": create_result,
                        "post_detail": post_detail,
                    }
                else:
                    data = create_result
            else:
                data = create_result
        except FacebookServiceError as exc:
            return self.handle_error(exc)
        return Response(data, status=status.HTTP_201_CREATED)


class PagePostDeleteAPIView(FacebookBaseAPIView):
    @extend_schema(
        summary="Delete a post",
        responses={200: OpenApiResponse(description="Delete result")},
    )
    def delete(self, request, post_id: str):
        service = self.get_service()
        try:
            data = service.delete_post(post_id)
        except FacebookServiceError as exc:
            return self.handle_error(exc)
        return Response(data, status=status.HTTP_200_OK)


class PagePostCommentsAPIView(FacebookBaseAPIView):
    @extend_schema(
        summary="Get post comments",
        parameters=[PaginationQuerySerializer],
        responses={200: OpenApiResponse(description="Comments list")},
    )
    def get(self, request, post_id: str):
        query = PaginationQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        service = self.get_service()
        try:
            data = service.get_post_comments(post_id, limit=query.validated_data["limit"])
        except FacebookServiceError as exc:
            return self.handle_error(exc)
        return Response(data)


class PagePostLikesAPIView(FacebookBaseAPIView):
    @extend_schema(
        summary="Get post likes",
        parameters=[PaginationQuerySerializer],
        responses={200: OpenApiResponse(description="Likes list")},
    )
    def get(self, request, post_id: str):
        query = PaginationQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        service = self.get_service()
        try:
            data = service.get_post_likes(post_id, limit=query.validated_data["limit"])
        except FacebookServiceError as exc:
            return self.handle_error(exc)
        return Response(data)


class PageInsightsAPIView(FacebookBaseAPIView):
    @extend_schema(
        summary="Get page insights",
        parameters=[InsightsQuerySerializer],
        responses={200: OpenApiResponse(description="Page insights")},
    )
    def get(self, request, page_id: str):
        query = InsightsQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        service = self.get_service()
        try:
            data = service.get_page_insights(
                page_id=page_id,
                metric=query.validated_data.get("metric"),
                period=query.validated_data.get("period", "day"),
            )
        except FacebookServiceError as exc:
            return self.handle_error(exc)
        return Response(data)
