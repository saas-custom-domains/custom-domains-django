# The app itself, on the hosts in settings.APP_HOSTS. Customer domains
# get statuspage/urls_custom_domains.py instead.
from django.urls import path

from domains import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path(
        "companies/<int:company_id>/domains",
        views.add_domain,
        name="add_domain",
    ),
    path(
        "domains/<int:domain_id>/check",
        views.check_domain,
        name="check_domain",
    ),
    path(
        "domains/<int:domain_id>/remove",
        views.remove_domain,
        name="remove_domain",
    ),
    path("webhooks/saas-domains", views.saas_domains_webhook),
    path("up", views.up),
]
