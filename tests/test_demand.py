import h3
import numpy as np
import pandas as pd
import pytest

from catchment import assumptions
from catchment.demand import build_demand
from conftest import POLY, make_rasters, write_tif


@pytest.fixture
def rasters(tmp_path):
    return make_rasters(tmp_path)


def test_hexes_are_area_hexes_sorted(rasters):
    df = build_demand(POLY, 9, *rasters)
    assert df.index.name == "hex"
    assert list(df.index) == sorted(h3.geo_to_cells(POLY, 9))
    assert 3 <= len(df) < 30


def test_columns_and_res_attr(rasters):
    df = build_demand(POLY, 9, *rasters)
    assert list(df.columns) == ["lat", "lon", "population", "households", "radiance", "multiplier", "demand"]
    assert df.attrs["res"] == 9


def test_hex_centres_are_lat_lon(rasters):
    df = build_demand(POLY, 9, *rasters)
    for h, row in df.iterrows():
        assert (row.lat, row.lon) == pytest.approx(h3.cell_to_latlng(h))


def test_population_is_pixels_in_hex(rasters):
    from catchment.load import worldpop_pixels
    df = build_demand(POLY, 9, *rasters)
    wp = worldpop_pixels(rasters[0])
    expected = wp["pop"].groupby([h3.latlng_to_cell(y, x, 9) for x, y in zip(wp.lon, wp.lat)]).sum()
    assert (df.population > 0).all()
    assert np.allclose(df.population, expected.reindex(df.index))


def test_households_are_population_over_household_size(rasters):
    df = build_demand(POLY, 9, *rasters)
    assert np.allclose(df.households, df.population / assumptions.HOUSEHOLD_SIZE)


def test_household_size_is_read_from_assumptions(rasters, monkeypatch):
    base = build_demand(POLY, 9, *rasters).households
    monkeypatch.setattr(assumptions, "HOUSEHOLD_SIZE", 9.0)
    assert np.allclose(build_demand(POLY, 9, *rasters).households, base / 2)


def test_nan_radiance_takes_the_minimum(tmp_path):
    wp, _ = make_rasters(tmp_path)
    arr = np.arange(100).reshape(10, 10) + 5.0
    arr[:, :5] = -9999
    vi = write_tif(tmp_path / "vn.tif", arr, 0.002, -9999)
    df = build_demand(POLY, 9, wp, vi)
    assert not df.radiance.isna().any()
    assert df.radiance.min() >= 5.0


def test_multipliers_hit_bounds_and_follow_radiance(rasters):
    df = build_demand(POLY, 9, *rasters)
    assert df.multiplier.min() == pytest.approx(assumptions.M_LOW)
    assert df.multiplier.max() == pytest.approx(assumptions.M_HIGH)
    m = df.sort_values("radiance").multiplier.to_numpy()
    assert (np.diff(m) >= -1e-12).all()


def test_multiplier_bounds_are_read_from_assumptions(rasters, monkeypatch):
    monkeypatch.setattr(assumptions, "M_LOW", 0.8)
    monkeypatch.setattr(assumptions, "M_HIGH", 1.2)
    df = build_demand(POLY, 9, *rasters)
    assert df.multiplier.min() == pytest.approx(0.8) and df.multiplier.max() == pytest.approx(1.2)


def test_flat_radiance_gives_midpoint_multiplier(tmp_path):
    wp, _ = make_rasters(tmp_path)
    vi = write_tif(tmp_path / "flat.tif", np.full((10, 10), 3.0), 0.002, -9999)
    df = build_demand(POLY, 9, wp, vi)
    assert (df.multiplier == (assumptions.M_LOW + assumptions.M_HIGH) / 2).all()
