import dataclasses
import re
import socket
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any
from urllib.parse import urlparse

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
    """The features scenario A's map GeoJSON source holds right now (MapLibre 5's getData is a Promise)."""
    return page.evaluate("async (id) => { const s = window.catchment?.a.map.getSource(id); return s ? (await s.getData()).features : []; }", source)


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
        a = page.get_by_test_id("scenario-a")
        with page.expect_response("**/plan") as planned:
            a.get_by_test_id("plan-button").click()
        body: dict[str, Any] = planned.value.json()
        expect(a.locator(".store-new")).to_have_count(10, timeout=15_000)
        assert a.locator(".store-operator").count() > 0 and a.locator(".store-competitor").count() > 0
        expect(a.get_by_test_id("metrics-heading")).to_contain_text("Operator")
        for metric in ("metric-demand", "metric-households", "metric-lost", "metric-unreached", "metric-slow", "metric-greedy", "metric-gain"):
            expect(a.get_by_test_id(metric)).to_have_text(re.compile(r"^[\d,]+$"), timeout=15_000)
        expect(a.get_by_test_id("metric-gap")).to_have_text("0.0%")
        expect(a.get_by_test_id("new-stores").locator("li")).to_have_count(10)
        expect(a.get_by_test_id("new-stores").locator("li").first).to_have_text(re.compile(r"^fresh [\d,]+, cannibalised [\d,]+$"))   # the <ol> numbers the stores
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
        a.locator(".store-new").first.click()
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
    (lambda g: {"method": "cpsat-from-greedy", "status": "HEURISTIC", "bound": 1.0, "bound_source": "capacity", "gap": 0.125},
     {"metric-gap": "12.5% (from the capacity bound, which can be loose)"}),   # #52: a capacity-bound gap does not read as the solver's
    (lambda g: {"method": "cpsat-from-greedy", "status": "FEASIBLE", "bound": 1.0, "bound_source": "solver", "gap": 0.125}, {"metric-gap": "12.5%"}),
])
def test_the_panel_explains_greedys_plan_and_labels_an_unknown_one(base_url: str, greedy_plan: Plan, changes: Callable[[Plan], dict[str, Any]],
                                                                   shown: dict[str, str | re.Pattern[str]]) -> None:
    crafted = plan_json(dataclasses.replace(greedy_plan, **changes(greedy_plan)))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(base_url)
        a = page.get_by_test_id("scenario-a")
        page.evaluate("async (body) => { (await import('/js/metrics.js')).showMetrics(document.querySelector('[data-testid=scenario-a]'), body); }", crafted)
        for testid, text in shown.items():
            expect(a.get_by_test_id(testid)).to_have_text(text)
        browser.close()


def test_the_lever_inputs_come_from_the_levers_endpoint(base_url: str) -> None:
    published: dict[str, dict[str, float]] = httpx.get(f"{base_url}/levers").json()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(base_url)
        a = page.get_by_test_id("scenario-a")
        for lever, spec in published.items():
            field = a.get_by_test_id(f"lever-{lever}")
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
        a = page.get_by_test_id("scenario-a")
        a.get_by_test_id("plan-button").click()
        expect(a.get_by_test_id("plan-button")).to_be_disabled()
        expect(a.get_by_test_id("elapsed")).to_have_text(re.compile(r"^Planning… (0\.[1-9]|[1-9]\d*\.\d) s$"))   # the count has moved on from 0.0
        held[0].continue_()
        expect(a.get_by_test_id("plan-button")).to_be_enabled(timeout=15_000)
        expect(a.get_by_test_id("elapsed")).to_have_text(re.compile(r"^Planned in \d+\.\d s$"))
        browser.close()


def test_a_late_network_response_leaves_a_drawn_plans_stores_on_the_map(base_url: str) -> None:
    held: list[Route] = []   # the /network request, held until the plan's stores are drawn
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.route("**/network", lambda route: held.append(route))
        page.route("https://tiles.openfreemap.org/**", lambda route: None)   # the style never loads, so the plan stays between its stores and its layers
        page.goto(base_url)
        a = page.get_by_test_id("scenario-a")
        a.get_by_test_id("plan-button").click()
        expect(a.locator(".store-new")).to_have_count(10, timeout=15_000)
        expect(a.get_by_test_id("market-demand-total")).to_have_text("-")   # the network has not arrived
        held[0].continue_()
        expect(a.get_by_test_id("market-demand-total")).not_to_have_text("-")   # it has now, and the page has run its loader
        expect(a.locator(".store-new")).to_have_count(10)
        browser.close()


def test_a_failed_levers_request_shows_its_own_error_and_disables_plan(base_url: str) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.route("**/levers", lambda route: route.fulfill(status=500))
        page.goto(base_url)
        a = page.get_by_test_id("scenario-a")
        expect(a.get_by_test_id("plan-button")).to_be_disabled()
        expect(a.locator(".error")).to_contain_text("levers")
        page.wait_for_timeout(1_000)   # the assumptions have loaded by now; they must not overwrite the message
        expect(a.locator(".error")).to_contain_text("levers")
        browser.close()


def test_changing_a_lever_greys_the_metrics_until_the_next_plan(base_url: str) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(base_url)
        a = page.get_by_test_id("scenario-a")
        metrics = a.locator(".metrics")
        a.get_by_test_id("lever-promise").fill("11")
        expect(metrics).not_to_have_class(re.compile("stale"))   # nothing to grey before a plan
        a.get_by_test_id("plan-button").click()
        expect(a.get_by_test_id("metric-demand")).to_have_text(re.compile(r"^[\d,]+$"), timeout=15_000)
        expect(metrics).not_to_have_class(re.compile("stale"))
        a.get_by_test_id("lever-promise").fill("12")
        expect(metrics).to_have_class(re.compile("stale"))
        a.get_by_test_id("plan-button").click()
        expect(metrics).not_to_have_class(re.compile("stale"), timeout=15_000)
        browser.close()


def test_a_lever_changed_while_planning_leaves_the_new_metrics_stale(base_url: str) -> None:
    held: list[Route] = []   # the /plan request, held until the lever has changed
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.route("**/plan", lambda route: held.append(route))
        page.goto(base_url)
        a = page.get_by_test_id("scenario-a")
        a.get_by_test_id("plan-button").click()
        while not held:
            page.wait_for_timeout(50)
        a.get_by_test_id("lever-promise").fill("12")   # the plan in flight is for promise 10
        held[0].continue_()
        expect(a.get_by_test_id("plan-button")).to_be_enabled(timeout=15_000)
        expect(a.get_by_test_id("metric-demand")).to_have_text(re.compile(r"^[\d,]+$"))
        expect(a.locator(".metrics")).to_have_class(re.compile("stale"))
        browser.close()


def digits(text: str) -> int:
    return int(re.sub(r"\D", "", text))


def test_on_load_the_existing_network_and_market_demand_show_and_follow_the_capture_lever(base_url: str) -> None:
    total: float = float(service_inputs().demand.sum())
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(base_url)
        a = page.get_by_test_id("scenario-a")
        expect(a.locator(".store-operator")).to_have_count(8, timeout=15_000)
        expect(a.locator(".store-competitor")).to_have_count(4)
        shown = a.get_by_test_id("market-demand-total")
        expect(shown).to_have_text(re.compile(r"^[\d,]+$"))
        assert digits(shown.inner_text()) == round(total)
        a.get_by_test_id("lever-capture").fill("1.5")
        a.get_by_test_id("lever-capture").dispatch_event("input")
        expect(shown).not_to_have_text(f"{round(total):,}")
        assert digits(shown.inner_text()) == round(total * 1.5)
        body: str = page.locator("body").inner_text().lower()
        assert not [brand for brand in ("blinkit", "zepto", "instamart", "swiggy", "eternal") if brand in body]
        browser.close()


def test_each_scenario_has_its_own_market_demand_that_follows_its_own_capture_lever(base_url: str) -> None:
    total: float = float(service_inputs().demand.sum())
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(base_url)
        a, b = page.get_by_test_id("scenario-a"), page.get_by_test_id("scenario-b")
        shown_a, shown_b = a.get_by_test_id("market-demand-total"), b.get_by_test_id("market-demand-total")
        for shown in (shown_a, shown_b):
            expect(shown).to_have_text(re.compile(r"^[\d,]+$"))
            assert digits(shown.inner_text()) == round(total)
        a.get_by_test_id("lever-capture").fill("1.5")
        a.get_by_test_id("lever-capture").dispatch_event("input")
        expect(shown_a).not_to_have_text(f"{round(total):,}")
        assert digits(shown_a.inner_text()) == round(total * 1.5)
        assert digits(shown_b.inner_text()) == round(total)   # B's lever did not move
        browser.close()


def test_changing_a_lever_in_one_scenario_greys_only_its_metrics(base_url: str) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(base_url)
        a, b = page.get_by_test_id("scenario-a"), page.get_by_test_id("scenario-b")
        for scenario in (a, b):
            scenario.get_by_test_id("plan-button").click()
            expect(scenario.get_by_test_id("metric-demand")).to_have_text(re.compile(r"^[\d,]+$"), timeout=15_000)
        a.get_by_test_id("lever-promise").fill("12")
        expect(a.locator(".metrics")).to_have_class(re.compile("stale"))
        expect(b.locator(".metrics")).not_to_have_class(re.compile("stale"))
        browser.close()


def test_copying_a_to_b_carries_the_capture_lever_to_bs_demand_layer_and_greys_bs_metrics(base_url: str) -> None:
    total: float = float(service_inputs().demand.sum())
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(base_url)
        a, b = page.get_by_test_id("scenario-a"), page.get_by_test_id("scenario-b")
        b.get_by_test_id("plan-button").click()
        expect(b.get_by_test_id("metric-demand")).to_have_text(re.compile(r"^[\d,]+$"), timeout=15_000)
        expect(b.locator(".metrics")).not_to_have_class(re.compile("stale"))
        a.get_by_test_id("lever-capture").fill("1.5")
        page.get_by_test_id("copy-a-to-b").click()
        expect(b.get_by_test_id("lever-capture")).to_have_value("1.5")
        assert digits(b.get_by_test_id("market-demand-total").inner_text()) == round(total * 1.5)
        expect(b.locator(".metrics")).to_have_class(re.compile("stale"))   # B's plan is for the levers it had before the copy
        browser.close()


def test_the_levers_demand_network_and_assumptions_are_fetched_once_for_both_scenarios(base_url: str) -> None:
    shared: set[str] = {"/levers", "/demand", "/network", "/assumptions"}
    requested: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.on("request", lambda request: requested.append(urlparse(request.url).path))
        page.goto(base_url)
        b = page.get_by_test_id("scenario-b")
        expect(b.get_by_test_id("spot-check-note")).to_be_visible(timeout=15_000)
        expect(b.locator(".store-operator")).to_have_count(8, timeout=15_000)
        assert sorted(path for path in requested if path in shared) == sorted(shared)
        browser.close()


def test_the_assumptions_the_spot_check_and_the_credits_are_visible(base_url: str) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(base_url)
        for side in ("a", "b"):   # each scenario's panel has its own note by its own congestion lever
            scenario = page.get_by_test_id(f"scenario-{side}")
            note = scenario.get_by_test_id("spot-check-note")
            expect(note).to_contain_text("Spot check")
            expect(note).to_contain_text("1.79")
            follows_multiplier = scenario.evaluate(
                "(section) => section.querySelector('[data-testid=lever-multiplier]').closest('label').nextElementSibling"
                " === section.querySelector('[data-testid=spot-check-note]')")
            assert follows_multiplier
        page.get_by_test_id("assumptions-button").click()
        drawer = page.get_by_test_id("assumptions-drawer")
        expect(drawer.get_by_role("row").filter(has_text="Household size")).to_be_visible()
        expect(page.get_by_test_id("network-seed")).to_contain_text("2026")
        expect(page.get_by_test_id("network-seed")).to_contain_text("synthetic")
        for credit in ("OpenStreetMap", "WorldPop", "Black Marble", "Overture", "OpenFreeMap"):
            expect(page.get_by_test_id("credits")).to_contain_text(credit)
        attribution = page.locator(".maplibregl-ctrl-attrib").first
        expect(attribution).to_contain_text("OpenStreetMap")
        expect(attribution).to_contain_text("WorldPop")
        browser.close()


DIFF_KEYS: list[str] = [
    "demand_covered", "households_covered", "lost_to_capacity", "unreached", "slow_traffic_coverage",
    "greedy_demand_covered", "gain_over_greedy", "gap", "new_stores",
]


def test_the_difference_table_shows_no_minus_zero(base_url: str, greedy_plan: Plan) -> None:
    """A plan a float hair under greedy has gained nothing: "0", not "-0" (as the panel, #46)."""
    a: dict[str, Any] = plan_json(greedy_plan)
    b: dict[str, Any] = plan_json(dataclasses.replace(greedy_plan, demand_covered=greedy_plan.greedy_demand_covered - 0.3))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(base_url)
        rows: list[dict[str, str]] = page.evaluate("async ([a, b]) => (await import('/js/compare.js')).diffRows(a, b)", [a, b])
        gain: dict[str, str] = next(r for r in rows if r["key"] == "gain_over_greedy")
        assert (gain["a"], gain["b"], gain["delta"]) == ("0", "0", "0")
        browser.close()


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
        for key in DIFF_KEYS:   # the table waits for both maps' basemap load (view.ready), which can trail the markers by seconds
            expect(page.get_by_test_id(f"diff-row-{key}")).to_be_visible(timeout=15_000)
        expect(page.get_by_test_id("diff-row-new_stores")).to_contain_text("+1")
        expect(page.get_by_test_id("diff-row-demand_covered")).to_contain_text(re.compile(r"[+−]\d"))
        browser.close()


def test_panning_or_zooming_either_map_moves_the_other(base_url: str) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(base_url)
        page.wait_for_function("window.catchment && window.catchment.a.map.loaded() && window.catchment.b.map.loaded()", timeout=20_000)

        def camera(side: str) -> list[float]:
            return page.evaluate(f"(() => {{ const m = window.catchment.{side}.map; return [m.getCenter().lng, m.getCenter().lat, m.getZoom()]; }})()")

        page.evaluate("window.catchment.a.map.jumpTo({ center: [77.2, 28.6], zoom: 13 })")
        expect_close(page, "b", [77.2, 28.6, 13.0])
        page.evaluate("window.catchment.b.map.jumpTo({ center: [77.0, 28.4], zoom: 12 })")
        expect_close(page, "a", [77.0, 28.4, 12.0])
        before = camera("a")
        box = page.get_by_test_id("scenario-a").get_by_test_id("map").bounding_box()
        assert box is not None
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.mouse.wheel(0, -300)
        page.wait_for_function(f"Math.abs(window.catchment.a.map.getZoom() - {before[2]}) > 0.01", timeout=10_000)
        page.wait_for_function("!window.catchment.a.map.isMoving()", timeout=10_000)
        expect_close(page, "b", camera("a"))
        assert camera("b")[2] != pytest.approx(before[2], abs=0.01)
        browser.close()


def expect_close(page: Page, side: str, want: list[float]) -> None:
    page.wait_for_function(
        f"(() => {{ const m = window.catchment.{side}.map, w = {want}; "
        "return Math.abs(m.getCenter().lng - w[0]) < 1e-6 && Math.abs(m.getCenter().lat - w[1]) < 1e-6 && Math.abs(m.getZoom() - w[2]) < 1e-6; })()",
        timeout=5_000,
    )
