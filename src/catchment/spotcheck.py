"""Spot check: draw routes to look up in a map app and compare with the model's times."""
import numpy as np
import pandas as pd

from catchment import assumptions

SEED = 16
COLUMNS = ["route", "candidate", "hex", "source", "destination", "free_flow_min", "model_min",
           "bad_snap_before", "app_min", "app", "looked_up"]


def draw_routes(table, candidates, hexes, bad, n=20, n_bad=5, edges=(2, 5, 8, 11, 14, 17), seed=SEED):
    rng = np.random.default_rng(seed)
    pairs = table[(table.minutes >= edges[0]) & (table.minutes <= edges[-1])]
    bins = np.digitize(pairs.minutes, edges[1:-1])
    share = [n // (len(edges) - 1) + (b < n % (len(edges) - 1)) for b in range(len(edges) - 1)]
    pick = [rng.choice(np.flatnonzero(bins == b), k, replace=False) for b, k in enumerate(share)]
    r = pairs.iloc[np.concatenate(pick)].sort_values("minutes").reset_index(drop=True)
    r["route"] = np.arange(1, len(r) + 1)
    r["free_flow_min"] = r.minutes.round(2)
    for c in ["source", "destination", "model_min", "bad_snap_before", "app_min", "app", "looked_up"]:
        r[c] = None
    return r[COLUMNS]


def write_sheet(routes, path):
    return False
