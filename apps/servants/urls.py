from django.urls import path

from . import views


app_name = "servants_api"


urlpatterns = [
    path("", views.servants_api, name="servants_api"),
    path("<int:servant_id>/", views.servant_detail_api, name="detail"),
]

page_urlpatterns = [
    path("", views.index, name="index"),
    path("<int:servant_id>/", views.detail, name="detail"),
]
