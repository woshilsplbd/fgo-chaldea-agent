from django.urls import path

from . import tool_views


app_name = "servants_tool"


urlpatterns = [
    path("", tool_views.servant_tool, name="servant_tool"),
]
