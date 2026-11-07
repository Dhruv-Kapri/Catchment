"""Time POST /plan over HTTP on the 04-plan grid, the 64 lever corners and N random scenarios: uv run python scripts/time-service.py [--url U] [--out CSV] [--limit N] [--random N --seed S]."""
import argparse
import csv
import itertools
import os
import random
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import httpx

from catchment.planning import LEVER_RANGES, LEVER_STEPS, WHOLE_LEVERS

BAR_S: float = 10.0
LEVERS: list[str] = list(LEVER_RANGES)
DEFAULTS: dict[str, float] = {}   # empty: the service fills in each lever's default
SWEEPS: dict[str, list[float]] = {   # copied from notebooks/04-plan.ipynb, cell 4
    "n_new": [1, 5, 15, 20],
    "promise": [8, 12, 14, 16],
    "multiplier": [1.0, 1.4, 2.2, 2.5],
    "capacity": [0.5, 0.75, 1.5, 2.0],
    "capture": [0.5, 0.75, 1.25, 1.5],
    "competitor_density": [0.0, 0.5, 1.5, 2.0],
}
FIELDS: list[str] = [*LEVERS, "http_status", "status", "gap", "bound_source", "plan_seconds", "request_seconds", "load_before"]


def random_scenario(rng: random.Random) -> dict[str, float]:
    """Every lever at a uniformly drawn step of its range."""
    scenario: dict[str, float] = {}
    for lever, (low, high) in LEVER_RANGES.items():
        value: float = round(low + rng.randint(0, round((high - low) / LEVER_STEPS[lever])) * LEVER_STEPS[lever], 10)
        scenario[lever] = int(value) if lever in WHOLE_LEVERS else value
    return scenario


def scenarios(n_random: int = 0, seed: int = 0) -> list[dict[str, float]]:
    """The 04-plan grid (no seed rows), the 64 corners, then n_random random scenarios, without repeats (a repeat would hit the service's cache)."""
    found: list[dict[str, float]] = [DEFAULTS]
    for lever, points in SWEEPS.items():
        found += [{lever: value} for value in points]
    found += [{"n_new": 20, "capacity": 0.5}, {"capture": 1.5, "competitor_density": 0.0}]
    for ends in itertools.product(*(LEVER_RANGES[lever] for lever in LEVERS)):
        found.append({lever: int(v) if lever in WHOLE_LEVERS else float(v) for lever, v in zip(LEVERS, ends)})
    rng = random.Random(seed)
    found += [random_scenario(rng) for _ in range(n_random)]
    unique: dict[frozenset[tuple[str, float]], dict[str, float]] = {}
    for scenario in found:
        unique.setdefault(frozenset(scenario.items()), scenario)
    return list(unique.values())


def time_one(client: httpx.Client, scenario: dict[str, float]) -> dict[str, Any]:
    """POST one scenario; the row has the load before, the wall-clock seconds and the plan's own status, gap, bound_source and seconds."""
    row: dict[str, Any] = {lever: scenario.get(lever, "") for lever in LEVERS}
    row["load_before"] = round(os.getloadavg()[0], 2)
    start = time.perf_counter()
    try:
        response = client.post("/plan", json=scenario)
        row["request_seconds"] = round(time.perf_counter() - start, 3)
        row["http_status"] = response.status_code
        if response.status_code == 200:
            body = response.json()
            row.update(status=body.get("status"), gap=body.get("gap"), bound_source=body.get("bound_source"), plan_seconds=body.get("seconds"))
    except httpx.HTTPError as error:
        row["request_seconds"] = round(time.perf_counter() - start, 3)
        row["http_status"] = f"{type(error).__name__}"
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--out", type=Path, default=Path("outputs/service-timing.csv"))
    parser.add_argument("--limit", type=int, default=None, help="time only the first N scenarios")
    parser.add_argument("--random", type=int, default=0, help="also time N random scenarios, each lever at a random step")
    parser.add_argument("--seed", type=int, default=0, help="the random scenarios' seed")
    args = parser.parse_args()
    todo = scenarios(args.random, args.seed)[: args.limit]
    rows: list[dict[str, Any]] = []
    with httpx.Client(base_url=args.url, timeout=120.0) as client:
        for i, scenario in enumerate(todo, 1):
            row = time_one(client, scenario)
            rows.append(row)
            print(f"{i:3d}/{len(todo)} {row['http_status']} {row.get('status')} {row['request_seconds']:7.2f} s gap {row.get('gap')} load {row['load_before']} {scenario}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    ok = [r for r in rows if r["http_status"] == 200]
    fast = [r for r in ok if float(r["request_seconds"]) <= BAR_S]
    slowest = max(rows, key=lambda r: float(r["request_seconds"]))
    loads: list[float] = [float(r["load_before"]) for r in rows]
    print(f"{len(rows)} plans, {len(ok)} answered 200, {len(fast)} within {BAR_S:g} s")
    print(f"slowest {slowest['request_seconds']} s at {({k: slowest[k] for k in LEVERS})}, load {slowest['load_before']}")
    print(f"load before: median {statistics.median(loads):.1f}, max {max(loads):.1f}; written to {args.out}")
    return 0 if len(fast) == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
