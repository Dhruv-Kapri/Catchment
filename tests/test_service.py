from typing import Any

import h3
import pytest
from fastapi.testclient import TestClient

from catchment.planning import Inputs, Scenario, plan
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


def test_the_plan_carries_each_operator_stores_service_area_and_catchment(client: TestClient) -> None:
    body = client.post("/plan", json={}).json()
    operator_stores: list[str] = body["network"]["Operator"] + body["sites"]
    assert list(body["service_areas"]) == list(body["catchments"]) == operator_stores
    for store in operator_stores:
        assert all(h3.is_valid_cell(cell) for cell in body["service_areas"][store] + body["catchments"][store])
        assert set(body["service_areas"][store]) <= set(body["catchments"][store])


def test_the_root_serves_the_page_with_its_plan_button(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert 'data-testid="plan-button"' in response.text


@pytest.mark.parametrize("levers, message", [
    ({"n_new": 99}, "n_new 99 is outside the lever range 1-20"),
    ({"n_new": 2.5}, "n_new 2.5 must be a whole number"),
    ({"seed": 1}, "seed is not a lever"),
    ({"colour": "red"}, "colour"),
])
def test_a_bad_scenario_is_a_422_that_states_why(client: TestClient, levers: dict[str, Any], message: str) -> None:
    response = client.post("/plan", json=levers)
    assert response.status_code == 422
    assert message in str(response.json()["detail"])
