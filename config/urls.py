"""Minimal URL configuration for the isolated V2 foundation."""

from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView


urlpatterns = [
    path(
        "",
        TemplateView.as_view(template_name="shell_preview.html"),
        name="shell_preview",
    ),
    path("admin/", admin.site.urls),
]
