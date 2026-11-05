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
