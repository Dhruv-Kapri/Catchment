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


def bad_pairs(table, k_in, k_out):
    """k_in pairs inside 2-17 minutes and k_out outside it."""
    inside = table[table.minutes.between(2, 17)].iloc[::7].head(k_in)
    outside = table[~table.minutes.between(2, 17)].iloc[::5].head(k_out)
    return pd.concat([inside, outside])[["candidate", "hex"]].reset_index(drop=True)


def test_bad_pairs_drawn_and_flagged_only_when_in_range():
    table, cands, hexes = make()
    bad = bad_pairs(table, 8, 3)
    r = draw_routes(table, cands, hexes, bad)
    flagged = r[r.bad_snap_before.eq(True)]
    assert len(r) == 20 and len(flagged) == 5
    inside = set(zip(*bad.head(8).T.values))
    assert set(zip(flagged.candidate, flagged.hex)) <= inside
    assert not set(zip(r.candidate, r.hex)) & set(zip(*bad.tail(3).T.values))
    assert not r[~r.bad_snap_before.eq(True)].apply(lambda x: (x.candidate, x.hex) in inside, axis=1).any()


def test_fewer_bad_pairs_than_n_bad_takes_all_and_still_n_routes():
    table, cands, hexes = make()
    bad = bad_pairs(table, 2, 3)
    r = draw_routes(table, cands, hexes, bad)
    assert len(r) == 20
    assert r.bad_snap_before.sum() == 2
    assert set(zip(r[r.bad_snap_before].candidate, r[r.bad_snap_before].hex)) == set(zip(*bad.head(2).T.values))


def test_shuffled_input_same_result():
    table, cands, hexes = make()
    bad = bad_pairs(table, 8, 3)
    a = draw_routes(table, cands, hexes, bad)
    b = draw_routes(table.sample(frac=1, random_state=0).reset_index(drop=True), cands, hexes, bad.iloc[::-1])
    pd.testing.assert_frame_equal(a, b)


def test_same_seed_same_result():
    table, cands, hexes = make()
    pd.testing.assert_frame_equal(draw_routes(table, cands, hexes, no_bad()), draw_routes(table, cands, hexes, no_bad(), seed=SEED))


def test_different_seed_different_result():
    table, cands, hexes = make()
    a, b = draw_routes(table, cands, hexes, no_bad()), draw_routes(table, cands, hexes, no_bad(), seed=SEED + 1)
    assert not a[["candidate", "hex"]].equals(b[["candidate", "hex"]])


def test_no_pair_drawn_twice():
    table, cands, hexes = make()
    bad = bad_pairs(table, 8, 0)
    r = draw_routes(table, cands, hexes, bad, n=60, n_bad=8)
    assert not r.duplicated(["candidate", "hex"]).any()


def test_model_min_is_free_flow_times_multiplier():
    table, cands, hexes = make()
    r = draw_routes(table, cands, hexes, no_bad())
    assert np.allclose(r.model_min, (r.free_flow_min * assumptions.MULTIPLIER).round(2), atol=0.011)
    assert (r.model_min == r.model_min.round(2)).all()
    assert (r.free_flow_min == r.free_flow_min.round(2)).all()


def test_source_and_destination_formatting():
    table, cands, hexes = make()
    r = draw_routes(table, cands, hexes, no_bad())
    c, h = cands.loc[r.candidate], hexes.loc[r.hex]
    assert list(r.source) == [f"{a:.6f},{b:.6f}" for a, b in zip(c.snap_lat, c.snap_lon)]
    assert list(r.destination) == [f"{a:.6f},{b:.6f}" for a, b in zip(h.lat, h.lon)]
    cands[["snap_lat", "snap_lon"]] = [28.4595123456, 77.0266339]
    hexes[["lat", "lon"]] = [28.5, 77.1234]
    r = draw_routes(table, cands, hexes, no_bad())
    assert set(r.source) == {"28.459512,77.026634"} and set(r.destination) == {"28.500000,77.123400"}
