import re
import socket
import threading
import time
from collections.abc import Iterator
from typing import Any

import h3
import pytest
import uvicorn
from playwright.sync_api import Page, expect, sync_playwright

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


def test_pressing_plan_draws_the_stores_and_shows_the_metrics(base_url: str) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(base_url)
        with page.expect_response("**/plan") as planned:
            page.get_by_test_id("plan-button").click()
        body: dict[str, Any] = planned.value.json()
        expect(page.locator(".store-new")).to_have_count(10, timeout=15_000)
        assert page.locator(".store-operator").count() > 0 and page.locator(".store-competitor").count() > 0
        for metric in ("metric-demand", "metric-households"):
            expect(page.get_by_test_id(metric)).to_have_text(re.compile(r"^[\d,]+$"))
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
