import dataclasses
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Any

import pytest
from fastapi.testclient import TestClient

from catchment.planning import LEVER_RANGES, LEVER_STEPS, Inputs, Method, Plan, Scenario, plan
from catchment.serialize import plan_json
from catchment.service import create_app
from service_inputs import service_inputs

TIMING: tuple[str, ...] = ("seconds", "build_seconds", "solve_seconds")


@pytest.fixture(scope="module")
def inputs() -> Inputs:
    return service_inputs()


@pytest.fixture(scope="module")
def client(inputs: Inputs) -> TestClient:
    return TestClient(create_app(inputs), raise_server_exceptions=False)   # a server error is a response to assert on, as a browser sees it


def untimed(body: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in body.items() if k not in TIMING}


def test_posting_no_levers_plans_the_default_scenario(client: TestClient, inputs: Inputs) -> None:
    response = client.post("/plan", json={})
    assert response.status_code == 200
    body = response.json()
    assert {"scenario", "sites", "network", "demand_covered", "households_covered", "status", "method"} <= body.keys()
    assert body["method"] == "cpsat-from-greedy" and body["scenario"]["n_new"] == len(body["sites"]) == 10
    assert untimed(body) == untimed(plan_json(plan(inputs, Scenario(), "cpsat-from-greedy")))


def test_the_root_serves_the_page_with_its_plan_button(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert 'data-testid="plan-button"' in response.text


@pytest.mark.parametrize("levers, message", [
    ({"n_new": 99}, "n_new 99 is outside the lever range 1-20"),
    ({"multiplier": 1.45}, "multiplier 1.45 is not in steps of 0.1 (lever range 1-2.5)"),
    ({"n_new": 2.5}, "n_new 2.5 must be a whole number (lever range 1-20)"),
    ({"capacity": "1"}, "capacity '1' must be a number (lever range 0.5-2)"),
    ({"seed": 1}, "seed is not a lever"),
    ({"colour": "red"}, "colour is not a lever"),
])
def test_a_bad_scenario_is_a_422_that_names_the_lever_and_its_range(client: TestClient, levers: dict[str, Any], message: str) -> None:
    response = client.post("/plan", json=levers)
    assert response.status_code == 422
    assert response.json()["detail"] == message


def test_the_levers_endpoint_publishes_the_ranges_steps_and_defaults(client: TestClient) -> None:
    defaults = {f.name: f.default for f in dataclasses.fields(Scenario)}
    expected = {lever: {"min": low, "max": high, "step": LEVER_STEPS[lever], "default": defaults[lever]} for lever, (low, high) in LEVER_RANGES.items()}
    response = client.get("/levers")
    assert response.status_code == 200
    assert response.json() == expected and list(response.json()) == list(LEVER_RANGES)


@contextmanager
def counting_plan(monkeypatch: pytest.MonkeyPatch, delay: float = 0.0) -> Iterator[dict[str, int]]:
    """Wrap the real plan: count calls and the most that ran at once."""
    state: dict[str, int] = {"calls": 0, "running": 0, "max_running": 0}
    guard = threading.Lock()

    def wrapper(inputs: Inputs, scenario: Scenario, method: Method) -> Plan:
        with guard:
            state["calls"] += 1
            state["running"] += 1
            state["max_running"] = max(state["max_running"], state["running"])
        try:
            time.sleep(delay)
            return plan(inputs, scenario, method)
        finally:
            with guard:
                state["running"] -= 1

    monkeypatch.setattr("catchment.service.plan", wrapper)
    yield state


def test_a_repeated_scenario_is_served_from_the_cache_without_planning_again(inputs: Inputs, monkeypatch: pytest.MonkeyPatch) -> None:
    with counting_plan(monkeypatch) as state:
        fresh = TestClient(create_app(inputs))
        first, second, spelled = fresh.post("/plan", json={}), fresh.post("/plan", json={}), fresh.post("/plan", json={"capacity": 1})
    assert [r.status_code for r in (first, second, spelled)] == [200, 200, 200]
    assert state["calls"] == 1 and first.json() == second.json() == spelled.json()


def test_the_service_plans_one_scenario_at_a_time(inputs: Inputs, monkeypatch: pytest.MonkeyPatch) -> None:
    with counting_plan(monkeypatch, delay=0.2) as state:
        fresh = TestClient(create_app(inputs))
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda n: fresh.post("/plan", json={"n_new": n}), [2, 3]))
    assert [r.status_code for r in responses] == [200, 200]
    assert state["calls"] == 2 and state["max_running"] == 1
