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


def test_pressing_plan_shows_every_operator_metric(base_url: str) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(base_url)
        page.get_by_test_id("plan-button").click()
        expect(page.get_by_test_id("metrics-heading")).to_contain_text("Operator")
        for metric in ("metric-demand", "metric-households", "metric-lost", "metric-unreached", "metric-slow", "metric-greedy", "metric-gain"):
            expect(page.get_by_test_id(metric)).to_have_text(re.compile(r"^[\d,]+$"), timeout=15_000)
        expect(page.get_by_test_id("metric-gap")).to_have_text(re.compile(r"^\d+(\.\d)?%$|^\D"))
        expect(page.get_by_test_id("new-stores").locator("li")).to_have_count(10)
        expect(page.get_by_test_id("new-stores").locator("li").first).to_have_text(re.compile(r"^1\. fresh [\d,]+, cannibalised [\d,]+$"))
        browser.close()
