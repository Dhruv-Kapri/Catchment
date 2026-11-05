"""The one place a Plan becomes JSON."""
import dataclasses
from typing import Any

from catchment.planning import Plan


def plan_json(plan: Plan) -> dict[str, Any]:
    """The plan's fields, with the scenario and new stores nested. Site and hex ids stay H3 strings."""
    return dataclasses.asdict(plan)
