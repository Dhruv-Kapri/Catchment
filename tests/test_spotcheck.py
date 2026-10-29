import numpy as np
import pandas as pd
import pytest

from catchment import assumptions
from catchment.spotcheck import SEED, draw_routes, write_sheet

EDGES = (2, 5, 8, 11, 14, 17)
CANDS = [f"c{i}" for i in range(4)]
HEXES = [f"h{i}" for i in range(60)]


def make(minutes=None):
    """Four candidates x sixty hexes; minutes sweep 0.5..29.5, so every bin and the out-of-range tails are populated."""
    rows = [(c, h, 0.5 + (i * 7 + j * 3) % 30) for i, c in enumerate(CANDS) for j, h in enumerate(HEXES)]
    table = pd.DataFrame(rows, columns=["candidate", "hex", "minutes"])
    cands = pd.DataFrame({"snap_lat": [28.4 + i / 100 for i in range(4)], "snap_lon": [77.0 + i / 100 for i in range(4)]}, index=CANDS)
    hexes = pd.DataFrame({"lat": [28.5 + i / 1000 for i in range(60)], "lon": [77.1 + i / 1000 for i in range(60)]}, index=HEXES)
    return table, cands, hexes


def no_bad():
    return pd.DataFrame({"candidate": [], "hex": []})


def test_n_routes_and_columns():
    table, cands, hexes = make()
    r = draw_routes(table, cands, hexes, no_bad())
    assert len(r) == 20
    assert list(r.columns) == ["route", "candidate", "hex", "source", "destination", "free_flow_min", "model_min",
                               "bad_snap_before", "app_min", "app", "looked_up"]


def test_minutes_in_range_and_each_bin_gets_its_share():
    table, cands, hexes = make()
    r = draw_routes(table, cands, hexes, no_bad())
    assert r.free_flow_min.between(2, 17).all()
    counts = np.histogram(r.free_flow_min, bins=EDGES)[0]
    assert list(counts) == [4, 4, 4, 4, 4]


def test_remainder_goes_to_first_bins():
    table, cands, hexes = make()
    r = draw_routes(table, cands, hexes, no_bad(), n=17, n_bad=0)
    assert list(np.histogram(r.free_flow_min, bins=EDGES)[0]) == [4, 4, 3, 3, 3]
