"""The one place a Plan becomes JSON."""
import dataclasses
from typing import Any

from catchment.planning import Plan


def gap_reason(plan: Plan) -> str | None:
    """Why the plan has no gap, as a short sentence; None when it has one."""
    if plan.gap is not None:
        return None
    if plan.method == "greedy":
        return "greedy states no bound"
    if plan.status == "UNKNOWN":
        return "no plan: CP-SAT found none, or the model was over the size cap"
    return "the plan covers no orders, so the gap has no finite ratio"


def plan_json(plan: Plan) -> dict[str, Any]:
    """The plan's fields, with the scenario and new stores nested. Site and hex ids stay H3 strings."""
    return {**dataclasses.asdict(plan), "gap_reason": gap_reason(plan)}
