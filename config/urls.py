"""Minimal URL configuration for the isolated V2 foundation."""

from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("", include("apps.home.urls")),
    path("api/servants/", include("apps.servants.urls")),
    path("admin/", admin.site.urls),
]
