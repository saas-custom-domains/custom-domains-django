import pytest

from domains.models import CustomDomain

from .conftest import WEBHOOK_TOKEN

pytestmark = pytest.mark.django_db
URL = "/webhooks/saas-domains"


@pytest.fixture
def domain(intercom):
    return CustomDomain.objects.create(
        company=intercom, host="status.intercom.com", provider_uuid="d1"
    )


def webhook(client, event, uuid="d1", token=WEBHOOK_TOKEN):
    return client.post(
        f"{URL}?token={token}",
        {"event": event, "domain": {"uuid": uuid, "host": "status.intercom.com"}},
        content_type="application/json",
        headers={"Host": "app:8000"},
    )


def test_webhook_needs_the_right_token(client, domain):
    assert webhook(client, "domain_dns_proxy_record_valid", token="x").status_code == 401
    domain.refresh_from_db()
    assert domain.status == "pending"


def test_webhook_rejects_everything_if_the_token_is_not_configured(
    client, domain, monkeypatch
):
    monkeypatch.setenv("SCD_WEBHOOK_TOKEN", "")
    assert webhook(client, "domain_dns_proxy_record_valid", token="").status_code == 401


def test_webhook_updates_the_status(client, domain):
    assert webhook(client, "domain_dns_proxy_record_valid").status_code == 200
    domain.refresh_from_db()
    assert domain.status == "active"

    webhook(client, "tls_certificate_issued")
    domain.refresh_from_db()
    assert domain.label == "Live"

    webhook(client, "domain_dns_proxy_record_invalid")
    domain.refresh_from_db()
    assert domain.status == "pending"


def test_webhook_ignores_other_events_and_unknown_domains(client, domain):
    assert webhook(client, "domain_created", uuid="other").status_code == 200
    res = client.post(
        f"{URL}?token={WEBHOOK_TOKEN}",
        {"event": "upstream_created", "upstream": {"uuid": "u"}},
        content_type="application/json",
    )
    assert res.status_code == 200
    res = client.post(f"{URL}?token={WEBHOOK_TOKEN}", "not json", content_type="application/json")
    assert res.status_code == 200


def test_caddy_ask(client, domain):
    assert client.get("/caddy/ask?domain=status.intercom.com").status_code == 404
    domain.status = "active"
    domain.save()
    assert client.get("/caddy/ask?domain=Status.Intercom.com").status_code == 200
    assert client.get("/caddy/ask?domain=evil.example").status_code == 404


def test_dashboard_shows_errors_next_to_the_company(client, intercom):
    res = client.post(f"/companies/{intercom.id}/domains", {"host": "admin.statuspage.com"})
    assert res.status_code == 400
    assert b"Can&#x27;t be one of our own domains." in res.content


def test_webhooks_on_an_internal_hostname_need_it_in_app_hosts(
    client, domain, settings
):
    # The mock (and many platforms) call the app by an internal name.
    settings.APP_HOSTS = ["app.statuspage.com", "localhost"]
    assert webhook(client, "domain_dns_proxy_record_valid").status_code == 404
