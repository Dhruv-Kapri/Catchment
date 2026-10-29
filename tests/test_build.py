import pandas as pd
import pytest

from catchment import assumptions, build
from conftest import POLY, make_rasters


@pytest.fixture
def env(tmp_path, monkeypatch):
    wp, vi = make_rasters(tmp_path)
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
        open(path, "wb").write(b"half")
        raise OSError("disk full")
    monkeypatch.setattr(pd.DataFrame, "to_parquet", partial_write)
    with pytest.raises(OSError):
        build.main(["demand"])
    assert not (env / "demand-r9.parquet").exists()
