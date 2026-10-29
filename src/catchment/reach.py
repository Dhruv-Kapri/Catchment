"""Reach: candidate sites and the travel-time table for the area, from a router."""
import math
from fractions import Fraction

import h3
import numpy as np
import pandas as pd
import shapely

from catchment import assumptions


def n_top(x_pct, n_hexes, n_with_places):
    """Candidate site count: the top X% of the area's hexes (rounded up, exactly), only those with a place."""
    return min(math.ceil(Fraction(str(x_pct)) * n_hexes / 100), n_with_places)


def build_reach(polygon, demand, places, res, x_pct, router):
    hexes = demand[shapely.contains_xy(polygon, demand.lon, demand.lat)]
    places = places[places.operating_status != "permanently_closed"]
    cells = pd.Series([h3.latlng_to_cell(y, x, res) for x, y in zip(places.lon, places.lat)])
    hexes = hexes.assign(places=cells.value_counts().reindex(hexes.index).fillna(0).astype(int))
    order = hexes.sort_values(["places", "demand"], ascending=False, kind="stable").index
    hexes["rank"] = pd.Series(np.arange(len(hexes)), index=order)
    k = n_top(x_pct, len(hexes), int((hexes.places > 0).sum()))
    candidates = hexes[hexes["rank"] < k].sort_values("rank")[["lat", "lon", "places", "rank"]]
    snap_lon, snap_lat, snap_m = router.snap(candidates.lon.to_numpy(), candidates.lat.to_numpy(), k=1)
    candidates["snap_lon"], candidates["snap_lat"], candidates["snap_m"] = snap_lon[:, 0], snap_lat[:, 0], snap_m[:, 0]
    minutes = router.minutes(candidates.snap_lon.to_numpy(), candidates.snap_lat.to_numpy(),
                             hexes.lon.to_numpy(), hexes.lat.to_numpy())
    src, dst = np.nonzero(minutes <= assumptions.MAX_PAIR_MIN)   # NaN compares False, so unroutable pairs drop out
    table = pd.DataFrame({"candidate": candidates.index[src], "hex": hexes.index[dst], "minutes": minutes[src, dst]})
    for df in (candidates, table):
        df.attrs = {"res": res, "x_pct": x_pct}
    return candidates, table
