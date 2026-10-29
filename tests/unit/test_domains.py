import pytest
import requests
from django.core.exceptions import ValidationError
from django.test import RequestFactory

from domains import services
from domains.models import CustomDomain
from domains.saas_domains import SaasDomains
from domains.utils import host_from, normalize_host


def test_normalize_host():
    assert normalize_host(" Status.Intercom.com. ") == "status.intercom.com"
    assert normalize_host("bücher.example") == "xn--bcher-kva.example"


def test_host_from_strips_the_port(settings):
    settings.ALLOWED_HOSTS = ["*"]
    request = RequestFactory().get("/", headers={"Host": "Status.Intercom.com:8000"})
    assert host_from(request) == "status.intercom.com"


def test_host_from_prefers_x_served_for(settings):
    settings.ALLOWED_HOSTS = ["*"]
    request = RequestFactory().get(
        "/", headers={"Host": "app.statuspage.com", "X-Served-For": "status.intercom.com"}
    )
    assert host_from(request) == "status.intercom.com"


@pytest.fixture
def api(monkeypatch):
    """Records SaaS Custom Domains API calls instead of making them."""
    calls = []

    def create_domain(self, host, **options):
        calls.append(("create", host, options))
        return {"uuid": f"uuid-{host}"}

    def verify_dns(self, uuid):
        calls.append(("verify", uuid))
        return {"dns_status": "valid"}

    monkeypatch.setattr(SaasDomains, "create_domain", create_domain)
    monkeypatch.setattr(SaasDomains, "verify_dns", verify_dns)
    return calls


def test_add_normalizes_and_registers_the_domain(intercom, api):
    domain = services.add_custom_domain(intercom, " Status.Intercom.com. ")
    assert domain.host == "status.intercom.com"
    assert domain.provider_uuid == "uuid-status.intercom.com"
    # No DNS contact, no instructions_recipient.
    assert api == [("create", "status.intercom.com", {})]


def test_add_sends_the_dns_contact(intercom, api):
    services.add_custom_domain(intercom, "status.intercom.com", "it@intercom.com")
    assert api[0][2] == {"instructions_recipient": "it@intercom.com"}


@pytest.mark.parametrize(
    "host, message",
    [
        ("intercom", "Enter a valid value."),
        ("https://status.intercom.com", "Enter a valid value."),
        ("statuspage.com", "Can't be one of our own domains."),
        ("admin.statuspage.com", "Can't be one of our own domains."),
    ],
)
def test_add_rejects_bad_and_reserved_hosts(intercom, api, host, message):
    with pytest.raises(ValidationError) as e:
        services.add_custom_domain(intercom, host)
    assert message in e.value.messages
    assert api == []


def test_add_rejects_a_domain_another_company_has(intercom, api):
    services.add_custom_domain(intercom, "status.intercom.com")
    with pytest.raises(ValidationError):
        services.add_custom_domain(intercom, "STATUS.intercom.com")


def test_add_keeps_no_row_if_the_api_fails(intercom, monkeypatch):
    def fail(self, host, **options):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(SaasDomains, "create_domain", fail)
    with pytest.raises(requests.ConnectionError):
        services.add_custom_domain(intercom, "status.intercom.com")
    assert not CustomDomain.objects.exists()


def test_check_dns_activates_the_domain(intercom, api):
    domain = services.add_custom_domain(intercom, "status.intercom.com")
    assert domain.label == "Waiting for DNS"
    assert services.check_dns(domain) == "valid"
    domain.refresh_from_db()
    assert domain.label == "DNS OK, waiting for HTTPS"


def _response(status):
    res = requests.Response()
    res.status_code = status
    res._content = b'{"error": "Custom domain x not found.", "error_code": "not_found"}'
    return res


def test_remove_treats_404_as_already_gone(intercom, api, monkeypatch):
    domain = services.add_custom_domain(intercom, "status.intercom.com")
    monkeypatch.setattr(requests.Session, "request", lambda *a, **kw: _response(404))
    services.remove_custom_domain(domain)
    assert not CustomDomain.objects.exists()


def test_remove_keeps_the_row_if_the_api_fails(intercom, api, monkeypatch):
    domain = services.add_custom_domain(intercom, "status.intercom.com")
    monkeypatch.setattr(requests.Session, "request", lambda *a, **kw: _response(500))
    with pytest.raises(requests.HTTPError):
        services.remove_custom_domain(domain)
    assert CustomDomain.objects.exists()
