"""The static demo bundle (ADR 0003): plans solved ahead of time, the read-only data, the ODbL notice and the provenance."""
import argparse
import json
import os
import shutil
import time
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from catchment import assumptions
from catchment.fetch import DATA
from catchment.planning import LEVERS, Scenario, load_inputs
from catchment.service import WEB, create_app

READ_ONLY: tuple[str, ...] = ("demand", "network", "levers", "assumptions")   # the read-only data the page reads


def sweep() -> list[Scenario]:
    """The default scenario, then each lever at every step of its range with the others at the default."""
    default = Scenario()
    scenarios: list[Scenario] = [default]
    for name, lever in LEVERS.items():
        for value in lever.values():
            if value != getattr(default, name):
                scenarios.append(Scenario(**{name: value}))
    return scenarios


def plan_file(scenario: Scenario) -> str:
    """Where a scenario's plan lives under bundle/: default.json, or <lever>-<value>.json for the one lever moved."""
    if (lever := scenario.moved()) is None:
        return "plans/default.json"
    return f"plans/{lever}-{getattr(scenario, lever):g}.json"


def write_json(path: Path, body: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body))


ODBL_URL: str = "https://opendatacommons.org/licenses/odbl/1-0/"
ODBL_NOTICE: str = f"""The JSON in this bundle (plans/, data/, index.json, metadata.json) is a Derivative Database of OpenStreetMap data, made available
under the Open Database License (ODbL) 1.0: {ODBL_URL}

Contains information from OpenStreetMap: (c) OpenStreetMap contributors. https://www.openstreetmap.org/copyright

The plans were computed from travel times routed on OpenStreetMap roads. The travel-time table is not published here. It
is supplied under the ODbL to anyone the plans reach who asks for it.

Other sources and their licences are in metadata.json.
"""
OVERTURE_PLACES_ATTRIBUTION: list[str] = [
    "Meta, Microsoft, PinMeTo, Krick, RenderSEO, DAC, BrightQuery, Birdeye, Uberall and OpenTravel Alliance: CDLA Permissive 2.0",
    "Foursquare: Copyright 2024 Foursquare Labs, Inc. All rights reserved. Available under Apache 2.0.",
    "AllThePlaces: CC0 1.0",
    "Overture Maps Foundation, overturemaps.org",
]
WORLDPOP_CITATION: str = (
    "Bondarenko M., Priyatikanto R., Tejedor-Garavito N., Zhang W., McKeen T., Cunningham A., Woods T., Hilton J., Cihan D., Nosatiuk B., "
    "Brinkhoff T., Tatem A., Sorichetta A.. 2025 Constrained estimates of 2015-2030 total number of people per grid square at a resolution "
    "of 3 arc (approximately 100m at the equator) R2025A version v1. Global Demographic Data Project - Funded by The Bill and Melinda Gates "
    "Foundation (INV-045237). WorldPop - School of Geography and Environmental Science, University of Southampton. DOI:10.5258/SOTON/WP00839")
OSRM_SH: Path = Path(__file__).resolve().parents[2] / "osrm" / "osrm.sh"


def osrm_image() -> str:
    """The OSRM image, read from osrm.sh so the pin lives in one place."""
    line: str = next(line for line in OSRM_SH.read_text().splitlines() if line.startswith("IMAGE="))
    return line.split('"')[1]


def metadata(provenance: dict[str, Any], solve: dict[str, Any]) -> dict[str, Any]:
    """Attribution and provenance for every source, from the data manifest and the solve record."""
    return {
        "openstreetmap": {"attribution": "(c) OpenStreetMap contributors", "licence": "ODbL 1.0", "licence_url": ODBL_URL,
                          "source": provenance["osm"]["source"], "extract_date": provenance["osm"]["data_date"]},
        "overture": {"release": provenance["overture"]["release"], "places_attribution": OVERTURE_PLACES_ATTRIBUTION},
        "worldpop": {"product": provenance["worldpop"]["source"], "licence": "CC BY 4.0", "doi": "10.5258/SOTON/WP00839",
                     "citation": WORLDPOP_CITATION},
        "viirs": {"product": provenance["viirs"]["source"], "name": "NASA Black Marble VNP46A4", "licence": "CC0",
                  "note": "NASA asks to be cited as the source."},
        "basemap": "OpenFreeMap (c) OpenMapTiles Data from OpenStreetMap",
        "osrm": {"image": osrm_image()},
        "solve": {"date": date.today().isoformat(), "method": "cpsat-from-greedy", "workers": assumptions.WORKERS, **solve},
    }


def build_bundle(app: FastAPI, out: Path, provenance: dict[str, Any]) -> dict[str, Any]:
    """Write the site under out: plans for sweep() and an index of them. Returns the solve record."""
    client = TestClient(app)
    bundle: Path = out / "bundle"
    for route in app.routes:
        if isinstance(route, APIRoute) and "GET" in route.methods and route.include_in_schema and "{" not in route.path:
            response = client.get(route.path)
            response.raise_for_status()
            write_json(bundle / "data" / f"{route.path.removeprefix('/')}.json", response.json())
    index: list[dict[str, Any]] = []
    load_before: tuple[float, float, float] = os.getloadavg()
    started = time.perf_counter()
    for scenario in sweep():
        levers: dict[str, float] = {lever: getattr(scenario, lever) for lever in LEVERS}
        response = client.post("/plan", json=levers)
        response.raise_for_status()
        file = plan_file(scenario)
        write_json(bundle / file, response.json())
        index.append({"levers": levers, "plan": file})
    write_json(bundle / "index.json", index)
    solve: dict[str, Any] = {"scenarios": len(index), "seconds": time.perf_counter() - started, "load_before": load_before, "load_after": os.getloadavg()}
    write_json(bundle / "metadata.json", metadata(provenance, solve))
    (bundle / "ODBL-NOTICE.txt").write_text(ODBL_NOTICE)
    shutil.copytree(WEB, out, dirs_exist_ok=True)
    return solve


def main() -> None:
    parser = argparse.ArgumentParser(description="Solve the sweep and write the static demo site.")
    parser.add_argument("--out", type=Path, default=Path("outputs/site"))
    parser.add_argument("--res", type=int, default=9)
    parser.add_argument("--x-pct", type=float, default=30)
    args = parser.parse_args()
    if args.out.exists():
        if any(args.out.iterdir()) and not (args.out / "bundle" / "index.json").exists():
            raise SystemExit(f"{args.out} is not empty and holds no bundle; refusing to delete it")
        shutil.rmtree(args.out)
    app = create_app(load_inputs(args.res, args.x_pct))
    solve = build_bundle(app, args.out, json.loads((DATA / "manifest.json").read_text()))
    missing: list[str] = [name for name in READ_ONLY if not (args.out / "bundle" / "data" / f"{name}.json").exists()]
    if missing:
        print(f"warning: no GET endpoint for {', '.join(missing)}, so the bundle lacks that read-only data")
    print(f"{solve['scenarios']} scenarios in {solve['seconds']:.0f} s; load average before {solve['load_before']}, after {solve['load_after']}; site in {args.out}")
