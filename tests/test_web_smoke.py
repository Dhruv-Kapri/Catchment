import dataclasses
import re
import socket
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any

import h3
import httpx
import pytest
import uvicorn
from playwright.sync_api import Page, Route, expect, sync_playwright

from catchment.planning import Plan, plan
from catchment.serialize import plan_json
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


def source_features(page: Page, source: str) -> list[dict[str, Any]]:
    """The features the map's GeoJSON source holds right now (MapLibre 5's getData is a Promise)."""
    return page.evaluate("async (id) => { const { view } = await import('/js/main.js'); const s = view.map.getSource(id); return s ? (await s.getData()).features : []; }", source)


def wait_for_features(page: Page, source: str, timeout: float = 30.0) -> list[dict[str, Any]]:
    """Poll until the source holds features (the style loads, and the plan answers, asynchronously)."""
    deadline: float = time.monotonic() + timeout
    while not (features := source_features(page, source)) and time.monotonic() < deadline:
        page.wait_for_timeout(100)
    return features


def test_pressing_plan_draws_the_stores_and_shows_every_operator_metric(base_url: str) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(base_url)
        with page.expect_response("**/plan") as planned:
            page.get_by_test_id("plan-button").click()
        body: dict[str, Any] = planned.value.json()
        expect(page.locator(".store-new")).to_have_count(10, timeout=15_000)
        assert page.locator(".store-operator").count() > 0 and page.locator(".store-competitor").count() > 0
        expect(page.get_by_test_id("metrics-heading")).to_contain_text("Operator")
        for metric in ("metric-demand", "metric-households", "metric-lost", "metric-unreached", "metric-slow", "metric-greedy", "metric-gain"):
            expect(page.get_by_test_id(metric)).to_have_text(re.compile(r"^[\d,]+$"), timeout=15_000)
        expect(page.get_by_test_id("metric-gap")).to_have_text("0.0%")
        expect(page.get_by_test_id("new-stores").locator("li")).to_have_count(10)
        expect(page.get_by_test_id("new-stores").locator("li").first).to_have_text(re.compile(r"^fresh [\d,]+, cannibalised [\d,]+$"))   # the <ol> numbers the stores
        # service areas: one fill feature per assigned hex, none for unserved hexes, one colour per store
        served: dict[str, str] = {cell: store for store, cells in body["service_areas"].items() for cell in cells}
        fills: list[dict[str, Any]] = wait_for_features(page, "service-areas")
        assert sorted(f["properties"]["cell"] for f in fills) == sorted(served)
        assert all(f["properties"]["store"] == served[f["properties"]["cell"]] for f in fills)
        colours: dict[str, set[str]] = {}
        for f in fills:
            colours.setdefault(f["properties"]["store"], set()).add(f["properties"]["colour"])
        assert all(len(c) == 1 for c in colours.values())
        assert len({c for cs in colours.values() for c in cs}) == len(colours)   # no two stores share a colour
        # selecting a new store outlines its catchment
        assert source_features(page, "catchment-outline") == []
        site: str = body["sites"][0]
        page.locator(".store-new").first.click()
        outline: list[dict[str, Any]] = wait_for_features(page, "catchment-outline")
        vertices: set[tuple[float, float]] = {(round(lng, 5), round(lat, 5)) for ring in (r for f in outline for poly in f["geometry"]["coordinates"] for r in poly) for lng, lat in ring}
        catchment_vertices: set[tuple[float, float]] = {(round(lng, 5), round(lat, 5)) for cell in body["catchments"][site] for lat, lng in h3.cell_to_boundary(cell)}
        assert vertices and vertices <= catchment_vertices
        browser.close()


@pytest.fixture(scope="module")
def greedy_plan() -> Plan:
    return plan(service_inputs())


@pytest.mark.parametrize("changes, shown", [
    (lambda g: {"method": "cpsat-from-greedy", "status": "HEURISTIC"}, {"plan-note": re.compile("^Greedy's plan kept"), "metric-gain": "0"}),
    (lambda g: {"method": "cpsat", "status": "UNKNOWN", "objective": None, "bound": None, "gap": None, "demand_covered": 1.0},
     {"plan-note": re.compile("^No plan"), "metric-gain": "no plan"}),
    (lambda g: {"method": "cpsat-from-greedy", "status": "OPTIMAL", "gap": 0.0, "demand_covered": g.greedy_demand_covered - 0.3},
     {"plan-note": "", "metric-gain": "0"}),   # a float hair under greedy is no loss, and not "-0"
    (lambda g: {"method": "cpsat-from-greedy", "status": "FEASIBLE", "gap": 0.0004}, {"metric-gap": "<0.1%"}),   # a small gap does not read as proven
])
def test_the_panel_explains_greedys_plan_and_labels_an_unknown_one(base_url: str, greedy_plan: Plan, changes: Callable[[Plan], dict[str, Any]],
                                                                   shown: dict[str, str | re.Pattern[str]]) -> None:
    crafted = plan_json(dataclasses.replace(greedy_plan, **changes(greedy_plan)))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(base_url)
        page.evaluate("async (body) => { (await import('/js/metrics.js')).showMetrics(body); }", crafted)
        for testid, text in shown.items():
            expect(page.get_by_test_id(testid)).to_have_text(text)
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
    held: list[Route] = []   # the /plan request, held so the plan is still running when the page is checked
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.route("**/plan", lambda route: held.append(route))
        page.goto(base_url)
        page.get_by_test_id("plan-button").click()
        expect(page.get_by_test_id("plan-button")).to_be_disabled()
        expect(page.get_by_test_id("elapsed")).to_have_text(re.compile(r"^Planning… (0\.[1-9]|[1-9]\d*\.\d) s$"))   # the count has moved on from 0.0
        held[0].continue_()
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


def test_a_lever_changed_while_planning_leaves_the_new_metrics_stale(base_url: str) -> None:
    held: list[Route] = []   # the /plan request, held until the lever has changed
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.route("**/plan", lambda route: held.append(route))
        page.goto(base_url)
        page.get_by_test_id("plan-button").click()
        while not held:
            page.wait_for_timeout(50)
        page.get_by_test_id("lever-promise").fill("12")   # the plan in flight is for promise 10
        held[0].continue_()
        expect(page.get_by_test_id("plan-button")).to_be_enabled(timeout=15_000)
        expect(page.get_by_test_id("metric-demand")).to_have_text(re.compile(r"^[\d,]+$"))
        expect(page.locator("#metrics")).to_have_class(re.compile("stale"))
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
