"""The static demo bundle (ADR 0003): plans solved ahead of time, the read-only data, the ODbL notice and the provenance."""
import json
import os
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from catchment.planning import LEVER_RANGES, WHOLE_LEVERS, Scenario

SWEEP_STEPS: dict[str, float] = {"n_new": 1, "promise": 1, "multiplier": 0.1, "capacity": 0.25, "capture": 0.25, "competitor_density": 0.25}
# TODO(integrator): #47 adds planning.LEVER_STEPS; replace SWEEP_STEPS with it.


def sweep() -> list[Scenario]:
    """The default scenario, then each lever at every step of its range with the others at the default."""
    default = Scenario()
    scenarios: list[Scenario] = [default]
    for lever, (low, high) in LEVER_RANGES.items():
        step = SWEEP_STEPS[lever]
        for k in range(round((high - low) / step) + 1):
            value = round(low + k * step, 10)
            value = int(value) if lever in WHOLE_LEVERS else value
            if value != getattr(default, lever):
                scenarios.append(Scenario(**{lever: value}))
    return scenarios


def plan_file(scenario: Scenario) -> str:
    """Where a scenario's plan lives under bundle/: default.json, or <lever>-<value>.json for the one lever moved."""
    for lever in LEVER_RANGES:
        if getattr(scenario, lever) != getattr(Scenario(), lever):
            return f"plans/{lever}-{getattr(scenario, lever):g}.json"
    return "plans/default.json"


def write_json(path: Path, body: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body))


def build_bundle(app: FastAPI, out: Path, provenance: dict[str, Any]) -> dict[str, Any]:
    """Write the site under out: plans for sweep() and an index of them. Returns the solve record."""
    client = TestClient(app)
    bundle: Path = out / "bundle"
    index: list[dict[str, Any]] = []
    load_before: tuple[float, float, float] = os.getloadavg()
    started = time.perf_counter()
    for scenario in sweep():
        levers: dict[str, float] = {lever: getattr(scenario, lever) for lever in LEVER_RANGES}
        response = client.post("/plan", json=levers)
        response.raise_for_status()
        file = plan_file(scenario)
        write_json(bundle / file, response.json())
        index.append({"levers": levers, "plan": file})
    write_json(bundle / "index.json", index)
    return {"scenarios": len(index), "seconds": time.perf_counter() - started, "load_before": load_before, "load_after": os.getloadavg()}
