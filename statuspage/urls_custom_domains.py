from django.urls import path

from status import views

urlpatterns = [
    path("", views.status_page, name="status_page"),
    path("subscribe", views.subscribe, name="subscribe"),
]
