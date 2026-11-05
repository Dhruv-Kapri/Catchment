from typing import Any

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


def test_demand_lists_every_hex_once_with_its_demand_and_households(client: TestClient, inputs: Inputs) -> None:
    response = client.get("/demand")
    assert response.status_code == 200
    assert response.json() == [{"hex": h, "demand": d, "households": hh} for h, d, hh in zip(inputs.hex_ids, inputs.demand, inputs.households)]


def test_network_lists_the_two_brands_existing_stores(client: TestClient, inputs: Inputs) -> None:
    response = client.get("/network")
    assert response.status_code == 200
    body = response.json()
    assert (len(body["Operator"]), len(body["Competitor"])) == (8, 4)
    assert body == plan(inputs, Scenario()).network


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
