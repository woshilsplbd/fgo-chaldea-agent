from django.urls import path

from . import views


app_name = "agent"


urlpatterns = [
    path("", views.chat, name="chat"),
]

api_urlpatterns = [
    path("chat/", views.chat_api, name="chat"),
]
