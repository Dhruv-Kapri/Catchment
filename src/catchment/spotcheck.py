"""Spot check: draw routes to look up in a map app and compare with the model's times."""
import numpy as np
import pandas as pd

from catchment import assumptions

SEED = 16
COLUMNS = ["route", "candidate", "hex", "source", "destination", "free_flow_min", "model_min",
           "bad_snap_before", "app_min", "app", "looked_up"]


def draw_routes(table, candidates, hexes, bad, n=20, n_bad=5, edges=(2, 5, 8, 11, 14, 17), seed=SEED):
    rng = np.random.default_rng(seed)
    table = table.sort_values(["candidate", "hex"], kind="stable")
    pairs = table[(table.minutes >= edges[0]) & (table.minutes <= edges[-1])]
    is_bad = pd.MultiIndex.from_frame(pairs[["candidate", "hex"]]).isin(pd.MultiIndex.from_frame(bad[["candidate", "hex"]]))
    bad_pairs, other = pairs[is_bad], pairs[~is_bad]
    drawn_bad = bad_pairs.iloc[rng.choice(len(bad_pairs), min(n_bad, len(bad_pairs)), replace=False)]
    m, bins = n - len(drawn_bad), np.digitize(other.minutes, edges[1:-1])
    share = [m // (len(edges) - 1) + (b < m % (len(edges) - 1)) for b in range(len(edges) - 1)]
    pick = [rng.choice(np.flatnonzero(bins == b), k, replace=False) for b, k in enumerate(share)]
    r = pd.concat([drawn_bad.assign(bad_snap_before=True), other.iloc[np.concatenate(pick)].assign(bad_snap_before=False)])
    r = r.sort_values("minutes").reset_index(drop=True)
    r["route"] = np.arange(1, len(r) + 1)
    r["free_flow_min"] = r.minutes.round(2)
    r["model_min"] = (r.minutes * assumptions.MULTIPLIER).round(2)
    c, h = candidates.loc[r.candidate], hexes.loc[r.hex]
    r["source"] = [f"{a:.6f},{b:.6f}" for a, b in zip(c.snap_lat, c.snap_lon)]
    r["destination"] = [f"{a:.6f},{b:.6f}" for a, b in zip(h.lat, h.lon)]
    for c in ["app_min", "app", "looked_up"]:
        r[c] = None
    return r[COLUMNS]


def write_sheet(routes, path):
    routes.to_csv(path, index=False)
    return True
