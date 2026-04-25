from django.urls import path

from .views import (
    PageDetailAPIView,
    PageInsightsAPIView,
    PagePostCommentsAPIView,
    PagePostDeleteAPIView,
    PagePostLikesAPIView,
    PagePostsAPIView,
)

urlpatterns = [
    path("page/<str:page_id>", PageDetailAPIView.as_view(), name="page-detail"),
    path("page/<str:page_id>/posts", PagePostsAPIView.as_view(), name="page-posts"),
    path("page/post/<str:post_id>", PagePostDeleteAPIView.as_view(), name="page-post-delete"),
    path(
        "page/post/<str:post_id>/comments",
        PagePostCommentsAPIView.as_view(),
        name="page-post-comments",
    ),
    path("page/post/<str:post_id>/likes", PagePostLikesAPIView.as_view(), name="page-post-likes"),
    path("page/<str:page_id>/insights", PageInsightsAPIView.as_view(), name="page-insights"),
]
