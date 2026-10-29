import h3
import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

POLY = box(77.045, 28.445, 77.055, 28.455)   # ~1 km box: a handful of res-9 hexes


def write_tif(path, arr, pixel, nodata):
    with rasterio.open(path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1,
                       dtype="float32", crs="EPSG:4326", transform=from_origin(77.04, 28.46, pixel, pixel),
                       nodata=nodata) as dst:
        dst.write(arr.astype("float32"), 1)
    return path


def make_rasters(tmp_path):
    """WorldPop-like 100 m pixels (40x40) and coarser VIIRS-like pixels (10x10), covering POLY."""
    rng = np.random.default_rng(0)
    wp = write_tif(tmp_path / "wp.tif", rng.integers(0, 50, (40, 40)) * 0.1 + 1, 0.0005, -99999)
    vi = write_tif(tmp_path / "vi.tif", np.arange(100).reshape(10, 10) + 1.0, 0.002, -9999)
    return wp, vi


RES = 9
FAR = 0.00005   # a far-side snap sits FAR degrees (~5 m, same hex) east of the point


class FakeRouter:
    """Snap j of a point is east + j * step degrees east of it, snap_m metres away. A pair takes `default` minutes
    unless `times` has (source hex, destination hex) or (source hex, source is a far-side snap, destination hex,
    destination is a far-side snap). Records the sources it is asked to time in `sources`."""
    peak_bytes = None

    def __init__(self, times=None, default=1.0, east=0.0, step=0.0, snap_m=0.0):
        self.times, self.default, self.east, self.step, self.snap_m = times or {}, default, east, step, snap_m

    def snap(self, lons, lats, k=1):
        lons = np.asarray(lons, float)[:, None] + self.east + self.step * np.arange(k)
        lats = np.asarray(lats, float)[:, None] + np.zeros(k)
        return lons, lats, np.full_like(lons, self.snap_m)

    def minutes(self, src_lons, src_lats, dst_lons, dst_lats):
        self.sources = (list(src_lons), list(src_lats))

        def side(lon, lat):
            cell = h3.latlng_to_cell(lat, lon, RES)
            return cell, bool(abs(lon - h3.cell_to_latlng(cell)[1]) > FAR / 2)
        src = [side(x, y) for x, y in zip(src_lons, src_lats)]
        dst = [side(x, y) for x, y in zip(dst_lons, dst_lats)]
        return np.array([[self.times.get((*s, *d), self.times.get((s[0], d[0]), self.default)) for d in dst]
                         for s in src], dtype=np.float32)


def four_snaps(src, dst, value):
    """The four far-side combinations of the pair (src, dst) with `value` minutes, or value(sf, df) if callable."""
    return {(src, sf, dst, df): value(sf, df) if callable(value) else value for sf in (False, True) for df in (False, True)}
