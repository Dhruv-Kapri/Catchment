"""The live service: POST /plan and the web map."""
import argparse
import dataclasses
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from catchment.planning import LEVER_RANGES, LEVER_STEPS, Inputs, Scenario, load_inputs, plan
from catchment.serialize import plan_json

CACHE_SIZE: int = 64   # plans remembered per service
WEB: Path = Path(__file__).resolve().parents[2] / "web"


def create_app(inputs: Inputs, web_dir: Path = WEB) -> FastAPI:
    """The service over inputs the caller loaded once."""
    app = FastAPI()
    lock = threading.Lock()                                   # one plan at a time; sync endpoints run in a threadpool
    cache: OrderedDict[Scenario, dict[str, Any]] = OrderedDict()   # the most recent CACHE_SIZE plans, by scenario
    defaults: dict[str, Any] = {f.name: f.default for f in dataclasses.fields(Scenario)}

    @app.get("/levers")
    def get_levers() -> dict[str, dict[str, float]]:
        """Each lever's range, step and default."""
        return {lever: {"min": low, "max": high, "step": LEVER_STEPS[lever], "default": defaults[lever]} for lever, (low, high) in LEVER_RANGES.items()}

    @app.post("/plan")
    def post_plan(levers: dict[str, Any]) -> dict[str, Any]:
        """Plan the scenario the six levers describe; an omitted lever takes its default. The seed is not a lever."""
        for key in levers:
            if key not in LEVER_RANGES:
                raise HTTPException(status_code=422, detail=f"{key} is not a lever")
        try:
            scenario = Scenario(**levers)
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        with lock:   # a repeat waits for the plan in progress, then finds it cached
            if scenario in cache:
                cache.move_to_end(scenario)
                return cache[scenario]
            body = plan_json(plan(inputs, scenario, method="cpsat-from-greedy"))
            cache[scenario] = body
            if len(cache) > CACHE_SIZE:
                cache.popitem(last=False)
            return body

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
