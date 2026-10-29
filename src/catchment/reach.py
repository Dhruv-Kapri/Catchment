"""Reach: candidate sites and the travel-time table for the area, from a router."""
import math
from fractions import Fraction

import h3
import numpy as np
import pandas as pd
import shapely


def n_top(x_pct, n_hexes, n_with_places):
    """Candidate site count: the top X% of the area's hexes (rounded up, exactly), only those with a place."""
    return min(math.ceil(Fraction(str(x_pct)) * n_hexes / 100), n_with_places)


def build_reach(polygon, demand, places, res, x_pct, router):
    hexes = demand[shapely.contains_xy(polygon, demand.lon, demand.lat)]
    cells = pd.Series([h3.latlng_to_cell(y, x, res) for x, y in zip(places.lon, places.lat)])
    hexes = hexes.assign(places=cells.value_counts().reindex(hexes.index).fillna(0).astype(int))
    order = hexes.sort_values(["places", "demand"], ascending=False, kind="stable").index
    hexes["rank"] = pd.Series(np.arange(len(hexes)), index=order)
    k = n_top(x_pct, len(hexes), int((hexes.places > 0).sum()))
    candidates = hexes[hexes["rank"] < k].sort_values("rank")[["lat", "lon", "places", "rank"]]
    return candidates, pd.DataFrame()
