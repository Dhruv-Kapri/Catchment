import h3
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

from catchment.reach import _nearest_roads, build_reach
from conftest import FAR, RES, FakeRouter, four_snaps

AREA = box(77.04, 28.44, 77.06, 28.46)
CENTRE = h3.latlng_to_cell(28.45, 77.05, RES)
H = sorted(h3.grid_disk(CENTRE, 1))   # seven hexes in the area: H[0] .. H[6]


SLOW = 9.0


def far_side_router(times):
    return FakeRouter(times, default=SLOW, step=FAR)


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


def test_a_pair_keeps_the_fast_time_from_the_sites_far_side_snap():
    demand = demand_of([10, 20, 7, 9, 100, 5, 5])
    router = far_side_router({(H[0], False, H[2], False): SLOW, (H[0], True, H[2], False): 2.0})
    _, table = build_reach(AREA, demand, places_in({H[0]: 1}), RES, 30, router)
    assert pairs(table)[(H[0], H[2])] == 2.0


def test_a_pair_keeps_the_fast_time_to_the_hexs_far_side_snap():
    demand = demand_of([10, 20, 7, 9, 100, 5, 5])
    router = far_side_router({(H[0], False, H[2], False): SLOW, (H[0], False, H[2], True): 2.0})
    _, table = build_reach(AREA, demand, places_in({H[0]: 1}), RES, 30, router)
    assert pairs(table)[(H[0], H[2])] == 2.0


def test_one_finite_time_among_four_unroutable_ones_is_kept_and_four_unroutable_are_absent():
    demand = demand_of([10, 20, 7, 9, 100, 5, 5])
    nan = np.nan
    times = four_snaps(H[0], H[2], nan) | {(H[0], True, H[2], True): 4.0} | four_snaps(H[0], H[3], nan)
    _, table = build_reach(AREA, demand, places_in({H[0]: 1}), RES, 30, far_side_router(times))
    got = pairs(table)
    assert got.get((H[0], H[2])) == 4.0
    assert (H[0], H[3]) not in got


def test_the_cap_applies_to_the_fastest_of_four():
    demand = demand_of([10, 20, 7, 9, 100, 5, 5])
    times = four_snaps(H[0], H[2], lambda sf, df: 20.0 + 2 * sf + df) | {(H[0], True, H[2], True): 15.0}   # best of four under the cap, the nearest snaps over it
    times |= four_snaps(H[0], H[3], lambda sf, df: 18.0 + 2 * sf + df)   # all four over
    _, table = build_reach(AREA, demand, places_in({H[0]: 1}), RES, 30, far_side_router(times))
    got = pairs(table)
    assert got.get((H[0], H[2])) == 15.0
    assert (H[0], H[3]) not in got


def test_one_snap_uses_only_the_nearest_roads():
    demand = demand_of([10, 20, 7, 9, 100, 5, 5])
    router = far_side_router({(H[0], False, H[2], False): 12.0, (H[0], True, H[2], True): 2.0})
    _, table = build_reach(AREA, demand, places_in({H[0]: 1}), RES, 30, router, snaps=1)
    assert pairs(table)[(H[0], H[2])] == 12.0


def test_unroutable_pairs_are_absent():
    demand = demand_of([10, 20, 7, 9, 100, 5, 5])
    places = places_in({H[0]: 2, H[1]: 3})
    times = {(H[1], H[2]): np.nan, (H[0], H[4]): np.nan}
    _, table = build_reach(AREA, demand, places, RES, 30, FakeRouter(times))
    got = pairs(table)
    assert (H[1], H[2]) not in got and (H[0], H[4]) not in got
    assert len(got) == 12
    assert not table.minutes.isna().any()


def test_table_covers_only_hexes_inside_the_area():
    demand = demand_of([10, 20, 7, 9, 100, 5, 5], extra=[OUTSIDE])
    _, table = build_reach(AREA, demand, places_in({H[0]: 1}), RES, 100, FakeRouter())
    assert set(table.hex) == set(H) and set(table.candidate) == {H[0]}


def test_candidates_carry_the_snapped_point_and_its_distance():
    demand = demand_of([10, 20, 7, 9, 100, 5, 5])
    candidates, _ = build_reach(AREA, demand, places_in({H[0]: 1}), RES, 30, FakeRouter(east=FAR, snap_m=12.5))
    site = candidates.loc[H[0]]
    lat, lon = h3.cell_to_latlng(H[0])
    assert (site.lat, site.lon) == (lat, lon)
    assert site.snap_lon == lon + 0.00005 and site.snap_lat == lat and site.snap_m == 12.5


def test_the_table_is_timed_from_every_snap_of_the_sites():
    router = FakeRouter(east=FAR, snap_m=12.5)
    candidates, _ = build_reach(AREA, demand_of([10, 20, 7, 9, 100, 5, 5]), places_in({H[0]: 1}), RES, 30, router)
    lat, lon = h3.cell_to_latlng(H[0])
    assert router.sources == ([lon + 0.00005] * 2, [lat] * 2)   # every snap of the site, nearest first


def test_frames_carry_res_x_pct_and_float32_minutes():
    candidates, table = build_reach(AREA, demand_of([10, 20, 7, 9, 100, 5, 5]), places_in({H[0]: 1}), RES, 2.5, FakeRouter())
    assert candidates.attrs == {"res": 9, "x_pct": 2.5} and table.attrs == {"res": 9, "x_pct": 2.5}
    assert table.minutes.dtype == np.float32
    assert list(table.columns) == ["candidate", "hex", "minutes"]


def test_a_demand_table_of_another_resolution_is_refused():
    with pytest.raises(ValueError, match="res 9"):
        build_reach(AREA, demand_of([10, 20, 7, 9, 100, 5, 5]), places_in({H[0]: 1}), 8, 30, FakeRouter())


def test_the_second_road_is_the_nearest_across_whatever_its_name():
    # Decision log 2026-10-29: the same-named variant was measured and rejected (#20)
    x, y = 77.05, 28.45
    at = lambda m: [x, y + m / 110_574]
    first = {"location": [x, y], "distance": 0.0, "name": "Mehrauli-Gurgaon Road", "nodes": [1, 2]}
    unnamed = {"location": at(8), "distance": 8.0, "name": "", "nodes": [3, 4]}
    same = {"location": at(9), "distance": 9.0, "name": "Mehrauli-Gurgaon Road", "nodes": [5, 6]}
    assert _nearest_roads([first, unnamed, same], x, y, 2) == [first, unnamed]
