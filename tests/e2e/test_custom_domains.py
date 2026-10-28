import time

from playwright.sync_api import Page, expect


def customer_url(host):
    # Goes through the mock proxy (see conftest.py).
    return f"http://{host}/"


def add_domain(page: Page, company, host):
    section = page.get_by_test_id(f"company-{company}")
    section.get_by_label("Domain", exact=True).fill(host)
    section.get_by_role("button", name="Add domain").click()
    return section


def test_connect_a_domain_serve_it_through_the_proxy_and_remove_it(page: Page):
    host = f"status-{int(time.time() * 1000)}.test"
    page.goto("/")
    add_domain(page, "intercom", host)
    row = page.get_by_test_id(f"domain-{host}")
    expect(row).to_be_visible()

    # The mock marks *.test as pointed after ~2s and sends webhooks.
    for _ in range(30):
        page.reload()
        if "Live" in row.inner_text():
            break
        time.sleep(0.5)
    expect(row).to_contain_text("Live")

    page.goto(customer_url(host))
    expect(page.get_by_role("heading", name="Intercom status")).to_be_visible()
    expect(page).to_have_title("Intercom status")
    # Django sees the customer's domain as the host.
    expect(page.get_by_text(f"Served on {host}")).to_be_visible()

    # A POST form on the custom domain, through the proxy, with Django's
    # CSRF Origin check on.
    page.get_by_label("Email").fill("reader@example.com")
    page.get_by_role("button", name="Subscribe to updates").click()
    expect(page.get_by_role("status")).to_have_text(
        "Subscribed to Intercom status updates."
    )

    page.goto("/")
    row.get_by_role("button", name="Remove").click()
    expect(row).to_be_hidden()
    gone = page.goto(customer_url(host))
    assert gone.status == 404


def test_a_domain_that_does_not_point_at_us_stays_pending(page: Page):
    host = f"status-{int(time.time() * 1000)}.example.com"
    page.goto("/")
    add_domain(page, "globex", host)
    row = page.get_by_test_id(f"domain-{host}")
    row.get_by_role("button", name="Check DNS").click()
    expect(row).to_contain_text("Waiting for DNS")

    row.get_by_role("button", name="Remove").click()
    expect(row).to_be_hidden()


def test_rejects_our_own_domains(page: Page):
    page.goto("/")
    section = add_domain(page, "intercom", "admin.statuspage.com")
    expect(section.get_by_role("alert")).to_have_text(
        "Can't be one of our own domains."
    )


def test_requests_that_skip_the_proxy_cannot_claim_a_domain(page: Page):
    spoofed = page.request.get("/", headers={"X-Served-For": "intercom.test"})
    assert spoofed.status == 403

    wrong_token = page.request.get(
        "/",
        headers={
            "X-Served-For": "intercom.test",
            "X-SaaS-Domains-Auth-Token": "guess",
        },
    )
    assert wrong_token.status == 403


def test_webhooks_need_the_right_token(page: Page):
    res = page.request.post(
        "/webhooks/saas-domains?token=x",
        data={"event": "domain_dns_proxy_record_valid", "domain": {"uuid": "x"}},
    )
    assert res.status == 401


def test_unknown_domains_get_a_404(page: Page):
    res = page.goto(customer_url("unknown.test"))
    assert res.status == 404
