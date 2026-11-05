"""The one place a Plan becomes JSON."""
import dataclasses
from typing import Any

import pandas as pd

from catchment import assumptions
from catchment.planning import Inputs, Plan
from catchment.spotcheck import SPOT_CHECK_SHEET, compare


def plan_json(plan: Plan) -> dict[str, Any]:
    """The plan's fields, with the scenario and new stores nested. Site and hex ids stay H3 strings."""
    return dataclasses.asdict(plan)


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
