from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from catchment import assumptions
from catchment.spotcheck import SEED, compare, draw_routes, write_sheet

EDGES = (2, 5, 8, 11, 14, 17)
CANDS = [f"c{i}" for i in range(4)]
HEXES = [f"h{i}" for i in range(60)]


def make(minutes: None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Four candidates x sixty hexes; minutes sweep 0.5..29.5, so every bin and the out-of-range tails are populated."""
    rows = [(c, h, 0.5 + (i * 7 + j * 3) % 30) for i, c in enumerate(CANDS) for j, h in enumerate(HEXES)]
    table = pd.DataFrame(rows, columns=["candidate", "hex", "minutes"])
    cands = pd.DataFrame({"snap_lat": [28.4 + i / 100 for i in range(4)], "snap_lon": [77.0 + i / 100 for i in range(4)]}, index=CANDS)
    hexes = pd.DataFrame({"lat": [28.5 + i / 1000 for i in range(60)], "lon": [77.1 + i / 1000 for i in range(60)]}, index=HEXES)
    return table, cands, hexes


def no_bad() -> pd.DataFrame:
    return pd.DataFrame({"candidate": [], "hex": []})


def test_n_routes_and_columns() -> None:
    table, cands, hexes = make()
    r = draw_routes(table, cands, hexes, no_bad())
    assert len(r) == 20
    assert list(r.columns) == ["route", "candidate", "hex", "source", "destination", "free_flow_min", "model_min",
                               "bad_snap_before", "app_min", "app", "looked_up"]


def test_minutes_in_range_and_each_bin_gets_its_share() -> None:
    table, cands, hexes = make()
    r = draw_routes(table, cands, hexes, no_bad())
    assert r.free_flow_min.between(2, 17).all()
    counts = np.histogram(r.free_flow_min, bins=EDGES)[0]
    assert list(counts) == [4, 4, 4, 4, 4]


def test_remainder_goes_to_first_bins() -> None:
    table, cands, hexes = make()
    r = draw_routes(table, cands, hexes, no_bad(), n=17, n_bad=0)
    assert list(np.histogram(r.free_flow_min, bins=EDGES)[0]) == [4, 4, 3, 3, 3]


def bad_pairs(table: pd.DataFrame, k_in: int, k_out: int) -> pd.DataFrame:
    """k_in pairs inside 2-17 minutes and k_out outside it."""
    inside = table[table.minutes.between(2, 17)].iloc[::7].head(k_in)
    outside = table[~table.minutes.between(2, 17)].iloc[::5].head(k_out)
    return pd.concat([inside, outside])[["candidate", "hex"]].reset_index(drop=True)


def test_bad_pairs_drawn_and_flagged_only_when_in_range() -> None:
    table, cands, hexes = make()
    bad = bad_pairs(table, 8, 3)
    r = draw_routes(table, cands, hexes, bad)
    flagged = r[r.bad_snap_before.eq(True)]
    assert len(r) == 20 and len(flagged) == 5
    inside = set(zip(*bad.head(8).T.values))
    assert set(zip(flagged.candidate, flagged.hex)) <= inside
    assert not set(zip(r.candidate, r.hex)) & set(zip(*bad.tail(3).T.values))
    assert not r[~r.bad_snap_before.eq(True)].apply(lambda x: (x.candidate, x.hex) in inside, axis=1).any()


def test_fewer_bad_pairs_than_n_bad_takes_all_and_still_n_routes() -> None:
    table, cands, hexes = make()
    bad = bad_pairs(table, 2, 3)
    r = draw_routes(table, cands, hexes, bad)
    assert len(r) == 20
    assert r.bad_snap_before.sum() == 2
    assert set(zip(r[r.bad_snap_before].candidate, r[r.bad_snap_before].hex)) == set(zip(*bad.head(2).T.values))


def test_shuffled_input_same_result() -> None:
    table, cands, hexes = make()
    bad = bad_pairs(table, 8, 3)
    a = draw_routes(table, cands, hexes, bad)
    b = draw_routes(table.sample(frac=1, random_state=0).reset_index(drop=True), cands, hexes, bad.iloc[::-1])
    pd.testing.assert_frame_equal(a, b)


def test_same_seed_same_result() -> None:
    table, cands, hexes = make()
    pd.testing.assert_frame_equal(draw_routes(table, cands, hexes, no_bad()), draw_routes(table, cands, hexes, no_bad(), seed=SEED))


def test_different_seed_different_result() -> None:
    table, cands, hexes = make()
    a, b = draw_routes(table, cands, hexes, no_bad()), draw_routes(table, cands, hexes, no_bad(), seed=SEED + 1)
    assert not a[["candidate", "hex"]].equals(b[["candidate", "hex"]])


def test_no_pair_drawn_twice() -> None:
    table, cands, hexes = make()
    bad = bad_pairs(table, 8, 0)
    r = draw_routes(table, cands, hexes, bad, n=60, n_bad=8)
    assert not r.duplicated(["candidate", "hex"]).any()


def test_model_min_is_free_flow_times_multiplier() -> None:
    table, cands, hexes = make()
    r = draw_routes(table, cands, hexes, no_bad())
    assert r.model_min.notna().all()
    assert np.allclose(r.model_min, (r.free_flow_min * assumptions.MULTIPLIER).round(2), atol=0.011)
    assert (r.model_min == r.model_min.round(2)).all()
    assert (r.free_flow_min == r.free_flow_min.round(2)).all()


def test_source_and_destination_formatting() -> None:
    table, cands, hexes = make()
    r = draw_routes(table, cands, hexes, no_bad())
    c, h = cands.loc[r.candidate], hexes.loc[r.hex]
    assert list(r.source) == [f"{a:.6f},{b:.6f}" for a, b in zip(c.snap_lat, c.snap_lon)]
    assert list(r.destination) == [f"{a:.6f},{b:.6f}" for a, b in zip(h.lat, h.lon)]
    cands[["snap_lat", "snap_lon"]] = [28.4595123456, 77.0266339]
    hexes[["lat", "lon"]] = [28.5, 77.1234]
    r = draw_routes(table, cands, hexes, no_bad())
    assert set(r.source) == {"28.459512,77.026634"} and set(r.destination) == {"28.500000,77.123400"}


def test_route_ids_run_1_to_n_in_free_flow_order() -> None:
    table, cands, hexes = make()
    r = draw_routes(table, cands, hexes, no_bad())
    assert list(r.route) == list(range(1, 21))
    assert r.free_flow_min.is_monotonic_increasing


def test_app_columns_empty() -> None:
    table, cands, hexes = make()
    r = draw_routes(table, cands, hexes, no_bad())
    assert r[["app_min", "app", "looked_up"]].isna().all().all()


def sample_routes() -> pd.DataFrame:
    table, cands, hexes = make()
    return draw_routes(table, cands, hexes, no_bad(), n=5, n_bad=0)


def test_write_sheet_writes_when_absent(tmp_path: Path) -> None:
    routes, path = sample_routes(), tmp_path / "spot-check-routes.csv"
    assert write_sheet(routes, path) is True
    back = pd.read_csv(path)
    assert list(back.columns) == list(routes.columns)
    assert list(back.route) == [1, 2, 3, 4, 5]
    assert back[["app_min", "app", "looked_up"]].isna().all().all()


def test_write_sheet_keeps_a_matching_existing_file(tmp_path: Path) -> None:
    routes, path = sample_routes(), tmp_path / "spot-check-routes.csv"
    write_sheet(routes, path)
    filled = pd.read_csv(path).astype({"app_min": float, "app": object})
    filled.loc[0, ["app_min", "app"]] = [12.0, "Google Maps"]
    filled.to_csv(path, index=False)
    assert write_sheet(routes, path) is False
    back = pd.read_csv(path)
    assert back.loc[0, "app_min"] == 12.0 and back.loc[0, "app"] == "Google Maps"


def test_write_sheet_raises_when_existing_routes_differ(tmp_path: Path) -> None:
    routes, path = sample_routes(), tmp_path / "spot-check-routes.csv"
    write_sheet(routes, path)
    for column, value in [("route", 9), ("candidate", "zz"), ("hex", "zz"), ("free_flow_min", 99.0)]:
        other = routes.copy()
        other.loc[0, column] = value
        with pytest.raises(ValueError):
            write_sheet(other, path)
    with pytest.raises(ValueError):
        write_sheet(routes.iloc[:3], path)


def test_write_sheet_keeps_a_sheet_drawn_from_float32_minutes(tmp_path: Path) -> None:
    table, cands, hexes = make()
    routes = draw_routes(table.astype({"minutes": "float32"}), cands, hexes, no_bad())   # OsrmRouter's dtype
    path = tmp_path / "spot-check.csv"
    write_sheet(routes, path)
    assert write_sheet(routes, path) is False


def test_committed_sheet_has_every_lookup_on_a_weekday_7_to_8_pm() -> None:
    sheet = pd.read_csv(Path(__file__).parent.parent / "docs" / "spot-check.csv")
    assert len(sheet) == 20 and sheet.app_min.notna().all()
    assert (sheet.app_min == sheet.app_min.round()).all() and (sheet.app_min > 0).all()
    assert (sheet.app == "Google Maps two-wheeler").all()
    when = pd.to_datetime(sheet.looked_up, format="%Y-%m-%d %H:%M")
    assert (when.dt.weekday < 5).all() and (when.dt.hour == 19).all()


def app_sheet() -> pd.DataFrame:
    """Free-flow 2, 4, 5, 10 min at x1.4 = 2.8, 5.6, 7, 14; app 7, 6, none, 14."""
    return pd.DataFrame({"route": [1, 2, 3, 4], "free_flow_min": [2.0, 4.0, 5.0, 10.0], "model_min": [2.8, 5.6, 7.0, 14.0],
                         "bad_snap_before": [True, False, False, True], "app_min": [7.0, 6.0, np.nan, 14.0]})


def test_compare_ratio_implied_and_diff() -> None:
    routes, summary = compare(app_sheet(), multiplier=1.4)
    routes = routes.set_index("route")
    assert routes.loc[1, "ratio"] == pytest.approx(2.5) and routes.loc[2, "ratio"] == pytest.approx(6 / 5.6) and routes.loc[4, "ratio"] == pytest.approx(1.0)
    assert routes.loc[1, "implied"] == pytest.approx(3.5) and routes.loc[4, "implied"] == pytest.approx(1.4)
    assert routes.loc[2, "diff_min"] == pytest.approx(0.4)
    assert summary["ratio_median"] == pytest.approx(6 / 5.6) and summary["implied_median"] == pytest.approx(1.5)


def test_compare_drops_routes_without_an_app_time_and_sorts_worst_first() -> None:
    routes, summary = compare(app_sheet(), multiplier=1.4)
    assert list(routes.route) == [1, 2, 4]
    assert summary["n"] == 3 and summary["n_no_app"] == 1
    assert summary["ratio_min"] == pytest.approx(1.0) and summary["ratio_max"] == pytest.approx(2.5)


def test_compare_bad_snap_split_and_ranks() -> None:
    _, summary = compare(app_sheet(), multiplier=1.4)
    assert summary["ratio_median_bad"] == pytest.approx(1.75) and summary["ratio_median_other"] == pytest.approx(6 / 5.6)
    assert summary["bad_snap_ranks"] == {1: 1, 4: 3}


def test_compare_uses_the_multiplier_argument_not_model_min() -> None:
    routes, _ = compare(app_sheet(), multiplier=2.0)
    assert routes.set_index("route").loc[4, "ratio"] == pytest.approx(14 / 20)
