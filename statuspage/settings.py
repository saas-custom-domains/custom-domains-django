"""Settings for Statuspage: one Django app, many customer domains."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_list(name, default=""):
    values = os.environ.get(name, default).split(",")
    return [v.strip() for v in values if v.strip()]


def env_bool(name, default):
    value = os.environ.get(name, str(default)).lower()
    return value in ("1", "true", "yes")


SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-not-secret")
DEBUG = env_bool("DEBUG", True)

# The domain customers can't claim, and the hostnames that serve the
# app itself (the dashboard, webhooks, Caddy's ask endpoint). Any other
# hostname is a customer domain. List every internal name your platform
# uses to reach the app, such as "app" for docker compose.
APP_DOMAIN = os.environ.get("APP_DOMAIN", "statuspage.com")
APP_HOSTS = env_list("APP_HOSTS", "app.statuspage.com,localhost")

# Customer domains can't be listed here, so CustomDomainMiddleware does
# the host check instead: it returns 404 for any host that isn't in
# APP_HOSTS or an active custom domain. Behind SaaS Custom Domains,
# ProxyTokenMiddleware sets the host to the customer's domain, so "*"
# is needed there too.
ALLOWED_HOSTS = ["*"]

# TLS ends at the proxy (SaaS Custom Domains or Caddy), which sends
# X-Forwarded-Proto: https. Without this, request.is_secure() is False
# and forms fail the CSRF Origin check. The local mock proxy speaks
# plain HTTP but still sends https, so compose.yaml turns this off.
if env_bool("TRUST_X_FORWARDED_PROTO", True):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# "saascustomdomains" (the default) or "caddy" to run your own proxy.
DOMAINS_PROVIDER = os.environ.get(
    "DOMAINS_PROVIDER", "saascustomdomains"
)
SCD_API_URL = os.environ.get(
    "SCD_API_URL", "https://app.saascustomdomains.com"
)

INSTALLED_APPS = [
    "companies",
    "domains",
    "status",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "domains.middleware.ProxyTokenMiddleware",
    "domains.middleware.CustomDomainMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "statuspage.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]

WSGI_APPLICATION = "statuspage.wsgi.application"

DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# SQLite keeps the example small. Use Postgres in a real app.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "db.sqlite3",
        "OPTIONS": {
            "init_command": "PRAGMA journal_mode=WAL;",
            "transaction_mode": "IMMEDIATE",
            "timeout": 5,
        },
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
