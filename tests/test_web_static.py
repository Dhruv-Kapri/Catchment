import functools
import http.server
import re
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from catchment.bundle import build_bundle
from catchment.service import create_app
from service_inputs import service_inputs

pytestmark = pytest.mark.browser


@pytest.fixture(scope="module")
def static_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """The built site on a plain static server: no catchment service is running."""
    site: Path = tmp_path_factory.mktemp("site")
    build_bundle(create_app(service_inputs()), site, {
        "osm": {"source": "x", "data_date": "x"}, "overture": {"release": "x"}, "worldpop": {"source": "x"}, "viirs": {"source": "x"}})
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=site)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join(timeout=10)


def test_the_static_page_plans_from_the_bundle_and_resets_the_other_levers(static_url: str) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(static_url)
        a, b = page.get_by_test_id("scenario-a"), page.get_by_test_id("scenario-b")
        expect(page.get_by_test_id("static-notice")).to_be_visible()
        for scenario in (a, b):
            expect(scenario.locator(".maplibregl-ctrl-attrib-inner")).to_contain_text("© OpenStreetMap contributors", timeout=15_000)   # ADR 0003: the published plans are ODbL
        a.get_by_test_id("plan-button").click()
        expect(a.locator(".store-new")).to_have_count(10, timeout=15_000)
        a.get_by_test_id("lever-n_new").fill("5")
        a.get_by_test_id("plan-button").click()
        expect(a.locator(".store-new")).to_have_count(5, timeout=15_000)
        a.get_by_test_id("lever-promise").fill("12")
        expect(a.get_by_test_id("lever-n_new")).to_have_value("10")
        a.get_by_test_id("plan-button").click()
        expect(a.locator(".store-new")).to_have_count(10, timeout=15_000)
        expect(a.get_by_test_id("error")).to_have_text("")
        b.get_by_test_id("lever-n_new").fill("5")
        a.get_by_test_id("lever-promise").fill("11")
        expect(b.get_by_test_id("lever-n_new")).to_have_value("5")   # each scenario resets its own other levers, not the other scenario's
        browser.close()


def test_a_lever_reset_to_its_default_recolours_the_demand_layer(static_url: str) -> None:
    """Moving another lever puts capture back to its default; the market demand shown must follow it (#44 in the static demo)."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(static_url)
        a = page.get_by_test_id("scenario-a")
        total = a.get_by_test_id("market-demand-total")
        expect(total).to_have_text(re.compile(r"^[\d,]+$"), timeout=15_000)
        at_default: str = total.inner_text()
        a.get_by_test_id("lever-capture").fill("1.5")
        expect(total).not_to_have_text(at_default)
        a.get_by_test_id("lever-n_new").fill("5")
        expect(a.get_by_test_id("lever-capture")).to_have_value("1")
        expect(total).to_have_text(at_default)
        browser.close()


def test_the_bundle_index_is_fetched_when_plan_is_first_pressed_not_on_load(static_url: str) -> None:
    requested: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.on("request", lambda request: requested.append(request.url))
        page.goto(static_url)
        a = page.get_by_test_id("scenario-a")
        expect(a.get_by_test_id("market-demand-total")).to_have_text(re.compile(r"^[\d,]+$"), timeout=15_000)
        assert [url for url in requested if url.endswith("bundle/index.json")] == []
        a.get_by_test_id("plan-button").click()
        expect(a.locator(".store-new")).to_have_count(10, timeout=15_000)
        assert len([url for url in requested if url.endswith("bundle/index.json")]) == 1
        browser.close()


def test_a_missing_bundle_index_is_an_error_and_never_a_post_to_the_service(static_url: str) -> None:
    posted: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.route("**/bundle/index.json", lambda route: route.fulfill(status=500))
        page.on("request", lambda request: posted.append(request.url) if request.method == "POST" else None)
        page.goto(static_url)
        a = page.get_by_test_id("scenario-a")
        expect(page.get_by_test_id("static-notice")).to_be_visible()
        a.get_by_test_id("plan-button").click()
        expect(a.get_by_test_id("error")).not_to_have_text("", timeout=15_000)
        assert posted == []
        browser.close()
