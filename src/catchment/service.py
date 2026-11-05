"""The live service: POST /plan and the web map."""
import argparse
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from catchment.planning import Inputs, Scenario, load_inputs, plan
from catchment.serialize import plan_json

WEB: Path = Path(__file__).resolve().parents[2] / "web"


def create_app(inputs: Inputs, web_dir: Path = WEB) -> FastAPI:
    """The service over inputs the caller loaded once."""
    app = FastAPI()

    @app.post("/plan")
    def post_plan(levers: dict[str, Any]) -> dict[str, Any]:
        """Plan the scenario the six levers describe; an omitted lever takes its default. The seed is not a lever."""
        return plan_json(plan(inputs, Scenario(**levers), method="cpsat-from-greedy"))

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
