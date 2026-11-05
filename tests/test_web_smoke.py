import re
import socket
import threading
import time
from collections.abc import Iterator

import pytest
import uvicorn
from playwright.sync_api import expect, sync_playwright

from catchment.service import create_app
from service_inputs import service_inputs

pytestmark = pytest.mark.browser


@pytest.fixture(scope="module")
def base_url() -> Iterator[str]:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(service_inputs()), host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


def test_pressing_plan_draws_the_stores_and_shows_the_metrics(base_url: str) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(base_url)
        page.get_by_test_id("plan-button").click()
        expect(page.locator(".store-new")).to_have_count(10, timeout=15_000)
        assert page.locator(".store-operator").count() > 0 and page.locator(".store-competitor").count() > 0
        for metric in ("metric-demand", "metric-households"):
            expect(page.get_by_test_id(metric)).to_have_text(re.compile(r"^[\d,]+$"))
        browser.close()


def digits(text: str) -> int:
    return int(re.sub(r"\D", "", text))


def test_on_load_the_existing_network_and_market_demand_show_and_follow_the_capture_lever(base_url: str) -> None:
    total: float = float(service_inputs().demand.sum())
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(base_url)
        expect(page.locator(".store-operator")).to_have_count(8, timeout=15_000)
        expect(page.locator(".store-competitor")).to_have_count(4)
        shown = page.get_by_test_id("market-demand-total")
        expect(shown).to_have_text(re.compile(r"^[\d,]+$"))
        assert digits(shown.inner_text()) == round(total)
        page.get_by_test_id("lever-capture").fill("1.5")
        page.get_by_test_id("lever-capture").dispatch_event("input")
        expect(shown).not_to_have_text(f"{round(total):,}")
        assert digits(shown.inner_text()) == round(total * 1.5)
        body: str = page.locator("body").inner_text().lower()
        assert not [brand for brand in ("blinkit", "zepto", "instamart", "swiggy", "eternal") if brand in body]
        browser.close()
