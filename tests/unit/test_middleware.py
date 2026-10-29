import logging

import pytest

from .conftest import proxied

pytestmark = pytest.mark.django_db


def test_app_host_gets_the_dashboard(client, domains):
    res = client.get("/", headers={"Host": "app.statuspage.com"})
    assert res.status_code == 200
    assert b"Statuspage dashboard" in res.content


def test_active_custom_domain_gets_its_status_page(client, domains):
    res = client.get("/", headers={"Host": "Status.Intercom.com:8000"})
    assert res.status_code == 200
    assert b"Intercom status" in res.content


def test_pending_and_unknown_domains_get_404(client, domains):
    assert client.get("/", headers={"Host": "status.globex.com"}).status_code == 404
    assert client.get("/", headers={"Host": "evil.example"}).status_code == 404


def test_custom_domains_only_see_status_page_urls(client, domains):
    host = {"Host": "status.intercom.com"}
    assert client.get("/", headers=host).status_code == 200
    assert client.get("/webhooks/saas-domains", headers=host).status_code == 404
    assert client.post("/domains/1/remove", headers=host).status_code == 404


def test_status_page_urls_are_not_on_the_app_host(client, domains):
    res = client.post("/subscribe", {"email": "a@b.co"}, headers={"Host": "localhost"})
    assert res.status_code == 404


def test_health_check_works_by_ip_address(client):
    assert client.get("/up", headers={"Host": "10.0.0.7:8000"}).status_code == 200


def test_reads_x_served_for_with_the_proxy_token(client, domains):
    res = client.get("/", headers=proxied("status.intercom.com"))
    assert res.status_code == 200
    assert b"Intercom status" in res.content
    # Django now sees the customer's domain as the host.
    assert res.wsgi_request.get_host() == "status.intercom.com"
    assert (
        res.wsgi_request.build_absolute_uri("/")
        == "https://status.intercom.com/"
    )


@pytest.mark.parametrize(
    "token", [None, "", "wrong", "test_proxy_token_but_longer"]
)
def test_rejects_x_served_for_without_the_right_token(client, domains, token):
    headers = proxied("status.intercom.com")
    del headers["X-SaaS-Domains-Auth-Token"]
    if token is not None:
        headers["X-SaaS-Domains-Auth-Token"] = token
    assert client.get("/", headers=headers).status_code == 403


@pytest.mark.parametrize("expected", [None, ""])
def test_rejects_x_served_for_if_the_token_is_not_configured(
    client, domains, monkeypatch, expected
):
    # An empty PROXY_AUTH_TOKEN must not match an empty header.
    if expected is None:
        monkeypatch.delenv("PROXY_AUTH_TOKEN")
    else:
        monkeypatch.setenv("PROXY_AUTH_TOKEN", expected)
    headers = proxied("status.intercom.com", **{"X-SaaS-Domains-Auth-Token": ""})
    assert client.get("/", headers=headers).status_code == 403


def test_without_allowed_hosts_star_custom_domains_get_400(
    client, domains, settings, caplog
):
    # The default way to configure Django rejects every customer domain.
    settings.ALLOWED_HOSTS = ["app.statuspage.com", "localhost"]
    with caplog.at_level(logging.ERROR, logger="django.security.DisallowedHost"):
        res = client.get("/", headers={"Host": "status.intercom.com"})
    assert res.status_code == 400
    assert (
        "Invalid HTTP_HOST header: 'status.intercom.com'. "
        "You may need to add 'status.intercom.com' to ALLOWED_HOSTS."
    ) in caplog.text
