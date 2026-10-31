"""Spot check: draw routes to look up in a map app and compare with the model's times."""
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from catchment import assumptions

SEED: int = 16
COLUMNS: list[str] = ["route", "candidate", "hex", "source", "destination", "free_flow_min", "model_min",
           "bad_snap_before", "app_min", "app", "looked_up"]


def draw_routes(table: pd.DataFrame, candidates: pd.DataFrame, hexes: pd.DataFrame, bad: pd.DataFrame, n: int = 20,
                n_bad: int = 5, edges: Sequence[float] = (2, 5, 8, 11, 14, 17), seed: int = SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    table = table.sort_values(["candidate", "hex"], kind="stable")
    pairs = table[(table.minutes >= edges[0]) & (table.minutes <= edges[-1])]
    is_bad = pd.MultiIndex.from_frame(pairs[["candidate", "hex"]]).isin(pd.MultiIndex.from_frame(bad[["candidate", "hex"]]))
    bad_pairs, other = pairs[is_bad], pairs[~is_bad]
    drawn_bad = bad_pairs.iloc[rng.choice(len(bad_pairs), min(n_bad, len(bad_pairs)), replace=False)]
    n_other, bins = n - len(drawn_bad), np.digitize(other.minutes, edges[1:-1])
    share = [n_other // (len(edges) - 1) + (b < n_other % (len(edges) - 1)) for b in range(len(edges) - 1)]
    pick = [rng.choice(np.flatnonzero(bins == b), k, replace=False) for b, k in enumerate(share)]
    r = pd.concat([drawn_bad.assign(bad_snap_before=True), other.iloc[np.concatenate(pick)].assign(bad_snap_before=False)])
    r = r.astype({"minutes": float}).sort_values("minutes", kind="stable").reset_index(drop=True)   # float32 from OSRM would not survive the CSV
    r["route"] = np.arange(1, len(r) + 1)
    r["free_flow_min"] = r.minutes.round(2)
    r["model_min"] = (r.minutes * assumptions.MULTIPLIER).round(2)
    c, h = candidates.loc[r.candidate], hexes.loc[r.hex]
    r["source"] = [f"{a:.6f},{b:.6f}" for a, b in zip(c.snap_lat, c.snap_lon)]
    r["destination"] = [f"{a:.6f},{b:.6f}" for a, b in zip(h.lat, h.lon)]
    for col in ["app_min", "app", "looked_up"]:
        r[col] = None
    return r[COLUMNS]


def write_sheet(routes: pd.DataFrame, path: Path | str) -> bool:
    """Write the sheet unless one exists (it may hold the app times); an existing one must be the same routes."""
    path = Path(path)
    if not path.exists():
        routes.to_csv(path, index=False)
        return True
    keys = ["route", "candidate", "hex", "free_flow_min"]
    old = pd.read_csv(path, dtype={"candidate": str, "hex": str})[keys]
    if not old.equals(routes[keys].reset_index(drop=True)):
        raise ValueError(f"{path} holds different routes; move it aside to draw a new sheet")
    return False


def compare(sheet: pd.DataFrame, multiplier: float = assumptions.MULTIPLIER) -> tuple[pd.DataFrame, dict[str, Any]]:
    """The model's error against the app per route (worst first), and the multiplier the app times imply."""
    found = sheet[sheet.app_min.notna()].copy()
    modelled = found.free_flow_min * multiplier
    found["ratio"], found["implied"], found["diff_min"] = found.app_min / modelled, found.app_min / found.free_flow_min, found.app_min - modelled
    routes = found.sort_values("ratio", ascending=False, kind="stable").reset_index(drop=True)
    bad = routes.bad_snap_before.astype(bool)
    r25, r75 = routes.ratio.quantile([0.25, 0.75])
    i25, i75 = routes.implied.quantile([0.25, 0.75])
    summary = {"n": len(routes), "n_no_app": len(sheet) - len(routes), "ratio_median": routes.ratio.median(),
               "ratio_q25": r25, "ratio_q75": r75, "ratio_min": routes.ratio.min(), "ratio_max": routes.ratio.max(),
               "implied_median": routes.implied.median(), "implied_q25": i25, "implied_q75": i75,
               "ratio_median_bad": routes.ratio[bad].median(), "ratio_median_other": routes.ratio[~bad].median(),
               "bad_snap_ranks": {int(r): int(i) + 1 for r, i in zip(routes.route[bad], routes.index[bad])}}
    return routes, summary
