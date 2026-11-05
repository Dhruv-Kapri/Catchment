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
        a = page.get_by_test_id("scenario-a")
        a.get_by_test_id("plan-button").click()
        expect(a.locator(".store-new")).to_have_count(10, timeout=15_000)
        assert a.locator(".store-operator").count() > 0 and a.locator(".store-competitor").count() > 0
        for metric in ("metric-demand", "metric-households"):
            expect(a.get_by_test_id(metric)).to_have_text(re.compile(r"^[\d,]+$"))
        browser.close()


DIFF_KEYS: list[str] = [
    "demand_covered", "households_covered", "lost_to_capacity", "unreached", "slow_traffic_coverage",
    "greedy_demand_covered", "gain_over_greedy", "gap", "new_stores",
]


def test_copying_a_to_b_and_changing_a_lever_shows_the_difference(base_url: str) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(base_url)
        a, b = page.get_by_test_id("scenario-a"), page.get_by_test_id("scenario-b")
        expect(b.get_by_test_id("lever-n_new")).to_have_value("10")   # B starts as a copy of A
        a.get_by_test_id("lever-n_new").fill("4")
        a.get_by_test_id("plan-button").click()
        expect(a.locator(".store-new")).to_have_count(4, timeout=15_000)
        page.get_by_test_id("copy-a-to-b").click()
        expect(b.get_by_test_id("lever-n_new")).to_have_value("4")
        b.get_by_test_id("lever-n_new").fill("5")
        b.get_by_test_id("plan-button").click()
        expect(b.locator(".store-new")).to_have_count(5, timeout=15_000)
        for key in DIFF_KEYS:
            expect(page.get_by_test_id(f"diff-row-{key}")).to_be_visible()
        expect(page.get_by_test_id("diff-row-new_stores")).to_contain_text("+1")
        expect(page.get_by_test_id("diff-row-demand_covered")).to_contain_text(re.compile(r"[+−]\d"))
        browser.close()
