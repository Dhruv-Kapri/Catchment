import contextlib
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest

from catchment import assumptions, build
from conftest import POLY, FakeRouter, make_rasters


@pytest.fixture
def env(tmp_path, monkeypatch):
    wp, vi = make_rasters(tmp_path)
    places = tmp_path / "overture_places.parquet"
    gpd.GeoDataFrame({"operating_status": [None, None, "permanently_closed"]},
                     geometry=gpd.points_from_xy([77.05, 77.048, 77.052], [28.45, 28.452, 28.448]), crs=4326).to_parquet(places)
    monkeypatch.setattr(build, "PLACES", places)
    monkeypatch.setattr(build, "served_osrm", lambda data_dir: contextlib.nullcontext(FakeRouter()))
    monkeypatch.setattr(build, "DATA", tmp_path)
    monkeypatch.setattr(build, "WORLDPOP", wp)
    monkeypatch.setattr(build, "VIIRS", vi)
    monkeypatch.setattr(build, "load_area", lambda: POLY)
    return tmp_path


def test_demand_writes_res_named_parquet(env):
    assert build.main(["demand"]) == 0
    assert (env / "demand-r9.parquet").exists()


def test_stored_capture_share_is_readable_from_the_file(env):
    build.main(["demand"])
    back = pd.read_parquet(env / "demand-r9.parquet")
    assert back.attrs["res"] == 9
    assert back.demand.sum() / back.households.sum() == pytest.approx(assumptions.ORDERS_PER_HOUSEHOLD_DAY)
    mean_m = (back.multiplier * back.households).sum() / back.households.sum()
    assert back.attrs["capture_share"] == pytest.approx(assumptions.ORDERS_PER_HOUSEHOLD_DAY / mean_m)


def test_prints_a_summary_with_the_capture_share(env, capsys):
    build.main(["demand"])
    assert "capture share" in capsys.readouterr().err


def test_write_is_atomic(env, monkeypatch):
    def partial_write(self, path, *a, **k):
        Path(path).write_bytes(b"half")
        raise OSError("disk full")
    monkeypatch.setattr(pd.DataFrame, "to_parquet", partial_write)
    with pytest.raises(OSError):
        build.main(["demand"])
    assert not (env / "demand-r9.parquet").exists()


def test_res_writes_a_separate_file(env):
    build.main(["demand"])
    build.main(["demand", "--res", "8"])
    assert (env / "demand-r8.parquet").exists()
    d9, d8 = pd.read_parquet(env / "demand-r9.parquet"), pd.read_parquet(env / "demand-r8.parquet")
    assert d8.attrs["res"] == 8 and len(d8) < len(d9)


def test_existing_output_is_skipped(env, capsys):
    build.main(["demand"])
    out = env / "demand-r9.parquet"
    out.write_bytes(b"sentinel")
    assert build.main(["demand"]) == 0
    assert out.read_bytes() == b"sentinel" and "skipping" in capsys.readouterr().err


def test_force_rebuilds_an_existing_output(env):
    out = env / "demand-r9.parquet"
    out.write_bytes(b"sentinel")
    assert build.main(["demand", "--force"]) == 0
    assert out.read_bytes() != b"sentinel"
    assert pd.read_parquet(out).attrs["res"] == 9


def test_default_runs_every_stage(env):
    build.main([])
    assert (env / "demand-r9.parquet").exists()
    assert (env / "candidates-r9-x30.parquet").exists() and (env / "table-r9-x30.parquet").exists()


def test_reach_writes_candidates_and_table_named_by_res_and_x(env):
    assert build.main(["reach"]) == 0
    assert (env / "candidates-r9-x30.parquet").exists() and (env / "table-r9-x30.parquet").exists()
    candidates = pd.read_parquet(env / "candidates-r9-x30.parquet")
    table = pd.read_parquet(env / "table-r9-x30.parquet")
    assert len(candidates) == 2 and list(table.columns) == ["candidate", "hex", "minutes"]
    assert set(table.candidate) == set(candidates.index)


def test_x_pct_writes_a_separate_file_named_by_x(env):
    build.main(["reach"])
    build.main(["reach", "--x-pct", "2.5"])
    assert (env / "candidates-r9-x2.5.parquet").exists() and (env / "table-r9-x2.5.parquet").exists()
    assert pd.read_parquet(env / "candidates-r9-x2.5.parquet").attrs["x_pct"] == 2.5
    assert (env / "candidates-r9-x30.parquet").exists()


def test_reach_builds_a_missing_demand_table_first(env):
    assert not (env / "demand-r9.parquet").exists()
    build.main(["reach"])
    assert (env / "demand-r9.parquet").exists()
    assert pd.read_parquet(env / "demand-r9.parquet").attrs["res"] == 9


def test_reach_reads_an_existing_demand_table(env):
    build.main(["demand"])
    before = (env / "demand-r9.parquet").stat().st_mtime_ns
    build.main(["reach"])
    assert (env / "demand-r9.parquet").stat().st_mtime_ns == before


def test_reach_is_skipped_only_when_both_outputs_exist(env):
    build.main(["reach"])
    (env / "table-r9-x30.parquet").unlink()
    (env / "candidates-r9-x30.parquet").write_bytes(b"sentinel")
    build.main(["reach"])
    assert (env / "table-r9-x30.parquet").exists()
    assert (env / "candidates-r9-x30.parquet").read_bytes() != b"sentinel"


def test_reach_prints_counts_against_0_5_time_and_memory(env, capsys, monkeypatch):
    router = FakeRouter()
    router.peak_bytes = 123_000_000
    monkeypatch.setattr(build, "served_osrm", lambda data_dir: contextlib.nullcontext(router))
    build.main(["reach"])
    err = capsys.readouterr().err
    assert "2 candidate sites" in err and "pairs within 17 min" in err
    assert "against 0.5's extrapolation of about 1.40 M pairs" in err
    assert "wall time" in err and "peak RSS" in err and "osrm-routed peak 123 MB" in err


def test_demand_without_fetched_rasters_says_to_fetch_them(env, monkeypatch, capsys):
    monkeypatch.setattr(build, "WORLDPOP", env / "worldpop.tif")
    monkeypatch.setattr(build, "VIIRS", env / "viirs.tif")
    assert build.main(["demand"]) == 1
    err = capsys.readouterr().err
    assert "catchment-fetch worldpop viirs" in err and "worldpop.tif" in err and "viirs.tif" in err
    assert not (env / "demand-r9.parquet").exists()
