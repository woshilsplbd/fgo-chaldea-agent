"""Minimal URL configuration for the isolated V2 foundation."""

from django.contrib import admin
from django.urls import path


urlpatterns = [
    path("admin/", admin.site.urls),
]
