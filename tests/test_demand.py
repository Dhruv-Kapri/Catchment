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
