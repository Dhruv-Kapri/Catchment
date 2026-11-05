"""The one place a Plan becomes JSON."""
import dataclasses
from typing import Any

from catchment.planning import Inputs, Plan, Scenario, place_network


def plan_json(plan: Plan) -> dict[str, Any]:
    """The plan's fields, with the scenario and new stores nested. Site and hex ids stay H3 strings."""
    return dataclasses.asdict(plan)


def demand_json(inputs: Inputs) -> list[dict[str, Any]]:
    """One record per hex: its H3 id, its demand (orders a day at the default capture share, as stored) and its households."""
    return [{"hex": str(h), "demand": float(d), "households": float(hh)} for h, d, hh in zip(inputs.hex_ids, inputs.demand, inputs.households)]


def network_json(inputs: Inputs) -> dict[str, list[str]]:
    """The existing network at the default scenario, brand -> H3 ids of its sites: what `plan(inputs, Scenario()).network` reports."""
    default = Scenario()
    placed = place_network(inputs, default.seed, default.competitor_density)
    return {brand: [str(inputs.site_ids[s]) for s in sites] for brand, sites in placed.items()}
