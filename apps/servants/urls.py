from django.urls import path

from . import views


app_name = "servants"


urlpatterns = [
    path("", views.servants_api, name="servants_api"),
]
