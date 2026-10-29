import pytest

from companies.models import Company
from domains.models import CustomDomain

PROXY_TOKEN = "test_proxy_token"
WEBHOOK_TOKEN = "test_webhook_token"


@pytest.fixture(autouse=True)
def env(monkeypatch, settings):
    monkeypatch.setenv("PROXY_AUTH_TOKEN", PROXY_TOKEN)
    monkeypatch.setenv("SCD_WEBHOOK_TOKEN", WEBHOOK_TOKEN)
    monkeypatch.setenv("SCD_API_TOKEN", "scd_test_token")
    monkeypatch.setenv("SCD_ACCOUNT_UUID", "acc_local")
    monkeypatch.setenv("SCD_UPSTREAM_UUID", "upstream_local")
    settings.APP_HOSTS = ["app.statuspage.com", "localhost", "testserver", "app"]
    settings.APP_DOMAIN = "statuspage.com"
    settings.SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


@pytest.fixture
def intercom(db):
    return Company.objects.get(slug="intercom")


@pytest.fixture
def domains(intercom):
    globex = Company.objects.get(slug="globex")
    CustomDomain.objects.create(
        company=intercom, host="status.intercom.com", status="active"
    )
    CustomDomain.objects.create(company=globex, host="status.globex.com")


def proxied(host, **extra):
    """Headers SaaS Custom Domains adds to a request for `host`."""
    return {
        "Host": "app.statuspage.com",
        "X-Forwarded-Host": "app.statuspage.com",
        "X-Forwarded-Proto": "https",
        "X-Served-For": host,
        "X-SaaS-Domains-Auth-Token": PROXY_TOKEN,
        **extra,
    }
