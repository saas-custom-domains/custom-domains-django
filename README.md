# Custom domains in Django

An example Django 6.1 app where each customer connects their own domain. It's a small status page product, Statuspage: every company gets a status page, and it can serve it on `status.theircompany.com` instead of a Statuspage URL.

It goes with the guide [How to Add Custom Domains to a Django App](https://saascustomdomains.com/blog/posts/implement-custom-domains-in-your-django-saas-app).

What's in it:

- `CustomDomainMiddleware` finds the company from the request's hostname and switches to a separate URLconf for status pages. Unknown and unverified domains get a 404.
- Requests from the [SaaS Custom Domains](https://saascustomdomains.com) proxy are accepted only with the upstream's auth token, so nobody can claim a customer's domain by sending `X-Served-For` themselves.
- Forms on custom domains pass Django's CSRF check behind the proxy (see [Forms behind the proxy](#forms-behind-the-proxy-origin-checking-failed)).
- A dashboard to add a domain, check its DNS and remove it. Webhooks update the status.
- SaaS Custom Domains issues and renews the HTTPS certificate for every customer domain, so the app has no TLS code.

## Run it in 2 minutes

You need Docker.

```bash
git clone https://github.com/saas-custom-domains/custom-domains-django
cd custom-domains-django
docker compose up --build
```

1. Open http://localhost:8000 and add `intercom.localhost` to Intercom.
2. Within a few seconds the status changes to **Live**: the mock API "found" the DNS records and sent a webhook.
3. Open http://intercom.localhost. The request goes through the mock proxy on port 80, the same way a real customer domain goes through SaaS Custom Domains, and you see Intercom's status page. Try the subscribe form.

`*.localhost` always resolves to your own machine in Chrome, Firefox, Safari and curl, so there's nothing to add to `/etc/hosts`.

The mock is [scd-mock](https://github.com/saas-custom-domains/scd-mock): a local copy of the SaaS Custom Domains API and proxy, so you can try everything without an account.

### Without Docker

You need Python 3.12 or newer, and Docker for the mock.

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
set -a && . ./.env && set +a
python manage.py migrate
python manage.py runserver

# in another terminal: the mock, pointed at the app on your machine
SCD_MOCK_UPSTREAM_HOST=host.docker.internal \
SCD_MOCK_WEBHOOK_URL=http://host.docker.internal:8000/webhooks/saas-domains \
docker compose up scd-mock
```

Then follow the same steps: add `intercom.localhost` at http://localhost:8000 and open http://intercom.localhost.

## How it works

```
Browser ── status.intercom.com ──▶ SaaS Custom Domains ──▶ your Django app
                                   (TLS certificate,       Host: app.statuspage.com
                                    proxy)                 X-Served-For: status.intercom.com
                                                           X-SaaS-Domains-Auth-Token: …
```

| File | What it does |
| --- | --- |
| `domains/middleware.py` | `ProxyTokenMiddleware` checks the proxy token; `CustomDomainMiddleware` finds the company and switches URLconf |
| `domains/utils.py` | `host_from()`, the one place that reads the hostname |
| `domains/models.py` | `CustomDomain`: normalized, unique host, status, reserved-domain check |
| `statuspage/urls_custom_domains.py` | The only URLs a custom domain can reach |
| `status/views.py` | The status page and its subscribe form |
| `domains/services.py` | Add, check and remove domains through the API |
| `domains/saas_domains.py` | API client for SaaS Custom Domains (`requests`) |
| `domains/views.py` | Dashboard, webhook endpoint, health check |

Settings that matter, in `statuspage/settings.py`: `APP_HOSTS` (hosts that serve the app itself), `APP_DOMAIN` (customers can't claim it), `ALLOWED_HOSTS = ["*"]` and `SECURE_PROXY_SSL_HEADER`.

## Django errors you'll hit, and the fixes

### "Invalid HTTP_HOST header"

With a normal `ALLOWED_HOSTS` list, the first request for a customer's domain gets `400 Bad Request` and this in the log:

```text
Invalid HTTP_HOST header: 'status.intercom.com'. You may need to add 'status.intercom.com' to ALLOWED_HOSTS.
```

`ALLOWED_HOSTS` is a fixed list and customer domains aren't. This app sets `ALLOWED_HOSTS = ["*"]` and lets `CustomDomainMiddleware`, which runs right after `SecurityMiddleware`, return 404 for any host that isn't in `APP_HOSTS` or an active custom domain.

### Forms behind the proxy: "Origin checking failed"

SaaS Custom Domains sends your app's own hostname in `Host` and `X-Forwarded-Host`, so hosting platforms route the request to you and apps that only work on their own domain keep working. The customer's domain arrives separately in `X-Served-For`.

Django's CSRF check compares the browser's `Origin` with `request.get_host()`. If your app has forms on custom domains, it needs to see the customer's domain there, or every POST fails with `403 CSRF verification failed. Request aborted.` and this in the log:

```text
Forbidden (Origin checking failed - https://status.intercom.com does not match any trusted origins.): /subscribe
```

`CSRF_TRUSTED_ORIGINS` doesn't help, for the same reason as `ALLOWED_HOSTS`. So once `ProxyTokenMiddleware` has checked the token, it sets the host to the customer's domain:

```python
request.META["HTTP_HOST"] = served_for
```

From then on `request.get_host()`, `request.build_absolute_uri()`, redirects and the CSRF check all use the customer's domain. Keep `USE_X_FORWARDED_HOST` off (the default): with it on, Django reads `X-Forwarded-Host`, which is your own hostname, and the form fails again. (SaaS Custom Domains support can also send the customer's domain in `X-Forwarded-Host` for your account.)

`SECURE_PROXY_SSL_HEADER` is needed too. TLS ends at the proxy, so without it Django thinks the request is plain HTTP, expects an `http://` origin, and fails with the same message.

### Health checks and webhooks get 404

Load balancers and Docker call the health check by IP address, and the mock (like many platforms) sends webhooks to an internal hostname such as `app:8000`. Neither is a customer domain, so the middleware would answer 404. `/up` skips the host check, and `APP_HOSTS` must list every internal hostname your own traffic arrives on (`compose.yaml` adds `app`).

### Locally: the mock is plain HTTP

Production always sends `X-Forwarded-Proto: https`. The mock proxy speaks plain HTTP, so the browser's origin is `http://intercom.localhost`, and if the mock claimed `https`, Django would expect an `https://` origin and fail the form with `Origin checking failed - http://intercom.localhost does not match any trusted origins.` That's why `compose.yaml` sets `SCD_MOCK_FORWARDED_PROTO=http`.

## Use it with your SaaS Custom Domains account

1. [Create an API token](https://app.saascustomdomains.com/api_tokens) and an upstream pointing at your deployed app (`SaasDomains().create_upstream("app.yourapp.com")` from `python manage.py shell`, or the dashboard).
2. Set the environment variables from `.env.example`: `SCD_API_TOKEN`, `SCD_ACCOUNT_UUID`, `SCD_UPSTREAM_UUID`, `PROXY_AUTH_TOKEN` (the upstream's auth token), `SCD_WEBHOOK_TOKEN` (from the webhook you create in the dashboard), `APP_HOSTS`, `APP_DOMAIN` and `SECRET_KEY`. Set `DEBUG=false`.
3. Remove `SCD_API_URL` so the client talks to the real API.

Your customers point a CNAME at `in.saascustomdomains.com` (or A records at our two static IPs for a root domain). See the [docs](https://docs.saascustomdomains.com).

## Tests

```bash
pytest                                  # unit tests (pytest-django)
docker compose up -d --build --wait
playwright install chromium
pytest tests/e2e                        # end to end, through the mock proxy
```

The unit tests include the failures above: a custom domain with a normal `ALLOWED_HOSTS`, and the subscribe form behind the proxy without the host change, with `USE_X_FORWARDED_HOST` on, and without `SECURE_PROXY_SSL_HEADER`. Each checks Django's exact log message.

The end-to-end tests use `*.test` domains and send the browser's requests for them to the mock proxy, so nothing depends on DNS or on port 80. To run a second stack side by side, set `APP_PORT`, `SCD_MOCK_API_PORT` and `SCD_MOCK_PROXY_PORT` for both `docker compose` and `pytest tests/e2e`.

CI runs both on every push and once a week, so a new Django release that breaks something shows up here first.

## Tested with

| | Version |
| --- | --- |
| Django | 6.1.2 |
| Python | 3.13 |
| requests | 2.34.2 |

Last checked: 2026-10-29.

## Not production-ready on purpose

There's no login. In your app, check in every dashboard view that the signed-in user owns the company and the domain. SQLite keeps the example small; use Postgres. Call the API from a background task if you don't want it inside the web request.

## License

MIT
