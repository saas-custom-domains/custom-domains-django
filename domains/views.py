import hmac
import json
import logging
import os

import requests
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from companies.models import Company

from .forms import AddDomainForm
from .models import CustomDomain
from .saas_domains import api_error
from .services import add_custom_domain, check_dns, remove_custom_domain

logger = logging.getLogger(__name__)

# This example has no login. In your app, check that the signed-in user
# owns the company (and the domain) in every one of these views.


def dashboard(request, errors=None, status=200):
    companies = list(Company.objects.prefetch_related("custom_domains"))
    for company in companies:
        company.error = (errors or {}).get(company.id)
    return render(
        request,
        "domains/dashboard.html",
        {"companies": companies},
        status=status,
    )


@require_POST
def add_domain(request, company_id):
    company = get_object_or_404(Company, pk=company_id)
    form = AddDomainForm(request.POST)
    if not form.is_valid():
        error = next(iter(form.errors.values()))[0]
    else:
        try:
            add_custom_domain(
                company,
                form.cleaned_data["host"],
                form.cleaned_data["dns_contact_email"],
            )
            return redirect("dashboard")
        except ValidationError as e:
            error = " ".join(e.messages)
        except requests.RequestException as e:
            logger.exception("Could not add the domain")
            error = api_error(e) or "Could not add the domain."
    return dashboard(request, errors={company.id: error}, status=400)


@require_POST
def check_domain(request, domain_id):
    check_dns(get_object_or_404(CustomDomain, pk=domain_id))
    return redirect("dashboard")


@require_POST
def remove_domain(request, domain_id):
    remove_custom_domain(get_object_or_404(CustomDomain, pk=domain_id))
    return redirect("dashboard")


STATUS_BY_EVENT = {
    "domain_dns_proxy_record_valid": CustomDomain.Status.ACTIVE,
    "domain_dns_proxy_record_invalid": CustomDomain.Status.PENDING,
}


@csrf_exempt
@require_POST
def saas_domains_webhook(request):
    # Events: https://docs.saascustomdomains.com/webhooks
    token = request.GET.get("token", "")
    expected = os.environ.get("SCD_WEBHOOK_TOKEN", "")
    if not expected or not hmac.compare_digest(
        token.encode(), expected.encode()
    ):
        return HttpResponse(status=401)

    try:
        payload = json.loads(request.body)
        event, uuid = payload["event"], payload["domain"]["uuid"]
    except (ValueError, KeyError, TypeError):
        # Not a domain event (e.g. upstream_created) or not JSON.
        return HttpResponse(status=200)

    domains = CustomDomain.objects.filter(provider_uuid=uuid)
    status = STATUS_BY_EVENT.get(event)
    if status:
        domains.update(status=status)
    elif event == "tls_certificate_issued":
        domains.update(https_ready=True)

    return HttpResponse(status=200)


def up(request):
    """Health check for Docker and load balancers."""
    return HttpResponse("ok")
