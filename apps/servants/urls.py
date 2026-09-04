from django.urls import path

from . import views


urlpatterns = [
    path("", views.servants_api, name="servants_api"),
]

page_urlpatterns = [
    path("", views.index, name="index"),
]
