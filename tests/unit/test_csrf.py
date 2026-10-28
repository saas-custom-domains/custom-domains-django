"""Forms on a custom domain behind the proxy, with Django's CSRF checks on.

The proxy sends your own hostname in Host and X-Forwarded-Host, and the
customer's domain in X-Served-For. Django compares the browser's Origin
with request.get_host(), so ProxyTokenMiddleware sets the host to the
customer's domain once the token checks out.
"""

import hmac
import logging
import os

import pytest
from django.http import HttpResponseForbidden
from django.test import Client

from status.models import Subscriber

from .conftest import proxied

pytestmark = pytest.mark.django_db

ORIGIN_FAILED = (
    "Origin checking failed - {} does not match any trusted origins."
)


class GuideProxyTokenMiddleware:
    """The published guide's version: checks the token, keeps Host as is."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.expected = os.environ["PROXY_AUTH_TOKEN"].encode()

    def __call__(self, request):
        if request.headers.get("X-Served-For"):
            token = request.headers.get("X-SaaS-Domains-Auth-Token", "")
            if not hmac.compare_digest(token.encode(), self.expected):
                return HttpResponseForbidden()
        return self.get_response(request)


def subscribe(origin="https://status.intercom.com", **headers):
    client = Client(enforce_csrf_checks=True)
    page = client.get("/", headers=proxied("status.intercom.com", **headers))
    assert page.status_code == 200
    token = client.cookies["csrftoken"].value
    return client.post(
        "/subscribe",
        {"email": "reader@example.com", "csrfmiddlewaretoken": token},
        headers=proxied("status.intercom.com", Origin=origin, **headers),
    )


def test_form_on_a_custom_domain_passes_the_csrf_check(domains):
    res = subscribe()
    assert res.status_code == 200
    assert b"Subscribed to Intercom status updates." in res.content
    assert Subscriber.objects.filter(email="reader@example.com").exists()


def test_without_the_host_rewrite_the_origin_check_fails(
    domains, settings, caplog
):
    settings.MIDDLEWARE = [
        "tests.unit.test_csrf.GuideProxyTokenMiddleware"
        if m == "domains.middleware.ProxyTokenMiddleware"
        else m
        for m in settings.MIDDLEWARE
    ]
    with caplog.at_level(logging.WARNING, logger="django.security.csrf"):
        res = subscribe()
    assert res.status_code == 403
    assert ORIGIN_FAILED.format("https://status.intercom.com") in caplog.text


def test_use_x_forwarded_host_undoes_the_fix(domains, settings, caplog):
    # X-Forwarded-Host is your own hostname too, and with this setting
    # Django prefers it to Host.
    settings.USE_X_FORWARDED_HOST = True
    with caplog.at_level(logging.WARNING, logger="django.security.csrf"):
        res = subscribe()
    assert res.status_code == 403
    assert ORIGIN_FAILED.format("https://status.intercom.com") in caplog.text


def test_without_secure_proxy_ssl_header_the_origin_check_fails(
    domains, settings, caplog
):
    # TLS ends at the proxy, so Django sees plain HTTP and expects an
    # http:// Origin.
    settings.SECURE_PROXY_SSL_HEADER = None
    with caplog.at_level(logging.WARNING, logger="django.security.csrf"):
        res = subscribe()
    assert res.status_code == 403
    assert ORIGIN_FAILED.format("https://status.intercom.com") in caplog.text


def test_plain_http_proxy_needs_secure_proxy_ssl_header_off(
    domains, settings, caplog
):
    # The local mock proxy speaks HTTP but sends X-Forwarded-Proto: https.
    with caplog.at_level(logging.WARNING, logger="django.security.csrf"):
        res = subscribe(origin="http://status.intercom.com")
    assert res.status_code == 403
    assert ORIGIN_FAILED.format("http://status.intercom.com") in caplog.text

    settings.SECURE_PROXY_SSL_HEADER = None
    assert subscribe(origin="http://status.intercom.com").status_code == 200
