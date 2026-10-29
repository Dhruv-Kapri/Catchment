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
