"""Spot check: draw routes to look up in a map app and compare with the model's times."""
import numpy as np
import pandas as pd

from catchment import assumptions

SEED = 16
COLUMNS = ["route", "candidate", "hex", "source", "destination", "free_flow_min", "model_min",
           "bad_snap_before", "app_min", "app", "looked_up"]


def draw_routes(table, candidates, hexes, bad, n=20, n_bad=5, edges=(2, 5, 8, 11, 14, 17), seed=SEED):
    return pd.DataFrame(columns=COLUMNS)


def write_sheet(routes, path):
    return False
