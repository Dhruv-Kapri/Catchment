import json
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from catchment.bundle import build_bundle
from catchment.planning import Inputs
from catchment.service import create_app
from service_inputs import service_inputs

TIMING: tuple[str, ...] = ("seconds", "build_seconds", "solve_seconds")
PROVENANCE: dict[str, Any] = {
    "osm": {"source": "https://example.test/osm.pbf", "data_date": "2026-10-27T21:23:59Z"},
    "overture": {"release": "2026-10-21.0"},
    "worldpop": {"source": "https://example.test/ind_pop_2025_CN_100m_R2025A_v1.tif"},
    "viirs": {"source": "https://example.test/VNP46A4.h5"},
}
DEFAULTS: dict[str, float] = {"n_new": 10, "promise": 10, "multiplier": 1.8, "capacity": 1, "capture": 1, "competitor_density": 1}
SWEPT: dict[str, list[float]] = {   # the ticket's literal UI steps
    "n_new": list(range(1, 21)),
    "promise": list(range(8, 17)),
    "multiplier": [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0, 2.1, 2.2, 2.3, 2.4, 2.5],
    "capacity": [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2],
    "capture": [0.5, 0.75, 1, 1.25, 1.5],
    "competitor_density": [0, 0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2],
}


def untimed(body: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in body.items() if k not in TIMING}


def read_text(path: Path) -> str:
    assert path.is_file(), f"{path} was not written"
    return path.read_text()


def read_json(path: Path) -> Any:  # noqa: ANN401 - a dict or a list, as the file holds
    return json.loads(read_text(path))


def probe_app(inputs: Inputs) -> FastAPI:
    """The service plus a read-only route of the kind sibling tickets add; it goes before the static mount, as theirs do."""
    app = create_app(inputs)
    app.add_api_route("/probe", lambda: {"hexes": [1, 2, 3]}, methods=["GET"])
    app.router.routes.insert(0, app.router.routes.pop())
    return app


@pytest.fixture(scope="module")
def inputs() -> Inputs:
    return service_inputs()


@pytest.fixture(scope="module")
def site(inputs: Inputs, tmp_path_factory: pytest.TempPathFactory) -> Path:
    out: Path = tmp_path_factory.mktemp("site")
    build_bundle(probe_app(inputs), out, PROVENANCE)
    return out


def test_the_index_lists_every_swept_scenario(site: Path) -> None:
    expected: list[dict[str, float]] = [DEFAULTS] + [{**DEFAULTS, lever: v} for lever, values in SWEPT.items() for v in values if v != DEFAULTS[lever]]
    index: list[dict[str, Any]] = read_json(site / "bundle" / "index.json")
    assert len(index) == len(expected) == 61
    assert sorted(sorted(e["levers"].items()) for e in index) == sorted(sorted(e.items()) for e in expected)


def test_every_bundle_plan_equals_the_apis_response(site: Path, inputs: Inputs) -> None:
    client = TestClient(create_app(inputs))
    index: list[dict[str, Any]] = read_json(site / "bundle" / "index.json")
    assert len(index) == 61
    for entry in index:
        response = client.post("/plan", json=entry["levers"])
        assert response.status_code == 200
        assert untimed(read_json(site / "bundle" / entry["plan"])) == untimed(response.json()), entry["levers"]


def test_every_readonly_get_route_is_mirrored(site: Path, inputs: Inputs) -> None:
    assert read_json(site / "bundle" / "data" / "probe.json") == TestClient(probe_app(inputs)).get("/probe").json()
    assert [p.name for p in (site / "bundle" / "data").iterdir()] == ["probe.json"]   # not /openapi.json, /docs or the static mount


def test_the_page_is_the_site_root(site: Path) -> None:
    assert 'data-testid="plan-button"' in read_text(site / "index.html")


def test_the_bundle_carries_the_odbl_notice_and_the_provenance(site: Path) -> None:
    notice: str = read_text(site / "bundle" / "ODBL-NOTICE.txt")
    assert "ODbL" in notice and "OpenStreetMap contributors" in notice and "https://opendatacommons.org/licenses/odbl/1-0/" in notice
    meta: dict[str, Any] = read_json(site / "bundle" / "metadata.json")
    assert meta["openstreetmap"]["extract_date"] == "2026-10-27T21:23:59Z"
    assert meta["overture"]["release"] == "2026-10-21.0"
    assert meta["worldpop"]["product"] == PROVENANCE["worldpop"]["source"]
    assert meta["osrm"]["image"] == "ghcr.io/project-osrm/osrm-backend:v26.10.0-debian"   # the pin in osrm/osrm.sh
