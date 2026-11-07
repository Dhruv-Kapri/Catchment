import dataclasses

import pytest

from catchment.planning import Plan, plan
from catchment.serialize import plan_json
from service_inputs import service_inputs


@pytest.fixture(scope="module")
def greedy_plan() -> Plan:
    return plan(service_inputs())


def test_a_greedy_plan_has_a_gap_reason_naming_why_it_has_no_gap(greedy_plan: Plan) -> None:
    body = plan_json(greedy_plan)
    assert body["gap"] is None
    assert body["gap_reason"] == "greedy states no bound"


@pytest.mark.parametrize("changes, reason", [
    ({"method": "cpsat", "status": "UNKNOWN", "objective": None, "bound": None, "gap": None},
     "no plan: CP-SAT found none, or the model was over the size cap"),
    ({"method": "cpsat", "status": "OPTIMAL", "objective": 0.0, "bound": 5.0, "gap": None},
     "the plan covers no orders, so the gap has no finite ratio"),
])
def test_a_cpsat_plan_without_a_gap_says_why(greedy_plan: Plan, changes: dict[str, object], reason: str) -> None:
    assert plan_json(dataclasses.replace(greedy_plan, **changes))["gap_reason"] == reason


def test_a_plan_with_a_gap_has_no_gap_reason(greedy_plan: Plan) -> None:
    body = plan_json(dataclasses.replace(greedy_plan, method="cpsat", status="FEASIBLE", objective=90.0, bound=100.0, gap=0.11))
    assert body["gap_reason"] is None


@pytest.mark.parametrize("changes, note", [
    ({}, "This is the greedy plan."),
    ({"method": "cpsat", "status": "UNKNOWN"},
     "No plan: CP-SAT found none, or the model was over the size cap. The metrics are the existing network's."),
    ({"method": "cpsat", "status": "HEURISTIC"},
     "Greedy's plan kept: CP-SAT found nothing better in time, or the model was over the size cap, so the gain over greedy is 0."),
    ({"method": "cpsat", "status": "OPTIMAL"}, ""),
])
def test_the_plan_note_is_the_servers_to_say(greedy_plan: Plan, changes: dict[str, object], note: str) -> None:
    assert plan_json(dataclasses.replace(greedy_plan, **changes))["plan_note"] == note
