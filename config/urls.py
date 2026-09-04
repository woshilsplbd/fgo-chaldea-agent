"""Minimal URL configuration for the isolated V2 foundation."""

from django.contrib import admin
from django.urls import include, path

from apps.agent.urls import api_urlpatterns
from apps.servants.urls import page_urlpatterns


urlpatterns = [
    path("", include("apps.home.urls")),
    path("api/servants/", include("apps.servants.urls")),
    path("api/tools/servant/", include("apps.servants.tool_urls")),
    path("servants/", include((page_urlpatterns, "servants"), namespace="servants")),
    path("news/", include("apps.news.urls")),
    path("agent/", include("apps.agent.urls")),
    path(
        "api/agent/",
        include((api_urlpatterns, "agent_api"), namespace="agent_api"),
    ),
    path("admin/", admin.site.urls),
]
