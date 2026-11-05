import re
import socket
import threading
import time
from collections.abc import Iterator

import httpx
import pytest
import uvicorn
from playwright.sync_api import Route, expect, sync_playwright

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


def test_the_lever_inputs_come_from_the_levers_endpoint(base_url: str) -> None:
    published: dict[str, dict[str, float]] = httpx.get(f"{base_url}/levers").json()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(base_url)
        for lever, spec in published.items():
            field = page.get_by_test_id(f"lever-{lever}")
            expect(field).to_have_attribute("min", f"{spec['min']:g}")
            expect(field).to_have_attribute("max", f"{spec['max']:g}")
            expect(field).to_have_attribute("step", f"{spec['step']:g}")
            expect(field).to_have_value(f"{spec['default']:g}")
        browser.close()


def test_the_elapsed_seconds_show_while_a_plan_runs(base_url: str) -> None:
    def slow(route: Route) -> None:
        time.sleep(1.5)
        route.continue_()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.route("**/plan", slow)
        page.goto(base_url)
        page.get_by_test_id("plan-button").click()
        expect(page.get_by_test_id("plan-button")).to_be_disabled()
        expect(page.get_by_test_id("elapsed")).to_have_text(re.compile(r"^Planning… \d+\.\d s$"))
        expect(page.get_by_test_id("plan-button")).to_be_enabled(timeout=15_000)
        expect(page.get_by_test_id("elapsed")).to_have_text(re.compile(r"^Planned in \d+\.\d s$"))
        browser.close()


def test_changing_a_lever_greys_the_metrics_until_the_next_plan(base_url: str) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(base_url)
        metrics = page.locator("#metrics")
        page.get_by_test_id("lever-promise").fill("11")
        expect(metrics).not_to_have_class(re.compile("stale"))   # nothing to grey before a plan
        page.get_by_test_id("plan-button").click()
        expect(page.get_by_test_id("metric-demand")).to_have_text(re.compile(r"^[\d,]+$"), timeout=15_000)
        expect(metrics).not_to_have_class(re.compile("stale"))
        page.get_by_test_id("lever-promise").fill("12")
        expect(metrics).to_have_class(re.compile("stale"))
        page.get_by_test_id("plan-button").click()
        expect(metrics).not_to_have_class(re.compile("stale"), timeout=15_000)
        browser.close()
