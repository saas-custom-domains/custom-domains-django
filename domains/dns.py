# Used when you run the proxy yourself (DOMAINS_PROVIDER=caddy). With
# SaaS Custom Domains, the API checks DNS for you.
import os

import dns.exception
import dns.resolver

CNAME_TARGET = os.environ.get("CNAME_TARGET", "in.statuspage.com")
OUR_IPS = set(os.environ.get("SERVER_IPS", "192.0.2.1").split(","))


def records(host, rtype):
    try:
        answer = dns.resolver.resolve(host, rtype)
    except dns.exception.DNSException:
        return set()
    return {r.to_text().rstrip(".").lower() for r in answer}


def points_to_us(host):
    # *.localhost always resolves to this machine.
    if host.endswith(".localhost"):
        return True
    if CNAME_TARGET in records(host, "CNAME"):
        return True
    return bool(records(host, "A") & OUR_IPS)
