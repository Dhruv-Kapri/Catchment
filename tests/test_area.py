from typing import Any

import numpy as np
import pytest
import shapely
from pyproj import Transformer

from catchment.area import load_area, relation_to_geometry


def way(*pts: tuple[float, float], role: str) -> dict[str, Any]:
    return {"role": role, "type": "way", "geometry": [{"lat": y, "lon": x} for x, y in pts]}


def test_outer_ring_from_two_ways() -> None:
    rel = {"members": [
        way((0, 0), (1, 0), (1, 1), role="outer"),
        way((1, 1), (0, 1), (0, 0), role="outer"),
    ]}
    g = relation_to_geometry(rel)
    assert g.geom_type == "Polygon" and g.is_valid
    assert g.area == pytest.approx(1.0)


def test_ways_joined_with_reversed_direction() -> None:
    rel = {"members": [
        way((0, 0), (1, 0), (1, 1), role="outer"),
        way((0, 0), (0, 1), (1, 1), role="outer"),
    ]}
    assert relation_to_geometry(rel).area == pytest.approx(1.0)


def test_inner_ring_becomes_hole() -> None:
    rel = {"members": [
        way((0, 0), (4, 0), (4, 4), (0, 4), (0, 0), role="outer"),
        way((1, 1), (2, 1), (2, 2), (1, 2), (1, 1), role="inner"),
    ]}
    g = relation_to_geometry(rel)
    assert g.area == pytest.approx(15.0)
    assert len(g.interiors) == 1


def test_two_outer_rings_make_multipolygon() -> None:
    rel = {"members": [
        way((0, 0), (1, 0), (1, 1), (0, 1), (0, 0), role="outer"),
        way((5, 5), (6, 5), (6, 6), (5, 6), (5, 5), role="outer"),
    ]}
    g = relation_to_geometry(rel)
    assert g.geom_type == "MultiPolygon" and len(g.geoms) == 2


def test_committed_area_is_valid_and_right_size() -> None:
    g = load_area()
    assert g.is_valid
    to_utm = Transformer.from_crs(4326, 32643, always_xy=True).transform
    utm = shapely.transform(g, lambda c: np.column_stack(to_utm(c[:, 0], c[:, 1])))
    assert 500 < utm.area / 1e6 < 560
    minx, miny, maxx, maxy = g.bounds
    assert 76.8 < minx < 76.95 and 77.2 < maxx < 77.3
    assert 28.3 < miny < 28.36 and 28.55 < maxy < 28.62
