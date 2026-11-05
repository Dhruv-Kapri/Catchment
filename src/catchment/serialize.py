"""The one place a Plan becomes JSON."""
import dataclasses
from typing import Any

import pandas as pd

from catchment import assumptions
from catchment.planning import Inputs, Plan, Scenario, place_network
from catchment.spotcheck import SPOT_CHECK_SHEET, compare


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


def demand_json(inputs: Inputs) -> list[dict[str, Any]]:
    """One record per hex: its H3 id, its demand (orders a day at the default capture share, as stored) and its households."""
    return [{"hex": str(h), "demand": float(d), "households": float(hh)} for h, d, hh in zip(inputs.hex_ids, inputs.demand, inputs.households)]


def network_json(inputs: Inputs) -> dict[str, list[str]]:
    """The existing network at the default scenario, brand -> H3 ids of its sites: what `plan(inputs, Scenario()).network` reports."""
    default = Scenario()
    placed = place_network(inputs, default.seed, default.competitor_density)
    return {brand: [str(inputs.site_ids[s]) for s in sites] for brand, sites in placed.items()}


def assumptions_json(inputs: Inputs) -> dict[str, Any]:
    """The read-only assumptions payload: the table, the spot-check error of the travel times, and the synthetic network's seed and store counts."""
    sheet = pd.read_csv(SPOT_CHECK_SHEET)
    _, summary = compare(sheet, assumptions.MULTIPLIER)
    spot_check: dict[str, Any] = {"routes": int(summary["n"]), "multiplier": assumptions.MULTIPLIER,
                                  **{k: float(summary[k]) for k in ("ratio_median", "ratio_q25", "ratio_q75", "implied_median", "implied_q25", "implied_q75")},
                                  "app": str(sheet.app.dropna().iloc[0]), "looked_up_from": str(sheet.looked_up.min()), "looked_up_to": str(sheet.looked_up.max())}
    stores = assumptions.brand_split(assumptions.network_size(float(inputs.demand.sum())))
    return {"table": assumptions.table().to_dict("records"), "spot_check": spot_check,
            "network": {"seed": assumptions.SEED, "synthetic": True, "stores": stores}}
