import h3
import numpy as np
import pandas as pd
from shapely.geometry import box

from catchment.reach import build_reach

RES = 9
AREA = box(77.04, 28.44, 77.06, 28.46)
CENTRE = h3.latlng_to_cell(28.45, 77.05, RES)
H = sorted(h3.grid_disk(CENTRE, 1))   # seven hexes in the area: H[0] .. H[6]


class FakeRouter:
    """Snaps every point to itself; minutes are 1.0 unless `times` has (source hex, destination hex)."""
    def __init__(self, times=None):
        self.times = times or {}

    def snap(self, lons, lats, k=1):
        lons, lats = np.asarray(lons, float)[:, None], np.asarray(lats, float)[:, None]
        return lons, lats, np.zeros_like(lons)

    def minutes(self, src_lons, src_lats, dst_lons, dst_lats):
        cell = lambda lon, lat: h3.latlng_to_cell(lat, lon, RES)
        src = [cell(x, y) for x, y in zip(src_lons, src_lats)]
        dst = [cell(x, y) for x, y in zip(dst_lons, dst_lats)]
        return np.array([[self.times.get((s, d), 1.0) for d in dst] for s in src], dtype=np.float32)


def demand_of(values, extra=()):
    """Demand table for the hexes in H (values in order) plus `extra` hexes."""
    cells = H + list(extra)
    centres = [h3.cell_to_latlng(c) for c in cells]
    df = pd.DataFrame({"lat": [c[0] for c in centres], "lon": [c[1] for c in centres],
                       "demand": list(values) + [1.0] * len(extra)}, index=pd.Index(cells, name="hex"))
    df.attrs["res"] = RES
    return df


def places_in(counts, status=None):
    """Places at the centres of the hexes in `counts` ({hex: n})."""
    rows = [(*h3.cell_to_latlng(c)[::-1], status) for c, n in counts.items() for _ in range(n)]
    return pd.DataFrame(rows, columns=["lon", "lat", "operating_status"])


def test_top_x_pct_picks_the_busiest_hexes_and_demand_breaks_ties():
    demand = demand_of([10, 20, 7, 9, 100, 5, 5])
    places = places_in({H[0]: 5, H[1]: 5, H[2]: 3, H[3]: 3, H[4]: 1})
    candidates, _ = build_reach(AREA, demand, places, RES, 30, FakeRouter())   # ceil(30% of 7) = 3
    assert list(candidates.index) == [H[1], H[0], H[3]]
    assert list(candidates["rank"]) == [0, 1, 2]
    assert list(candidates.places) == [5, 5, 3]


def test_hexes_without_places_never_qualify():
    demand = demand_of([10, 20, 7, 9, 100, 5, 5])
    places = places_in({H[0]: 5, H[1]: 5, H[2]: 3, H[3]: 3, H[4]: 1})
    candidates, _ = build_reach(AREA, demand, places, RES, 100, FakeRouter())   # X allows all 7; 5 have places
    assert list(candidates.index) == [H[1], H[0], H[3], H[2], H[4]]


def test_x_changes_the_candidate_count():
    demand = demand_of([10, 20, 7, 9, 100, 5, 5])
    places = places_in({H[0]: 5, H[1]: 5, H[2]: 3, H[3]: 3, H[4]: 1})
    counts = [len(build_reach(AREA, demand, places, RES, x, FakeRouter())[0]) for x in (15, 30, 45)]
    assert counts == [2, 3, 4]   # ceil of 1.05, 2.1, 3.15


def test_count_is_exact_where_float_arithmetic_rounds_up():
    cells = sorted(h3.grid_disk(CENTRE, 6))[:100]   # 7% of 100 is 7; 7 / 100 * 100 is 7.000000000000001 in floats
    centres = [h3.cell_to_latlng(c) for c in cells]
    demand = pd.DataFrame({"lat": [c[0] for c in centres], "lon": [c[1] for c in centres], "demand": 1.0},
                          index=pd.Index(cells, name="hex"))
    candidates, _ = build_reach(box(77.0, 28.4, 77.1, 28.5), demand, places_in({c: 1 for c in cells}), RES, 7, FakeRouter())
    assert len(candidates) == 7


OUTSIDE = h3.latlng_to_cell(28.5, 77.2, RES)   # ~16 km from AREA


def test_a_hex_with_its_centre_outside_the_area_is_not_a_candidate():
    demand = demand_of([10, 20, 7, 9, 100, 5, 5], extra=[OUTSIDE])
    places = places_in({H[0]: 5, OUTSIDE: 50})   # the outside hex is the busiest, and the highest demand ranks it first
    candidates, _ = build_reach(AREA, demand, places, RES, 100, FakeRouter())
    assert list(candidates.index) == [H[0]]


def test_permanently_closed_places_do_not_count():
    demand = demand_of([10, 20, 7, 9, 100, 5, 5])
    places = pd.concat([places_in({H[0]: 1, H[1]: 1}), places_in({H[1]: 2, H[2]: 3}, "permanently_closed")])
    candidates, _ = build_reach(AREA, demand, places, RES, 100, FakeRouter())
    assert list(candidates.index) == [H[1], H[0]]   # tied at 1 place each; H[2] has only closed places
    assert list(candidates.places) == [1, 1]


def pairs(table):
    return {(c, h): m for c, h, m in zip(table.candidate, table.hex, table.minutes)}


def test_pairs_over_17_minutes_are_absent_and_exactly_17_is_kept():
    demand = demand_of([10, 20, 7, 9, 100, 5, 5])
    places = places_in({H[0]: 2, H[1]: 3})
    times = {(H[1], H[0]): 17.0, (H[1], H[2]): 17.5, (H[0], H[4]): 100.0}
    _, table = build_reach(AREA, demand, places, RES, 30, FakeRouter(times))   # candidates H[1], H[0]
    got = pairs(table)
    assert got.get((H[1], H[0])) == 17.0
    assert (H[1], H[2]) not in got and (H[0], H[4]) not in got
    assert len(got) == 12   # 2 candidates x 7 hexes, less the 2 over the cap


def test_unroutable_pairs_are_absent():
    demand = demand_of([10, 20, 7, 9, 100, 5, 5])
    places = places_in({H[0]: 2, H[1]: 3})
    times = {(H[1], H[2]): np.nan, (H[0], H[4]): np.nan}
    _, table = build_reach(AREA, demand, places, RES, 30, FakeRouter(times))
    got = pairs(table)
    assert (H[1], H[2]) not in got and (H[0], H[4]) not in got
    assert len(got) == 12
    assert not table.minutes.isna().any()
