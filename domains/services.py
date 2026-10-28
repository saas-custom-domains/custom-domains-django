from django.conf import settings

from .dns import points_to_us
from .models import CustomDomain
from .saas_domains import SaasDomains
from .utils import normalize_host


def managed():
    """True with SaaS Custom Domains, False if you run Caddy yourself."""
    return settings.DOMAINS_PROVIDER == "saascustomdomains"


def add_custom_domain(company, host, dns_contact_email=""):
    domain = CustomDomain(company=company, host=normalize_host(host))
    domain.full_clean()
    domain.save()
    if not managed():
        return domain

    # Whoever manages their DNS gets step-by-step instructions
    recipient = dns_contact_email or company.dns_contact_email
    options = {"instructions_recipient": recipient} if recipient else {}
    try:
        res = SaasDomains().create_domain(domain.host, **options)
    except Exception:
        # Don't keep a domain the proxy doesn't know about.
        domain.delete()
        raise
    domain.provider_uuid = res["uuid"]
    domain.save(update_fields=["provider_uuid"])
    return domain


def check_dns(domain):
    if managed() and domain.provider_uuid:
        res = SaasDomains().verify_dns(domain.provider_uuid)
        dns_status = res["dns_status"]  # "valid", "pending" or "invalid"
    else:
        dns_status = "valid" if points_to_us(domain.host) else "invalid"

    if dns_status == "valid":
        domain.status = CustomDomain.Status.ACTIVE
        domain.save(update_fields=["status"])
    return dns_status


def remove_custom_domain(domain):
    # Proxy first, database second: if the API call fails, the row is
    # still here and the user can try again.
    if managed() and domain.provider_uuid:
        SaasDomains().delete_domain(domain.provider_uuid)
    domain.delete()
