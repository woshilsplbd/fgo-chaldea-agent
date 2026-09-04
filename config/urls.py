"""Minimal URL configuration for the isolated V2 foundation."""

from django.contrib import admin
from django.urls import include, path

from apps.servants.urls import page_urlpatterns


urlpatterns = [
    path("", include("apps.home.urls")),
    path("api/servants/", include("apps.servants.urls")),
    path("servants/", include((page_urlpatterns, "servants"), namespace="servants")),
    path("news/", include("apps.news.urls")),
    path("admin/", admin.site.urls),
]
