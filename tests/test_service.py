from typing import Any

import pytest
from fastapi.testclient import TestClient

from catchment import assumptions
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


def test_assumptions_serves_the_table_the_spot_check_error_and_the_network_seed(client: TestClient, inputs: Inputs) -> None:
    response = client.get("/assumptions")
    assert response.status_code == 200
    body = response.json()
    assert body["table"] == assumptions.table().to_dict("records")
    spot = body["spot_check"]
    assert spot["routes"] == 20 and spot["multiplier"] == assumptions.MULTIPLIER
    assert spot["implied_median"] == pytest.approx(1.79, abs=0.01) and spot["ratio_median"] == pytest.approx(1.0, abs=0.01)
    assert spot["ratio_q25"] < spot["ratio_median"] < spot["ratio_q75"]
    network = body["network"]
    assert network["seed"] == 2026 and network["synthetic"] is True
    assert sum(network["stores"].values()) == assumptions.network_size(inputs.demand.sum())
