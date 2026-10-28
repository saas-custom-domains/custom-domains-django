import hmac
import os

from django.conf import settings
from django.http import Http404, HttpResponseForbidden

from .models import CustomDomain
from .utils import host_from

# Load balancers and Docker call the health check by IP address, which
# is neither an app host nor a custom domain.
HEALTH_CHECK_PATH = "/up"


class ProxyTokenMiddleware:
    # List it before CustomDomainMiddleware in settings.MIDDLEWARE

    def __init__(self, get_response):
        self.get_response = get_response
        # Unset or empty means no request may use X-Served-For.
        self.expected = os.environ.get("PROXY_AUTH_TOKEN", "").encode()

    def __call__(self, request):
        served_for = request.headers.get("X-Served-For")
        if served_for:
            token = request.headers.get("X-SaaS-Domains-Auth-Token", "")
            if not self.expected or not hmac.compare_digest(
                token.encode(), self.expected
            ):
                return HttpResponseForbidden()

            # The proxy sends your own hostname in Host. The token proves
            # this request came through it, so hand Django the customer's
            # domain instead: the CSRF Origin check, redirects and
            # build_absolute_uri() all use request.get_host().
            request.META["HTTP_HOST"] = served_for

        return self.get_response(request)


class CustomDomainMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.company = None
        if request.path == HEALTH_CHECK_PATH:
            return self.get_response(request)

        host = host_from(request)

        if host not in settings.APP_HOSTS:
            domain = (
                CustomDomain.objects.select_related("company")
                .filter(host=host, status=CustomDomain.Status.ACTIVE)
                .first()
            )
            if domain is None:
                raise Http404("Unknown domain")

            request.company = domain.company
            request.urlconf = "statuspage.urls_custom_domains"

        return self.get_response(request)
