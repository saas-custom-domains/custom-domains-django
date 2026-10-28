"""End-to-end tests against `docker compose up`.

The browser sends every request for a customer domain (*.test) to the
mock proxy, the way DNS sends a real customer domain to SaaS Custom
Domains. Host and Origin stay "intercom.test" whatever port the mock
listens on, so several stacks can run side by side.
"""

import os

import pytest

APP_PORT = os.environ.get("APP_PORT", "8000")
PROXY_PORT = os.environ.get("SCD_MOCK_PROXY_PORT", "80")


@pytest.fixture(scope="session")
def base_url():
    return f"http://localhost:{APP_PORT}"


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    return {
        **browser_type_launch_args,
        "proxy": {"server": f"http://127.0.0.1:{PROXY_PORT}", "bypass": "localhost"},
    }
