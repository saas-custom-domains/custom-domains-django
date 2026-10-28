def host_from(request):
    # Behind SaaS Custom Domains, Host is your own hostname and the
    # customer's domain is in X-Served-For. ProxyTokenMiddleware has
    # already rejected the request if the proxy's token was missing.
    host = request.headers.get("X-Served-For") or request.get_host()
    return host.split(":")[0].lower()


def normalize_host(value):
    # "Status.Intercom.com." and "status.intercom.com" are the same host
    host = value.strip().lower().rstrip(".")
    try:
        # Internationalized domains are stored as punycode.
        return host.encode("idna").decode()
    except UnicodeError:
        return host  # the model's validators reject it
