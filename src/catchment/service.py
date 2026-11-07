"""The live service: POST /plan and the web map."""
import argparse
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from catchment.planning import LEVERS, Inputs, Scenario, load_inputs, plan
from catchment.serialize import assumptions_json, demand_json, network_json, plan_json

CACHE_SIZE: int = 64   # plans remembered per service
WEB: Path = Path(__file__).resolve().parents[2] / "web"


def create_app(inputs: Inputs, web_dir: Path = WEB) -> FastAPI:
    """The service over inputs the caller loaded once."""
    app = FastAPI()
    planning = threading.Lock()                               # one plan at a time; sync endpoints run in a threadpool
    cache_lock = threading.Lock()                             # held only to read or write the cache, so a cached plan never waits for a solve
    cache: OrderedDict[Scenario, dict[str, Any]] = OrderedDict()   # the most recent CACHE_SIZE plans, by scenario

    @app.get("/levers")
    def get_levers() -> dict[str, dict[str, float | str]]:
        """Each lever's range, step, default and label."""
        return {name: {"min": lever.low, "max": lever.high, "step": lever.step, "default": lever.default, "label": lever.label} for name, lever in LEVERS.items()}

    assumed: dict[str, Any] = assumptions_json(inputs)

    @app.post("/plan")
    def post_plan(levers: dict[str, Any]) -> dict[str, Any]:
        """Plan the scenario the six levers describe; an omitted lever takes its default. The seed is not a lever."""
        for key in levers:
            if key not in LEVERS:
                raise HTTPException(status_code=422, detail=f"{key} is not a lever")
        try:
            scenario = Scenario(**levers)
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        def cached() -> dict[str, Any] | None:
            with cache_lock:
                if scenario in cache:
                    cache.move_to_end(scenario)
                return cache.get(scenario)

        if (body := cached()) is not None:
            return body
        with planning:
            if (body := cached()) is not None:   # the same scenario was planned while this request waited its turn
                return body
            body = plan_json(plan(inputs, scenario, method="cpsat-from-greedy"))
            with cache_lock:
                cache[scenario] = body
                if len(cache) > CACHE_SIZE:
                    cache.popitem(last=False)
            return body

    demand: list[dict[str, Any]] = demand_json(inputs)

    @app.get("/demand")
    def get_demand() -> list[dict[str, Any]]:
        """Every hex with its demand (orders a day at the default capture share) and households."""
        return demand

    network: dict[str, list[str]] = network_json(inputs)

    @app.get("/network")
    def get_network() -> dict[str, list[str]]:
        """The existing stores of the two brands, by site, at the default scenario."""
        return network

    @app.get("/assumptions")
    def get_assumptions() -> dict[str, Any]:
        """The assumptions table, the spot-check error of the travel times and the synthetic network's seed; read-only."""
        return assumed

    app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the plan service and the web map.")
    parser.add_argument("--res", type=int, default=9)
    parser.add_argument("--x-pct", type=float, default=30)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run(create_app(load_inputs(args.res, args.x_pct)), host=args.host, port=args.port)
