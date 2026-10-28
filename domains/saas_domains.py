# A small client for the SaaS Custom Domains API.
# Docs: https://docs.saascustomdomains.com/custom-domains
import os

import requests
from django.conf import settings


class SaasDomains:
    def __init__(self):
        self.base = f"{settings.SCD_API_URL}/api/v1/accounts"
        self.account = os.environ["SCD_ACCOUNT_UUID"]
        self.session = requests.Session()
        token = os.environ["SCD_API_TOKEN"]
        self.session.headers["Authorization"] = f"Bearer {token}"

    def create_upstream(self, host):
        return self._request("POST", "upstreams", {"host": host})

    def create_domain(self, host, **options):
        body = {"host": host, **options}
        return self._request("POST", self._domains(), body)

    def verify_dns(self, uuid):
        path = f"{self._domains()}/{uuid}/verify_dns_records"
        return self._request("POST", path)

    def delete_domain(self, uuid):
        try:
            return self._request("DELETE", f"{self._domains()}/{uuid}")
        except requests.HTTPError as e:
            # Already gone is fine: the goal is that it doesn't exist.
            if e.response.status_code != 404:
                raise

    def _domains(self):
        upstream = os.environ["SCD_UPSTREAM_UUID"]
        return f"upstreams/{upstream}/custom_domains"

    def _request(self, method, path, body=None):
        url = f"{self.base}/{self.account}/{path}"
        res = self.session.request(method, url, json=body, timeout=10)
        res.raise_for_status()
        return res.json()


def api_error(exc):
    """The API's message for a failed call, e.g. "Host has already been taken"."""
    if isinstance(exc, requests.HTTPError):
        try:
            return exc.response.json()["error"]
        except (ValueError, KeyError, TypeError):
            pass
    return None
